"""Typed errors for OpenUnlock.

Every failure surfaces as one of these, with a message a human can act on.
Nothing here ever prints a raw traceback to the user for expected failures.
"""


class OpenUnlockError(Exception):
    """Base error for all expected OpenUnlock failures."""


class ToolNotFoundError(OpenUnlockError):
    """adb/fastboot (or another external binary) is not installed."""

    def __init__(self, tool):
        super().__init__(
            f"'{tool}' was not found. Install Android platform-tools "
            f"(https://developer.android.com/tools/adb) and make sure "
            f"'{tool}' is on your PATH."
        )
        self.tool = tool


class DeviceNotFoundError(OpenUnlockError):
    """No device matched, or no device is attached at all."""

    def __init__(self, detail="No device found. Connect a phone and "
                               "accept the USB-debugging prompt."):
        super().__init__(detail)


class CommandFailedError(OpenUnlockError):
    """An adb/fastboot command ran and failed."""

    def __init__(self, cmd, returncode, output=""):
        self.cmd = cmd
        self.returncode = returncode
        self.output = output
        msg = f"Command failed (exit {returncode}): {' '.join(cmd)}"
        if output.strip():
            msg += f"\n{output.strip()}"
        super().__init__(msg)


class RefusedError(OpenUnlockError):
    """The tool refuses to do something unsafe or out of scope.

    Used for IMEI/serial changes, FRP bypass, and any operation on a device
    the user does not own or has not confirmed.
    """

    pass
