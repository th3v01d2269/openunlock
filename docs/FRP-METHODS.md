# FRP Method Catalog — what works, what is patched, and how each is prevented

This document is the bridge to the prevention project
(docs/PREVENTION-PROJECT.md). Every method here is publicly documented;
the point of cataloguing them is to understand the attack surface so the
next project can close it. Use these only on a phone you own.

Honest headline, November 2026: **there is no publicly documented
working FRP bypass for the newest firmware.** Google and Samsung have
closed the accessibility/share-sheet entry points build by build. The
methods below work on older firmware and on specific models/patch levels
— and the "patched" labels are as important as the methods themselves.

## Method 1 — TalkBack -> Help & Feedback -> YouTube -> Settings

* Applies to: Android 5.0–9.0; some Samsung devices on Android 14/15.
* Patched: Android 10+ for most vendors; Samsung closed the share-sheet
  entry points in successive 2024–2026 updates.
* How it works: enable TalkBack from the setup wizard, open its Help &
  Feedback page, follow a link into YouTube, reach Settings from there,
  add a new Google account.
* How it is detected / prevented:
  * Setup wizard runs in a restricted profile — accessibility services
    launched from setup can no longer start arbitrary activities; the
    Help & Feedback webview is sandboxed with no navigation to Settings.
  * Prevention (next project): audit every activity reachable from the
    setup wizard and assert none can launch `android.settings.SETTINGS`
    or a browser; add a test that walks the accessibility entry points
    on each new firmware and fails the build if a path opens Settings.

## Method 2 — Emergency dialer -> notification shade -> Settings

* Applies to: Android 8.0 and earlier.
* Patched: Android 9 (2018).
* How it works: from the verification screen open the emergency dialer,
  fill it with a long string, pull down the notification shade, tap the
  Settings gear.
* How it is detected / prevented:
  * The emergency dialer no longer exposes the notification shade, and
    the shade itself is locked until setup completes.
  * Prevention: the emergency dialer is a separate, minimal activity
    with no navigation targets; verify by static analysis that it
    declares no intent filters beyond CALL_EMERGENCY.

## Method 3 — Maps / YouTube intent -> share -> Settings

* Applies to: Android 10–12 (varies by vendor skin).
* Patched: Android 13+; Samsung closed most share-sheet entries in
  One UI 5/6.
* How it works: launch Maps or YouTube by intent from the setup flow,
  use the share sheet to reach a browser or Settings.
* How it is detected / prevented:
  * Share targets are now filtered during setup — system apps that can
    open Settings are not offered as share targets from the wizard.
  * Prevention: enumerate share targets available during setup on each
    firmware and assert the list contains no Settings/browser entry.

## Method 4 — Verification screen -> Forgot password -> browser

* Applies to: Android 11–12.
* Patched: Android 13 — the forgot-password flow opens a restricted
  WebView instead of a general browser.
* How it works: choose "Try another way", enter an address, tap "Forgot
  password" — this used to open a full browser.
* How it is detected / prevented:
  * The recovery flow is now served inside a Custom Tab with no
    navigation bar and no access to Settings.
  * Prevention: assert the recovery WebView cannot navigate outside
    accounts.google.com (allow-list check in the WebViewClient).

## Method 5 — Samsung setup-wizard share-sheet loophole (Android 15)

* Applies to: Samsung Galaxy A/M-series, Android 15, patches up to
  early 2026.
* Patched: rolling — S-series with the latest 2026 patches need other
  methods; entry points close build by build.
* How it works: navigate the Samsung setup wizard in a specific
  sequence to reach accessibility settings, then use the share sheet to
  open Galaxy Store / YouTube and add an account.
* How it is detected / prevented:
  * Samsung's own patches close each share-sheet entry point as it is
    found; Knox attestation can flag a device whose setup was bypassed.
  * Prevention: the wizard's share sheet should only offer targets
    that cannot escape the wizard; automated UI tests on each new One UI
    build should attempt every share-sheet path and fail if Settings
    becomes reachable.

## Partition-level erase (not a "bypass" — a reset of the lock record)

* `fastboot erase frp` / `erase config`, mtkclient `e frp`, edl firehose
  erase. Requires an unlocked bootloader path (fastboot) or a low-level
  mode (BROM/EDL). This is what `openunlock frp erase` does.
* How it is detected / prevented:
  * Verified Boot (AVB) + a locked bootloader refuse unsigned partition
    writes entirely — erase only works once the bootloader is unlocked
    or the device is in a low-level mode, both of which are themselves
    gated (OEM unlocking toggle, auth).
  * Prevention: keep the bootloader locked, keep OEM unlocking off by
    default, and make the frp partition part of the verified-boot chain
    so a tampered frp partition fails attestation on next boot.

## Official path (always first)

1. Sign in with the previously synced Google account, or recover it at
   https://accounts.google.com/signin/recovery.
2. Proof of purchase + manufacturer service centre / carrier.
3. Only then, on your own phone, a partition-level erase.

## Sources

* EaseUS / Dr.Fone Samsung A16 FRP guides (Oct 2026) — TalkBack and
  emergency-dialer methods on Android 14/15, with the official-path
  recommendation first.
* Temaah, "Samsung Android 15 FRP Bypass Without a PC" (2026) —
  setup-wizard loophole, patch status by series.
* sod-calculator.com Samsung FRP guide — TalkBack (Android 9 and
  earlier), emergency-call keyboard trick (Android 8 and earlier),
  setup-wizard glitch (Android 10), add-account workaround (11/12).
* Google, Android Factory Reset Protection documentation (source.android.com).
