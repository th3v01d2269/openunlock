"""Device model + detection across adb and fastboot modes.

A phone shows up in exactly one mode at a time: `adb` (system on),
`fastboot` (bootloader), or neither (off / wrong drivers / unauthorized).
"""
from dataclasses import dataclass, field

from .adb import Adb, parse_getprop
from .errors import DeviceNotFoundError
from .fastboot import Fastboot


@dataclass
class Device:
    serial: str
    mode: str  # "adb" | "fastboot"
    model: str = ""
    brand: str = ""
    android_version: str = ""
    bootloader_unlocked: str = ""  # "yes" | "no" | ""
    extra: dict = field(default_factory=dict)

    @property
    def label(self):
        name = self.model or self.brand or "unknown device"
        return f"{name} ({self.serial}, {self.mode})"


def detect(serial=None):
    """Find attached devices. Returns [Device] (possibly empty).

    With a serial, returns just that device (in whichever mode it is in).
    """
    found = []
    for s, state in Adb().devices():
        if serial and s != serial:
            continue
        if state == "device":
            found.append(Device(serial=s, mode="adb"))
        else:
            found.append(Device(serial=s, mode=f"adb:{state}"))
    for s in Fastboot().devices():
        if serial and s != serial:
            continue
        found.append(Device(serial=s, mode="fastboot"))
    return found


def require_one(serial=None):
    """Return the single attached device, or raise."""
    devices = [d for d in detect(serial) if d.mode in ("adb", "fastboot")]
    if not devices:
        raise DeviceNotFoundError()
    if len(devices) > 1:
        raise DeviceNotFoundError(
            f"{len(devices)} devices attached; pass --serial to pick one: "
            + ", ".join(d.serial for d in devices))
    return devices[0]


def fill_info(device):
    """Populate model/brand/version/unlock state for an adb-mode device."""
    if device.mode != "adb":
        return device
    adb = Adb(device.serial)
    props = adb.getprop()
    device.model = props.get("ro.product.model", "")
    device.brand = props.get("ro.product.brand", "")
    device.android_version = props.get("ro.build.version.release", "")
    device.extra = {
        "sdk": props.get("ro.build.version.sdk", ""),
        "build": props.get("ro.build.display.id", ""),
        "hardware": props.get("ro.hardware", ""),
    }
    return device


def fill_fastboot_info(device):
    """Populate unlock state for a fastboot-mode device."""
    if device.mode != "fastboot":
        return device
    fb = Fastboot(device.serial)
    info = fb.getvar_all()
    device.model = info.get("product", "")
    device.bootloader_unlocked = info.get("unlocked", "")
    device.extra = {k: v for k, v in info.items()
                    if k in ("version-bootloader", "version-baseband",
                             "secure", "is-userspace")}
    return device


def info_dict(device):
    """Full info dict for display/JSON output."""
    if device.mode == "adb":
        fill_info(device)
        adb = Adb(device.serial)
        props = adb.getprop()
        from . import profiles as profiles_mod
        profile = profiles_mod.match_device(device.brand, device.model)
        return {
            "serial": device.serial,
            "mode": "adb",
            "model": device.model,
            "brand": device.brand,
            "android": device.android_version,
            "sdk": props.get("ro.build.version.sdk", ""),
            "build": props.get("ro.build.display.id", ""),
            "hardware": props.get("ro.hardware", ""),
            "battery": _battery(adb),
            "storage": _storage(adb),
            "profile": profile["brand"],
            "profile_unlock": profile.get("unlock", {}).get("method", ""),
        }
    fill_fastboot_info(device)
    from . import profiles as profiles_mod
    profile = profiles_mod.match_device("", device.model)
    return {
        "serial": device.serial,
        "mode": "fastboot",
        "product": device.model,
        "bootloader_unlocked": device.bootloader_unlocked,
        "vars": device.extra,
        "profile": profile["brand"],
        "profile_unlock": profile.get("unlock", {}).get("method", ""),
    }


def _battery(adb):
    try:
        out = adb.shell("dumpsys", "battery")
        level = [l.split(":")[1].strip() for l in out.splitlines()
                 if "level:" in l]
        return level[0] if level else ""
    except Exception:
        return ""


def _storage(adb):
    try:
        return adb.shell("df", "-h", "/data").strip().splitlines()[-1]
    except Exception:
        return ""
