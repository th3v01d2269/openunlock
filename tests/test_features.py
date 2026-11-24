"""Tests for the OpenUnlock v0.2 feature set.

Run: python -m unittest discover -s tests -v
No phone and no adb/fastboot needed — subprocess calls are mocked, and
firmware zips are built in-memory.
"""
import json
import os
import struct
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openunlock import apple as apple_mod
from openunlock import firmware as firmware_mod
from openunlock import frp as frp_mod
from openunlock import imei as imei_mod
from openunlock import lockscreen as lock_mod
from openunlock import profiles as profiles_mod
from openunlock.device import Device
from openunlock.errors import OpenUnlockError, RefusedError
from openunlock.protocols import mtk as mtk_mod
from openunlock.protocols import qualcomm as qc_mod

VALID_IMEI = "490154203237518"  # classic Luhn-valid example IMEI
BAD_IMEI = "490154203237519"


class TestImei(unittest.TestCase):
    def test_luhn_valid(self):
        self.assertTrue(imei_mod.luhn_valid(VALID_IMEI))
        self.assertFalse(imei_mod.luhn_valid(BAD_IMEI))
        self.assertFalse(imei_mod.luhn_valid("123"))
        self.assertFalse(imei_mod.luhn_valid(""))

    def test_parse_service_call_imei(self):
        # Build a fake `service call` hex dump containing the IMEI as
        # UTF-16LE inside the parcel.
        utf16 = VALID_IMEI.encode("utf-16-le")
        raw = b"\x00\x00\x00\x00" + struct.pack("<I", len(VALID_IMEI)) + utf16
        raw += b"\x00" * (-len(raw) % 4)
        words = struct.unpack("<%dI" % (len(raw) // 4), raw)
        lines = []
        for i in range(0, len(words), 4):
            chunk = words[i:i + 4]
            lines.append("  0x%08x: %s" % (
                i * 4, " ".join("%08x" % w for w in chunk)))
        self.assertEqual(imei_mod.parse_service_call_imei("\n".join(lines)),
                         [VALID_IMEI])

    def test_parse_service_call_empty(self):
        self.assertEqual(imei_mod.parse_service_call_imei(""), [])

    def test_load_backup_rejects_bad_luhn(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json",
                                         delete=False) as f:
            json.dump({"kind": "imei-backup", "serial": "X",
                       "imei": [BAD_IMEI]}, f)
            path = f.name
        try:
            with self.assertRaises(OpenUnlockError):
                imei_mod.load_backup(path)
        finally:
            os.unlink(path)

    def test_restore_refuses_serial_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "backup.json")
            with open(path, "w") as f:
                json.dump({"kind": "imei-backup", "serial": "OTHER",
                           "imei": [VALID_IMEI], "partitions": {}}, f)
            dev = Device(serial="MINE", mode="fastboot")
            with patch("openunlock.device.require_one",
                       return_value=dev):
                with self.assertRaises(RefusedError):
                    imei_mod.restore_imei(path, serial="MINE", confirm=True)

    def test_restore_requires_confirm(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "backup.json")
            with open(path, "w") as f:
                json.dump({"kind": "imei-backup", "serial": "MINE",
                           "imei": [VALID_IMEI], "partitions": {}}, f)
            with self.assertRaises(OpenUnlockError):
                imei_mod.restore_imei(path, serial="MINE", confirm=False)

    def test_restore_happy_path(self):
        with tempfile.TemporaryDirectory() as d:
            img = os.path.join(d, "modemst1.img")
            with open(img, "wb") as f:
                f.write(b"\x00" * 64)
            path = os.path.join(d, "backup.json")
            with open(path, "w") as f:
                json.dump({"kind": "imei-backup", "serial": "MINE",
                           "imei": [VALID_IMEI],
                           "partitions": {
                               "modemst1": {"path": img, "status": "ok"},
                               "modemst2": {"path": None, "status": "failed"},
                               "fsg": {"path": None, "status": "failed"}}}, f)
            dev = Device(serial="MINE", mode="fastboot")
            with patch("openunlock.device.require_one", return_value=dev), \
                 patch("openunlock.imei.Fastboot") as mock_fb_cls:
                mock_fb = mock_fb_cls.return_value
                mock_fb.require_device.return_value = "MINE"
                mock_fb.flash.return_value = "OKAY"
                out = imei_mod.restore_imei(path, serial="MINE",
                                            confirm=True)
            self.assertIn("modemst1: restored", out)
            self.assertIn("modemst2: skipped", out)

    def test_verify_matches_backup(self):
        with patch("openunlock.imei.read_imei",
                   return_value={"imei": [VALID_IMEI], "meid": "",
                                 "source": "test"}):
            with tempfile.NamedTemporaryFile("w", suffix=".json",
                                             delete=False) as f:
                json.dump({"kind": "imei-backup", "serial": "MINE",
                           "imei": [VALID_IMEI]}, f)
                path = f.name
            try:
                result = imei_mod.verify_imei(path, serial="MINE")
            finally:
                os.unlink(path)
        self.assertEqual(result["luhn_ok"], [True])
        self.assertTrue(result["matches_backup"])


class TestFrp(unittest.TestCase):
    def test_catalog_has_five_methods(self):
        methods = frp_mod.list_methods()
        self.assertEqual(len(methods), 5)
        ids = {m["id"] for m in methods}
        self.assertIn("talkback-settings", ids)
        self.assertIn("samsung-setup-wizard", ids)
        for m in methods:
            self.assertIn(m["status"],
                          ("patched", "mostly-patched", "partially-working"))

    def test_unknown_method_refused(self):
        with self.assertRaises(RefusedError):
            frp_mod.run_method("not-a-method", serial="X")

    def test_run_method_reports_per_step(self):
        adb = MagicMock()
        adb.require_device.return_value = "X"
        adb._argv.return_value = ["adb", "shell"]
        with patch("openunlock.frp.Adb", return_value=adb), \
             patch("openunlock.frp.runner.run_quiet",
                   return_value=(0, "OK")) as mock_run:
            report = frp_mod.run_method("emergency-dialer", serial="X")
        self.assertEqual(report["method"], "emergency-dialer")
        shell_steps = [s for s in report["steps"]
                       if s["kind"] == "shell"]
        self.assertTrue(all(s["result"] == "ok" for s in shell_steps))
        self.assertTrue(any(s["result"].startswith("manual")
                            for s in report["steps"]))
        self.assertEqual(mock_run.call_count, len(shell_steps))

    def test_run_method_failed_step_reported(self):
        adb = MagicMock()
        adb.require_device.return_value = "X"
        adb._argv.return_value = ["adb", "shell"]
        with patch("openunlock.frp.Adb", return_value=adb), \
             patch("openunlock.frp.runner.run_quiet",
                   return_value=(1, "error: closed")):
            report = frp_mod.run_method("talkback-settings", serial="X")
        shell_steps = [s for s in report["steps"]
                       if s["kind"] == "shell"]
        self.assertTrue(all(s["result"] == "failed" for s in shell_steps))

    def test_erase_requires_confirm(self):
        with self.assertRaises(OpenUnlockError):
            frp_mod.erase_frp(serial="X", confirm=False)

    def test_erase_unknown_method(self):
        with self.assertRaises(OpenUnlockError):
            frp_mod.erase_frp(serial="X", confirm=True, method="nope")

    def test_status_interpretation(self):
        adb = MagicMock()
        adb.require_device.return_value = "X"
        adb.shell.side_effect = lambda *a: {
            ("ls", "/dev/block/by-name"): "frp\nboot\n",
            ("settings", "get", "secure",
             "user_setup_complete"): "0\n",
            ("settings", "get", "global",
             "device_provisioned"): "0\n",
        }[a]
        adb.getprop.return_value = {"ro.frp.pst": "/dev/block/bootdevice/by-name/frp"}
        with patch("openunlock.frp.Adb", return_value=adb):
            s = frp_mod.status(serial="X")
        self.assertTrue(s["frp_partition"])
        self.assertIn("not completed", s["interpretation"])

    def test_frp_test_verdict(self):
        with patch("openunlock.frp.status",
                   return_value={"user_setup_complete": "1",
                                 "device_provisioned": "1",
                                 "frp_partition": True}):
            result = frp_mod.test_frp(serial="X")
        self.assertTrue(result["verdict"].startswith("PASSED"))


class TestLockscreen(unittest.TestCase):
    def _mock_adb(self, rc, out):
        adb = MagicMock()
        adb.require_device.return_value = "X"
        adb._argv.return_value = ["adb", "shell"]
        return adb

    def test_is_rooted_true(self):
        with patch("openunlock.lockscreen.Adb",
                   return_value=self._mock_adb(0, "")), \
             patch("openunlock.lockscreen.runner.run_quiet",
                   return_value=(0, "uid=0(root) gid=0")):
            self.assertTrue(lock_mod.is_rooted(serial="X"))

    def test_is_rooted_false(self):
        with patch("openunlock.lockscreen.Adb",
                   return_value=self._mock_adb(0, "")), \
             patch("openunlock.lockscreen.runner.run_quiet",
                   return_value=(0, "uid=2000(shell) gid=2000")):
            self.assertFalse(lock_mod.is_rooted(serial="X"))

    def test_remove_refuses_non_root(self):
        with patch("openunlock.lockscreen.is_rooted", return_value=False):
            with self.assertRaises(OpenUnlockError):
                lock_mod.remove_lock(serial="X", confirm=True)

    def test_remove_requires_confirm(self):
        with self.assertRaises(OpenUnlockError):
            lock_mod.remove_lock(serial="X", confirm=False)

    def test_reset_requires_confirm(self):
        with self.assertRaises(OpenUnlockError):
            lock_mod.reset_lock(serial="X", confirm=False)


class TestProfiles(unittest.TestCase):
    def test_lookup_by_brand_and_alias(self):
        self.assertEqual(profiles_mod.get_profile("xiaomi")["brand"],
                         "Xiaomi")
        self.assertEqual(profiles_mod.get_profile("redmi")["brand"],
                         "Xiaomi")
        self.assertEqual(profiles_mod.get_profile("poco")["brand"],
                         "Xiaomi")
        self.assertEqual(profiles_mod.get_profile("iqoo")["brand"], "Vivo")

    def test_unknown_falls_back_to_generic(self):
        self.assertEqual(
            profiles_mod.get_profile("nonexistentbrand")["brand"],
            "Generic Android")

    def test_list_has_all_brands(self):
        brands = {b for b, _ in profiles_mod.list_profiles()}
        for expected in ("Samsung", "Xiaomi", "Oppo", "Realme", "OnePlus",
                         "Vivo", "Huawei", "Honor", "Motorola", "Google",
                         "Sony", "Nokia", "Infinix", "Tecno", "Asus"):
            self.assertIn(expected, brands)

    def test_match_device(self):
        p = profiles_mod.match_device("samsung", "SM-S938B")
        self.assertEqual(p["brand"], "Samsung")
        self.assertIn("Knox", str(p["unlock"]["notes"]))

    def test_format_profile(self):
        text = profiles_mod.format_profile(
            profiles_mod.get_profile("google"))
        self.assertIn("Google", text)
        self.assertIn("flashing unlock", text)


class TestFirmware(unittest.TestCase):
    def _make_zip(self, d, metadata=None, with_vbmeta=True):
        path = os.path.join(d, "firmware.zip")
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("super.img", b"\x00" * 16)
            zf.writestr("boot.img", b"\x00" * 16)
            if with_vbmeta:
                zf.writestr("vbmeta.img", b"\x00" * 16)
            if metadata is not None:
                zf.writestr("META-INF/com/android/metadata", metadata)
        return path

    def test_inspect_detects_dynamic_and_vbmeta(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._make_zip(
                d, metadata="pre-device=sunfish\n"
                            "post-build=google/sunfish/17\n"
                            "post-security-patch-level=2026-11-05\n")
            report = firmware_mod.inspect_firmware(path)
        self.assertTrue(report["dynamic_partitions"])
        self.assertTrue(report["has_vbmeta"])
        self.assertTrue(report["has_boot"])
        self.assertEqual(report["device"], "sunfish")
        self.assertEqual(report["security_patch"], "2026-11-05")
        self.assertEqual(report["warnings"], [])

    def test_inspect_warns_without_vbmeta(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._make_zip(d, with_vbmeta=False)
            report = firmware_mod.inspect_firmware(path)
        self.assertFalse(report["has_vbmeta"])
        self.assertTrue(any("vbmeta" in w for w in report["warnings"]))

    def test_inspect_rejects_non_zip(self):
        with tempfile.NamedTemporaryFile("w", suffix=".bin",
                                         delete=False) as f:
            f.write("not a zip")
            path = f.name
        try:
            with self.assertRaises(OpenUnlockError):
                firmware_mod.inspect_firmware(path)
        finally:
            os.unlink(path)

    def test_inspect_warns_wrong_device_and_downgrade(self):
        with tempfile.TemporaryDirectory() as d:
            path = self._make_zip(
                d, metadata="pre-device=otherphone\n"
                            "post-security-patch-level=2026-09-01\n")
            adb = MagicMock()
            adb.require_device.return_value = "X"
            adb.getprop.return_value = {
                "ro.product.device": "sunfish",
                "ro.build.version.release": "17",
                "ro.build.version.security_patch": "2026-11-05",
            }
            with patch("openunlock.firmware.Adb", return_value=adb):
                report = firmware_mod.inspect_firmware(path, serial="X")
        self.assertTrue(any("wrong-device" in w.lower() or
                            "otherphone" in w for w in report["warnings"]))
        self.assertTrue(any("older than" in w for w in report["warnings"]))


class TestMtkProtocol(unittest.TestCase):
    def test_handshake_sequence(self):
        seq = mtk_mod.handshake_sequence()
        self.assertEqual(seq, [(0xA0, 0x5F), (0x0A, 0xF5),
                               (0x50, 0xAF), (0x05, 0xFA)])
        # Each exchange is a SINGLE byte — never a 4-byte packet.
        for send, expect in seq:
            self.assertTrue(0 <= send <= 0xFF)
            self.assertTrue(0 <= expect <= 0xFF)

    def test_get_hw_code_round_trip(self):
        self.assertEqual(mtk_mod.build_get_hw_code(), b"\xfd")
        hwcode, hwver = mtk_mod.parse_hw_code(b"\x67\x89\x00\x01")
        self.assertEqual(hwcode, 0x6789)
        self.assertEqual(hwver, 1)

    def test_parse_target_config(self):
        flags = mtk_mod.parse_target_config(0x07)
        self.assertTrue(flags["sbc"] and flags["sla"] and flags["daa"])
        self.assertTrue(flags["needs_auth"])
        flags = mtk_mod.parse_target_config(0x00)
        self.assertFalse(flags["needs_auth"])

    def test_detect_usb_parses_lsusb(self):
        fake = ("Bus 001 Device 002: ID 0e8d:0003 MediaTek Inc. "
                "MT65xx Preloader\n"
                "Bus 001 Device 003: ID 1234:5678 Something Else\n")
        with patch("openunlock.protocols.mtk.runner.run_quiet",
                   return_value=(0, fake)):
            found = mtk_mod.detect_usb()
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["mode"], "brom")


class TestQualcommProtocol(unittest.TestCase):
    def test_hello_response_framing(self):
        pkt = qc_mod.build_hello_response(mode=0)
        self.assertEqual(len(pkt), 48)
        cmd, length = qc_mod.parse_packet_header(pkt)
        self.assertEqual(cmd, 0x02)
        self.assertEqual(length, 0x30)

    def test_parse_hello_round_trip(self):
        body = struct.pack("<IIII", 2, 1, 0x100000, 0)
        body += struct.pack("<6I", 0, 0, 0, 0, 0, 0)
        pkt = qc_mod.pack_header(0x01, 0x30) + body
        parsed = qc_mod.parse_hello(pkt)
        self.assertEqual(parsed["version"], 2)
        self.assertEqual(parsed["max_len"], 0x100000)
        self.assertEqual(parsed["mode"], 0)

    def test_parse_hello_rejects_wrong_cmd(self):
        pkt = qc_mod.pack_header(0x05, 0x08)
        with self.assertRaises(OpenUnlockError):
            qc_mod.parse_hello(pkt)

    def test_parse_read_data(self):
        pkt = qc_mod.pack_header(0x03, 0x14) + struct.pack("<III", 1, 0x1000, 0x200)
        req = qc_mod.parse_read_data(pkt)
        self.assertEqual(req, {"image": 1, "offset": 0x1000, "length": 0x200})

    def test_build_done(self):
        pkt = qc_mod.build_done()
        self.assertEqual(pkt, struct.pack("<II", 0x05, 0x08))

    def test_program_xml(self):
        xml = qc_mod.program_xml("boot", "boot.img", 0x1000, 0x2000)
        self.assertIn('label="boot"', xml)
        self.assertIn('filename="boot.img"', xml)
        self.assertIn('start_sector="4096"', xml)
        root = ET.fromstring(xml.split("?>\n", 1)[1])
        self.assertEqual(root[0].tag, "program")

    def test_erase_xml(self):
        xml = qc_mod.erase_xml("frp", 0x200, 0x10)
        self.assertIn("<erase", xml)
        self.assertIn('label="frp"', xml)

    def test_parse_firehose_response(self):
        resp = qc_mod.parse_firehose_response(
            '<data><log value="hello" /><response value="ACK" /></data>')
        self.assertTrue(resp["ack"])
        self.assertEqual(resp["log"], ["hello"])
        nak = qc_mod.parse_firehose_response(
            '<data><response value="NAK" /></data>')
        self.assertFalse(nak["ack"])

    def test_detect_usb_parses_lsusb(self):
        fake = ("Bus 001 Device 004: ID 05c6:9008 Qualcomm, Inc. "
                "Gobi Wireless Modem (QDL mode)\n")
        with patch("openunlock.protocols.qualcomm.runner.run_quiet",
                   return_value=(0, fake)):
            found = qc_mod.detect_usb()
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["mode"], "edl")


class TestApple(unittest.TestCase):
    def test_parse_lsusb_dfu(self):
        out = ("Bus 001 Device 002: ID 05ac:1227 Apple, Inc. iPhone\n"
               "Bus 001 Device 003: ID 1234:5678 Other\n")
        found = apple_mod._parse_lsusb(out)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["pid"], 0x1227)

    def test_detect_apple_classifies_dfu(self):
        fake = "Bus 001 Device 002: ID 05ac:1227 Apple, Inc. iPhone\n"
        with patch("openunlock.apple.runner.run_quiet",
                   return_value=(0, fake)):
            devs = apple_mod.detect_apple()
        self.assertEqual(len(devs), 1)
        self.assertTrue(devs[0]["dfu"])
        self.assertEqual(devs[0]["mode"], "DFU mode")

    def test_detect_apple_none(self):
        with patch("openunlock.apple.runner.run_quiet",
                   return_value=(0, "Bus 001 Device 001: ID 1d6b:0002\n")):
            self.assertEqual(apple_mod.detect_apple(), [])


if __name__ == "__main__":
    unittest.main()
