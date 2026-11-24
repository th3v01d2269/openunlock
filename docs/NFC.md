# OpenUnlock — NFC tap-to-run

**Version 0.2.3.** The client phone is the tag. No pre-programmed NFC
tags, nothing to stick on a phone, nothing to write.

> **Not tested on a real phone.** There is no Android device in the
> build environment, so everything here is verified structurally only
> (the APK builds, the manifest declares the right filters, the Tasker
> XML parses and its action codes match a real Tasker 6.2.26 export).
> The first real test is: install the APK on the host phone, arm the
> reader, tap a client phone, and watch what happens.

## The idea

OpenUnlock runs on **your** phone (the host). The host phone is the
NFC **reader**. The **client** phone — the one that needs FRP checked,
IMEI read, or servicing — is the **tag**: tap it against the host
phone and its NFC chip presents itself. That detection is the trigger.

* Detection fires on **any** tag. The tag UID is shown only as info
  and is never used as identity: modern Android randomizes the UID
  every time a phone presents as a tag, so a UID can never reliably
  identify one client.
* Nothing is programmed. There is no "write a tag" step in this
  version — the earlier writer idea was dropped on purpose, because
  the client itself is the tag.

## Primary path: the app's reader mode

1. On the host phone, open OpenUnlock. Turn NFC on (Settings).
2. Tap **Start NFC reader**. The status line reads "NFC reader:
   ARMED". (The reader turns off when the app leaves the foreground —
   reader mode only owns the NFC controller while the app is in front.)
3. Tap the client phone against the host phone, back to back.
4. On detection the app prints the tag UID (info only) and tech list,
   runs the default action — **FRP status** first — and then starts
   the wireless-ADB flow below.
5. The default action is changeable: tap **NFC default: …** to cycle
   FRP status → IMEI read → Firmware inspect → All profiles →
   Device info + profile → back to FRP status.

### What the tap can and cannot do

The tap is only a **trigger**. NFC alone cannot change any setting on
the client — it cannot turn on wireless debugging, cannot turn on
Wi-Fi, cannot unlock anything. What the tap does is start the
wireless-ADB flow, which uses real channels (USB, then Wi-Fi) to
connect to the client. That is the whole honest scope of "automatic".

## Auto-enable wireless ADB (runs after every tap)

After detection, the app tries to make the client reachable over
Wi-Fi, so the USB cable can be unplugged. It needs an `adb` binary on
the **host** phone — Termux android-tools:

```bash
# in Termux on the host phone
pkg install android-tools
```

The app looks for `/data/data/com.termux/files/usr/bin/adb` and runs
it through the Shizuku shell. (If a bundled adb binary is ever
needed instead — e.g. Termux is not installed — the app would have to
ship one; it does not today. Termux is the requirement.)

### Path A — USB OTG (the reliable one)

1. Plug the client into the host phone by USB OTG (USB-C to USB-C
   cable, or USB-C OTG adapter + cable).
2. On tap, the app runs `adb devices`. A USB client shows up with a
   plain serial (no `:` in it).
3. It reads the client's Wi-Fi IP (`ip addr show wlan0`, falling back
   to the `dhcp.wlan0.ipaddress` property).
4. It runs `adb tcpip 5555`, then `adb connect <client-ip>:5555`,
   then confirms the client in `adb devices`.
5. Success means: **unplug the USB cable** — the client stays
   reachable over Wi-Fi. In Termux you can now run the CLI against
   it, e.g. `python -m openunlock info`, `frp status`, `imei`.

If the client shows an **"Allow USB debugging?"** prompt, tap Allow
on the client and tap **Enable wireless ADB (auto)** again. If no
Wi-Fi IP can be read, the client is probably not on Wi-Fi — join Wi-Fi
first, then tap again.

### Path B — wireless debugging already on (mDNS)

If no USB client is found, the app scans the current Wi-Fi for 10
seconds for wireless debugging advertisements
(`_adb-tls-pair._tcp` and `_adb-tls-connect._tcp`).

* **Pairing service found:** the app prints its address and tells
  you to open **Wireless debugging → Pair device with pairing code**
  on the client, read the 6-digit code off the client's screen, type
  it into the **Pairing code** box, and tap **Pair + connect**. The
  app then runs `adb pair <host>:<pair-port> <code>` and
  `adb connect <host>:<connect-port>`. The code changes every time the
  pairing screen is opened — read it fresh.
* **Only a connect service found** (the client was paired before):
  the app tries a straight `adb connect` on its own.
* **Nothing found:** wireless debugging is off on the client, or the
  phones are on different networks. Turn it on (Settings →
  Developer options → Wireless debugging) and tap again — or use
  the USB path, which needs no setting on the client beyond the
  Allow prompt.

You can also run the flow without a tap: **Enable wireless ADB
(auto)** does the same thing on demand.

### Hard limits — say them plainly

* **NFC cannot enable wireless ADB by itself.** The tap starts the
  flow; the flow needs USB OTG first, or wireless debugging already
  on and advertising. There is no way around that with NFC.
* **A fully FRP-locked device with neither USB nor wireless
  debugging on cannot have wireless ADB auto-enabled.** The USB OTG
  flow is the fallback: plug it in, tap Allow if prompted, and the
  tap takes it from there. If the locked device will not present over
  USB either (no Allow prompt appears, or the setup wizard blocks
  it), wireless ADB is not reachable from this app — use the
  desktop CLI / Termux version with a cable, or the official FRP
  recovery path in the app (`FRP official recovery path`).
* **FRP-locked devices vary.** Some present their NFC chip as soon
  as the screen is on; some only after the setup wizard reaches a
  certain step; some have NFC off by default. What to try, in order:
  screen on → NFC on in Settings if you can reach it → tap again →
  plug in USB OTG and tap again. If the host shows no detection at
  all, the client is not presenting — the app cannot force it.
* **Same Wi-Fi matters.** The mDNS path only works when both phones
  are on the same network. A phone hotspot works: host the hotspot
  on one phone, join it from the other.
* **The in-app live actions inspect the host phone.** FRP status,
  IMEI read, and device info in the app run on the phone the app is
  installed on. Once wireless ADB is connected, client servicing
  goes through the Termux CLI (`python -m openunlock …`), which
  talks to the connected client. That split is by design in this
  version — the app's on-screen actions were not rerouted through
  the client connection.
* **IMEI restore guardrail, unchanged:** restore is
  backup-to-same-device only. No arbitrary IMEI writes, in the app
  or the CLI.

## Deep links — `openunlock://`

The app answers these URIs, from Tasker, Termux, or a shell:

| URI | Does | Shizuku? |
|---|---|---|
| `openunlock://frp` | FRP status | Yes |
| `openunlock://imei` | IMEI read (this phone) | Yes |
| `openunlock://firmware` | Opens the firmware ZIP picker | Partly |
| `openunlock://profiles` | Lists all device profiles | No (offline) |
| `openunlock://info` | Device info + brand profile | Yes |
| `openunlock://wireless-adb` | Run the wireless-ADB flow | Yes (runs `adb`) |
| `openunlock://adb-devices` | Print `adb devices` | Yes (runs `adb`) |
| `openunlock://shizuku-status` | Print the Shizuku state | No (reports it) |
| `openunlock://pair?code=123456` | Pair + connect (code from the client's screen) | Yes (runs `adb pair`) |
| `openunlock://nfc-reader` | Arm the NFC reader | No |

Try it from a shell on the host phone:

```bash
am start -a android.intent.action.VIEW -d 'openunlock://frp'
```

## Tasker project — Shizuku in three paths (v0.2.2)

File: `tasker/OpenUnlock-NFC.prj.xml`. Full write-up:
[`tasker/README.md`](../tasker/README.md). Import in Tasker: Menu →
Data → Import Project → the file. (Re-import after any XML change.)

Tasker drives Shizuku three ways, and the project now uses all
three:

* **A. Deep links** — a task opens an `openunlock://` URI and the
  app does the Shizuku work (same action as the on-screen button).
  Tasks: OU Wireless ADB - start/status, OU Pair client, OU Arm NFC
  reader, plus the six NFC profiles (one per action, including the
  new OU NFC - Wireless ADB).
* **B. Tasker Run Shell with "Use Shizuku" ticked** — Tasker runs a
  shell command as the ADB shell user directly. Task **OU Check
  Shizuku** runs `id` and notifies OK (uid=2000) or FAIL with the
  fix. The tick is a manual step after import — the XML cannot set
  it (its encoding is not published anywhere checkable).
* **C. rish via Termux RUN_COMMAND** — for commands that need the
  Termux environment (`adb`, the Python CLI). Tasks: OU rish -
  Shizuku status, OU rish - adb devices, OU rish - wireless ADB
  flow (the USB-to-wireless steps as a shell script), and **OU Setup
  Check - rish + adb**, which reports exactly what is missing
  (rish / adb / python / `~/openunlock`). RUN_COMMAND cannot return
  output to Tasker, so each rish task saves its result to
  `Tasker/ou-rish-*.txt` and posts it with `termux-notification`.
  **OU Check All** runs the Shizuku check, the wireless-ADB status,
  and the setup check in one go.

There is also the earlier profile-less task, **OU CLI FRP status
(Termux)**, which asks Termux to run `python -m openunlock frp
status` via the documented `com.termux.RUN_COMMAND` service intent.
Run it by hand from Tasker, or from the existing dispatcher by name.
Duplicate it and change the arguments for other CLI commands.

Each task logs one line to `/storage/emulated/0/Tasker/events.csv`
(`ou_<name>`), so a run can be proven from the log — the same
proof rule as the rest of the automation: a broadcast alone proves
nothing.

**Why the NFC profiles are fallback, not primary:** the profiles
fire on *any* NFC tag (blank tag ID, event code 600). A client
phone randomizes its UID per tap, so an NFC profile can never
reliably match one specific client — and when the app is open in
reader mode, reader mode grabs the tag first anyway, so the Tasker
profile only fires when the app is not armed. The app's reader
mode is the reliable trigger; Tasker is the backup for when the
app is not in front.

**Tasker XML notes (for the next person who edits it):** only the
action codes in the real Tasker 6.2.26 exports on this machine are
used: Run Shell `123`, Notify `523`, Perform Task `130`, NFC Tag
event `600`. No If/Else, Wait, or Read File actions — conditionals
are done inside the shell commands themselves. The Run Shell
actions use `am start …` (no root, no Shizuku needed for that). The
`RUN_COMMAND` tasks need the `com.termux.permission.RUN_COMMAND`
permission — test it once; if Termux ignores the intent, build the
same action in the Tasker UI with the Termux:Tasker plugin instead
(30 seconds, guaranteed correct).

## Requirements

| Thing | Why | Notes |
|---|---|---|
| Host phone with NFC | Reader mode | The app checks and says so if absent |
| NFC on, both phones | Detection | Client screen on helps |
| Shizuku (host) | Live shell features + running `adb` | Offline features work without it |
| Termux + `android-tools` (host) | The `adb` binary for the wireless-ADB flow | `pkg install android-tools` |
| Termux:Tasker plugin (optional) | CLI from Tasker without the intent workaround | Only for the CLI task |
| Same Wi-Fi (mDNS path) | Wireless-debugging discovery | Or use the USB path |
| USB OTG cable/adapter | Path A | The reliable fallback |

## What did not change

The NFC work is **in addition to** the original app, not a
replacement for it. Every original feature is intact and reachable
from the main screen exactly as before: this-phone info, device info
+ brand profile, FRP status + 5-method catalog + run, IMEI read +
Luhn check, all device profiles, firmware ZIP inspection via the
file picker. The app still works fully with no NFC interaction at
all — NFC is one extra section at the bottom of the same screen.
