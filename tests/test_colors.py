"""colors 单元测试：hex/rgb/hsv 换算与取色格式化。"""
import pytest

from shiguang_capture.colors import format_color, hex_to_rgb, rgb_to_hex, rgb_to_hsv


class TestRgbToHex:
    def test_basic(self):
        assert rgb_to_hex(125, 155, 255) == "#7D9BFF"

    def test_black_white(self):
        assert rgb_to_hex(0, 0, 0) == "#000000"
        assert rgb_to_hex(255, 255, 255) == "#FFFFFF"

    def test_clamps_out_of_range(self):
        assert rgb_to_hex(300, -5, 128) == "#FF0080"

    def test_lower(self):
        assert rgb_to_hex(255, 0, 0, upper=False) == "#ff0000"


class TestHexToRgb:
    def test_full(self):
        assert hex_to_rgb("#7D9BFF") == (125, 155, 255)

    def test_no_hash(self):
        assert hex_to_rgb("7d9bff") == (125, 155, 255)

    def test_short_form(self):
        assert hex_to_rgb("#f00") == (255, 0, 0)

    def test_invalid(self):
        with pytest.raises(ValueError):
            hex_to_rgb("#12")
        with pytest.raises(ValueError):
            hex_to_rgb("zzzzzz")


class TestRgbToHsv:
    def test_pure_red(self):
        assert rgb_to_hsv(255, 0, 0) == (0, 100, 100)

    def test_white(self):
        assert rgb_to_hsv(255, 255, 255) == (0, 0, 100)

    def test_green(self):
        assert rgb_to_hsv(0, 255, 0) == (120, 100, 100)


class TestFormatColor:
    def test_hex(self):
        assert format_color(125, 155, 255, "hex") == "#7D9BFF"

    def test_rgb(self):
        assert format_color(125, 155, 255, "rgb") == "rgb(125, 155, 255)"

    def test_hsv(self):
        assert format_color(255, 0, 0, "hsv") == "hsv(0, 100%, 100%)"

    def test_unknown_format(self):
        with pytest.raises(ValueError):
            format_color(0, 0, 0, "cmyk")

    @pytest.mark.parametrize('rgb,expected', [((255,0,0), 'hsl(0, 100%, 50%)'),
        ((0,255,0), 'hsl(120, 100%, 50%)'), ((255,255,255), 'hsl(0, 0%, 100%)'),
        ((0,0,0), 'hsl(0, 0%, 0%)'), ((128,128,128), 'hsl(0, 0%, 50%)')])
    def test_hsl(self, rgb, expected):
        assert format_color(*rgb, 'hsl') == expected

    def test_rgba_alpha_is_explicit_output_value(self):
        assert format_color(300,-5,128,'rgba') == 'rgba(255, 0, 128, 1)'
