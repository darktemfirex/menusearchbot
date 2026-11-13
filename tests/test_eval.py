"""법령 챗봇 인수 테스트 (spec.md 의 테스트 시나리오 + eval/questions_laws.jsonl 의 질문마다 하나씩).

아직 구현이 없는 상태에서 먼저 만든 테스트다. 지금은 모두 실패(빨간불)해야 한다.

테스트가 요구하는 인터페이스 (구현은 tools/chatbot.py 에 만든다):

    from chatbot import answer
    result = answer(question, history=None)

    result = {
        "kind": "answer" | "withheld",       # 「답변 보류」면 "withheld"
        "text": "답 본문",                    # withheld 면 빈 문자열이어도 된다
        "sources": [                          # 리랭킹이 고른 조항 그대로(코드가 붙임). withheld 면 []
            {"law": "근로기준법", "article": "제60조", "title": "연차 유급휴가",
             "pending": True, "pending_dates": ["2027-06-09"]},
        ],
    }
    history = [{"question": "...", "result": <앞 질문의 result>}, ...]   # 앞 대화(오래된 것부터)

실행(표준 라이브러리 unittest, pytest 설치 불필요):
    python -m unittest tests.test_eval -v        # 실제 AXRouter API 를 부른다(질문마다 몇 초)

규칙
- 정답 조항(gold)이 있으면: 답의 출처에 그 조항(법 이름 + 조 번호)이 모두 있다.
- 정답 조항이 비어 있으면: 「답변 보류」가 나오고 출처·답 본문이 없다.
- 그 조항에 「시행 예정」 표시가 있으면: 출처에 pending=True 와 예정일이 있다.
  (어느 조항이 시행 예정인지는 laws/ 원문을 index.py 의 split_articles 로 읽어 정한다)
"""
import json
import os
import sys
import unittest

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(LAB, "tools")
EVAL = os.path.join(LAB, "eval", "questions_laws.jsonl")
sys.path.insert(0, TOOLS)

from index import split_articles  # noqa: E402  (이미 있는 저장 단계 코드: 조항 자르기 + 메타데이터)

# (파일 이름, 조 번호) -> 메타데이터(법 이름, 시행 예정 여부, 예정일)
ARTICLES = {(a["meta"]["source"], a["meta"]["article"]): a["meta"] for a in split_articles()}


def ask(question, history=None):
    """챗봇 엔진을 부른다. 아직 tools/chatbot.py 가 없으면 여기서 실패한다."""
    from chatbot import answer
    return answer(question, history=history)


def has_source(result, law, article):
    return any(s["law"] == law and s["article"] == article for s in result["sources"])


class Base(unittest.TestCase):
    def assert_answers_with(self, result, golds):
        """golds: [(법 이름, 조 번호, 파일 이름)]"""
        self.assertEqual(result["kind"], "answer", f"답변 보류가 나왔다: {result}")
        for law, article, _doc in golds:
            self.assertTrue(has_source(result, law, article),
                            f"출처에 {law} {article} 가 없다. 나온 출처: "
                            f"{[(s['law'], s['article']) for s in result['sources']]}")
        # 시행 예정 조항이면 표시가 있어야 한다
        for law, article, doc in golds:
            meta = ARTICLES[(doc, article)]
            if meta["pending"]:
                src = next(s for s in result["sources"] if s["law"] == law and s["article"] == article)
                self.assertTrue(src["pending"], f"{law} {article} 는 「시행 예정」 조항인데 표시가 없다")
                for d in meta["pending_dates"]:
                    self.assertIn(d, src["pending_dates"], f"{law} {article} 의 예정일 {d} 가 없다")

    def assert_withheld(self, result):
        self.assertEqual(result["kind"], "withheld", f"「답변 보류」가 아니다: {result}")
        self.assertEqual(result["sources"], [], "답변 보류인데 출처가 붙었다")
        self.assertEqual((result.get("text") or "").strip(), "", "답변 보류인데 답 본문이 있다")


# ---------------------------------------------------------------------------
# 1. eval/questions_laws.jsonl — 질문마다 테스트 하나 (gold 있음 / 없음 / 시행 예정)
# ---------------------------------------------------------------------------
class EvalQuestions(Base):
    pass


def _law_name(doc):
    # 법 이름은 index.py 가 laws/ 파일 첫 줄에서 읽은 값과 같아야 한다
    for (source, _article), meta in ARTICLES.items():
        if source == doc:
            return meta["law"]
    raise KeyError(doc)


def _make_test(row):
    golds = [(_law_name(g["doc"]), g["article"], g["doc"]) for g in row["gold"]]

    def test(self):
        result = ask(row["question"])
        if golds:
            self.assert_answers_with(result, golds)
        else:
            self.assert_withheld(result)

    pending = any(ARTICLES[(d, a)]["pending"] for _l, a, d in golds)
    kind = "보류" if not golds else ("시행예정" if pending else "근거")
    test.__doc__ = f"{row['id']} [{row['type']}/{kind}] {row['question']}"
    return f"test_{row['id']}_{row['type']}_{kind}", test


for _row in (json.loads(line) for line in open(EVAL, encoding="utf-8") if line.strip()):
    _name, _fn = _make_test(_row)
    setattr(EvalQuestions, _name, _fn)


# ---------------------------------------------------------------------------
# 2. spec.md 4. 테스트 시나리오 T1~T5 (엔진이 맡는 것만. T6~T10 은 화면·서버 쪽이라 여기서 안 다룬다)
# ---------------------------------------------------------------------------
LAW_EQ = "남녀고용평등과 일ㆍ가정 양립 지원에 관한 법률"


class SpecScenarios(Base):
    def test_T1_육아휴직_1_2주는_제19조를_근거로_답한다(self):
        result = ask("육아휴직 1~2주만 쓸 수 있나요?")
        self.assert_answers_with(result, [(LAW_EQ, "제19조", "L2_남녀고용평등법.md")])

    def test_T2_난임치료휴가는_제18조의3_시행예정_2026_11_26이_보인다(self):
        result = ask("난임치료휴가는 며칠이고 그중 며칠이 유급인가요?")
        self.assert_answers_with(result, [(LAW_EQ, "제18조의3", "L2_남녀고용평등법.md")])
        src = next(s for s in result["sources"] if s["article"] == "제18조의3")
        self.assertTrue(src["pending"])
        self.assertIn("2026-11-26", src["pending_dates"])
        self.assertIn("6일", result["text"])
        self.assertIn("4일", result["text"])

    def test_T3_올해_최저임금은_답변_보류(self):
        self.assert_withheld(ask("올해 최저임금은?"))

    def test_T4_앞_질문을_이어서_이해한다(self):
        q1 = "난임치료휴가는 며칠이고 그중 며칠이 유급인가요?"
        first = ask(q1)
        followup = ask("그럼 그중 며칠이 유급이에요?", history=[{"question": q1, "result": first}])
        self.assertEqual(followup["kind"], "answer", f"되묻기에 답변 보류가 나왔다: {followup}")
        self.assertTrue(has_source(followup, LAW_EQ, "제18조의3"))
        self.assertIn("4일", followup["text"])

    def test_T5_앞_맥락과_무관한_새_질문은_끌려가지_않는다(self):
        q1 = "난임치료휴가는 며칠이고 그중 며칠이 유급인가요?"
        first = ask(q1)
        second = ask("올해 최저임금은?", history=[{"question": q1, "result": first}])
        self.assert_withheld(second)


if __name__ == "__main__":
    unittest.main(verbosity=2)
