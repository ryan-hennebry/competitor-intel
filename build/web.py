#!/usr/bin/env python3
"""The page renderer: a run's brief.json, and the run it cites, to one self-contained web page.

WHY THIS EXISTS. Stage 7 writes data; no agent writes HTML (73-web-plan.md § The contract, W5
:127-151). This file began as a copy of T:build-t.py, with every constant typed for one cohort
deleted. Each became a read of brief.json, sources.tsv or logos/logos.json, or a count
derived from them. The page's anatomy lives in build/web/template.html.

INPUTS, all under BRIEF_ROOT: brief.json (or --brief), claims.jsonl, pages/index.tsv, snapshots/,
sources.tsv (url, label), logos/logos.json and its files. OUTPUTS: $BRIEF_ROOT/web/, the unit stage
11 stages (index.html, its subset font, icons, og.png: N1's per brief, T's shared; logos are inlined), $BRIEF_ROOT/audit/
gate-NN.txt (the next free NN, build/build.py's convention) and audit/page-text.md (--text's text).

Usage:
  python3 build/web.py [BRIEF_ROOT] [--brief PATH] [--framing n1|t]
  python3 build/web.py --text PAGE.html    the page's words: blocks in reading order, one per line,
                                           then card lines, then accessible names (T's lint text)
  python3 build/web.py --text BRIEF.json --authored
                                           the authored words only, one block per line, no template
                                           string (G28): what stage 7's text checks read
  python3 build/web.py --card BRIEF_ROOT --out PNG
                                           the run's share card alone
  python3 build/web.py --selftest          offline, no browser, stdlib only
Framing n1 is the default (43-rulings.md:125-135). Framing t is T's banner, title and address, kept
so a T fixture's render can be graded against live T.
Exit: 0 every gate held; 1 a gate failed; 2 bad usage or an unreadable input.
"""
import argparse, base64, csv, hashlib, html, importlib.util, json, re, shutil, struct, subprocess
import sys, tempfile
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "build/web"
TEMPLATE = WEB / "template.html"
ASSETS = WEB / "assets"
SCHEMA = WEB / "brief.schema.json"
# The OFL master: @ibm/plex-sans-variable 0.2.0 fonts/complete/woff2/IBM Plex Sans Var-Roman.woff2
# (T:research/25-variant-q-spec.md:213), cut to Latin, Latin Extended and T's own extra characters,
# all features, axes and hinting kept. A TrueType file, so --selftest reads its cmap with struct.
FONT_MASTER = ASSETS / "plex-sans-var-latin.ttf"
FONT_LICENCE = ASSETS / "OFL-IBMPlexSans.txt"
FONT_OUT = "fonts/plex-sans-var.woff2"
LAYOUT_FEATURES = "kern,liga,calt,ccmp,locl,mark,mkmk,case,sups,numr,dnom,frac,lnum,pnum,tnum"  # T's 25§5
ICONS = ("favicon-p.svg", "favicon-32.png", "apple-touch-icon.png", "in-the-loop-mark.svg", "og.png")
LOGOS_JSON = "logos/logos.json"

# The operator's own links and words, the same on every page.
SITE = "https://ryanhennebry.xyz"
REPO = "https://github.com/ryan-hennebry/competitor-intel"
LINKEDIN = "https://www.linkedin.com/in/ryanhennebry"
DESC = "Written by Ryan Hennebry’s competitor intelligence agent. Each finding cites the page it came from."
FRAMINGS = {
    # N1: a company's own page carries no banner and its own title. Its address is brief.json's
    # company.slug with a trailing slash (D10): the path the site serves with a 200, so canonical,
    # og:url and the link publish prints are one string. T keeps the address the site pins for it.
    "n1": {"banner": False, "title": "Competitor intel brief: {name}", "alt": "Competitor intel brief: {name}.",
           "path": "{slug}/"},
    "t": {"banner": True, "title": "Competitor intelligence agent: example brief",
          "alt": "Competitor intelligence agent: example brief.", "path": "competitor-intel-agent"},
}

# The card's evidence lead-ins (T:build-t.py:676-679). A quote shows only from an en row with no
# gloss; any other row shows its gloss after the lead its state and language give.
LEAD_UNFOUND, LEAD_PARA, LEAD_LANG = "Searched, not found:", "Paraphrased:", "Paraphrased from {}:"
LEAD_BLOCKED = "Could not read:"  # a blocked row's page refused the fetch, so it has no words to quote
LANGS = {"fr": "French", "de": "German", "es": "Spanish", "it": "Italian", "nl": "Dutch", "pt": "Portuguese",
         "sv": "Swedish", "da": "Danish", "nb": "Norwegian", "no": "Norwegian", "fi": "Finnish", "pl": "Polish",
         "cs": "Czech", "ca": "Catalan", "ja": "Japanese", "zh": "Chinese", "ko": "Korean"}
# 36 R3: a row whose quote names a maker only as an integration reads against its answer line unless
# this lead says so. The answer's `integration` list names those rows (W2-rulings.md G10); nothing infers it.
INTEG = "An integration, not named as a customer:"
NUMBER_WORDS = ("one", "two", "three", "four", "five", "six")  # the schema caps rivals at six
TAGS = {"act": ("t-high", "Act."), "watch": ("t-watch", "Watch.")}
MOVES_HEAD = ("Company", "Change or silence", "What it means and action")
MATRIX_CORNER = "Terms"
NT_ATTRS = ' target="_blank" rel="noopener" aria-describedby="nt"'
MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
DATE_SPACES_RE = re.compile(rf"\b(\d{{1,2}}) ((?:{MONTHS})[a-z]*)\b(?: (\d{{4}})\b)?")
# A quote the page cannot show as words: a page fragment, which the row's gloss replaces
# (`references/methodology.md` gloss row). `](` is a Markdown link's seam (G34).
QUOTE_FRAGMENTS = ("{", "[img", "|", '"', "](")


def quote_is_fragment(q):
    """The fragment test, written once: the card shows the row's gloss instead of this quote.
    claims-check.py L19 runs it at stage 4, so an owed gloss is caught before any page (G38)."""
    return not str(q).strip() or any(s in q for s in QUOTE_FRAGMENTS)


def bind_dates(t):
    """22f10: a day, month and year never break across lines. Every printed text takes it: prose,
    a gloss, and a card's quote (G34), since binding a date's spaces changes no word."""
    # A day and month without a year binds too ("From 19 October"): web-check's pt.marks reads any
    # day-month pair as one unit (vandelay run 2).
    return DATE_SPACES_RE.sub(lambda m: m.group(1) + "&nbsp;" + m.group(2)
                              + ("&nbsp;" + m.group(3) if m.group(3) else ""), t)


def text_of(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s))


def curl(t):
    """§2, 32 F10, G71: a straight ' between two letters becomes ’. The renderer owns the page's
    typography, so an agent types ASCII. A ' this cannot place stays straight; in a shown quote it
    fails the build. G72: a plural possessive's s' before a word boundary ("drivers'") becomes ’ too,
    inside an open ‘ as well (G76): ’ is both the apostrophe and the closing quote, so it is right either way."""
    t = re.sub(r"(?<=[^\W\d_])'(?=[^\W\d_])", "’", t)
    # vandelay run 2: "IRIS Inc.'s" and a headline quoted in its quote, "'The pipes are leaky':".
    t = re.sub(r"(?<=[.\d])'(?=[^\W\d_])", "’", t)  # an apostrophe after a full stop or a digit
    t = re.sub(r"(?:^|(?<=\s))'(?=\d)", "’", t)  # an elision before digits: the ’90s
    t = re.sub(r"(?:^|(?<=[\s(\[—–]))'(?=[^\W\d_])", "‘", t)  # an opening quote at the start or after a space
    t = re.sub(r"(?<=s)'(?!\w)", "’", t)
    if "‘" in t:  # a closing quote after an opening one: ’ is right either way (G76)
        t = re.sub(r"(?<=[\w.,!?])'(?!\w)", "’", t)
    return t


def esc(t):
    """Every string the page prints passes here, so every one is curled (G71)."""
    return html.escape(curl(t), quote=False)


def ids(c):
    return [] if c is None else [c] if isinstance(c, str) else list(c)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def slug_id(t):
    """An h2's id, as T made it."""
    return "vT-" + re.sub(r"[^a-z0-9]+", "-", html.unescape(t).lower().replace("’", "")).strip("-")


def page_url(brief, framing="n1"):
    """The page's one address, its canonical and og:url: SITE/<company.slug>/ for a brief (D10), so a
    scratch replay is a brief whose slug is globex-replay, never a flag that could desync the head."""
    return f"{SITE}/" + FRAMINGS[framing]["path"].format(slug=brief["company"]["slug"])


def og_image_url(site_url, png):
    """og:image: the page's own og.png, its ?v= the first 12 hex of the card's sha256, so a changed
    card is always a new URL. With no card drawn (no browser) it says so, and publish refuses it."""
    return site_url.rstrip("/") + "/og.png?v=" + (sha(png)[:12] if png else "unrendered")


def on_text(s, fn):
    """Apply fn to text between tags only, never inside a tag or a ref."""
    return "".join(p if p[:1] in ("<", "\x00") else fn(p) for p in re.split("(<[^>]+>|\x00[^\x01]*\x01)", s))


def name_spans(names):
    """G65: a cohort or client name never hyphenates, whatever its case: Chrome splits "ev.en-ergy" though
    it leaves capitalised words whole. Each name, verbatim from brief.json, and its possessive go in one
    span.name, which template.html sets to hyphens: manual. A name inside a URL, a host or a longer word stays
    bare; one joined to an authored hyphen ("ev.energy-led") is wrapped, since Chrome splits it too (G69)."""
    forms = sorted({esc(n) for n in names if n}, key=len, reverse=True)
    rx = re.compile(r"(?<![\w./@])(?:" + "|".join(map(re.escape, forms)) + r")(?:[’']s)?(?![\w/@]|\.\w)")
    return lambda t: rx.sub(lambda m: f'<span class="name">{m.group(0)}</span>', t)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BC = load_module("brief_check", ROOT / "tools/brief-check.py")  # logo_gate, rule_S: written once there
def cmap_of(path):
    """The code points a TrueType file maps, read with struct alone: the CI runner has no fontTools."""
    data = Path(path).read_bytes()
    tables = {data[12 + 16 * i:16 + 16 * i]: struct.unpack(">I", data[20 + 16 * i:24 + 16 * i])[0]
              for i in range(struct.unpack(">H", data[4:6])[0])}
    off, cps = tables[b"cmap"], set()
    for i in range(struct.unpack(">H", data[off + 2:off + 4])[0]):
        s = off + struct.unpack(">I", data[off + 8 + 8 * i:off + 12 + 8 * i])[0]
        fmt = struct.unpack(">H", data[s:s + 2])[0]
        if fmt == 4:
            seg2 = struct.unpack(">H", data[s + 6:s + 8])[0]
            n, ro = seg2 // 2, s + 16 + 3 * seg2
            ends = struct.unpack(f">{n}H", data[s + 14:s + 14 + seg2])
            starts = struct.unpack(f">{n}H", data[s + 16 + seg2:s + 16 + 2 * seg2])
            deltas = struct.unpack(f">{n}h", data[s + 16 + 2 * seg2:ro])
            offs = struct.unpack(f">{n}H", data[ro:ro + seg2])
            for k in range(n):
                for c in range(starts[k], ends[k] + 1):
                    if offs[k]:
                        p = ro + 2 * k + offs[k] + 2 * (c - starts[k])
                        g = struct.unpack(">H", data[p:p + 2])[0]
                        g = (g + deltas[k]) & 0xFFFF if g else 0
                    else:
                        g = (c + deltas[k]) & 0xFFFF
                    if g and c != 0xFFFF:
                        cps.add(c)
        elif fmt == 12:
            for k in range(struct.unpack(">I", data[s + 12:s + 16])[0]):
                a, b, _ = struct.unpack(">III", data[s + 16 + 12 * k:s + 28 + 12 * k])
                cps.update(range(a, b + 1))
    return cps


class Words(HTMLParser):
    """T's lint text (T:build-t.py:1029-1105, unchanged): the page's words in DOM order, one block
    per line, table rows as prose lines; then every card line; then every accessible name."""
    BLOCK = {"p", "li", "h1", "h2", "tr", "legend", "button", "title", "figure", "ul", "ol", "caption",
             "section", "footer", "nav", "div", "header", "main", "article", "table"}
    VOID = {"br", "img", "input", "col", "meta", "link", "hr", "source", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines, self.names, self.cards, self.cur, self.skip, self.depth, self.side = [], [], [], "", 0, 0, []
        self.open = []  # each open element's classes, so an end tag knows what it closes

    def flush(self):
        if self.cur.strip() and not self.side:
            self.lines.append(re.sub(r"\s+", " ", self.cur).strip())
        if not self.side:
            self.cur = ""

    def side_flush(self):
        d, mode, buf = self.side[-1]
        text = re.sub(r"\s+", " ", buf).strip().strip(",").strip()
        if text and mode in ("names", "cards"):
            getattr(self, mode).append(text)
        self.side[-1][2] = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get("class") or "").split()
        if tag in ("script", "style", "head"):
            self.skip += 1
        for k in ("aria-label", "alt"):
            if a.get(k):
                self.names.append(a[k])
        if tag in self.VOID:
            if tag == "br":
                self.feed_text(" ")
            return
        self.depth += 1
        self.open.append(cls)
        if self.side and self.side[-1][1] == "cards" and any(c.startswith("card__") and c != "card__lead" for c in cls):
            self.side_flush()
        mode = ("drop" if {"pn", "chip", "cite__n"} & set(cls) else "cards" if "card" in cls
                else "names" if "sr-only" in cls or "hidden" in a else None)
        if mode and not (self.side and self.side[-1][1] in ("drop", "cards")):
            self.side.append([self.depth, mode, ""])
        elif tag in self.BLOCK and "cite" not in cls:  # a cell trigger's value stays in its row's line
            self.flush()
        if tag in ("td", "th") and self.cur.strip() and not self.side:
            self.cur += ", "

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head"):
            self.skip -= 1
        if tag in self.VOID:
            return
        cls = self.open.pop() if self.open else []
        if self.side and self.side[-1][1] == "cards" and any(c.startswith("card__") and c != "card__lead" for c in cls):
            self.side_flush()
        if self.side and self.side[-1][0] == self.depth:
            self.side_flush()
            self.side.pop()
        elif tag in self.BLOCK and "cite" not in cls:
            self.flush()
        self.depth -= 1

    def feed_text(self, data):
        if self.side:
            self.side[-1][2] += data
        else:
            self.cur += data

    def handle_data(self, data):
        if not self.skip:
            self.feed_text(data)


def page_text(src):
    """--text: T's lint text for any page, live T's included."""
    w = Words()
    w.feed(src)
    w.flush()
    triggers = [re.sub(r"\s+", " ", text_of(m)).strip()
                for m in re.findall(r'<button class="(?:chip|cite|q2__co)"[^>]*>(.*?)</button>', src, re.S)]
    return "\n\n".join(w.lines + w.cards + sorted(set(w.names + triggers))) + "\n"


def template_text(src):
    """--text PAGE --template (W2-rulings.md G49): the page lines its template prints, and only
    those: every line of template.html's own text, the page's h1 and run line, each table's header
    row, and the INTEG lead. Never a brief.json word, a claim's text or a source line. A critic's
    quote inside one of these lines is a template string, which critique-check may close as
    `ruled@template`."""
    def lines(html_src):
        return [ln for ln in page_text(html_src).split("\n") if ln.strip()]
    out = lines(TEMPLATE.read_text(encoding="utf-8"))
    out += [ln for f in re.findall(r'<h1>.*?</h1>|<p class="run">.*?</p>', src, re.S) for ln in lines(f"<div>{f}</div>")]
    # The two header rows the template types: the moves table's (MOVES_HEAD) and the matrix's, which
    # opens on MATRIX_CORNER before the companies' printed names. The map's header row is authored.
    heads = [ln for f in re.findall(r"<thead\b.*?</thead>", src, re.S) for ln in lines(f"<div>{f}</div>")]
    out += [ln for ln in heads if ln.split(" , ")[0] in (MATRIX_CORNER, MOVES_HEAD[0])]
    return "\n\n".join(dict.fromkeys(out + [INTEG])) + "\n"


def authored_text(b):
    """--text --authored (W2-rulings.md G28): the brief's authored words only, in page order, one
    block per line, blank-line separated, with no template string. A q span keeps the curly quotes
    the page prints, so claims-check's B4 sees it; a g span prints without the template's language
    lead. Stage 7's text checks read this, so a template numeral (the run line, a "source N" name)
    never reaches B1: the template is certified once, not per brief."""
    def j(arr):
        return "".join("“" + x["t"] + "”" if x.get("q") else x["t"] for x in arr).strip()
    out = [j(p["lede"]) + " " + j(p["body"]) for p in b["quick_take"]]  # one paragraph, one space at the seam (G71)
    m = b["map"]
    for ax in ("across", "down"):
        out += [m[ax]["question"], m[ax]["yes"], m[ax]["no"]]
    out += [a[ax]["name"] for a in m["answers"] for ax in ("across", "down") if a[ax].get("name")]
    for r in b["recommendations"]:
        out += [j(r["test"]), j(r["why"]), j(r["next_step"])]
    out.append(b["moves_heading"])
    for mv in b["moves"]:
        out += [j(mv["change"]), j(mv["meaning"])]
    mx = b["matrix"]
    out.append(mx["heading"])
    for row in mx["rows"]:
        out += [row["label"]] + [c["t"] for c in row["cells"]]
    out.append(j(mx["legend"]))
    out += [j(q) for q in b["open_questions"]]
    return "\n\n".join(re.sub(r"\s+", " ", t).strip() for t in out if t and t.strip()) + "\n"


# The brief.json keys whose strings are not authored words: IDs, slugs, files, dates, enums, and the
# entities' names, which the template prints. Every other string is the author's (G34).
NOT_AUTHORED = {"c", "slug", "snapshot", "logo", "run_date", "columns", "serves", "rival", "date", "action",
                "answer", "mark", "company", "rivals", "integration",
                "id", "cmp", "slot", "metric", "domain", "jd_url", "role", "dates"}


# The brief.json keys the page never prints as text (G71's straight-' gate skips them). The second
# line is the typed keys (design.md § 3): span ids and pointers, slots, metrics, the run's own facts.
NOT_PRINTED = {"c", "slug", "snapshot", "logo", "run_date", "columns", "serves", "rival", "date", "action",
               "answer", "mark", "integration",
               "id", "cmp", "slot", "metric", "domain", "jd_url", "role", "dates"}


def authored_strings(b):
    """Every authored string in a brief.json, found by walking it, not by naming fields: a span array
    joined as the page joins it, a q span in its curls; any other string as it stands."""
    out = []

    def walk(node):
        if isinstance(node, list) and node and all(isinstance(x, dict) and "t" in x and "mark" not in x for x in node):
            out.append(re.sub(r"\s+", " ", "".join("“" + x["t"] + "”" if x.get("q") else x["t"] for x in node)).strip())
        elif isinstance(node, list):
            for x in node:
                walk(x)
        elif isinstance(node, dict):
            for k, v in node.items():
                if k not in NOT_AUTHORED:
                    walk(v)
        elif isinstance(node, str) and node.strip():
            out.append(re.sub(r"\s+", " ", node).strip())
    walk(b)
    return out


def page_chars(src):
    """Every character the page can set in its face: its text, less scripts, styles and comments, plus
    the strings its CSS draws with content:."""
    styles = " ".join(re.findall(r'content:\s*"([^"]*)"', src))
    body = re.sub(r"<(script|style)\b.*?</\1>|<!--.*?-->", "", src, flags=re.S)
    return {c for c in html.unescape(re.sub(r"<[^>]+>", "", body)) + styles if c not in "\n\r\t"}
def read_inputs(root, brief_path):
    """Everything the page reads from the run. An unreadable required file is exit 2."""
    root = Path(root)
    try:
        brief = json.loads(Path(brief_path).read_text(encoding="utf-8"))
        ledger = [json.loads(ln) for ln in (root / "claims.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
        pages = list(csv.DictReader((root / "pages/index.tsv").open(encoding="utf-8"), delimiter="\t"))
        snaps = {p.name: p.read_text(encoding="utf-8") for p in sorted((root / "snapshots").glob("*.json"))}
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"FAIL: cannot read the run at {root}: {exc}\n")
        raise SystemExit(2)
    labels = {}
    if (root / "sources.tsv").is_file():
        labels = {r["url"]: r["label"] for r in csv.DictReader((root / "sources.tsv").open(encoding="utf-8"), delimiter="\t")}
    logos = {}
    if (root / LOGOS_JSON).is_file():
        logos = {r.get("slug"): r for r in json.loads((root / LOGOS_JSON).read_text(encoding="utf-8"))}
    return dict(root=root, brief_path=Path(brief_path), brief=brief, ledger=ledger, pages=pages, snaps=snaps,
                labels=labels, logos=logos, template=TEMPLATE.read_text(encoding="utf-8"))


def render(inp, framing="n1", measured=None, og_png=None):
    """The page, or the reasons there is none: {"src", "errors", "log", ...}. T's steps, in T's order.
    og_png is the card's bytes, drawn before the fill so og:image carries their hash."""
    errors, log = [], []
    E = errors.append
    root, b, ledger = inp["root"], inp["brief"], inp["ledger"]
    claims = {r["id"]: r for r in ledger}
    snap_text = "\n".join(inp["snaps"].values())
    ok = [p for p in inp["pages"] if p.get("status") in ("200", "000")]
    ok_urls = {p["url"] for p in ok}
    # A page read only to locate a logo (logos.json's page_url) backs no claim and no span, so its
    # fetch date is not the run's; a span reaches a page only through its claim's URL (the operator, 2026-10-12).
    backs = {c.get("url") for c in ledger}
    logo_only = {r.get("page_url") for r in inp["logos"].values()} - backs
    days = {p["fetched_at"][:10] for p in ok if p["url"] not in logo_only or p.get("final_url") in backs}
    dates = b.get("dates")
    if dates:  # D4: the evidence window is the counted pages' fetch days, first to last; a run may cross midnight
        ev = dates["evidence"]
        run_d, run_to = date.fromisoformat(ev["from"]), date.fromisoformat(ev["to"])
        if not days or (min(days), max(days)) != (ev["from"], ev["to"]):
            E(f"evidence dates: counted pages were fetched on {sorted(days)}; brief.json's dates.evidence is "
              f"{ev['from']} to {ev['to']}")
    else:
        run_d = run_to = date.fromisoformat(b["run_date"])
        if days != {b["run_date"]}:  # the run line names one date (T:build-t.py:56-60)
            E(f"run date: counted pages were fetched on {sorted(days)}; brief.json's run_date is {b['run_date']}")
    co, rivals = b["company"], b["rivals"]
    ents = [co] + rivals
    by_slug = {e["slug"]: e for e in ents}

    def shown(e):
        return e.get("short") or e["name"]

    for e in ents:  # PROV: each name verbatim from its own site, so its snapshot carries it as its name
        snap = inp["snaps"].get(e["snapshot"])
        name = json.loads(snap).get("name") if snap else None
        if name != e["name"]:
            E(f"{e['slug']}: name {e['name']!r} is not snapshots/{e['snapshot']}'s name ({name!r})")

    def claim_ok(cid, where):
        """A claim must exist, carry a URL, and that URL must be in a snapshot."""
        c = claims.get(cid)
        if not c:
            E(f"{where}: {cid} is not in claims.jsonl")
        elif not c.get("url"):
            E(f"{where}: {cid} has no URL")
        elif c["url"] not in snap_text:
            E(f"{where}: {cid}'s URL is in no snapshot: {c['url']}")
        else:
            return True
        return False

    # G71: a ' curl() cannot place ("'90s") would print straight, so the build fails naming the field.
    # A span array is read joined, as spans() curls it; keys the page never prints are skipped.
    def straight(node, path):
        if isinstance(node, list) and node and all(isinstance(x, dict) and "t" in x and "mark" not in x for x in node):
            node = "".join(x["t"] for x in node)
        if isinstance(node, str):
            if "'" in curl(node):
                E(f"{path}: a straight ' curl() cannot place: {node.strip()[:60]!r}")
        elif isinstance(node, (list, dict)):
            for k, v in (node.items() if isinstance(node, dict) else enumerate(node)):
                if k not in NOT_PRINTED:
                    straight(v, f"{path}.{k}" if isinstance(k, str) else f"{path}[{k}]")
    straight(b, "brief")

    # 1. The template: its anatomy, and the brief's skeleton between the BRIEF markers.
    tpl = inp["template"]
    m_sk = re.search(r"<!--BRIEF\{-->\n(.*?)<!--\}BRIEF-->\n", tpl, re.S)
    if not m_sk:
        return dict(errors=["template: no <!--BRIEF{--> skeleton"], log=log)

    # 2. Spans to HTML, in the form T's markdown step produced: a claim ref \x00C-nnn\x01 closes each
    # run of spans that rest on the same claims, and the chip pass below moves it to its sentence end.
    def spans(arr, seam=False):
        """seam (G71): the field meets another at a seam the template owns, so its ends are stripped.
        ' is curled across the joined field, so a span boundary ("Northwind" + "'s") curls too."""
        ts = [s["t"] for s in arr]
        if seam and ts:
            ts[0] = ts[0].lstrip()
            ts[-1] = ts[-1].rstrip()
        whole, k, arr_ = curl("".join(ts)), 0, []
        for s, t in zip(arr, ts):
            arr_.append(dict(s, t=whole[k:k + len(t)]))
            k += len(t)
        arr, out = arr_, []
        for i, s in enumerate(arr):
            t = esc(s["t"])
            if s.get("q"):
                t = "“" + t + "”"
            if s.get("g"):
                rows = [claims.get(c, {}) for c in ids(s["c"])]
                lang = next((r.get("lang") for r in rows if r.get("lang") not in (None, "en")), None)
                if lang not in LANGS:
                    E(f"a gloss span names no language the page can print: {s['t'][:50]!r} ({lang!r})")
                lead = LEAD_LANG.format(LANGS.get(lang, lang))
                pre = re.match(r"\s*", t).group(0)
                t = pre + lead + " " + t[len(pre):]
            out.append(t)
            nxt = arr[i + 1] if i + 1 < len(arr) else None
            if s["c"] is not None and (nxt is None or nxt["c"] != s["c"]):
                out.append("".join(f"\x00{c}\x01" for c in ids(s["c"])))
        return "".join(out)

    # G71: the renderer owns the lede/body and test/why seams: one space, whatever the spans' ends.
    qt = "\n".join(f"<p><strong>{spans(p['lede'], True)}</strong> {spans(p['body'], True)}</p>" for p in b["quick_take"])
    recs = "\n".join(f'<p class="rec"><strong>{spans(r["test"], True)}</strong> {spans(r["why"], True)} '
                     f'<span class="next"><strong>Next&nbsp;step:</strong> {spans(r["next_step"])}</span></p>' for r in b["recommendations"])
    moves = ["<table>\n<thead>\n<tr>\n" + "".join(f"<th>{h}</th>\n" for h in MOVES_HEAD) + "</tr>\n</thead>\n<tbody>"]
    for mv in b["moves"]:
        cls, word = TAGS[mv["action"]]
        moves.append(f"<tr>\n<td>{esc(shown(by_slug[mv['rival']]))}</td>\n<td>{spans(mv['change'])}</td>\n"
                     f'<td>{spans(mv["meaning"])} <span class="{cls}">{word}</span></td>\n</tr>')
    moves.append("</tbody>\n</table>")
    mx = b["matrix"]
    head = "".join(f"<th>{'<strong>' + esc(shown(co)) + '</strong>' if s == co['slug'] else esc(shown(by_slug[s]))}</th>\n"
                   for s in mx["columns"])
    rows = []
    for r in mx["rows"]:
        cells = "".join(f"<td>{esc(c['t'])}{''.join(chr(0) + i + chr(1) for i in ids(c['c']))}</td>\n"
                        if c["mark"] == "cited" else f'<td class="mx-unk">{esc(c["t"])}</td>\n' for c in r["cells"])
        rows.append(f"<tr>\n<td>{esc(r['label'])}</td>\n{cells}</tr>")
    matrix = (f'<table class="mx-src">\n<thead>\n<tr>\n<th>{MATRIX_CORNER}</th>\n{head}</tr>\n</thead>\n<tbody>\n'
              + "\n".join(rows) + "\n</tbody>\n</table>")
    if mx["legend"]:
        matrix += f'\n<p class="mx-note">{spans(mx["legend"])}</p>'
    oq = "<ol>\n" + "\n".join(f"<li>{spans(q)}</li>" for q in b["open_questions"]) + "\n</ol>"
    body = m_sk.group(1)
    for slot, val in (("QUICK-TAKE", qt), ("MAP", "<p>@@FIGURE@@</p>"), ("RECOMMENDATIONS", recs),
                      ("MOVES-HEADING", esc(b["moves_heading"])), ("MOVES", "\n".join(moves)),
                      ("MATRIX-HEADING", esc(mx["heading"])), ("MATRIX", matrix),
                      ("OPEN-QUESTIONS", oq)):
        if body.count(f"<!--{slot}-->") != 1:
            E(f"template: the skeleton holds <!--{slot}--> {body.count(f'<!--{slot}-->')} times, want 1")
        body = body.replace(f"<!--{slot}-->", val)
    # Headings take their id from their words (T:build-t.py:259-261).
    body = re.sub(r"<h2>(.*?)</h2>", lambda m: f'<h2 id="{slug_id(m.group(1))}">{m.group(1)}</h2>', body)
    heads = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', body)
    # 22f10: a date is never split. "14 Sep 2026", "25 September 2025".
    body = on_text(body, bind_dates)
    for c in sorted({c for c in re.findall("\x00(C-\\d+)\x01", body)}):
        claim_ok(c, "span")
    # 3. Triggers. Each chip, cell or logo is first a placeholder \x02n\x03 naming a group of claims,
    # so print numbers can follow the finished DOM (§17) before any trigger is rendered.
    REF_RE = re.compile("\x00(C-\\d+)\x01")
    groups = []

    def group(kind, cids, **kw):
        groups.append(dict(kind=kind, cids=list(cids), **kw))
        return f"\x02{len(groups) - 1}\x03"

    def matrix_nowrap(t):  # a nowrap span keeps a hyphenated word whole with the face's own hyphen
        return on_text(t, lambda p: re.sub(r"\b(\w+(?:-\w+)+)\b", r'<span class="nw">\1</span>', p))

    def matrix_table(t):
        """§9: the whole value cell is the trigger, its number chip closing the value."""
        if len(re.findall(r"<tr>\s*<td>.*?</td>(.*?)</tr>", t, re.S)) != len(mx["rows"]):
            E(f"matrix: the table lost a row; want {len(mx['rows'])}")

        def cell(c):
            inner = c.group(1)
            cids = REF_RE.findall(inner)
            if not cids:
                E(f"matrix cell without a source: {text_of(inner)!r}")
                return c.group(0)
            return "<td>" + group("cell", cids, value=REF_RE.sub("", inner).strip()) + "</td>"
        t = matrix_nowrap(t)  # every hyphenated word, row labels included, before the values become triggers
        hd, _, rest = t.partition("</thead>")
        rest = re.sub(r"(?<=</td>)\s*<td>(.*?)</td>", cell, rest, flags=re.S)
        label = html.escape(mx["heading"] + ", scrolls sideways")
        return (f'<div class="tbl tbl--mx"><div class="mx scroller" role="region" tabindex="0" aria-label="{label}">'
                + (hd + "</thead>" + rest).replace('<table class="mx-src">', '<table class="matrix">', 1) + "</div></div>")

    def table(m):
        t = m.group(0)
        if t.startswith('<table class="mx-src">'):
            return matrix_table(t)
        cols = len(re.findall(r"<th[ >]", t.split("</thead>")[0]))
        # Explicit roles: below 40rem the rivals table reflows as a grid, and ARIA keeps it a table.
        t = (t.replace("<thead>", '<thead role="rowgroup">').replace("<tbody>", '<tbody role="rowgroup">')
             .replace("<tr>", '<tr role="row">').replace("<th>", '<th role="columnheader">').replace("<td>", '<td role="cell">'))
        return '<div class="tbl">' + t.replace("<table>", f'<table class="t{cols}" role="table">', 1) + "</div>"

    body = re.sub(r"<table[^>]*>.*?</table>", table, body, flags=re.S)
    n_cited = sum(c["mark"] == "cited" for r in mx["rows"] for c in r["cells"])
    if sum(g["kind"] == "cell" for g in groups) != n_cited:
        E(f"matrix: {sum(g['kind'] == 'cell' for g in groups)} cell triggers, want {n_cited}, one per cited cell")

    # 4. Chips (§8): a sentence's refs make one chip, after its closing punctuation. A sentence end is
    # . ? or !, an optional closing ” ’ or ), then whitespace, <br> or the block's end, read on text only.
    ATOM = re.compile(r"(<[^>]+>|\x00C-\d+\x01|&[#\w]+;|.)", re.S)
    unchipped = []

    def chip_block(inner, where):
        atoms = ATOM.findall(inner)
        kind = ["ref" if a[0] == "\x00" else "tag" if a[0] == "<" else "text" for a in atoms]
        flat = [(" " if re.match(r"<br\b", a) else "") if k == "tag" else "" if k == "ref" else html.unescape(a)
                for a, k in zip(atoms, kind)]
        txt = [i for i in range(len(atoms)) if flat[i]]
        ends, start = [], 0
        for j, i in enumerate(txt):
            if flat[i] not in ".?!":
                continue
            e, nx = i, j + 1
            if nx < len(txt) and flat[txt[nx]] in "”’)":
                e, nx = txt[nx], nx + 1
            if nx < len(txt) and not flat[txt[nx]].isspace():
                continue
            bnd = txt[nx] if nx < len(txt) else len(atoms)
            seg = atoms[start:e + 1]
            ends.append(dict(start=start, e=e, b=bnd, q=flat[i] == "?", cids=[],
                             text=re.sub(r"\s+", " ", "".join(flat[start:e + 1])).strip(),
                             exempt=any(a.startswith(("<strong", '<span class="next"')) for a in seg)))
            start = bnd
        refs = [i for i, k in enumerate(kind) if k == "ref"]
        if refs and not ends:
            E(f"{where}: a block with claims and no sentence end: {text_of(inner)[:60]!r}")
            return inner
        for t in refs:
            k = next((k for k, s in enumerate(ends) if s["b"] > t), None)
            if k is None:
                E(f"{where}: claims after the last sentence end: {text_of(inner)[-60:]!r}")
                continue
            ends[k]["cids"].append(REF_RE.match(atoms[t]).group(1))
        for k, s in enumerate(ends):  # a question carries no chip: its claims go to the next sentence
            if s["q"] and s["cids"] and k + 1 < len(ends):
                ends[k + 1]["cids"][:0], s["cids"] = s["cids"], []
        opens, closes = {}, {}
        for k, s in enumerate(ends):
            if not s["cids"]:
                if not (s["exempt"] or s["q"]):
                    unchipped.append((where, s["text"]))
                continue
            # The bind (§8): the sentence's last word, its punctuation and the chip, as one span, so a
            # chip never opens a line. The chip follows the punctuation with no space ("text.[1]", WPF).
            i = s["e"]
            while i - 1 >= s["start"] and (kind[i - 1] == "ref" or (kind[i - 1] == "text" and not flat[i - 1].isspace())):
                i -= 1
            opens[i] = '<span class="nw">'
            closes[s["e"]] = group("chip", s["cids"]) + "</span>"
        return "".join(opens.get(i, "") + ("" if k == "ref" else a) + closes.get(i, "")
                       for i, (a, k) in enumerate(zip(atoms, kind)))

    def chip_blocks(m):
        tag, attrs, inner = m.group(1), m.group(2), m.group(3)
        if "\x00" not in inner and not re.search(r"[.?!]", text_of(inner)):
            return m.group(0)
        return f"<{tag}{attrs}>" + chip_block(inner, f"<{tag}{attrs}>") + f"</{tag}>"

    BLOCK_RE = re.compile(r"<(p|li|td)(\b[^>]*)>(.*?)</\1>", re.S)
    mx_part = re.search(r'<div class="tbl tbl--mx">.*?</table></div></div>', body, re.S).group(0)
    before, _, after = body.partition(mx_part)
    body = BLOCK_RE.sub(chip_blocks, before) + mx_part + BLOCK_RE.sub(chip_blocks, after)
    if "\x00" in body or "\x01" in body:
        E("a claim ref was left unplaced")
    log.append("Sentences without a chip (claim-headers, next steps and questions are exempt):")
    log += [f"  {w} {s}" for w, s in unchipped]
    # 5. The map (§11, §12): one real table, its categories labelled directly in the headers, no
    # ticks, no corner name, no axis prefix. One entry per company; nothing is placed by hand.
    mp = b["map"]
    AXES = (mp["across"], mp["down"])
    # The map lists the hiring company first, then companies in map.answers' order: T's map order
    # differs from its run line's, so only the answers can carry it.
    answers = sorted(mp["answers"], key=lambda a: (a["company"] != co["slug"], mp["answers"].index(a)))

    def is_yes(a):
        return a["answer"] == "yes"

    def answer_line(axis, a):
        """§2c: "<yes header>: <name>" for a yes, the no header for a no."""
        return f"{axis['yes']}: {a['name']}" if is_yes(a) else axis["no"]

    for a in answers:  # §12's gates
        e = by_slug[a["company"]]
        for axis_key in ("across", "down"):
            ans = a[axis_key]
            for cid in ids(ans["c"]):
                c = claims.get(cid)
                if not c or c.get("subject") != e["name"]:  # methodology.md:89: never a shortened form
                    E(f"map {shown(e)}: {cid} must exist and name {e['name']!r}")
                    continue
                want = ("verified",) if is_yes(ans) else ("verified", "unfound")
                if c["state"] not in want:
                    E(f"map {shown(e)}: {cid} is {c['state']}, a {ans['answer']!r} needs {' or '.join(want)}")
                claim_ok(cid, f"map {shown(e)}")
                if is_yes(ans) and (not ans["name"] or ans["name"] not in c["claim"]):
                    E(f"map {shown(e)}: the yes name {ans['name']!r} is not verbatim in {cid}'s claim")
    QKEY = {"tl": (True, True), "tr": (False, True), "bl": (True, False), "br": (False, False)}
    quad = {q: [a for a in answers if (is_yes(a["across"]), is_yes(a["down"])) == QKEY[q]] for q in QKEY}

    # The logo gate (25§0 A2) is brief-check's logo_gate. The build emits --k, --ar, --trim and --m,
    # and CSS does the arithmetic. --k is Q's density factor, (median ink share / own) ** 0.5; a record
    # without an ink share takes 1. A company whose logo is null sets its name as a wordmark.
    logo_css, recs_ = [], {e["slug"]: inp["logos"].get(e["logo"]) for e in ents if e["logo"]}
    dens = sorted(r["ink_share"] for r in recs_.values() if r and r.get("ink_share"))
    for e in ents:
        if not e["logo"]:
            continue
        r = recs_[e["slug"]]
        if not r:
            E(f"{shown(e)}: logo {e['logo']!r} has no record in {LOGOS_JSON}")
            continue
        E_before = len(errors)
        errors.extend(f"{shown(e)}: logo not gated: {f}" for f in BC.logo_gate(r, root))
        if len(errors) > E_before:
            continue
        f = r.get("trim_file") or r["file"]
        data = (root / f).read_bytes()
        if r.get("trim_file") and sha(data) != r.get("trim_sha256"):
            E(f"{shown(e)}: the trimmed logo's sha256 does not match {LOGOS_JSON}")
        svg = f.endswith(".svg")
        if (svg and b"<svg" not in data) or ("ink_box" in r and not r["ink_box"]):
            E(f"{shown(e)}: the logo has no ink")
        aspect = r.get("aspect") or svg_aspect(data)
        if not aspect:
            E(f"{shown(e)}: no aspect ratio in its record or its file")
            continue
        k = (dens[len(dens) // 2] / r["ink_share"]) ** 0.5 if dens and r.get("ink_share") else 1.0
        uri = f"data:{'image/svg+xml' if svg else 'image/png'};base64," + base64.b64encode(data).decode()
        logo_css.append(f'.q2__logo--{e["slug"]} {{ --k: {k:.4f}; --ar: {aspect}; --trim: 1.00; --m: url("{uri}"); }}')
    if errors:  # no figure is drawn unless every map claim and every logo passes
        return dict(errors=errors, log=log)

    def entry(a):
        e = by_slug[a["company"]]
        return ('<span class="q2__ent">' + group("logo", ids(a["across"]["c"]) + ids(a["down"]["c"]), slug=e["slug"],
                                                 co=shown(e), logo=bool(e["logo"]), answers=(a["across"], a["down"]),
                                                 axis_cids=(ids(a["across"]["c"]), ids(a["down"]["c"]))) + "</span>")

    def cell_q(q):
        cos = "".join(entry(a) for a in quad[q])
        return (f'<td role="cell" class="q2__cell q2__cell--{q}">' + (f'<div class="q2__cos">{cos}</div>' if cos else "")
                + "</td>")

    def rh(t):
        return f'<th scope="row" role="rowheader" class="q2__rh">{esc(t)}</th>'
    n = len(rivals)
    caption = (f"{shown(co)} and {NUMBER_WORDS[n - 1]} {'rival' if n == 1 else 'rivals'}, placed by two questions: "
               f"{AXES[0]['question']}, and {AXES[1]['question']}?")
    figure = ('<figure class="q2" id="vT-map">\n<table class="q2__t" role="table">\n'
              f'<caption class="sr-only">{esc(caption)}</caption>\n'
              '<colgroup><col class="q2__c0"><col><col></colgroup>\n'
              '<thead role="rowgroup"><tr role="row"><td class="q2__corner" role="cell"></td>'
              + "".join(f'<th scope="col" role="columnheader" class="q2__ch">{esc(t)}</th>' for t in (AXES[0]["yes"], AXES[0]["no"]))
              + '</tr></thead>\n<tbody role="rowgroup">\n'
              f'<tr role="row">{rh(AXES[1]["yes"])}{cell_q("tl")}{cell_q("tr")}</tr>\n'
              f'<tr role="row">{rh(AXES[1]["no"])}{cell_q("bl")}{cell_q("br")}</tr>\n</tbody>\n</table>\n</figure>')
    # §12's header gate, read off the drawn table: each header's words equal the category part of
    # every answer line in the cells it heads.
    cols = re.findall(r'class="q2__ch">(.*?)</th>', figure)
    for rname, cells in re.findall(r'class="q2__rh">(.*?)</th>(.*?)</tr>', figure, re.S):
        for cname, td in zip(cols, re.findall(r'<td role="cell" class="q2__cell.*?</td>', cells, re.S)):
            for gid in re.findall("\x02(\\d+)\x03", td):
                g = groups[int(gid)]
                got = tuple(esc(answer_line(ax, an).partition(":")[0]) for ax, an in zip(AXES, g["answers"]))
                if got != (cname, rname):
                    E(f"map: {g['co']} sits under {cname!r} and {rname!r}, but its answer lines read {got}")
    body, k = re.subn(r"<p>@@FIGURE@@</p>", lambda _m: figure, body)
    if k != 1:
        E(f"figure slot: {k} matches, want 1")
    log.append("Quadrants: " + "; ".join(f"{q} " + (", ".join(a["company"] for a in quad[q]) or "(empty)") for q in QKEY))
    # 6. Print numbers (§17): one per URL, ranked by first appearance in the finished DOM.
    num = {}
    for gid in re.findall("\x02(\\d+)\x03", body):
        for u in sorted(dict.fromkeys(claims[c]["url"] for c in groups[int(gid)]["cids"]), key=lambda u: num.get(u, 10 ** 6)):
            num.setdefault(u, len(num) + 1)
    label = {}
    for u in num:  # labels are sources.tsv's (W13): one row per cited URL
        if not inp["labels"].get(u):
            E(f"no label for {u}: sources.tsv has no row for it")
            continue
        label[u] = esc(inp["labels"][u])
        if "'" in curl(inp["labels"][u]):
            E(f"label for {u}: a straight ' curl() cannot place: {inp['labels'][u]!r}")
        if len(inp["labels"][u]) > BC.LABEL_MAX:  # 31, live T's longest: the contract's cap (G17)
            E(f"label over {BC.LABEL_MAX} characters: {inp['labels'][u]}")

    def host(u):
        return urlparse(u).hostname.removeprefix("www.")

    MON = {m: i + 1 for i, m in enumerate("january february march april may june july august september october "
                                          "november december".split())}
    DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})|\b([A-Z][a-z]+) (\d{1,2}), (\d{4})|\b(\d{1,2}) ([A-Z][a-z]+) (\d{4})")

    def first_date(cid):
        """R's §9 reading: the first date in the qualifier, or None."""
        for m in DATE_RE.finditer(claims[cid].get("qualifier", "")):
            try:
                if m.group(1):
                    return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                mo, dd, yy = (m.group(4), m.group(5), m.group(6)) if m.group(4) else (m.group(8), m.group(7), m.group(9))
                return date(int(yy), next(v for k, v in MON.items() if k.startswith(mo.lower()) and len(mo) >= 3), int(dd))
            except (StopIteration, ValueError):
                continue
        return None

    read_on = {k: date.fromisoformat(p["fetched_at"][:10]) for p in ok for k in (p.get("final_url"), p["url"]) if k}

    def url_date(u):
        """§10, 31 Rec 2: the date is the URL's. The first row in ledger order on that URL whose
        qualifier's date is not the day it was read gives it; else "read" and that day (D4: the
        page's own fetch day, which across midnight is not every page's)."""
        rd = read_on.get(u, run_d)
        for c in ledger:
            if c.get("url") == u:
                d = first_date(c["id"])
                if d and d != rd:
                    return f"{d.day}&nbsp;{d:%b}&nbsp;{d.year}"
        return f"read {rd.day}&nbsp;{rd:%b}&nbsp;{rd.year}"

    # 7. Every source carries one evidence line: an en row's quote in curly quotes, or a lead-in and
    # the row's gloss (§2e). The lead is derived from the row: unfound, its language, or a gloss.
    ev_log, card_ids = [], []

    def evidence(cid, integ=False):
        c = claims[cid]
        q, gloss, lang = c.get("quote", ""), c.get("gloss"), c.get("lang", "en")
        # G76: whether the card quotes the row is brief-check's shows_quote, which budget-check's
        # integration rule also reads, so stage 6 lists only rows that pass the test below.
        lead = (None if BC.shows_quote(c) else LEAD_UNFOUND if c["state"] == "unfound"
                else LEAD_BLOCKED if c["state"] == "blocked"
                else LEAD_LANG.format(LANGS.get(lang, lang)) if lang != "en" else LEAD_PARA)
        if integ and (lead or "integration" not in c.get("claim", "")):
            E(f"{cid}: {INTEG!r} needs a shown quote and a claim that says integration (36 R3)")
        if lead is None:
            shown_q = curl(q)
            if quote_is_fragment(q):
                E(f"{cid}: its quote is empty or a page artefact, and it has no gloss to show instead")
            if "'" in shown_q:
                E(f"{cid}: a straight ' outside a word in a shown quote (§2): {shown_q!r}")
            pre = f'<span class="card__lead">{INTEG}</span> ' if integ else ""
            return 4, (f"{INTEG} " if integ else "") + "“" + shown_q + "”", f'<span class="card__quote">{pre}“{bind_dates(esc(shown_q))}”</span>'
        if lang != "en" and lang not in LANGS:
            E(f"{cid}: no language name for lang {lang!r}")
        text = gloss  # W13 writes a gloss on every row whose quote cannot show, unfound rows included
        if not text and lead == LEAD_BLOCKED:  # a blocked row's claim is the record of the refusal
            text = c.get("claim")
        if not text:
            E(f"{cid}: {lead} needs the row's gloss")
            return 1, "", ""
        if text.startswith(lead):  # a gloss that already carries the lead prints it once
            text = text[len(lead):].lstrip()
        if "'" in curl(text):
            E(f"{cid}: gloss: a straight ' curl() cannot place: {text[:60]!r}")
        para = bind_dates(esc(text))
        return 2, f"{lead} {text}", f'<span class="card__para"><span class="card__lead">{lead}</span> {para}</span>'

    def source(u, cid, where, integ=False):
        k, line, ev_html = evidence(cid, integ)
        ev_log.append((where, cid, k, line))
        return (f'<span class="card__src" data-claim="{cid}"><span class="card__label"><a href="{html.escape(u)}">'
                f'{label.get(u, "")}</a></span><span class="card__meta"><span translate="no">{host(u)}</span> · '
                f"{url_date(u)}</span>" + ev_html + "</span>")

    def urls_of(cids):
        first = {}
        for c in cids:
            first.setdefault(claims[c]["url"], c)
        return sorted(first.items(), key=lambda kv: num[kv[0]])

    def pn(us):
        return '<span class="pn" aria-hidden="true">' + '<span class="pn__sep">,</span>'.join(str(num[u]) for u, _ in us) + "</span>"

    def card(cid_, inner):
        card_ids.append(cid_)
        return f'<span class="card" id="{cid_}" popover="auto" style="position-anchor: --{cid_}">{inner}</span>'

    def trigger(cls, cid_, inner):
        return (f'<button class="{cls}" type="button" popovertarget="{cid_}" popovertargetaction="show" '
                f'style="anchor-name: --{cid_}">{inner}</button>')

    def numbers(us):
        """§8: the source numbers, joined by U+2009, ascending, its span widened to part them."""
        return '<span class="n-sep">&thinsp;</span>'.join(str(num[u]) for u, _ in us)

    seen = {"chip": 0, "cell": 0}

    def render_group(m):
        g = groups[int(m.group(1))]
        us = urls_of(g["cids"])
        many = len(us) > 1
        if g["kind"] in seen:
            seen[g["kind"]] += 1
        if g["kind"] == "chip":
            i = f"vT-c{seen['chip']}"
            name = f'<span class="sr-only">{"Source" + "s" * many} </span>{numbers(us)}'
            return trigger("chip", i, name) + card(i, "".join(source(u, c, i) for u, c in us)) + pn(us)
        if g["kind"] == "cell":
            i = f"vT-m{seen['cell']}"
            name = (g["value"] + f'<span class="sr-only">, {"sources" if many else "source"} </span>&nbsp;'
                    f'<span class="cite__n">{numbers(us)}</span>')
            return trigger("cite", i, name) + card(i, "".join(source(u, c, i) for u, c in us)) + pn(us)
        # A logo (§11b, §12): the company's name (31 Rec 1), then two blocks, across then down, each
        # an answer line in the headers' own words and its sources.
        i = f"vT-map-{g['slug']}"
        blocks = f'<span class="card__co">{esc(g["co"])}</span>' + "".join(
            f'<span class="card__grp"><span class="card__ans">{esc(answer_line(ax, an))}</span>'
            + "".join(source(claims[c]["url"], c, i, c in an["integration"]) for c in cs) + "</span>"
            for ax, an, cs in zip(AXES, g["answers"], g["axis_cids"]))
        mark = (f'<span class="q2__logo q2__logo--{g["slug"]}" aria-hidden="true"><span class="q2__mono"></span></span>'
                f'<span class="sr-only">{esc(g["co"])}</span>' if g["logo"] else f'<span class="q2__wm">{esc(g["co"])}</span>')
        return trigger("q2__co", i, mark) + card(i, blocks) + pn(urls_of(g["cids"]))

    body = re.sub("\x02(\\d+)\x03", render_group, body)
    if len(card_ids) != len(set(card_ids)):
        E("a card id repeats")
    if sorted(num.values()) != list(range(1, len(num) + 1)):
        E("print numbers are not contiguous from 1")
    log.append(f"Triggers: {seen['chip']} chips, {seen['cell']} cells, {sum(g['kind'] == 'logo' for g in groups)} logos; "
               f"{len(num)} URLs")
    log += [f"  {where.removeprefix('vT-'):14} {cid} {k} {line[:110]}" for where, cid, k, line in ev_log]
    # 8. The h1 (§7) and the run line (40 §2, RT-2): written from the run, no year, no typed count.
    company = co["name"]
    h1 = (f'<h1><!-- SNAPSHOT-EXEMPT (the agent\'s repo) -->{esc(company)} brief, <span class="nw">made with</span> '
          '<span class="h1__who"><span class="nw">Ryan&nbsp;Hennebry’s</span> <span class="nw"><a href="{{REPO}}">'
          'competitor-intel agent</a></span></span><!-- /SNAPSHOT-EXEMPT --></h1>')
    names = [shown(co)] + [shown(r) for r in rivals]
    run_dm = f"{run_d.day}&nbsp;{run_d:%B}"
    if run_to != run_d:  # the window, as the evidence holds it: "From 11 to 12 October"
        start = f"{run_d.day}" if run_d.month == run_to.month else run_dm
        run_dm = f"{start} to {run_to.day}&nbsp;{run_to:%B}"
    run = (f'<p class="run">{"On" if run_to == run_d else "From"} {run_dm}, the agent read {len(ok_urls)} pages on '
           f"{esc(', '.join(names[:-1]) + ' and ' + names[-1])}, logging {len(ledger)} claims.</p>")
    run_text = text_of(run)
    parts = [run_dm.replace("&nbsp;", "\xa0"), f" {len(ok_urls)} ", f" {len(ledger)} "] + [curl(n) for n in names[1:]]  # printed curled (G71)
    for part in dict.fromkeys(parts):  # each part as often as it is meant to stand: 18 pages and 18 claims is two
        if run_text.count(part) != parts.count(part):
            E(f"run line: {part!r} appears {run_text.count(part)} times, want {parts.count(part)}")
    if str(run_d.year) in run_text + text_of(h1) or str(run_to.year) in run_text + text_of(h1):
        E("title block: the year is on the page (RT-2: metadata only)")
    fr = FRAMINGS[framing]
    site_url = page_url(b, framing)
    title, alt = fr["title"].format(name=curl(company)), fr["alt"].format(name=curl(company))  # as the h1 prints it

    # 9. The print Sources list (§17): every number, its label, host and full URL.
    psrc = "".join(f'<li><span class="psrc__n">{num[u]}</span> {label.get(u, "")}, <span translate="no">{host(u)}</span> '
                   f'<span class="psrc__u" translate="no">{html.escape(u)}</span></li>' for u in sorted(num, key=num.get))

    # 10. Fill the template. The banner shows only in T's framing (N1).
    src = tpl.replace(m_sk.group(0), body.rstrip() + "\n")
    banner = re.search(r"<!--BANNER\{-->(.*?)<!--\}BANNER-->", src, re.S)
    if not banner:
        E("template: no <!--BANNER{--> block")
    else:
        src = src.replace(banner.group(0), banner.group(1) if fr["banner"] else "")
    toc = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', src)
    contents = "".join(f'<li><a href="#{i}">{t}</a></li>' for i, t in toc)
    if [t for _, t in toc[:len(heads)]] != [t for _, t in heads] or len(toc) != len(heads) + 1:
        E(f"contents: {[t for _, t in toc]} are not the brief's h2s and Also built")
    fills = {"<!--H1-->": h1, "<!--RUN-->": run, "<!--CONTENTS-->": contents, "<!--SOURCES-->": psrc,
             "/*LOGOCSS*/": "\n".join(logo_css + ([measured] if measured else [])),
             "{{TITLE}}": html.escape(title), "{{DESC}}": html.escape(DESC), "{{REPO}}": REPO, "{{LINKEDIN}}": LINKEDIN,
             "{{SITE}}": html.escape(site_url), "{{OGIMG}}": html.escape(og_image_url(site_url, og_png)),
             "{{OGALT}}": html.escape(alt),
             # D4: the page date is the final build's stamp, metadata only (RT-2 keeps the year off the page)
             "<!--PAGEDATE-->": (f'<meta property="article:published_time" content="{html.escape(dates["page"])}">'
                                 if dates and dates.get("page") else "")}
    for tag, val in fills.items():
        if tag not in src:
            E(f"template: {tag} missing")
        src = src.replace(tag, val)
    if re.search(r"\{\{[A-Z]+\}\}|<!--[A-Z0-9-]+-->|<!--[A-Z]+[{}]-->|<!--[{}][A-Z]+-->|/\*LOGOCSS\*/",
                 src.replace("<!--GENERATED-->", "")):
        E("template: an unfilled placeholder is left")
    if src.count('<figure class="q2') != 1:
        E("one map (§1.2)")
    # 10b. G65: every name the brief prints, in prose, tables, map, cards and sources, in one place.
    art = re.search(r'<article class="brief">.*?</article>', src, re.S)
    if not art:
        E('template: no <article class="brief"> to hold the names')
    else:
        wrap = name_spans([n for e in ents for n in (e["name"], e.get("short"))])
        src = src[:art.start()] + on_text(art.group(0), wrap) + src[art.end():]

    # 11. New tab (40 §5, RT-4): every http(s) link opens a new tab and is described by #nt; no arrow.
    fixed = len(re.findall(r'<a\s[^>]*href="https?://', re.sub(r'<span class="card".*?(?=<span class="pn")', "", src, flags=re.S)))
    src = re.sub(r"<a(\s[^>]*)>(.*?)</a>",
                 lambda m: m.group(0) if not re.search(r'\shref="https?://', m.group(1)) else f"<a{m.group(1)}{NT_ATTRS}>{m.group(2)}</a>",
                 src, flags=re.S)
    a_tags = re.findall(r"<a\s[^>]*>", src)
    nt_http = [a for a in a_tags if re.search(r'href="https?://', a)]
    if len(nt_http) != fixed + len(ev_log) or any(NT_ATTRS not in a for a in nt_http):
        E(f"new tab: {len(nt_http)} http(s) links, want {fixed + len(ev_log)} (the page's own plus one per "
          f"evidence line), each with{NT_ATTRS}")
    if len(re.findall(r'\starget="', src)) != len(nt_http) or any(re.search(r"\starget=", a) for a in a_tags if a not in nt_http):
        E("new tab: a fragment or mailto: link carries a target, or a target sits off a link")
    if src.count("↗") + src.count('class="ext"'):
        E("new tab: an arrow glyph or .ext on the page (the underline marks a link)")
    if len(re.findall(r'<span id="nt" hidden>opens in a new tab</span>', src)) != 1 or src.count('id="nt"') != 1:
        E("new tab: want exactly one #nt reading 'opens in a new tab'")

    # 12. Link audit over the finished page: every http href is in a snapshot unless it sits in a
    # SNAPSHOT-EXEMPT block; every in-page link and popover target has a target.
    exempt = {html.unescape(h) for blk in re.findall(r"<!-- SNAPSHOT-EXEMPT.*?<!-- /SNAPSHOT-EXEMPT -->", src, re.S)
              for h in re.findall(r'href="([^"]+)"', blk)}
    hrefs = [html.unescape(h) for h in re.findall(r'href="([^"]+)"', src)]
    errors.extend(f"href not in a snapshot: {h}" for h in hrefs if h.startswith("http") and h not in exempt
                  and h not in snap_text)
    all_ids = re.findall(r'\bid="([^"]+)"', src)
    if len(all_ids) != len(set(all_ids)):
        E(f"an id repeats: {sorted({i for i in all_ids if all_ids.count(i) > 1})}")
    errors.extend(f"in-page link without a target: {h}" for h in hrefs if h.startswith("#") and h[1:] not in all_ids)
    errors.extend(f"popovertarget without a target: {t}" for t in re.findall(r'popovertarget="([^"]+)"', src)
                  if t not in all_ids)
    n_recs = len(b["recommendations"])
    if re.search(r"<em\b", src) or src.count('<span class="next"><strong>Next&nbsp;step:</strong> ') != n_recs or 'class="do"' in src:
        E(f"40 §2b, 38§3: want no <em>, no .do, and exactly {n_recs} '<span class=\"next\"><strong>Next&nbsp;step:</strong> '")
    if src.count('<h2 class="psrc__h">') != 1:
        E("§17 gate: the print source list has one h2, inside .psrc")
    src = src.replace("<!--GENERATED-->", "<!-- GENERATED by build/web.py from template.html, brief.json and the run's "
                      "claims.jsonl, sources.tsv and logos/logos.json. Edit those, then rebuild. -->")
    log.append(f"COMPANY: {company!r}; framing {framing}; head: title {title!r}; address {site_url}")
    log.append(f"pages: {len(ok_urls)}; claims: {len(ledger)}; date: {run_d}; URLs numbered: {len(num)}")
    return dict(src=src, errors=errors, log=log, title_lines=(text_of(h1), run_text), card_ids=card_ids,
                site_url=site_url)


def svg_aspect(data):
    """Width over height from an SVG's viewBox, or its width and height."""
    t = data.decode("utf-8", "replace")
    m = re.search(r'viewBox="\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', t)
    if not m:
        m = re.search(r'<svg\b[^>]*\bwidth="([\d.]+)(?:px)?"[^>]*\bheight="([\d.]+)(?:px)?"', t)
    return round(float(m.group(1)) / float(m.group(2)), 4) if m and float(m.group(2)) else None


# THE SHARE CARD (the operator, 2026-10-12: design B4, vertically centred). Each N1 page gets its own
# og.png: the hiring company's logo as a one-colour mask, "Competitor intel brief" beneath, on T's
# card ground and face (T:sharecard/cards/card-matched-v3.html). A company with no logo gets its
# name set large in Inter in the logo's place (E8), so no brief fails for lack of a logo. card_plan()
# is stdlib, so --selftest grades the logo source; render_card() needs Pillow and Chromium, as the
# build's browser pass does. build() draws the card before the template fill, so og:image's ?v= is
# the card's own hash (og_image_url).
CARD_FONT = ASSETS / "inter-latin-var.woff2"
CARD_W, CARD_H, CARD_DPR = 1200, 630, 2
CARD_EDGE, CARD_LOGO_W, CARD_LOGO_MAX_H, CARD_GAP = 192, 500, 240, 72  # CSS px; B4's logo is 500 wide
CARD_LABEL = "Competitor intel brief"
CARD_CROP = 127  # device px every ink pixel keeps clear of the 3:2 centre crop's sides (LinkedIn)
CARD_GROUND, CARD_INK = (0x17, 0x19, 0x1B), 0x17 + 24  # a channel above CARD_INK is ink


def png_size(data):
    """(width, height) from a PNG's IHDR, or None."""
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", data[16:24])


def card_plan(root, brief, logos):
    """The card's logo source and its device-pixel box, or the reasons there is none. A record's
    `card_file` (with `card_sha256`) is its full-resolution, ink-cropped mask source; without one the
    page's own trim_file, else file. A vector draws at any size; a raster is only ever downscaled."""
    root, co = Path(root), brief["company"]
    if not co.get("logo"):  # E8: the name card, the name the page prints beside rivals
        return dict(mode="name", name=curl(co.get("short") or co["name"]), file=None), []
    r = logos.get(co["logo"])
    if not r:
        return None, [f"card: logo {co['logo']!r} has no record in {LOGOS_JSON}"]
    key = "card_file" if r.get("card_file") else "trim_file" if r.get("trim_file") else "file"
    want = r.get({"card_file": "card_sha256", "trim_file": "trim_sha256", "file": "sha256"}[key])
    p = (root / str(r[key])).resolve()
    if not p.is_relative_to(root.resolve()) or not p.is_file():
        return None, [f"card: {key} {r[key]!r} is no file inside the run"]
    data = p.read_bytes()
    if sha(data) != want:
        return None, [f"card: {r[key]} does not hash to {LOGOS_JSON}'s {key.replace('file', 'sha256')}"]
    svg, px = r[key].endswith(".svg"), png_size(data)
    if svg:
        aspect = svg_aspect(data)
    elif px:
        aspect = px[0] / px[1]
    else:
        return None, [f"card: {r[key]} is neither SVG nor PNG"]
    if not aspect:
        return None, [f"card: {r[key]} has no aspect ratio"]
    wd = round(min(CARD_LOGO_W, CARD_LOGO_MAX_H * aspect) * CARD_DPR)
    hd = round(wd / aspect)
    if px and (px[0] < wd or px[1] < hd):
        return None, [f"card: {r[key]} is {px[0]}x{px[1]} px and the card draws it at {wd}x{hd} device px; "
                      f"a logo is never upscaled. Add a card_file to {LOGOS_JSON}: the verbatim source, "
                      f"processed as trim_file is, at full resolution"]
    return dict(mode="logo", name=co["name"], file=r[key], data=data, svg=svg, px=px, wd=wd, hd=hd), []


CARD_HTML = """<!doctype html><meta charset="utf-8"><style>
@font-face { font-family: "InterV"; src: url("data:font/woff2;base64,%(font)s") format("woff2"); font-weight: 100 900; }
* { margin: 0; box-sizing: border-box; }
html, body { width: %(w)spx; height: %(h)spx; overflow: hidden; background: #17191b; color: #f2f5f8;
  font-family: "InterV", sans-serif; -webkit-font-smoothing: antialiased; }
.card { width: %(w)spx; height: %(h)spx; padding: 0 %(edge)spx; display: flex; flex-direction: column;
  justify-content: flex-start; }
.logo { width: %(lw)spx; height: %(lh)spx; flex: none; background-color: #f2f5f8;
  -webkit-mask: url("%(mask)s") 0 0 / 100%% 100%% no-repeat; mask: url("%(mask)s") 0 0 / 100%% 100%% no-repeat; }
.nm { flex: none; font-weight: 700; letter-spacing: -0.02em; line-height: 1.04; color: #f2f5f8; text-wrap: balance;
  text-box: trim-both cap alphabetic; }
.lab { margin: %(gap)spx 0 0 -3px; font-weight: 600; letter-spacing: -0.01em; line-height: 1.08; color: #aeb4ba;
  white-space: nowrap; text-box: trim-both cap alphabetic; }
</style><div class="card">%(mark)s<p class="lab">%(label)s</p></div>"""


def card_ink(png):
    """(left, right) 3:2 crop margins of a card screenshot's ink, in device px, and its RGB image."""
    import io
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGB")
    box = im.point(lambda v: 255 if v > CARD_INK else 0).convert("L").point(lambda v: 255 if v else 0).getbbox()
    crop = (im.width - im.height * 3 / 2) / 2
    return (box[0] - crop, im.width - crop - box[2]) if box else (None, None), im


def render_card(plan, dest):
    """Draw plan's card to dest (2400x1260 PNG): the label at the largest whole size whose ink keeps
    CARD_CROP clear of the 3:2 crop's right side, the stack centred on whole CSS px; then the whole
    card's ink must keep CARD_CROP clear of both sides. Returns (log lines, errors)."""
    import io
    from PIL import Image
    from playwright.sync_api import sync_playwright
    named = plan["mode"] == "name"
    if named:  # E8: the name, at the largest whole size that keeps the logo's height cap and the crop clear
        mask, mark = "", f'<p class="nm">{html.escape(plan["name"])}</p>'
    elif plan["svg"]:
        mask, mark = "data:image/svg+xml;base64," + base64.b64encode(plan["data"]).decode(), '<div class="logo"></div>'
    else:  # the alpha alone, Lanczos-downscaled once to the exact device box the browser then draws 1:1
        a = Image.open(io.BytesIO(plan["data"])).convert("RGBA").getchannel("A")
        a = a.resize((plan["wd"], plan["hd"]), Image.LANCZOS)
        m = Image.merge("LA", (Image.new("L", a.size, 255), a))
        buf = io.BytesIO()
        m.save(buf, "PNG")
        mask, mark = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(), '<div class="logo"></div>'
    page = CARD_HTML % dict(font=base64.b64encode(CARD_FONT.read_bytes()).decode(), w=CARD_W, h=CARD_H, edge=CARD_EDGE,
                            lw=0 if named else plan["wd"] / CARD_DPR, lh=0 if named else plan["hd"] / CARD_DPR, mask=mask,
                            gap=CARD_GAP, label=html.escape(CARD_LABEL), mark=mark)
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        try:
            pg = b.new_page(viewport={"width": CARD_W, "height": CARD_H}, device_scale_factor=CARD_DPR)
            pg.set_content(page, wait_until="load")
            pg.evaluate("document.fonts.ready.then(() => true)")
            if not pg.evaluate("[...document.fonts].some((f) => f.family.replace(/\"/g, '') === 'InterV' && f.status === 'loaded')"):
                return [], ["card: Inter did not load"]
            fits, nm = {}, None
            if named:  # the label at its floor while the name grows: lo below must fit
                pg.evaluate("document.querySelector('.lab').style.fontSize = '24px'")

                def fit_name(size):
                    pg.evaluate(f"document.querySelector('.nm').style.fontSize = '{size}px'")
                    h = pg.evaluate("document.querySelector('.nm').getBoundingClientRect().height")
                    (_, right), _ = card_ink(pg.screenshot())
                    return h <= CARD_LOGO_MAX_H and right is not None and right >= CARD_CROP
                nlo, nhi = 24, 200
                if not fit_name(nlo):
                    return [], [f"card: the name {plan['name']!r} does not fit at {nlo} px"]
                while nhi - nlo > 1:
                    mid = (nlo + nhi) // 2
                    nlo, nhi = (mid, nhi) if fit_name(mid) else (nlo, mid)
                nm = nlo
                pg.evaluate(f"document.querySelector('.nm').style.fontSize = '{nm}px'")

            def fit(size):
                pg.evaluate(f"document.querySelector('.lab').style.fontSize = '{size}px'")
                (_, right), _ = card_ink(pg.screenshot())  # the hang fixes the left; the size moves the right
                fits[size] = right is not None and right >= CARD_CROP
                return fits[size]
            lo, hi = 24, 160  # lo must fit; hi must not
            if not fit(lo) or fit(hi):
                return [], [f"card: the label fits at {sorted(s for s, f in fits.items() if f)} px of {sorted(fits)}"]
            while hi - lo > 1:
                mid = (lo + hi) // 2
                lo, hi = (mid, hi) if fit(mid) else (lo, mid)
            pg.evaluate(f"document.querySelector('.lab').style.fontSize = '{lo}px'")
            top_el = ".nm" if named else ".logo"
            stack = pg.evaluate("document.querySelector('.lab').getBoundingClientRect().bottom"
                                f" - document.querySelector('{top_el}').getBoundingClientRect().top")
            top = round((CARD_H - stack) / 2)
            pg.evaluate(f"document.querySelector('.card').style.paddingTop = '{top}px'")
            box = None if named else pg.evaluate("(r => [r.x, r.y, r.width, r.height].map((v) => v * %d))"
                                                 "(document.querySelector('.logo').getBoundingClientRect())" % CARD_DPR)
            (left, right), im = card_ink(pg.screenshot())
        finally:
            b.close()
    if box and (any(abs(v - round(v)) > 1e-6 for v in box) or [round(v) for v in box[2:]] != [plan["wd"], plan["hd"]]):
        errors.append(f"card: the logo's device box {box} is not {plan['wd']}x{plan['hd']} on whole pixels")
    if im.size != (CARD_W * CARD_DPR, CARD_H * CARD_DPR) or im.getpixel((0, 0)) != CARD_GROUND:
        errors.append(f"card: {im.size}, ground {im.getpixel((0, 0))}")
    if left is None or min(left, right) < CARD_CROP:
        errors.append(f"card: 3:2 crop margins L{left} R{right}, want {CARD_CROP} or more")
    if errors:
        return [], errors
    im.save(dest, "PNG", optimize=True)
    if named:
        what = f"name {plan['name']!r} at {nm}px (no logo, E8)"
    else:
        src = (f"vector {plan['file']}" if plan["svg"] else
               f"{plan['file']} {plan['px'][0]}x{plan['px'][1]} px, Lanczos-downscaled")
        what = f"logo {plan['wd']}x{plan['hd']} device px from {src}"
    return [f"card: og.png {im.width}x{im.height}, sha256 {sha(Path(dest).read_bytes())}; {what}; "
            f"label {lo}px; top {top}px of a {stack:g}px stack; 3:2 crop margins L{left:g} R{right:g}"], []


def card_only(root, out):
    """--card: this run's card alone, to out, as build() draws it."""
    root = Path(root)
    try:
        b = json.loads((root / "brief.json").read_text(encoding="utf-8"))
        logos = ({r.get("slug"): r for r in json.loads((root / LOGOS_JSON).read_text(encoding="utf-8"))}
                 if (root / LOGOS_JSON).is_file() else {})
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"FAIL: cannot read the run at {root}: {exc}\n")
        return 2
    plan, errors = card_plan(root, b, logos)
    log = []
    if plan:
        try:
            log, errors = render_card(plan, out)
        except Exception as exc:
            errors = [f"card: {type(exc).__name__}: {exc}"]
    sys.stdout.write("".join(f"{ln}\n" for ln in log))
    sys.stderr.write("".join(f"FAIL {e}\n" for e in errors))
    return 1 if errors else 0
def subset_font(chars, dest):
    """The page's own face: the master cut to the page's characters, T's subset options (25§5)."""
    from fontTools import subset
    opts = subset.Options()
    opts.flavor, opts.layout_features = "woff2", LAYOUT_FEATURES.split(",")
    font = subset.load_font(str(FONT_MASTER), opts)
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=sorted(ord(c) for c in chars))
    sub.subset(font)
    subset.save_font(font, str(dest), opts)


# The page's voice test, written once (W2-rulings.md G27, G31): the lint gate below runs it on the page's
# text, and claims-check.py L18 runs it on a ledger's glosses, which the page prints on its cards.
PAGE_LINTS = (("voice-lint.sh", ("--page",)), ("ai-smell.sh", ()))


def page_lints(path):
    """{tool: (exit, stdout + stderr)} for each of PAGE_LINTS on one text file."""
    out = {}
    for tool, flags in PAGE_LINTS:
        r = subprocess.run(["bash", str(ROOT / "tools" / tool), *flags, str(path)], cwd=ROOT, capture_output=True,
                           text=True)
        out[tool] = (r.returncode, r.stdout + r.stderr)
    return out


def lint_gate(root, src, title_lines):
    """T §23: voice-lint and ai-smell on the page's text. The title block describes the method by
    design, so voice-card P4 alone is exempt there (40 §2b); everything else blocks."""
    errors, log = [], []
    text = page_text(src)
    lint_file = root / "audit/page-text.md"
    lint_file.parent.mkdir(parents=True, exist_ok=True)
    lint_file.write_text(text, encoding="utf-8")
    lint = page_lints(lint_file)
    p4 = {row[0] for row in csv.reader((ROOT / "quality-bar/04-banned-patterns.tsv").open(encoding="utf-8"), delimiter="\t")
          if row and not row[0].startswith("#") and len(row) > 6 and "(P4" in row[6]}
    file_lines = text.split("\n")
    titles = {i + 1 for i, ln in enumerate(file_lines) for t in title_lines if ln == re.sub(r"\s+", " ", t).strip()}
    if not p4 or len(titles) != 2:
        errors.append(f"lint gate: P4 rows {sorted(p4)}, title lines {sorted(titles)}; want some and 2")
    fail_re = re.compile(r"^FAIL: (\S+) at (.+?):(\d+): ")
    vl_out = lint["voice-lint.sh"][1].splitlines()
    fails_all = [ln for ln in vl_out if ln.startswith("FAIL")]
    exempt = [ln for ln in fails_all if (m := fail_re.match(ln)) and m.group(1) in p4
              and m.group(2) == str(lint_file) and int(m.group(3)) in titles]
    fails = [ln for ln in fails_all if ln not in exempt]
    log += [f"EXEMPT (title block, P4): {ln}" for ln in exempt]
    routes = [ln for ln in vl_out if ln.startswith("ROUTE")]
    smell = lint["ai-smell.sh"][1]
    vl_rc = lint["voice-lint.sh"][0]
    # A ROUTE is the truth critic's, never a block. T also required exactly one, reading "every": its
    # own sentence's count, so that clause went with the other typed counts.
    if (vl_rc not in (0, 1) or (vl_rc == 1 and not fails_all) or (vl_rc == 0 and fails_all) or fails
            or lint["ai-smell.sh"][0] or "AI-SMELL-OK" not in smell or " 0 findings" not in smell):
        errors.append("lint gate: " + " | ".join(f"{t} exit {rc}" for t, (rc, _) in lint.items())
                      + f"; {len(fails)} blocking FAIL, {len(exempt)} EXEMPT\n" + "\n".join(fails) + "\n" + smell)
    log.append(f"lint ({lint_file}): voice-lint exit {vl_rc}, {len(fails)} blocking FAIL, {len(exempt)} EXEMPT; "
               f"ai-smell exit {lint['ai-smell.sh'][0]}")
    log += routes
    return errors, log


MEASURE_JS = """() => {
  const halves = [];
  for (const th of document.querySelectorAll('.q2__rh')) {
    const w = th.textContent.trim().split(/\\s+/), h = Math.ceil(w.length / 2), cs = getComputedStyle(th);
    for (const part of [w.slice(0, h).join(' '), w.slice(h).join(' ')]) {
      const s = document.createElement('span'); s.style.whiteSpace = 'nowrap'; s.textContent = part; th.appendChild(s);
      halves.push(s.getBoundingClientRect().width + parseFloat(cs.paddingInlineStart) + parseFloat(cs.paddingInlineEnd));
      s.remove();
    }
  }
  return Math.max(0, ...halves);
}"""
C0_JS = "() => Math.max(0, ...[...document.querySelectorAll('.matrix tr > :first-child')].map((c) => c.getBoundingClientRect().width))"
NAME_JS = """() => {
  const widths = [0];
  for (const c of document.querySelectorAll('table.t3 tr > :first-child')) {
    for (const word of c.textContent.trim().split(/\\s+/)) {
      const s = document.createElement('span'); s.style.whiteSpace = 'nowrap'; s.textContent = word; c.appendChild(s);
      widths.push(s.getBoundingClientRect().width); s.remove();
    }
  }
  return Math.max(...widths);
}"""
COL1_JS = """() => { const c = document.querySelector('table.t3 th:first-child'), cs = getComputedStyle(c);
  return c.getBoundingClientRect().width - parseFloat(cs.paddingInlineStart) - parseFloat(cs.paddingInlineEnd); }"""
GATE_WIDTHS = (320, 360, 390, 480, 640, 800, 1024, 1440)  # web-check's three, the reflow band, and between
# A name that reaches into its cell's end padding has lost its gutter, though nothing scrolls yet; and
# the page itself must never scroll sideways (a wordmark, a long word).
OVERFLOW_JS = """() => {
  const out = [...document.querySelectorAll('table.t3 tr > :first-child')].filter((c) => {
    const r = document.createRange(); r.selectNodeContents(c);
    return r.getBoundingClientRect().right > c.getBoundingClientRect().right - parseFloat(getComputedStyle(c).paddingInlineEnd) + 0.5;
  }).map((c) => c.textContent.trim());
  for (const m of document.querySelectorAll('.q2__wm')) {  // a wordmark stays inside its map cell's content box
    const td = m.closest('td'), r = document.createRange(); r.selectNodeContents(m);
    if (r.getBoundingClientRect().right > td.getBoundingClientRect().right - parseFloat(getComputedStyle(td).paddingInlineEnd) + 0.5)
      out.push(m.textContent.trim());
    const left = m.getBoundingClientRect().left;  // and every line of it starts where its box does
    if ([...r.getClientRects()].some((l) => l.left > left + 0.5)) out.push(`wordmark lines not at its start: ${m.textContent.trim()}`);
  }
  const d = document.documentElement;
  if (d.scrollWidth > d.clientWidth) out.push(`the page scrolls sideways by ${d.scrollWidth - d.clientWidth} px`);
  return out;
}"""
HEIGHTS_JS = """() => Object.fromEntries([...document.querySelectorAll('.card')]
  .filter((c) => c.previousElementSibling.checkVisibility())
  .map((c) => { c.showPopover(); const h = Math.round(c.getBoundingClientRect().height); c.hidePopover(); return [c.id, h]; }))"""


def browser_pass(page, measure):
    """In Chromium, on the written page: measure the widths the template leaves to each page (W5
    :133-134); or, with measure False, each card's height at 390 (§10) and any moves name cell that
    overflows at any of GATE_WIDTHS. A browser is a build dependency."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 390, "height": 844})
        pg.goto(page.as_uri())
        pg.evaluate("document.fonts.ready")
        if measure:
            c0, name = pg.evaluate(C0_JS), pg.evaluate(NAME_JS)
            col1 = []  # from 40rem the name column is a share of the table: its narrowest box
            for w in (640, 1024, 1440):
                pg.set_viewport_size({"width": w, "height": 900})
                col1.append(pg.evaluate(COL1_JS))
            pg.set_viewport_size({"width": 1440, "height": 900})
            q2 = pg.evaluate(MEASURE_JS)
            # The sticky first column plus 1 clears a focused cell (36 R5); a header's longer half
            # plus its padding sets the map's first column; the moves table's widest name word sets
            # its name column, the CSS adding the cell's end padding.
            out = (f":root {{ --mx-c0: {-int(-c0 // 1) + 1}px; --q2-c0: {-int(-q2 // 1)}px; "
                   f"--t3-name: {-int(-name // 1)}px; }}")
            if -int(-name // 1) > min(col1):  # the share's content box is too narrow for this page's widest name
                out += "\n@media (width >= 40rem) { table.t3 th:nth-child(1) { width: calc(var(--t3-name) + 16px); } }"
        else:
            out = {"heights": pg.evaluate(HEIGHTS_JS), "overflow": {}}
            for w in GATE_WIDTHS:
                pg.set_viewport_size({"width": w, "height": 844})
                out["overflow"][w] = pg.evaluate(OVERFLOW_JS)
        b.close()
    return out
def gate_log(root, lines, errors):
    """audit(): every violation collected, written to the next free audit/gate-NN.txt, then exit."""
    code = 1 if errors else 0
    audit = Path(root) / "audit"
    audit.mkdir(parents=True, exist_ok=True)
    n = 1
    while (audit / f"gate-{n:02d}.txt").exists():
        n += 1
    out = lines + (["FAIL"] + errors if errors else ["PASS: every gate held"]) + [f"exit={code}"]
    (audit / f"gate-{n:02d}.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))
    return code


def build(root, brief_path, framing="n1", browser=True, subset=True):
    """Render, write $BRIEF_ROOT/web/, and audit. A render that fails writes no page."""
    root = Path(root).resolve()  # the runbook's BRIEF_ROOT is relative; file URIs need it absolute
    shutil.rmtree(root / "web", ignore_errors=True)  # never leave an older page beside a failed build
    pre = BC.rule_S(BC.Ctx(brief_path, root, BC.load_schema()))
    if pre:
        return gate_log(root, [f"brief.json: {brief_path}"], [f"brief.json: {m}" for m in pre])
    inp = read_inputs(root, brief_path)
    # The card first, before the template fill, so og:image carries its hash. N1: the brief's own
    # card, drawn in Chromium; T keeps the shared one, assets/og.png. With no browser it is planned only.
    card, og_png, card_log, card_errors = None, None, [], []
    if framing == "t":
        og_png = (ASSETS / "og.png").read_bytes()
    else:
        card, card_errors = card_plan(root, inp["brief"], inp["logos"])
        if card and browser:
            with tempfile.TemporaryDirectory() as d:
                try:
                    card_log, card_errors = render_card(card, Path(d) / "og.png")
                except Exception as exc:  # Pillow and Chromium are build dependencies; a page without its card fails
                    card_log, card_errors = [], [f"card: {type(exc).__name__}: {exc}"]
                if not card_errors:
                    og_png = (Path(d) / "og.png").read_bytes()
    r = render(inp, framing, og_png=og_png)
    log, errors = r["log"] + card_log, list(r["errors"]) + card_errors
    if errors:
        return gate_log(root, log, errors)
    src = r["src"]
    chars = page_chars(src)
    missing = sorted(c for c in chars if ord(c) not in cmap_of(FONT_MASTER))
    if missing:  # §19: every character the page sets is in the face
        return gate_log(root, log, [f"font: {FONT_MASTER.name} lacks {[f'U+{ord(c):04X} {c}' for c in missing]}"])
    out = root / "web"
    (out / "fonts").mkdir(parents=True)
    for name in ICONS:
        if name != "og.png":
            shutil.copyfile(ASSETS / name, out / name)
    if og_png:
        (out / "og.png").write_bytes(og_png)
    shutil.copyfile(FONT_LICENCE, out / "fonts" / FONT_LICENCE.name)
    if subset:
        try:
            subset_font(chars, out / FONT_OUT)
            log.append(f"font: {FONT_OUT}, {len(chars)} characters, {(out / FONT_OUT).stat().st_size} bytes")
        except Exception as exc:  # fontTools and brotli are build dependencies; a page without its face fails
            errors.append(f"font subset: {type(exc).__name__}: {exc}")
    else:
        log.append("font: cmap checked, not subset (--selftest: fontTools is no CI dependency)")
    page = out / "index.html"
    page.write_text(src, encoding="utf-8")
    lint_errors, lint_log = lint_gate(root, src, r["title_lines"])
    errors += lint_errors
    log += lint_log
    if browser:
        try:
            measured = browser_pass(page, True)
            r = render(inp, framing, measured, og_png=og_png)
            page.write_text(r["src"], encoding="utf-8")
            seen = browser_pass(page, False)
            heights = seen["heights"]
            errors.extend(f"overflow at {w} px: {n!r}" for w, ns in seen["overflow"].items() for n in ns)
            log.append(f"measured: {measured}")
        except Exception as exc:  # a browser is a build dependency here; say so rather than skip the check
            errors.append(f"browser pass: {type(exc).__name__}: {exc}")
            heights = {}
        if heights and len(heights) != len(r["card_ids"]):
            errors.append(f"card heights: measured {len(heights)} of {len(r['card_ids'])} cards")
        if heights and max(heights.values()) > min(0.6 * 844, 480):
            errors.append(f"a card at 390 is taller than its max-height: {max(heights.items(), key=lambda kv: kv[1])}")
        log.append(f"card heights at 390: {len(heights)} cards, tallest {max(heights.values(), default=0)}px")
    else:
        log.append("browser: not run (--selftest: offline, no browser); widths unmeasured, card heights unchecked")
        if card and card["mode"] == "name":
            log.append(f"card: planned a name card for {card['name']!r} (no logo, E8), not drawn (no browser)")
        elif card:
            log.append(f"card: planned from {card['file']} at {card['wd']}x{card['hd']} device px, not drawn (no browser)")
    log.append(f"wrote {page}")
    return gate_log(root, log, errors)
def _edit_json(path, fn):
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _edit_rows(root, cid, fn):
    p = root / "claims.jsonl"
    rows = [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    for r in rows:
        if r["id"] == cid:
            fn(r)
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def _edit_text(path, old, new):
    s = path.read_text(encoding="utf-8")
    assert old in s, (path, old)
    path.write_text(s.replace(old, new), encoding="utf-8")


def _card_png(w, h, sha_ok=True):
    """A mutation: give the hiring company (coopelec) a w x h RGBA card_file, hashed right or wrong."""
    import zlib

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(b"".join(b"\0" + b"\xff" * 4 * w for _ in range(h)))) + chunk(b"IEND", b""))

    def fn(root, brief):
        (root / "logos/coopelec.card.png").write_bytes(png)
        _edit_json(root / LOGOS_JSON, lambda recs: [r.update(card_file="logos/coopelec.card.png",
                                                             card_sha256=sha(png) if sha_ok else "0" * 64)
                                                    for r in recs if r["slug"] == "coopelec"])
    return fn


def _set(keys, val):
    def fn(root, brief):
        def go(d):
            for k in keys[:-1]:
                d = d[k]
            d[keys[-1]] = val(d[keys[-1]]) if callable(val) else val
        _edit_json(brief, go)
    return fn


# The green base is the committed pair tools/fixtures/web/synthetic.json and synthetic/. Each red case
# mutates a copy and must red naming its own gate. No case needs a browser, fontTools or the network.
SELF_CASES = [
    ("the synthetic brief, N1 framing", None, None, "n1"),
    ("the synthetic brief, T framing", None, None, "t"),
    ("a date in a gloss stays on one line (22f10)",
     lambda root, brief: _edit_rows(root, "C-012", lambda r: r.update(gloss=r["gloss"] + " Its count dates from 3 May 2026.")),
     ("page", "dates from 3&nbsp;May&nbsp;2026."), "n1"),
    # G71: the renderer owns the page's typography. An agent types ASCII and the page prints ’; a field's
    # ends never decide the space at the lede/body or test/why seam.
    ("a straight ' in a gloss prints curled (G71)",
     lambda root, brief: _edit_rows(root, "C-012", lambda r: r.update(gloss=r["gloss"] + " Its count is the company's own.")),
     ("page", "the company’s own."), "n1"),
    ("a straight ' in a source label prints curled (G71)",
     lambda root, brief: _edit_text(root / "sources.tsv", "\tFlexibility Register list\n", "\tFlexibility Register's list\n"),
     ("page", "Flexibility Register’s list</a>"), "n1"),
    ("a straight ' across a span seam prints curled (G71)",
     _set(("recommendations", 0, "why"), lambda w: w[:1] + [{"id": "rec.0.why.1", "t": " Nordvent", "c": "C-007"},
                                                          {"id": "rec.0.why.2", "t": "'s team already chose it.", "c": "C-007"}]),
     ("page", "Nordvent’s team already chose"), "n1"),
    ("a straight ' curl() cannot place in a brief field (G71)",
     _set(("open_questions", 0, 0, "t"), lambda t: t + " Ask the team' now."),
     "brief.open_questions[0]: a straight ' curl() cannot place", "n1"),
    # G72: a plural possessive's s' before a word boundary curls. G76: inside a ‘ too, where ’ closes it.
    ("a plural possessive prints curled (G72)",
     _set(("open_questions", 0, 0, "t"), lambda t: t + " Ask the makers' view of the drivers'."),
     ("page", "Ask the makers’ view of the drivers’."), "n1"),
    ("a quoted phrase ending in s' closes on ’ (G76)",
     _set(("open_questions", 0, 0, "t"), lambda t: t + " They call it ‘the drivers'."),
     ("page", "They call it ‘the drivers’."), "n1"),
    ("an s' after a closed quote prints curled",
     _set(("open_questions", 0, 0, "t"), lambda t: t + " ‘a’ then the drivers'."),
     ("page", "‘a’ then the drivers’."), "n1"),
    ("an s' before a quote opens prints curled",
     _set(("open_questions", 0, 0, "t"), lambda t: t + " the drivers' view, ‘in short’."),
     ("page", "the drivers’ view, ‘in short’."), "n1"),
    # vandelay run 2: a day and month with no year binds, as web-check's pt.marks reads it.
    ("a day and month with no year prints bound",
     _set(("open_questions", 0, 0, "t"), lambda t: t + " From 19 October it bills."),
     ("page", "From 19&nbsp;October it bills."), "n1"),
    # vandelay run 2: a headline quoted inside a quote, and an apostrophe after a full stop.
    ("an opening ' and an Inc.'s print curled",
     _set(("open_questions", 0, 0, "t"), lambda t: t + " They said 'act now' at Acme Inc.'s desk in the '90s."),
     ("page", "They said ‘act now’ at Acme Inc.’s desk in the ’90s."), "n1"),
    # vandelay run 2: a blocked row (the page refused the fetch) has no words to quote; its claim
    # is the record of the refusal and prints behind its own lead.
    ("a blocked row with no quote or gloss prints its claim behind 'Could not read:'",
     lambda root, brief: _edit_rows(root, "C-012", lambda r: (r.update(state="blocked", quote=""), r.pop("gloss", None))),
     ("page", "Could not read:"), "n1"),
    ("a ' after a letter other than s stays straight, so the build fails",
     _set(("open_questions", 0, 0, "t"), lambda t: t + " Ask the team'."),
     "brief.open_questions[0]: a straight ' curl() cannot place", "n1"),
    ("a straight ' curl() cannot place in a gloss (G71)",
     lambda root, brief: _edit_rows(root, "C-012", lambda r: r.update(gloss=r["gloss"] + " Per the team' count.")),
     "C-012: gloss: a straight ' curl() cannot place", "n1"),
    ("a straight ' curl() cannot place in a source label (G71)",
     lambda root, brief: _edit_text(root / "sources.tsv", "\tFlexibility Register list\n", "\tFlexibility Register' list\n"),
     "label for https://register.example/lead-parties: a straight ' curl() cannot place", "n1"),
    ("a cohort name typed with ' builds, its run line curled (G71)",
     lambda root, brief: [_edit_text(f, "Calder Systems", "Calder's Grid") for f in
                          (brief, root / "claims.jsonl", root / "snapshots/calder.example.json", root / "logos/logos.json")],
     ("page", "ZephyrLoads, Calder’s Grid, Mistral"), "n1"),
    ("a body typed with extra leading spaces prints one at the seam (G71)",
     _set(("quick_take", 0, "body", 0, "t"), lambda t: "   " + t.lstrip()),
     ("page", "at scale.</strong> Paraphrased from French: "), "n1"),
    ("a lede and body typed with no space at their seam print one (G71)",
     lambda root, brief: (_set(("quick_take", 0, "lede", 0, "t"), lambda t: t + "  ")(root, brief),
                          _set(("quick_take", 0, "body", 0, "t"), str.lstrip)(root, brief)),
     ("page", "at scale.</strong> Paraphrased from French: "), "n1"),
    ("a test and why typed with no space at their seam print one (G71)",
     _set(("recommendations", 0, "why", 0, "t"), str.lstrip),
     ("page", 'reaches them.</strong> <span class="name">Øresund Flex</span> says'), "n1"),
    ("a lowercase-initial name sits in span.name, so it never hyphenates (G65)", _set(("rivals", 3, "short"), "zephyrloads"),
     ("page", '<span class="card__co"><span class="name">zephyrloads</span></span>'), "n1"),
    ("a name joined to an authored hyphen sits in span.name (G69)",
     lambda root, brief: (_set(("rivals", 3, "short"), "ev.energy")(root, brief),
                          _set(("quick_take", 0, "body", 0, "t"), lambda t: t + " An ev.energy-led pilot is one.")(root, brief)),
     ("page", '<span class="name">ev.energy</span>-led'), "n1"),
    ("a name after an authored hyphen sits in span.name (G69)",
     lambda root, brief: (_set(("rivals", 3, "short"), "ev.energy")(root, brief),
                          _set(("quick_take", 0, "body", 0, "t"), lambda t: t + " A non-ev.energy fleet is one.")(root, brief)),
     ("page", 'non-<span class="name">ev.energy</span> fleet'), "n1"),
    ("a client name typed with ' prints curled in the title and metadata (G76)",
     lambda root, brief: [_edit_text(f, "d’Électricité", "d'Électricité") for f in
                          (brief, root / "claims.jsonl", root / "snapshots/coopelec.example.json")],
     ("page", "<title>Competitor intel brief: Société Coopérative d’Électricité"), "n1"),
    ("a date in a card quote stays on one line (G34)",
     lambda root, brief: _edit_rows(root, "C-010", lambda r: r.update(quote=r["quote"] + " from 3 May 2026")),
     ("page", "home from 3&nbsp;May&nbsp;2026”"), "n1"),
    ("a Markdown link seam in a shown quote (G34)",
     lambda root, brief: _edit_rows(root, "C-010", lambda r: r.update(quote="see [pricing](https://calder.example/pricing)")),
     "C-010: its quote is empty or a page artefact", "n1"),
    ("a character outside the font master", _set(("quick_take", 0, "lede", 0, "t"), lambda t: t.replace("scale", "scaleΩ")),
     "lacks ['U+03A9 Ω']", "n1"),
    ("a cited URL with no sources.tsv label",
     lambda root, brief: _edit_text(root / "sources.tsv", "https://register.example/lead-parties\tFlexibility Register list\n", ""),
     "no label for https://register.example/lead-parties", "n1"),
    ("a cited URL's label of 32 characters (G17)",
     lambda root, brief: _edit_text(root / "sources.tsv", "\tFlexibility Register list\n", "\tFlexibility Register list (2026)\n"),
     "label over 31 characters: Flexibility Register list (2026)", "n1"),
    ("a name that is not its snapshot's", _set(("company", "name"), "Coopélec SA"), "is not snapshots/", "n1"),
    ("a map claim whose subject is the short form",
     lambda root, brief: _edit_rows(root, "C-002", lambda r: r.update(subject="Coopélec")),
     "map Coopélec: C-002 must exist and name", "n1"),
    ("a yes answer resting on an unfound row",
     lambda root, brief: _edit_rows(root, "C-002", lambda r: r.update(state="unfound")),
     "C-002 is unfound, a 'yes' needs verified", "n1"),
    # G10: the lead follows the answer's integration list, and only a quoted integration row takes it.
    ("an integration row, listed, prints the INTEG lead",
     lambda root, brief: (_edit_rows(root, "C-010", lambda r: r.update(claim=r["claim"] + " It is an integration.")),
                          _set(("map", "answers", 4, "down", "integration"), ["C-010"])(root, brief)),
     ("page", INTEG + "</span> “utilities pay per connected home”"), "n1"),
    ("an integration list naming an unquoted row whose claim says integration",
     lambda root, brief: (_edit_rows(root, "C-005", lambda r: r.update(claim=r["claim"] + " It is an integration.")),
                          _set(("map", "answers", 1, "down", "integration"), ["C-005"])(root, brief)),
     "C-005: 'An integration, not named as a customer:' needs a shown quote", "n1"),
    ("an integration list naming a quoted row whose claim says no integration",
     _set(("map", "answers", 4, "down", "integration"), ["C-010"]),
     "C-010: 'An integration, not named as a customer:' needs a shown quote", "n1"),
    ("a rival name inside another rival's (the run-line count, D3)", _set(("rivals", 5, "short"), "Grid"),
     "run line: 'Grid' appears 2 times, want 1", "n1"),
    ("a yes name not verbatim in its claim", _set(("map", "answers", 0, "across", "name"), "Grid Register"),
     "not verbatim in C-002", "n1"),
    ("a cited URL in no snapshot",
     lambda root, brief: _edit_text(root / "snapshots/coopelec.example.json", '"https://coopelec.example/about",', ""),
     "is in no snapshot: https://coopelec.example/about", "n1"),
    ("a brief the schema rejects", _set(("matrix", "heading"), ""), "brief.json:", "n1"),
    ("a non-en row with no gloss", lambda root, brief: _edit_rows(root, "C-012", lambda r: r.pop("gloss")),
     "C-012: Paraphrased from French: needs the row's gloss", "n1"),
    # W18-fix5-verify.md Nice 1: guards shows_quote's `state` term, which no other case reds.
    ("an unfound row with no gloss", lambda root, brief: _edit_rows(root, "C-005", lambda r: r.pop("gloss")),
     "C-005: Searched, not found: needs the row's gloss", "n1"),
    ("a run date the fetch index does not hold", _set(("run_date",), "2026-10-02"), "run date:", "n1"),
    # The share card (the operator, 2026-10-12): a raster logo is only ever downscaled, from bytes logos.json pins.
    ("a raster card_file at least the card's logo box builds; with no browser the card is unrendered",
     _card_png(1000, 400), ("page", "/coopelec/og.png?v=unrendered"), "n1"),
    # The card's URL carries its own content hash (e-publish § Q4), so a changed card is a new URL.
    ("T's shared card: og:image's ?v= is its sha256's first 12 hex",
     None, ("page", "/competitor-intel-agent/og.png?v=" + hashlib.sha256((ASSETS / "og.png").read_bytes()).hexdigest()[:12]), "t"),
    # E8: no brief fails for lack of a logo; the card sets the company's name instead.
    ("a hiring company with no logo builds (E8)", _set(("company", "logo"), None),
     ("page", "/coopelec/og.png?v=unrendered"), "n1"),
    # D4: dates.evidence is the claim-backing pages' fetch window, dates.page the stamp the final build sets.
    ("dates: a one-day window prints one day; the page date is metadata",
     _set(("dates",), {"evidence": {"from": "2026-10-01", "to": "2026-10-01"}, "page": "2026-10-03"}),
     ("page", 'On 1&nbsp;October, the agent read'), "n1"),
    ("dates: the page date is the page's published_time",
     _set(("dates",), {"evidence": {"from": "2026-10-01", "to": "2026-10-01"}, "page": "2026-10-03"}),
     ("page", '<meta property="article:published_time" content="2026-10-03">'), "n1"),
    ("dates: a run across midnight prints its window",
     lambda root, brief: (_edit_text(root / "pages/index.tsv", "\t200\t2026-10-01T09:00:00Z\t6d9fa9cb", "\t200\t2026-10-02T00:10:00Z\t6d9fa9cb"),
                          _set(("dates",), {"evidence": {"from": "2026-10-01", "to": "2026-10-02"}, "page": "2026-10-02"})(root, brief)),
     ("page", 'From 1 to 2&nbsp;October, the agent read'), "n1"),
    ("dates: an evidence window the fetch index does not hold",
     _set(("dates",), {"evidence": {"from": "2026-09-30", "to": "2026-10-01"}, "page": "2026-10-01"}),
     "evidence dates:", "n1"),
    ("a raster card_file smaller than the card's logo box (never upscaled)", _card_png(999, 400),
     "a logo is never upscaled", "n1"),
    ("a card_file whose bytes logos.json does not pin", _card_png(1000, 400, sha_ok=False),
     "card: logos/coopelec.card.png does not hash", "n1"),
    ("a logo file changed after its gate",
     lambda root, brief: (root / "logos/coopelec.svg").write_bytes((root / "logos/coopelec.svg").read_bytes() + b" "),
     "logo not gated", "n1"),
]


def selftest():
    """Every case on a fresh copy of the synthetic pair, offline, with no browser."""
    import contextlib, io
    fx, failed = ROOT / "tools/fixtures/web", []
    for name, mutate, want, framing in SELF_CASES:
        with tempfile.TemporaryDirectory() as d:
            root, brief = Path(d) / "run", Path(d) / "brief.json"
            shutil.copytree(fx / "synthetic", root)
            shutil.copyfile(fx / "synthetic.json", brief)
            if mutate:
                mutate(root, brief)
            with contextlib.redirect_stdout(io.StringIO()):
                code = build(root, brief, framing, browser=False, subset=False)
            logs = sorted((root / "audit").glob("gate-*.txt"))
            got = logs[-1].read_text(encoding="utf-8") if logs else ""
            page = root / "web/index.html"
            if isinstance(want, tuple):  # green, and the page carries the string
                src = page.read_text(encoding="utf-8") if page.is_file() else ""
                ok = code == 0 and want[1] in src
                why = "" if ok else f"exit {code}, want {want[1]!r} on the page\n{got[-600:]}"
            elif want is None:
                src = page.read_text(encoding="utf-8") if page.is_file() else ""
                # D10: a brief's address is SITE/<company.slug>/, the path the site serves with a 200.
                site = SITE + "/" + ("competitor-intel-agent" if framing == "t" else "coopelec/")
                ok = (code == 0 and f'<link rel="canonical" href="{site}">' in src
                      and f'<meta property="og:url" content="{site}">' in src
                      and ('<aside class="banner"' in src) == (framing == "t")
                      and "Bourgogne-Franche-Comté brief, made with" in page_text(src))
                why = "" if ok else f"exit {code}, page {'present' if src else 'absent'}\n{got[-600:]}"
            else:
                ok = code == 1 and want in got and not page.is_file()  # a failed render writes no page
                why = "" if ok else f"exit {code}, want {want!r}\n{got[-600:]}"
            print(f"{'ok  ' if ok else 'FAIL'} {'red  ' if isinstance(want, str) else 'green'} {name}")
            if not ok:
                failed.append(f"{name}: {why}")
    # G27: a stage run exports BRIEF_ROOT, and a run root holds no headings.json; the lint gate must
    # still grade, never exit 2 on the missing record nor read the exemplar's.
    import os
    with tempfile.TemporaryDirectory() as d:
        root, brief = Path(d) / "run", Path(d) / "brief.json"
        shutil.copytree(fx / "synthetic", root)
        shutil.copyfile(fx / "synthetic.json", brief)
        old_env = os.environ.get("BRIEF_ROOT")
        os.environ["BRIEF_ROOT"] = str(root)
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                code = build(root, brief, "n1", browser=False, subset=False)
        finally:
            os.environ.pop("BRIEF_ROOT") if old_env is None else os.environ.update(BRIEF_ROOT=old_env)
        got = sorted((root / "audit").glob("gate-*.txt"))[-1].read_text(encoding="utf-8")
        ok = code == 0 and "voice-lint exit 0" in got
        print(f"{'ok  ' if ok else 'FAIL'} green BRIEF_ROOT exported at a root with no headings.json (G27)")
        if not ok:
            failed.append(f"G27 exported BRIEF_ROOT: exit {code}\n{got[-600:]}")
        # G49: --template prints the template's lines (nav, the run line, both typed header rows,
        # INTEG) and none of the page's other lines: no authored word, card line or source line.
        src = (root / "web/index.html").read_text(encoding="utf-8") if code == 0 else ""
        tpl = [ln for ln in template_text(src).split("\n") if ln.strip()]
        auth = [ln for ln in authored_text(json.loads(brief.read_text(encoding="utf-8"))).split("\n") if ln.strip()]
        want = ["Email me", " the agent read ", MOVES_HEAD[1], MATRIX_CORNER + " , ", INTEG]
        missing = [w for w in want if not any(w in ln for ln in tpl)]
        leaked = [ln for ln in tpl if any(a in ln for a in auth)]
        words = Words()
        words.feed(src)
        words.flush()
        cards = [ln for ln in tpl if ln in words.cards]
        ok = src and not missing and not leaked and not cards
        print(f"{'ok  ' if ok else 'FAIL'} red   --text --template prints the template's lines only (G49)")
        if not ok:
            failed.append(f"--template: missing {missing}, authored {leaked[:2]}, card lines {cards[:2]}")
    # G28: --authored carries the brief's own words and no template string, so B1 never meets the run
    # line or a "source N" name; a q span keeps its curly pair for B4, a g span drops the lead.
    base = json.loads((fx / "synthetic.json").read_text(encoding="utf-8"))
    auth = authored_text(base)
    template = [t for t in ("the agent read", "Email me", "Paraphrased from", "source ", "Also built",
                            "Next step") if t in auth]
    authored = [t for t in ("“1,200 home batteries”", "Mistral Réseaux says it controls 40,000 heaters",
                            "Who trades, who pays", "No maker named") if t not in auth]
    walked = [t for t in authored_strings(base) if t not in auth]  # G34: every authored field, walked
    ok = not template and not authored and not walked
    print(f"{'ok  ' if ok else 'FAIL'} red   --text --authored prints authored words only, every field (G28, G34)")
    if not ok:
        failed.append(f"--authored: template strings {template}, missing authored {authored}, unwalked {walked[:3]}")
    # G71: the lede/body seam takes one space whatever the spans' ends, so the lints never read "scale.Mistral".
    bare = json.loads(json.dumps(base))
    bare["quick_take"][0]["body"][0]["t"] = bare["quick_take"][0]["body"][0]["t"].lstrip()
    ok = authored_text(bare) == auth and "at scale. Mistral" in auth
    print(f"{'ok  ' if ok else 'FAIL'} green --text --authored joins lede and body with one space (G71)")
    if not ok:
        failed.append(f"--authored seam: {authored_text(bare).split(chr(10))[0][:90]!r}")
    if failed:
        print("SELFTEST FAIL\n" + "\n".join(failed))
        return 1
    print(f"SELFTEST OK ({sum(isinstance(w, str) for _, _, w, _ in SELF_CASES) + 1} red, "
          f"{sum(not isinstance(w, str) for _, _, w, _ in SELF_CASES) + 1} green)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render a run's brief.json to its web page, and audit it.")
    ap.add_argument("root", nargs="?", help="BRIEF_ROOT; default $BRIEF_ROOT")
    ap.add_argument("--brief", help="the brief.json to render; default BRIEF_ROOT/brief.json")
    ap.add_argument("--framing", choices=sorted(FRAMINGS), default="n1")
    ap.add_argument("--text", metavar="PAGE", help="print a page's text and exit")
    ap.add_argument("--authored", action="store_true",
                    help="with --text BRIEF_JSON: print the brief's authored words only, no template string")
    ap.add_argument("--template", action="store_true",
                    help="with --text PAGE: print only the lines the page's template prints (G49)")
    ap.add_argument("--card", metavar="BRIEF_ROOT", help="render that run's share card alone, to --out")
    ap.add_argument("--out", metavar="PNG", help="with --card: where the card is written")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if bool(a.card) != bool(a.out):
        sys.stderr.write("FAIL: --card BRIEF_ROOT and --out PNG go together\n")
        return 2
    if a.card:
        return card_only(a.card, a.out)
    if a.authored and not a.text:
        sys.stderr.write("FAIL: --authored qualifies --text BRIEF_JSON\n")
        return 2
    if a.template and (not a.text or a.authored):
        sys.stderr.write("FAIL: --template qualifies --text PAGE, never --authored\n")
        return 2
    if a.text:
        src = Path(a.text).read_text(encoding="utf-8")
        if a.authored:
            try:
                sys.stdout.write(authored_text(json.loads(src)))
            except (ValueError, KeyError, TypeError, IndexError) as exc:
                sys.stderr.write(f"FAIL: {a.text} is not a brief.json brief-check passes ({exc!r})\n")
                return 2
            return 0
        sys.stdout.write(template_text(src) if a.template else page_text(src))
        return 0
    import os
    root = a.root or os.environ.get("BRIEF_ROOT")
    if not root or not Path(root).is_dir():
        sys.stderr.write("FAIL: name a BRIEF_ROOT directory, or set $BRIEF_ROOT\n")
        return 2
    brief = Path(a.brief) if a.brief else Path(root) / "brief.json"
    if not brief.is_file():
        sys.stderr.write(f"FAIL: no brief.json at {brief}\n")
        return 2
    return build(root, brief, a.framing)


if __name__ == "__main__":
    sys.exit(main())
