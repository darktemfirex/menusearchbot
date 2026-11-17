"""메뉴찾기 엔진: ask.py 의 검색·리랭킹·답변을 불러 쓰고, 대화 이어가기와 출처 조립만 더한다.

    from chatbot import answer
    answer(question, history=None) -> {"kind": "answer"|"withheld", "text": str, "sources": [...]}
"""
import ask as engine
from index import load_key

_state = {}


def _ready():
    if not _state:
        _state["key"] = load_key()
        _state["records"] = engine.load_store()
    return _state["key"], _state["records"]


def _standalone(question, history, key):
    """앞 질문이 있으면 되묻기를 앞 맥락과 합쳐 혼자 읽어도 되는 질문 하나로 바꾼다."""
    if not history:
        return question
    turns = "\n".join(f"- {h['question']}" for h in history[-3:])
    prompt = (f"앞 질문들:\n{turns}\n\n새 질문: {question}\n\n"
              "새 질문이 앞 질문을 이어서 묻는 것(지시어·생략이 있어 앞 맥락이 있어야 이해됨)이면, "
              "앞 맥락을 넣어 혼자서도 이해되는 질문 한 문장으로 다시 써. "
              "앞 질문과 무관한 새 주제이면 새 질문을 한 글자도 바꾸지 말고 그대로 출력해. "
              "다시 쓴 질문 한 문장만 출력해.")
    try:
        return engine.chat(prompt, key).strip() or question
    except Exception:
        return question


def _source(meta):
    return {"kind": meta["kind"], "id": meta["id"], "name": meta["name"], "detail": meta["detail"]}


def answer(question, history=None):
    key, records = _ready()
    q = _standalone(question, history, key)
    picked = engine.rerank(q, engine.search(q, records, key), key)
    if not picked:
        return {"kind": "withheld", "text": "", "sources": []}
    text = engine.answer(q, picked, key)
    return {"kind": "answer", "text": text, "sources": [_source(r["meta"]) for r in picked]}  # 출처는 코드가 붙인다
