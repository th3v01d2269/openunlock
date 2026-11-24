"""Tkinter GUI for OpenUnlock.

Simple device panel: refresh the device list, show info, and run the safe
operations. Destructive actions pop a confirmation dialog first — there is
no way to trigger them with one accidental click.
"""
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import (__version__, apple, backup, device as device_mod, firmware,
               flash, frp, imei, lockscreen, profiles as profiles_mod,
               unlock)
from .errors import OpenUnlockError


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"OpenUnlock {__version__}")
        self.geometry("640x480")
        self.serial = None

        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Button(top, text="Refresh devices",
                   command=self.refresh).pack(side="left")
        self.device_var = tk.StringVar(value="no device selected")
        ttk.Label(top, textvariable=self.device_var).pack(
            side="left", padx=8)

        self.listbox = tk.Listbox(self, height=6)
        self.listbox.pack(fill="x", padx=8)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=8, pady=8)
        ttk.Button(btns, text="Device info",
                   command=self.show_info).pack(side="left", padx=2)
        ttk.Button(btns, text="Bootloader unlock",
                   command=self.do_unlock).pack(side="left", padx=2)
        ttk.Button(btns, text="Flash image...",
                   command=self.do_flash).pack(side="left", padx=2)
        ttk.Button(btns, text="Factory reset",
                   command=self.do_reset).pack(side="left", padx=2)
        ttk.Button(btns, text="Backup boot",
                   command=self.do_backup).pack(side="left", padx=2)

        btns2 = ttk.Frame(self)
        btns2.pack(fill="x", padx=8, pady=4)
        ttk.Button(btns2, text="FRP status",
                   command=self.do_frp_status).pack(side="left", padx=2)
        ttk.Button(btns2, text="IMEI read",
                   command=self.do_imei_read).pack(side="left", padx=2)
        ttk.Button(btns2, text="IMEI backup",
                   command=self.do_imei_backup).pack(side="left", padx=2)
        ttk.Button(btns2, text="Show profile",
                   command=self.do_profile).pack(side="left", padx=2)
        ttk.Button(btns2, text="Inspect firmware...",
                   command=self.do_firmware).pack(side="left", padx=2)
        ttk.Button(btns2, text="Remove lock (root)",
                   command=self.do_lock_remove).pack(side="left", padx=2)

        self.log = tk.Text(self, height=14, state="disabled")
        self.log.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def _write(self, text):
        self.log.config(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def refresh(self):
        self.listbox.delete(0, "end")
        try:
            for d in device_mod.detect():
                self.listbox.insert("end", f"{d.serial}  [{d.mode}]")
        except OpenUnlockError as exc:
            self._write(f"Error: {exc}")
        if self.listbox.size() == 0:
            self.listbox.insert("end", "(no devices — connect a phone)")

    def _on_select(self, _event):
        sel = self.listbox.curselection()
        if not sel:
            return
        text = self.listbox.get(sel[0])
        if text.startswith("("):
            self.serial = None
            return
        self.serial = text.split()[0]
        self.device_var.set(self.serial)

    def _need_serial(self):
        if not self.serial:
            messagebox.showwarning("No device",
                                   "Select a device from the list first.")
            return False
        return True

    def _confirm(self, title, text):
        return messagebox.askyesno(title, text + "\n\nAre you sure?")

    def show_info(self):
        if not self._need_serial():
            return
        try:
            dev = device_mod.require_one(self.serial)
            info = device_mod.info_dict(dev)
            self._write("\n".join(f"{k}: {v}" for k, v in info.items()))
        except OpenUnlockError as exc:
            self._write(f"Error: {exc}")

    def do_unlock(self):
        if not self._need_serial():
            return
        if not self._confirm("Unlock bootloader",
                              "This FACTORY-RESETS the phone. All data is erased."):
            return
        try:
            self._write(unlock.unlock(self.serial, confirm=True))
        except OpenUnlockError as exc:
            self._write(f"Error: {exc}")

    def do_flash(self):
        if not self._need_serial():
            return
        path = filedialog.askopenfilename(title="Choose image to flash")
        if not path:
            return
        part = "boot"
        if not self._confirm("Flash partition",
                              f"Flash {path} to partition '{part}'?"):
            return
        try:
            self._write(flash.flash_partition(part, path, self.serial,
                                              confirm=True))
        except OpenUnlockError as exc:
            self._write(f"Error: {exc}")

    def do_reset(self):
        if not self._need_serial():
            return
        if not self._confirm("Factory reset",
                              "This erases ALL user data on the phone."):
            return
        try:
            self._write(flash.factory_reset(self.serial, confirm=True))
        except OpenUnlockError as exc:
            self._write(f"Error: {exc}")

    def do_backup(self):
        if not self._need_serial():
            return
        try:
            path = backup.backup_partition("boot", "./backups", self.serial)
            self._write(f"Saved boot to {path}")
        except OpenUnlockError as exc:
            self._write(f"Error: {exc}")

    def do_frp_status(self):
        if not self._need_serial():
            return
        try:
            s = frp.status(self.serial)
            self._write("\n".join(f"{k}: {v}" for k, v in s.items()))
        except OpenUnlockError as exc:
            self._write(f"Error: {exc}")

    def do_imei_read(self):
        if not self._need_serial():
            return
        try:
            info = imei.read_imei(self.serial)
            self._write(f"IMEI: {', '.join(info['imei']) or '—'}")
            self._write(f"MEID: {info['meid'] or '—'}")
        except OpenUnlockError as exc:
            self._write(f"Error: {exc}")

    def do_imei_backup(self):
        if not self._need_serial():
            return
        try:
            path = imei.backup_imei(self.serial)
            self._write(f"IMEI backup saved to {path}")
        except OpenUnlockError as exc:
            self._write(f"Error: {exc}")

    def do_profile(self):
        if not self._need_serial():
            return
        try:
            dev = device_mod.require_one(self.serial)
            device_mod.fill_info(dev)
            prof = profiles_mod.match_device(dev.brand, dev.model)
            self._write(profiles_mod.format_profile(prof))
        except OpenUnlockError as exc:
            self._write(f"Error: {exc}")

    def do_firmware(self):
        path = filedialog.askopenfilename(title="Choose firmware ZIP")
        if not path:
            return
        try:
            report = firmware.inspect_firmware(path, self.serial)
            self._write(firmware.format_report(report))
        except OpenUnlockError as exc:
            self._write(f"Error: {exc}")

    def do_lock_remove(self):
        if not self._need_serial():
            return
        if not self._confirm("Remove screen lock",
                              "Deletes the lock credential database. "
                              "Requires a ROOTED device."):
            return
        try:
            self._write(lockscreen.remove_lock(self.serial, confirm=True))
        except OpenUnlockError as exc:
            self._write(f"Error: {exc}")


def run_gui():
    App().mainloop()
