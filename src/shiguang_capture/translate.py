"""translate.py — 翻译引擎（QQ 截图式「翻译」动作的落地实现）。

三级后端，按可用性自动降级（都保持隐私零外发）：

1. **ArgosBackend**（首选）：Argos Translate + CTranslate2 离线神经翻译。
   模型本地推理，图像与文本都不出本机。中英模型约 100MB，按需下载一次。
2. **LocalDictBackend**（兜底）：内置术语词典，逐词替换。零依赖、秒级可用，
   用于模型未安装或文本极短的场景。
3. **CloudBackend**（显式许可才启用）：任何云端外发必须先过
   `assert_privacy_guard`（PRD NFR-6 隐私红线）。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

# ---------------------------------------------------------------- 语言检测

_CJK = re.compile(r"[\u4e00-\u9fff]")
_LATIN = re.compile(r"[A-Za-z]")


def detect_language(text: str) -> str:
    """粗略判定源语言：zh / en / unknown（按字符占比）。"""
    total = len(re.sub(r"\s", "", text))
    if total == 0:
        return "unknown"
    cjk = len(_CJK.findall(text))
    latin = len(_LATIN.findall(text))
    if cjk / total >= 0.2:
        return "zh"
    if latin / total >= 0.5:
        return "en"
    return "unknown"


# ------------------------------------------------------- 内置离线词典（兜底）

# 开箱即用的术语表：覆盖截图场景高频词，作为模型缺失时的兜底。
_ZH2EN: dict[str, str] = {
    "截图": "screenshot", "屏幕": "screen", "识别": "recognition",
    "翻译": "translation", "保存": "save", "复制": "copy", "取消": "cancel",
    "确认": "confirm", "设置": "settings", "更新": "update", "版本": "version",
    "图片": "image", "文字": "text", "工具": "tool", "功能": "feature",
    "长截图": "scrolling screenshot", "贴图": "pin to screen", "取色": "color picker",
    "录屏": "screen recording", "剪贴板": "clipboard", "快捷键": "hotkey",
    "隐私": "privacy", "本地": "local", "云端": "cloud", "识别率": "accuracy",
    "这个": "this", "可以": "can", "支持": "support", "使用": "use",
    "桌面": "desktop", "窗口": "window", "系统": "system", "文件": "file",
    "关于": "about", "帮助": "help", "退出": "quit", "开始": "start",
}

_EN2ZH: dict[str, str] = {v: k for k, v in _ZH2EN.items()}
_EN2ZH.update({
    "hello": "你好", "world": "世界", "screenshot": "截图",
    "screen": "屏幕", "capture": "捕获", "image": "图像",
    "text": "文字", "translate": "翻译", "settings": "设置",
    "update": "更新", "download": "下载", "install": "安装",
    "version": "版本", "privacy": "隐私", "local": "本地",
    "cloud": "云端", "clipboard": "剪贴板", "hotkey": "快捷键",
    "save": "保存", "copy": "复制", "cancel": "取消", "confirm": "确认",
    "toolbar": "工具栏", "this": "这个", "tool": "工具", "feature": "功能",
    "quick": "快速", "utility": "工具", "press": "按", "start": "开始",
    "for": "用于", "and": "和", "the": "", "is": "是",
})


@dataclass
class TranslationResult:
    source_text: str
    target_text: str
    source_lang: str
    target_lang: str
    engine: str
    elapsed_ms: int = 0
    glossary_hits: list[tuple[str, str]] = field(default_factory=list)
    degraded: bool = False          # True = 走了词典兜底，译文不完整

    @property
    def is_identity(self) -> bool:
        return self.source_text.strip() == self.target_text.strip()


# --------------------------------------------------- Argos 离线神经翻译后端

class ArgosBackend:
    """Argos Translate 离线神经翻译（本地推理，文本不出本机）。"""

    name = "argos-local"
    is_local = True

    def __init__(self) -> None:
        from . import _argos_compat

        _argos_compat.apply()          # 注入 stanza 桩 + 固定 MiniSBD 切分
        import argostranslate.translate

        self._t = argostranslate.translate
        log.info("Argos Translate 已就绪（离线神经翻译 · MiniSBD 轻量切分）")

    def supports(self, source: str, target: str) -> bool:
        try:
            installed = self._t.get_installed_languages()
            langs = {lang.code: lang for lang in installed}
            if source not in langs or target not in langs:
                return False
            # 直接语言对模型存在，或可经 pivot（如 en 中转）到达
            return langs[source].get_translation(langs[target]) is not None
        except Exception:  # noqa: BLE001
            return False

    def translate(self, text: str, source: str, target: str) -> TranslationResult:
        import time

        t0 = time.perf_counter()
        out = self._t.translate(text, source, target)
        elapsed = int((time.perf_counter() - t0) * 1000)
        return TranslationResult(
            source_text=text, target_text=out, source_lang=source,
            target_lang=target, engine=self.name, elapsed_ms=elapsed,
        )


def argos_available() -> bool:
    """依赖与中英语言包是否就绪。"""
    try:
        from . import _argos_compat

        _argos_compat.apply()
        import argostranslate.translate as t

        codes = {lang.code for lang in t.get_installed_languages()}
        return {"en", "zh"}.issubset(codes)
    except Exception:  # noqa: BLE001
        return False


# ------------------------------------------------------------- 本地词典后端

class LocalDictBackend:
    """离线术语词典后端：零依赖、秒级可用，作为模型缺失时的兜底。"""

    name = "local-dict"
    is_local = True

    def translate(self, text: str, source: str, target: str) -> TranslationResult:
        import time

        t0 = time.perf_counter()
        hits: list[tuple[str, str]] = []

        if target == "zh":
            out = text
            for en in sorted(_EN2ZH, key=len, reverse=True):
                if not en:
                    continue
                pattern = re.compile(rf"(?<![A-Za-z]){re.escape(en)}(?![A-Za-z])",
                                     re.IGNORECASE)
                if pattern.search(out):
                    out = pattern.sub(_EN2ZH[en], out)
                    hits.append((en, _EN2ZH[en]))
        else:
            out = text
            # 中文按词长倒序替换，避免「截」先于「截图」命中
            for zh in sorted(_ZH2EN, key=len, reverse=True):
                if zh in out:
                    out = out.replace(zh, f" {_ZH2EN[zh]} ")
                    hits.append((zh, _ZH2EN[zh]))
            out = re.sub(r"\s{2,}", " ", out).strip()

        elapsed = int((time.perf_counter() - t0) * 1000)
        return TranslationResult(
            source_text=text, target_text=out, source_lang=source,
            target_lang=target, engine=self.name, elapsed_ms=elapsed,
            glossary_hits=hits[:12], degraded=True,
        )


# ------------------------------------------------------------- 云端占位后端

class CloudBackend:
    """云端翻译后端占位：仅当用户显式开启隐私许可时才会被创建。

    真实接入点在 translate()——可对接任意翻译 API / 自建服务。
    """

    name = "cloud-api"
    is_local = False

    def __init__(self, provider: str = "generic") -> None:
        self.provider = provider

    def translate(self, text: str, source: str, target: str) -> TranslationResult:
        raise NotImplementedError(
            "云端翻译尚未接入。请在设置中关闭「允许云端翻译」，"
            "或等待 V1.x 版本发布（隐私默认不上传）"
        )


# ------------------------------------------------------------------ 工厂

def create_translator(config) -> object:
    """按配置创建翻译后端：优先离线神经模型，不可用则词典兜底。"""
    if getattr(config, "allow_cloud_translate", False):
        return CloudBackend(getattr(config, "cloud_provider", "generic"))
    from .offline_translation import available, BundledTranslator
    if available():
        return BundledTranslator()
    if argos_available():
        try:
            return ArgosBackend()
        except Exception as exc:  # noqa: BLE001
            log.warning("Argos 初始化失败（%s），降级为词典后端", exc)
    return LocalDictBackend()


def resolve_direction(text: str, config) -> tuple[str, str]:
    """决定翻译方向。config.target_lang 为 auto 时按内容自动判定。"""
    src = detect_language(text)
    pref = getattr(config, "target_lang", "auto")
    if pref in ("zh", "en"):
        return src, pref
    if src == "zh":
        return "zh", "en"
    return "en", "zh"


def translate_text(text: str, config, *, allow_cloud: bool = False) -> TranslationResult:
    """翻译入口：检测语言 → 选后端 → 出结果（含降级标注）。"""
    backend = create_translator(config)
    if not getattr(backend, "is_local", True) and not allow_cloud:
        raise PermissionError("云端翻译未获显式许可，已阻止外发（PRD NFR-6）")

    src, target = resolve_direction(text, config)
    if src == target:
        return TranslationResult(text, text, src, target, "same-language")

    # 后端不支持该语言对时，回落到词典（不静默返回原文）
    if isinstance(backend, ArgosBackend) and not backend.supports(src, target):
        log.info("Argos 缺少 %s→%s 模型，降级为词典后端", src, target)
        backend = LocalDictBackend()

    return backend.translate(text, src, target)
