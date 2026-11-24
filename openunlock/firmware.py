"""Firmware-package inspection (Android 16 / 17 era).

Parses a firmware ZIP with the standard library only (zipfile) and reports
what a servicing tool needs to know before flashing:

* dynamic-partition layout (super.img present, or the metadata flag)
* AVB / vbmeta presence (vbmeta.img, vbmeta_system.img)
* boot / recovery / vendor_boot images present
* metadata (META-INF/com/android/metadata): device, build, timestamps,
  security patch level
* Android version from any build.prop found inside the package
* anti-rollback / downgrade risk: warns when the firmware is OLDER than
  the device (rolling back can trip anti-rollback and brick), and when the
  firmware is NEWER than the device (verify the rollback index before
  flashing — the device's anti-rollback counter may refuse it)

OTA payload.bin packages cannot be inspected with the stdlib alone — the
inspector says so plainly instead of guessing.
"""
import os
import re
import zipfile

from .adb import Adb
from .errors import OpenUnlockError


def _parse_metadata(text):
    out = {}
    for line in text.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip()
    return out


def _parse_build_prop(text):
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out


def _version_tuple(version):
    """'17' -> (17,), '16.1' -> (16, 1). Non-numeric -> ()."""
    parts = re.findall(r"\d+", version or "")
    return tuple(int(p) for p in parts) if parts else ()


def inspect_firmware(path, serial=None):
    """Inspect a firmware ZIP. Returns a report dict."""
    if not os.path.isfile(path):
        raise OpenUnlockError(f"Firmware file not found: {path}")
    if not zipfile.is_zipfile(path):
        raise OpenUnlockError(
            f"Not a ZIP firmware package: {path}. (OTA payload.bin files "
            "are not supported by this inspector.)")
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        report = {
            "file": os.path.abspath(path),
            "size_bytes": os.path.getsize(path),
            "entries": len(names),
            "has_super": any(n.endswith("super.img") for n in names),
            "has_vbmeta": any("vbmeta" in n and n.endswith(".img")
                              for n in names),
            "has_boot": any(n.endswith("boot.img") for n in names),
            "has_recovery": any(n.endswith("recovery.img") for n in names),
            "has_payload_bin": "payload.bin" in names,
            "dynamic_partitions": False,
            "android_version": "",
            "security_patch": "",
            "device": "",
            "build": "",
            "warnings": [],
        }
        report["dynamic_partitions"] = report["has_super"]
        meta_name = "META-INF/com/android/metadata"
        if meta_name in names:
            meta = _parse_metadata(
                zf.read(meta_name).decode("utf-8", "replace"))
            report["device"] = meta.get("pre-device", "")
            report["build"] = meta.get("post-build", meta.get("pre-build", ""))
            report["security_patch"] = meta.get(
                "post-security-patch-level",
                meta.get("pre-security-patch-level", ""))
            if meta.get("post-timestamp"):
                report["build_timestamp"] = meta["post-timestamp"]
            if meta.get("ota-type", "").lower().find("dynamic") >= 0:
                report["dynamic_partitions"] = True
        for name in names:
            if name.endswith("build.prop"):
                props = _parse_build_prop(
                    zf.read(name).decode("utf-8", "replace"))
                report["android_version"] = props.get(
                    "ro.build.version.release", "")
                report["security_patch"] = report["security_patch"] or \
                    props.get("ro.build.version.security_patch", "")
                report["device"] = report["device"] or \
                    props.get("ro.product.device", "")
                break
        if report["has_payload_bin"]:
            report["warnings"].append(
                "This is an OTA-style package (payload.bin): partition "
                "images are inside the payload and cannot be listed with "
                "this inspector. Use a full fastboot (factory) image for "
                "partition-level work.")
        if not report["has_vbmeta"]:
            report["warnings"].append(
                "No vbmeta image found — AVB verification state cannot be "
                "checked. Flashing boot without a matching vbmeta can fail "
                "verified boot.")
        if report["has_super"] and not report["has_vbmeta"]:
            report["warnings"].append(
                "Dynamic-partition (super) device without vbmeta in the "
                "package — confirm the vbmeta source before flashing.")
        if serial:
            _compare_with_device(report, serial)
        return report


def _compare_with_device(report, serial):
    """Compare firmware vs the attached device; append warnings."""
    adb = Adb(serial)
    try:
        adb.require_device()
        props = adb.getprop()
    except OpenUnlockError as exc:
        report["warnings"].append(f"Could not read device: {exc}")
        return
    dev_version = props.get("ro.build.version.release", "")
    dev_patch = props.get("ro.build.version.security_patch", "")
    dev_device = props.get("ro.product.device", "")
    fw_version = report.get("android_version", "")
    fw_patch = report.get("security_patch", "")
    if report.get("device") and dev_device and \
            report["device"] != dev_device:
        report["warnings"].append(
            f"Firmware is for device '{report['device']}' but this phone "
            f"is '{dev_device}'. Do NOT flash — wrong-device firmware "
            "bricks phones.")
    if fw_version and dev_version:
        fw_v, dev_v = _version_tuple(fw_version), _version_tuple(dev_version)
        if fw_v and dev_v:
            if fw_v > dev_v:
                report["warnings"].append(
                    f"Firmware Android {fw_version} is NEWER than the "
                    f"device's Android {dev_version}. Verify the "
                    "anti-rollback (rollback index) status before flashing.")
            elif fw_v < dev_v:
                report["warnings"].append(
                    f"Firmware Android {fw_version} is OLDER than the "
                    f"device's Android {dev_version} — downgrading can trip "
                    "anti-rollback protection and brick the phone.")
    if fw_patch and dev_patch and fw_patch < dev_patch:
        report["warnings"].append(
            f"Firmware security patch {fw_patch} is older than the "
            f"device's {dev_patch} — anti-rollback may refuse this flash.")


def format_report(report):
    """Render an inspect_firmware() report as readable text."""
    lines = [f"Firmware: {report['file']} ({report['size_bytes']} bytes, "
             f"{report['entries']} entries)"]
    lines.append(f"  Device: {report.get('device') or '—'}")
    lines.append(f"  Android: {report.get('android_version') or '—'}"
                 f"  Patch: {report.get('security_patch') or '—'}")
    lines.append(f"  Build: {report.get('build') or '—'}")
    lines.append(f"  Dynamic partitions (super.img): "
                 f"{'yes' if report['dynamic_partitions'] else 'no'}")
    lines.append(f"  vbmeta present: {'yes' if report['has_vbmeta'] else 'no'}")
    lines.append(f"  boot.img: {'yes' if report['has_boot'] else 'no'}"
                 f"  recovery.img: {'yes' if report['has_recovery'] else 'no'}")
    for w in report.get("warnings", []):
        lines.append(f"  WARNING: {w}")
    return "\n".join(lines)
