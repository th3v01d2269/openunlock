"""Protocol plugins: per-chipset deep modes (BROM/EDL/etc).

The adb/fastboot core covers phones that are alive and unlocked. The deep
work — a phone that won't boot, a locked bootloader on MTK/Qualcomm — needs
chipset-specific protocols spoken over USB (MTK BootROM, Qualcomm Sahara /
firehose). This package implements the public, documented framing of those
protocols and delegates actual flash operations to the open-source tools
(mtkclient, edl) when they are installed.

Existing open-source projects that do this work — integrate them rather
than rewriting them:
  - MTK: mtkclient (https://github.com/bkerler/mtkclient) — GPLv3,
    BootROM/preloader, readback, unlock, bypass auth.
  - Qualcomm: edl (https://github.com/bkerler/edl) — GPLv3, Sahara +
    firehose, flashing in EDL mode.
  - Unisoc: unisoc-unlock (PyPI) — identifier-token bootloader unlock.
"""
from .base import ProtocolPlugin
from .mtk import MtkPlugin
from .qualcomm import QualcommPlugin

PLUGINS = {
    "mtk": MtkPlugin,
    "qualcomm": QualcommPlugin,
}


def get_plugin(name):
    """Return a plugin instance by name ('mtk' | 'qualcomm')."""
    if name not in PLUGINS:
        from ..errors import OpenUnlockError
        raise OpenUnlockError(
            f"Unknown protocol plugin: {name} "
            f"(available: {', '.join(PLUGINS)})")
    return PLUGINS[name]()


def list_plugins():
    """Return [(name, plugin display name)]."""
    return [(name, cls.name) for name, cls in PLUGINS.items()]


__all__ = ["ProtocolPlugin", "MtkPlugin", "QualcommPlugin",
           "get_plugin", "list_plugins", "PLUGINS"]
