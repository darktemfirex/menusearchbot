"""화면(tools/web/index.html) 정적 검사. 실행: python -m unittest tests_app.test_ui -v"""
import colorsys
import os
import re
import unittest

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(LAB, "tools", "web", "index.html"), encoding="utf-8").read()


def _hex_colors(text):
    for h in re.findall(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", text):
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        yield h, tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


class UiTests(unittest.TestCase):
    def test_노란색을_쓰지_않는다(self):
        for h, (r, g, b) in _hex_colors(HTML):
            hue, light, sat = colorsys.rgb_to_hls(r, g, b)[0] * 360, colorsys.rgb_to_hls(r, g, b)[1], colorsys.rgb_to_hls(r, g, b)[2]
            is_yellow = 40 <= hue <= 70 and sat > 0.3 and 0.35 < light < 0.97
            self.assertFalse(is_yellow, f"노란 계열 색 #{h}")
        self.assertIsNone(re.search(r"(?i)\b(yellow|gold|lemon|khaki)\b", HTML))

    def test_키가_화면에_없다(self):
        self.assertNotIn("AXROUTER", HTML)
        self.assertNotIn("axrouter.ai", HTML)
        self.assertNotIn("Authorization", HTML)

    def test_샘플_질문_버튼이_없다(self):
        self.assertNotIn("EXAMPLES", HTML)
        self.assertNotIn('id="examples"', HTML)
        self.assertNotIn("어디에 있나요?", HTML)

    def test_사용자_글과_AI_글을_HTML로_해석하지_않는다(self):
        self.assertNotIn("innerHTML", HTML)
        self.assertIn("textContent", HTML)

    def test_빈_입력은_보내지_않는다(self):
        self.assertRegex(HTML, r"\.trim\(\)")
        self.assertRegex(HTML, r"if\s*\(\s*!\s*q\s*\)\s*return")

    def test_답변_보류_카드와_시행예정_표시와_로딩과_오류_문구(self):
        for s in ["답변 보류", "s.detail", "loading", "잠시 후 다시 시도해 주세요"]:
            self.assertIn(s, HTML)

    def test_보라_말풍선과_분홍_점선_보류_카드(self):
        self.assertRegex(HTML, r"dashed")
        self.assertRegex(HTML, r"/api/ask")


if __name__ == "__main__":
    unittest.main(verbosity=2)
