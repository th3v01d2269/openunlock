# Architecture

## Why adb/fastboot is the core

UnlockTool and every paid servicing tool ultimately talk to the phone over
USB. For a phone that is alive, the free, documented channels already exist:

- **adb** — Android Debug Bridge. Ships with Google's platform-tools.
  Shell access, properties, file transfer, reboot targets. Needs USB
  debugging on and the RSA prompt accepted.
- **fastboot** — bootloader protocol. Flashing, erasing, booting images,
  `flashing unlock` / `flashing lock`, `getvar`. Needs the bootloader.

Everything in `openunlock/` v0.1 is a typed, tested wrapper around those
two. No raw USB, no proprietary drivers, no accounts.

## Layers

```
CLI / GUI
   │  (argparse / Tkinter — presentation only, no logic)
   ▼
operations: unlock.py, flash.py, backup.py, device.py, imei.py, frp.py,
  lockscreen.py, profiles.py, firmware.py, apple.py
   │  (safety gates live here: --confirm, protected partitions,
   │   IMEI restore-from-own-backup-only, FRP method metadata,
   │   root checks, input validation)
   ▼
transports: adb.py, fastboot.py
   │  (one class per tool; parsing lives here and is unit-tested)
   ▼
runner.py
   │  (subprocess, timeouts, ToolNotFoundError, CommandFailedError)
   ▼
adb / fastboot binaries (Google platform-tools)
```

Rules:

1. **Presentation never runs a command.** CLI/GUI call operation functions.
2. **Operations never run a binary.** They call transport methods.
3. **Transports never decide policy.** They run and parse.
4. **Every destructive path has a gate** in the operation layer
   (`confirm=True`), tested in `tests/test_openunlock.py`.

## Plugin system

`openunlock/protocols/base.py` defines `ProtocolPlugin`. A plugin owns one
chipset's low-level mode (MTK BootROM, Qualcomm Sahara/firehose) and exposes
`detect / device_info / read_partition / write_partition / restore_imei`.
The framing is real code in this repo (MTK handshake + GET_HW_CODE,
Sahara packet builders, firehose XML builders); live flash operations
delegate to the installed open-source tools (`mtk`, `edl`) because the
actual transfer needs their DA/firehose handling and the user's own
loader files. Plugins must follow the same safety rules as the core
(restore-original-only IMEI, confirm gates).

## What a full UnlockTool clone would also need

- Per-chipset Download Agents / firehose programmers (vendor files — the
  project will never redistribute these; users supply their own).
- Live USB sessions for the framed protocols (v0.3: pyusb transport
  driving the MTK handshake and Sahara state machine against real
  devices).
- Per-model profiles (partition maps, unlock quirks, auth requirements).
- A signed release + update channel.

That is the roadmap in `docs/ROADMAP.md`, not a promise for v0.2.

## New modules in v0.2

- `imei.py` — read (3 sources), backup (values + modem partitions),
  restore (partition restore, serial gate), verify (Luhn + compare).
- `frp.py` — status detection, erase (3 transports), METHODS catalog
  (5 methods, executable steps + metadata), `run_method` per-step
  reporting, `test_frp` harness.
- `lockscreen.py` — reset (factory reset) + remove (root-gated
  locksettings-db deletion).
- `profiles.py` + `profiles.json` — 15 brands + generic fallback.
- `firmware.py` — ZIP inspection, AVB/super detection, anti-rollback
  warnings, device comparison.
- `apple.py` — DFU/recovery detection (lsusb/system_profiler) +
  checkm8/usbliter8 research note.
- `protocols/mtk.py`, `protocols/qualcomm.py` — real framing code (see
  above); `protocols/__init__.py` — plugin registry.
