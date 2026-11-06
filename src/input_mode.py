"""One persisted switch for the application's complete keyboard/mouse backend."""
import json
import threading
import time
from pathlib import Path

from ok.device.interaction_methods.base import BaseInteraction
from ok.device.interaction_methods.post_message import PostMessageInteraction
from ok.device.interaction_methods.pynput import PynputInteraction

from src.app_identity import CONFIG_ROOT
from src.workshop import atomic_write, json_bytes

BACKGROUND = "background"
SYSTEM = "system"
MODES = {BACKGROUND, SYSTEM}


def settings_path():
    return CONFIG_ROOT / "ClientSettings.json"


def read_mode(path=None):
    try:
        value = json.loads(Path(path or settings_path()).read_text(encoding="utf-8")).get("input_mode")
        return value if value in MODES else BACKGROUND
    except (OSError, ValueError, TypeError, AttributeError):
        return BACKGROUND


def uses_background_input(interaction):
    if isinstance(interaction, SwitchableInteraction):
        return interaction.mode == BACKGROUND
    return isinstance(interaction, PostMessageInteraction)


class SwitchableInteraction(BaseInteraction):
    def __init__(self, capture, hwnd_window, mode_file=None):
        super().__init__(capture)
        self.hwnd_window = hwnd_window
        self.mode_file = Path(mode_file or settings_path())
        self.mode = read_mode(self.mode_file)
        self._backends = {}
        self._lock = threading.RLock()
        self._held_keys = set()
        self._held_buttons = set()

    def _backend(self):
        if self.mode not in self._backends:
            cls = PostMessageInteraction if self.mode == BACKGROUND else PynputInteraction
            self._backends[self.mode] = cls(self.capture, self.hwnd_window)
        backend = self._backends[self.mode]
        backend.capture = self.capture
        return backend

    def set_mode(self, mode):
        if mode not in MODES:
            raise ValueError("Invalid input mode")
        with self._lock:
            if self._held_keys or self._held_buttons:
                raise RuntimeError("Release all inputs before switching input mode.")
            if mode == SYSTEM and not self.hwnd_window.is_foreground():
                self.hwnd_window.bring_to_front()
                if not self.hwnd_window.is_foreground():
                    raise RuntimeError("Focus the game before enabling system input.")
            atomic_write(self.mode_file, json_bytes({"input_mode": mode}))
            self.mode = mode

    def _ready(self):
        return self.mode == BACKGROUND or self.hwnd_window.is_foreground()

    def _call(self, method, *args, release=False, **kwargs):
        with self._lock:
            if not release and not self._ready():
                return False
            backend = self._backend()
            previous = getattr(backend, "check_clickable", True)
            try:
                # A key pressed by us must be released even if focus was lost.
                if release and self.mode == SYSTEM:
                    backend.check_clickable = False
                return getattr(backend, method)(*args, **kwargs)
            finally:
                if self.mode == SYSTEM:
                    backend.check_clickable = previous

    def send_key(self, key, down_time=0.01):
        return self._call("send_key", key, down_time)

    def send_key_down(self, key):
        with self._lock:
            if self._ready():
                self._held_keys.add(key)
                return self._call("send_key_down", key)
            return False

    def send_key_up(self, key):
        with self._lock:
            owned = key in self._held_keys
            try:
                return self._call("send_key_up", key, release=owned)
            finally:
                self._held_keys.discard(key)

    def click(self, x=-1, y=-1, move_back=False, name=None, down_time=0.01, move=False, key="left"):
        return self._call("click", x, y, move_back=move_back, name=name, down_time=down_time, move=move, key=key)

    def right_click(self, x=-1, y=-1, move_back=False, name=None):
        return self.click(x, y, move_back=move_back, name=name, key="right")

    def mouse_down(self, x=-1, y=-1, name=None, key="left"):
        with self._lock:
            if self._ready():
                self._held_buttons.add(key)
                return self._call("mouse_down", x, y, name=name, key=key)
            return False

    def mouse_up(self, key="left"):
        with self._lock:
            owned = key in self._held_buttons
            try:
                return self._call("mouse_up", key=key, release=owned)
            finally:
                self._held_buttons.discard(key)

    def move(self, x, y):
        return self._call("move", x, y)

    def swipe(self, x1, y1, x2, y2, duration=3, settle_time=0):
        with self._lock:
            if self.mode == BACKGROUND:
                return self._call("swipe", x1, y1, x2, y2, duration, settle_time=settle_time)
            if not self._ready():
                return False
            self.mouse_down(x1, y1)
            try:
                steps = max(1, int(duration / 20))
                for step in range(1, steps + 1):
                    if not self._ready():
                        raise RuntimeError("Game window lost focus; dragging stopped")
                    self.move(int(x1 + (x2 - x1) * step / steps), int(y1 + (y2 - y1) * step / steps))
                    time.sleep(max(0, duration) / steps / 1000)
            finally:
                self.mouse_up()

    def scroll(self, x, y, scroll_amount):
        return self._call("scroll", x, y, scroll_amount)

    def input_text(self, text):
        if self.mode == BACKGROUND:
            return self._call("input_text", text)
        if self._ready():
            from pynput.keyboard import Controller
            Controller().type(text)

    def activate(self):
        if self.mode == BACKGROUND:
            return self._call("activate")
        return self.hwnd_window.bring_to_front()

    def should_capture(self):
        ready = self._ready()
        if not ready:
            self.on_destroy()
        return ready

    def on_run(self):
        if self.mode == SYSTEM:
            self.hwnd_window.bring_to_front()

    def on_destroy(self):
        for key in tuple(self._held_keys):
            self.send_key_up(key)
        for button in tuple(self._held_buttons):
            self.mouse_up(button)


def switch_all_inputs(executor, mode):
    """Call on the executor thread, between tasks rather than during a rotation."""
    if getattr(executor, "current_task", None) is not None:
        raise RuntimeError("Stop the current task before switching input mode.")
    interaction = executor.interaction
    if not isinstance(interaction, SwitchableInteraction):
        raise RuntimeError("Connect the Windows target before switching input mode.")
    interaction.set_mode(mode)
    executor.reset_scene()
    return mode
