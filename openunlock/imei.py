"""IMEI / MEID — full working features: read, backup, restore, verify.

LEGAL BOUNDARY — read this before using this module.
----------------------------------------------------
An IMEI identifies a handset on the carrier network. Changing an IMEI to a
*different* value — e.g. to evade a carrier blacklist, to clone another
phone, or to disguise a stolen device — is a crime in several
jurisdictions, including the UK under the Mobile Telephones
(Re-programming) Act 2002, and is fraud under US law when done to evade a
blacklist or deceive a carrier.

This module is a REPAIR and RESEARCH tool, not a changer. The hard rule,
enforced in code:

* ``read``    — read the IMEI/MEID the phone reports (same as *#06#),
  via dumpsys, the iphonesubinfo service call, or fastboot getvar.
* ``backup``  — save the phone's own values AND the modemst1/modemst2/fsg
  partitions that hold them, tied to the device serial.
* ``restore`` — write values/partitions back ONLY from a backup file taken
  from the SAME device serial. There is NO parameter anywhere in this
  project that accepts an IMEI value to write: ``restore`` takes a backup
  file, never a --imei argument, and any serial mismatch raises
  RefusedError before anything is written.
* ``verify``  — Luhn-check the digits and compare the live value against
  the backup.

Legitimate use case: a bad flash or corrupted NVRAM/EFS leaves the phone
reporting a null IMEI (000000000000000); restoring the phone's own
original IMEI from its backup is repair. Where the IMEI lives and how
tampering is detected is documented in docs/IMEI-RESEARCH.md — that
document is the bridge to the prevention project.
"""
import json
import os
import re
from datetime import datetime, timezone

from . import backup as backup_mod
from .adb import Adb
from .errors import OpenUnlockError, RefusedError
from .fastboot import Fastboot

IMEI_RE = re.compile(r"\b(\d{15})\b")
# Partitions that hold the IMEI / modem identity on Qualcomm + MTK devices.
IMEI_PARTITIONS = ("modemst1", "modemst2", "fsg")


def luhn_valid(number):
    """Luhn check for a 15-digit IMEI (last digit is the check digit)."""
    if not re.fullmatch(r"\d{15}", number or ""):
        return False
    total = 0
    for i, ch in enumerate(reversed(number)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _parse_iphonesubinfo(output):
    """Extract IMEIs from `adb shell dumpsys iphonesubinfo` output."""
    found = []
    for line in output.splitlines():
        if re.search(r"imei|device.?id|subscriber", line, re.I):
            found += IMEI_RE.findall(line)
    if not found:
        found = [n for n in IMEI_RE.findall(output) if luhn_valid(n)]
    seen, out = set(), []
    for n in found:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def parse_service_call_imei(output):
    """Parse `service call iphonesubinfo` parcel output into IMEI strings.

    The service call prints a hex dump of the reply Parcel. The IMEI is
    stored as a UTF-16 string: a 4-byte length (in 16-bit units) followed
    by the code units. This reconstructs the parcel bytes from the hex
    dump, decodes the UTF-16 strings, and returns any 15-digit runs.
    Example line:  0x00000000: 00000000 0000000f 00330035 ...
    """
    words = []
    for line in output.splitlines():
        m = re.search(r"0x[0-9a-fA-F]+:\s+((?:[0-9a-fA-F]{8}\s*)+)", line)
        if m:
            words += [int(w, 16) for w in m.group(1).split()]
    if not words:
        return []
    raw = b"".join(w.to_bytes(4, "little") for w in words)
    found = []
    # Try decoding the whole parcel as UTF-16LE and look for digit runs.
    try:
        text = raw.decode("utf-16-le", errors="ignore")
        found = [n for n in re.findall(r"\d{15}", text) if luhn_valid(n)]
    except Exception:
        found = []
    return found


def read_imei(serial=None, slot=1):
    """Return {'imei': [...], 'meid': '', 'source': ...} for the phone.

    Tries, in order: dumpsys iphonesubinfo, the iphonesubinfo service
    call (parcel parsing), vendor ril properties, fastboot getvar imei.
    Raises OpenUnlockError when nothing readable comes back.
    """
    adb = Adb(serial)
    adb.require_device()
    imeis, source = [], ""
    try:
        imeis = _parse_iphonesubinfo(adb.shell("dumpsys", "iphonesubinfo"))
        if imeis:
            source = "dumpsys iphonesubinfo"
    except OpenUnlockError:
        pass
    if not imeis:
        try:
            out = adb.shell("service", "call", "iphonesubinfo", str(slot))
            imeis = parse_service_call_imei(out)
            if imeis:
                source = f"service call iphonesubinfo {slot}"
        except OpenUnlockError:
            pass
    meid = ""
    try:
        props = adb.getprop()
        for key in ("ro.ril.oem.meid", "ril.meid"):
            if props.get(key):
                meid = props[key]
                break
    except OpenUnlockError:
        pass
    if not imeis and not meid:
        # Last resort: fastboot getvar (some devices expose it).
        try:
            fb = Fastboot(serial)
            fb.require_device()
            value = fb.getvar("imei")
            if IMEI_RE.fullmatch(value or ""):
                imeis = [value]
                source = "fastboot getvar imei"
        except OpenUnlockError:
            pass
    if not imeis and not meid:
        raise OpenUnlockError(
            "Could not read IMEI/MEID over adb or fastboot on this device. "
            "Dial *#06# on the phone, or read the label on the box — "
            "the value is the same one this tool would back up.")
    return {"imei": imeis, "meid": meid, "source": source}


def backup_imei(serial=None, out_dir="./backups"):
    """Back up this device's IMEI values AND the modem partitions.

    Writes imei-backup-<serial>.json plus modemst1/modemst2/fsg images
    (when readable — they need root; failures are recorded, not hidden).
    Returns the path of the JSON backup.
    """
    from . import device as device_mod
    info = read_imei(serial)
    dev = device_mod.require_one(serial)
    os.makedirs(out_dir, exist_ok=True)
    partitions = {}
    for part in IMEI_PARTITIONS:
        try:
            path = backup_mod.backup_partition(part, out_dir, serial)
            partitions[part] = {"path": path, "status": "ok"}
        except OpenUnlockError as exc:
            partitions[part] = {"path": None, "status": f"failed: {exc}"}
    data = {
        "tool": "openunlock",
        "kind": "imei-backup",
        "serial": dev.serial,
        "model": dev.model,
        "imei": info["imei"],
        "meid": info["meid"],
        "source": info.get("source", ""),
        "partitions": partitions,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    path = os.path.join(os.path.abspath(out_dir),
                        f"imei-backup-{dev.serial}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path


def load_backup(path):
    """Load and structurally validate an IMEI backup file."""
    if not os.path.isfile(path):
        raise OpenUnlockError(f"IMEI backup file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("kind") != "imei-backup" or not data.get("serial"):
        raise OpenUnlockError(f"Not an OpenUnlock IMEI backup: {path}")
    for value in data.get("imei", []):
        if not luhn_valid(value):
            raise OpenUnlockError(
                f"Backup contains an invalid IMEI ({value}) — refusing.")
    return data


def restore_imei(backup_path, serial=None, confirm=False):
    """Restore the phone's ORIGINAL IMEI from its own backup. --confirm.

    Hard gates: confirm required; backup serial must equal this device's
    serial; values must be Luhn-valid (checked in load_backup). The write
    is a partition restore: the backed-up modemst1/modemst2/fsg images
    are flashed back via fastboot, which restores the values they contain.
    No IMEI value is ever typed or invented — the only source is the
    backup. Partitions that were not backed up are reported, not guessed.
    """
    if not confirm:
        raise OpenUnlockError("IMEI restore requires --confirm.")
    data = load_backup(backup_path)
    from . import device as device_mod
    dev = device_mod.require_one(serial)
    if data["serial"] != dev.serial:
        raise RefusedError(
            f"Backup belongs to serial {data['serial']}, but this phone is "
            f"{dev.serial}. OpenUnlock never writes one phone's IMEI to "
            "another phone.")
    fb = Fastboot(serial)
    fb.require_device()
    results = []
    for part in IMEI_PARTITIONS:
        entry = data.get("partitions", {}).get(part, {})
        img = entry.get("path")
        if not img or entry.get("status") != "ok" or not os.path.isfile(img):
            results.append(f"{part}: skipped — no usable backup image")
            continue
        out = fb.flash(part, img)
        results.append(f"{part}: restored from backup image")
    if not any("restored" in r for r in results):
        raise OpenUnlockError(
            "No modem partition image was available in the backup, so "
            "nothing was written. Re-run `imei backup` on a rooted device "
            "so modemst1/modemst2/fsg can be read, then restore.")
    return "\n".join(results) + (
        "\nReboot and run `openunlock imei verify --from "
        f"{backup_path}` to confirm the values are back.")


def verify_imei(backup_path=None, serial=None):
    """Luhn-check the live IMEI and compare it against a backup (if given).

    Returns {'live': [...], 'luhn_ok': [...], 'matches_backup': bool|None}.
    """
    info = read_imei(serial)
    result = {
        "live": info["imei"],
        "luhn_ok": [luhn_valid(v) for v in info["imei"]],
        "matches_backup": None,
    }
    if backup_path:
        data = load_backup(backup_path)
        result["backup_serial"] = data["serial"]
        result["backup_imei"] = data["imei"]
        result["matches_backup"] = data["imei"] == info["imei"]
    return result
