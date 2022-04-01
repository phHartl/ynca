"""Test Zone subunit"""

from typing import Callable
from unittest import mock
import pytest
from ynca.constants import Avail

from ynca.subunit import SubunitBase
from ynca.errors import YncaInitializationFailedException

from .mock_yncaconnection import YncaConnectionMock


SYS = "SYS"
SUBUNIT = "SUBUNIT"

INITIALIZE_FULL_RESPONSES = [
    (
        (SUBUNIT, "AVAIL"),
        [
            (SUBUNIT, "AVAIL", "Ready"),
        ],
    ),
    (
        (SYS, "VERSION"),
        [
            (SYS, "VERSION", "Version"),
        ],
    ),
]

# Need a class with an ID to test some of the handling
class TestSubunit(SubunitBase):
    id = SUBUNIT


@pytest.fixture
def connection():
    c = YncaConnectionMock()
    c.setup_responses()
    return c


@pytest.fixture
def update_callback() -> Callable[[], None]:
    return mock.MagicMock()


@pytest.fixture
def initialized_SubunitBase(connection) -> TestSubunit:
    connection.get_response_list = INITIALIZE_FULL_RESPONSES
    sui = TestSubunit(connection)
    sui.initialize()
    return sui


def test_construct(connection, update_callback):

    sui = TestSubunit(connection)

    assert connection.register_message_callback.call_count == 1
    assert update_callback.call_count == 0


def test_initialize_fail(connection, update_callback):

    sui = TestSubunit(connection)
    sui.register_update_callback(update_callback)

    with pytest.raises(YncaInitializationFailedException):
        sui.initialize()

    assert update_callback.call_count == 0


def test_initialize(connection, update_callback):

    connection.get_response_list = INITIALIZE_FULL_RESPONSES

    sui = TestSubunit(connection)
    sui.register_update_callback(update_callback)

    sui.initialize()

    assert update_callback.call_count == 1
    assert sui.avail == Avail.READY


def test_unknown_functions_ignored(
    connection, initialized_SubunitBase, update_callback
):
    initialized_SubunitBase.register_update_callback(update_callback)
    connection.send_protocol_message(SUBUNIT, "UnknownFunction", "Value")
    assert update_callback.call_count == 0


def test_status_not_ok_ignored(connection, initialized_SubunitBase, update_callback):
    initialized_SubunitBase.register_update_callback(update_callback)
    connection.send_protocol_error("@UNDEFINED")
    assert update_callback.call_count == 0
    connection.send_protocol_error("@RESTRICTED")
    assert update_callback.call_count == 0
