"""Windows input handler using a global low-level mouse hook via ctypes.

IMPORTANT - why the hook callback is so minimal:
Windows low-level hooks (WH_MOUSE_LL) run *inside the system input path*. Every
mouse event waits for the callback to return, and Windows enforces a
LowLevelHooksTimeout (often 300 ms, sometimes less). Any slow work in the
callback - above all file I/O such as writing a log line - delays or drops input
for the whole desktop and the pointer crawls to a few frames per second.

So the hook callback does exactly one thing: push an event onto a queue and
return. Logging and trigger dispatch happen on a separate consumer thread.
"""
import platform
import queue
import threading
from typing import Optional

from agent.input.base import InputHandler
from agent.logger import ContextLogger

IS_WINDOWS = platform.system() == "Windows"

# Everything Windows-specific is imported lazily so this module can still be
# imported on Linux (agent/input/__init__.py imports it unconditionally).
if IS_WINDOWS:
    import ctypes
    import ctypes.wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    # Critical on 64-bit: without an explicit restype the hook handle returned
    # by SetWindowsHookExW is truncated to a 32-bit int and the hook fails.
    user32.SetWindowsHookExW.restype = ctypes.c_void_p
    user32.CallNextHookEx.restype = ctypes.c_ssize_t
    user32.CallNextHookEx.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM
    ]
    user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
    user32.UnhookWindowsHookEx.restype = ctypes.wintypes.BOOL

    WH_MOUSE_LL = 14
    WM_MBUTTONDOWN = 0x0207

    LowLevelMouseProc = ctypes.WINFUNCTYPE(
        ctypes.c_long, ctypes.c_int, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM
    )


class WindowsInputHandler(InputHandler):
    """Detects a global Middle Click on Windows using a low-level mouse hook."""

    def __init__(self, logger: ContextLogger):
        super().__init__(logger)
        self._hook_id = None
        self._hook_thread: Optional["threading.Thread"] = None
        self._consumer_thread: Optional["threading.Thread"] = None
        self._stop_event = None
        self._events: "queue.Queue[str]" = queue.Queue()
        # Keep a strong reference: if the WINFUNCTYPE wrapper is garbage
        # collected the callback pointer becomes invalid and the hook crashes.
        self._callback = None

    # ---- hook thread -----------------------------------------------------

    def _mouse_proc(self, nCode, wParam, lParam):
        """Runs in the system input path - must return immediately, no I/O."""
        try:
            if nCode == 0 and wParam == WM_MBUTTONDOWN:
                self._events.put_nowait("MIDDLE")
        except Exception:
            # Never let an exception escape into the Windows input path.
            pass
        return user32.CallNextHookEx(self._hook_id, nCode, wParam, lParam)

    def _run_hook(self):
        """Install the hook and pump messages (must be the installing thread)."""
        if not IS_WINDOWS:
            return

        self._callback = LowLevelMouseProc(self._mouse_proc)
        # hMod must be NULL for a global low-level hook. Passing
        # GetModuleHandleW(None) here overflows the untyped ctypes argument and
        # the hook silently fails to install.
        self._hook_id = user32.SetWindowsHookExW(WH_MOUSE_LL, self._callback, None, 0)

        if not self._hook_id:
            self._logger.error("Failed to set mouse hook")
            return

        self._logger.info("Mouse hook installed")

        msg = ctypes.wintypes.MSG()
        while not self._stop_event.is_set():
            # Non-blocking pump plus a short wait: the loop stays responsive
            # enough to notice stop_event and shut down cleanly.
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            self._stop_event.wait(0.01)

        user32.UnhookWindowsHookEx(self._hook_id)
        self._hook_id = None
        self._logger.info("Mouse hook removed")

    # ---- consumer thread -------------------------------------------------

    def _consume(self):
        """Do the slow work (logging, trigger dispatch) off the input path."""
        while not self._stop_event.is_set():
            try:
                self._events.get(timeout=0.2)
            except queue.Empty:
                continue

            self._logger.info("Middle click detected")
            self._fire_trigger()

    # ---- lifecycle -------------------------------------------------------

    async def start(self):
        if not IS_WINDOWS:
            self._logger.warning("WindowsInputHandler only works on Windows")
            return

        self._running = True
        self._stop_event = threading.Event()

        self._consumer_thread = threading.Thread(
            target=self._consume, name="input-consumer", daemon=True
        )
        self._consumer_thread.start()

        self._hook_thread = threading.Thread(
            target=self._run_hook, name="mouse-hook", daemon=True
        )
        self._hook_thread.start()

        self._logger.info("Windows input handler started")

    async def stop(self):
        self._running = False
        if self._stop_event is not None:
            self._stop_event.set()
        for thread in (self._hook_thread, self._consumer_thread):
            if thread:
                thread.join(timeout=2)
        self._logger.info("Windows input handler stopped")
