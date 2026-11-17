"""브라우저 검색 모드용 데이터: data/search_data.xlsx → tools/web/data.json

검색 서버가 없는 정적 주소(GitHub Pages 등)에서 화면이 이 파일로 직접 검색합니다.
엑셀을 바꿨다면 python3 tools/export_web_data.py 를 다시 실행해 주세요.
(임베딩 벡터와 API 키는 들어가지 않습니다.)
"""
import json
import os

from index import LAB, load_items

OUT = os.path.join(LAB, "tools", "web", "data.json")


def main():
    # k: s=화면 · i=인터페이스, i: ID, n: 이름, d: 메뉴 경로 또는 연계 상세
    rows = [{"k": "s" if it["meta"]["kind"] == "screen" else "i",
             "i": it["meta"]["id"], "n": it["meta"]["name"], "d": it["meta"]["detail"]} for it in load_items()]
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(rows)}행 저장: {OUT}")


if __name__ == "__main__":
    main()
