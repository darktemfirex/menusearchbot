"""브라우저 E2E 테스트(Playwright). 진짜 서버 + 진짜 엔진(AXRouter API 호출)으로 화면을 직접 눌러 본다.

준비(한 번):  pip install playwright   그리고   python -m playwright install chromium
실행:         python -m unittest tests_app.test_e2e -v
"""
import os
import sys
import threading
import unittest

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(LAB, "tools"))

from playwright.sync_api import sync_playwright  # noqa: E402

import server  # noqa: E402
from chatbot import answer  # noqa: E402

WAIT_MS = 120_000  # 검색 + 리랭킹 + 답변이 몇 번의 API 호출이라 넉넉히


class E2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = server.make_server(answer, port=0)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.httpd.server_address[1]}/"
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        self.page = self.browser.new_page()
        self.page.set_default_timeout(WAIT_MS)
        self.page.goto(self.url)

    def tearDown(self):
        self.page.close()

    def ask(self, question):
        self.page.fill("#input", question)
        self.page.click("#send")

    def test_E2E1_방학_육아휴직_질문은_출처_카드에_제19조가_있다(self):
        self.ask("애 학교가 방학인데 1~2주만 육아휴직 쓸 수 있나요?")
        sticker = self.page.locator(".sticker", has_text="제19조")
        sticker.first.wait_for()
        self.assertGreaterEqual(sticker.count(), 1)
        self.assertEqual(self.page.locator(".withheld").count(), 0)

    def test_E2E2_최저임금_질문은_화면에_답변_보류가_보인다(self):
        self.ask("올해 최저임금은 얼마예요?")
        self.page.locator(".withheld", has_text="답변 보류").wait_for()
        self.assertTrue(self.page.get_by_text("답변 보류").is_visible())
        self.assertEqual(self.page.locator(".sticker").count(), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
