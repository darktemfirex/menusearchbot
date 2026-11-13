"""같은 질문을 AI에게 법을 주는 방법만 바꿔 나란히 보여 줍니다.

  ① 그냥 묻기     아무것도 안 주고 질문만 · AI가 학습한 데이터로 답함
  ② 통째로 넣기   법 네 개 전문(약 18만 토큰)을 질문과 함께 · --all 을 붙일 때만
  ③ RAG          laws/ 에서 조항을 찾아(뜻 검색 20개 → 리랭킹 5개) 그 조항만 보고 답함
                 출처는 코드가 붙이고, 답하는 조항이 없으면 보류
  ※ claude-haiku-5-5 는 한 번에 100만 토큰까지 받습니다. 넘으면 「context window 초과」로 거절합니다.

사용:
  python3 tools/rag_vs_plain.py "아이 방학 때 육아휴직 1~2주만 쓸 수 있나요?"
  python3 tools/rag_vs_plain.py "질문1" "질문2"     # 따옴표 하나가 질문 하나
  python3 tools/rag_vs_plain.py --all "질문"        # ② 통째로 넣기도 같이(느리고 비쌈)
  python3 tools/rag_vs_plain.py                     # 물어볼 질문을 입력받습니다

키: 실습 폴더 .env 의 AXROUTER_API_KEY 하나로 임베딩과 답변을 모두 부릅니다.
검색 부품(자르기·임베딩·리랭킹)은 search_compare.py 것을 그대로 씁니다.
"""
import json
import os
import sys
import time
import urllib.request

from search_compare import CACHE, LAB, RERANK_MODEL, chat, cos, embed, load_chunks, load_key, rerank, ssl_ctx


def doc_vectors(chunks, key):
    # 조항 임베딩은 처음 한 번만 만들고 .cache 에 둔다(search_compare.py와 같은 파일)
    if os.path.exists(CACHE):
        return json.load(open(CACHE))
    print(f"조항 {len(chunks)}개를 임베딩하는 중(처음 한 번, 몇 초)…")
    vecs = embed([c["text"] for c in chunks], key)
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump(vecs, open(CACHE, "w"))
    return vecs


def plain(q, key):
    return chat(f"{q}\n\n세 문장 안으로 답해 줘.", key).strip()


def stuff_all(q, key):
    # 검색 없이 법 네 개 전문을 통째로 넣는다. 걸린 시간과 넣은 토큰 수를 같이 돌려준다
    folder = os.path.join(LAB, "laws")
    laws = "\n\n".join(open(os.path.join(folder, n), encoding="utf-8").read()
                       for n in sorted(os.listdir(folder)) if n.endswith(".md"))
    body = json.dumps({"model": RERANK_MODEL, "max_tokens": 2000, "messages": [{"role": "user", "content":
           f"아래 법령만 근거로 질문에 세 문장 안으로 답하고, 근거 조항을 적어. 「시행 예정」 표시가 있으면 언제부터인지 말해.\n\n"
           f"질문: {q}\n\n{laws}"}]}).encode()
    req = urllib.request.Request("https://axrouter.ai/v1/chat/completions", data=body,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    t = time.time()
    res = json.load(urllib.request.urlopen(req, timeout=300, context=ssl_ctx()))
    used = res.get("usage", {}).get("prompt_tokens", 0)
    return (res["choices"][0]["message"]["content"] or "").strip(), time.time() - t, used


def rag(q, chunks, doc_vecs, key):
    qv = embed([q], key)[0]
    sem = [cos(qv, v) for v in doc_vecs]
    picked = rerank(chunks, sem, q, key)
    if not picked:
        return "답변 보류 · laws/ 에 이 질문에 답하는 조항이 없습니다.", []
    context = "\n\n".join(chunks[i]["text"] for i in picked)
    answer = chat(f"아래 조항만 근거로 질문에 세 문장 안으로 답해. 조항에 없는 내용은 말하지 마. "
                  f"「시행 예정」 표시가 있으면 언제부터인지 꼭 말해.\n\n질문: {q}\n\n{context}", key).strip()
    # 출처는 AI가 쓰지 않고 코드가 붙인다(찾은 조항 그대로)
    return answer, [f"{chunks[i]['law']} {chunks[i]['article']}({chunks[i]['title']})" for i in picked[:3]]


def main():
    args = [a for a in sys.argv[1:] if a.strip()]
    with_all = "--all" in args  # 통째로 넣기(②)는 느리고 비싸서 켤 때만
    qs = [a for a in args if a != "--all"] or [input("질문: ").strip()]
    key = load_key()
    chunks = load_chunks()
    doc_vecs = doc_vectors(chunks, key)
    for q in qs:
        print(f"\n■ 질문: {q}")
        t = time.time()
        a = plain(q, key)
        print(f"\n  ① 그냥 묻기  ({time.time() - t:.0f}초)")
        print("   ", a.replace("\n", "\n    "))
        if with_all:
            try:
                a, sec, used = stuff_all(q, key)
                print(f"\n  ② 통째로 넣기  ({sec:.0f}초 · 넣은 토큰 {used:,})")
                print("   ", a.replace("\n", "\n    "))
            except Exception as e:  # 너무 길면 모델이 거절한다
                print(f"\n  ② 통째로 넣기 → 실패: {e}")
        t = time.time()
        answer, sources = rag(q, chunks, doc_vecs, key)
        print(f"\n  ③ RAG  ({time.time() - t:.0f}초 · 넣은 조항 5개)")
        print("   ", answer.replace("\n", "\n    "))
        for s in sources:
            print(f"    출처: {s}")


if __name__ == "__main__":
    main()
