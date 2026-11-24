"""Command-line interface for OpenUnlock.

Every destructive command requires --confirm. Run `openunlock --help`
for the full command list, or `openunlock <group> --help` per group.
"""
import argparse
import json
import sys

from . import (__version__, apple, backup, device as device_mod, firmware,
               flash, frp, imei, lockscreen, profiles as profiles_mod,
               unlock)
from .adb import Adb
from .errors import OpenUnlockError
from .protocols import get_plugin, list_plugins


def _serial_arg(p):
    p.add_argument("--serial", help="target a specific device serial")


def _confirm_arg(p):
    p.add_argument("--confirm", action="store_true",
                   help="confirm a destructive operation")


def build_parser():
    p = argparse.ArgumentParser(
        prog="openunlock",
        description="Open-source Android phone servicing toolkit.")
    p.add_argument("--version", action="version",
                   version=f"openunlock {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("devices", help="list attached phones")
    s.set_defaults(func=cmd_devices)

    s = sub.add_parser("info", help="show full info for the attached phone")
    _serial_arg(s)
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_info)

    s = sub.add_parser("unlock", help="unlock the bootloader (WIPES the phone)")
    _serial_arg(s)
    _confirm_arg(s)
    s.set_defaults(func=cmd_unlock)

    s = sub.add_parser("relock", help="relock the bootloader")
    _serial_arg(s)
    _confirm_arg(s)
    s.set_defaults(func=cmd_relock)

    s = sub.add_parser("flash", help="flash a partition image")
    s.add_argument("partition")
    s.add_argument("image")
    _serial_arg(s)
    _confirm_arg(s)
    s.set_defaults(func=cmd_flash)

    s = sub.add_parser("boot", help="boot an image once, without flashing")
    s.add_argument("image")
    _serial_arg(s)
    s.set_defaults(func=cmd_boot)

    s = sub.add_parser("reset", help="factory reset (WIPES the phone)")
    _serial_arg(s)
    _confirm_arg(s)
    s.set_defaults(func=cmd_reset)

    s = sub.add_parser("partitions", help="list partitions on the phone")
    _serial_arg(s)
    s.set_defaults(func=cmd_partitions)

    s = sub.add_parser("backup", help="back up one partition over adb")
    s.add_argument("partition")
    s.add_argument("--out", default="./backups")
    _serial_arg(s)
    s.set_defaults(func=cmd_backup)

    s = sub.add_parser("reboot", help="reboot the phone")
    s.add_argument("target", nargs="?", default="",
                   choices=["", "recovery", "bootloader", "fastboot", "edl"])
    _serial_arg(s)
    s.set_defaults(func=cmd_reboot)

    # ---- IMEI ----
    s = sub.add_parser("imei", help="IMEI read / backup / restore / verify")
    imei_sub = s.add_subparsers(dest="imei_cmd", required=True)
    q = imei_sub.add_parser("read", help="read IMEI/MEID from the phone")
    _serial_arg(q)
    q.set_defaults(func=cmd_imei_read)
    q = imei_sub.add_parser("backup", help="back up IMEI values + modem partitions")
    _serial_arg(q)
    q.add_argument("--out", default="./backups")
    q.set_defaults(func=cmd_imei_backup)
    q = imei_sub.add_parser("restore", help="restore the phone's ORIGINAL IMEI from its own backup")
    q.add_argument("--from", dest="backup", required=True)
    _serial_arg(q)
    _confirm_arg(q)
    q.set_defaults(func=cmd_imei_restore)
    q = imei_sub.add_parser("verify", help="Luhn-check live IMEI, compare with a backup")
    q.add_argument("--from", dest="backup", default=None)
    _serial_arg(q)
    q.set_defaults(func=cmd_imei_verify)

    # ---- FRP ----
    s = sub.add_parser("frp", help="Factory Reset Protection tools")
    frp_sub = s.add_subparsers(dest="frp_cmd", required=True)
    q = frp_sub.add_parser("official", help="print the official FRP recovery path")
    q.set_defaults(func=cmd_frp_official)
    q = frp_sub.add_parser("status", help="detect FRP / setup state")
    _serial_arg(q)
    q.set_defaults(func=cmd_frp_status)
    q = frp_sub.add_parser("methods", help="list the bypass method catalog")
    q.set_defaults(func=cmd_frp_methods)
    q = frp_sub.add_parser("try", help="run one bypass method's steps")
    q.add_argument("method")
    _serial_arg(q)
    q.set_defaults(func=cmd_frp_try)
    q = frp_sub.add_parser("erase", help="erase the frp partition")
    q.add_argument("--method", default="fastboot",
                   choices=["fastboot", "mtk", "edl"])
    q.add_argument("--loader", default=None,
                   help="firehose programmer (EDL method only)")
    q.add_argument("--include-config", action="store_true")
    _serial_arg(q)
    _confirm_arg(q)
    q.set_defaults(func=cmd_frp_erase)
    q = frp_sub.add_parser("test", help="verify whether FRP still blocks setup")
    _serial_arg(q)
    q.set_defaults(func=cmd_frp_test)

    # ---- Screen lock ----
    s = sub.add_parser("lockscreen", help="screen-lock removal")
    ls_sub = s.add_subparsers(dest="ls_cmd", required=True)
    q = ls_sub.add_parser("reset", help="factory reset (removes the lock, wipes data)")
    _serial_arg(q)
    _confirm_arg(q)
    q.set_defaults(func=cmd_ls_reset)
    q = ls_sub.add_parser("remove", help="remove lock credentials (ROOTED devices only)")
    _serial_arg(q)
    _confirm_arg(q)
    q.set_defaults(func=cmd_ls_remove)

    # ---- Profiles ----
    s = sub.add_parser("profiles", help="device brand profiles")
    pr_sub = s.add_subparsers(dest="pr_cmd", required=True)
    q = pr_sub.add_parser("list", help="list all brand profiles")
    q.set_defaults(func=cmd_profiles_list)
    q = pr_sub.add_parser("show", help="show one brand profile")
    q.add_argument("brand")
    q.set_defaults(func=cmd_profiles_show)

    # ---- Firmware ----
    s = sub.add_parser("firmware", help="firmware package inspection")
    fw_sub = s.add_subparsers(dest="fw_cmd", required=True)
    q = fw_sub.add_parser("inspect", help="inspect a firmware ZIP")
    q.add_argument("file")
    _serial_arg(q)
    q.set_defaults(func=cmd_firmware_inspect)

    # ---- Apple ----
    s = sub.add_parser("apple", help="Apple A12/A13 detection (research)")
    ap_sub = s.add_subparsers(dest="ap_cmd", required=True)
    q = ap_sub.add_parser("detect", help="detect Apple devices in DFU/recovery")
    q.set_defaults(func=cmd_apple_detect)

    # ---- Chipset protocols ----
    s = sub.add_parser("mtk", help="MediaTek BootROM protocol")
    mtk_sub = s.add_subparsers(dest="mtk_cmd", required=True)
    q = mtk_sub.add_parser("detect", help="detect MTK devices in BROM/preloader")
    q.set_defaults(func=cmd_mtk_detect)
    q = mtk_sub.add_parser("info", help="show MTK device info")
    q.set_defaults(func=cmd_mtk_info)
    q = mtk_sub.add_parser("read", help="read a partition (needs mtkclient)")
    q.add_argument("partition")
    q.add_argument("out")
    q.set_defaults(func=cmd_mtk_read)
    q = mtk_sub.add_parser("write", help="write a partition (needs mtkclient)")
    q.add_argument("partition")
    q.add_argument("image")
    _confirm_arg(q)
    q.set_defaults(func=cmd_mtk_write)

    s = sub.add_parser("edl", help="Qualcomm EDL / Sahara / firehose")
    edl_sub = s.add_subparsers(dest="edl_cmd", required=True)
    q = edl_sub.add_parser("detect", help="detect Qualcomm devices in EDL (9008)")
    q.set_defaults(func=cmd_edl_detect)
    q = edl_sub.add_parser("info", help="show EDL device info")
    q.set_defaults(func=cmd_edl_info)
    q = edl_sub.add_parser("read", help="read a partition (needs edl client)")
    q.add_argument("partition")
    q.add_argument("out")
    q.add_argument("--loader", default=None)
    q.set_defaults(func=cmd_edl_read)
    q = edl_sub.add_parser("write", help="write a partition (needs edl client)")
    q.add_argument("partition")
    q.add_argument("image")
    q.add_argument("--loader", default=None)
    _confirm_arg(q)
    q.set_defaults(func=cmd_edl_write)

    s = sub.add_parser("plugins", help="list protocol plugins")
    s.set_defaults(func=cmd_plugins)

    s = sub.add_parser("gui", help="open the graphical interface")
    s.set_defaults(func=cmd_gui)

    return p


# ---- core commands ----

def cmd_devices(args):
    found = device_mod.detect()
    if not found:
        print("No devices found. Connect a phone (adb or fastboot mode).")
        return 0
    for d in found:
        print(f"{d.serial}\t{d.mode}")
    return 0


def cmd_info(args):
    dev = device_mod.require_one(args.serial)
    info = device_mod.info_dict(dev)
    if args.json:
        print(json.dumps(info, indent=2))
    else:
        for key, value in info.items():
            print(f"{key}: {value}")
    return 0


def cmd_unlock(args):
    print("WARNING: unlocking the bootloader factory-resets the phone.")
    print("All user data will be erased. This cannot be undone.")
    print(unlock.unlock(args.serial, confirm=args.confirm))
    return 0


def cmd_relock(args):
    print("WARNING: only relock with stock firmware installed.")
    print("Relocking over custom firmware can brick the phone.")
    print(unlock.relock(args.serial, confirm=args.confirm))
    return 0


def cmd_flash(args):
    print(f"Flashing {args.partition} with {args.image} ...")
    print(flash.flash_partition(args.partition, args.image,
                                args.serial, confirm=args.confirm))
    return 0


def cmd_boot(args):
    print(flash.boot_image(args.image, args.serial))
    return 0


def cmd_reset(args):
    print("WARNING: factory reset erases all user data.")
    print(flash.factory_reset(args.serial, confirm=args.confirm))
    return 0


def cmd_partitions(args):
    for part in backup.list_partitions(args.serial):
        print(part)
    return 0


def cmd_backup(args):
    path = backup.backup_partition(args.partition, args.out, args.serial)
    print(f"Saved {args.partition} to {path}")
    return 0


def cmd_reboot(args):
    adb = Adb(args.serial)
    adb.require_device()
    print(adb.reboot(args.target))
    return 0


# ---- IMEI ----

def cmd_imei_read(args):
    info = imei.read_imei(args.serial)
    print(f"IMEI: {', '.join(info['imei']) or '—'}")
    print(f"MEID: {info['meid'] or '—'}")
    print(f"Source: {info.get('source') or '—'}")
    for value in info["imei"]:
        print(f"  {value}: Luhn {'OK' if imei.luhn_valid(value) else 'INVALID'}")
    return 0


def cmd_imei_backup(args):
    path = imei.backup_imei(args.serial, args.out)
    data = imei.load_backup(path)
    print(f"Saved IMEI backup to {path}")
    print(f"  IMEI: {', '.join(data['imei'])}")
    for part, entry in data["partitions"].items():
        print(f"  {part}: {entry['status']}")
    return 0


def cmd_imei_restore(args):
    print("WARNING: this writes the backed-up modem partitions to the phone.")
    print("The backup must belong to THIS device — the serial is checked.")
    print(imei.restore_imei(args.backup, args.serial, confirm=args.confirm))
    return 0


def cmd_imei_verify(args):
    result = imei.verify_imei(args.backup, args.serial)
    print(f"Live IMEI: {', '.join(result['live']) or '—'}")
    for value, ok in zip(result["live"], result["luhn_ok"]):
        print(f"  {value}: Luhn {'OK' if ok else 'INVALID'}")
    if args.backup:
        print(f"Backup IMEI: {', '.join(result['backup_imei'])}")
        print(f"Matches backup: {'YES' if result['matches_backup'] else 'NO'}")
    return 0


# ---- FRP ----

def cmd_frp_official(args):
    print(frp.official_path())
    return 0


def cmd_frp_status(args):
    s = frp.status(args.serial)
    for key, value in s.items():
        print(f"{key}: {value}")
    return 0


def cmd_frp_methods(args):
    print("FRP bypass method catalog (see docs/FRP-METHODS.md for detail):")
    for m in frp.list_methods():
        print(f"\n{m['id']} — {m['name']}")
        print(f"  Applies to: {m['applies_to']}")
        print(f"  Status: {m['status']} (patched: {m['patched_as_of']})")
    print("\nUse only on a phone you own. Newest firmware: most methods "
          "are patched — see the catalog.")
    return 0


def cmd_frp_try(args):
    print(frp.official_path())
    print()
    report = frp.run_method(args.method, args.serial)
    print(f"Method: {report['name']} [{report['status']}]")
    print(f"Applies to: {report['applies_to']}")
    for step in report["steps"]:
        mark = {"ok": "[ok]", "failed": "[FAILED]",
                "manual — do this on the phone": "[MANUAL]"}.get(
                    step["result"], f"[{step['result']}]")
        print(f"  {mark} step {step['n']}: {step['desc']}")
        if step.get("output"):
            print(f"      {step['output']}")
    print(report["note"])
    print("Next: run `openunlock frp test` to check whether FRP is gone.")
    return 0


def cmd_frp_erase(args):
    print("WARNING: erasing the FRP partition removes the lock record. "
          "Use only on a phone you own.")
    print(frp.erase_frp(args.serial, confirm=args.confirm,
                        method=args.method,
                        include_config=args.include_config,
                        loader=args.loader))
    return 0


def cmd_frp_test(args):
    result = frp.test_frp(args.serial)
    for key, value in result.items():
        print(f"{key}: {value}")
    return 0


# ---- Screen lock ----

def cmd_ls_reset(args):
    print("WARNING: factory reset erases all user data.")
    print(lockscreen.reset_lock(args.serial, confirm=args.confirm))
    return 0


def cmd_ls_remove(args):
    print("WARNING: this deletes the lock credential database and reboots.")
    print(lockscreen.remove_lock(args.serial, confirm=args.confirm))
    return 0


# ---- Profiles ----

def cmd_profiles_list(args):
    for brand, chips in profiles_mod.list_profiles():
        print(f"{brand}: {chips}")
    return 0


def cmd_profiles_show(args):
    print(profiles_mod.format_profile(
        profiles_mod.get_profile(args.brand)))
    return 0


# ---- Firmware / Apple / protocols ----

def cmd_firmware_inspect(args):
    print(firmware.format_report(
        firmware.inspect_firmware(args.file, args.serial)))
    return 0


def cmd_apple_detect(args):
    devs = apple.detect_apple()
    if not devs:
        print("No Apple device detected on USB.")
    for d in devs:
        print(f"Apple device PID 0x{d['pid']:04x}: {d['mode']}"
              f" — {d['description']}")
    print()
    print(apple.apple_research_note())
    return 0


def cmd_mtk_detect(args):
    plugin = get_plugin("mtk")
    print(f"MTK devices in BROM/preloader: {plugin.detect()}")
    return 0


def cmd_mtk_info(args):
    print(get_plugin("mtk").device_info())
    return 0


def cmd_mtk_read(args):
    print(get_plugin("mtk").read_partition(args.partition, args.out))
    return 0


def cmd_mtk_write(args):
    if not args.confirm:
        print("Writing a partition requires --confirm.")
        return 1
    print(get_plugin("mtk").write_partition(args.partition, args.image))
    return 0


def cmd_edl_detect(args):
    plugin = get_plugin("qualcomm")
    print(f"Qualcomm devices in EDL (9008): {plugin.detect()}")
    return 0


def cmd_edl_info(args):
    print(get_plugin("qualcomm").device_info())
    return 0


def cmd_edl_read(args):
    print(get_plugin("qualcomm").read_partition(
        args.partition, args.out, loader=args.loader))
    return 0


def cmd_edl_write(args):
    if not args.confirm:
        print("Writing a partition requires --confirm.")
        return 1
    print(get_plugin("qualcomm").write_partition(
        args.partition, args.image, loader=args.loader))
    return 0


def cmd_plugins(args):
    for name, display in list_plugins():
        print(f"{name}: {display}")
    return 0


def cmd_gui(args):
    from .gui import run_gui
    run_gui()
    return 0


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except OpenUnlockError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
