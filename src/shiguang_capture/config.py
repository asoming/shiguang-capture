"""config.py — 应用配置（纯逻辑，JSON 持久化，可单元测试）。"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

APP_DIR_NAME = "shiguang-capture"


@dataclass
class HotkeyConfig:
    """全局热键（FR-1.1：可自定义 + 冲突检测）。"""

    capture_region: str = "f1"
    capture_fullscreen: str = "shift+f1"
    capture_scroll: str = "ctrl+f1"
    pin_last: str = "f3"
    color_picker: str = "f2"
    hide_all_pins: str = "shift+f3"
    restore_all_pins: str = "ctrl+shift+f3"
    ocr_recognize: str = "f4"
    record_toggle: str = "f6"
    record_stop: str = "f7"

    def conflicts(self) -> list[tuple[str, str]]:
        """返回互相冲突的热键对（同一按键分配给两个动作）。"""
        seen: dict[str, str] = {}
        out: list[tuple[str, str]] = []
        for action, key in asdict(self).items():
            norm = "+".join(sorted(part.strip() for part in key.lower().split("+") if part.strip()))
            if norm in seen:
                out.append((seen[norm], action))
            else:
                seen[norm] = action
        return out


@dataclass
class AppConfig:
    hotkeys: HotkeyConfig = field(default_factory=HotkeyConfig)
    save_dir: str = "~/Pictures/Shiguang"
    record_dir: str = "~/Videos/Shiguang"
    image_format: str = "png"          # png / jpg
    copy_to_clipboard: bool = True     # 截图后自动写剪贴板
    play_shutter_sound: bool = False
    pin_default_opacity: float = 1.0   # 贴图默认透明度（FR-1.23）
    picker_format: str = "hex"         # hex / rgb / hsv / hsl / rgba
    ocr_engine: str = "local"          # local / cloud（本地优先，FR 隐私红线）
    target_lang: str = "auto"          # 翻译目标语言：auto / zh / en
    allow_cloud_translate: bool = False  # 云端翻译总开关（默认关，隐私红线 NFR-6）
    launch_at_login: bool = False
    output_formats: dict = field(default_factory=dict)

    # ---------- 持久化 ----------
    @staticmethod
    def default_path() -> Path:
        if os.name == "nt":
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
        elif os.uname().sysname == "Darwin":  # type: ignore[attr-defined]
            base = Path.home() / "Library/Application Support"
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        return base / APP_DIR_NAME / "config.json"

    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        """加载配置；文件缺失或损坏时回落默认值（不抛异常，不阻塞启动）。"""
        p = path or cls.default_path()
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        cfg = cls()
        hk = raw.pop("hotkeys", {}) if isinstance(raw, dict) else {}
        for k, v in (hk.items() if isinstance(hk, dict) else []):
            if k in HotkeyConfig.__dataclass_fields__ and isinstance(v, str):
                setattr(cfg.hotkeys, k, v)
        for k, v in (raw.items() if isinstance(raw, dict) else []):
            if k not in {"hotkeys"} and k in cls.__dataclass_fields__:
                default = getattr(cfg, k)
                if type(v) is type(default) or (isinstance(default, float) and type(v) is int):
                    setattr(cfg, k, v)
        cfg.pin_default_opacity = max(0.1, min(1.0, cfg.pin_default_opacity))
        if cfg.ocr_engine != "local":
            cfg.ocr_engine = "local"
        cfg.allow_cloud_translate = False
        if cfg.picker_format not in {'hex', 'rgb', 'hsv', 'hsl', 'rgba'}:
            cfg.picker_format = 'hex'
        choices = {'ocr': {'text', 'json'}, 'code': {'text', 'code', 'json'},
                   'table': {'text', 'markdown', 'table', 'json'}, 'translate': {'text', 'json'}}
        cfg.output_formats = {mode: value for mode, value in cfg.output_formats.items()
                              if mode in choices and isinstance(value, str) and value in choices[mode]}
        return cfg

    def save(self, path: Path | None = None) -> Path:
        p = path or self.default_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=p.parent,
                                             prefix=".config-", delete=False) as temp:
                name = Path(temp.name)
                json.dump(asdict(self), temp, ensure_ascii=False, indent=2)
                temp.flush()
                os.fsync(temp.fileno())
            name.replace(p)
        finally:
            if name is not None:
                name.unlink(missing_ok=True)
        return p
