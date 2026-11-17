"""data/search_data.xlsx 읽기·행 변환 테스트(API 호출 없음). 실행: python -m unittest tests_app.test_index -v"""
import os
import sys
import unittest

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(LAB, "tools"))

import index  # noqa: E402


class IndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items = index.load_items()

    def test_머리글을_뺀_모든_행을_읽는다(self):
        self.assertEqual(len(self.items), 624)  # 625행 - 머리글

    def test_화면과_인터페이스가_모두_있다(self):
        kinds = {it["meta"]["kind"] for it in self.items}
        self.assertEqual(kinds, {"screen", "interface"})

    def test_화면_행은_메뉴_경로를_담는다(self):
        it = next(i for i in self.items if i["meta"]["id"] == "70-5004")
        self.assertEqual(it["meta"]["name"], "업무마감 등록")
        self.assertEqual(it["meta"]["detail"], "물류센터 > 물류재고 > 물류재고조사")
        self.assertIn("메뉴 경로: 물류센터 > 물류재고 > 물류재고조사", it["text"])

    def test_인터페이스_행은_코드_번호를_뗀_상세를_담는다(self):
        it = next(i for i in self.items if i["meta"]["id"] == "IF-DPD-0017")
        self.assertIn("빅데이터플랫폼", it["meta"]["detail"])
        self.assertNotIn("07:", it["meta"]["detail"])
        self.assertIn("파일연계", it["text"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
