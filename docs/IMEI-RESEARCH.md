# IMEI Research — how it is provisioned, where it lives, how tampering is detected

This document supports the IMEI module (`openunlock/imei.py`) and the
prevention project (docs/PREVENTION-PROJECT.md). It describes the
mechanisms, not a how-to for changing an IMEI — the module enforces
restore-from-own-backup-only, and this document explains why that
boundary matters technically.

## Factory provisioning

At the factory, the IMEI is written into the modem's non-volatile (NV)
storage:

* **Qualcomm:** NV item 550 (and the related RFNV items) hold the IMEI.
  The standard factory/service path is QPST/QCN: the phone is put in
  diagnostic mode, QPST writes NV item 550, and the value is then
  protected by the modem firmware. QCN files are the backup format for
  the whole NV store.
* **MediaTek:** the IMEI lives in NVRAM (the `nvram`/`nvdata` and
  `nvcfg` partitions), written at the factory with the SN writer tool.
  mtkclient can read/write these partitions in BROM/DA mode.
* **Samsung:** the IMEI lives in EFS (`efs` partition); the service path
  is the Samsung tooling, not a public API.
* **Unisoc:** the IMEI lives in the NV partitions written by the
  ResearchDownload / SPD tooling.

There is no generic Android API for writing an IMEI. That is by design:
the value is supposed to be written once, at the factory, and then only
read.

## Where it lives on the device

| Partition | Chipset | Contents |
|---|---|---|
| `fsg` | Qualcomm | Factory modem image — includes the factory IMEI copy |
| `modemst1`, `modemst2` | Qualcomm | Modem NV storage — the live IMEI (NV item 550) |
| `nvram`, `nvdata` | MediaTek | NVRAM — the live IMEI |
| `efs` | Samsung | EFS — the live IMEI |
| `persist` | Various | Sometimes a backup copy of device identity |

When a bad flash corrupts `modemst1/modemst2` (or `nvram`), the phone
reports a null IMEI (000000000000000) or a wrong one. Restoring the
backed-up partitions restores the factory values — that is the repair
`openunlock imei restore` performs, and it only ever writes back what
came from the same device.

## How IMEI tampering is detected (the prevention angle)

1. **Cross-partition mismatch.** `fsg` (factory) vs `modemst1/2`
   (live) should agree. A phone whose live NV differs from the factory
   image is either repaired (with a record) or tampered. A checker can
   read both and compare.
2. **Label vs live.** The IMEI printed on the box / back label / carrier
   account should match the live value. Mismatch is the classic
   tamper signal — carriers check this on activation.
3. **NV write counters / modem logs.** The modem firmware tracks NV
   writes; a device with many NV writes and no service record is
   suspicious. (Vendor-specific; not readable over adb on stock
   firmware.)
4. **Luhn check.** The 15th digit is a Luhn check digit. A random
   15-digit number fails it ~90% of the time — `openunlock imei verify`
   checks this.
5. **Attestation.** On devices with hardware attestation, the modem
   identity is part of the attested device state; a changed IMEI breaks
   the attestation chain (this is why SafetyNet/Play Integrity can
   flag a tampered phone even after the value is "fixed").
6. **Carrier-side.** The network sees the IMEI on every attach. A
   blacklisted IMEI is rejected at attach regardless of what the phone
   reports locally — which is why changing the IMEI does not actually
   defeat a blacklist for long, and why it is prosecuted as fraud
   when it is done to evade one.

## Legal boundary (repeated from the module)

UK Mobile Telephones (Re-programming) Act 2002: re-programming a mobile
telephone's IMEI is an offence. US law treats IMEI alteration done to
evade a blacklist or deceive a carrier as fraud. The module's rule —
restore from the same device's own backup only, never an arbitrary value
— is what keeps this a repair/research tool.

## Sources

* Qualcomm QPST / QCN documentation (public service manuals).
* bkerler/edl README — NV / QCN references; firehose partition access.
* bkerler/mtkclient README — NVRAM read/write in BROM/DA mode.
* GSMA IMEI allocation and Luhn check-digit specification.
* Android source: `iphonesubinfo` service (frameworks/base/telephony).
