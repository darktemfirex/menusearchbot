"""서버 테스트(API 호출 없음: 엔진 자리에 가짜 answer 함수를 끼운다).
실행: python -m unittest tests_app.test_server -v
"""
import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request

LAB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(LAB, "tools"))

import server  # noqa: E402

FAKE = {"kind": "answer", "text": "가짜 답", "sources": [
    {"kind": "screen", "id": "70-5004", "name": "업무마감 등록", "detail": "물류센터 > 물류재고 > 물류재고조사"}]}


def start(answer_fn):
    httpd = server.make_server(answer_fn, port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def post(httpd, payload):
    port = httpd.server_address[1]
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/ask", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=10)
        return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

        def fake(q, history=None):
            self.calls.append((q, history))
            return FAKE
        self.httpd = start(fake)

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def test_로컬_127_0_0_1_에만_연결한다(self):
        self.assertEqual(self.httpd.server_address[0], "127.0.0.1")

    def test_질문이_오면_엔진_결과를_그대로_돌려준다(self):
        status, body = post(self.httpd, {"question": "업무마감 화면은?", "history": []})
        self.assertEqual(status, 200)
        self.assertEqual(body, FAKE)
        self.assertEqual(self.calls[0][0], "업무마감 화면은?")

    def test_빈_질문과_공백_질문은_400이고_엔진을_부르지_않는다(self):
        for q in ["", "   ", "\n\t "]:
            status, body = post(self.httpd, {"question": q})
            self.assertEqual(status, 400)
            self.assertIn("error", body)
        self.assertEqual(self.calls, [])

    def test_앞_대화를_엔진에_넘긴다(self):
        hist = [{"question": "앞", "result": FAKE}]
        post(self.httpd, {"question": "뒤", "history": hist})
        self.assertEqual(self.calls[0][1], hist)

    def test_엔진이_예외를_내면_500과_안내_문구(self):
        def boom(q, history=None):
            raise RuntimeError("secret-internal-detail")
        h = start(boom)
        try:
            status, body = post(h, {"question": "q"})
        finally:
            h.shutdown()
            h.server_close()
        self.assertEqual(status, 500)
        self.assertEqual(body["error"], "잠시 후 다시 시도해 주세요")
        self.assertNotIn("secret-internal-detail", json.dumps(body))

    def _req(self, method, path, origin=None):
        port = self.httpd.server_address[1]
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method)
        if origin:
            req.add_header("Origin", origin)
        return urllib.request.urlopen(req, timeout=10)

    def test_상태_확인_주소가_ok를_돌려준다(self):
        r = self._req("GET", "/api/health")
        self.assertEqual(json.load(r), {"ok": True})

    def test_허용한_출처에만_접속을_허용한다(self):
        ok = self._req("GET", "/api/health", origin="https://darktemfirex.github.io")
        self.assertEqual(ok.headers["Access-Control-Allow-Origin"], "https://darktemfirex.github.io")
        other = self._req("GET", "/api/health", origin="https://evil.example")
        self.assertIsNone(other.headers["Access-Control-Allow-Origin"])

    def test_사전확인_OPTIONS는_허용_출처에만_헤더를_준다(self):
        r = self._req("OPTIONS", "/api/ask", origin="https://darktemfirex.github.io")
        self.assertEqual(r.status, 204)
        self.assertEqual(r.headers["Access-Control-Allow-Private-Network"], "true")
        self.assertIn("POST", r.headers["Access-Control-Allow-Methods"])
        r2 = self._req("OPTIONS", "/api/ask", origin="https://evil.example")
        self.assertIsNone(r2.headers["Access-Control-Allow-Origin"])

    def test_터널로_들어온_요청도_암호_없이_처리한다(self):
        """Host 가 터널 주소여도(Tailscale Funnel 등) 질문을 처리한다. 허용 출처 제한(CORS)만 둔다."""
        req = urllib.request.Request(f"http://127.0.0.1:{self.httpd.server_address[1]}/api/ask",
                                     data=json.dumps({"question": "q"}).encode(),
                                     headers={"Content-Type": "application/json", "Host": "pc.example.ts.net"})
        self.assertEqual(urllib.request.urlopen(req, timeout=10).status, 200)

    def test_화면이_열린다(self):
        port = self.httpd.server_address[1]
        r = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10)
        self.assertEqual(r.status, 200)
        self.assertIn("text/html", r.headers["Content-Type"])

    def test_화면_응답에_API_키가_없다(self):
        key = server.load_key_or_none()
        port = self.httpd.server_address[1]
        html = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10).read().decode("utf-8")
        if key:
            self.assertNotIn(key, html)
        self.assertNotIn("AXROUTER", html)


class BindAddress(unittest.TestCase):
    def test_PORT가_없으면_로컬_전용_8765(self):
        self.assertEqual(server.bind_address({}), ("127.0.0.1", 8765))

    def test_PORT가_있으면_밖에서_접속되도록_0_0_0_0(self):
        self.assertEqual(server.bind_address({"PORT": "8080"}), ("0.0.0.0", 8080))

    def test_PORT가_숫자가_아니면_로컬_기본값(self):
        self.assertEqual(server.bind_address({"PORT": "abc"}), ("127.0.0.1", 8765))


class StartupChecks(unittest.TestCase):
    def test_store가_없으면_index_py_안내(self):
        msg = server.startup_problem(key="k", store_exists=False)
        self.assertIn("python3 tools/index.py", msg)

    def test_키가_없으면_키_안내(self):
        msg = server.startup_problem(key=None, store_exists=True)
        self.assertIn("AXROUTER_API_KEY", msg)

    def test_둘_다_있으면_문제없음(self):
        self.assertIsNone(server.startup_problem(key="k", store_exists=True))

    def test_안내문에_키_값이_들어가지_않는다(self):
        msg = server.startup_problem(key=None, store_exists=False)
        self.assertNotIn("sk-", msg)


if __name__ == "__main__":
    unittest.main(verbosity=2)

