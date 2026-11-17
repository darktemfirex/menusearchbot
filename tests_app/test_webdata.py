"""브라우저 검색 모드(Pages)용 파일 테스트(API 호출 없음). 실행: python -m unittest tests_app.test_webdata -v"""
import json
import os
import sys
import unittest

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(LAB, "tools"))

import index  # noqa: E402

WEB = os.path.join(LAB, "tools", "web")


class WebData(unittest.TestCase):
    def test_data_json이_엑셀_행과_같다(self):
        with open(os.path.join(WEB, "data.json"), encoding="utf-8") as f:
            rows = json.load(f)
        items = index.load_items()
        self.assertEqual(len(rows), len(items))
        self.assertEqual([r["i"] for r in rows], [it["meta"]["id"] for it in items])
        self.assertEqual({r["k"] for r in rows}, {"s", "i"})

    def test_data_json에_벡터나_키가_없다(self):
        with open(os.path.join(WEB, "data.json"), encoding="utf-8") as f:
            text = f.read()
        self.assertNotIn("vector", text)
        self.assertNotIn("AXROUTER", text)

    def test_화면이_검색_스크립트와_데이터를_쓴다(self):
        with open(os.path.join(WEB, "index.html"), encoding="utf-8") as f:
            html = f.read()
        self.assertIn('src="search.js"', html)
        self.assertIn("data.json", html)
        self.assertIn("menusearchbot.zip", html)  # Pages 에서 내려받기 링크
        self.assertTrue(os.path.exists(os.path.join(WEB, "search.js")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
