from typing import Callable
from unittest import mock
import pytest

from ynca.constants import Mute, Subunit, SoundPrg, TwoChDecoder
from ynca.subunits.functions import Pwr
from ynca.subunits.zone import (
    Input,
    PureDirMode,
    Straight,
    ZoneBase,
    Main,
    Zone2,
    Zone3,
    Zone4,
)

from .mock_yncaconnection import YncaConnectionMock

SYS = "SYS"
SUBUNIT = "TESTZONE"
NUM_SCENES = 12

INITIALIZE_FULL_RESPONSES = [
    (
        (SUBUNIT, "AVAIL"),
        [
            (SUBUNIT, "AVAIL", "Ready"),
        ],
    ),
    (
        (SUBUNIT, "BASIC"),
        [
            (SUBUNIT, "PWR", "Standby"),
            (SUBUNIT, "SLEEP", "Off"),
            (SUBUNIT, "VOL", "-30.0"),
            (SUBUNIT, "MUTE", "Off"),
            (SUBUNIT, "INP", "HDMI1"),
            (SUBUNIT, "STRAIGHT", "Off"),
            (SUBUNIT, "ENHANCER", "On"),
            (SUBUNIT, "SOUNDPRG", "Standard"),
            (SUBUNIT, "3DCINEMA", "Auto"),
            (SUBUNIT, "PUREDIRMODE", "Off"),
            (SUBUNIT, "SPBASS", "4"),
            (SUBUNIT, "SPTREBLE", "-4"),
            (SUBUNIT, "ADAPTIVEDRC", "Off"),
        ],
    ),
    (
        (SUBUNIT, "MAXVOL"),
        [
            (SUBUNIT, "MAXVOL", "1.2"),
        ],
    ),
    (
        (SUBUNIT, "SCENENAME"),
        [
            (SUBUNIT, "SCENE1NAME", "Scene name 1"),
            (SUBUNIT, "SCENE2NAME", "Scene name 2"),
            (SUBUNIT, "SCENE3NAME", "Scene name 3"),
            (SUBUNIT, "SCENE4NAME", "Scene name 4"),
            (SUBUNIT, "SCENE5NAME", "Scene name 5"),
            (SUBUNIT, "SCENE6NAME", "Scene name 6"),
            (SUBUNIT, "SCENE7NAME", "Scene name 7"),
            (SUBUNIT, "SCENE8NAME", "Scene name 8"),
            (SUBUNIT, "SCENE9NAME", "Scene name 9"),
            (SUBUNIT, "SCENE10NAME", "Scene name 10"),
            (SUBUNIT, "SCENE11NAME", "Scene name 11"),
            (SUBUNIT, "SCENE12NAME", "Scene name 12"),
        ],
    ),
    (
        (SUBUNIT, "2CHDECODER"),
        [
            (SUBUNIT, "2CHDECODER", "Dolby PLIIx Movie"),
        ],
    ),
    (
        (SUBUNIT, "ZONENAME"),
        [
            (SUBUNIT, "ZONENAME", "ZoneName"),
        ],
    ),
    (
        (SYS, "VERSION"),
        [
            (SYS, "VERSION", "Version"),
        ],
    ),
]


# Need a zone class with an id for testing
class DummyZone(ZoneBase):
    id = "TESTZONE"


@pytest.fixture
def connection():
    c = YncaConnectionMock()
    c.setup_responses()
    return c


@pytest.fixture
def update_callback() -> Callable[[], None]:
    return mock.MagicMock()


@pytest.fixture
def initialized_zone(connection) -> ZoneBase:
    connection.get_response_list = INITIALIZE_FULL_RESPONSES
    z = DummyZone(connection)
    z.initialize()
    return z


def test_construct(connection, update_callback):

    DummyZone(connection)

    assert connection.register_message_callback.call_count == 1
    assert update_callback.call_count == 0


def test_construct_specific_zones(connection):

    # Just grabbing coverage :/
    z = Main(connection)
    z.id = Subunit.MAIN
    z = Zone2(connection)
    z.id = Subunit.ZONE2
    z = Zone3(connection)
    z.id = Subunit.ZONE3
    z = Zone4(connection)
    z.id = Subunit.ZONE4


def test_initialize_minimal(connection, update_callback):
    connection.get_response_list = [
        (
            (SUBUNIT, "ZONENAME"),
            [
                (SUBUNIT, "ZONENAME", "ZoneName"),
            ],
        ),
        (
            (SYS, "VERSION"),
            [
                (SYS, "VERSION", "Version"),
            ],
        ),
    ]

    z = DummyZone(connection)
    z.register_update_callback(update_callback)
    z.unregister_update_callback(update_callback)

    z.initialize()

    assert update_callback.call_count == 0
    assert z.zonename == "ZoneName"
    assert z.pwr is None
    assert z.inp is None
    assert z.vol is None
    assert z.maxvol is None
    assert z.mute is None
    assert z.straight is None
    assert z.soundprg is None
    assert z.twochdecoder is None
    assert z.puredirmode is None
    for scene_id in range(1, NUM_SCENES + 1):
        assert getattr(z, f"scene{scene_id}name") is None


def test_initialize_full(connection, update_callback):

    connection.get_response_list = INITIALIZE_FULL_RESPONSES

    z = DummyZone(connection)
    z.register_update_callback(update_callback)

    z.initialize()

    assert z.pwr is Pwr.STANDBY
    assert z.inp == Input.HDMI1
    assert z.vol == -30.0
    assert z.maxvol == 1.2
    assert z.mute is Mute.OFF
    assert z.straight is Straight.OFF
    assert z.soundprg is SoundPrg.STANDARD
    assert z.zonename == "ZoneName"
    assert z.twochdecoder is TwoChDecoder.DolbyPl2xMovie
    assert z.puredirmode is PureDirMode.OFF

    for scene_id in range(1, NUM_SCENES + 1):
        assert getattr(z, f"scene{scene_id}name") == f"Scene name {scene_id}"


def test_mute(connection, initialized_zone: ZoneBase):
    # Writing to device
    initialized_zone.mute = Mute.ON
    connection.put.assert_called_with(SUBUNIT, "MUTE", "On")
    initialized_zone.mute = Mute.ATT_MINUS_20
    connection.put.assert_called_with(SUBUNIT, "MUTE", "Att -20 dB")
    initialized_zone.mute = Mute.ATT_MINUS_40
    connection.put.assert_called_with(SUBUNIT, "MUTE", "Att -40 dB")
    initialized_zone.mute = Mute.OFF
    connection.put.assert_called_with(SUBUNIT, "MUTE", "Off")

    # Updates from device
    connection.send_protocol_message(SUBUNIT, "MUTE", "On")
    assert initialized_zone.mute is Mute.ON
    connection.send_protocol_message(SUBUNIT, "MUTE", "Att -20 dB")
    assert initialized_zone.mute is Mute.ATT_MINUS_20
    connection.send_protocol_message(SUBUNIT, "MUTE", "Att -40 dB")
    assert initialized_zone.mute is Mute.ATT_MINUS_40
    connection.send_protocol_message(SUBUNIT, "MUTE", "Off")
    assert initialized_zone.mute is Mute.OFF


def test_volume(connection, initialized_zone: ZoneBase):
    # Writing to device

    # Positive with step rounding
    initialized_zone.vol = 0
    connection.put.assert_called_with(SUBUNIT, "VOL", "0.0")
    initialized_zone.vol = 0.1
    connection.put.assert_called_with(SUBUNIT, "VOL", "0.0")
    initialized_zone.vol = 0.4
    connection.put.assert_called_with(SUBUNIT, "VOL", "0.5")

    # Negative with step rounding
    initialized_zone.vol = -5
    connection.put.assert_called_with(SUBUNIT, "VOL", "-5.0")
    initialized_zone.vol = -0.5
    connection.put.assert_called_with(SUBUNIT, "VOL", "-0.5")
    initialized_zone.vol = -0.4
    connection.put.assert_called_with(SUBUNIT, "VOL", "-0.5")
    initialized_zone.vol = -0.1
    connection.put.assert_called_with(SUBUNIT, "VOL", "0.0")

    # Up
    initialized_zone.vol_up()
    connection.put.assert_called_with(SUBUNIT, "VOL", "Up")
    initialized_zone.vol_up(1)
    connection.put.assert_called_with(SUBUNIT, "VOL", "Up 1 dB")
    initialized_zone.vol_up(2)
    connection.put.assert_called_with(SUBUNIT, "VOL", "Up 2 dB")
    initialized_zone.vol_up(5)
    connection.put.assert_called_with(SUBUNIT, "VOL", "Up 5 dB")
    initialized_zone.vol_up(50)
    connection.put.assert_called_with(SUBUNIT, "VOL", "Up")

    # Down
    initialized_zone.vol_down()
    connection.put.assert_called_with(SUBUNIT, "VOL", "Down")
    initialized_zone.vol_down(1)
    connection.put.assert_called_with(SUBUNIT, "VOL", "Down 1 dB")
    initialized_zone.vol_down(2)
    connection.put.assert_called_with(SUBUNIT, "VOL", "Down 2 dB")
    initialized_zone.vol_down(5)
    connection.put.assert_called_with(SUBUNIT, "VOL", "Down 5 dB")
    initialized_zone.vol_down(50)
    connection.put.assert_called_with(SUBUNIT, "VOL", "Down")

    # Updates from device
    connection.send_protocol_message(SUBUNIT, "VOL", "0.0")
    assert initialized_zone.vol == 0
    connection.send_protocol_message(SUBUNIT, "VOL", "10.0")
    assert initialized_zone.vol == 10
    connection.send_protocol_message(SUBUNIT, "VOL", "-10.0")
    assert initialized_zone.vol == -10


def test_input(connection, initialized_zone: ZoneBase):
    # Writing to device
    initialized_zone.inp = Input.RHAPSODY
    connection.put.assert_called_with(SUBUNIT, "INP", "Rhapsody")

    # Updates from device
    connection.send_protocol_message(SUBUNIT, "INP", "Napster")
    assert initialized_zone.inp == Input.NAPSTER

    connection.send_protocol_message(SUBUNIT, "INP", "Some unknown input")
    assert initialized_zone.inp == Input.UNKNOWN


def test_soundprg(connection, initialized_zone: ZoneBase):
    # Writing to device
    initialized_zone.soundprg = SoundPrg.THE_ROXY_THEATRE
    connection.put.assert_called_with(SUBUNIT, "SOUNDPRG", "The Roxy Theatre")

    # Updates from device
    connection.send_protocol_message(SUBUNIT, "SOUNDPRG", "Sci-Fi")
    assert initialized_zone.soundprg == SoundPrg.SCI_FI

    connection.send_protocol_message(SUBUNIT, "SOUNDPRG", "Unmapped soundprg")
    assert initialized_zone.soundprg == SoundPrg.UNKNOWN


def test_straight(connection, initialized_zone: ZoneBase):
    # Writing to device
    initialized_zone.straight = Straight.ON
    connection.put.assert_called_with(SUBUNIT, "STRAIGHT", "On")
    initialized_zone.straight = Straight.OFF
    connection.put.assert_called_with(SUBUNIT, "STRAIGHT", "Off")

    # Updates from device
    connection.send_protocol_message(SUBUNIT, "STRAIGHT", "On")
    assert initialized_zone.straight == Straight.ON
    connection.send_protocol_message(SUBUNIT, "STRAIGHT", "Off")
    assert initialized_zone.straight == Straight.OFF


def test_scenerecall(connection, initialized_zone: ZoneBase):

    initialized_zone.scene_recall(42)
    connection.put.assert_called_with(SUBUNIT, "SCENE", "Scene 42")


def test_scenename(connection, initialized_zone: ZoneBase):

    # Updates from device
    connection.send_protocol_message(SUBUNIT, "SCENE3NAME", "New Name")
    assert initialized_zone.scene3name == "New Name"


def test_zonename(connection, initialized_zone: ZoneBase):
    # Writing to device
    initialized_zone.zonename = "new name"
    connection.put.assert_called_with(SUBUNIT, "ZONENAME", "new name")
    with pytest.raises(ValueError):
        initialized_zone.zonename = "new name is too long"

    # Updates from device
    connection.send_protocol_message(SUBUNIT, "ZONENAME", "updated")
    assert initialized_zone.zonename == "updated"


def test_twochdecoder(connection, initialized_zone: ZoneBase):
    # Writing to device
    initialized_zone.twochdecoder = TwoChDecoder.DolbyPl
    connection.put.assert_called_with(SUBUNIT, "2CHDECODER", "Dolby PL")

    # Updates from device
    connection.send_protocol_message(SUBUNIT, "2CHDECODER", "DTS NEO:6 Cinema")
    assert initialized_zone.twochdecoder is TwoChDecoder.DtsNeo6Cinema


def test_puredirmode(connection, initialized_zone: ZoneBase):
    # Writing to device
    initialized_zone.puredirmode = PureDirMode.ON
    connection.put.assert_called_with(SUBUNIT, "PUREDIRMODE", "On")
    initialized_zone.puredirmode = PureDirMode.OFF
    connection.put.assert_called_with(SUBUNIT, "PUREDIRMODE", "Off")

    # Updates from device
    connection.send_protocol_message(SUBUNIT, "PUREDIRMODE", "On")
    assert initialized_zone.puredirmode == PureDirMode.ON
    connection.send_protocol_message(SUBUNIT, "PUREDIRMODE", "Off")
    assert initialized_zone.puredirmode == PureDirMode.OFF
