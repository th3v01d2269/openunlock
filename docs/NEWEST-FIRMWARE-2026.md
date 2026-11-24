# Newest Firmware — verified state, November 2026

Reference for what "works with the newest firmware" means in this
project. All facts verified by web search on 2026-11-24; sources listed
at the end.

## Android versions

* **Android 17 is current.** Launched June 16, 2026; QPR1 Sept 15, 2026;
  **QPR2 rolled out Nov 10, 2026** (a month early) to 23 Pixel devices
  (Pixel 6a through Pixel 11, including Fold and Tablet). Pixel 6 and
  6 Pro are end-of-life — last patch October 2026.
* **November 2026 security bulletin: 216 CVEs, 23 Critical**, across
  Android 14, 15, 16, 16 QPR2 and 17. Two patch levels: **2026-11-01**
  (119 fixes: Framework/System/runtime) and **2026-11-05** (97 fixes:
  kernel + MediaTek/Qualcomm/Arm/Imagination/Unisoc). A phone showing
  2026-11-01 is only half-patched; 2026-11-05 is the full fix.
* Headline bugs: CVE-2026-58868 (Framework RCE, no user interaction),
  CVE-2026-58876 and CVE-2026-58936 (System RCE), CVE-2026-58882
  ("SMS of Death", WAP Push DoS). None reported exploited in the wild.
* **Android 16 / 16 QPR2** remains the version on most non-Pixel
  flagships shipping in late 2026 (Samsung One UI 8, Xiaomi HyperOS 4).

## Platform facts that shape servicing

* **Dynamic partitions / super.img** are universal on Android 10+
  flagships; `fastbootd` (userspace fastboot) handles super-partition
  flashing, not the bootloader. `fastboot flash` on a dynamic device
  goes through fastbootd.
* **AVB / vbmeta**: verified boot is mandatory; flashing boot without a
  matching vbmeta (or an empty vbmeta with verification disabled) fails
  boot on a locked bootloader.
* **Anti-rollback**: rollback indexes in vbmeta mean downgrading to an
  older security patch can brick. `firmware inspect` warns on this.
* **Samsung One UI 8.0 removed the OEM unlocking toggle entirely** —
  assume One UI 8+ Galaxy phones cannot be bootloader-unlocked.
* **Xiaomi HyperOS**: Community-app permission + ~72h wait (168h on
  MIUI); China-region phones effectively closed; 1 phone/30 days,
  4/year per account.
* **Huawei**: bootloader codes discontinued 2018 — no legitimate path.

## Newest chipsets (late 2026)

| Chipset | Process | Notable | Servicing note |
|---|---|---|---|
| Snapdragon 8 Elite Gen 5 | 3nm N3P, 2+6 up to 4.6 GHz, Adreno 840 | Fastest Android SoC; Galaxy S26, Xiaomi 17 | EDL 9008 + signed firehose; Sahara V3 (cmd 0x0A) |
| Dimensity 9500 | 3nm N3P, 1+3+4 up to 4.21 GHz, Mali-G1 Ultra | Vivo X300 Pro, Oppo Find X9 | BROM patched; V6 protocol, valid DA + auth required |
| Exynos 2600 | 2nm GAA, 1+3+6 up to 3.8 GHz, Xclipse 960 | Galaxy S26 (non-US) | Samsung Download mode; One UI 8 unlock removed |
| Tensor G5 | 3nm, Pixel 10 family, TSMC | On-device Gemini Nano | Standard Pixel fastboot flow |
| Apple A19 Pro | 3nm, 6-core up to 4.26 GHz | iPhone 17 Pro | See Apple note below |
| Unisoc T820 / T770 | mid-range 5G | Transsion, Nokia/HMD, Samsung A-series | SPD download mode, FDL1/FDL2, identifier-token unlock |

## Apple

* **checkm8 (CVE-2019-8900) covers A5–A11 only.** A12/A13 were immune.
* **usbliter8 (Paradigm Shift, disclosed June 2026)** is a checkm8-style
  BootROM exploit for **A12/A13** (Synopsys DesignWare USB controller
  flaw in DFU mode). Unpatchable, runs unsigned code, loads custom
  iBoot — the basis for the A12/A13 ramdisk work UnlockTool sells.
  It does NOT break the Secure Enclave.
* **Dopamine 3.0 (Aug 2026)** is the first public jailbreak for iOS
  26.0/26.0.1 on A12/A13. A14+ has no public BootROM exploit.

## Open-source tooling coverage (Nov 2026)

* **mtkclient** (bkerler): BROM/preloader, read/write, `da seccfg
  unlock`. MT678x/MT689x/MT688x/MT698x need V6 + valid DA. DAA/SLA/
  Remote-Auth devices: no public solution. Newer chips (Dimensity
  9000+, MT6895/MT6983): patched BootROMs.
* **edl** (bkerler): Sahara V3 support fixed (cmd 0x0A chip-ID read);
  firehose via user-supplied programmer; USB PID 0x9008.
* **unisoc-unlock** (PyPI): identifier-token bootloader unlock for
  Unisoc/SPD.
* **checkra1n / palera1n / ipwndfu / gaster**: checkm8 tooling (A5–A11).

## Sources

* Google Android Security Bulletin, November 2026 (via TechRepublic,
  whysogeek, thetechhacker, ipv6.press).
* Android Police / TechRepublic / Droid-Life, Android 17 QPR2 rollout
  (Nov 10, 2026).
* macmyths / geekchamp / mobilityarena / androlib, 2026 chipset
  rankings (Snapdragon 8 Elite Gen 5, Dimensity 9500, Exynos 2600,
  Tensor G5, A19 Pro).
* bkerler/mtkclient README; bkerler/edl README; flashguidehub guides.
* The Apple Wiki, checkm8; The Register, "usbliter8" (June 19, 2026);
  techengage.com iOS jailbreak history (Dopamine 3.0, Aug 2026).
* droidrooter.com 2026 bootloader guide (checked 2026-11-05);
  customdroid.info; awesome-android-root bootloader guide.
* unlocktool.org (UnlockTool v2026.11.23.0 feature list).
