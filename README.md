# OpenUnlock — an open-source phone servicing toolkit

A free, open-source foundation for the kind of work paid tools like
[UnlockTool](https://www.unlocktool.org/) do: detect Android phones, read
device info, unlock bootloaders the official way, flash firmware, back up
partitions, and factory-reset. Built as a computer-science project — clean
Python, no proprietary blobs, no license fees, no accounts.

**What this is not:** a 1:1 clone of UnlockTool. The commercial tool's real
moat is years of reverse-engineered, proprietary per-chipset loaders (MediaTek
DA files, Qualcomm firehose programmers, Apple ramdisks). Those can't be
reproduced in one project, and this repo doesn't try. What it does is build
the honest, working core on top of the free tools that already exist
(`adb`, `fastboot`) and a plugin architecture where chipset modules can grow
— with pointers to the open-source projects that already solved parts of it
(`mtkclient`, `edl`).

## Features (working now)

| Feature | How | Needs |
|---|---|---|
| List connected devices | `adb devices` + `fastboot devices` | platform-tools |
| Full device info + brand profile | model, Android version, bootloader state, matched profile | adb |
| Bootloader unlock / relock | `fastboot flashing unlock` (official OEM flow) | unlocked-allowed device, fastboot |
| Flash a partition | `fastboot flash <part> <file>` | firmware file, fastboot |
| Boot an image once | `fastboot boot <file>` | image, fastboot |
| Factory reset | `fastboot -w` / recovery wipe | fastboot |
| Partition backup | `adb pull` from `/dev/block/by-name` | root/adb-root, or a rooted device |
| IMEI read / backup / restore / verify | dumpsys + service-call parcel parsing; modemst/fsg backup | adb (+ root for partitions) |
| FRP status / erase / bypass methods / test | partition erase via fastboot/MTK/EDL; ADB method library | fastboot or chipset tool |
| Screen-lock removal | factory reset, or locksettings-db removal (rooted only) | adb (+ root for remove) |
| Firmware inspection | ZIP metadata, super/vbmeta detection, anti-rollback warnings | a firmware ZIP |
| Apple A12/A13 detection | DFU/recovery detection via lsusb/system_profiler | lsusb or macOS |
| MTK BROM + Qualcomm Sahara framing | handshake/Sahara packet builders, firehose XML | pyusb optional; mtkclient/edl for live ops |
| GUI | Tkinter device panel | Python 3 + Tk |
| Plugin system | `openunlock.protocols` | — |

## Scope and legal guardrails (educational project)

This is a computer-science project on defensive security research: the
FRP and IMEI features exist so the NEXT project can learn to detect and
prevent them (see `docs/PREVENTION-PROJECT.md`). The guardrails are part
of the design, not an afterthought:

- **IMEI: restore-original-only.** `imei restore` takes a backup file
  from the same device serial — there is no parameter anywhere that
  accepts an IMEI value to write. Changing an IMEI to a different value
  is illegal in the UK (Mobile Telephones (Re-programming) Act 2002)
  and fraud in the US when done to evade a blacklist. The legitimate
  use is repair: restoring a phone's own IMEI after a bad flash wiped
  it. See `docs/IMEI-RESEARCH.md`.
- **FRP: documented methods only, honestly labelled.** The bypass
  library implements publicly documented entry points (TalkBack,
  emergency dialer, intent/share-sheet escapes, setup-wizard
  loopholes). Each method carries its firmware applicability and patch
  status — most are patched on current firmware, and the catalog says
  so. There is no invented bypass for the newest firmware. The
  partition-level erase (`erase frp`) is the same operation mtkclient
  and edl perform. See `docs/FRP-METHODS.md`.
- **No vendor files, ever.** No DA blobs, firehose programmers, Apple
  ramdisks, or leaked loaders in this repo, and no code that downloads
  them. Users supply their own files for their own devices.
- **Use it on phones you own.** Every destructive command needs
  `--confirm` and prints what it is about to do first.
- **No accounts, no phone-home, no license checks.** Stdlib only
  (pyusb optional, for direct USB detection).

## Install

```bash
# 1. Android platform-tools (adb + fastboot) — free from Google:
#    https://developer.android.com/tools/adb
#    or: sudo apt install android-tools-adb android-tools-fastboot
# 2. Python 3.10+
git clone https://github.com/th3v01d2269/openunlock.git
cd openunlock
pip install -e .
```

No third-party Python dependencies. Standard library only.

## Termux (run it from a phone)

No PC needed — see [docs/TERMUX.md](docs/TERMUX.md). In Termux:

```bash
pkg install python android-tools git
git clone https://github.com/th3v01d2269/openunlock.git ~/openunlock
cd ~/openunlock && pip install -e . --break-system-packages
openunlock devices
```

CLI only in Termux (no GUI — no Tk display). Connect a target phone over
wireless debugging or USB OTG.

## Android app (APK)

A native Kotlin app version is in `android/` — see
[docs/ANDROID.md](docs/ANDROID.md). Debug APK: `android/app-debug.apk`
(`com.openunlock`, v0.2.5, minSdk 26). Live features need the Shizuku
app; offline features (profiles, FRP catalog, IMEI checks, firmware
inspect) work without it. The APK is a port of the Python logic, not an
embedded Python runtime — Gradle cannot build in this sandbox, so it is
built with kotlinc + aapt2 + d8 directly (`android/manual/build-manual.sh`).
v0.2.2 adds Tasker + Shizuku integration (new deep links, rish tasks, setup check — see docs/NFC.md and tasker/README.md) on top of the v0.2.1 NFC tap-to-run (the client phone is the tag — see
[docs/NFC.md](docs/NFC.md)) on top of the original features; nothing
original was removed. v0.2.3 is a diagnostic + hardened release: v0.2.2
would not open at all on the user's moto g 2025, so startup is now
wrapped in try/catch with an on-screen crash report and a Diagnostics
section. v0.2.4 fixes the tap crash: v0.2.3 opened, but every button tap
closed the app — a global crash handler (any thread) now shows the crash
in a CrashActivity instead of vanishing, every tap handler is guarded,
and the version line sits at the top of the screen. Tested on the user's
moto g 2025: v0.2.3 opens, v0.2.4 still closed on every tap, v0.2.5 is
the intent audit being tested — every intent resolves before firing,
every tap is logged before its work runs.

## Use

```bash
openunlock devices                 # list attached phones (adb + fastboot)
openunlock info                    # full info for the attached phone
openunlock info --serial R5CX123   # target one phone
openunlock unlock --confirm        # official bootloader unlock (WIPES the phone)
openunlock relock --confirm
openunlock flash boot boot.img --confirm
openunlock boot recovery.img
openunlock reset --confirm         # factory reset (WIPES the phone)
openunlock partitions              # list partitions on the phone
openunlock backup boot --out ./backups
openunlock imei read               # read IMEI/MEID (+ Luhn check)
openunlock imei backup             # back up IMEI values + modemst/fsg
openunlock imei restore --from backup.json --confirm
openunlock imei verify --from backup.json
openunlock frp official            # the official FRP recovery path
openunlock frp status              # detect FRP / setup state
openunlock frp methods             # the bypass method catalog
openunlock frp try talkback-settings
openunlock frp erase --confirm     # erase the frp partition
openunlock frp test                # verify whether FRP still blocks
openunlock lockscreen reset --confirm
openunlock lockscreen remove --confirm   # rooted devices only
openunlock profiles list
openunlock profiles show xiaomi
openunlock firmware inspect firmware.zip [--serial R5CX123]
openunlock apple detect            # Apple devices in DFU/recovery
openunlock mtk detect              # MediaTek BROM/preloader devices
openunlock edl detect              # Qualcomm EDL (9008) devices
openunlock gui                     # graphical interface
```

Every destructive command (`unlock`, `relock`, `flash`, `reset`) requires
`--confirm` and prints exactly what it is about to do first.

## Architecture

```
openunlock/
  runner.py    subprocess wrapper: finds binaries, timeouts, clean errors
  adb.py       adb: devices, shell, properties, reboot
  fastboot.py  fastboot: devices, getvar, flash/erase/boot, unlock
  device.py    Device model + detection across adb/fastboot (+ profile match)
  unlock.py    bootloader unlock/relock flow with safety gates
  flash.py     partition flashing + image booting
  backup.py    partition listing + backup over adb
  imei.py      IMEI read / backup (values + modemst/fsg) / restore-original /
               verify (Luhn + live-vs-backup)
  frp.py       FRP status, partition erase (fastboot/MTK/EDL), bypass method
               library (executable steps + metadata), test harness
  lockscreen.py  screen-lock removal: factory reset, or locksettings-db
               removal on rooted devices only
  profiles.py + profiles.json  per-brand registry (key combos, unlock
               quirks, chipsets) + generic fallback
  firmware.py  firmware ZIP inspection: super/vbmeta, metadata,
               anti-rollback warnings
  apple.py     Apple DFU/recovery detection + checkm8/usbliter8 research
  protocols/   MTK BROM framing + Qualcomm Sahara/firehose framing,
               delegating live ops to mtkclient / edl
  gui.py       Tkinter interface
  cli.py       command-line interface
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and
[docs/ROADMAP.md](docs/ROADMAP.md). Research docs:
[docs/FRP-METHODS.md](docs/FRP-METHODS.md),
[docs/IMEI-RESEARCH.md](docs/IMEI-RESEARCH.md),
[docs/NEWEST-FIRMWARE-2026.md](docs/NEWEST-FIRMWARE-2026.md),
[docs/PREVENTION-PROJECT.md](docs/PREVENTION-PROJECT.md) (the next project).

## Roadmap

1. **v0.2 — DONE (this release).** MTK BROM framing + Qualcomm Sahara/
   firehose framing as real code (handshake, packet builders, XML
   builders); mtkclient/edl delegation for live ops. Device profiles
   for 15 brands + generic fallback. IMEI read/backup/restore/verify.
   FRP status/erase/method library/test harness. Screen-lock removal.
   Firmware inspection. Apple DFU/recovery detection. 59 tests.
2. **v0.3 — live protocol sessions.** Wire the framing into real USB
   sessions (pyusb transport): MTK handshake -> GET_HW_CODE -> DA load
   against a real device; Sahara hello -> loader upload -> firehose
   configure/program against a real EDL device. Both still need the
   user's own DA / firehose files.
3. **v0.4 — Samsung download-mode (Odin protocol) plugin, Xiaomi
   auth-bypass research notes.**
4. **v1.0 — plugin registry, per-model profiles, signed releases.**

Next project (separate repo): **prevention** — see
`docs/PREVENTION-PROJECT.md`: detect and prevent FRP/IMEI exploits
using the attack-surface inventory this project built.

## Contributing

PRs welcome. Rules: no proprietary loaders or leaked vendor files, no
IMEI code path that writes an arbitrary value (restore-from-own-backup
only), every destructive path needs a confirmation gate and a test.
See `CONTRIBUTING.md` when it lands.

## License

MIT. See [LICENSE](LICENSE).
