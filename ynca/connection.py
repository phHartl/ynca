import logging
import queue
import re
import threading
import time
from enum import Enum
from typing import Callable, Optional, Set

import serial  # type: ignore
import serial.threaded  # type: ignore

from .errors import YncaConnectionError

logger = logging.getLogger(__name__)


class YncaProtocolStatus(Enum):
    OK = 0
    UNDEFINED = 1
    RESTRICTED = 2


class YncaProtocol(serial.threaded.LineReader):

    # YNCA spec specifies that there should be at least 100 milliseconds between commands
    COMMAND_SPACING = 0.1

    # YNCA spec says standby timeout is 40 seconds, so use a shorter period to be on the safe side
    KEEP_ALIVE_INTERVAL = 30

    def __init__(self):
        super().__init__()
        self.message_callback = None
        self.disconnect_callback = None
        self._send_queue = None
        self._send_thread = None
        self._last_sent_command = None
        self.connected = False
        self._keep_alive_pending = False
        self.num_commands_sent = 0

    def connection_made(self, transport):
        super().connection_made(transport)

        logger.debug("Connected")

        self._send_queue = queue.Queue()
        self._send_thread = threading.Thread(target=self._send_handler)
        self._send_thread.start()

        self.connected = True
        self._keep_alive_pending = False

        # When the device is in low power mode the first command is to wake up and gets lost
        # So send a dummy keep-alive on connect and a real one to make sure keep-alive administration is up-to-date
        self._send_keepalive()
        self._send_keepalive()

    def connection_lost(self, exc):
        self.connected = False

        logger.debug("Connection closed/lost")

        # There seems to be no way to clear a queue so just read all and add the _EXIT command
        try:
            while self._send_queue.get(False):
                pass
        except queue.Empty:
            self._send_queue.put("_EXIT")
        self._send_thread.join(2)

        if exc:
            logger.error(exc)

        if self.disconnect_callback:
            self.disconnect_callback()

    def handle_line(self, line):
        ignore = False
        status = YncaProtocolStatus.OK
        subunit = None
        function = None
        value = None

        logger.debug("< %s", line)

        if line == "@UNDEFINED":
            status = YncaProtocolStatus.UNDEFINED
        elif line == "@RESTRICTED":
            status = YncaProtocolStatus.RESTRICTED

        match = re.match(r"@(?P<subunit>.+?):(?P<function>.+?)=(?P<value>.*)", line)
        if match is not None:
            subunit = match.group("subunit")
            function = match.group("function")
            value = match.group("value")

            if (
                self._keep_alive_pending
                and subunit == "SYS"
                and function == "MODELNAME"
            ):
                ignore = True

        self._keep_alive_pending = False

        if not ignore and self.message_callback is not None:
            self.message_callback(status, subunit, function, value)

    def _send_keepalive(self):
        self._send_queue.put("_KEEP_ALIVE")

    def _send_handler(self):
        stop = False
        while not stop:
            try:
                message = self._send_queue.get(True, self.KEEP_ALIVE_INTERVAL)

                if message == "_EXIT":
                    stop = True
                elif message == "_KEEP_ALIVE":
                    message = "@SYS:MODELNAME=?"  # This message is suggested by YNCA spec for keep-alive
                    self._keep_alive_pending = True

                if not stop:
                    logger.debug("> %s", message)

                    self._last_sent_command = message
                    self.write_line(message)
                    time.sleep(
                        self.COMMAND_SPACING
                    )  # Maintain required command spacing
            except queue.Empty:
                # To avoid random message being eaten because device goes to sleep, keep it alive
                self._send_keepalive()

    def put(self, subunit, funcname, parameter):
        self._send_queue.put(f"@{subunit}:{funcname}={parameter}")
        self.num_commands_sent += 1

    def get(self, subunit, funcname):
        self.put(subunit, funcname, "?")


class YncaConnection:
    @classmethod
    def create_from_serial_url(cls, serial_url):
        return cls(serial_url)

    def __init__(
        self,
        serial_url: str,
    ):
        """Instantiate a YncaConnection

        serial_url -- Can be a devicename (e.g. /dev/ttyUSB0 or COM3),
                      but also any of supported url handlers by pyserial
                      https://pyserial.readthedocs.io/en/latest/url_handlers.html
                      This allows to setup IP connections with socket://ip:50000
                      or select a specific usb-2-serial with hwgrep:// which is
                      useful when the links to ttyUSB# change randomly.
        """
        self._port = serial_url
        self._serial = None
        self._readerthread: Optional[serial.threaded.ReaderThread] = None
        self._protocol: Optional[YncaProtocol] = None

        self._message_callbacks: Set[
            Callable[[YncaProtocolStatus, str, str, str], None]
        ] = set()

    def register_message_callback(
        self, callback: Callable[[YncaProtocolStatus, str, str, str], None]
    ):
        self._message_callbacks.add(callback)

    def unregister_message_callback(
        self, callback: Callable[[YncaProtocolStatus, str, str, str], None]
    ):
        self._message_callbacks.remove(callback)

    def _call_registered_message_callbacks(
        self, status: YncaProtocolStatus, subunit: str, function_: str, value: str
    ):
        for callback in self._message_callbacks:
            callback(status, subunit, function_, value)

    def connect(self, disconnect_callback: Callable[[], None] = None):
        try:
            self._serial = serial.serial_for_url(self._port)
            self._readerthread = serial.threaded.ReaderThread(
                self._serial, YncaProtocol
            )
            self._readerthread.start()
            _, self._protocol = self._readerthread.connect()
        except serial.SerialException as e:
            raise YncaConnectionError(e)

        if self._protocol:
            self._protocol.message_callback = self._call_registered_message_callbacks
            self._protocol.disconnect_callback = disconnect_callback

    def close(self):
        # Disconnect callback is for unexpected disconnects
        # Don't need it to be called on planned `close()`
        self._protocol.disconnect_callback = None

        if self._readerthread:
            self._readerthread.close()

    def put(self, subunit: str, funcname: str, parameter: str):
        if self._protocol:
            self._protocol.put(subunit, funcname, parameter)

    def get(self, subunit: str, funcname: str):
        if self._protocol:
            self._protocol.get(subunit, funcname)

    @property
    def connected(self):
        return self._protocol.connected

    @property
    def num_commands_sent(self):
        return self._protocol.num_commands_sent
