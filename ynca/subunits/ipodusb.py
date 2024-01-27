from __future__ import annotations

from ..constants import Subunit
from ..subunit import SubunitBase
from . import MediaPlaybackMixins


class IpodUsb(MediaPlaybackMixins, SubunitBase):
    id = Subunit.IPODUSB
