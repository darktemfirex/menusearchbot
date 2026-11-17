"""PWA(설치형 웹앱) 파일·경로 테스트(API 호출 없음). 실행: python -m unittest tests_app.test_pwa -v"""
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

WEB = os.path.join(LAB, "tools", "web")


class PwaFiles(unittest.TestCase):
    def test_매니페스트가_설치_조건을_갖춘다(self):
        m = json.load(open(os.path.join(WEB, "manifest.webmanifest"), encoding="utf-8"))
        self.assertEqual(m["display"], "standalone")
        self.assertTrue(m["name"] and m["short_name"] and m["start_url"])
        sizes = {i["sizes"] for i in m["icons"]}
        self.assertTrue({"192x192", "512x512"} <= sizes)
        for i in m["icons"]:
            self.assertTrue(os.path.exists(os.path.join(WEB, i["src"].lstrip("/"))), i["src"])

    def test_아이콘은_PNG_파일이다(self):
        for n in (192, 512):
            self.assertEqual(open(os.path.join(WEB, f"icon-{n}.png"), "rb").read(8), b"\x89PNG\r\n\x1a\n")

    def test_화면이_매니페스트와_서비스워커를_연결한다(self):
        html = open(os.path.join(WEB, "index.html"), encoding="utf-8").read()
        self.assertIn('rel="manifest"', html)
        self.assertIn("serviceWorker.register", html)

    def test_서비스워커는_질문_API를_캐시하지_않는다(self):
        sw = open(os.path.join(WEB, "sw.js"), encoding="utf-8").read()
        self.assertIn('"/api/"', sw)
        self.assertIn('req.method !== "GET"', sw)


class PwaRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = server.make_server(lambda q, history=None: {}, port=0)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def get(self, path):
        try:
            return urllib.request.urlopen(self.base + path, timeout=10)
        except urllib.error.HTTPError as e:
            return e

    def test_PWA_파일이_알맞은_형식으로_나간다(self):
        for path, ctype in [("/manifest.webmanifest", "application/manifest+json"), ("/sw.js", "javascript"),
                            ("/icon-192.png", "image/png"), ("/icon-512.png", "image/png"),
                            ("/search.js", "javascript"), ("/data.json", "application/json")]:
            r = self.get(path)
            self.assertEqual(r.status, 200, path)
            self.assertIn(ctype, r.headers["Content-Type"], path)

    def test_정해진_파일_밖의_경로는_404(self):
        for path in ["/server.py", "/../server.py", "/index.py", "/store/index.json", "/.env"]:
            self.assertEqual(self.get(path).code, 404, path)




class LandingAndApp(unittest.TestCase):
    """주소(/)는 설치 전용 안내, 챗봇 화면은 app.html 로 나뉜다."""

    @classmethod
    def setUpClass(cls):
        cls.httpd = server.make_server(lambda q, history=None: {}, port=0)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def read(self, path):
        return urllib.request.urlopen(self.base + path, timeout=10).read().decode("utf-8")

    def test_설치_화면에는_챗봇이_연결되어_있지_않다(self):
        html = open(os.path.join(WEB, "index.html"), encoding="utf-8").read()
        self.assertIn('id="install"', html)
        self.assertIn("beforeinstallprompt", html)
        for s in ['id="chat"', "api/ask", 'id="input"', "search.js", "data.json"]:
            self.assertNotIn(s, html, s)

    def test_매니페스트는_설치된_앱의_시작_화면을_app_html로_한다(self):
        m = json.load(open(os.path.join(WEB, "manifest.webmanifest"), encoding="utf-8"))
        self.assertEqual(m["start_url"], "app.html")
        self.assertTrue(os.path.exists(os.path.join(WEB, "app.html")))

    def test_이미_설치된_앱으로_열면_앱_화면으로_보낸다(self):
        html = open(os.path.join(WEB, "index.html"), encoding="utf-8").read()
        self.assertIn('location.replace("app.html")', html)

    def test_서버_루트는_챗봇_화면이고_index_html은_설치_화면(self):
        self.assertIn('id="chat"', self.read("/"))
        self.assertIn('id="chat"', self.read("/app.html"))
        landing = self.read("/index.html")
        self.assertIn('id="install"', landing)
        self.assertNotIn('id="chat"', landing)

    def test_서비스워커가_앱_화면을_미리_담는다(self):
        sw = open(os.path.join(WEB, "sw.js"), encoding="utf-8").read()
        self.assertIn('"app.html"', sw)


if __name__ == "__main__":
    unittest.main(verbosity=2)
