# Roadmap

## v0.1 — done

- adb/fastboot core with typed errors and timeouts
- Device detection + info (adb + fastboot modes)
- Official bootloader unlock / relock with confirmation gates
- Flash / boot / erase (protected partitions refused) / factory reset
- Partition list + backup over adb
- Tkinter GUI
- Plugin interface + documented MTK / Qualcomm stubs
- Unit tests (mocked subprocess — no phone needed)

## v0.2 — done (this release, Nov 24, 2026)

- **MTK BROM framing as real code** — handshake sequence (4 single-byte
  exchanges), GET_HW_CODE build/parse, target-config flags, USB
  detection (pyusb or lsusb); live flash ops delegate to mtkclient.
- **Qualcomm Sahara + firehose framing as real code** — packet header
  pack/parse, hello parse/build, read-data parse, DONE/EXECUTE builders,
  firehose XML builders (configure/program/erase/power) + response
  parser; live ops delegate to the edl client.
- **Device profiles** — 15 brands + generic fallback in profiles.json
  (key combos, unlock quirks, chipsets); `info` attaches the profile.
- **IMEI** — read (dumpsys + service-call parcel parsing + fastboot
  getvar), backup (values + modemst1/modemst2/fsg), restore-original-only
  (serial match, no arbitrary-value path), verify (Luhn + live-vs-backup).
- **FRP** — status detection, partition erase via fastboot/MTK/EDL,
  5-method ADB bypass library with per-step reporting and firmware
  applicability metadata, test harness.
- **Screen lock** — factory reset + locksettings-db removal (rooted only).
- **Firmware inspection** — ZIP metadata, super/vbmeta, anti-rollback
  warnings.
- **Apple** — DFU/recovery detection + checkm8/usbliter8 research.
- **Docs** — FRP-METHODS.md, IMEI-RESEARCH.md, NEWEST-FIRMWARE-2026.md,
  PREVENTION-PROJECT.md (brief for the next project).
- 59 tests, all passing.

## v0.3 — live protocol sessions (next)

- Wire the framing into real USB sessions (pyusb transport): MTK
  handshake -> GET_HW_CODE -> DA load against a real device; Sahara
  hello -> loader upload -> firehose configure/program against a real
  EDL device. Both still need the user's own DA / firehose files.
- Samsung download-mode (Odin protocol) plugin skeleton.
- Xiaomi auth research notes.

## v1.0

- Plugin registry via entry points
- Per-model profiles (partition maps, quirks)
- Signed releases, Windows installer, `pip install openunlock`

## Next project (separate repo): prevention

See `docs/PREVENTION-PROJECT.md` — detect and prevent FRP/IMEI
exploits using the attack-surface inventory this project built.

## Never

- IMEI writes of arbitrary values (restore-from-own-backup only)
- FRP bypasses claimed to work on firmware where they are patched
- Redistributing vendor loaders, DA files, or firehose programmers
- Anything that services a phone without the owner's consent
