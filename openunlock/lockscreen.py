"""Screen-lock removal — the lawful ways only.

Two paths, in order of preference:
1. ``reset`` — factory reset via recovery/fastboot. Wipes the phone,
   including the lock. Works on any device, no root needed. This is the
   path to use when the data is not recoverable or not needed.
2. ``remove`` — delete the lock credential database
   (/data/system/locksettings.db*) on a ROOTED device, then reboot. This
   keeps user data but requires root, which itself requires an unlocked
   bootloader. It refuses to run on a non-rooted device — detected with
   `adb shell su -c id` — instead of failing halfway through.

There is no lockscreen-bypass exploit here: no pattern brute-forcing, no
gatekeeper bypass, no smali patching. A locked phone that is not rooted
and whose owner cannot remember the PIN/pattern/password is reset, not
picked.
"""
from . import runner
from .adb import Adb
from .errors import OpenUnlockError
from .flash import factory_reset


def is_rooted(serial=None):
    """True when `su` runs as uid=0 on the device."""
    adb = Adb(serial)
    try:
        adb.require_device()
    except OpenUnlockError:
        return False
    rc, out = runner.run_quiet(
        adb._argv("shell", "su", "-c", "id"))
    return rc == 0 and "uid=0" in out


def reset_lock(serial=None, confirm=False):
    """Factory reset — removes the screen lock by wiping the phone."""
    if not confirm:
        raise OpenUnlockError(
            "Screen-lock reset requires --confirm. This erases all data.")
    return factory_reset(serial, confirm=True)


def remove_lock(serial=None, confirm=False):
    """Remove lock credentials on a ROOTED device. Requires --confirm.

    Deletes locksettings.db* and the gatekeeper password/key files, then
    reboots. Refuses when the device is not rooted.
    """
    if not confirm:
        raise OpenUnlockError(
            "Lock removal requires --confirm.")
    if not is_rooted(serial):
        raise OpenUnlockError(
            "Device is not rooted (`su` did not return uid=0). Lock "
            "removal needs root. Use `openunlock lockscreen reset "
            "--confirm` (factory reset) instead, or root the phone first.")
    adb = Adb(serial)
    adb.require_device()
    files = [
        "/data/system/locksettings.db",
        "/data/system/locksettings.db-shm",
        "/data/system/locksettings.db-wal",
        "/data/system/gatekeeper.password.key",
        "/data/system/gatekeeper.pattern.key",
    ]
    out = []
    for path in files:
        rc, text = runner.run_quiet(
            adb._argv("shell", "su", "-c", f"rm -f {path}"))
        out.append(f"{path}: {'removed' if rc == 0 else 'failed: ' + text.strip()}")
    adb.reboot()
    return "\n".join(out) + "\nDevice rebooting — lock should be gone."
