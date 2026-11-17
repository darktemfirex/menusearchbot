# 메뉴찾기 봇

찾는 화면·업무를 말하면 **메뉴 경로와 화면ID**를 알려 주는 챗봇입니다(설치형 웹앱 PWA 지원).
`data/search_data.xlsx` 의 화면·인터페이스 목록만 근거로 답하고, 목록에 없으면 「답변 보류」라고 답합니다.

필요한 것: **AXRouter API 키**(`AXROUTER_API_KEY`). 키는 저장소에 넣지 마세요.

## 0. Pages에서 내려받기

https://darktemfirex.github.io/menusearchbot/ 에서 **앱 내려받기**(`menusearchbot.zip`)를 눌러 압축을 풀고, Windows는 `run.bat`, Mac/Linux는 `sh run.sh` 를 실행합니다(Python 3.8 이상, API 키 필요).
Pages 주소(`/`)는 **앱 설치 전용 화면**입니다(챗봇은 연결돼 있지 않습니다). 설치한 앱은 `app.html` 을 열고, 서버가 없어서 이름·경로·ID로만 찾는 **브라우저 검색 모드**로 동작합니다. AI 답변은 내려받은 앱(서버 실행)에서 나옵니다.

## 1. Codespaces (설치 없이 브라우저에서)

1. 저장소 페이지에서 **Code → Codespaces → Create codespace on main**
2. 키는 미리 **Settings → Codespaces → Secrets** 에 `AXROUTER_API_KEY` 로 등록해 두면 자동으로 들어갑니다.
   키가 없으면 자동 실행된 서버가 바로 종료됩니다. 이때는 터미널에서 `AXROUTER_API_KEY=키 python3 tools/server.py` 로 직접 실행하거나, 비밀값을 등록한 뒤 Codespace 를 다시 시작하세요. 로그는 `/tmp/menusearchbot.log` 입니다.
3. 서버가 자동으로 뜨고, **포트 8765** 알림의 「브라우저에서 열기」를 누릅니다.

## 2. 내 PC에서 한 줄로

Python 3.10 이상이 필요합니다(추가 패키지 없음).

```bash
git clone https://github.com/darktemfirex/menusearchbot.git
cd menusearchbot
```

- Windows: `run.bat`
- Mac/Linux: `sh run.sh`

처음 실행하면 키를 물어보고 `.env` 에 저장합니다(`.env` 는 git 에 올라가지 않습니다).
서버가 뜨면 http://127.0.0.1:8765/ 가 열립니다.

**자동 시작(Windows):** `autostart.bat` 을 한 번 실행하면 로그인할 때마다 서버가 창 없이 뜹니다. 끄려면 `autostart.bat off`.

**휴대폰에서 이 PC 서버 쓰기(터널):** 서버는 PC 안에서만 열려 있으므로 HTTPS 터널이 필요합니다. 터널로 들어온 요청은 `.env` 의 `ACCESS_TOKEN` 이 맞아야만 처리하고, 토큰이 없으면 모두 거절합니다(내 PC 에서 직접 여는 것은 토큰이 필요 없습니다). Tailscale 을 쓰는 예: PC 에서 `tailscale funnel 8765` 를 실행해 나온 `https://…ts.net` 주소가 앱의 `DEFAULT_SERVER`(tools/web/app.html)와 같아야 합니다. 휴대폰은 `…/app.html#t=토큰` 링크로 처음 한 번 열면 토큰이 저장됩니다(또는 앱의 「접속 암호」 버튼).

**앱의 서버 자동 감지:** 설치한 앱은 열 때 AI 서버(같은 주소 → 내 PC `127.0.0.1:8765` → 고정 서버 `DEFAULT_SERVER`)를 찾습니다. 찾으면 상단에 「AI 서버 연결됨」, 못 찾으면 「브라우저 검색 모드」로 표시하고 이름·경로·ID 검색으로 동작합니다. 휴대폰은 터널(HTTPS) 서버와 접속 암호가 있어야 AI 를 쓸 수 있습니다.

## 3. Docker

```bash
docker build -t menusearchbot .
docker run --rm -p 8080:8080 -e AXROUTER_API_KEY=여기에_키 -e PORT=8080 menusearchbot
```

http://localhost:8080/ 에서 열립니다.

## 데이터를 바꿀 때(엑셀 → 검색 데이터)

`data/search_data.xlsx` 를 바꾼 뒤 검색 데이터를 다시 만듭니다.

```bash
python3 tools/index.py            # AI 검색용 store/index.json
python3 tools/export_web_data.py   # 브라우저 검색 모드용 tools/web/data.json
```

## 테스트(API 호출 없음)

```bash
python3 -m unittest tests_app.test_index tests_app.test_ui tests_app.test_server tests_app.test_pwa
```

## 알아 둘 점

- 질문마다 검색·리랭킹·답변을 서버와 API 가 처리하므로 오프라인에서는 답하지 못합니다(PWA 는 화면 껍데기만 캐시).
- PWA 설치는 HTTPS 주소 또는 `localhost` 에서만 됩니다.
- 로컬 실행은 `127.0.0.1` 에만 연결합니다. 서버 환경에서 `PORT` 가 주어지면 `0.0.0.0:PORT` 로 엽니다.
