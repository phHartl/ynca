"""
Simple socket server to test without a YNCA device

Note that it just responds to commands and does not implement
special interactions like when turning on a ZONE the SYS unit turns on.

It is intended to be just enough to test without a real device
"""

import argparse
from collections import namedtuple
import logging
import re
import socketserver
from typing import Tuple

RESTRICTED = "@RESTRICTED"
UNDEFINED = "@UNDEFINED"
OK = "OK"

YncaCommand = namedtuple("YncaCommand", ["subunit", "function", "value"])


def line_to_command(line):
    match = re.search(r"@(?P<subunit>.+?):(?P<function>.+?)=(?P<value>.*)", line)
    if match is not None:
        subunit = match.group("subunit")
        function = match.group("function")
        value = match.group("value")
        return YncaCommand(subunit, function, value)
    return None


class YncaDataStore:
    def __init__(self) -> None:
        self._store = {}

    def fill_from_file(self, filename):
        print(f"--- Filling store with data from file: {filename}")
        command = None
        with open(filename) as file:
            for line in file:
                line = line.strip()
                # Error values are stored based on command sent on previous line
                if RESTRICTED in line or UNDEFINED in line:
                    # Only set RESTRICTED or UNDEFINED for non existing entries
                    # Avoids "removal" of valid values e.g. when subunit got turned off
                    if self.get_data(command.subunit, command.function) == UNDEFINED:
                        self.add_data(
                            command.subunit,
                            command.function,
                            RESTRICTED if RESTRICTED in line else UNDEFINED,
                        )
                else:
                    command = line_to_command(line)
                    if command is not None and command.value != "?":
                        self.add_data(command.subunit, command.function, command.value)

    def add_data(self, subunit, function, value):
        if subunit not in self._store:
            self._store[subunit] = {}
        self._store[subunit][function] = value

    def get_data(self, subunit, function):
        try:
            value = self._store[subunit][function]
        except KeyError:
            return UNDEFINED
        return value

    def put_data(self, subunit, function, new_value):
        """Write new value, returns tuple with result and if value changed in case of OK"""
        try:
            if subunit in self._store:
                old_value = self._store[subunit][function]
                if old_value is None or new_value not in [UNDEFINED, RESTRICTED]:
                    self._store[subunit][function] = new_value
                return (OK, old_value != new_value)
        except KeyError:
            return (UNDEFINED, False)
        return (RESTRICTED, False)


class YncaCommandHandler(socketserver.StreamRequestHandler):
    """
    The request handler class for our server.

    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """

    def __init__(self, request, client_address, server):
        self.store = server.store
        super().__init__(request, client_address, server)

    def write_line(self, line: str):
        print(f"< {line}")
        line += "\r\n"
        self.wfile.write(line.encode("utf-8"))

    def handle_get(self, subunit, function, skip_error_response=False):

        # Some GET commands result in multple reponses
        if subunit == "SYS" and function == "INPNAME":
            sys_values = self.store._store["SYS"]
            for key in sys_values.keys():
                if key.startswith("INPNAME") and key != "INPNAME":
                    self.handle_get(subunit, key)
            return
        elif function == "BASIC":  # Only applies to zones, but should be good enough
            for basic_function in [
                "PWR",
                "SLEEP",
                "VOL",
                "MUTE",
                "INP",
                "STRAIGHT",
                "ENHANCER",
                "SOUNDPRG",
                "3DCINEMA",
                "PUREDIRMODE",
                "SPBASS",
                "SPTREBLE",
                "ADAPTIVEDRC",
            ]:
                self.handle_get(subunit, basic_function, skip_error_response=True)
            return
        elif function == "SCENENAME":
            response_sent = False
            subunit_values = self.store._store[subunit]
            for key in subunit_values.keys():
                if (
                    key.startswith("SCENE")
                    and key.endswith("NAME")
                    and key != "SCENENAME"
                ):
                    self.handle_get(subunit, key)
                    response_sent = True
            if not response_sent:
                self.write_line(RESTRICTED)
            return

        # Standard handling
        value = self.store.get_data(subunit, function)
        if value.startswith("@"):
            if not skip_error_response:
                self.write_line(value)
        else:
            self.write_line(f"@{subunit}:{function}={value}")

    def handle_put(self, subunit, function, value):
        result = self.store.put_data(subunit, function, value)
        if result[0].startswith("@"):
            self.write_line(result[0])
        elif result[1]:
            # Value change so send a report
            self.write_line(f"@{subunit}:{function}={value}")

    def handle(self):
        # self.rfile is a file-like object created by the handler;
        # we can now use e.g. readline() instead of raw recv() calls
        #
        # Note that the connection is closed when this handler returns!

        print(f"--- Client connected from: {self.client_address[0]}")
        while True:
            line = self.rfile.readline()
            if line == b"":
                print("--- Client disconnected")
                return
            line = line.strip()
            line = line.decode("utf-8")
            print(f"> {line}")

            command = line_to_command(line)
            if command is not None:
                if command.value == "?":
                    self.handle_get(command.subunit, command.function)
                else:
                    self.handle_put(command.subunit, command.function, command.value)


class YncaServer(socketserver.TCPServer):
    def __init__(self, server_address: Tuple[str, int], initfile=None) -> None:
        super().__init__(server_address, YncaCommandHandler)

        self.store = YncaDataStore()

        if initfile:
            self.store.fill_from_file(initfile)
        else:
            # Minimum needed data to satisfy example.py script
            self.store.add_data("SYS", "MODELNAME", "ModelName")
            self.store.add_data("SYS", "VERSION", "Version")
            self.store.add_data("MAIN", "AVAIL", "Not ready")
            self.store.add_data("MAIN", "VOL", "0.0")
            self.store.add_data("MAIN", "ZONENAME", "ZoneName")
            self.store.add_data("ZONE2", "AVAIL", "Not ready")
            self.store.add_data("ZONE2", "ZONENAME", "ZoneName")


def main(args):
    # with socketserver.TCPServer((args.host, args.port), YncaCommandHandler) as server:
    with YncaServer((args.host, args.port), args.initfile) as server:
        # Activate the server; this will keep running until you
        # interrupt the program with Ctrl-C

        print("--- Waiting for connections")

        server.timeout = None
        server.serve_forever()


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="YNCA server to emulate a device for testing."
    )
    parser.add_argument(
        "--host",
        help="Host interface to bind to, default is localhost",
        default="localhost",
    )
    parser.add_argument(
        "--port", help="Port to use, default is the standard port 50000", default=50000
    )

    parser.add_argument(
        "--initfile",
        help="File to use to initialize the YncaDatastore. Needs to contain Ynca command logging in format `> @SUBUNIT:FUNCTION=VALUE` for sent values, and `< @SUBUNIT:FUNCTION=VALUE`. E.g. output of example script with loglevel DEBUG.",
    )
    parser.add_argument(
        "--loglevel",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Define loglevel, default is INFO.",
    )

    args = parser.parse_args()

    logging.basicConfig(level=args.loglevel)

    main(args)
