"""Partition listing and backup over adb.

Reading raw partitions needs privileges: on most phones this means a rooted
device or `adb root`. The functions here report that honestly instead of
pretending a backup succeeded when it didn't.

- list_partitions(): reads /dev/block/by-name over adb shell.
- backup_partition(): pulls /dev/block/by-name/<part> to a local file.
  Verifies the local file is non-empty afterwards.
"""
import os

from .adb import Adb
from .errors import OpenUnlockError


def list_partitions(serial=None):
    """Return [partition names] from /dev/block/by-name, or raise."""
    adb = Adb(serial)
    adb.require_device()
    out = adb.shell("ls", "/dev/block/by-name")
    names = [l.strip() for l in out.splitlines() if l.strip()]
    if not names:
        raise OpenUnlockError(
            "Could not list partitions. The phone may need root access "
            "(`adb root` works only on userdebug/eng builds).")
    return names


def backup_partition(partition, out_dir, serial=None):
    """Pull one partition to <out_dir>/<partition>.img. Returns the path."""
    adb = Adb(serial)
    adb.require_device()
    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(os.path.abspath(out_dir), f"{partition}.img")
    adb.pull(f"/dev/block/by-name/{partition}", dest)
    if not os.path.isfile(dest) or os.path.getsize(dest) == 0:
        raise OpenUnlockError(
            f"Backup of '{partition}' produced an empty file — the phone "
            "probably refused the read (needs root). Nothing useful was saved.")
    return dest


def backup_all(out_dir, serial=None, skip=("userdata", "super")):
    """Back up every listed partition except the huge/sensitive ones.

    userdata and super are skipped by default: they are multi-GB and
    userdata contains the owner's private data. Pass skip=() to include them.
    Returns {partition: path} for the partitions that succeeded.
    """
    results = {}
    for part in list_partitions(serial):
        if part in skip:
            continue
        try:
            results[part] = backup_partition(part, out_dir, serial)
        except OpenUnlockError as exc:
            results[part] = f"FAILED: {exc}"
    return results
