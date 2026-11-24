# OpenUnlock for Android

A real Android app version of OpenUnlock (v0.2.3), built Nov 24, 2026.
**APK: `android/app-debug.apk`** (669 KB, debug-signed, `com.openunlock`).

> **Not tested on a real phone.** There is no Android device in the build
> environment, so the APK is verified structurally only (aapt badging,
> apksigner v2+v3, dex class listing). Install it on a phone and try the
> offline features first — they need no Shizuku and no other phone.

## What it is

A native Kotlin app (no embedded Python — see "Why native" below) with one
screen:

| Feature | Needs | Status |
|---|---|---|
| This phone — device info (`getprop`) | Shizuku | Live via Shizuku shell |
| Device info + brand profile | Shizuku | Live + offline profile data |
| FRP status (partition, props, setup state) | Shizuku | Live via Shizuku shell |
| FRP method catalog (5 methods, patch status) | — | Offline, from the Python catalog |
| FRP official recovery path | — | Offline |
| Run an FRP method (shell steps execute, manual steps shown) | Shizuku | Live via Shizuku shell |
| IMEI read (dumpsys / service-call parcel parse) | Shizuku | Live via Shizuku shell |
| IMEI Luhn check (type any 15-digit IMEI) | — | Offline |
| All device profiles / show one brand | — | Offline, from profiles.json |
| Firmware ZIP inspection (pick a ZIP) | — | Offline, java.util.zip port |
| Clear output | — | — |

NOT in the app (they need a real `adb`/`fastboot` binary — use the
desktop CLI or the Termux version): bootloader unlock/relock, flashing,
partition backup/restore, fastboot FRP erase. The app never fakes a live
result: when Shizuku is missing it says so on screen.

## NFC tap-to-run (v0.2.1, additive — nothing above changed)

Full write-up: [docs/NFC.md](NFC.md). Short version: the host phone
is the NFC **reader**; tap a client phone against it and that
detection triggers the default action (FRP status first, changeable
with the "NFC default" button) and then the wireless-ADB auto-enable
flow (USB OTG → `adb tcpip 5555` → `adb connect`, or mDNS wireless
debugging pairing). Deep links `openunlock://frp|imei|firmware|
profiles|info` work from Tasker, Termux, or `am start`. A Tasker
fallback project is in `tasker/OpenUnlock-NFC.prj.xml`. NFC is one
extra section at the bottom of the same screen — every feature in the
table above works exactly as before with no NFC interaction at all.

**v0.2.2 — Tasker + Shizuku, also additive.** Five new deep links
(`wireless-adb`, `adb-devices`, `shizuku-status`, `pair?code=…`,
`nfc-reader`) so Tasker can drive every Shizuku action in the app,
a Shizuku status-check task that notifies OK/FAIL, rish tasks that
run `rish -c '…'` through Termux (Shizuku status, `adb devices`,
the wireless-ADB flow, and a setup check that reports exactly what
is missing), and a new NFC profile for wireless ADB. Full write-up:
[`tasker/README.md`](../tasker/README.md). Nothing original changed
— the 18-point feature check passes.

**v0.2.3 — diagnostic + hardened release, also additive.** v0.2.2
installed on the user's moto g 2025 (Android 15) but would not open
at all, with no visible error. Static review cleared the manifest,
all view IDs, the Shizuku/NFC null-checks and the theme, so the
failure is either at Activity construction (field initializers run
before `onCreate`, where nothing could catch them) or inside a
startup helper. Changes: the Shizuku listener is now created inside
`onCreate` instead of as a field initializer; the whole `onCreate`
body is wrapped in try/catch and shows a startup failure on screen
(with the stack trace) instead of silently closing, and saves it to
`Android/data/com.openunlock/files/openunlock-diagnostics.txt`;
`updateShizukuStatus()`, `updateNfcStatus()`, `handleIntent()` and
the listener registration each have their own try/catch; the main
screen has a Diagnostics section (version, Shizuku, NFC, last startup
error, diagnostics file path) plus a "Save diagnostics to file"
button.

## App won't open? (troubleshooting)

1. **Uninstall fully, then install fresh.** Settings → Apps →
   OpenUnlock → Uninstall. Then install the new APK. This clears
   any stale-install conflict from the 0.2.0 → 0.2.1 → 0.2.2 update
   chain (same package, debug-signed) and any corrupted app data.
2. **Read what the app says.** v0.2.3 shows a startup failure on
   screen instead of closing: screenshot it (or copy the text) and
   send it back — it names the exact exception. The same text is in
   `Android/data/com.openunlock/files/openunlock-diagnostics.txt`
   (Files app → Internal storage → Android → data → com.openunlock
   → files). The Diagnostics section at the bottom of the main
   screen also shows the last startup error, or "none".
3. **If even v0.2.3 shows nothing** (taps the icon, nothing at all,
   no screen, no crash dialog), the failure is before the Activity
   runs at all — most likely a stale install state or a bad install.
   Do step 1, then check free storage and reinstall.

## Install

```bash
adb install android/app-debug.apk
# or: copy the APK to the phone and tap it (allow unknown sources for
# the file manager / browser you use)
```

## Shizuku setup (for the live features)

1. Install the **Shizuku** app (GitHub: RikkaApps/Shizuku) on the phone.
2. In Shizuku, start the service via **wireless debugging** (Android 11+):
   Settings → Developer options → Wireless debugging → pair with the
   code Shizuku shows. (No root needed; no PC needed after pairing.)
3. Open OpenUnlock, tap **Request Shizuku permission**, allow it in
   Shizuku. The status line at the top of the app shows whether Shizuku
   is running and whether permission is granted.
4. Without Shizuku, every offline row in the table above still works.

## Why native (no embedded Python)

The original plan was Chaquopy (Gradle plugin embedding CPython, so the
`openunlock/` package would run inside the app). That plan failed on the
build environment, not on the design:

* **Gradle is broken in this sandbox.** Every Gradle invocation — even
  `gradle tasks` on an empty project, offline, with no plugins — fails
  with `Could not receive a message from the daemon` (root cause in the
  client log: `IllegalArgumentException: Unexpected type tag 109` while
  reading the daemon's reply). Chaquopy is a Gradle plugin, so it cannot
  build here either.
* The APK was therefore built with the SDK tools directly
  (`android/manual/build-manual.sh`: kotlinc + aapt2 + d8 + zipalign +
  apksigner) and the Python logic was **ported to Kotlin**:
  `Profiles.kt` (from profiles.py), `FrpCatalog.kt` (from frp.py
  METHODS), `Imei.kt` (Luhn + dumpsys/service-call parsers),
  `Firmware.kt` (ZIP inspection). The data files are generated from the
  Python sources, not hand-copied: `assets/profiles.json` is a copy of
  `openunlock/profiles.json`; `assets/frp-catalog.json` is produced by
  `android/manual/generate-frp-catalog.py`.
* **Parity gap, stated honestly:** the APK does not run the Python core;
  it runs Kotlin ports of the same logic and data. Anything the ports
  compute (Luhn, catalog text, firmware report) is identical to the CLI;
  the FRP/IMEI shell commands are the same commands the CLI runs over
  adb, executed here through the Shizuku shell. The one behavioral
  difference: the CLI's `imei backup`/`restore` (partition images) and
  `frp erase` (fastboot/MTK/EDL) are absent — they need binaries the app
  cannot ship. IMEI restore is backup-to-same-device only in the CLI and
  stays that way; nothing in the app writes an IMEI value.
* Shizuku API is pinned to **12.1.0** on purpose: 13.x removed
  `Shizuku.newProcess`, which is how the app runs shell commands.

## How it was built

SDK: `~/workspace/android-sdk` (cmdline-tools 12.0, platform-tools
37.0.3, platforms android-34, build-tools 34.0.0 — installed by direct
curl download because sdkmanager's Java HTTP client cannot tunnel
through the egress proxy). Kotlin compiler 2.0.0
(`~/workspace/kotlinc`). Java 17. `build-manual.sh` does:
aapt2 compile → aapt2 link → kotlinc → d8 → zip/add dex+assets →
zipalign → apksigner (fresh debug keystore in `android/manual/`).

The Gradle project in `android/` (AGP 8.5.2, Kotlin 2.0.0, minSdk 26,
targetSdk 34) is kept as the reference build for a normal machine —
it should build there; it cannot build in this sandbox for the Gradle
reason above.

## Verification done here

* `aapt dump badging`: package `com.openunlock`, versionCode 5,
  versionName 0.2.3, minSdk 26, targetSdk 34, permissions
  `moe.shizuku.manager.permission.API_V23` + `android.permission.NFC`,
  launchable `com.openunlock.MainActivity`, intent filters for
  `openunlock://` (VIEW + NDEF_DISCOVERED), singleTop.
* `apksigner verify --verbose`: v2 + v3 schemes true, 1 signer.
* `dexdump`: all six app classes present
  (MainActivity, ShizukuShell, Profiles, FrpCatalog, Imei, Firmware)
  plus Kotlin stdlib and the Shizuku API; MainActivity implements
  `NfcAdapter.ReaderCallback` (`onTagDiscovered`, `wirelessAdbFlow`,
  `pairAndConnect`, `findAdbBinary` all present), NsdManager refs present.
* APK contents: classes.dex, assets/profiles.json,
  assets/frp-catalog.json, resources, signed manifest.
* Original-features check (Nov 24): all six areas verified present
  and reachable from the main screen — this-phone info, device info +
  brand profile, FRP status + catalog + run, IMEI read + Luhn check,
  all device profiles, firmware ZIP inspection. The NFC work is
  additive only; the only removed lines in the diff are version
  strings and the class-declaration line.
* `tasker/OpenUnlock-NFC.prj.xml` parses as valid XML; its action
  codes (Run Shell 123, Notify 523) match a real Tasker 6.2.26 export.
* `python3 -m unittest discover` on the desktop CLI still passes
  (59 tests) — the ports were checked against the same logic.

Known-benign d8 warnings (build still succeeds, dex complete):
R8 8.2.2 predates Kotlin 2.0 metadata, so it warns it cannot parse the
Kotlin metadata on the six app classes (runtime behavior unaffected —
no reflection is used); and two Shizuku service-side AIDL stub types
are missing, which only matters for the `bindUserService` path this app
does not use.

## Rebuilding

```bash
# Regenerate the FRP catalog after changing openunlock/frp.py:
python3 android/manual/generate-frp-catalog.py
# (profiles.json is a plain copy of openunlock/profiles.json)
# Rebuild the APK:
bash android/manual/build-manual.sh   # -> android/app-debug.apk
```

## Still open

* **Install + run on a real phone** (his moto g, which already runs
  Shizuku): offline features first, then Shizuku live features.
  Nothing here has been run on hardware.
* The Termux version and the all-in-one portable Windows version are
  separate deliverables (not this APK).
* A release-signed build (release keystore, not the debug keystore)
  is needed before distributing the APK beyond his own phone.
