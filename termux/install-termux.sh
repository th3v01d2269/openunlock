#!/data/data/com.termux/files/usr/bin/bash
# OpenUnlock — Termux installer (moto g / any Android phone with Termux)
# Run inside Termux:  bash ~/openunlock/termux/install-termux.sh
# or straight from the repo:  bash termux/install-termux.sh
set -e
echo "== OpenUnlock Termux install =="
pkg update -y
pkg install -y python android-tools git
# android-tools = adb + fastboot. python = CPython (stdlib only, no other deps).
if [ ! -d "$HOME/openunlock" ]; then
  git clone https://github.com/th3v01d2269/openunlock.git "$HOME/openunlock"
else
  echo "openunlock already at \$HOME/openunlock — pulling latest."
  git -C "$HOME/openunlock" pull --ff-only || true
fi
cd "$HOME/openunlock"
pip install -e . --break-system-packages
echo ""
echo "== Verify =="
openunlock --help | head -5
echo ""
adb version
fastboot --version 2>/dev/null | head -1 || true
echo ""
echo "Installed. Try:  openunlock devices"
echo "No GUI in Termux (no Tk display) — CLI only."
echo "See docs/TERMUX.md for connecting a target phone."
