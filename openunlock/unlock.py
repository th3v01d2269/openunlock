"""Bootloader unlock / relock — the official OEM flow only.

Unlocking the bootloader WIPES the phone (factory reset by design) and
usually voids the warranty and breaks SafetyNet/Play Integrity. This module
makes that impossible to do by accident:

- the device must be in fastboot mode
- the caller must pass confirm=True (the CLI requires --confirm)
- the user is told, in plain text, what will happen before anything runs

There is deliberately no "bypass" path here: if the OEM does not allow
unlocking (carrier-locked, `oem_unlock` not permitted), the command fails
and the module reports why instead of working around it.
"""
from .errors import OpenUnlockError
from .fastboot import Fastboot


def _confirm_or_raise(confirm, what):
    if not confirm:
        raise OpenUnlockError(
            f"{what} requires --confirm. This wipes the phone. "
            "Re-run with --confirm if you are sure.")


def unlock(serial=None, confirm=False):
    """Official bootloader unlock. Returns the fastboot output."""
    _confirm_or_raise(confirm, "Bootloader unlock")
    fb = Fastboot(serial)
    fb.require_device()
    unlocked = fb.getvar("unlocked")
    if unlocked == "yes":
        return "Bootloader is already unlocked."
    # Modern devices: `fastboot flashing unlock`. Older: `fastboot oem unlock`.
    try:
        out = fb.flashing("unlock")
    except OpenUnlockError:
        out = fb.oem("unlock")
    return out


def relock(serial=None, confirm=False):
    """Official bootloader relock. Returns the fastboot output.

    Only relock with stock firmware installed — relocking over a custom
    ROM/recovery can brick the phone.
    """
    _confirm_or_raise(confirm, "Bootloader relock")
    fb = Fastboot(serial)
    fb.require_device()
    unlocked = fb.getvar("unlocked")
    if unlocked == "no":
        return "Bootloader is already locked."
    try:
        out = fb.flashing("lock")
    except OpenUnlockError:
        out = fb.oem("lock")
    return out


def status(serial=None):
    """Return 'yes'/'no'/'' for the bootloader unlocked flag."""
    fb = Fastboot(serial)
    fb.require_device()
    return fb.getvar("unlocked")
