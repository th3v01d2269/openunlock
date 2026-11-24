# Prevention Project — brief for the defensive follow-up

## Goal

Detect and prevent FRP bypasses and IMEI tampering — the exploits the
OpenUnlock project implements for research. The premise: you cannot
prevent what you cannot enumerate, so the first project built the
attack surface inventory; this project turns it into detection and
prevention.

## What OpenUnlock teaches (attack-surface inventory)

From `openunlock/frp.py` + `docs/FRP-METHODS.md`:

| Attack surface | Method | Current state (Nov 2026) |
|---|---|---|
| Setup-wizard accessibility entry points | TalkBack -> Help & Feedback -> YouTube -> Settings | Mostly patched; Samsung A/M Android 15 partially open |
| Emergency dialer | Dialer -> notification shade -> Settings | Patched since Android 9 |
| Intent / share-sheet escapes | Maps/YouTube intent -> share -> Settings | Patched Android 13+ |
| Account-recovery WebView | Forgot password -> browser | Patched Android 13 |
| Samsung setup-wizard share sheet | Wizard sequence -> Galaxy Store/YouTube | Rolling patches, 2026 |
| Partition-level erase | `erase frp` / `erase config` via fastboot/BROM/EDL | Works — gated by bootloader/low-level-mode access |

From `openunlock/imei.py` + `docs/IMEI-RESEARCH.md`:

| Attack surface | Method | Current state |
|---|---|---|
| Modem NV write (Qualcomm NV 550, MTK NVRAM) | QPST/QCN, mtkclient NVRAM write | Works with low-level access |
| Partition restore (modemst/fsg/efs) | Flash backed-up partitions | Works with low-level access |
| Label vs live mismatch | — | Detectable at activation |

## Detection ideas

1. **FRP partition integrity.** Read the `frp` partition and verify it
   against the verified-boot chain: a wiped or hand-edited frp partition
   on a locked bootloader should fail attestation on next boot.
2. **Setup-wizard reachability audit.** Automated UI tests on each new
   firmware: walk every accessibility entry point and every share-sheet
   target from the setup wizard; fail the build if Settings or a
   browser becomes reachable.
3. **Patch-level attestation.** Refuse setup completion when the device
   reports a patch level older than the FRP fixes (2026-11-05 covers
   the current set); surface it in enterprise attestation.
4. **IMEI cross-checks.** Compare live IMEI vs `fsg` factory copy vs
   printed label vs carrier record; flag mismatches. Check the Luhn
   digit and the NV write counters where readable.
5. **Bootloader state as a signal.** An unlocked bootloader + a wiped
   frp partition is a high-confidence tamper signal; attestation
   services should weight it.
6. **Low-level-mode detection.** A device that has entered BROM/EDL
   mode leaves traces (fuse counters on some chips, e.g. Samsung
   Knox/Warranty bit). Surface those in attestation.

## Proposed project structure

```
prevention/
  detectors/
    frp_integrity.py     # frp partition + verified-boot checks
    wizard_audit.py      # setup-wizard reachability tests
    imei_crosscheck.py   # live vs fsg vs label comparison
    attestation.py       # patch-level + bootloader-state scoring
  fixtures/
    firmware-matrix.json # firmware versions x methods (from FRP-METHODS.md)
  tests/
    test_detectors.py    # mocked firmware states
  docs/
    THREAT-MODEL.md
    DETECTION-PLAYBOOK.md
```

## Non-goals

* No new bypasses. The prevention project consumes the OpenUnlock
  catalog as data; it does not extend it.
* No production deployment claims — this is a research prototype for a
  college project, same as OpenUnlock.

## Inputs (already built)

* `openunlock/frp.py` — METHODS catalog (executable steps + metadata).
* `docs/FRP-METHODS.md` — per-method detection/prevention notes.
* `openunlock/imei.py` — read/backup/restore/verify.
* `docs/IMEI-RESEARCH.md` — provisioning, storage, detection signals.
* `openunlock/firmware.py` — firmware inspection (patch levels, AVB).
