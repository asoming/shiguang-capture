"""tests/test_translate.py — 翻译引擎（纯逻辑，无 Qt）。

不依赖 argostranslate 是否安装：模型可用时验证神经翻译，
不可用时验证词典兜底与降级标注——两条路径都必须通。
"""
from __future__ import annotations

import pytest

from shiguang_capture.config import AppConfig
from shiguang_capture.translate import (
    ArgosBackend, CloudBackend, LocalDictBackend, TranslationResult,
    argos_available, create_translator, detect_language, resolve_direction,
    translate_text,
)


class TestDetectLanguage:
    def test_chinese(self):
        assert detect_language("这是一个截图工具的说明文字") == "zh"

    def test_english(self):
        assert detect_language("This is a screenshot tool for you") == "en"

    def test_empty(self):
        assert detect_language("") == "unknown"

    def test_whitespace_only(self):
        assert detect_language("   \n\t ") == "unknown"

    def test_short_english(self):
        assert detect_language("save") == "en"

    def test_pure_symbols(self):
        assert detect_language("!!! ??? 123") == "unknown"


class TestResolveDirection:
    def test_auto_zh_to_en(self):
        assert resolve_direction("这是一段中文", AppConfig()) == ("zh", "en")

    def test_auto_en_to_zh(self):
        assert resolve_direction("this is english", AppConfig()) == ("en", "zh")

    def test_forced_zh_target(self):
        cfg = AppConfig(target_lang="zh")
        assert resolve_direction("hello world", cfg) == ("en", "zh")

    def test_forced_en_target(self):
        cfg = AppConfig(target_lang="en")
        assert resolve_direction("你好世界", cfg) == ("zh", "en")

    def test_forced_target_same_as_source_preserved(self):
        """同语种保留原文，不伪造源语言。"""
        cfg = AppConfig(target_lang="en")
        assert resolve_direction("hello world", cfg) == ("en", "en")


class TestLocalDictBackend:
    def setup_method(self):
        self.backend = LocalDictBackend()

    def test_is_local_and_degraded(self):
        assert self.backend.is_local is True
        r = self.backend.translate("save", "en", "zh")
        assert r.degraded is True
        assert r.engine == "local-dict"

    def test_en_to_zh(self):
        assert self.backend.translate("screenshot", "en", "zh").target_text == "截图"

    def test_zh_to_en(self):
        r = self.backend.translate("截图", "zh", "en")
        assert "screenshot" in r.target_text

    def test_word_boundary_no_partial(self):
        """'screenshots' 不应被 'screenshot' 部分替换。"""
        assert self.backend.translate("screenshots", "en", "zh").target_text == "screenshots"

    def test_case_insensitive(self):
        assert self.backend.translate("Screenshot", "en", "zh").target_text == "截图"

    def test_longest_zh_term_wins(self):
        """中文按词长倒序替换，'截图' 不应被拆成 '截' + '图'。"""
        r = self.backend.translate("截图工具", "zh", "en")
        assert "screenshot" in r.target_text

    def test_glossary_hits_recorded(self):
        r = self.backend.translate("save and copy", "en", "zh")
        pairs = dict(r.glossary_hits)
        assert pairs.get("save") == "保存"
        assert pairs.get("copy") == "复制"

    def test_unknown_words_kept(self):
        assert "zzqq" in self.backend.translate("zzqq xxyy", "en", "zh").target_text

    def test_returns_translation_result(self):
        assert isinstance(self.backend.translate("hi", "en", "zh"), TranslationResult)

    def test_elapsed_ms_non_negative(self):
        assert self.backend.translate("save", "en", "zh").elapsed_ms >= 0


class TestCloudBackend:
    def test_not_local(self):
        assert CloudBackend().is_local is False

    def test_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            CloudBackend().translate("hi", "en", "zh")


class TestFactory:
    def test_default_is_local(self):
        assert isinstance(create_translator(AppConfig()), (LocalDictBackend, ArgosBackend))

    def test_cloud_when_allowed(self):
        cfg = AppConfig(allow_cloud_translate=True)
        assert isinstance(create_translator(cfg), CloudBackend)

    def test_argos_available_is_bool(self):
        assert isinstance(argos_available(), bool)

    def test_never_returns_cloud_without_consent(self):
        assert not isinstance(create_translator(AppConfig()), CloudBackend)


class TestTranslateText:
    def test_auto_zh_to_en(self):
        r = translate_text("截图工具很好用", AppConfig(), allow_cloud=False)
        assert r.source_lang == "zh" and r.target_lang == "en"
        assert "screenshot" in r.target_text

    def test_auto_en_to_zh(self):
        r = translate_text("save the screenshot", AppConfig(), allow_cloud=False)
        assert r.source_lang == "en" and r.target_lang == "zh"
        assert "保存" in r.target_text

    def test_cloud_blocked_without_consent(self):
        cfg = AppConfig(allow_cloud_translate=True)
        with pytest.raises(PermissionError):
            translate_text("hello", cfg, allow_cloud=False)

    def test_local_never_raises(self):
        assert translate_text("nothing", AppConfig()).engine in ("local-dict", "argos-local")

    def test_unknown_lang_defaults_en_zh(self):
        r = translate_text("123 !!!", AppConfig())
        assert r.source_lang == "en" and r.target_lang == "zh"

    def test_target_text_differs_from_source_for_known_words(self):
        """翻译必须真的改变文本，不能静默返回原文。"""
        r = translate_text("screenshot save copy", AppConfig())
        assert r.target_text.strip() != r.source_text.strip()
        assert not r.is_identity


@pytest.mark.skipif(not argos_available(), reason="未安装 Argos 离线模型")
class TestArgosBackend:
    """仅在离线神经模型就绪时运行。"""

    def test_reports_local(self):
        b = ArgosBackend()
        assert b.is_local is True and b.name == "argos-local"

    def test_en_to_zh_quality(self):
        r = translate_text("This is a quick screenshot tool.", AppConfig())
        assert r.engine == "argos-local"
        assert r.degraded is False
        assert r.target_text.strip()
        assert r.target_text != r.source_text

    def test_zh_to_en_quality(self):
        r = translate_text("这是一个截图工具", AppConfig())
        assert r.engine == "argos-local"
        assert any(w in r.target_text.lower() for w in ("screenshot", "screen", "tool"))

