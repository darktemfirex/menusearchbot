// 서비스 워커: 화면 껍데기(HTML·아이콘)만 캐시한다. 질문(/api/ask)은 캐시하지 않고 항상 서버로 보낸다.
// 화면을 고쳤으면 아래 VERSION 을 올려서 옛 캐시를 버리게 한다.
const VERSION = "v3";
const CACHE = "menu-finder-" + VERSION;
// search.js·data.json 도 미리 담아 두면 Pages 의 브라우저 검색 모드가 오프라인에서도 동작한다
const SHELL = ["./", "manifest.webmanifest", "icon-192.png", "icon-512.png", "search.js", "data.json"];   // 상대 경로: 서버 루트와 하위 주소 모두에서 동작

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("menu-finder-") && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin || url.pathname.includes("/api/")) return;
  // 화면은 항상 최신을 먼저 받고, 연결이 없을 때만 캐시를 쓴다
  e.respondWith(
    fetch(req)
      .then((res) => {
        if (res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); }
        return res;
      })
      .catch(() => caches.match(req).then((hit) => hit || caches.match("./")))
  );
});
