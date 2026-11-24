"""Qualcomm Sahara + Firehose protocol scaffolding.

Implements the PUBLIC, documented framing of the Sahara protocol and the
Firehose XML command builders, as documented in the open-source edl
project (GPLv3, https://github.com/bkerler/edl — edlclient/Library/
sahara_defs.py, sahara.py, firehose.py), the linux-msm qdl project, and
the Linux kernel Sahara documentation. No firehose programmer (.elf/.mbn)
is included or downloaded — the user supplies their own programmer for
their exact chipset.

Verified constants:
* All values little-endian. Every packet starts with `u32 cmd; u32 len`.
* Commands: HELLO 0x01 (0x30), HELLO_RESP 0x02 (0x30), READ_DATA 0x03
  (0x14), END_OF_IMAGE 0x04 (0x10), DONE 0x05 (0x08), DONE_RESP 0x06
  (0x0c), RESET 0x07 (0x08), RESET_RESP 0x08 (0x08).
* Modes: IMAGE_TX_PENDING 0, IMAGE_TX_COMPLETE 1, MEMORY_DEBUG 2,
  COMMAND 3.
* HELLO_REQ: u32 version, compatible, max_len, mode, reserved[6]
  (total 0x30). HELLO_RESP: u32 version, compatible, status, mode,
  reserved[6].
* READ_DATA: u32 image, offset, length (0x14). READ_DATA64: u64 image,
  offset, length (0x20). END_OF_IMAGE: u32 image, status (0x10).
  DONE is empty (0x08). DONE_RESP: u32 status (0x0c).
  EXECUTE: u32 client_cmd (0x0c).
* Sahara V3 (newer devices): cmd 0x02 (MSM_HW_ID_READ) and 0x03
  (OEM_PK_HASH_READ) no longer respond; use cmd 0x0A (CHIP_ID_V3_READ)
  for extended chip info.
* EDL USB PID is 0x9008 (VID 0x05c6).
* Firehose functions (from the edl client): configure, program,
  firmwarewrite, patch, setbootablestoragedrive, ufs, emmc, power,
  benchmark, read, getstorageinfo, getcrc16digest, getsha256digest,
  erase, peek, poke, nop, xml.

Limits, stated plainly:
* The Sahara handshake only uploads a loader. The loader (firehose
  programmer) is device-specific and must be supplied by the user.
* Newer Qualcomm phones (Snapdragon 8 Elite Gen 5 family) need a valid
  signed loader; loader autodetection does not work on Sahara V3.
* Actual EDL read/write delegates to the edl client when installed.
"""
import re
import struct
import xml.etree.ElementTree as ET

from .. import runner
from ..errors import OpenUnlockError
from .base import ProtocolPlugin

EDLCLIENT = "https://github.com/bkerler/edl"

VID_QC = 0x05C6
PID_EDL = 0x9008

# Sahara command IDs
CMD_HELLO = 0x01
CMD_HELLO_RESP = 0x02
CMD_READ_DATA = 0x03
CMD_END_IMAGE = 0x04
CMD_DONE = 0x05
CMD_DONE_RESP = 0x06
CMD_RESET = 0x07
CMD_RESET_RESP = 0x08
CMD_EXEC = 0x0B
CMD_EXEC_RESP = 0x0C
CMD_EXEC_DATA = 0x0D

# Sahara V3 / command-mode queries
CMD_MSM_HW_ID_READ = 0x02
CMD_OEM_PK_HASH_READ = 0x03
CMD_CHIP_ID_V3_READ = 0x0A

# Modes
MODE_IMAGE_TX_PENDING = 0
MODE_IMAGE_TX_COMPLETE = 1
MODE_MEMORY_DEBUG = 2
MODE_COMMAND = 3

HELLO_LEN = 0x30
SAHARA_VERSION = 2
SAHARA_COMPATIBLE = 1
STATUS_SUCCESS = 0


def pack_header(cmd, length):
    """Sahara packet header: u32 cmd, u32 length, little-endian."""
    return struct.pack("<II", cmd, length)


def parse_packet_header(data):
    """Parse the 8-byte Sahara header -> (cmd, length)."""
    if len(data) < 8:
        raise OpenUnlockError("Sahara packet too short for a header.")
    return struct.unpack("<II", data[:8])


def parse_hello(data):
    """Parse a HELLO (0x01) packet from the target.

    Returns {'version', 'compatible', 'max_len', 'mode'}.
    """
    cmd, length = parse_packet_header(data)
    if cmd != CMD_HELLO:
        raise OpenUnlockError(f"Expected HELLO (0x01), got 0x{cmd:02x}.")
    if length != HELLO_LEN or len(data) < HELLO_LEN:
        raise OpenUnlockError(
            f"HELLO length should be 0x30, got 0x{length:x}.")
    version, compatible, max_len, mode = struct.unpack("<IIII", data[8:24])
    return {"version": version, "compatible": compatible,
            "max_len": max_len, "mode": mode}


def build_hello_response(mode=MODE_IMAGE_TX_PENDING,
                         version=SAHARA_VERSION,
                         compatible=SAHARA_COMPATIBLE,
                         max_len=0x400000):
    """Build the host's HELLO_RESP (0x02) packet: 48 bytes total."""
    body = struct.pack("<IIII", version, compatible, STATUS_SUCCESS, mode)
    body += struct.pack("<6I", 0, 0, 0, 0, 0, 0)  # reserved[6]
    return pack_header(CMD_HELLO_RESP, HELLO_LEN) + body


def parse_read_data(data):
    """Parse a READ_DATA (0x03) request -> {'image', 'offset', 'length'}."""
    cmd, length = parse_packet_header(data)
    if cmd != CMD_READ_DATA:
        raise OpenUnlockError(f"Expected READ_DATA (0x03), got 0x{cmd:02x}.")
    image, offset, length = struct.unpack("<III", data[8:20])
    return {"image": image, "offset": offset, "length": length}


def parse_read_data64(data):
    """Parse a READ_DATA64 request -> {'image', 'offset', 'length'}."""
    cmd, length = parse_packet_header(data)
    image, offset, length = struct.unpack("<QQQ", data[8:32])
    return {"image": image, "offset": offset, "length": length}


def build_done():
    """Build a DONE (0x05) packet: header only, 8 bytes."""
    return pack_header(CMD_DONE, 0x08)


def build_exec_cmd(client_cmd):
    """Build an EXECUTE (0x0B) command-mode packet."""
    return pack_header(CMD_EXEC, 0x0C) + struct.pack("<I", client_cmd)


# ---------------------------------------------------------------------------
# Firehose XML builders
# ---------------------------------------------------------------------------

def _firehose_doc(elements):
    root = ET.Element("data")
    for tag, attrs in elements:
        ET.SubElement(root, tag, attrs)
    return '<?xml version="1.0" ?>\n' + ET.tostring(root, encoding="unicode")


def configure_xml(memory="ufs", verbose="0", max_payload_size="1048576"):
    """Firehose <configure> command."""
    return _firehose_doc([("configure", {
        "MemoryName": memory, "verbose": verbose,
        "MaxPayloadSizeToTargetInBytes": max_payload_size})])


def program_xml(label, filename, start_sector, num_sectors,
                sector_size="4096", physical_partition="0"):
    """Firehose <program> command: write a file to a partition."""
    return _firehose_doc([("program", {
        "SECTOR_SIZE_IN_BYTES": str(sector_size),
        "file_sector_offset": "0",
        "filename": filename,
        "label": label,
        "num_partition_sectors": str(num_sectors),
        "physical_partition_number": str(physical_partition),
        "start_sector": str(start_sector)})])


def erase_xml(label, start_sector, num_sectors, physical_partition="0"):
    """Firehose <erase> command."""
    return _firehose_doc([("erase", {
        "label": label,
        "num_partition_sectors": str(num_sectors),
        "physical_partition_number": str(physical_partition),
        "start_sector": str(start_sector)})])


def power_xml(value="reset"):
    """Firehose <power> command (value: reset / off)."""
    return _firehose_doc([("power", {"value": value})])


def parse_firehose_response(xml_text):
    """Parse a firehose reply: {'ack': bool, 'value': str, 'log': [str]}.

    Replies look like: <data><log value="..."/></data> and
    <data><response value="ACK" /></data>.
    """
    result = {"ack": False, "value": "", "log": []}
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return result
    for child in root:
        if child.tag == "response":
            result["value"] = child.get("value", "")
            result["ack"] = result["value"].upper() == "ACK"
        elif child.tag == "log":
            result["log"].append(child.get("value", ""))
    return result


def detect_usb():
    """Find Qualcomm EDL (VID 0x05c6, PID 0x9008) devices.

    Uses pyusb when installed, otherwise parses `lsusb` output.
    Returns [{vid, pid, mode}].
    """
    found = []
    try:
        import usb.core  # pyusb, optional
        for dev in usb.core.find(find_all=True):
            if dev.idVendor == VID_QC and dev.idProduct == PID_EDL:
                found.append({"vid": dev.idVendor, "pid": dev.idProduct,
                              "mode": "edl"})
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
            if vid == VID_QC and pid == PID_EDL:
                found.append({"vid": vid, "pid": pid, "mode": "edl"})
    return found


class QualcommPlugin(ProtocolPlugin):
    name = "edl (Qualcomm Sahara/firehose)"
    chipsets = ["sm8650", "sm8750", "sm8850", "sm8845", "sdm845", "sm8250",
                "sm8350", "sm8450", "sm8550", "sm7475", "sm7550"]

    def detect(self):
        return bool(detect_usb())

    def device_info(self):
        devs = detect_usb()
        if not devs:
            raise OpenUnlockError(
                "No Qualcomm device in EDL mode (USB 05c6:9008). Put the "
                "phone in EDL with `adb reboot edl` or the test point.")
        return {"devices": devs,
                "note": "Sahara hello will report the chipset; a firehose "
                        "programmer for that exact chipset is still needed."}

    def _delegate(self, args):
        rc, text = runner.run_quiet(["edl"] + args)
        if rc != 0:
            raise OpenUnlockError(
                "edl failed or is not installed. Install it: "
                f"{EDLCLIENT} — then put the phone in EDL (9008) mode and "
                f"supply a firehose programmer. Output: {text.strip()}")
        return text

    def read_partition(self, partition, out_path, loader=None):
        args = ["r", partition, out_path]
        if loader:
            args.append(f"--loader={loader}")
        return self._delegate(args)

    def write_partition(self, partition, image_path, loader=None):
        args = ["w", partition, image_path]
        if loader:
            args.append(f"--loader={loader}")
        return self._delegate(args)

    def restore_imei(self, backup_data, serial):
        raise OpenUnlockError(
            "Qualcomm IMEI restore needs the edl client plus the device's "
            "own QCN/NV backup: restore the modemst1/modemst2/fsg "
            "partitions from the backup with edl in EDL mode, or write "
            "NV item 550 via QPST/QCN. OpenUnlock will not write IMEI "
            "values itself — the backup file is the only source of the "
            "original values.")
