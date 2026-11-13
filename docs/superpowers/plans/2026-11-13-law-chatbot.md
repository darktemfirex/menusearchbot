# 법령 챗봇 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (이 세션에서 직접, TDD로 하나씩). Steps use `- [ ]`.

**Goal:** `index.py`·`ask.py`를 엔진으로 써서 근거 조항을 붙여 답하고 근거가 없으면 「답변 보류」하는 로컬 웹 챗봇을 만든다.

**Architecture:** `tools/chatbot.py`(엔진 래퍼: 되묻기 합치기 + 검색·리랭킹·답 + 출처 조립) → `tools/server.py`(표준 라이브러리 HTTP 서버, 127.0.0.1, 정적 화면 + `POST /api/ask`) → `tools/web/index.html`(시안 A 화면). 대화 기록은 브라우저가 들고 있다가 질문마다 서버로 보낸다(서버는 저장하지 않음).

**Tech Stack:** Python 표준 라이브러리(unittest, http.server), 순수 HTML/CSS/JS.

**Spec:** `spec.md`

## Global Constraints

- 키는 `.env`의 `AXROUTER_API_KEY` 그대로(`index.load_key`). 서버에서만 쓰고 화면·로그로 내보내지 않는다.
- 서버는 `127.0.0.1`에만 연결. 서버 스크립트는 `tools/` 아래, 한 줄로 실행.
- 출처는 AI가 아니라 코드가 붙인다(리랭킹이 고른 조항의 meta 그대로).
- 429는 20초 쉬었다 재시도(엔진 `ask.chat`/`index.embed`가 이미 함). 그 외 오류는 「잠시 후 다시 시도해 주세요」.
- 노란색 금지. 로딩 표시 있음. 빈/공백 입력은 전송하지 않음.
- `tests/`는 수정하지 않는다. 추가 테스트는 `tests_app/`에 둔다.
- `index.py`·`ask.py`·`laws/`는 변경하지 않는다.

## Review Focus

- 공백만 있는 질문이 서버로 와도 400으로 거절(화면 검사만 믿지 않음).
- 앞 질문이 있을 때 모델 되묻기 재작성이 실패해도 원 질문으로 계속 진행.
- 서버가 보내는 JSON에 키 문자열이 없다.
- 엔진 예외 시 서버가 500 + 안내 문구 JSON을 돌려주고 죽지 않는다.
- 사용자 입력이 화면에서 HTML로 해석되지 않는다(textContent 사용).

---

### Task 1: 엔진 `chatbot.answer`

**Files:** Create `tools/chatbot.py` · Test `tests/test_eval.py`(기존, 수정 금지)

**Interfaces:** Produces `answer(question: str, history: list|None=None) -> {"kind","text","sources"}`, `sources[i] = {"law","article","title","pending","pending_dates"}`.

- [ ] Step 1: 테스트는 이미 있음(19개 빨강). 실행해 `ModuleNotFoundError` 확인.
- [ ] Step 2: `chatbot.py` 구현 — 키·store를 한 번만 읽어 캐시; `history`가 있으면 모델로 단독 질문으로 재작성(무관하면 그대로); `ask.search`→`ask.rerank`; 0개면 withheld; 아니면 `ask.answer` + meta로 sources 조립.
- [ ] Step 3: `python -m unittest tests.test_eval -v` → 통과 수 확인. 실패하는 질문은 원인 확인(엔진은 안 고침; 재작성 프롬프트만 조정).

### Task 2: 서버 `tools/server.py`

**Files:** Create `tools/server.py` · Test `tests_app/test_server.py`

**Interfaces:** Consumes `chatbot.answer`. Produces `make_app(answer_fn) -> http.server.HTTPServer subclass handler`; `POST /api/ask` body `{"question","history"}` → 200 result JSON / 400 `{"error"}` / 500 `{"error":"잠시 후 다시 시도해 주세요"}`; `GET /` → index.html.

- [ ] Step 1: 테스트(스텁 answer_fn, 실제 서버를 포트 0으로 띄움): 빈/공백 → 400, 정상 → 결과 그대로, 예외 → 500+안내, 응답 본문에 키 값 없음, `127.0.0.1` 바인딩.
- [ ] Step 2: 실패 확인 → 구현 → 통과 확인.
- [ ] Step 3: `main()`: 시작 전 키·store 확인(없으면 spec T7/T8 안내로 종료, 키 값 출력 금지), 브라우저 자동 열기.

### Task 3: 화면 `tools/web/index.html`

**Files:** Create `tools/web/index.html` · Test `tests_app/test_ui.py`

- [ ] Step 1: 테스트: 노란 계열 색상(#ff0/#ffd/yellow 등) 없음, 키/`AXROUTER` 문자열 없음, `textContent` 사용, 예시 질문 3개(T1~T3), 입력 비면 전송 막는 로직 문자열 존재.
- [ ] Step 2: 구현: 보라 말풍선, 스티커 출처(법·조·제목), 시행 예정일 배지, 분홍 점선 「답변 보류」 카드, 로딩 점, 예시 버튼, 오류 시 안내 말풍선.
- [ ] Step 3: 서버 띄워 브라우저로 확인.

### Self-Review
spec §3 1~9 → Task1(3·4·5·6), Task2(1·2·7), Task3(8·9). 시안 파일 없음 → spec 설명 기준으로 구현.
