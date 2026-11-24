"""Partition flashing, one-off booting, and factory reset.

All destructive operations require confirm=True (the CLI maps this to
--confirm) and validate their inputs before touching the phone.
"""
import os

from .errors import OpenUnlockError
from .fastboot import Fastboot


def _require_file(path):
    if not os.path.isfile(path):
        raise OpenUnlockError(f"Image file not found: {path}")
    return os.path.abspath(path)


def flash_partition(partition, image_path, serial=None, confirm=False):
    """fastboot flash <partition> <image>. Returns fastboot output."""
    if not confirm:
        raise OpenUnlockError(
            f"Flashing {partition} requires --confirm.")
    image = _require_file(image_path)
    fb = Fastboot(serial)
    fb.require_device()
    return fb.flash(partition, image)


def boot_image(image_path, serial=None):
    """Boot an image once without flashing it (e.g. a recovery or kernel)."""
    image = _require_file(image_path)
    fb = Fastboot(serial)
    fb.require_device()
    return fb.boot(image)


def factory_reset(serial=None, confirm=False):
    """fastboot -w: wipe userdata + cache. Returns fastboot output."""
    if not confirm:
        raise OpenUnlockError(
            "Factory reset requires --confirm. This erases all user data.")
    fb = Fastboot(serial)
    fb.require_device()
    return fb._run("-w")


def erase_partition(partition, serial=None, confirm=False):
    """Erase a single partition. Refuses the partitions that brick phones."""
    protected = {"bootloader", "aboot", "sbl1", "tz", "rpm", "hyp",
                 "devcfg", "xbl", "abl"}
    if partition in protected:
        raise OpenUnlockError(
            f"Refusing to erase '{partition}': erasing it bricks the phone.")
    if not confirm:
        raise OpenUnlockError(f"Erasing {partition} requires --confirm.")
    fb = Fastboot(serial)
    fb.require_device()
    return fb.erase(partition)
