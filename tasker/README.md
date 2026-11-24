# OpenUnlock — Tasker + Shizuku

**File:** `tasker/OpenUnlock-NFC.prj.xml` (v0.2.2, app versionCode 4).
Import in Tasker: Menu → Data → Import Project → this file.
Re-import after any XML change.

> **Not tested on a real phone.** The XML parses, every action code
> is one found in the real Tasker 6.2.26 exports on this phone, the
> generated rish scripts pass `sh -n`, and the app side (deep links)
> is verified in the APK — but no Tasker task here has ever run on
> hardware. Run **OU Check All** first after importing; it tells you
> exactly what is missing.

## The three ways Tasker drives Shizuku

| Path | How it works | Good for | Needs |
|---|---|---|---|
| **A. Deep links** | Tasker opens `openunlock://…` and the *app* does the Shizuku work — the same action as the on-screen button | Everything the app can do | The app installed |
| **B. Tasker Run Shell + "Use Shizuku"** | Tasker runs a shell command as the ADB shell user (uid 2000) directly | Status checks whose result Tasker must read (`id`, `settings`, `pm`, `dumpsys`) | The "Use Shizuku" tick (see below) |
| **C. rish via Termux RUN_COMMAND** | Tasker asks Termux to run `rish -c '…'` — the Shizuku shell *inside* Termux | Anything needing the Termux environment: the `adb` binary, the Python CLI | rish exported + Termux + Termux:API |

Paths B and C exist because each one can do something the other
cannot: B captures output into a Tasker variable (so a task can
notify on failure), but it cannot see Termux's private binaries
(`adb`, `python`); C can run `adb` and the CLI, but RUN_COMMAND
runs in the background and cannot return output to Tasker — so the
rish tasks save their result to a file and post it with
`termux-notification`.

## Setup (do once, in order)

1. **Shizuku running.** Open the Shizuku app → "Shizuku is
   running". If not: Settings → Developer options → Wireless
   debugging ON → Shizuku → Start via Wireless Debugging (pair with
   the 6-digit code the first time). Shizuku stops on every reboot —
   open the app and tap Start again.
2. **Tasker authorized in Shizuku.** First time Tasker runs a shell
   command with Shizuku, tap Allow on the prompt (or Shizuku →
   Authorized applications → Tasker → Allow).
3. **Tick "Use Shizuku" on the Run Shell actions.** The XML encoding
   of this checkbox is not published anywhere checkable, so it is
   NOT set in this file — setting it wrong would break the import.
   After importing, open each Run Shell action in the tasks below
   and tick **Use Shizuku** (one minute per action), or turn on
   Tasker → Preferences → Misc → "Use Shizuku By Default" (Tasker
   6.6+) as belt-and-braces. Without the tick, Shizuku commands run
   as plain Tasker shell: `OU Check Shizuku` reads FAIL and says so.
   Tasks with a Shizuku Run Shell action: **OU Check Shizuku**.
4. **Termux + tools.** In Termux: `pkg install android-tools python
   termux-api` (android-tools = the `adb` binary the wireless-ADB
   flow needs; termux-api = the `termux-notification` command the
   rish tasks report through). Clone the CLI if it is not there:
   `git clone https://github.com/th3v01d2269/openunlock.git ~/openunlock`.
5. **rish (only for the OU rish tasks).** In the Shizuku app: "Use
   Shizuku in terminal apps" → export `rish` and `rish.dex`, edit
   `PKG` in the `rish` script to `com.termux`, and put it where
   Termux finds it (`$PREFIX/bin/rish` or `~/rish`). Then run
   **OU Setup Check** — it reports exactly whether rish is found.
6. **RUN_COMMAND permission.** The rish tasks and the CLI task use
   the documented `com.termux.RUN_COMMAND` service intent. If
   Termux ignores it, grant `com.termux.permission.RUN_COMMAND`
   (the Termux:Tasker plugin action in the UI is the 30-second
   alternative — same command, guaranteed correct).
7. **Run OU Check All.** It runs the Shizuku check, the wireless-ADB
   status, and the setup check, and tells you what is missing.

## Deep-link map (Path A)

| Deep link | In-app action | Shizuku? |
|---|---|---|
| `openunlock://frp` | FRP status | Yes — getprop / settings / ls |
| `openunlock://imei` | IMEI read (this phone) | Yes — dumpsys / service call |
| `openunlock://firmware` | Firmware ZIP picker | Partly — getprop if allowed |
| `openunlock://profiles` | All device profiles | No — offline asset data |
| `openunlock://info` | Device info + brand profile | Yes — getprop |
| `openunlock://wireless-adb` | Run the wireless-ADB flow | Yes — runs `adb` |
| `openunlock://adb-devices` | Print `adb devices` | Yes — runs `adb` |
| `openunlock://shizuku-status` | Print the Shizuku state | No — reports the state |
| `openunlock://pair?code=123456` | Pair + connect (code from the client's screen) | Yes — runs `adb pair` |
| `openunlock://nfc-reader` | Arm the NFC reader | No |

Try one from a shell: `am start -a android.intent.action.VIEW -d 'openunlock://frp'`

## Profiles (NFC fallback — enable only the ones you want)

Every profile fires on **any** NFC tag (event code 600, blank tag
ID) and opens the matching deep link. A client phone randomizes its
UID per tap, so no profile can match one specific client — and all
enabled profiles fire at once on any tag. The app's reader mode is
the reliable trigger; these are the fallback for when the app is not
armed. Disable the ones you do not want.

| Profile | Task | Opens |
|---|---|---|
| OU NFC - FRP status | OU NFC FRP status | `openunlock://frp` |
| OU NFC - IMEI read | OU NFC IMEI read | `openunlock://imei` |
| OU NFC - Firmware inspect | OU NFC Firmware inspect | `openunlock://firmware` |
| OU NFC - Profiles | OU NFC Profiles | `openunlock://profiles` |
| OU NFC - Device info | OU NFC Device info | `openunlock://info` |
| OU NFC - Wireless ADB | OU NFC Wireless ADB | `openunlock://wireless-adb` |

## Tasks (run by hand from Tasker's Tasks tab, or from a dispatcher)

| Task | Path | Does |
|---|---|---|
| OU Wireless ADB - start | A | Opens `openunlock://wireless-adb` — runs the flow (USB OTG → tcpip → connect, else mDNS pairing) |
| OU Wireless ADB - status | A | Opens `openunlock://adb-devices` — prints `adb devices` in the app |
| OU Pair client | A | Opens `openunlock://pair` — read the 6-digit code off the client's screen, type it in the app, tap Pair + connect |
| OU Arm NFC reader | A | Opens `openunlock://nfc-reader` — arms the reader without opening the app first |
| OU Check Shizuku | B | Run Shell (`id`) with "Use Shizuku" ticked → notifies **OK** (uid=2000) or **FAIL** with the fix (start Shizuku / tick Use Shizuku). The FAIL text is the notification — it cannot be missed. |
| OU rish - Shizuku status | C | `rish -c 'id'` in Termux → result to a notification + `Tasker/ou-rish-status.txt` |
| OU rish - adb devices | C | `rish -c 'adb devices'` in Termux → notification + `Tasker/ou-rish-adb.txt` |
| OU rish - wireless ADB flow | C | The USB-to-wireless flow as a shell script (same steps as the app's Path A): find the USB client, read its Wi-Fi IP, `adb tcpip 5555`, `adb connect`, verify → notification + `Tasker/ou-rish-wireless.txt` |
| OU Setup Check - rish + adb | C | Checks rish, adb, python, and `~/openunlock` in Termux → notification + `Tasker/ou-setup-check.txt` naming exactly what is missing and how to fix it |
| OU CLI FRP status (Termux) | C | `python -m openunlock frp status` in Termux (duplicate it and change the arguments for other CLI commands) |
| OU Check All | — | Runs OU Check Shizuku + OU Wireless ADB - status + OU Setup Check, then notifies |

## How the rish tasks work (read before editing one)

1. A Tasker Run Shell action writes the script to
   `/storage/emulated/0/Tasker/ou-rish-*.sh` with `printf '%s\n'`.
   (Single-quoted lines, so `$` survives into the file.)
2. A second Run Shell action fires it with the documented intent:
   `am startservice --user 0 -n com.termux/.app.RunCommandService
   -a com.termux.RUN_COMMAND --es com.termux.RUN_COMMAND_PATH
   /data/data/com.termux/files/usr/bin/sh --esa
   com.termux.RUN_COMMAND_ARGUMENTS "/storage/emulated/0/Tasker/ou-rish-*.sh"
   --es com.termux.RUN_COMMAND_WORKDIR /data/data/com.termux/files/home
   --ez com.termux.RUN_COMMAND_BACKGROUND true`
3. Inside Termux the script finds `rish` (`command -v rish`, then
   `~/rish`), runs `rish -c '…'`, writes the output to
   `/storage/emulated/0/Tasker/ou-rish-*.txt`, and posts it with
   `termux-notification`. If rish is not found, the notification
   says so and points at OU Setup Check.
4. A Notify action tells you where the result went.

RUN_COMMAND cannot return output to Tasker — that is a platform
limit, not a bug. The file + notification is the result channel.

## Proof rule

Every task logs one line to `/storage/emulated/0/Tasker/events.csv`
(`ou_<name>`), same as the rest of the automation. A broadcast
alone proves nothing; the log line plus the result file is the
proof a run happened.

## Honest limits

- **Nothing here has run on real hardware.** Import it, run
  **OU Check All**, and fix what it reports before trusting any
  of it. The rish path especially needs a one-time live test
  (RUN_COMMAND permission, rish location, `termux-notification`).
- **The "Use Shizuku" tick is a manual step.** The XML cannot set
  it. If `OU Check Shizuku` says FAIL, that is the first thing to
  check — the task's own notification says so.
- **Shizuku stops on reboot.** After a reboot, open the Shizuku
  app and tap Start before any of this works. Nothing here
  auto-starts it.
- **In-app live actions inspect the host phone.** FRP status, IMEI
  read, and device info in the app run on the phone the app is
  installed on. Client servicing goes through the Termux CLI once
  wireless ADB is connected.
- **IMEI restore guardrail, unchanged:** restore is
  backup-to-same-device only. No arbitrary IMEI writes, in the app,
  the CLI, or any Tasker task here.
- **NFC profiles fire on any tag.** Do not expect them to tell one
  client from another — use the app's reader mode for that.

## Editing this file

Only the action codes in the real Tasker 6.2.26 exports on this
machine are used: Run Shell `123`, Notify `523`, Perform Task
`130`, NFC Tag event `600`. No If/Else, Wait, or Read File actions
— conditionals are done inside the shell commands themselves
(`case`, `&&`/`||`), and waiting is done inside the scripts
(`sleep`). If you add an action, take its code from a real export,
not from memory. After any XML change, re-import the project.
