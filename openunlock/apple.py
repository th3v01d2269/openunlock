"""Apple A12 / A13 — detection and research documentation ONLY.

What this module does:
* Detect a connected Apple device in DFU / recovery / normal mode by
  parsing `lsusb` (Linux) or `system_profiler SPUSBDataType` (macOS) for
  Apple's USB vendor ID (0x05ac). DFU mode is PID 0x1227, recovery mode
  is PID 0x1281.
* Document the exploit lineage so the project can study it.

What it deliberately does NOT do: implement a BootROM exploit. The
checkm8-style work lives in dedicated projects (checkra1n, palera1n,
ipwndfu, gaster) and writing a working exploit is out of scope for this
repo — and unnecessary for the educational goal, which is understanding
the chain: DFU -> unsigned code in SecureROM -> boot a custom ramdisk.

Background (public research, cited in the report):
* checkm8 (axi0mX, 27 Sep 2019, CVE-2019-8900): use-after-free in the
  SecureROM USB/DFU stack, A5–A11. Unpatchable (BootROM is read-only).
  A12/A13 were NOT vulnerable to checkm8 — Apple patched the UAF and the
  memory-leak primitive it relied on.
* usbliter8 (Paradigm Shift, disclosed June 2026): a checkm8-style
  BootROM exploit for A12/A13, in the Synopsys DesignWare USB controller
  handling of DFU setup packets. Also unpatchable (same immutable
  SecureROM). It can run unsigned code during boot and load custom iBoot
  images. It does NOT break the Secure Enclave — passcodes stay protected.
* Ramdisk boot (what UnlockTool sells as "Apple A12/A13 ramdisk"): once
  unsigned code runs in DFU, a custom ramdisk can be booted to read/write
  the filesystem without iOS running — the basis for passcode-bypass
  research and data recovery on those chips. A12/A13 + iOS 26.0/26.0.1
  also saw the first public jailbreak (Dopamine 3.0, Aug 2026).
* A14 and later: the USB-controller flaw is fixed; no public BootROM
  exploit exists for A14+ as of Nov 2026.
"""
import re
import subprocess

from . import runner
from .errors import OpenUnlockError

APPLE_VID = 0x05AC
# Well-known Apple USB PIDs (from the checkra1n / ipwndfu research).
APPLE_PIDS = {
    0x1227: "DFU mode",
    0x1281: "Recovery mode",
    0x12A8: "Normal mode (iOS running)",
    0x12A0: "Normal mode (older iOS)",
    0x1290: "DFU mode (older devices)",
    0x1292: "Recovery mode (older devices)",
}

DFU_PIDS = {0x1227, 0x1290}
RECOVERY_PIDS = {0x1281, 0x1292}


def _parse_lsusb(output):
    """Parse `lsusb` output into [{vid, pid, description}]."""
    found = []
    for line in output.splitlines():
        m = re.search(r"ID\s+([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\s+(.*)$",
                      line)
        if m and int(m.group(1), 16) == APPLE_VID:
            found.append({
                "vid": int(m.group(1), 16),
                "pid": int(m.group(2), 16),
                "description": m.group(3).strip(),
            })
    return found


def _parse_system_profiler(output):
    """Parse macOS system_profiler SPUSBDataType text for Apple devices."""
    found = []
    current = None
    for line in output.splitlines():
        m = re.match(r"\s*Vendor ID:\s*0x([0-9a-fA-F]+)", line)
        if m:
            current = {"vid": int(m.group(1), 16)}
            continue
        m = re.match(r"\s*Product ID:\s*0x([0-9a-fA-F]+)", line)
        if m and current is not None:
            current["pid"] = int(m.group(1), 16)
            if current["vid"] == APPLE_VID:
                current["description"] = "Apple device (system_profiler)"
                found.append(current)
            current = None
    return found


def detect_apple():
    """Return a list of detected Apple devices with mode classification.

    Tries lsusb first (Linux), then system_profiler (macOS). Returns [] when
    no Apple device is connected. Raises OpenUnlockError when neither tool
    exists on this machine.
    """
    devices = []
    rc, out = runner.run_quiet(["lsusb"])
    if rc == 0:
        devices = _parse_lsusb(out)
    else:
        rc, out = runner.run_quiet(["system_profiler", "SPUSBDataType"])
        if rc == 0:
            devices = _parse_system_profiler(out)
        else:
            raise OpenUnlockError(
                "Neither `lsusb` (Linux) nor `system_profiler` (macOS) is "
                "available — cannot scan for Apple devices on this machine.")
    for d in devices:
        pid = d["pid"]
        d["mode"] = APPLE_PIDS.get(pid, f"Unknown Apple mode (PID 0x{pid:04x})")
        d["dfu"] = pid in DFU_PIDS
        d["recovery"] = pid in RECOVERY_PIDS
    return devices


def apple_research_note():
    """Short explainer printed by `openunlock apple detect`."""
    return (
        "Apple A12/A13 research note:\n"
        "  checkm8 (CVE-2019-8900, axi0mX 2019) covers A5-A11 only.\n"
        "  A12/A13 are covered by 'usbliter8' (Paradigm Shift, June 2026):\n"
        "  a BootROM flaw in the DFU USB controller, unpatchable, that lets\n"
        "  unsigned code run at boot and a custom ramdisk be loaded.\n"
        "  A14+ is not affected. This tool detects DFU/recovery devices\n"
        "  only — it does not implement the exploit. See checkra1n,\n"
        "  palera1n, and the Paradigm Shift write-up for the research."
    )
