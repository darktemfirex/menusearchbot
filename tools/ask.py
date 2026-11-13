"""RAG 검색 단계: store/ 를 읽어 질문에 답합니다(저장은 index.py).

  1. 질문을 같은 모델(gemini/gemini-embedding-2)로 임베딩 → 코사인 유사도로 가까운 조항 20개
  2. claude-haiku-5-5 가 20개를 다시 읽고 질문에 직접 답하는 조항만 최대 5개 고르기(리랭킹)
  3. 고른 조항만 보고 답하기 · 출처는 AI가 아니라 코드가 붙임
  4. 고를 조항이 없으면 「답변 보류」

사용:
  python3 tools/ask.py "육아휴직 1~2주만 쓸 수 있나요?"
  python3 tools/ask.py "질문1" "질문2"     # 따옴표 하나가 질문 하나
  python3 tools/ask.py                     # 물어볼 질문을 입력받습니다
"""
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request

from index import BASE_URL, MODEL, STORE, embed, load_key, ssl_ctx

CHAT_MODEL = "claude-haiku-5-5"
TOP_K = 20
PICK = 5


def load_store():
    if not os.path.exists(STORE):
        sys.exit("store/index.json 이 없습니다. 먼저 python3 tools/index.py 를 실행해 주세요.")
    d = json.load(open(STORE, encoding="utf-8"))
    if d["model"] != MODEL:
        sys.exit(f"store/ 는 {d['model']} 로 만들어졌습니다. 질문도 같은 모델이어야 합니다.")
    return d["records"]


def chat(prompt, key):
    # 답 전에 숨은 추론 토큰을 쓰는 모델이 있어 max_tokens를 넉넉히 둔다
    body = json.dumps({"model": CHAT_MODEL, "max_tokens": 2000,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    while True:
        req = urllib.request.Request(f"{BASE_URL}/chat/completions", data=body,
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            res = json.load(urllib.request.urlopen(req, timeout=120, context=ssl_ctx()))
            return (res["choices"][0]["message"]["content"] or "").strip()
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            time.sleep(20)


def cos(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def search(q, records, key):
    qv = embed([q], key)[0]
    scored = sorted(((cos(qv, r["vector"]), r) for r in records), key=lambda x: -x[0])
    return scored[:TOP_K]


def rerank(q, cands, key):
    listing = "\n\n".join(f"[{n}] {r['text'][:700]}" for n, (_, r) in enumerate(cands))
    out = chat(f"질문: {q}\n\n아래 후보 조항 중 질문에 직접 답하는 것을 관련 높은 순서로 최대 {PICK}개 골라 "
               f"번호만 쉼표로 출력해. 답하는 조항이 없으면 NONE 한 단어만.\n\n{listing}", key)
    if "NONE" in out.upper():
        return []
    nums = [int(x) for x in re.findall(r"\d+", out) if int(x) < len(cands)]
    return [cands[n][1] for n in dict.fromkeys(nums)][:PICK]


def answer(q, picked, key):
    context = "\n\n".join(r["text"] for r in picked)
    return chat(f"아래 조항만 근거로 질문에 세 문장 안으로 답해. 조항에 없는 내용은 말하지 마. "
                f"「시행 예정」 표시가 있으면 언제부터인지 꼭 말해.\n\n질문: {q}\n\n{context}", key)


def source(r):
    m = r["meta"]
    tag = f" · {', '.join(m['pending_dates'])} 시행 예정 포함" if m["pending"] else ""
    return f"{m['law']} {m['article']}({m['title']}){tag}"


def ask(q, records, key):
    t = time.time()
    cands = search(q, records, key)
    picked = rerank(q, cands, key)
    print(f"\n■ 질문: {q}")
    print(f"  뜻 검색 1등 점수 {cands[0][0]:.3f} · 후보 {len(cands)}개 → 리랭킹 {len(picked)}개")
    if not picked:
        print("  답변 보류 · store/ 에 이 질문에 답하는 조항이 없습니다.")
        print(f"  ({time.time() - t:.0f}초)")
        return
    print("   ", answer(q, picked, key).replace("\n", "\n    "))
    for r in picked:  # 출처는 코드가 붙인다(고른 조항 그대로)
        print(f"    출처: {source(r)}")
    print(f"  ({time.time() - t:.0f}초)")


def main():
    qs = [a for a in sys.argv[1:] if a.strip()] or [input("질문: ").strip()]
    key = load_key()
    records = load_store()
    for q in qs:
        ask(q, records, key)


if __name__ == "__main__":
    main()
