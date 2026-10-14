#!/usr/bin/env python3
"""Per-brief page checks: one run's web page, in Chrome and WebKit, at 1440, 1024 and 390 px.

WHY THIS EXISTS. 73-web-plan.md W6 (:153-173) split T's verifier (T:verify-t.py) in two. This half
runs on every brief, in minutes: T's page-generic groups, a page-bounds group (no
sideways overflow outside a .scroller, no clipped text) and the head (noindex; canonical and og:url
equal to SITE/<company.slug>/, D10). The other half, the card and hover suite, had no caller and
was deleted in S9 of the Globex redesign. Every expectation T typed for one cohort is read here from
brief.json, the run's claims.jsonl or the page; the template's own constants (grid, type, colours)
stay typed.

Usage:
  python3 tools/web-check.py BRIEF_ROOT [--only GROUP,...] [--engine chrome|webkit] [--port N]
  python3 tools/web-check.py --selftest     offline: no browser, no network, stdlib only
It serves BRIEF_ROOT/web/ on 127.0.0.1:PORT (default 8802, T's) and saves screenshots to
BRIEF_ROOT/web/shots/. One line per check: PASS or FAIL, its id, the evidence.
Exit: 0 every check passed; 1 a check failed or crashed; 2 bad usage or an unreadable input.
"""
import argparse, functools, html, http.server, importlib.util, json, re, shutil, subprocess, sys
import tempfile, threading, traceback, urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINES = ("chrome", "webkit")
WIDTHS = (1440, 1024, 390)  # 73-web-plan.md:160; a group T swept over more widths runs at these
MAIL = "mailto:you@example.com"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


WEBPY = load_module("web_py", ROOT / "build/web.py")  # SITE, REPO, DESC, FRAMINGS, page_url: written once there


class Brief:
    """What the checks expect, read from the run and its page, never typed for one company."""

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.web = self.root / "web"
        self.b = json.loads((self.root / "brief.json").read_text(encoding="utf-8"))
        rows = (self.root / "claims.jsonl").read_text(encoding="utf-8").splitlines()
        self.claims = {r["id"]: r for r in (json.loads(x) for x in rows if x.strip())}
        self.src = (self.web / "index.html").read_text(encoding="utf-8")
        name = self.b["company"]["name"]
        n1 = WEBPY.FRAMINGS["n1"]  # a run's page is N1 (43-rulings.md:125-135)
        self.url = WEBPY.page_url(self.b)
        shown = WEBPY.curl(name)  # web.py curls the name in the title and metadata (G76)
        self.title, self.alt = n1["title"].format(name=shown), n1["alt"].format(name=shown)
        self.year = str(self.b.get("run_date") or self.b["dates"]["evidence"]["to"])[:4]
        ents = {e["slug"]: e for e in [self.b["company"], *self.b["rivals"]]}
        self.co = {s: e.get("short") or e["name"] for s, e in ents.items()}  # the map's name for each

    def quadrants(self):
        return map_quadrants(self.b)


def map_quadrants(b):
    """Map cells, in answer order: rows are the down axis (yes on top), columns the across axis. Each name
    after the curl() web.py prints it with (G71), so "Calder's Grid" is the page's "Calder’s Grid"."""
    co = {e["slug"]: e.get("short") or e["name"] for e in [b["company"], *b["rivals"]]}
    q = {"tl": [], "tr": [], "bl": [], "br": []}
    for a in b["map"]["answers"]:
        key = ("t" if a["down"]["answer"] == "yes" else "b") + ("l" if a["across"]["answer"] == "yes" else "r")
        q[key].append(WEBPY.curl(co[a["company"]]))
    return q


def judge_map_quadrants(got, b):
    """The page's map cells, read off the DOM, against brief.json's answers."""
    want = map_quadrants(b)
    return [] if got == want else [f"quadrants: page {got}, want {want}"]


class Harness:
    """T's ok/check/page loop, with the engine, widths and port chosen per run."""

    def __init__(self, brief, port=0, only="", engines=ENGINES, widths=WIDTHS):
        self.B, self.port, self.engines, self.widths = brief, port, tuple(engines), tuple(widths)
        self.only = [g for g in only.split(",") if g]
        self.R, self.pw, self.browsers, self.server = [], None, {}, None
        self.base = f"http://127.0.0.1:{port}/"

    def ok(self, cid, cond, detail=""):
        self.R.append((bool(cond), cid))
        print(("PASS" if cond else "FAIL"), cid, detail, flush=True)

    def run(self, groups):
        """Each group in turn; a crash is a FAIL, never a skip. --only names the groups to run."""
        names = [g.__name__ for g in groups]
        unknown = [n for n in self.only if n not in names]
        if unknown:
            self.ok("only.names", False, f"no such group {unknown}; groups are {names}")
        for fn in groups:
            if self.only and fn.__name__ not in self.only:
                continue
            try:
                fn(self)
            except Exception as e:
                self.ok(f"{fn.__name__}.crashed", False, f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}")

    def finish(self):
        fails = [c for p, c in self.R if not p]
        print(f"\n{len(self.R) - len(fails)} PASS, {len(fails)} FAIL" + (f": {', '.join(fails)}" if fails else ""), flush=True)
        return 1 if fails or not self.R else 0

    def start(self):
        """Serve the run's web/ on the port, so two chunks on two ports never share a server."""
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass
        class Server(http.server.ThreadingHTTPServer):
            def handle_error(self, request, client_address):  # a browser closing its socket early is not a page fault
                if not isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError)):
                    super().handle_error(request, client_address)
        handler = functools.partial(Quiet, directory=str(self.B.web))
        self.server = Server(("127.0.0.1", self.port), handler)
        # Port 0 is the default (G34): the system picks a free port, so a port another process holds
        # never stops a run. A named port is still honoured.
        self.port = self.server.server_address[1]
        self.base = f"http://127.0.0.1:{self.port}/"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        urllib.request.urlopen(self.base + "index.html", timeout=5).read(64)

    def browser(self, eng):
        """Chrome is the installed Google Chrome, as T verified; WebKit is Playwright's, launched on first use."""
        if self.pw is None:
            from playwright.sync_api import sync_playwright
            self.pw = sync_playwright().start()
        if eng not in self.browsers:
            self.browsers[eng] = self.pw.chromium.launch(channel="chrome") if eng == "chrome" else self.pw.webkit.launch()
        return self.browsers[eng]

    def page(self, w=1440, h=900, js=True, touch=False, rm=False, dsf=1, eng="chrome"):
        ctx = self.browser(eng).new_context(viewport={"width": w, "height": h}, device_scale_factor=dsf,
                                            java_script_enabled=js, is_mobile=touch, has_touch=touch,
                                            reduced_motion="reduce" if rm else "no-preference")
        pg = ctx.new_page()
        pg.logs = []
        pg.on("console", lambda m: pg.logs.append(f"{m.type}: {m.text}"))
        pg.on("pageerror", lambda e: pg.logs.append(f"pageerror: {e}"))
        pg.goto(self.base + "index.html")
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(300)
        return pg

    @staticmethod
    def ev(pg, js, arg=None):
        return pg.evaluate(js, arg)

    def close(self):
        for b in self.browsers.values():
            b.close()
        if self.pw:
            self.pw.stop()
        if self.server:
            self.server.shutdown()
            self.server.server_close()  # release the port, so a second harness in one process can bind it


# ---- The three checks the plan adds (:162-163). Each judge is pure, so --selftest reds it offline. ----

class _Head(HTMLParser):
    def __init__(self):
        super().__init__()
        self.robots, self.canonical, self.og_url = [], [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta" and a.get("name") == "robots":
            self.robots.append(a.get("content"))
        elif tag == "link" and a.get("rel") == "canonical":
            self.canonical.append(a.get("href"))
        elif tag == "meta" and a.get("property") == "og:url":
            self.og_url.append(a.get("content"))


def judge_head(src, url):
    """The served bytes: exactly one robots noindex, and one canonical and one og:url, each equal to url."""
    p = _Head()
    p.feed(src)
    out = []
    if p.robots != ["noindex"]:
        out.append(f"noindex: meta robots is {p.robots}, want exactly ['noindex']")
    if p.canonical != [url]:
        out.append(f"canonical: {p.canonical}, want exactly [{url!r}]")
    if p.og_url != [url]:
        out.append(f"og:url: {p.og_url}, want exactly [{url!r}]")
    return out


# Every rendered element with a box: its edges, whether a .scroller holds it, and, where it clips its
# own overflow and carries text, its scroll and client sizes. .sr-only and closed cards have no box
# a reader sees, so they are left out.
BOUNDS = """() => { const out = [], vw = document.documentElement.clientWidth;
  const name = (e) => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (e.classList.length ? '.' + [...e.classList].join('.') : '');
  for (const e of document.body.querySelectorAll('*')) {
    if (e.closest('.sr-only, [hidden]') || !e.checkVisibility()) continue;
    const r = e.getBoundingClientRect(); if (!r.width && !r.height) continue;
    const s = getComputedStyle(e), clips = /hidden|clip/.test(s.overflowX + s.overflowY) && e.textContent.trim() !== '';
    out.push({sel: name(e), l: r.left, r: r.right, scroller: !!e.closest('.scroller'),
              clip: clips ? [e.scrollWidth, e.clientWidth, e.scrollHeight, e.clientHeight] : null,
              ellipsis: s.textOverflow === 'ellipsis' && e.scrollWidth > e.clientWidth}); }
  return {vw, sw: document.documentElement.scrollWidth, els: out}; }"""


def judge_matrix(width, scrolls):
    """From 1248 the matrix hangs at T's 800 px and shows every column: a matrix that scrolls there
    hides a company behind the scroller's edge (W15-verify-2 Recommended 1). Below 1248 it may scroll."""
    out = []
    if abs(width - 800) > 1:
        out.append(f"width {width:.1f}, want 800")
    if scrolls:
        out.append("the matrix scrolls: a column sits past the scroller's edge")
    return out


def judge_bounds(facts):
    """Sideways overflow outside a .scroller, and text an element clips. Returns failure lines."""
    vw, out = facts["vw"], []
    if facts["sw"] > vw:
        out.append(f"the page scrolls sideways: scrollWidth {facts['sw']} > {vw}")
    over = [f"{e['sel']} {e['l']:.1f}..{e['r']:.1f}" for e in facts["els"]
            if not e["scroller"] and (e["r"] > vw + 0.5 or e["l"] < -0.5)]
    if over:
        out.append(f"{len(over)} element(s) outside a .scroller overflow the {vw} px viewport: {over[:6]}")
    clipped = [f"{e['sel']} {e['clip']}" for e in facts["els"]
               if e["clip"] and (e["clip"][0] > e["clip"][1] + 1 or e["clip"][2] > e["clip"][3] + 1)]
    clipped += [f"{e['sel']} ellipsis" for e in facts["els"] if e.get("ellipsis")]
    if clipped:
        out.append(f"{len(clipped)} element(s) clipped their text: {clipped[:6]}")
    return out


NAMES = "() => [...document.querySelectorAll('.brief .name')].map((e) => getComputedStyle(e).hyphens)"


def judge_names(hy):
    """G65, G69: each cohort and client name web.py wraps in .brief computes hyphens: manual at 390, so CSS
    hyphenation never splits it in either engine. No .name at all means the wrap or its rule is gone."""
    if not hy:
        return ["no .brief .name on the page: web.py wrapped no cohort or client name"]
    bad = [h for h in hy if h != "manual"]
    return [f"{len(bad)} of {len(hy)} .brief .name compute hyphens {sorted(set(bad))}, want manual"] if bad else []


def judge_map_a11y(snap, headers, names):
    """The map's accessible table: each header and company name, after the same curl() web.py prints with
    (G71), so a typed ' in a label matches the page's ’."""
    want = ([f'columnheader "{WEBPY.curl(t)}"' for t in headers[:2]] + [f'rowheader "{WEBPY.curl(t)}"' for t in headers[2:]]
            + [f'button "{WEBPY.curl(n)}"' for n in names])
    missing = [w for w in want if w not in snap]
    return [f"missing {missing}"] if missing else []


def judge_map_headers(h):
    """G70, G71: --q2-c0 is the longer half of the longest row label, so the renderer guarantees each row
    header at most two lines, and a short label sets on one. A third line is W6's WebKit defect. Each row
    header's cap-top sits within 1 px of its row's logo ink top; each column header holds one line."""
    bad = []
    if abs(h["col0"] - h["want"]) > 1:
        bad.append(f"width: row-header column {h['col0']}, --q2-c0 {h['want']}")
    if any(not 1 <= r[0] <= 2 for r in h["rows"]):
        bad.append(f"lines: row headers set on {[r[0] for r in h['rows']]} lines, want 1 or 2 each")
    if any(abs(r[1]) > 1 for r in h["rows"]):
        bad.append(f"cap-top: row header cap-top minus logo-ink-top {[r[1] for r in h['rows']]}, want within 1 px")
    if h["cols"] != [1, 1]:
        bad.append(f"columns: column header lines {h['cols']}, want [1, 1]")
    return bad


# ---- The groups. T's JS is kept verbatim where it was generic; ids say what changed. ----

def head(H):
    """The bytes the server sends, as a crawler reads them, and the same three in the live DOM."""
    src = urllib.request.urlopen(H.base + "index.html", timeout=10).read().decode("utf-8")
    bad = judge_head(src, H.B.url)
    H.ok("head.noindex, canonical and og:url", not bad, "; ".join(bad) or f"noindex; both are {H.B.url}")
    for eng in H.engines:
        pg = H.page(eng=eng)
        got = H.ev(pg, """() => [[...document.querySelectorAll('meta[name=robots]')].map((m) => m.content),
          [...document.querySelectorAll('link[rel=canonical]')].map((l) => l.href),
          [...document.querySelectorAll('meta[property="og:url"]')].map((m) => m.content)]""")
        H.ok(f"head.dom {eng}", got == [["noindex"], [H.B.url], [H.B.url]], f"{got}")
        if eng == "chrome":  # W6-verify.md Recommended 2
            hp = H.ev(pg, "() => CSS.supports('hanging-punctuation', 'first')")
            H.ok("template.webkit-only scoping chrome", hp is False,
                 "template.html scopes its three WebKit fixes (the 390 measure, hyphens: manual below 30rem, the matrix "
                 f"end margin) with @supports (hanging-punctuation: first); Chrome supports it: {hp}. If true, Chrome "
                 "takes all three and leaves live T")
        pg.context.close()


def page_bounds(H):
    """No sideways overflow outside a .scroller and no clipped text; a full-page screenshot per engine and width."""
    shots = H.B.web / "shots"
    shots.mkdir(exist_ok=True)
    for eng in H.engines:
        for w in H.widths:
            pg = H.page(w, 844 if w < 500 else 900, touch=w < 500, eng=eng)
            bad = judge_bounds(H.ev(pg, BOUNDS))
            pg.screenshot(path=str(shots / f"{eng}-{w}.png"), full_page=True)
            H.ok(f"page.bounds {eng} {w}", not bad, "; ".join(bad) or f"shot {shots.name}/{eng}-{w}.png")
            if w == 390:  # below 30rem the template hyphenates prose; a name must stay whole (G65)
                hy = H.ev(pg, NAMES)
                bad = judge_names(hy)
                H.ok(f"names.hyphens {eng} 390", not bad, "; ".join(bad) or f"{len(hy)} .brief .name, each hyphens: manual")
            pg.context.close()


# T's grid, the template's own: (rail, text column) edges per width (T:verify-t.py POS).
POS = {1440: ((144, 352), (416, 1024)), 1024: ((40, 248), (312, 920)), 390: (None, (16, 374))}
LAYOUT = """() => { const b = document.querySelector('.brief').getBoundingClientRect(), c = document.getElementById('contents');
  const rail = c.checkVisibility() ? c.getBoundingClientRect() : null;
  const mx = document.querySelector('.tbl--mx'), sc = mx.querySelector('.mx');
  const lab = [...c.querySelectorAll('a')].map((a) => a.getBoundingClientRect().height);
  const rg = document.createRange(); rg.selectNodeContents(c.querySelector('a')); const t = rg.getClientRects()[0];
  const capTop = t ? t.top + (1.025 - 0.698) * 16 - (t.height - 1.3 * 16) / 2 : null;
  const qt = document.querySelector('#vT-quick-take ~ p strong').getBoundingClientRect().bottom;
  return {text: [b.left, b.right], rail: rail && [rail.left + 12, rail.right - 4], sw: document.documentElement.scrollWidth,
          mxw: mx.getBoundingClientRect().width, scrolls: sc.scrollWidth > sc.clientWidth + 1, lab, qt, vh: innerHeight,
          h1: document.querySelector('h1').getBoundingClientRect().top, capTop,
          qth: document.getElementById('vT-quick-take').getBoundingClientRect().top}; }"""


def layout(H):
    """T's layout group at the plan's widths. Dropped as one company's data: "the matrix scrolls below
    1248", true of a 795 px matrix only; the width still holds where the page hangs it to 800."""
    for eng in H.engines:
        for w in H.widths:
            pg = H.page(w, 844 if w < 500 else 900, touch=w < 500, eng=eng)
            g = H.ev(pg, LAYOUT)
            rail, text = POS[w]
            good = all(abs(a - b) <= 1 for a, b in zip(g["text"], text)) and (
                rail is None or (g["rail"] and all(abs(a - b) <= 1 for a, b in zip(g["rail"], rail))))
            H.ok(f"layout.grid {eng} {w}", good, f"text {[round(x, 1) for x in g['text']]} want {text}; rail "
                 f"{g['rail'] and [round(x, 1) for x in g['rail']]} want {rail}")
            if w >= 1024:
                off = (g["text"][0] + g["text"][1]) / 2 - w / 2
                H.ok(f"layout.centre {eng} {w}", abs(off - (0 if w >= 1248 else 104)) <= 1, f"text centre minus viewport centre {off}")
                H.ok(f"layout.rail {eng} {w}", all(h <= 40 for h in g["lab"]) and abs(g["capTop"] - g["qth"]) <= 1,
                     f"label heights {g['lab']}; first label cap top {g['capTop']:.1f}, first h2 cap top {g['qth']:.1f}")
            if w >= 1248:
                bad = judge_matrix(g["mxw"], g["scrolls"])
                H.ok(f"layout.matrix {eng} {w}", not bad, "; ".join(bad) or f"width {g['mxw']:.1f}, scrolls {g['scrolls']}")
            H.ok(f"layout.no sideways scroll {eng} {w}", g["sw"] == w, f"scrollWidth {g['sw']}")
            if w == 390:
                H.ok(f"layout.first screen {eng} 390", g["qt"] <= g["vh"], f"the first bold sentence ends at {g['qt']:.0f} of {g['vh']}")
            pg.context.close()


RHYTHM = """() => { const R = (e) => e.getBoundingClientRect(), $ = (s) => document.querySelector(s);
  const q = $('#vT-map'), recs = $('#vT-recommendations'), mx = $('.tbl--mx');
  const note = mx.nextElementSibling.matches('.mx-note') ? mx.nextElementSibling : null, last = note || mx; // the legend, where the brief has one
  const oq = last.nextElementSibling, ol = oq.nextElementSibling, also = $('#vT-also');
  const ap = also.nextElementSibling, ap2 = ap.nextElementSibling, foot = $('.foot');
  if (oq.id !== 'vT-open-questions' || ol.tagName !== 'OL' || ol.nextElementSibling !== also) return ['order', oq.id, ol.tagName];
  return [R(q).top - R(q.previousElementSibling).bottom, R(recs).top - R(q).bottom, R(oq).top - R(last).bottom, R(ol).top - R(oq).bottom,
          R(also).top - R(ol).bottom, R(ap).top - R(also).bottom, R(ap2).top - R(ap).bottom, R(foot).top - R(ap2).bottom]; }"""


def rhythm(H):
    """T's rhythm. A brief with a matrix legend (p.mx-note) measures the h2 above it from the legend."""
    for eng in H.engines:
        for w in H.widths:
            pg = H.page(w, 900, touch=w < 500, eng=eng)
            r = H.ev(pg, RHYTHM)
            want = [40, 64, 64, 24, 64, 24, 20 if w > 480 else 16, 128]
            H.ok(f"layout.rhythm {eng} {w}", r[0] != "order" and all(abs(a - b) <= 1 for a, b in zip(r, want)),
                 f"{[round(x, 1) if isinstance(x, (int, float)) else x for x in r]} want {want}")
            pg.context.close()


H1_TYPE = """() => { const h = document.querySelector('h1'), s = getComputedStyle(h);
  return {font: [s.fontSize, s.lineHeight, s.fontWeight], wrap: s.textWrap || s.textWrapMode,
          href: h.querySelector('a') && h.querySelector('a').getAttribute('href')}; }"""


def title(H):
    """T's title.type. Dropped as one company's data: title.lines, the h1's line starts per width,
    which follow the company's name; page.bounds holds any width's h1 inside the page."""
    for eng in H.engines:
        for w in H.widths:
            pg = H.page(w, 900, eng=eng)
            r = H.ev(pg, H1_TYPE)
            f = ["26px", "32px", "600"] if w >= 480 else ["24px", "30px", "600"]
            H.ok(f"title.type {eng} {w}", r["font"] == f and "wrap" in r["wrap"] and "balance" not in r["wrap"] and r["href"] == WEBPY.REPO,
                 f"{r['font']}, text-wrap {r['wrap']}, link {r['href']}")
            pg.context.close()


BAR = """() => { const m = document.querySelector('.head__wm'), n = document.querySelector('.head__nav');
  const rg = document.createRange(); rg.selectNodeContents(m);
  const lines = new Set([...rg.getClientRects()].map((x) => Math.round(x.top))).size;
  const mr = m.getBoundingClientRect(), nr = n.getBoundingClientRect();
  return {lines, h: document.querySelector('.head').getBoundingClientRect().height, wm: mr.height, gap: nr.left - mr.right,
          ends: [mr.right, nr.left], ww: mr.width, txt: m.textContent, fors: document.querySelectorAll('.head__for').length,
          mark: document.querySelector('.head__umbrella').checkVisibility(), slash: document.querySelector('.head__slash').checkVisibility()}; }"""


def bar(H):
    for eng in H.engines:
        for w in H.widths:
            pg = H.page(w, 844, touch=w < 500, eng=eng)
            r = H.ev(pg, BAR)
            shown = w >= 368
            good = round(r["h"]) == 64 and r["lines"] == 1 and r["gap"] >= 16 and r["mark"] == shown and r["slash"] == shown
            if w == 390:  # 40 §4 (M): the wordmark ends at 185, the nav starts at 227
                good = good and r["wm"] <= 40 and all(abs(a - b) <= 1 for a, b in zip(r["ends"], (185, 227)))
            H.ok(f"bar.fit {eng} {w}", good, f"bar {r['h']}, wordmark {r['lines']} line(s) {r['wm']} tall, ends "
                 f"{[round(x, 1) for x in r['ends']]}, {r['gap']:.1f} to the nav, mark {r['mark']}, slash {r['slash']}")
            H.ok(f"bar.label {eng} {w}", r["txt"] == "Competitor intel" and abs(r["ww"] - 119.06) <= 0.5 and r["fors"] == 0,
                 f"{r['txt']!r}, {r['ww']:.2f} wide, .head__for {r['fors']}")
            pg.context.close()
        pg = H.page(eng=eng)
        links = H.ev(pg, "() => [document.querySelector('.head__umbrella').href, document.querySelector('.head__mark').getAttribute('href'), "
                         "document.querySelector('.head__mail').getAttribute('href'), document.querySelector('.head__logo').alt]")
        H.ok(f"bar.links {eng}", links == ["https://in-the-loop.studio/", "#top", MAIL, "In The Loop"], f"{links}")
        pg.context.close()


# Lines in a block, read from its glyphs. .sr-only and cards are skipped.
NLINES = """(el) => { let n = 0, last = null; const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT,
    {acceptNode: (t) => t.parentElement.closest('.sr-only, .card, .pn') ? 2 : 1});
  for (let t; (t = w.nextNode());) for (let i = 0; i < t.data.length; i++) { if (/\\s/.test(t.data[i])) continue;
    const rg = document.createRange(); rg.setStart(t, i); rg.setEnd(t, i + 1); const r = rg.getClientRects()[0];
    if (r && (last === null || r.top > last + 5)) { n++; last = r.top; } }
  return n; }"""
FOOT = """() => { const R = (e) => e.getBoundingClientRect(), [l, rt] = document.querySelectorAll('.foot__line');
  const rows = [...document.querySelectorAll('.foot__row')].map(R), foot = R(document.querySelector('.foot'));
  const last = document.querySelector('#vT-also').parentElement.querySelector('.psrc').previousElementSibling;
  const lines = [...document.querySelectorAll('#vT-also ~ p')].map(""" + NLINES + """), col = R(document.querySelector('.brief'));
  const wide = [R(document.querySelector('.layout')).left, Math.max(col.right, R(document.querySelector('.tbl--mx')).right)];
  const s = getComputedStyle(document.querySelector('.foot__line')), ps = getComputedStyle(document.querySelector('#vT-also + p'));
  return {row: Math.abs(R(l).top - R(rt).top) < 1, left: R(l).left, right: R(rt).right, sideGap: R(rt).left - R(l).right, wide,
          toRule: foot.top - R(last).bottom, ruleToCap: rows[0].top - foot.top, capGap: rows[1].top - rows[0].bottom,
          stack: R(rt).top - R(l).bottom, end: document.documentElement.scrollHeight - (rows[3].bottom + scrollY),
          lines, type: [s.fontSize, s.lineHeight, s.letterSpacing, s.color], p: [ps.fontSize, ps.lineHeight],
          hrefs: [...document.querySelectorAll('.foot a')].map((a) => a.getAttribute('href'))}; }"""


def footer(H):
    """T's footer and also.lines; the footer rows from 432 px, stacked below (Ryan, 5 October 2026)."""
    for eng in H.engines:
        for w in H.widths:
            pg = H.page(w, 900, eng=eng)
            r = H.ev(pg, FOOT)
            row = w >= 432
            H.ok(f"footer.sides {eng} {w}", r["row"] == row and abs(r["left"] - r["wide"][0]) <= 1 and abs(r["right"] - r["wide"][1]) <= 1,
                 f"row {r['row']}, sides {r['left']:.1f} to {r['right']:.1f}, wide grid {r['wide']}")
            sp = [r["toRule"], r["ruleToCap"], r["capGap"], r["end"]]
            good = all(abs(a - b) <= 1 for a, b in zip(sp, (128, 32, 12, 72))) and (r["sideGap"] >= 72 if row else abs(r["stack"] - 32) <= 1)
            H.ok(f"footer.spacing {eng} {w}", good, f"to rule, rule to cap, baseline to cap, to page end {[round(x, 1) for x in sp]}; "
                 + (f"between sides {r['sideGap']:.1f}" if row else f"stacked {r['stack']:.1f}"))
            H.ok(f"footer.type {eng} {w}", r["type"] == ["14px", "21px", "normal", "rgb(77, 83, 90)"]
                 and r["hrefs"] == [WEBPY.LINKEDIN, "https://in-the-loop.studio/", WEBPY.REPO, MAIL], f"{r['type']}; {r['hrefs']}")
            want, p = ([3, 3], ["16px", "23px"]) if w < 480 else ([2, 2], ["20px", "28px"])  # 40 §2a
            H.ok(f"also.lines {eng} {w}", r["lines"] == want and r["p"] == p, f"lines {r['lines']}, {r['p']}")
            pg.context.close()


# WebKit, as Safari, moves Tab between form fields only unless "Press Tab to highlight each item" is on;
# Option-Tab is how a keyboard reader reaches links and buttons there.
TAB = {"chrome": "Tab", "webkit": "Alt+Tab"}
OPEN = "() => [...document.querySelectorAll('.card:popover-open')].map((c) => c.id)"
TARGETS = "(s) => [...document.querySelectorAll(s)].map((t) => t.getAttribute('popovertarget'))"
DOCK = "() => { const c = document.querySelector('.card:popover-open').getBoundingClientRect(); return [c.left, innerWidth - c.right, innerHeight - c.bottom]; }"


def states(H):
    """T's states group at T's own viewports (each is a state, not a width sweep). The triggers T named
    by id are taken by position and their ids read from the page."""
    for eng in H.engines:
        pg = H.page(640, 450, dsf=2, eng=eng)  # 200% zoom of 1280x900
        cites = H.ev(pg, TARGETS, ".cite")
        r = H.ev(pg, "() => [document.documentElement.scrollWidth, getComputedStyle(document.querySelector('.layout')).gridTemplateColumns.split(' ').length]")
        pg.locator(".head__toc").click(); pg.wait_for_timeout(300)
        sheet = H.ev(pg, "() => document.getElementById('contents').matches(':popover-open')")
        pg.locator('#contents a[href="#vT-open-questions"]').click(); pg.wait_for_timeout(300)
        jumped = H.ev(pg, "() => Math.round(document.getElementById('vT-open-questions').getBoundingClientRect().top)")
        k = min(3, len(cites) - 1)
        pg.locator(".cite").nth(k).scroll_into_view_if_needed(); pg.locator(".cite").nth(k).click(); pg.wait_for_timeout(300)
        dock = H.ev(pg, DOCK)
        H.ok(f"states.200% zoom {eng}", r == [640, 1] and sheet and 90 <= jumped <= 100 and [round(x) for x in dock] == [16, 16, 16],
             f"scrollWidth, columns {r}; sheet {sheet}; jump lands at {jumped}; card gaps {dock}")
        pg.context.close()
        pg = H.page(768, 900, js=False, eng=eng)
        chips, logos = H.ev(pg, TARGETS, ".brief > p .chip"), H.ev(pg, TARGETS, ".q2__co")
        pg.locator(".brief > p .chip").first.click(); pg.wait_for_timeout(200)
        a = H.ev(pg, OPEN)
        pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
        pg.locator(".q2__co").first.focus(); pg.keyboard.press("Enter"); pg.wait_for_timeout(200)
        b = H.ev(pg, OPEN)
        k = min(4, len(cites) - 1)
        pg.keyboard.press("Escape"); pg.locator(".cite").nth(k).click(); pg.wait_for_timeout(200)
        c = H.ev(pg, OPEN)
        pg.mouse.click(5, 400); pg.wait_for_timeout(100)
        light = H.ev(pg, OPEN)
        pg.locator(".brief > p .chip").nth(1).hover(); pg.wait_for_timeout(600)
        d = H.ev(pg, OPEN)
        pg.locator(".head__toc").click(); pg.wait_for_timeout(200)
        sheet = H.ev(pg, "() => document.getElementById('contents').matches(':popover-open')")
        logs = [x for x in pg.logs if "favicon" not in x]
        H.ok(f"states.JS off {eng}", a == chips[:1] and b == logos[:1] and c == [cites[k]] and light == [] and d == [] and sheet and not logs,
             f"chip {a}, logo by Enter {b}, cell {c} want {cites[k]}, light dismiss {light}, hover {d}, sheet {sheet}, console {logs}")
        pg.context.close()
        pg = H.page(1440, 900, rm=True, eng=eng)
        pg.locator(".brief > p .chip").first.click(); pg.wait_for_timeout(30)
        t = H.ev(pg, "() => { const c = document.querySelector('.card:popover-open'); const s = getComputedStyle(c); return [s.transitionDuration, s.opacity]; }")
        pg.keyboard.press("Escape"); pg.wait_for_timeout(30)
        closed = H.ev(pg, OPEN)
        ct = H.ev(pg, "() => getComputedStyle(document.querySelector('.chip')).transitionDuration")
        H.ok(f"states.reduced motion {eng}", set(t[0].replace(" ", "").split(",")) == {"0s"} and t[1] == "1" and closed == [] and "0.12s" in ct,
             f"card {t}; closed at once {closed == []}; chip colour transition {ct}")
        pg.context.close()
        pg = H.page(768, 900, rm=True, eng=eng)
        pg.locator(".head__toc").click(); pg.wait_for_timeout(20)
        s = H.ev(pg, "() => { const c = getComputedStyle(document.getElementById('contents')); return [c.translate, c.transitionProperty]; }")
        H.ok(f"states.reduced motion sheet fades only {eng}", s[0] in ("none", "0px") and "opacity" in s[1], f"{s}")
        pg.context.close()
        pg = H.page(1440, 900, eng=eng)
        H.ev(pg, """() => { for (const sh of document.styleSheets) for (const r of [...sh.cssRules]) if (r.conditionText === 'not (anchor-name: --a)')
            { const st = document.createElement('style'); st.textContent = [...r.cssRules].map((x) => x.cssText).join('\\n'); document.head.append(st); }
          document.querySelectorAll('[style*=anchor]').forEach((e) => e.removeAttribute('style')); }""")
        chip = pg.locator(".brief > p .chip").nth(min(3, len(chips) - 1))
        if eng == "webkit":  # a click never focuses a button in WebKit, as in Safari, so its reader opens the card by key
            chip.focus(); pg.keyboard.press("Enter")
        else:
            chip.click()
        pg.wait_for_timeout(300)
        d = H.ev(pg, DOCK)
        pg.keyboard.press(TAB[eng]); pg.wait_for_timeout(100)
        H.ok(f"states.no anchor support docks {eng}", [round(x) for x in d] == [16, 16, 16] and H.ev(pg, "() => document.activeElement.tagName") == "A", f"gaps {d}")
        pg.context.close()


PRINT = """() => { const vis = (s) => [...document.querySelectorAll(s)].some((e) => e.checkVisibility());
  const seq = [...document.querySelectorAll('.pn')].filter((e) => e.checkVisibility()).flatMap((e) => e.textContent.split(',').map(Number));
  const items = [...document.querySelectorAll('.psrc li')].map((li) => [li.querySelector('.psrc__n').textContent, li.textContent, li.querySelector('.psrc__u').textContent]);
  const mail = getComputedStyle(document.querySelector('.foot a[href^="mailto"]'), '::after').content;
  const mx = document.querySelector('.mx'), q = document.querySelector('.q2 table');
  return {hidden: !vis('.bar') && !vis('.chip') && !vis('.cite__n') && !vis('.card') && !vis('#contents'), first: [...new Set(seq)], items,
          mail, whole: mx.scrollWidth <= mx.clientWidth && q.scrollWidth <= q.clientWidth + 1, brk: getComputedStyle(document.querySelector('.q2')).breakInside,
          pos: getComputedStyle(document.querySelector('.pn')).fontVariantPosition, text: getComputedStyle(document.querySelector('.brief > p')).color,
          foot: getComputedStyle(document.querySelector('.foot')).breakBefore}; }"""
SHARE = """() => { const q = (s) => [...document.querySelectorAll(s)], one = (s) => { const e = q(s); return e.length === 1 ? (e[0].content ?? e[0].getAttribute('href')) : `x${e.length}`; };
  const keys = ['title', 'meta[name=description]', 'link[rel=canonical]', 'meta[property="og:type"]', 'meta[property="og:url"]', 'meta[property="og:title"]',
    'meta[property="og:description"]', 'meta[property="og:image"]', 'meta[property="og:image:width"]', 'meta[property="og:image:height"]',
    'meta[property="og:image:alt"]', 'meta[name="twitter:card"]', 'meta[name="twitter:image:alt"]', 'meta[name=robots]', 'link[rel=apple-touch-icon]'];
  return {tags: Object.fromEntries(keys.map((k) => [k, k === 'title' ? (q('title').length === 1 ? document.title : 'x' + q('title').length) : one(k)])),
          icons: q('link[rel=icon]').map((l) => l.getAttribute('href')), title: document.querySelector('.title').textContent}; }"""


def print_and_head(H):
    """T's group. The title, description and alt are N1's, from build/web.py; the year is the run's.
    The PDF footer check is Chrome's: Playwright prints a PDF in Chromium only."""
    for eng in H.engines:
        pg = H.page(1440, 900, eng=eng)
        pg.emulate_media(media="print")
        r = H.ev(pg, PRINT)
        n = len(r["first"])
        good_items = len(r["items"]) == n and all(i[0] == str(k + 1) and re.search(r"https?://", i[2]) and ", " in i[1] for k, i in enumerate(r["items"]))
        H.ok(f"states.print {eng}", r["hidden"] and r["first"] == list(range(1, n + 1)) and good_items and "you@example.com" in r["mail"]
             and r["whole"] and r["brk"] == "avoid" and r["pos"] == "super" and r["foot"] == "avoid",
             f"hidden {r['hidden']}, numbers 1..{n} in order {r['first'] == list(range(1, n + 1))}, print source items {len(r['items'])} "
             f"well formed {good_items}, address {r['mail']}, map and matrix whole {r['whole']}, footer break-before {r['foot']}")
        H.ok(f"pt.print {eng}", r["text"] == "rgb(0, 0, 0)", f"print body text {r['text']}")
        if eng == "chrome":
            pdf = Path(tempfile.mkdtemp()) / "print.pdf"
            pg.pdf(path=str(pdf), format="A4", print_background=True)
            n_pdf = int(re.search(r"^Pages:\s+(\d+)", subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout, re.M).group(1))
            texts = [subprocess.run(["pdftotext", "-f", str(i), "-l", str(i), "-layout", str(pdf), "-"], capture_output=True, text=True).stdout
                     for i in range(1, n_pdf + 1)]
            rows = ("Built by Ryan", "part of In The Loop.", "Made with my agent.", "To get in touch")
            whole = [i + 1 for i, t in enumerate(texts) if all(x in t for x in rows)]
            blank = [i + 1 for i, t in enumerate(texts) if not t.strip()]
            above = bool(re.search(r"https?://", texts[-1].split(rows[0])[0]))
            H.ok("states.print footer chrome", whole == [n_pdf] and above and not blank,
                 f"{n_pdf} pages; whole footer on pages {whole}; a source above it on the last page {above}; blank pages {blank}")
            shutil.rmtree(pdf.parent)
        pg.emulate_media(media="screen")
        m = H.ev(pg, SHARE)
        t = m["tags"]
        H.ok(f"states.head tags {eng}", t["title"] == t['meta[property="og:title"]'] == H.B.title
             and t["meta[name=description]"] == t['meta[property="og:description"]'] == WEBPY.DESC and H.B.year not in m["title"],
             f"{t['title']!r}, {t['meta[name=description]']!r}; want {H.B.title!r}; year {H.B.year} in .title {H.B.year in m['title']}")
        og_img = t['meta[property="og:image"]']
        good = (t["link[rel=canonical]"] == t['meta[property="og:url"]'] and re.fullmatch(r"https://[^/\s]+/\S+", t["link[rel=canonical]"] or "")
                and isinstance(og_img, str) and (H.B.web / "og.png").is_file()  # ?v= is the card's own hash
                and og_img == WEBPY.og_image_url(t['meta[property="og:url"]'], (H.B.web / "og.png").read_bytes())
                and t['meta[name="twitter:card"]'] == "summary_large_image"
                and [t['meta[property="og:image:width"]'], t['meta[property="og:image:height"]']] == ["2400", "1260"]
                and t['meta[property="og:image:alt"]'] == t['meta[name="twitter:image:alt"]'] == H.B.alt
                and t['meta[property="og:type"]'] == "article" and t["meta[name=robots]"] == "noindex"
                and m["icons"] == ["favicon-p.svg", "favicon-32.png"] and t["link[rel=apple-touch-icon]"] == "apple-touch-icon.png"
                and all(not str(v).startswith("x") for v in t.values()))
        H.ok(f"states.share tags {eng}", good, f"{t}; icons {m['icons']}")
        pg.context.close()
    share_files(H)


def share_files(H):
    """Brief 2026-10-05: og.png is the dark card (#17191b at (0, 0)); each icon is every pixel opaque, the
    dot's centre in the mark's #17191b (favicon-p.svg's viewBox 96 88 336 336; the dot centres on 204, 254)."""
    from PIL import Image
    d = H.B.web
    sizes = {f: (lambda b: (int.from_bytes(b[16:20], "big"), int.from_bytes(b[20:24], "big")))((d / f).read_bytes())
             for f in ("og.png", "favicon-32.png", "apple-touch-icon.png")}
    og0 = Image.open(d / "og.png").convert("RGBA").getpixel((0, 0))
    icons = {}
    for f, n in (("favicon-32.png", 32), ("apple-touch-icon.png", 180)):
        im = Image.open(d / f).convert("RGBA")
        dot = (round((204 - 96) * n / 336), round((254 - 88) * n / 336))
        icons[f] = (sum(1 for q in im.getdata() if q[3] != 255), im.getpixel(dot))
    icons_ok = all(bad == 0 and px == (0x17, 0x19, 0x1b, 255) for bad, px in icons.values())
    H.ok("states.share card", sizes == {"og.png": (2400, 1260), "favicon-32.png": (32, 32), "apple-touch-icon.png": (180, 180)}
         and og0 == (0x17, 0x19, 0x1b, 255) and icons_ok, f"PNG sizes {sizes}; og.png (0, 0) {og0}; icons (non-opaque px, dot px) {icons}")


FOCUS = """() => { const e = document.activeElement; if (e === document.body) return null;
  const s = getComputedStyle(e), b = e.getBoundingClientRect();
  const kind = e.matches('.skip') ? 'skip' : e.closest('.banner') ? 'banner' : e.matches('.head__umbrella') ? 'logo' : e.matches('.head__mark') ? 'wordmark'
    : e.matches('.head__toc') ? 'contents' : e.matches('.head__mail') ? 'email' : e.closest('h1') ? 'h1' : e.closest('#contents') ? 'rail'
    : e.matches('.chip, .cite, .q2__co') ? 'trigger' : e.closest('.brief') && e.closest('p') && !e.closest('.card') ? 'also' : e.closest('.foot') ? 'foot'
    : e.closest('.card') ? 'card' : e.matches('.mx') ? 'scroller' : e.tagName;
  return [kind, s.outlineStyle !== 'none' && s.outlineWidth === '2px', !e.closest('.bar, .banner, .card, .skip') && b.top < 64]; }"""
N_STOPS = "() => document.querySelectorAll('a[href], button, [tabindex]').length"


def focus_order(H):
    """T's focus order, with N1's head: no banner, so the skip link leads to the logo. The rail shows from 1024."""
    for eng in H.engines:
        for w in H.widths:
            head_ = ["skip", "logo", "wordmark", "email", "h1", "rail"] if w >= 1024 else ["skip", "logo", "wordmark", "contents", "email", "h1"]
            pg = H.page(w, 900, eng=eng)
            seq, bad = [], []
            for _ in range(H.ev(pg, N_STOPS) + 20):
                pg.keyboard.press(TAB[eng]); pg.wait_for_timeout(10)
                r = H.ev(pg, FOCUS)
                if r is None:
                    break
                seq.append(r[0])
                if not r[1] or r[2]:
                    bad.append(r)
            runs = [k for i, k in enumerate(seq) if i == 0 or seq[i - 1] != k]
            tail = ["trigger", "scroller", "trigger", "also", "foot"]
            H.ok(f"focus.order {eng} {w}", runs[:len(head_)] == head_ and runs[len(head_):len(head_) + 5] == tail and not bad,
                 f"{len(seq)} stops; runs {runs}; faults {bad[:4]}")
            pg.context.close()


MXSTOP = """() => { const e = document.activeElement; if (!e.matches('.mx .cite')) return null;
  const td = e.closest('td'), st = td.parentElement.firstElementChild, sc = e.closest('.mx');
  const c = td.getBoundingClientRect(), b = sc.getBoundingClientRect(), r = e.getBoundingClientRect();
  const ring = 4; // the 2px outline at offset 2
  return [e.getAttribute('popovertarget'), Math.min(c.left, r.left - ring) - st.getBoundingClientRect().right,
          b.left + sc.clientLeft + sc.clientWidth - Math.max(c.right, r.right + ring)]; }"""


def focus_matrix(H):
    """36 R5: Tab through every matrix cell from the scroller; each focused cell and its ring sit inside the
    scroller's visible box, clear of the sticky first column. T's viewport heights, at the plan's widths."""
    for eng in H.engines:
        for w in H.widths:
            h = {1440: 900, 1024: 768, 390: 844}.get(w, 900)
            pg = H.page(w, h, eng=eng)
            n = H.ev(pg, "() => document.querySelectorAll('.mx .cite').length")
            H.ev(pg, "() => document.querySelector('.mx').focus()")
            stops, under, right = 0, [], []
            for _ in range(n + 10):
                pg.keyboard.press(TAB[eng]); pg.wait_for_timeout(30)
                r = H.ev(pg, MXSTOP)
                if r is None:
                    break
                stops += 1
                if r[1] < -0.5:
                    under.append(f"{r[0]} {r[1]:.0f}")
                if r[2] < -0.5:
                    right.append(f"{r[0]} {r[2]:.0f}")
            H.ok(f"focus.matrix clear of the sticky column {eng} {w}x{h}", n > 0 and stops == n and not under,
                 f"{stops} of {n} cell stops; {len(under)} under the first column {under[:6]}")
            H.ok(f"focus.matrix clear of the right edge {eng} {w}x{h}", n > 0 and stops == n and not right,
                 f"{stops} of {n} cell stops; {len(right)} cut at the right edge {right[:6]}")
            pg.context.close()


def fonts(H):
    """Every character on the page is in the page's own subset. Dropped as one company's data: T's "U+2009
    is on the page", true where a chip has two sources. The platform-font read is CDP, so Chrome's."""
    from fontTools.ttLib import TTFont
    cmap = TTFont(H.B.web / WEBPY.FONT_OUT).getBestCmap()
    for eng in H.engines:
        pg = H.page(1440, 900, eng=eng)
        chars = H.ev(pg, "() => document.body.innerText + [...document.querySelectorAll('.card, .sr-only, .chip')].map((e) => e.textContent).join('')")
        miss = sorted({c for c in chars if c not in "\n\t" and ord(c) not in cmap})
        H.ok(f"build.cmap {eng}", not miss, f"missing {miss}; {len(set(chars))} distinct characters")
        if eng == "chrome":
            cdp = pg.context.new_cdp_session(pg)
            cdp.send("DOM.enable"); cdp.send("CSS.enable")
            root = cdp.send("DOM.getDocument", {"depth": -1})["root"]["nodeId"]
            fams = set()
            for sel in ("h1", ".brief h2", ".brief > p", "strong", "td", ".chip", ".cite__n", ".q2__ch", ".foot__line", ".head__mark", "#contents a"):
                nid = cdp.send("DOM.querySelector", {"nodeId": root, "selector": sel})["nodeId"]
                if not nid:  # a page without the element is a FAIL with its name, not a crash
                    fams.add(f"no {sel}"); continue
                fams |= {f["familyName"] for f in cdp.send("CSS.getPlatformFontsForNode", {"nodeId": nid})["fonts"]}
            H.ok("build.cmap platform fonts chrome", fams == {"IBM Plex Sans Var"}, f"{fams}")
        pg.context.close()


PT = """() => { const g = (s) => getComputedStyle(document.querySelector(s)), c = document.createElement('canvas').getContext('2d');
  const p = g('.brief > p'); c.font = `400 ${p.fontSize} "IBM Plex Sans"`;
  const lines = [], full = [];
  for (const el of document.querySelectorAll('.brief > p')) {
    const walk = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, {acceptNode: (n) => n.parentElement.closest('.chip, .card, .pn, .sr-only') ? 2 : 1});
    const runs = {p: new Map(), n: new Map()};
    for (let n; (n = walk.nextNode());) for (let i = 0; i < n.data.length; i++) {
      const rg = document.createRange(); rg.setStart(n, i); rg.setEnd(n, i + 1); const r = rg.getClientRects()[0]; if (!r) continue;
      const per = runs[n.parentElement.closest('.next') ? 'n' : 'p'], k = Math.round(r.bottom); per.set(k, (per.get(k) || 0) + 1); }
    for (const per of Object.values(runs)) { const v = [...per.entries()].sort((a, b) => a[0] - b[0]).map((e) => e[1]); lines.push(...v); full.push(...v.slice(0, -1)); } }
  const all = [...document.querySelectorAll('body *')].filter((e) => getComputedStyle(e).letterSpacing !== 'normal').map((e) => e.className || e.tagName);
  return {body: [p.fontSize, p.lineHeight, c.measureText('x').actualBoundingBoxAscent], lines, full,
          h1: [g('h1').fontSize, g('h1').lineHeight, g('h1').fontWeight], h2: [g('.brief h2').fontSize, g('.brief h2').lineHeight, g('.brief h2').fontWeight],
          td: [g('td').fontSize, g('td').lineHeight], th: [g('th').fontSize, g('th').lineHeight], foot: [g('.foot__line').fontSize, g('.foot__line').lineHeight],
          tracking: all.slice(0, 5), wrap: g('.brief > p').textWrap || g('.brief > p').textWrapStyle}; }"""
GAPS = """() => { const R = (e) => e.getBoundingClientRect(), h = document.querySelector('#vT-recommendations');
  const p2 = document.querySelector('#vT-recommendations ~ p + p') || document.querySelector('#vT-quick-take ~ p + p'), p1 = p2.previousElementSibling;
  return [R(p2).top - R(p1).bottom, R(h).top - R(h.previousElementSibling).bottom, R(h.nextElementSibling).top - R(h).bottom]; }"""
VISIBLE = "() => document.body.innerText + [...document.querySelectorAll('.card')].map((c) => c.textContent).join(' ')"


def butterick(H):
    """T's Butterick group. pt.space takes the first two adjacent paragraphs after the recommendations h2
    (T took the two recommendations; a brief may have one)."""
    for eng in H.engines:
        for w in H.widths:
            pg = H.page(w, 900, touch=w < 500, eng=eng)
            r, g = H.ev(pg, PT), H.ev(pg, GAPS)
            small = w < 480
            body = ["16px", "23px", 8.26] if small else ["20px", "28px", 10.32]
            H.ok(f"pt.body {eng} {w}", r["body"][:2] == body[:2] and abs(r["body"][2] - body[2]) <= 0.1, f"{r['body']}")
            mean = sum(r["full"]) / len(r["full"]) if r["full"] else 0  # a paragraph's last line is not a measure
            H.ok(f"pt.measure {eng} {w}", (60 <= mean <= 66 if not small else mean >= 43) and max(r["lines"]) <= 90,
                 f"mean {mean:.1f} characters per full line over {len(r['full'])} lines, longest {max(r['lines'])}")
            h1, h2 = (["24px", "30px", "600"], ["20px", "26px", "600"]) if small else (["26px", "32px", "600"], ["22px", "28px", "600"])
            H.ok(f"pt.headings {eng} {w}", r["h1"] == h1 and r["h2"] == h2, f"h1 {r['h1']}, h2 {r['h2']}")
            para = 16 if small else 20
            H.ok(f"pt.space {eng} {w}", abs(g[0] - para) <= 1 and abs(g[1] - 64) <= 1 and abs(g[2] - 24) <= 1 and g[1] > g[2] > g[0],
                 f"paragraph {g[0]:.1f}, above h2 {g[1]:.1f}, below h2 {g[2]:.1f}")
            if w == 1440:
                H.ok(f"pt.tables {eng}", r["td"] == ["16px", "23px"] and r["th"] == ["16px", "20px"], f"td {r['td']}, th {r['th']}")
                H.ok(f"pt.footer {eng}", r["foot"] == ["14px", "21px"], f"{r['foot']}")
                H.ok(f"pt.tracking {eng}", not r["tracking"], f"elements with letter-spacing {r['tracking']}")
                H.ok(f"pt.widows {eng}", "pretty" in (r["wrap"] or ""), f"text-wrap {r['wrap']}")
                g2 = H.ev(pg, LAYOUT)
                H.ok(f"pt.centre {eng}", abs((g2["text"][0] + g2["text"][1]) / 2 - 720) <= 1, f"text centre {(g2['text'][0] + g2['text'][1]) / 2}, viewport 720")
                vis = H.ev(pg, VISIBLE)
                loose = re.findall(r"\b\d{1,2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b", vis)
                H.ok(f"pt.marks {eng}", "'" not in vis and '"' not in vis and not loose,
                     f"straight ' {vis.count(chr(39))}, straight \" {vis.count(chr(34))}; unbound dates {loose[:4]}")
            pg.context.close()
    css = "\n".join(re.findall(r"<style>(.*?)</style>", H.B.src, re.S))
    H.ok("pt.no-ops", "font-optical-sizing" not in css and "font-variant-numeric" not in css and "font-variant-position: super" in css,
         f"font-optical-sizing {css.count('font-optical-sizing')}, font-variant-numeric {css.count('font-variant-numeric')}")


def lum(c):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def contrast(a, b):
    a, b = [tuple(int(float(x)) for x in re.findall(r"[\d.]+", s)[:3]) for s in (a, b)]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return round((hi + 0.05) / (lo + 0.05), 2)


STYLE = """(s) => { const c = getComputedStyle(document.querySelector(s)); return [c.color, c.backgroundColor, c.boxShadow, c.borderRadius,
  c.fontSize, c.lineHeight, c.fontWeight, c.letterSpacing]; }"""
# Matrix cells holding a trigger, as [row, column] in tbody; T's two cells, (2, 3) and (4, 1), where they hold one.
CITE_CELLS = """() => [...document.querySelectorAll('.tbl--mx tbody tr')].flatMap((tr, i) =>
  [...tr.querySelectorAll('td')].map((td, j) => td.querySelector('.cite') ? [i, j] : null).filter(Boolean))"""


def chip_look_and_cells(H):
    for eng in H.engines:
        pg = H.page(1440, 900, eng=eng)
        rest, cell_rest = H.ev(pg, STYLE, ".brief > p .chip"), H.ev(pg, STYLE, ".cite__n")
        pg.locator(".brief > p .chip").first.hover(); pg.wait_for_timeout(600)
        hov = H.ev(pg, STYLE, ".brief > p .chip")
        H.ok(f"chips.look {eng}", rest[:2] == ["rgb(77, 83, 90)", "rgb(245, 246, 247)"] and rest[3:] == ["4px", "12px", "16px", "500", "normal"]
             and "inset" in rest[2] and hov[:2] == ["rgb(26, 28, 30)", "rgb(223, 226, 229)"] and contrast(*rest[:2]) == 7.19
             and contrast(*hov[:2]) == 13.14 and cell_rest[:2] == rest[:2] and cell_rest[3:] == rest[3:],
             f"rest {rest[:2]} {contrast(*rest[:2])}:1 {rest[3:]}; hover {hov[:2]} {contrast(*hov[:2])}:1; cell chip {cell_rest[:2]} {cell_rest[3:]}")
        pg.keyboard.press("Escape"); pg.mouse.move(5, 500); pg.wait_for_timeout(700)
        cells = H.ev(pg, CITE_CELLS)
        pick = lambda want: want if want in cells else cells[0]
        r1, c1 = pick([2, 3])
        td = pg.locator(".tbl--mx tbody tr").nth(r1).locator("td").nth(c1)
        td.scroll_into_view_if_needed()
        b = td.bounding_box()
        pg.mouse.move(b["x"] + b["width"] - 3, b["y"] + b["height"] - 3); pg.wait_for_timeout(150)
        fill = H.ev(pg, "(e) => getComputedStyle(e).backgroundColor", td.element_handle())
        early = H.ev(pg, OPEN)
        pg.wait_for_timeout(300)
        late = H.ev(pg, OPEN)
        want = H.ev(pg, "(e) => e.querySelector('.cite').getAttribute('popovertarget')", td.element_handle())
        H.ok(f"chips.cells hover {eng}", fill == "rgb(245, 246, 247)" and early == [] and late == [want],
             f"cell {r1},{c1}: fill {fill}; at 150ms {early}, at 450ms {late}, want {want}")
        pg.keyboard.press("Escape"); pg.mouse.move(5, 500); pg.wait_for_timeout(700)
        r2, c2 = pick([4, 1])
        td2 = pg.locator(".tbl--mx tbody tr").nth(r2).locator("td").nth(c2)
        td2.scroll_into_view_if_needed()
        b2 = td2.bounding_box()
        pg.mouse.click(b2["x"] + 3, b2["y"] + b2["height"] - 3); pg.wait_for_timeout(250)
        want2 = H.ev(pg, "(e) => e.querySelector('.cite').getAttribute('popovertarget')", td2.element_handle())
        H.ok(f"chips.cells click in a corner {eng}", H.ev(pg, OPEN) == [want2], f"cell {r2},{c2}: {H.ev(pg, OPEN)}, want {want2}")
        pg.context.close()


QD = """() => Object.fromEntries(['tl','tr','bl','br'].map((q) => [q, [...document.querySelectorAll(`.q2__cell--${q} .q2__co`)]
  .map((t) => t.querySelector('.sr-only, .q2__wm').textContent)]))"""
MAP_HEAD = """() => { const R = (e) => e.getBoundingClientRect();
  const col0 = R(document.querySelector('.q2__rh')).width, want = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--q2-c0'));
  const lines = (e) => { const rg = document.createRange(); rg.selectNodeContents(e); return new Set([...rg.getClientRects()].map((x) => Math.round(x.top))).size; };
  const rows = [...document.querySelectorAll('.q2__rh')].map((th) => { const logo = th.parentElement.querySelector('.q2__logo');
    return [lines(th), logo ? R(th).top + parseFloat(getComputedStyle(th).paddingTop) - R(logo).top : 0]; });
  return {col0, want, rows, cols: [...document.querySelectorAll('.q2__ch')].map(lines)}; }"""
# Each logo's box, against the template's formula on the page's own --A, --k, --ar and --trim (§13).
LOGOS = """() => { const A = parseFloat(getComputedStyle(document.querySelector('.q2')).getPropertyValue('--A'));
  return [...document.querySelectorAll('.q2__logo')].map((l) => { const s = getComputedStyle(l), v = (n) => parseFloat(s.getPropertyValue(n));
    const h = Math.sqrt(A * v('--k') / v('--ar')) * v('--trim'), r = l.getBoundingClientRect();
    return [l.className.split('--')[1], [r.width, r.height], [h * v('--ar'), h], A]; }); }"""


def map_checks(H):
    """T's map group. The quadrants, header labels and names are brief.json's; the row-header column is the
    page's measured --q2-c0 (T typed 136); each logo box is the template's formula on the page's own values
    (T typed seven sizes from 30 §13)."""
    a = H.B.b["map"]
    for eng in H.engines:
        pg = H.page(1440, 900, eng=eng)
        one = H.ev(pg, """() => [document.querySelectorAll('figure.q2').length, !!document.querySelector('.rv__pill, #rv, [data-map], .q2__tick, .q2__xname'),
          [...document.querySelectorAll('.q2 th, .q2 td')].filter((c) => /^(Yes|No)$/.test(c.textContent.trim())).length]""")
        H.ok(f"map.one {eng}", one == [1, False, 0], f"figures {one[0]}, toggle or tick left {one[1]}, Yes/No cells {one[2]}")
        H.ok(f"map.quadrants {eng}", not judge_map_quadrants(H.ev(pg, QD), H.B.b), f"{H.ev(pg, QD)}, want {H.B.quadrants()}")
        snap = pg.locator("#vT-map table").aria_snapshot()
        bad = judge_map_a11y(snap, [a[ax][k] for ax in ("across", "down") for k in ("yes", "no")],
                             [H.B.co[x["company"]] for x in a["answers"]])
        H.ok(f"map.a11y {eng}", not bad, f"{'; '.join(bad) or 'missing []'}; " + snap.replace("\n", " | ")[:200])
        h = H.ev(pg, MAP_HEAD)
        H.ok(f"map.headers {eng} 1440", not judge_map_headers(h),
             f"row-header column {h['col0']}, --q2-c0 {h['want']}; row header lines and cap-top minus logo-ink-top {h['rows']}; column header lines {h['cols']}")
        x = H.ev(pg, """() => { const s = (q) => getComputedStyle(document.querySelector(q));
          return [s('.q2__cell--tr').borderLeftWidth + ' ' + s('.q2__cell--tr').borderLeftColor, s('.q2__cell--bl').borderTopColor,
                  s('.q2__cell--tl').backgroundColor, s('.q2__t').borderTopWidth, s('.q2__mono').backgroundColor]; }""")
        H.ok(f"map.cross {eng}", x == ["1px rgb(138, 143, 148)", "rgb(138, 143, 148)", "rgba(0, 0, 0, 0)", "0px", "rgb(26, 28, 30)"], f"{x}")
        pg.context.close()
        pg = H.page(390, 844, touch=True, eng=eng)
        r = H.ev(pg, """() => [...document.querySelectorAll('.q2__t tbody tr')].map((tr) => { const th = tr.querySelector('.q2__rh').getBoundingClientRect();
          const cells = [...tr.querySelectorAll('.q2__cell')].map((c) => c.getBoundingClientRect());
          return [Math.round(th.width - tr.getBoundingClientRect().width), cells.every((c) => c.top >= th.bottom - 0.5)]; })""")
        H.ok(f"map.headers {eng} 390", r == [[0, True], [0, True]], f"(row header width minus row width, above its pair) {r}")
        pg.context.close()
        for w, A in ((1440, 1800), (390, 1200)):  # the template's --A per width (§13)
            p4 = H.page(w, 900, eng=eng)
            got = H.ev(p4, LOGOS)
            off = [(s, [round(v, 1) for v in box], [round(v, 1) for v in want_]) for s, box, want_, a_ in got
                   if a_ != A or abs(box[0] - want_[0]) > 1.5 or abs(box[1] - want_[1]) > 1.5]
            H.ok(f"map.logo boxes {eng} {w}", got and not off, f"{len(got)} logos at --A {A}; off by more than 1.5 {off}")
            p4.context.close()


GROUPS = [head, page_bounds, layout, rhythm, title, bar, footer, states, print_and_head, focus_order, focus_matrix,
          fonts, butterick, chip_look_and_cells, map_checks]


# ---- --selftest: T's mutant pattern (T:verify-t.py:70), offline. Each red case mutates one input and must
# red its judge, naming the fault; remove a check and its mutant goes green, so the selftest reds. ----

_QB = {"company": {"slug": "k", "name": "Kiwi Grid"}, "rivals": [{"slug": "c", "name": "Calder's Grid"}],
       "map": {"answers": [{"company": "c", "across": {"answer": "yes"}, "down": {"answer": "yes"}}]}}


def _page_facts(vw, *els, sw=None):
    base = dict(sel="p", l=16, r=vw - 16, scroller=False, clip=None, ellipsis=False)
    return {"vw": vw, "sw": sw or vw, "els": [dict(base, **e) for e in els]}


def selftest():
    import contextlib, io
    fx = ROOT / "tools/fixtures/web"
    with tempfile.TemporaryDirectory() as d:
        root = Path(d) / "run"
        shutil.copytree(fx / "synthetic", root)
        shutil.copyfile(fx / "synthetic.json", root / "brief.json")
        with contextlib.redirect_stdout(io.StringIO()):
            code = WEBPY.build(root, root / "brief.json", "n1", browser=False, subset=False)
        if code != 0:
            print(f"SELFTEST FAIL: the synthetic page did not render offline (exit {code})")
            return 1
        B = Brief(root)
        # G34: two harnesses on the default port both serve; a fixed default would fail the second bind.
        hs = [Harness(B), Harness(B)]
        try:
            for h in hs:
                h.start()
            ports = sorted({h.port for h in hs})
            both = len(ports) == 2 and 0 not in ports
        except OSError as e:
            both, ports = False, str(e)
        finally:
            for h in hs:
                if h.server:
                    h.server.shutdown()
                    h.server.server_close()
        print(f"{'ok  ' if both else 'FAIL'} green two default harnesses serve side by side (port 0): {ports}")
        if not both:
            return 1
    src, url, robots = B.src, B.url, '<meta name="robots" content="noindex">'
    canon, og = f'<link rel="canonical" href="{url}">', f'<meta property="og:url" content="{url}">'
    wrong = f"{WEBPY.SITE}/{WEBPY.FRAMINGS['t']['path']}"
    cases = [  # (name, judge, input, the failure's first word, or None for green)
        ("the synthetic page's head", judge_head, (src, url), None),
        ("noindex removed", judge_head, (src.replace(robots, ""), url), "noindex"),
        ("robots says index", judge_head, (src.replace(robots, robots.replace("noindex", "index")), url), "noindex"),
        ("canonical off the brief's slug", judge_head, (src.replace(canon, canon.replace(url, wrong)), url), "canonical"),
        ("og:url off the brief's slug", judge_head, (src.replace(og, og.replace(url, wrong)), url), "og:url"),
        ("a matrix at 800 px that shows every column", judge_matrix, (800.0, False), None),
        ("a matrix that scrolls at 1440", judge_matrix, (800.0, True), "the matrix scrolls"),
        ("a matrix off 800 px", judge_matrix, (780.0, False), "width"),
        ("a page in its box, a wide table in its scroller", judge_bounds,
         (_page_facts(390, {}, {"sel": "td", "l": 300, "r": 900, "scroller": True}),), None),
        ("a cell outside its scroller", judge_bounds, (_page_facts(390, {"sel": "td", "l": 300, "r": 420}),), "1 element(s) outside"),
        ("an element left of the page", judge_bounds, (_page_facts(390, {"sel": "h1", "l": -8, "r": 300}),), "1 element(s) outside"),
        ("the page scrolls sideways", judge_bounds, (_page_facts(390, {}, sw=420),), "the page scrolls"),
        ("text clipped by overflow: hidden", judge_bounds, (_page_facts(390, {"sel": "h1", "clip": [300, 280, 30, 30]}),), "1 element(s) clipped"),
        ("text cut by an ellipsis", judge_bounds, (_page_facts(390, {"sel": "p", "ellipsis": True}),), "1 element(s) clipped"),
        ("every name hyphens: manual (G65)", judge_names, (["manual", "manual"],), None),
        ("a name that hyphenates (the .name rule gone)", judge_names, (["manual", "auto"],), "1 of 2"),
        ("no name wrapped (the web.py wrap gone)", judge_names, ([],), "no .brief .name"),
        ("a map header or name typed with ' matches the page's ’ (G71)", judge_map_a11y,
         ('- columnheader "Maker’s pick"\n- columnheader "No"\n- rowheader "Who’s in"\n- rowheader "No"\n- button "Kiwi’s Grid"',
          ["Maker's pick", "No", "Who's in", "No"], ["Kiwi's Grid"]), None),
        ("a map header missing from the table", judge_map_a11y,
         ('- columnheader "No"\n- rowheader "Yes"\n- rowheader "No"\n- button "Coopélec"',
          ["Maker's pick", "No", "Yes", "No"], ["Coopélec"]), "missing"),
        ("a cohort name typed with ' sits in its quadrant as the page's ’ (G71)", judge_map_quadrants,
         ({"tl": ["Calder’s Grid"], "tr": [], "bl": [], "br": []}, _QB), None),
        ("a cohort name missing from its quadrant", judge_map_quadrants,
         ({"tl": [], "tr": [], "bl": [], "br": []}, _QB), "quadrants"),
        ("map row headers on two lines each, T's map", judge_map_headers,
         ({"col0": 140, "want": 140, "rows": [[2, 0], [2, -0.5]], "cols": [1, 1]},), None),
        ("a short row header on one line (W18's, G71)", judge_map_headers,
         ({"col0": 140, "want": 140, "rows": [[1, 0], [2, -0.5]], "cols": [1, 1]},), None),
        ("a row header on three lines (W6's WebKit defect)", judge_map_headers,
         ({"col0": 140, "want": 140, "rows": [[3, 0], [2, -0.5]], "cols": [1, 1]},), "lines"),
        ("a row header's cap-top 2 px off its logo", judge_map_headers,
         ({"col0": 140, "want": 140, "rows": [[2, 2], [2, -0.5]], "cols": [1, 1]},), "cap-top"),
        ("a row-header column 2 px off --q2-c0", judge_map_headers,
         ({"col0": 142, "want": 140, "rows": [[2, 0], [2, -0.5]], "cols": [1, 1]},), "width"),
        ("a column header on two lines", judge_map_headers,
         ({"col0": 140, "want": 140, "rows": [[2, 0], [2, -0.5]], "cols": [2, 1]},), "columns"),
    ]
    if not all(s in src for s in (robots, canon, og)):
        print("SELFTEST FAIL: a mutation target is missing from the synthetic page's head")
        return 1
    failed = []
    for name, judge, args, want in cases:
        got = judge(*args)
        good = (not got) if want is None else any(g.startswith(want) for g in got)
        print(f"{'ok  ' if good else 'FAIL'} {'green' if want is None else 'red  '} {name}" + ("" if good else f": got {got}"))
        if not good:
            failed.append(name)
    if failed:
        print(f"SELFTEST FAIL: {failed}")
        return 1
    print(f"SELFTEST OK ({sum(c[3] is not None for c in cases)} red, {sum(c[3] is None for c in cases) + 1} green)")
    return 0


def main(argv=None, groups=GROUPS, prog="web-check", doc=__doc__, offline=selftest):
    """web-check's command line; `groups` lets a caller pass its own groups."""
    ap = argparse.ArgumentParser(prog=prog, description=doc.split("\n")[0])
    ap.add_argument("root", nargs="?", help="BRIEF_ROOT: brief.json, claims.jsonl and the rendered web/")
    ap.add_argument("--only", default="", help="comma-separated group names")
    ap.add_argument("--engine", choices=ENGINES, help="one engine; default both")
    ap.add_argument("--width", type=int, choices=WIDTHS, help="one width; default all three")
    ap.add_argument("--port", type=int, default=0, help="default 0: a free port the system picks")
    if offline:
        ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if offline and a.selftest:
        return offline()
    if not a.root:
        ap.error("BRIEF_ROOT is required")
    try:
        brief = Brief(a.root)
    except (OSError, ValueError, KeyError) as e:
        print(f"{prog}: unreadable input: {e}", file=sys.stderr)
        return 2
    H = Harness(brief, a.port, a.only, [a.engine] if a.engine else ENGINES, [a.width] if a.width else WIDTHS)
    try:
        H.start()
    except OSError as e:
        print(f"{prog}: cannot serve {brief.web} on port {a.port}: {e}", file=sys.stderr)
        return 2
    try:
        H.run(groups)
    finally:
        H.close()
    return H.finish()


if __name__ == "__main__":
    sys.exit(main())
