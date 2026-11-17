// 브라우저 검색 모드: 검색 서버가 없는 정적 주소(GitHub Pages 등)에서 data.json 을 직접 검색한다.
// AI 가 아니라 이름·경로·ID 글자 겹침으로 찾는다(되묻기 이해와 설명 문장은 없다).
(function (root) {
  const TOP = 5;
  const MIN_SCORE = 4;
  const FILLER = new Set(["어디", "어디에", "어디서", "어느", "있나", "있어요", "있는지", "확인", "찾아", "찾고", "보여", "알려",
    "주세요", "좀", "화면", "메뉴", "인터페이스", "어떻게", "뭐", "무엇", "위치", "경로", "싶어", "싶어요", "관련"]);

  const norm = (s) => String(s || "").toLowerCase().replace(/[\s_\-()\[\]·.>/]/g, "");

  function tokens(q) {
    const out = [];
    for (let t of String(q).split(/[\s,.?!·]+/)) {
      if (!t) continue;
      t = t.replace(/(해줘|해주세요|해 주세요|나요|인가요|예요|이에요)$/, "");
      if (t.length >= 3) t = t.replace(/(에서|으로|은|는|이|가|을|를|의|에|도|로)$/, "");
      if (t.length < 2 || FILLER.has(t)) continue;
      out.push(t);
    }
    return out;
  }

  function bigrams(s) {
    const g = new Map();
    for (let i = 0; i < s.length - 1; i++) { const b = s.slice(i, i + 2); g.set(b, (g.get(b) || 0) + 1); }
    return g;
  }
  function dice(a, b) {
    if (a.length < 2 || b.length < 2) return 0;
    const ga = bigrams(a), gb = bigrams(b);
    let hit = 0, na = 0, nb = 0;
    for (const [k, v] of ga) { na += v; if (gb.has(k)) hit += Math.min(v, gb.get(k)); }
    for (const v of gb.values()) nb += v;
    return (2 * hit) / (na + nb);
  }

  function score(row, toks, q) {
    const name = norm(row.n), detail = norm(row.d), id = norm(row.i);
    let s = 0;
    for (const t of toks) {
      const tn = norm(t);
      if (id === tn || (tn.length >= 4 && id.includes(tn))) s += 20;
      else if (name === tn) s += 12;
      else if (name.includes(tn)) s += 8 + (tn.length / name.length) * 4;
      else if (detail.includes(tn)) s += 3;
      else { const d = dice(tn, name); if (d > 0.4) s += d * 6; }
    }
    if (s > 0) {
      if (q.includes("인터페이스") && row.k === "i") s += 3;
      else if ((q.includes("화면") || q.includes("메뉴")) && row.k === "s") s += 2;
    }
    return s;
  }

  // rows: data.json 내용 · 돌려주는 값은 서버 응답(/api/ask)과 같은 모양
  function search(q, rows) {
    const toks = tokens(q);
    const scored = toks.length === 0 ? [] : rows
      .map((r) => ({ r, s: score(r, toks, q) }))
      .filter((x) => x.s >= MIN_SCORE)
      .sort((a, b) => b.s - a.s || a.r.n.localeCompare(b.r.n));
    // 1등 점수의 60%에 못 미치는 항목(한 단어만 겹친 것 등)은 뺀다
    const picked = scored.filter((x) => x.s >= scored[0].s * 0.6).slice(0, TOP).map((x) => x.r);
    if (!picked.length) return { kind: "withheld", text: "", sources: [] };
    return {
      kind: "answer",
      text: `「${q.trim()}」와 관련된 ${picked.length}건을 찾았습니다. (AI 서버 없이 브라우저에서 검색한 결과입니다.)`,
      sources: picked.map((r) => ({ kind: r.k === "s" ? "screen" : "interface", id: r.i, name: r.n, detail: r.d })),
    };
  }

  const api = { search, tokens };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.MenuSearch = api;
})(typeof self !== "undefined" ? self : this);
