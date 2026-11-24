"""fastboot wrapper: talk to a phone in bootloader mode.

Covers device listing, getvar parsing, flashing/erasing/booting, and the
official bootloader unlock/relock flow. fastboot writes its status to
stderr, so outputs are read from the combined stream.
"""
import re

from . import runner
from .errors import DeviceNotFoundError

DEVICE_LINE = re.compile(r"^(\S+)\s+fastboot\s*$")
VAR_LINE = re.compile(r"^(\S+):\s*(.*)$")


def parse_devices(output):
    """Parse `fastboot devices` output into [serial]."""
    return [m.group(1) for line in output.splitlines()
            if (m := DEVICE_LINE.match(line.strip()))]


def parse_getvar_all(output):
    """Parse `fastboot getvar all` output into {key: value}.

    Real fastboot lines look like "(bootloader) unlocked: yes".
    """
    out = {}
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("(bootloader)"):
            line = line[len("(bootloader)"):].strip()
        if line.startswith(("OKAY", "Finished")):
            continue
        m = VAR_LINE.match(line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


class Fastboot:
    def __init__(self, serial=None):
        self.serial = serial

    def _argv(self, *args):
        base = ["fastboot"]
        if self.serial:
            base += ["-s", self.serial]
        return base + list(args)

    def devices(self):
        return parse_devices(runner.run(["fastboot", "devices"]))

    def require_device(self):
        found = self.devices()
        if self.serial:
            if self.serial not in found:
                raise DeviceNotFoundError(
                    f"Device {self.serial} is not in fastboot mode.")
            return self.serial
        if not found:
            raise DeviceNotFoundError(
                "No device in fastboot mode. Reboot to bootloader first "
                "(adb reboot bootloader).")
        if len(found) > 1:
            raise DeviceNotFoundError(
                f"{len(found)} devices in fastboot; pass --serial: "
                + ", ".join(found))
        return found[0]

    def _run(self, *args, timeout=180):
        """fastboot prints to stderr; capture both streams."""
        self.require_device()
        argv = self._argv(*args)
        runner.which_or_raise(argv[0])
        import subprocess
        try:
            proc = subprocess.run(argv, capture_output=True, text=True,
                                  timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            from .errors import CommandFailedError
            raise CommandFailedError(argv, -1,
                                     f"timed out after {timeout}s") from exc
        out = proc.stdout + proc.stderr
        if proc.returncode != 0:
            from .errors import CommandFailedError
            raise CommandFailedError(argv, proc.returncode, out)
        return out

    def getvar(self, name):
        out = self._run("getvar", name)
        m = re.search(rf"^{re.escape(name)}:\s*(.*)$", out, re.M)
        return m.group(1).strip() if m else ""

    def getvar_all(self):
        return parse_getvar_all(self._run("getvar", "all"))

    def flash(self, partition, image_path):
        return self._run("flash", partition, image_path)

    def erase(self, partition):
        return self._run("erase", partition)

    def boot(self, image_path):
        """Boot an image once without flashing it."""
        return self._run("boot", image_path)

    def reboot(self, target=""):
        args = ["reboot"]
        if target:
            args.append(target)
        return self._run(*args)

    def oem(self, *args):
        return self._run("oem", *args)

    def flashing(self, *args):
        return self._run("flashing", *args)
