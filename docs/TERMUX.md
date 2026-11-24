# OpenUnlock on Termux (Android)

Run the whole toolkit from a phone — no PC, no install of Python from
anywhere else. Termux gives you a real Linux shell, `adb` and `fastboot`
from the `android-tools` package, and the OpenUnlock CLI on top.

## Install (in Termux on the phone)

```bash
pkg update && pkg install -y python android-tools git
git clone https://github.com/th3v01d2269/openunlock.git ~/openunlock
cd ~/openunlock
pip install -e . --break-system-packages
openunlock --help
```

Or one command once the repo is on the phone:

```bash
bash ~/openunlock/termux/install-termux.sh
```

No other dependencies. Standard library only (pyusb optional).

## Connecting a target phone

OpenUnlock talks to a phone through `adb` / `fastboot`, same as on a PC.
Pick whichever fits:

1. **Wireless debugging (easiest, Android 11+).** On the target phone:
   Settings > Developer options > Wireless debugging ON. Pair once:
   `adb pair <target-ip>:<pair-port>` (enter the 6-digit code), then
   `adb connect <target-ip>:<connect-port>`. Now `openunlock devices`
   sees it. Works phone-to-phone over the same Wi-Fi.
2. **Same phone (this phone as the target).** Enable wireless debugging
   on the phone itself, then `adb pair 127.0.0.1:<pair-port>` and
   `adb connect 127.0.0.1:<connect-port>`. The phone drives itself.
   (Some features need the target unlocked/rooted — see below.)
3. **USB OTG.** Plug the target phone in with a USB-OTG adapter and a
   cable. Termux needs USB permission for the device (Android asks when
   you plug it in). Then `adb devices` should list it. Fastboot mode
   works the same way once the target is in the bootloader.

## What works in Termux

| Feature | Needs |
|---|---|
| `devices`, `info`, `profiles` | adb connection to the target |
| `imei read / verify` | adb |
| `imei backup` (modemst/fsg partitions) | adb + root on the target |
| `frp status / methods / test` | adb |
| `frp erase` | fastboot, or mtkclient/edl (below) |
| `firmware inspect`, `apple detect` | a firmware ZIP / lsusb |
| `unlock / relock / flash / reset` | fastboot + confirm flag |
| `lockscreen remove` | root on the target |

## What does NOT work in Termux

- **The GUI** (`openunlock gui`) — Tkinter has no display in Termux.
  CLI only.
- **MTK / Qualcomm live ops** out of the box — the protocol framing is
  in the package, but live sessions delegate to `mtkclient` / `edl`.
  Both are pip-installable in Termux (`pip install mtkclient edl`),
  then `openunlock mtk detect` / `openunlock edl detect` can use them.

## Notes

- Every destructive command needs `--confirm` and prints what it is
  about to do first. Same guardrails as the desktop version: IMEI
  restore is backup-to-same-device only, FRP methods are publicly
  documented and labelled by firmware applicability, no vendor files.
- Keep the tool and the target phone's data in mind: unlocking wipes
  the target phone. Back up first.
