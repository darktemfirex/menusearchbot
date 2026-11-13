"""같은 질문을 네 가지 방법으로 찾아 나란히 비교합니다.

  ① 키워드 검색(BM25)   글자가 겹치면 찾음
  ② 뜻 검색(임베딩)      뜻이 가까우면 찾음
  ③ 하이브리드           ①과 ②의 순위를 합침(RRF)
  ④ 뜻 검색 + 리랭킹     ②로 20개를 뽑고 AI가 다시 읽어 5개를 고름

사용:
  python3 tools/search_compare.py "아이 방학 때 육아휴직 1주만 쓸 수 있나요?"
  python3 tools/search_compare.py "질문1" "질문2" "질문3"   # 따옴표 하나가 질문 하나
  python3 tools/search_compare.py            # 물어볼 질문을 입력받습니다

키: 실습 폴더의 .env 파일에 AXROUTER_API_KEY=... 한 줄 (또는 같은 이름의 환경변수)
파이썬 기본 라이브러리만 씁니다(설치할 것 없음).
"""
import json
import math
import os
import re
import ssl
import sys
import urllib.request
from collections import Counter

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.environ.get("EMBED_MODEL", "gemini/gemini-embedding-2")
RERANK_MODEL = os.environ.get("RERANK_MODEL", "claude-haiku-5-5")
WITHHOLD = 0.65  # 뜻 검색 1등 점수가 이보다 낮으면 보류 후보(4교시 실측 기준)
CACHE = os.path.join(LAB, ".cache", "emb_" + MODEL.replace("/", "_") + ".json")


def load_key():
    k = os.environ.get("AXROUTER_API_KEY")
    p = os.path.join(LAB, ".env")
    if not k and os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            if line.strip().startswith("AXROUTER_API_KEY="):
                k = line.split("=", 1)[1].strip().strip('"')
    if not k:
        sys.exit("키가 없습니다. 실습 폴더 .env에 AXROUTER_API_KEY=... 를 넣어 주세요.")
    return k


# 조항 단위로 자르기: 「## 제N조(제목)」마다 한 조각, 앞에 법 이름을 붙인다
def load_chunks():
    chunks = []
    folder = os.path.join(LAB, "laws")
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".md"):
            continue
        text = open(os.path.join(folder, name), encoding="utf-8").read()
        law = text.splitlines()[0].lstrip("# ").strip()
        for part in re.split(r"(?m)^(?=## 제\d+조)", text):
            m = re.match(r"## (제\d+조(?:의\d+)?)\(([^)]*)\)", part)
            if m:
                chunks.append({"law": law, "article": m.group(1), "title": m.group(2), "text": f"[{law}] " + part.strip()})
    return chunks


# ---------- 키워드 검색(BM25) ----------
def toks(s):
    words = re.sub(r"[^\w]", " ", s.lower()).split()
    # 한국어는 조사가 붙어서(「휴가를」「휴가는」) 어절이 안 맞으니 두 글자씩도 센다
    return words + [w[i:i + 2] for w in words for i in range(max(1, len(w) - 1))]


def bm25(chunks, q, k1=1.5, b=0.75):
    tfs = [Counter(toks(c["text"])) for c in chunks]
    lens = [sum(t.values()) for t in tfs]
    avg = sum(lens) / len(lens)
    df = Counter(w for t in tfs for w in t)
    n = len(chunks)
    out = []
    for t, ln in zip(tfs, lens):
        s = 0.0
        for w in toks(q):
            if w in t:
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                s += idf * t[w] * (k1 + 1) / (t[w] + k1 * (1 - b + b * ln / avg))
        out.append(s)
    return out


# ---------- 의미 검색(임베딩 + 코사인 유사도) ----------
def ssl_ctx():
    try:
        import certifi  # 있으면 쓴다(맥에서 인증서 오류 방지)
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def embed(texts, key):
    ctx = ssl_ctx()
    vecs = []
    for i in range(0, len(texts), 64):
        body = json.dumps({"model": MODEL, "input": texts[i:i + 64]}).encode()
        req = urllib.request.Request("https://axrouter.ai/v1/embeddings", data=body,
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        data = json.load(urllib.request.urlopen(req, timeout=120, context=ctx))["data"]
        vecs += [d["embedding"] for d in sorted(data, key=lambda x: x["index"])]
    return vecs


def cos(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


# ---------- 하이브리드: 두 검색의 순위를 합친다(RRF) ----------
def rrf(*score_lists, k=60):
    out = [0.0] * len(score_lists[0])
    for scores in score_lists:
        order = sorted(range(len(scores)), key=lambda i: -scores[i])
        for rank, i in enumerate(order):
            out[i] += 1 / (k + rank + 1)
    return out


# ---------- 리랭킹: 뜻 검색 20개를 AI가 질문과 나란히 놓고 다시 고른다 ----------
def chat(prompt, key):
    # 답 전에 숨은 추론 토큰을 쓰는 모델이 있어 max_tokens를 넉넉히 둔다
    body = json.dumps({"model": RERANK_MODEL, "max_tokens": 2000,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://axrouter.ai/v1/chat/completions", data=body,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=120, context=ssl_ctx()))["choices"][0]["message"]["content"] or ""


def rerank(chunks, sem, q, key, k=20):
    cand = sorted(range(len(chunks)), key=lambda i: -sem[i])[:k]
    listing = "\n\n".join(f"[{n}] {chunks[i]['text'][:700]}" for n, i in enumerate(cand))
    out = chat(f"질문: {q}\n\n아래 후보 조항 중 질문에 직접 답하는 것을 관련 높은 순서로 최대 5개 골라 번호만 쉼표로 출력해. "
               f"답하는 조항이 없으면 NONE.\n\n{listing}", key)
    if "NONE" in out.upper():
        return []
    picked = [int(x) for x in re.findall(r"\d+", out) if int(x) < len(cand)]
    return [cand[n] for n in dict.fromkeys(picked)][:5]


def label(c):
    return f"{c['law'][:8]} {c['article']}({c['title'][:10]})"


def compare(q, chunks, doc_vecs, key):
    qv = embed([q], key)[0]
    kw = bm25(chunks, q)
    sem = [cos(qv, v) for v in doc_vecs]
    hy = rrf(kw, sem)

    def top(scores, n=3):
        return sorted(range(len(chunks)), key=lambda i: -scores[i])[:n]

    print(f"\n■ 질문: {q}")
    print("  ① 키워드 검색")
    for i in top(kw):
        print(f"     {kw[i]:5.1f}  {label(chunks[i])}")
    print("  ② 뜻 검색")
    for i in top(sem):
        print(f"     {sem[i]:.3f}  {label(chunks[i])}")
    print("  ③ 하이브리드(①+② 순위 합침)")
    for i in top(hy):
        print(f"            {label(chunks[i])}")
    print("  ④ 뜻 검색 20개 → 리랭킹")
    picked = rerank(chunks, sem, q, key)
    if not picked:
        print("            AI 판단: 답하는 조항 없음 → 보류 후보")
    for i in picked[:3]:
        print(f"            {label(chunks[i])}")
    best = max(sem)
    note = "보류 후보" if best < WITHHOLD else "답할 수 있음"
    print(f"  ▶ 뜻 검색 1등 점수 {best:.3f} (기준 {WITHHOLD}) → {note}")


def main():
    qs = [a for a in sys.argv[1:] if a.strip()] or [input("질문: ").strip()]
    chunks = load_chunks()
    key = load_key()

    if os.path.exists(CACHE):  # 조항 임베딩은 처음 한 번만 만든다
        doc_vecs = json.load(open(CACHE))
    else:
        print(f"조항 {len(chunks)}개를 임베딩하는 중(처음 한 번, 몇 초)…")
        doc_vecs = embed([c["text"] for c in chunks], key)
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        json.dump(doc_vecs, open(CACHE, "w"))

    for q in qs:
        compare(q, chunks, doc_vecs, key)
    print("\n점수 단위가 다릅니다: 키워드는 겹친 글자 점수, 뜻 검색은 방향이 얼마나 같은지(1에 가까울수록 비슷).")
    print("리랭킹은 질문마다 AI를 한 번 더 부릅니다(조금 느리고 비용이 듭니다).")


if __name__ == "__main__":
    main()
