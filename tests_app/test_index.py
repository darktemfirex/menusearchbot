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
        self.assertEqual(len(self.items), 753)  # 754행 - 머리글(물류 624 + 수발주 129)

    def test_화면과_인터페이스가_모두_있다(self):
        kinds = {it["meta"]["kind"] for it in self.items}
        self.assertEqual(kinds, {"screen", "interface"})

    def test_화면_행은_메뉴_경로를_담는다(self):
        it = next(i for i in self.items if i["meta"]["id"] == "70-5004")
        self.assertEqual(it["meta"]["name"], "업무마감 등록")
        self.assertEqual(it["meta"]["detail"], "물류센터 > 물류재고 > 물류재고조사")
        self.assertIn("메뉴 경로: 물류센터 > 물류재고 > 물류재고조사", it["text"])

    def test_수발주_화면이_있고_업무가_검색_글에_들어간다(self):
        it = next(i for i in self.items if i["meta"]["id"] == "50-9906")
        self.assertEqual(it["meta"]["name"], "수발주공통코드관리")
        self.assertIn("업무: 수발주", it["text"])
        self.assertEqual(sum(1 for i in self.items if "업무: 수발주" in i["text"]), 129)

    def test_화면과_인터페이스_개수(self):
        n = lambda k: sum(1 for i in self.items if i["meta"]["kind"] == k)
        self.assertEqual((n("screen"), n("interface")), (436, 317))

    def test_ID는_겹치지_않는다(self):
        ids = [(i["meta"]["kind"], i["meta"]["id"]) for i in self.items]
        self.assertEqual(len(ids), len(set(ids)))

    def test_열_위치가_밀려도_머리글_이름으로_읽는다(self):
        # 업무 열이 없는 예전 구조와 업무 열이 낀 새 구조가 같은 결과가 된다
        old = [{"A": "번호", "B": "구분", "C": "인터페이스ID", "D": "인터페이스명", "I": "설명"},
               {"A": "1", "B": "화면", "C": "70-1", "D": "가", "I": "메뉴 > 하위"}]
        new = [{"A": "번호", "B": "업무", "C": "구분", "D": "인터페이스ID", "E": "인터페이스명", "J": "설명"},
               {"A": "1", "B": "물류", "C": "화면", "D": "70-1", "E": "가", "J": "메뉴 > 하위"}]
        a, b = index.make_item(index.normalize(old)[0]), index.make_item(index.normalize(new)[0])
        self.assertEqual(a["meta"], b["meta"])
        self.assertNotIn("업무", a["text"])
        self.assertIn("업무: 물류", b["text"])

    def test_인터페이스_행은_코드_번호를_뗀_상세를_담는다(self):
        it = next(i for i in self.items if i["meta"]["id"] == "IF-DPD-0017")
        self.assertIn("빅데이터플랫폼", it["meta"]["detail"])
        self.assertNotIn("07:", it["meta"]["detail"])
        self.assertIn("파일연계", it["text"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
