"""Linux input handler using evdev.

Listens to *every* input device that has a middle button (BTN_MIDDLE), so any
mouse works - USB, wireless receivers that expose several nodes, Bluetooth,
laptop touchpads with a physical middle button, etc. Only the middle-button
press triggers a clip; every other button and movement is ignored.

Devices are re-scanned periodically, so a mouse plugged in after the agent
started (or re-plugged after being unplugged) is picked up automatically.
The devices are only read, never grabbed, so the mouse keeps working normally
for the desktop.
"""
import asyncio
import errno
import platform
import time
from typing import Dict, Optional, Set

from agent.input.base import InputHandler
from agent.logger import ContextLogger

# Seconds between scans for new/removed input devices.
RESCAN_SECONDS = 3.0

# Ignore repeated presses inside this window (a receiver can expose the same
# physical mouse on more than one device node, which would double-trigger).
DEBOUNCE_SECONDS = 0.3


class LinuxInputHandler(InputHandler):
    """Detects BTN_MIDDLE presses from any mouse via evdev."""

    def __init__(self, logger: ContextLogger):
        super().__init__(logger)
        self._running = False
        self._scanner: Optional[asyncio.Task] = None
        self._readers: Dict[str, asyncio.Task] = {}   # device path -> reader task
        self._ignored: Set[str] = set()               # paths without BTN_MIDDLE
        self._denied: Set[str] = set()                # paths we could not open (logged once)
        self._warned_no_device = False
        self._last_fire = 0.0

    # ------------------------------------------------------------------
    # Device discovery
    # ------------------------------------------------------------------

    def _scan(self, evdev) -> None:
        """Open any new device that has a middle button and start reading it."""
        try:
            paths = set(evdev.list_devices())
        except OSError as e:
            self._logger.error("Cannot list input devices", error=str(e))
            return

        # Forget paths that disappeared so a re-plugged device is re-examined.
        self._ignored &= paths
        self._denied &= paths

        for path in paths:
            task = self._readers.get(path)
            if task is not None and not task.done():
                continue
            if path in self._ignored or path in self._denied:
                continue

            try:
                device = evdev.InputDevice(path)
            except PermissionError:
                self._denied.add(path)
                self._logger.warning(
                    "No permission to read input device. Add the service user to "
                    "the 'input' group: sudo usermod -aG input courtreplay",
                    path=path,
                )
                continue
            except OSError:
                continue  # unplugged between list and open; retry next scan

            if self._has_middle_button(device, evdev):
                self._logger.info("Listening to input device", name=device.name, path=path)
                self._readers[path] = asyncio.create_task(self._read(path, device, evdev))
            else:
                self._ignored.add(path)
                device.close()

        if not self._readers and not self._warned_no_device:
            self._warned_no_device = True
            self._logger.warning(
                "No input device with a middle button found yet; still watching for one"
            )
        elif self._readers:
            self._warned_no_device = False

    @staticmethod
    def _has_middle_button(device, evdev) -> bool:
        keys = device.capabilities().get(evdev.ecodes.EV_KEY, [])
        return evdev.ecodes.BTN_MIDDLE in keys

    # ------------------------------------------------------------------
    # Event reading
    # ------------------------------------------------------------------

    async def _read(self, path: str, device, evdev) -> None:
        ecodes = evdev.ecodes
        try:
            async for event in device.async_read_loop():
                # value 1 = pressed (0 = released, 2 = auto-repeat: ignored)
                if (
                    event.type == ecodes.EV_KEY
                    and event.code == ecodes.BTN_MIDDLE
                    and event.value == 1
                ):
                    self._on_middle_press()
        except asyncio.CancelledError:
            raise
        except OSError as e:
            if e.errno == errno.ENODEV:
                self._logger.info("Input device removed", name=device.name, path=path)
            else:
                self._logger.error("Input read error", path=path, error=str(e))
        except Exception as e:
            self._logger.error("Input read error", path=path, error=str(e))
        finally:
            try:
                device.close()
            except Exception:
                pass
            self._readers.pop(path, None)

    def _on_middle_press(self) -> None:
        now = time.monotonic()
        if now - self._last_fire < DEBOUNCE_SECONDS:
            return
        self._last_fire = now
        self._logger.info("BTN_MIDDLE detected")
        self._fire_trigger()

    async def _scan_loop(self, evdev) -> None:
        while self._running:
            self._scan(evdev)
            await asyncio.sleep(RESCAN_SECONDS)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self):
        if platform.system() != "Linux":
            self._logger.warning("LinuxInputHandler only works on Linux")
            return

        try:
            import evdev
        except ImportError:
            self._logger.error("evdev not installed. Run: pip install evdev")
            return

        self._running = True
        self._scanner = asyncio.create_task(self._scan_loop(evdev))
        self._logger.info("Linux input handler started")

    async def stop(self):
        self._running = False
        tasks = [t for t in [self._scanner, *self._readers.values()] if t]
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._readers.clear()
        self._scanner = None
        self._logger.info("Linux input handler stopped")
