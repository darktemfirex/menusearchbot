"""메뉴찾기 봇 로컬 웹 서버(127.0.0.1 전용).

사용:  python3 tools/server.py      → 브라우저가 열린다 (http://127.0.0.1:8765)
키는 서버 안에서만 쓰고 화면·로그로 내보내지 않는다.
"""
import http.server
import json
import os
import sys
import webbrowser

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(LAB, "tools"))

from index import STORE  # noqa: E402

WEB = os.path.join(LAB, "tools", "web")
HOST, PORT = "127.0.0.1", 8765
ERROR_TEXT = "잠시 후 다시 시도해 주세요"
STATIC = {  # PWA(설치형 웹앱) 파일: 경로 → Content-Type
    "/manifest.webmanifest": "application/manifest+json; charset=utf-8",
    "/sw.js": "text/javascript; charset=utf-8",
    "/search.js": "text/javascript; charset=utf-8",
    "/data.json": "application/json; charset=utf-8",
    "/icon-192.png": "image/png",
    "/icon-512.png": "image/png",
}


def load_key_or_none():
    k = os.environ.get("AXROUTER_API_KEY")
    p = os.path.join(LAB, ".env")
    if not k and os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("AXROUTER_API_KEY="):
                    k = line.split("=", 1)[1].strip().strip('"')
    return k or None


def startup_problem(key, store_exists):
    """시작할 수 없으면 사용자에게 보일 안내를, 괜찮으면 None 을 돌려준다(키 값은 절대 넣지 않는다)."""
    if not store_exists:
        return "store/index.json 이 없습니다. 먼저 python3 tools/index.py 를 실행해 주세요."
    if not key:
        return "키가 없습니다. 프로젝트 폴더 .env 에 AXROUTER_API_KEY=... 를 넣어 주세요."
    return None


def bind_address(env):
    """로컬 실행은 127.0.0.1:8765 전용. axhub 같은 서버가 PORT 를 넣어 주면 0.0.0.0:PORT 로 연다."""
    try:
        return "0.0.0.0", int(env["PORT"])
    except (KeyError, ValueError):
        return HOST, PORT


def make_server(answer_fn, port=PORT, host=HOST):
    class Handler(http.server.BaseHTTPRequestHandler):
        def _send(self, status, body, ctype="application/json; charset=utf-8"):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path in ("/", "/index.html"):
                name = "index.html"
            elif path in STATIC:  # PWA 파일만 이름을 정해 둔 것에서 내보낸다(임의 경로 접근 불가)
                name = path.lstrip("/")
            else:
                return self._send(404, {"error": "not found"})
            with open(os.path.join(WEB, name), "rb") as f:
                body = f.read()
            ctype = "text/html; charset=utf-8" if name == "index.html" else STATIC[path]
            self._send(200, body, ctype)

        def do_POST(self):
            if self.path != "/api/ask":
                return self._send(404, {"error": "not found"})
            try:
                n = int(self.headers.get("Content-Length") or 0)
                payload = json.loads(self.rfile.read(n) or b"{}")
                question = payload.get("question")
            except (ValueError, AttributeError):
                return self._send(400, {"error": "질문을 읽을 수 없습니다"})
            if not isinstance(question, str) or not question.strip():
                return self._send(400, {"error": "질문을 입력해 주세요"})
            history = payload.get("history") or []
            try:
                self._send(200, answer_fn(question.strip(), history=history))
            except Exception as e:  # 화면이 멈추거나 비지 않게: 상세는 서버 콘솔에만(키는 포함되지 않음)
                import traceback  # 키는 요청 헤더에만 있고 예외 글에는 들어가지 않는다
                print(f"  오류: {type(e).__name__}: {e}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                self._send(500, {"error": ERROR_TEXT})

        def log_message(self, fmt, *args):
            pass

    return http.server.ThreadingHTTPServer((host, port), Handler)


def main():
    problem = startup_problem(load_key_or_none(), os.path.exists(STORE))
    if problem:
        sys.exit(problem)
    from chatbot import answer
    host, port = bind_address(os.environ)
    httpd = make_server(answer, port=port, host=host)
    print(f"메뉴찾기 봇: http://{host}:{httpd.server_address[1]}/  (끄려면 Ctrl+C)")
    if host == HOST:  # 내 PC에서만 브라우저를 연다(서버에서는 열지 않음)
        webbrowser.open(f"http://{HOST}:{httpd.server_address[1]}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
