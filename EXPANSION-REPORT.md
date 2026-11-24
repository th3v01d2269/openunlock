# Expansion Report — OpenUnlock v0.1 → v0.2 (Nov 24, 2026)

## What was added, per module

### 1. `openunlock/imei.py` — full IMEI features (real code)
- **read**: IMEI/MEID via `dumpsys iphonesubinfo`, `service call
  iphonesubinfo` parcel parsing (reconstructs the Parcel hex dump and
  decodes the UTF-16 IMEI), vendor ril properties, and `fastboot getvar
  imei` as a last resort. Luhn validation on every value.
- **backup**: saves the values AND the `modemst1`/`modemst2`/`fsg`
  partitions into a JSON backup tied to the device serial; per-partition
  success/failure is recorded, not hidden.
- **restore**: flashes the backed-up modem partitions back via fastboot.
  Hard gates: `--confirm`, serial must match the backup (else
  RefusedError), values Luhn-checked. **No code path accepts an IMEI
  value to write** — restore takes a backup file only.
- **verify**: Luhn-checks the live IMEI and compares it with a backup.
- **Research doc**: `docs/IMEI-RESEARCH.md` — factory provisioning
  (Qualcomm NV item 550 / QPST-QCN, MTK NVRAM, Samsung EFS), where the
  IMEI lives, and how tampering is detected (fsg-vs-modemst mismatch,
  label-vs-live, NV write counters, Luhn, attestation, carrier-side).

### 2. `openunlock/frp.py` — WORKING FRP unlock (real code)
- **status**: `ro.frp.pst`, `sys.oem_unlock_allowed`, frp partition
  presence, `user_setup_complete` / `device_provisioned`, with a plain
  interpretation of what the readings mean.
- **erase**: `--method fastboot|mtk|edl` — fastboot `erase frp` (plus
  `config` with `--include-config`), mtkclient `e frp`, firehose erase
  with a user-supplied `--loader`. Confirm gate stays.
- **bypass method library**: 5 methods as executable step sequences
  (`talkback-settings`, `emergency-dialer`, `youtube-maps-settings`,
  `add-account-browser`, `samsung-setup-wizard`). `frp methods` lists
  the catalog; `frp try <method>` runs the `am start`/settings steps
  against a real device and reports each step ok/failed/manual.
- **test**: `frp test` re-checks setup state and gives a PASSED / NOT
  PASSED verdict — the only honest success criterion.
- **Research doc**: `docs/FRP-METHODS.md` — full catalog with firmware
  applicability AND a "how each method is detected / prevented" section
  per method (the bridge to the prevention project).

### 3. `openunlock/lockscreen.py`
- `lockscreen reset --confirm` (factory reset) and `lockscreen remove
  --confirm` (deletes locksettings.db* + gatekeeper keys, reboots).
  Remove is root-gated: it detects root via `su -c id` and refuses on
  a non-rooted device instead of failing halfway.

### 4. `openunlock/profiles.py` + `profiles.json`
- 15 brands (Samsung, Xiaomi, Oppo, Realme, OnePlus, Vivo, Huawei,
  Honor, Motorola, Google, Sony, Nokia, Infinix, Tecno, Asus) + generic
  fallback. Each: key combos (fastboot/recovery/download/EDL/BROM),
  unlock method + wait + quirks, chipset family, FRP partition.
- `profiles list` / `profiles show <brand>`; `info` attaches the
  matching profile automatically.

### 5. `openunlock/protocols/mtk.py` — real BROM scaffolding
- Handshake as 4 separate single-byte exchanges (0xA0→0x5F, 0x0A→0xF5,
  0x50→0xAF, 0x05→0xFA); GET_HW_CODE (0xFD) build/parse;
  GET_TARGET_CONFIG (0xD8) flag parsing (SBC/SLA/DAA); USB detection
  (pyusb or lsusb) for VID 0x0e8d PIDs 0x0003/0x2000/0x0001/0x200A.
- Live flash ops delegate to mtkclient when installed.

### 6. `openunlock/protocols/qualcomm.py` — real Sahara/firehose scaffolding
- Sahara packet header pack/parse, HELLO parse, HELLO_RESP builder
  (48 bytes), READ_DATA/READ_DATA64 parsers, DONE and EXECUTE builders,
  V3 command constants (0x0A CHIP_ID_V3_READ).
- Firehose XML builders (configure/program/erase/power) + response
  parser (ACK/NAK/log). EDL USB detection (05c6:9008).
- Live ops delegate to the edl client when installed.

### 7. `openunlock/apple.py`
- Apple detection via lsusb / system_profiler (DFU 0x1227, recovery
  0x1281). Research note on checkm8 (A5–A11, CVE-2019-8900) and
  usbliter8 (A12/A13, June 2026). No exploit code.

### 8. `openunlock/firmware.py`
- Firmware ZIP inspection: super.img (dynamic partitions), vbmeta/AVB,
  boot/recovery, metadata parsing, build.prop parsing, anti-rollback
  warnings (firmware newer than device; firmware older than device;
  wrong-device firmware). OTA payload.bin flagged as unsupported.

### 9. CLI / GUI / docs
- `cli.py`: new groups `imei`, `frp`, `lockscreen`, `profiles`,
  `firmware`, `apple`, `mtk`, `edl`, `plugins` — all with confirm gates.
- `gui.py`: second button row (FRP status, IMEI read/backup, profile,
  firmware inspect, lock removal).
- README (educational scope + guardrails), ROADMAP (v0.2 done, v0.3
  live sessions), ARCHITECTURE (new modules), version bumped to 0.2.0.
- New docs: `docs/FRP-METHODS.md`, `docs/IMEI-RESEARCH.md`,
  `docs/NEWEST-FIRMWARE-2026.md`, `docs/PREVENTION-PROJECT.md`.

### 10. Tests
- `tests/test_features.py`: 46 new tests (59 total, all passing).
  Covers IMEI Luhn/parcel parsing/backup-restore matching/serial
  refusal, FRP catalog + per-step runner + erase gates, lockscreen root
  checks, profile lookup + fallback, firmware ZIP inspection (fake ZIP
  built in-test), MTK handshake/HW-code/target-config, Sahara
  framing/firehose XML, Apple lsusb parsing.

## What is real working code vs documented stub

| Area | Status |
|---|---|
| adb/fastboot core, unlock, flash, backup | Real, tested |
| IMEI read/backup/restore/verify | Real (restore = partition restore from own backup) |
| FRP status/erase/method runner/test | Real (methods = executable step sequences) |
| Lockscreen reset/remove | Real (remove needs root) |
| Profiles, firmware inspect, Apple detect | Real |
| MTK handshake framing, HW-code parse | Real code; live USB session not yet wired (v0.3) |
| Sahara packet + firehose XML builders | Real code; live USB session not yet wired (v0.3) |
| MTK/Qualcomm flash read/write | Delegates to mtkclient/edl when installed; clear error otherwise |
| Apple exploit, FRP bypass on newest firmware | Deliberately not built (see below) |

## Working vs patched on newest firmware (honest assessment)

- **FRP bypasses**: no publicly documented working method exists for
  the newest firmware (Android 17 / Nov 2026 patches). TalkBack and
  emergency-dialer are patched since Android 9/10; intent/share-sheet
  escapes since Android 13; Samsung Android 15 setup-wizard loophole
  works only on some A/M-series with patches up to early 2026. The
  catalog says this per method. Partition-level `erase frp` still
  works where the bootloader/low-level mode is accessible — that is a
  function of bootloader state, not firmware version.
- **IMEI**: read/backup/restore work on current firmware (adb +
  fastboot paths). The write path needs root (partition backup) and
  fastboot (partition restore) — unchanged by firmware version.
- **MTK BROM**: Dimensity 9000+ / 9500 chips have patched BootROMs;
  classic exploit does not apply; valid DA + auth required.
- **Qualcomm EDL**: Sahara V3 needs a valid signed loader; loader
  autodetection is gone on V3 devices.
- **Samsung One UI 8**: OEM unlocking toggle removed — no unlock path.
- **Xiaomi HyperOS**: Community-app permission + ~72h wait; China
  models effectively closed.

## Newest-firmware facts verified (with sources)

- Android 17 current; QPR2 rolled out Nov 10, 2026 to 23 Pixel devices
  (Pixel 6a–11); Pixel 6/6 Pro end-of-life. (Android Police, TechRepublic,
  Droid-Life.)
- Nov 2026 bulletin: 216 CVEs, 23 Critical; patch levels 2026-11-01
  (119) and 2026-11-05 (97). (Google bulletin via TechRepublic et al.)
- Chipsets: Snapdragon 8 Elite Gen 5 (3nm N3P, 4.6 GHz), Dimensity 9500
  (3nm, 4.21 GHz), Exynos 2600 (2nm GAA, 3.8 GHz), Tensor G5, A19 Pro.
  (macmyths, geekchamp, mobilityarena, androlib.)
- Sahara constants verified against UltronTool PROTOCOL.md (qdl/edl
  cross-check), kernel Sahara docs, edl deepwiki.
- MTK handshake constants verified against DeepEyeUnlocker
  BROM_HANDSHAKE_FIX.md, da-boot deepwiki, mtkclient deepwiki.
- checkm8 (CVE-2019-8900, A5–A11) and usbliter8 (A12/A13, Paradigm
  Shift, June 2026) verified via The Apple Wiki and The Register.
- FRP method classes verified via EaseUS/Dr.Fone A16 guides (Oct 2026),
  Temaah Android 15 guide, sod-calculator Samsung guide.

## Deliberately not built (and why)

- **No IMEI changer.** No code path writes an arbitrary IMEI value.
  Restore is backup-to-same-device only. This is the legal boundary
  (UK 2002 Act; US fraud law) and it does not block any requested
  feature — read/backup/restore/verify all work.
- **No FRP bypass for newest firmware.** None is publicly documented;
  inventing one would be fabrication. The catalog labels the gap.
- **No vendor files.** No DA blobs, firehose programmers, Apple
  ramdisks, or leaked loaders in the repo; no code downloads them.
- **No checkm8/usbliter8 exploit implementation.** Detection +
  research documentation only; the exploit lives in checkra1n/palera1n.
- **No live USB sessions yet.** The framing is real code; driving it
  over USB against a real device is v0.3 work (pyusb transport).

## Prevention project seeded

`docs/PREVENTION-PROJECT.md` — brief for the defensive follow-up:
goal, attack-surface inventory from this project, six detection ideas
(FRP partition integrity, setup-wizard reachability audit, patch-level
attestation, IMEI cross-checks, bootloader-state signal, low-level-mode
traces), and a proposed project structure. The tool itself is not built
yet — the brief is the starting spec.
