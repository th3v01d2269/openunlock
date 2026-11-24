"""Plugin interface for chipset protocols.

A plugin speaks one chipset's low-level protocol (MTK BootROM, Qualcomm
Sahara/firehose, ...) and exposes the same small set of operations the core
uses. Plugins are optional: the core works fine without any installed.

To add a plugin: subclass ProtocolPlugin, implement the methods, and register
it in openunlock.protocols.registry (or entry points, once the project
grows). Every method must raise OpenUnlockError on failure and must never
touch IMEI/serial/MEID.
"""
from abc import ABC, abstractmethod


class ProtocolPlugin(ABC):
    #: human name, e.g. "mtkclient (MediaTek BootROM)"
    name = "base"
    #: chipsets this plugin handles, e.g. ["mt6765", "mt6789"]
    chipsets = []

    @abstractmethod
    def detect(self):
        """Return True if a device for this protocol is attached."""

    @abstractmethod
    def device_info(self):
        """Return a dict of chip / storage / security info."""

    @abstractmethod
    def read_partition(self, partition, out_path):
        """Read a partition to out_path. Returns out_path."""

    @abstractmethod
    def write_partition(self, partition, image_path):
        """Write image_path to a partition. Returns the tool output."""

    def supports(self, chipset):
        return chipset in self.chipsets

    def restore_imei(self, backup_data, serial):
        """Restore the device's ORIGINAL IMEI from its own backup.

        Optional: plugins implement this only for the restore path
        (NVRAM on MTK, NV items on Qualcomm). The default refuses —
        writing IMEI values without a chipset path is not allowed.
        backup_data is the dict from imei.load_backup(); the plugin must
        verify backup_data['serial'] == serial itself.
        """
        from ..errors import OpenUnlockError
        raise OpenUnlockError(
            "This protocol plugin cannot write IMEI values. IMEI restore "
            "needs the chipset tool (mtkclient for MTK, edl/QPST for "
            "Qualcomm) with the backup file as the source.")
