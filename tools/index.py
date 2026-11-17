"""RAG 저장 단계: data/search_data.xlsx 의 화면·인터페이스 목록을 한 줄씩 벡터와 함께 store/ 에 저장합니다.

  1. data/search_data.xlsx 를 읽어 행(화면 또는 연계 인터페이스) 하나씩 자르기 (표준 라이브러리만 사용)
  2. 행마다 메타데이터: 구분(화면/인터페이스) · ID · 이름 · 메뉴 경로/연계 상세
  3. 행 글을 벡터로: AXRouter gemini/gemini-embedding-2 (64개씩, 429면 20초 쉬었다 재시도)
  4. 행 글 · 벡터 · 메타데이터를 한 묶음으로 store/index.json 에 저장

사용:  python3 tools/index.py
키:    프로젝트 폴더 .env 의 AXROUTER_API_KEY (또는 같은 이름의 환경변수)
"""
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_URL = "https://axrouter.ai/v1"
MODEL = "gemini/gemini-embedding-2"
BATCH = 64
RETRY_WAIT = 20
DATA = os.path.join(LAB, "data", "search_data.xlsx")
STORE = os.path.join(LAB, "store", "index.json")

_M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def load_key():
    k = os.environ.get("AXROUTER_API_KEY")
    p = os.path.join(LAB, ".env")
    if not k and os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            if line.strip().startswith("AXROUTER_API_KEY="):
                k = line.split("=", 1)[1].strip().strip('"')
    if not k:
        sys.exit("키가 없습니다. 프로젝트 폴더 .env에 AXROUTER_API_KEY=... 를 넣어 주세요.")
    return k


def ssl_ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


# 1. xlsx 읽기: 첫 시트의 행마다 {열 글자: 값} 사전으로 돌려준다
def read_xlsx(path):
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(_M + "si"):
                # 후리가나(rPh) 글은 빼고 본문(t, r/t)만 이어 붙인다
                parts = si.findall(_M + "t") + si.findall(_M + "r/" + _M + "t")
                shared.append("".join(t.text or "" for t in parts))
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    rows = []
    for row in sheet.iter(_M + "row"):
        cells = {}
        for c in row.findall(_M + "c"):
            col = re.match(r"[A-Z]+", c.get("r")).group()
            v = c.find(_M + "v")
            if c.get("t") == "inlineStr":
                text = "".join(t.text or "" for t in c.iter(_M + "t"))
            elif v is None:
                continue
            elif c.get("t") == "s":
                text = shared[int(v.text)]
            else:
                text = v.text or ""
            cells[col] = text.strip()
        rows.append(cells)
    return rows


def _plain(s):
    """「F:파일연계」「07:빅데이터플랫폼」처럼 앞에 붙은 코드 번호를 뗀다."""
    return re.sub(r"^[A-Za-z0-9]{1,2}:", "", s or "").strip()


# 2. 행 하나를 검색용 글과 메타데이터로 바꾼다
# 열: A 번호 · B 구분(화면/연계) · C ID · D 이름 · E 연계방식 · F 프로그램종류 · G 실행주기 · H 수행시간 · I 메뉴경로(화면)/대상시스템(연계)
def make_item(row):
    kind, id_, name = row.get("B", ""), row.get("C", ""), row.get("D", "")
    if not (kind and id_ and name):
        return None
    biz = f" | 업무: {row['업무']}" if row.get("업무") else ""   # 물류·수발주처럼 업무 구분이 있으면 검색 글에 넣는다
    if kind == "화면":
        path = row.get("I", "")
        return {
            "text": f"[화면] {name} (화면ID {id_}){biz} | 메뉴 경로: {path} > {name}",
            "meta": {"kind": "screen", "id": id_, "name": name, "detail": path},
        }
    method, prog, cycle, when = _plain(row.get("E")), _plain(row.get("F")), _plain(row.get("G")), row.get("H", "").replace("\r\n", " ")
    system = _plain(row.get("I"))
    when_txt = f" {when}" if when else ""
    detail = f"인터페이스 · {system} · {method} · {prog} · 주기 {cycle}{when_txt}"
    return {
        "text": f"[인터페이스] {name} (인터페이스ID {id_}){biz} | 대상 시스템: {system} | 연계방식: {method} | "
                f"프로그램 종류: {prog} | 실행주기: {cycle}{when_txt}",
        "meta": {"kind": "interface", "id": id_, "name": name, "detail": detail},
    }


_HEADERS = {"번호": "A", "구분": "B", "인터페이스ID": "C", "인터페이스명": "D", "연계방식": "E",
            "프로그램종류": "F", "실행주기": "G", "배치수행시간": "H", "설명": "I", "업무": "업무"}


def normalize(rows):
    """머리글 이름으로 열을 찾아 make_item 이 쓰는 열 글자(A~I)로 맞춘다.
    '업무' 열이 끼어 있어 열 위치가 밀린 엑셀도 같은 방식으로 읽는다."""
    header = {col: _HEADERS.get(re.sub(r"\s+", "", name)) for col, name in rows[0].items()}
    return [{header[c]: v for c, v in r.items() if header.get(c)} for r in rows[1:]]


def load_items(path=DATA):
    items = [make_item(r) for r in normalize(read_xlsx(path))]
    return [it for it in items if it]


# 3. 64개씩 임베딩, 429면 20초 쉬었다 다시
def embed(texts, key):
    ctx = ssl_ctx()
    vecs = []
    for i in range(0, len(texts), BATCH):
        body = json.dumps({"model": MODEL, "input": texts[i:i + BATCH]}).encode()
        tries = 0
        while True:
            req = urllib.request.Request(f"{BASE_URL}/embeddings", data=body,
                                         headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
            try:
                data = json.load(urllib.request.urlopen(req, timeout=120, context=ctx))["data"]
                break
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    print(f"  429 · {RETRY_WAIT}초 쉬었다 다시 보냅니다…", file=sys.stderr)
                    time.sleep(RETRY_WAIT)
                    continue
                tries += 1  # 5xx 는 두세 번 다시 시도, 그 외(400·401 등)는 바로 올린다
                print(f"  embed HTTP {e.code} (시도 {tries}/3)", file=sys.stderr)
                if e.code < 500 or tries >= 3:
                    raise
                time.sleep(2 * tries)
            except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError, KeyError) as e:
                tries += 1  # 연결 끊김·시간 초과·응답 형식 이상(키는 로그에 넣지 않는다)
                print(f"  embed {type(e).__name__} (시도 {tries}/3)", file=sys.stderr)
                if tries >= 3:
                    raise
                time.sleep(2 * tries)
        vecs += [d["embedding"] for d in sorted(data, key=lambda x: x["index"])]
        print(f"  임베딩 {min(i + BATCH, len(texts))}/{len(texts)}")
    return vecs


def main():
    key = load_key()
    items = load_items()
    if not items:
        sys.exit("data/search_data.xlsx 에서 화면·인터페이스 행을 찾지 못했습니다.")
    print(f"{len(items)}개 행을 임베딩합니다({MODEL}).")
    vecs = embed([it["text"] for it in items], key)
    # 4. 글 · 벡터 · 메타데이터를 한 묶음으로 저장
    records = [{"id": n, "text": it["text"], "vector": v, "meta": it["meta"]}
               for n, (it, v) in enumerate(zip(items, vecs))]
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    json.dump({"model": MODEL, "dim": len(vecs[0]), "count": len(records), "records": records},
              open(STORE, "w", encoding="utf-8"), ensure_ascii=False)
    screens = sum(1 for it in items if it["meta"]["kind"] == "screen")
    print(f"\n저장: {STORE}")
    print(f"행 수: {len(items)} · 화면 {screens} · 인터페이스 {len(items) - screens}")


if __name__ == "__main__":
    main()
