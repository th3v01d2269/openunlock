# Changelog

All notable changes to OpenUnlock. Format follows Keep a Changelog;
versioning follows SemVer.

## [Unreleased]

### Added
- Termux support: `termux/install-termux.sh` + `docs/TERMUX.md` —
  run the full CLI from a phone (wireless debugging or USB OTG),
  installable with `pkg install python android-tools git`.
- Android APK in progress (Chaquopy + Shizuku, `android/`).

## [0.2.0] — 2026-11-24

### Added
- IMEI read / backup / restore / verify (`imei.py`, `docs/IMEI-RESEARCH.md`).
  Restore is backup-to-same-device only; no code path writes an arbitrary
  IMEI value.
- Working FRP unlock (`frp.py`, `docs/FRP-METHODS.md`): status detection,
  partition erase via fastboot/MTK/EDL, an executable bypass-method
  library with per-method firmware applicability, and a `frp test`
  verification harness.
- Screen-lock removal (`lockscreen.py`): factory reset, or
  locksettings-db removal on rooted devices only.
- Device profiles for 15 brands + generic fallback (`profiles.py`,
  `profiles.json`): key combos, unlock quirks, chipsets, FRP partition.
  `info` attaches the matching profile automatically.
- MTK BROM framing as real code (`protocols/mtk.py`): 4-step handshake,
  GET_HW_CODE, target-config flags, USB detection. Live ops delegate to
  mtkclient when installed.
- Qualcomm Sahara/firehose framing as real code
  (`protocols/qualcomm.py`): packet builders/parsers, firehose XML
  builders, EDL USB detection. Live ops delegate to the edl client.
- Apple A12/A13 detection (`apple.py`): DFU/recovery via lsusb /
  system_profiler, plus checkm8/usbliter8 research notes. No exploit code.
- Firmware inspection (`firmware.py`): ZIP metadata, super/vbmeta
  detection, anti-rollback warnings.
- CLI groups: `imei`, `frp`, `lockscreen`, `profiles`, `firmware`,
  `apple`, `mtk`, `edl`, `plugins`. GUI second button row.
- Docs: `docs/FRP-METHODS.md`, `docs/IMEI-RESEARCH.md`,
  `docs/NEWEST-FIRMWARE-2026.md`, `docs/PREVENTION-PROJECT.md`
  (brief for the defensive follow-up project).
- 46 new tests (59 total, all passing).

### Honest limits (see README)
- No public FRP bypass exists for the newest firmware (Android 17 /
  Nov 2026 patches); the catalog labels the gap instead of inventing one.
- Live MTK/Qualcomm USB sessions are v0.3 work; framing is real code,
  the USB transport is not yet wired.
- No vendor files (DA blobs, firehose programmers, Apple ramdisks) in
  this repo, and no code downloads them.

## [0.1.0] — 2026-11-24

### Added
- adb/fastboot core with typed errors and timeouts.
- Device detection + info (adb + fastboot modes).
- Official bootloader unlock / relock with confirmation gates.
- Flash / boot / erase (protected partitions refused) / factory reset.
- Partition list + backup over adb.
- Tkinter GUI, plugin interface, documented MTK/Qualcomm stubs.
- 13 unit tests (mocked subprocess — no phone needed).
