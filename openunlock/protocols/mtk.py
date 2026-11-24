"""MediaTek BootROM / preloader protocol scaffolding.

Implements the PUBLIC, documented parts of the MTK BootROM protocol as
found in the open-source mtkclient project (GPLv3,
https://github.com/bkerler/mtkclient — see mtkclient/Library/
mtk_preloader.py) and the da-boot project. No proprietary Download Agent
(DA) blobs are included or downloaded — the user supplies their own DA
for their chipset via --loader, exactly as mtkclient requires.

Verified constants (sources: mtkclient mtk_preloader.py via DeepWiki
documentation; DeepEyeUnlocker BROM_HANDSHAKE_FIX.md; da-boot handshake):
* USB VID 0x0e8d; PIDs: BROM 0x0003, preloader 0x2000, download 0x0001,
  DA mode 0x200A.
* Handshake: FOUR separate single-byte exchanges, in order:
  0xA0 -> 0x5F, 0x0A -> 0xF5, 0x50 -> 0xAF, 0x05 -> 0xFA.
  (Sending the 4 bytes as one packet is WRONG — each byte after the
  first is treated as a new command and the session desyncs.)
* GET_HW_CODE = 0xFD: returns 4 bytes, big-endian; upper 16 bits are the
  hwcode (e.g. 0x6789 = MT6789), lower 16 bits the hwver.
* GET_TARGET_CONFIG = 0xD8: bitmask — SBC 0x1, SLA 0x2, DAA 0x4.
* SEND_AUTH = 0xE2: sends the auth file when DAA is enabled.
* USBDL_MAGIC = 0x444C0000. Responses: ACK 0x5A, NACK 0xA5.
* CMD_READ16_A2 = 0xA2 (IoT chips: read hwver from registers).

Limits, stated plainly:
* MT678x/MT689x/MT688x/MT698x use the V6 protocol and need a valid DA.
* Devices with DAA/SLA/Remote-Auth enabled have NO public solution.
* Newer chips (Dimensity 9000+, e.g. MT6895/MT6983) have patched
  BootROMs; the classic exploit does not apply. Dimensity 9500 devices
  are in this category — BROM access needs a valid DA and auth.
* Actual flash read/write delegates to mtkclient when installed
  (`mtk` on PATH). This module frames the handshake and parses the
  replies; it does not reimplement the DA protocol.
"""
import re
import struct

from .. import runner
from ..errors import OpenUnlockError
from .base import ProtocolPlugin

MTKCLIENT = "https://github.com/bkerler/mtkclient"

VID_MTK = 0x0E8D
PID_MODES = {
    0x0003: "brom",
    0x2000: "preloader",
    0x0001: "download",
    0x200A: "da",
}

# Four separate single-byte exchanges — never one 4-byte packet.
HANDSHAKE = ((0xA0, 0x5F), (0x0A, 0xF5), (0x50, 0xAF), (0x05, 0xFA))

CMD_GET_HW_CODE = 0xFD
CMD_GET_TARGET_CONFIG = 0xD8
CMD_SEND_AUTH = 0xE2
CMD_READ16_A2 = 0xA2
USBDL_MAGIC = 0x444C0000

RSP_ACK = 0x5A
RSP_NACK = 0xA5

# GET_TARGET_CONFIG bitmask
FLAG_SBC = 0x01  # Secure Boot Control
FLAG_SLA = 0x02  # Serial Link Authentication
FLAG_DAA = 0x04  # Download Agent Authentication


def handshake_sequence():
    """Return the BROM handshake as [(send_byte, expect_byte), ...]."""
    return list(HANDSHAKE)


def build_get_hw_code():
    """One-byte GET_HW_CODE command."""
    return bytes([CMD_GET_HW_CODE])


def parse_hw_code(resp):
    """Parse a 4-byte GET_HW_CODE reply -> (hwcode, hwver), big-endian."""
    if len(resp) < 4:
        raise OpenUnlockError(
            f"GET_HW_CODE reply too short: {resp.hex()}")
    hwcode, hwver = struct.unpack(">HH", resp[:4])
    return hwcode, hwver


def parse_target_config(byte):
    """Parse the GET_TARGET_CONFIG bitmask into named flags."""
    return {
        "raw": byte,
        "sbc": bool(byte & FLAG_SBC),
        "sla": bool(byte & FLAG_SLA),
        "daa": bool(byte & FLAG_DAA),
        "needs_auth": bool(byte & FLAG_DAA),
    }


def detect_usb():
    """Find MTK devices in BROM/preloader/download/DA mode.

    Uses pyusb when installed, otherwise parses `lsusb` output.
    Returns [{vid, pid, mode}].
    """
    found = []
    try:
        import usb.core  # pyusb, optional
        for dev in usb.core.find(find_all=True):
            if dev.idVendor == VID_MTK and dev.idProduct in PID_MODES:
                found.append({"vid": dev.idVendor, "pid": dev.idProduct,
                              "mode": PID_MODES[dev.idProduct]})
        return found
    except ImportError:
        pass
    rc, out = runner.run_quiet(["lsusb"])
    if rc != 0:
        return found
    for line in out.splitlines():
        m = re.search(r"ID\s+([0-9a-fA-F]{4}):([0-9a-fA-F]{4})", line)
        if m:
            vid, pid = int(m.group(1), 16), int(m.group(2), 16)
            if vid == VID_MTK and pid in PID_MODES:
                found.append({"vid": vid, "pid": pid,
                              "mode": PID_MODES[pid]})
    return found


class MtkPlugin(ProtocolPlugin):
    name = "mtkclient (MediaTek BootROM)"
    chipsets = ["mt6765", "mt6768", "mt6785", "mt6789", "mt6833", "mt6853",
                "mt6873", "mt6877", "mt6893", "mt6983", "mt6895", "mt6985"]

    def detect(self):
        return bool(detect_usb())

    def device_info(self):
        devs = detect_usb()
        if not devs:
            raise OpenUnlockError(
                "No MediaTek device in BROM/preloader mode. Power off, "
                "hold Vol Up or Vol Down, plug in USB.")
        return {"devices": devs,
                "note": "Run GET_HW_CODE (0xFD) after the handshake to "
                        "identify the exact chipset."}

    def _delegate(self, args):
        """Delegate a flash operation to mtkclient when installed."""
        rc, text = runner.run_quiet(["mtk"] + args)
        if rc != 0:
            raise OpenUnlockError(
                "mtkclient failed or is not installed. Install it: "
                f"{MTKCLIENT} — then put the phone in BROM mode and retry. "
                f"Output: {text.strip()}")
        return text

    def read_partition(self, partition, out_path):
        return self._delegate(["r", partition, out_path])

    def write_partition(self, partition, image_path):
        return self._delegate(["w", partition, image_path])

    def restore_imei(self, backup_data, serial):
        raise OpenUnlockError(
            "MTK IMEI restore needs mtkclient plus the device's own NVRAM "
            "backup: restore the nvram/nvdata partitions from the backup "
            "with `mtk w nvram <file>` / `mtk w nvdata <file>` in BROM "
            "mode. OpenUnlock will not write IMEI values itself — the "
            "backup file is the only source of the original values.")
