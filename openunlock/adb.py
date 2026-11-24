"""adb wrapper: talk to a phone in Android (system) mode.

Covers device listing, shell commands, properties, and reboot targets.
All methods raise OpenUnlockError subclasses on failure; they never
swallow an error into an empty result.
"""
import re

from . import runner
from .errors import DeviceNotFoundError

DEVICE_LINE = re.compile(r"^(\S+)\s+(device|offline|unauthorized|no permissions)\s*$")


def parse_devices(output):
    """Parse `adb devices` output into [(serial, state)]."""
    devices = []
    for line in output.splitlines():
        m = DEVICE_LINE.match(line.strip())
        if m:
            devices.append((m.group(1), m.group(2)))
    return devices


def parse_getprop(output):
    """Parse `adb shell getprop` output into {key: value}."""
    props = {}
    for line in output.splitlines():
        m = re.match(r"^\[([^\]]+)\]: \[(.*)\]$", line.strip())
        if m:
            props[m.group(1)] = m.group(2)
    return props


class Adb:
    def __init__(self, serial=None):
        self.serial = serial

    def _argv(self, *args):
        base = ["adb"]
        if self.serial:
            base += ["-s", self.serial]
        return base + list(args)

    def devices(self):
        """Return [(serial, state)] for every attached adb device."""
        return parse_devices(runner.run(["adb", "devices"]))

    def require_device(self):
        """Return this Adb's serial, or the only attached device.

        Raises DeviceNotFoundError when there are zero or (without an
        explicit serial) more than one.
        """
        found = self.devices()
        live = [s for s, st in found if st == "device"]
        if self.serial:
            if self.serial not in [s for s, _ in found]:
                raise DeviceNotFoundError(
                    f"Device {self.serial} is not attached.")
            return self.serial
        if not live:
            raise DeviceNotFoundError()
        if len(live) > 1:
            raise DeviceNotFoundError(
                f"{len(live)} devices attached; pass --serial to pick one: "
                + ", ".join(live))
        return live[0]

    def shell(self, *cmd, timeout=120):
        self.require_device()
        return runner.run(self._argv("shell", *cmd), timeout=timeout)

    def getprop(self):
        """Return all system properties as a dict."""
        return parse_getprop(self.shell("getprop"))

    def get_prop(self, key, default=""):
        return self.getprop().get(key, default)

    def reboot(self, target=""):
        """Reboot: '' (system), 'recovery', 'bootloader', 'fastboot', 'edl'."""
        args = ["reboot"]
        if target:
            args.append(target)
        self.require_device()
        return runner.run(self._argv(*args))

    def wait_for_device(self, timeout=60):
        return runner.run(["adb", "wait-for-device"], timeout=timeout)

    def pull(self, remote, local):
        self.require_device()
        return runner.run(self._argv("pull", remote, local))

    def push(self, local, remote):
        self.require_device()
        return runner.run(self._argv("push", local, remote))
