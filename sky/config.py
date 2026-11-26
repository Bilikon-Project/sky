from __future__ import annotations

import os
import re
from pathlib import Path

def _default_config_dir() -> Path:

    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "sky"

CONFIG_DIR = _default_config_dir()
CONFIG_FILE = CONFIG_DIR / "sky.conf"

DEFAULT_COLORS = {
    "background_color": "#1a1b26",
    "foreground_color": "#c0caf5",
    "accent_color":     "#7aa2f7",
    "accent_color_1":   "#7dcfff",
    "accent_color_2":   "#bb9af7",
    "color_dir":        "#7aa2f7",
    "color_symlink":    "#7dcfff",
    "color_executable": "#9ece6a",
    "color_hidden":     "#565f89",
    "color_error":      "#f7768e",
    "color_warning":    "#e0af68",
    "color_success":    "#9ece6a",
}

DERIVED_FROM = {
    "color_dir": "accent_color",
    "color_symlink": "accent_color_1",
}

MODES = ("tui", "gui", "tui+gui")
SPLIT_DIRECTIONS = ("left", "right", "down", "top")

_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_TRUE = {"yes", "true", "on", "enable", "enabled"}
_FALSE = {"no", "false", "off", "disable", "disabled"}

def normalize_hex(value) -> str | None:
    if not isinstance(value, str) or not _HEX_RE.match(value):
        return None
    value = value.lower()
    if len(value) == 4:
        value = "#" + "".join(ch * 2 for ch in value[1:])
    return value

def mix(color_a: str, color_b: str, t: float) -> str:
    a, b = normalize_hex(color_a), normalize_hex(color_b)
    if not a or not b:
        return color_a
    out = "#"
    for i in (1, 3, 5):
        x, y = int(a[i:i + 2], 16), int(b[i:i + 2], 16)
        out += f"{round(x + (y - x) * t):02x}"
    return out

class Config:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else CONFIG_FILE
        self.values: dict = {}
        self.shortcuts: dict[str, str] = {}
        self.shortcuts_enabled = True
        self.warnings: list[str] = []
        self.load()

    def load(self):
        self.values.clear()
        self.shortcuts.clear()
        self.shortcuts_enabled = True
        self.warnings.clear()

        try:
            text = self.path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return
        except OSError as e:
            self.warnings.append(f"config okunamadı ({self.path}): {e}")
            return

        for lineno, raw in enumerate(text.splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            key, sep, rest = line.partition(":")
            if not sep:
                self.warnings.append(f"satır {lineno}: ':' bulunamadı, atlandı")
                continue
            key = key.strip()
            rest = self._strip_comment(rest.strip()).strip()

            if key == "sky.shortcuts":
                self._load_shortcut(lineno, rest)
            else:
                self.values[key] = self._convert(rest)

        self._validate()

    @staticmethod
    def _strip_comment(s: str) -> str:
        m = re.search(r"\s#", s)
        return s[:m.start()] if m else s

    def _load_shortcut(self, lineno: int, rest: str):
        if ":" not in rest:
            val = rest.lower()
            if val in _TRUE:
                self.shortcuts_enabled = True
            elif val in _FALSE:
                self.shortcuts_enabled = False
            else:
                self.warnings.append(
                    f"satır {lineno}: sky.shortcuts için 'enable' veya 'disable' bekleniyordu")
            return

        combo, _, action = rest.partition(":")
        combo = combo.strip().lower().replace(" ", "")
        action = action.strip()
        if not combo or not action:
            self.warnings.append(f"satır {lineno}: kısayol biçimi hatalı")
            return
        self.shortcuts[combo] = action

    @staticmethod
    def _convert(v: str):
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1].strip()
        low = v.lower()
        if low in _TRUE:
            return True
        if low in _FALSE:
            return False
        if low in ("", "none") or v == "#":
            return None
        return v

    def _validate(self):
        for key in DEFAULT_COLORS:
            val = self.values.get(key)
            if val is not None and normalize_hex(val) is None:
                self.warnings.append(
                    f"{key}: geçersiz renk {val!r} (örn. #1a1b26), varsayılan kullanılacak")
        raw_mode = self.values.get("default_mode")
        if isinstance(raw_mode, str) and raw_mode.lower() not in MODES:
            self.warnings.append(f"default_mode: geçersiz değer {raw_mode!r} (tui | gui | tui+gui)")
        raw_dir = self.values.get("split_direction")
        if isinstance(raw_dir, str) and raw_dir.lower() not in SPLIT_DIRECTIONS:
            self.warnings.append(
                f"split_direction: geçersiz değer {raw_dir!r} ({' | '.join(SPLIT_DIRECTIONS)})")

    def get(self, key, default=None):
        val = self.values.get(key)
        return default if val is None else val

    def color(self, key: str) -> str:
        k = key
        while k:
            val = normalize_hex(self.values.get(k))
            if val:
                return val
            k = DERIVED_FROM.get(k)
        return DEFAULT_COLORS.get(key, DEFAULT_COLORS["foreground_color"])

    def _bool(self, key: str, default: bool) -> bool:
        v = self.values.get(key)
        return v if isinstance(v, bool) else default

    @property
    def default_mode(self) -> str:
        v = self.get("default_mode", "tui")
        v = str(v).lower() if not isinstance(v, bool) else "tui"
        return v if v in MODES else "tui"

    @property
    def start_path(self) -> str:
        v = self.get("start_path", "~")
        return v if isinstance(v, str) else "~"

    @property
    def show_hidden(self) -> bool:
        return self._bool("show_hidden", False)

    @property
    def trash_path(self) -> Path:
        v = self.get("trash_path")
        if isinstance(v, str):
            return Path(v).expanduser()
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        return Path(base) / "Trash"

    @property
    def file_types_all(self) -> bool:
        return self._bool("file_types_all", True)

    @property
    def file_types(self) -> tuple[str, ...]:
        raw = self.values.get("file_types")
        if not isinstance(raw, str):
            return ()
        out = []
        for part in re.split(r"[,\s]+", raw):
            part = part.strip().lower()
            if part:
                out.append(part if part.startswith(".") else "." + part)
        return tuple(out)

    @property
    def visible_file_types(self) -> tuple[str, ...] | None:
        if self.file_types_all:
            return None
        return self.file_types or None

    @property
    def split_enabled(self) -> bool:

        for key in ("split", "split_mode"):
            v = self.values.get(key)
            if isinstance(v, bool):
                return v
            if isinstance(v, str):
                return v.lower() in _TRUE
        return False

    @property
    def split_direction(self) -> str:
        v = self.get("split_direction", "right")
        v = v.lower() if isinstance(v, str) else "right"
        return v if v in SPLIT_DIRECTIONS else "right"

    @property
    def font_families(self) -> list[str]:
        out = []
        for key in ("global_font", "global_other_font"):
            v = self.get(key)
            if isinstance(v, str):
                out.append(v)
        return out
