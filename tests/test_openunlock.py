"""Tests for OpenUnlock parsers and safety gates.

Run: python -m unittest discover -s tests -v
No phone and no adb/fastboot needed — subprocess calls are mocked.
"""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openunlock import adb as adb_mod
from openunlock import fastboot as fb_mod
from openunlock import flash as flash_mod
from openunlock import unlock as unlock_mod
from openunlock.errors import OpenUnlockError


class TestAdbParsing(unittest.TestCase):
    def test_parse_devices(self):
        out = ("List of devices attached\n"
               "R5CX123ABC\tdevice\n"
               "ZYX987\tunauthorized\n\n")
        self.assertEqual(adb_mod.parse_devices(out),
                         [("R5CX123ABC", "device"), ("ZYX987", "unauthorized")])

    def test_parse_devices_empty(self):
        self.assertEqual(
            adb_mod.parse_devices("List of devices attached\n\n"), [])

    def test_parse_getprop(self):
        out = ("[ro.product.model]: [moto g]\n"
               "[ro.build.version.release]: [15]\n"
               "[ro.build.version.sdk]: [35]\n")
        self.assertEqual(adb_mod.parse_getprop(out), {
            "ro.product.model": "moto g",
            "ro.build.version.release": "15",
            "ro.build.version.sdk": "35",
        })


class TestFastbootParsing(unittest.TestCase):
    def test_parse_devices(self):
        out = "R5CX123ABC\tfastboot\nZYX987\tfastboot\n"
        self.assertEqual(fb_mod.parse_devices(out),
                         ["R5CX123ABC", "ZYX987"])

    def test_parse_getvar_all(self):
        out = ("(bootloader) unlocked: yes\n"
               "(bootloader) product: moto g\n"
               "(bootloader) version-bootloader: 1.2\n"
               "OKAY [  0.010s]\n"
               "Finished. Total time: 0.010s\n")
        self.assertEqual(fb_mod.parse_getvar_all(out), {
            "unlocked": "yes",
            "product": "moto g",
            "version-bootloader": "1.2",
        })


class TestSafetyGates(unittest.TestCase):
    def test_unlock_requires_confirm(self):
        with self.assertRaises(OpenUnlockError):
            unlock_mod.unlock(confirm=False)

    def test_relock_requires_confirm(self):
        with self.assertRaises(OpenUnlockError):
            unlock_mod.relock(confirm=False)

    def test_flash_requires_confirm(self):
        with self.assertRaises(OpenUnlockError):
            flash_mod.flash_partition("boot", "boot.img", confirm=False)

    def test_reset_requires_confirm(self):
        with self.assertRaises(OpenUnlockError):
            flash_mod.factory_reset(confirm=False)

    def test_flash_missing_file(self):
        with self.assertRaises(OpenUnlockError):
            flash_mod.flash_partition("boot", "/nonexistent/boot.img",
                                      confirm=True)

    def test_erase_protected_partition_refused(self):
        with self.assertRaises(OpenUnlockError):
            flash_mod.erase_partition("bootloader", confirm=True)

    def test_unlock_already_unlocked_short_circuits(self):
        fb = fb_mod.Fastboot("TEST123")
        with patch.object(fb_mod.Fastboot, "require_device",
                          return_value="TEST123"), \
             patch.object(fb_mod.Fastboot, "getvar", return_value="yes"):
            # unlock() builds its own Fastboot; patch at class level
            with patch.object(fb_mod.Fastboot, "flashing") as mock_flash:
                result = unlock_mod.unlock("TEST123", confirm=True)
                self.assertIn("already unlocked", result)
                mock_flash.assert_not_called()


class TestCliSmoke(unittest.TestCase):
    def test_devices_no_phone(self):
        from openunlock import cli
        with patch("openunlock.device.detect", return_value=[]):
            self.assertEqual(cli.cmd_devices(argparse_ns()), 0)


def argparse_ns(**kw):
    from types import SimpleNamespace
    return SimpleNamespace(**kw)


if __name__ == "__main__":
    unittest.main()
