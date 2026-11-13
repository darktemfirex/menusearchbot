"""RAG 저장 단계: laws/ 법령을 조항 단위로 잘라 벡터와 함께 store/ 에 저장합니다.

  1. laws/*.md 를 「## 제N조」 하나씩 자르기
  2. 조항마다 메타데이터: 법 이름 · 조 번호 · 「시행 예정」 여부
  3. 조항 글을 벡터로: AXRouter gemini/gemini-embedding-2 (64개씩, 429면 20초 쉬었다 재시도)
  4. 조항 글 · 벡터 · 메타데이터를 한 묶음으로 store/index.json 에 저장

사용:  python3 tools/index.py
키:    실습 폴더 .env 의 AXROUTER_API_KEY (또는 같은 이름의 환경변수)
"""
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_URL = "https://axrouter.ai/v1"
MODEL = "gemini/gemini-embedding-2"
BATCH = 64
RETRY_WAIT = 20
STORE = os.path.join(LAB, "store", "index.json")


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


def ssl_ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


# 1·2. 조항 단위로 자르고 메타데이터를 붙인다
def split_articles():
    folder = os.path.join(LAB, "laws")
    items = []
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".md"):
            continue
        text = open(os.path.join(folder, name), encoding="utf-8").read()
        law = text.splitlines()[0].lstrip("# ").strip()
        for part in re.split(r"(?m)^(?=## 제\d+조)", text):
            m = re.match(r"## (제\d+조(?:의\d+)?)\(([^)]*)\)", part)
            if not m:
                continue
            body = part.strip()
            dates = sorted(set(re.findall(r"(\d{4}-\d{2}-\d{2}) 시행 예정", body)))
            items.append({
                "text": f"[{law}] " + body,
                "meta": {
                    "law": law,
                    "article": m.group(1),
                    "title": m.group(2),
                    "pending": "시행 예정" in body,  # 「시행 예정」 표시가 붙은 항이 있는 조항
                    "pending_dates": dates,
                    "source": name,
                },
            })
    return items


# 3. 64개씩 임베딩, 429면 20초 쉬었다 다시
def embed(texts, key):
    ctx = ssl_ctx()
    vecs = []
    for i in range(0, len(texts), BATCH):
        body = json.dumps({"model": MODEL, "input": texts[i:i + BATCH]}).encode()
        while True:
            req = urllib.request.Request(f"{BASE_URL}/embeddings", data=body,
                                         headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
            try:
                data = json.load(urllib.request.urlopen(req, timeout=120, context=ctx))["data"]
                break
            except urllib.error.HTTPError as e:
                if e.code != 429:
                    raise
                print(f"  429 · {RETRY_WAIT}초 쉬었다 다시 보냅니다…")
                time.sleep(RETRY_WAIT)
        vecs += [d["embedding"] for d in sorted(data, key=lambda x: x["index"])]
        print(f"  임베딩 {min(i + BATCH, len(texts))}/{len(texts)}")
    return vecs


def main():
    key = load_key()
    items = split_articles()
    if not items:
        sys.exit("laws/ 에서 조항을 찾지 못했습니다.")
    print(f"조항 {len(items)}개를 임베딩합니다({MODEL}).")
    vecs = embed([it["text"] for it in items], key)
    # 4. 글 · 벡터 · 메타데이터를 한 묶음으로 저장
    records = [{"id": n, "text": it["text"], "vector": v, "meta": it["meta"]}
               for n, (it, v) in enumerate(zip(items, vecs))]
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    json.dump({"model": MODEL, "dim": len(vecs[0]), "count": len(records), "records": records},
              open(STORE, "w", encoding="utf-8"), ensure_ascii=False)
    pending = sum(1 for it in items if it["meta"]["pending"])
    print(f"\n저장: {STORE}")
    print(f"조항 수: {len(items)} · 시행 예정 조항 수: {pending}")


if __name__ == "__main__":
    main()
