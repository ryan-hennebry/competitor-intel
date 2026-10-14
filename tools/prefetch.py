#!/usr/bin/env python3
"""Prefetch a run's pages in code before any agent reads them (Globex design § 3, `prefetch-client`
and `prefetch-rivals` nodes).

WHY THIS EXISTS. Globex's agents spent 74-244 s of each discovery and extraction turn in curl loops
(find-T row 2), and the reader resolved the job ad by hand. Fetching is byte work: these two nodes
do it 16 at a time through `tools/fetch.py --json`, so every page lands in `pages/` with its text
layer and index row before the agent that quotes it is spawned.

  prefetch.py client BRIEF_ROOT [--jd URL]
      The job ad and the client's own site. The URL is `--jd` or `$RUN_ROOT/run.json` `jd_url`.
      1. The ad. A board the code knows is read through its own API (BOARDS): Workable's job page is
         a JS app whose ad sits at `api/v2/accounts/<account>/jobs/<shortcode>`, and its account
         widget carries the company's own paragraph and the sibling postings. The page itself is
         fetched too, for its JobPosting JSON-LD. Neither the ad nor the page fetched with a 2xx:
         STOP jd-unreachable. Nor when the richer of the two text layers (fetch.py renders a JS
         shell, given AD_CHROME_TIMEOUT) holds under AD_PROSE_MIN prose characters: a shell is
         never passed downstream. `ad_prose` records the count.
      2. The company, in order: JSON-LD `hiringOrganization.name`, the board's account name,
         `og:site_name`, the last <title> segment, the board account or Notion workspace in the
         URL. Platform names (PLATFORMS) never count. None found: STOP no-company. This is
         AGENTS.md's hard stop: a JD that is unreachable or does not identify the company.
      3. The client's home page, when the ad links it (`hiringOrganization.sameAs` or `url`, or a
         "website" link): the home page, its llms.txt and sitemap.xml, and up to CLIENT_LINKS
         same-host links from the home page, the client's own lists and pricing first.
      Writes `captures/jd.json`: `state` OK or STOP, the typed `stop` and `reason`, the company,
      `home_url`, `positioning_pages` (home, the board's company page, llms.txt; the reader node's
      gate joins its positioning lines to them) and every fetch with its state.
  prefetch.py rivals BRIEF_ROOT
      For each `names.json` rival: its home page, sitemap.xml, and up to two pricing and three
      case or customer pages linked from them. Writes `captures/rivals.json` and `id-blocks.json`,
      each part's claim ID block (`tools/node-check.py` § ID BLOCKS), which the extractors read.
  prefetch.py --selftest     offline: a local server and a mirror, fetch.py with no Chrome

A fetch that is blocked or not reached is a state, recorded, never a failure of this tool.
INTEL_PREFETCH_MIRROR=<dir> is the test seam: `https://<host>/<path>` is read from
`file://<dir>/<host>/<path>` (`index.html` for a bare path) and indexed under the https URL.

EXIT CODES. 0 done. 3 STOP (client only; captures/jd.json says which). 2 bad usage or an
unreadable input. Stdlib only.
"""
import concurrent.futures as cf
import html
import http.server
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import threading
import urllib.parse

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parent.parent
FETCH = ROOT / "tools" / "fetch.py"
JOBS = 16
CLIENT_LINKS = 24
PRICING_MAX, CASES_MAX = 2, 3
PLATFORMS = {"notion", "workable", "ashby", "greenhouse", "lever", "linkedin", "indeed", "careers",
             "jobs", "job board", "apply", "recruitee", "teamtailor", "personio", "bamboohr",
             "breezy", "wellfound", "otta", "welcome to the jungle", "join", "careers page"}
PLATFORM_HOSTS = ("notion.site", "notion.so", "workable.com", "ashbyhq.com", "greenhouse.io",
                  "lever.co", "linkedin.com", "indeed.com", "recruitee.com", "teamtailor.com",
                  "personio.de", "bamboohr.com", "breezy.hr", "fillout.com", "typeform.com",
                  "google.com", "twitter.com", "x.com", "facebook.com", "instagram.com")
CLIENT_PRIORITY = re.compile(r"pric|plan|customer|client|case|stor|testimon|partner|integrat|"
                             r"\bvs\b|-vs-|compar|alternativ|about|team|product|solution|platform|"
                             r"terms|legal", re.I)
PRICING = re.compile(r"pric|/plans?\b", re.I)
CASES = re.compile(r"case-stud|customer|success-stor|/clients?\b|testimonial|/stories", re.I)
ASSET = re.compile(r"\.(png|jpe?g|gif|svg|webp|ico|css|js|mjs|json|xml|pdf|zip|mp4|woff2?)(\?|$)", re.I)
STOP_EXIT = 3
FIXTURES = ROOT / "tools" / "fixtures" / "prefetch"
# [INFERRED] The least prose a job ad's text layer may carry: a JS shell measured 0 (Notion),
# rendered ads 2,625 to 3,974; the selftest's synthetic ads carry 600.
AD_PROSE_MIN = 500
# Seconds fetch.py lets Chrome render the job ad (FETCH_CHROME_TIMEOUT; other pages keep its 20 s).
# Measured: the Notion ad's render took 17.0 s of the 20 s default; the reader's 45 s retry kept it.
AD_CHROME_TIMEOUT = 45


# ---- fetching --------------------------------------------------------------------------------

def mirror_path(url):
    mirror = os.environ.get("INTEL_PREFETCH_MIRROR")
    if not mirror:
        return None
    u = urllib.parse.urlparse(url)
    path = u.path or "/"
    if path.endswith("/"):
        path += "index.html"
    return pathlib.Path(mirror) / (u.hostname or "") / path.lstrip("/")


def fetch(brief, url, chrome_timeout=None):
    """fetch.py --json on one URL: {url, state, status, path, exit}. Never raises.
    `chrome_timeout` overrides fetch.py's render wait (FETCH_CHROME_TIMEOUT), in seconds."""
    args = [sys.executable, str(FETCH), url, "--json"]
    local = mirror_path(url)
    if local is not None:
        args = [sys.executable, str(FETCH), "file://" + str(local), "--as-url", url, "--json"]
    env = dict(os.environ, BRIEF_ROOT=str(brief), PYTHONDONTWRITEBYTECODE="1")
    if chrome_timeout:
        env["FETCH_CHROME_TIMEOUT"] = str(chrome_timeout)
    try:
        p = subprocess.run(args, env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           timeout=120)
        said = {}
        for line in reversed(p.stdout.splitlines()):
            if line.startswith("{"):
                said = json.loads(line)
                break
    except (subprocess.TimeoutExpired, ValueError) as exc:
        return {"url": url, "state": "FAILED", "status": None, "path": None, "exit": 1, "note": str(exc)}
    out = {k: said.get(k) for k in ("url", "state", "status", "path", "exit")}
    out["url"] = url
    out["state"] = out.get("state") or "FAILED"
    return out


def ok(rec):
    """A page fetched with a 2xx, or a mirror capture (curl reports 000 for file://)."""
    status = str(rec.get("status") or "")
    return rec.get("state") == "FETCHED" and (status.startswith("2") or (
        status == "000" and bool(os.environ.get("INTEL_PREFETCH_MIRROR"))))


def canon(url):
    """One key per page: scheme, `www.` and a trailing slash do not make a second page."""
    u = urllib.parse.urlparse(url)
    host = (u.hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    return (host, u.path.rstrip("/") or "/", u.query)


def fetch_all(brief, urls, chrome_timeout=None):
    keys, kept = set(), []
    for u in urls:
        if u and canon(u) not in keys:
            keys.add(canon(u))
            kept.append(u)
    urls = kept
    with cf.ThreadPoolExecutor(max_workers=JOBS) as ex:
        return list(ex.map(lambda u: fetch(brief, u, chrome_timeout), urls))


def final_url(brief, rec):
    """The URL the fetch landed on (pages/index.tsv `final_url`), so relative links resolve
    against the page a redirect served, not the address asked for."""
    for row in index_rows(brief):
        if rec and row.get("path") == rec.get("path") and str(row.get("final_url", "")).startswith("http"):
            return row["final_url"]
    return rec.get("url") if rec else None


def body(brief, rec):
    if not rec or not rec.get("path"):
        return ""
    try:
        return (brief / rec["path"]).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def ad_prose(brief, rec):
    """Prose characters on a fetched page's text layer, as fetch.py counts them (every line but
    image and meta lines); 0 when it wrote none. The layer is the one fetch.py kept, so a shell
    Chrome rendered counts its rendered text."""
    txt = brief / (rec.get("path") or "")
    try:
        lines = txt.with_suffix(".txt").read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError):
        return 0
    return load_fetch().prose_chars(lines)


def fetch_method(brief, rec):
    """How fetch.py got the page (`pages/methods.tsv`: curl, chrome, chrome-failed, ...)."""
    path = brief / "pages" / "methods.tsv"
    rows = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    return next((l.split("\t")[1] for l in reversed(rows) if l.split("\t")[0] == rec.get("path")), "unknown")


# ---- reading a page --------------------------------------------------------------------------

def json_ld(text):
    out = []
    for m in re.finditer(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", text, re.S | re.I):
        try:
            data = json.loads(html.unescape(m.group(1)).strip())
        except ValueError:
            continue
        stack = [data]
        while stack:
            d = stack.pop()
            if isinstance(d, list):
                stack += d
            elif isinstance(d, dict):
                out.append(d)
                stack += [v for v in d.values() if isinstance(v, (dict, list))]
    return out


def hiring_org(text):
    for d in json_ld(text):
        org = d.get("hiringOrganization")
        if isinstance(org, dict) and org.get("name"):
            return org
    return None


def meta(text, prop):
    m = re.search(r"<meta[^>]+(?:property|name)=[\"']%s[\"'][^>]*>" % re.escape(prop), text, re.I)
    if not m:
        return None
    c = re.search(r"content=[\"']([^\"']*)[\"']", m.group(0), re.I)
    return html.unescape(c.group(1)).strip() if c else None


def title(text):
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(m.group(1))).strip() if m else None


def platform(name):
    return not name or name.strip().lower() in PLATFORMS


def unplatform(name):
    """`acme on Notion` is the workspace `acme`: a platform suffix is dropped, never the name."""
    m = re.fullmatch(r"(.+?) on (\w[\w ]*)", (name or "").strip())
    return m.group(1).strip() if m and m.group(2).lower() in PLATFORMS else name


def links(text, base):
    out = []
    for m in re.finditer(r"""href\s*=\s*["']([^"'#]+)""", text, re.I):
        href = html.unescape(m.group(1)).strip()
        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        out.append(urllib.parse.urljoin(base, href))
    for m in re.finditer(r"<loc>\s*([^<\s]+)\s*</loc>", text, re.I):
        out.append(html.unescape(m.group(1)))
    return out


def same_site(a, b):
    ha, hb = (urllib.parse.urlparse(x).hostname or "" for x in (a, b))
    strip = lambda h: h[4:] if h.startswith("www.") else h
    return bool(ha) and strip(ha) == strip(hb)


def site_root(url):
    u = urllib.parse.urlparse(url)
    return f"{u.scheme}://{u.netloc}/"


def website_link(text, base):
    for m in re.finditer(r"<a\b([^>]*)>(.*?)</a>", text, re.S | re.I):
        label = re.sub(r"<[^>]+>|\s+", " ", m.group(2)).strip().lower()
        h = re.search(r"""href\s*=\s*["']([^"']+)""", m.group(1), re.I)
        if h and (re.fullmatch(r"(view |visit )?(our |company )?website", label) or "company-url" in m.group(1)):
            return urllib.parse.urljoin(base, html.unescape(h.group(1)))
    return None


def platform_host(url):
    host = urllib.parse.urlparse(url or "").hostname or ""
    return any(host == h or host.endswith("." + h) for h in PLATFORM_HOSTS)


# ---- the job ad ------------------------------------------------------------------------------

def board(jd_url):
    """(kind, account, ad_url, company_url) for a board the code knows, else (None, None, jd, None)."""
    u = urllib.parse.urlparse(jd_url)
    host, parts = (u.hostname or "").lower(), [p for p in u.path.split("/") if p]
    if host == "apply.workable.com" and len(parts) >= 3 and parts[1] == "j":
        acct, code = parts[0], parts[2]
        return ("workable", acct, f"https://apply.workable.com/api/v2/accounts/{acct}/jobs/{code}",
                f"https://apply.workable.com/api/v1/widget/accounts/{acct}?details=true")
    if host.endswith("ashbyhq.com") and parts:
        return ("ashby", parts[0],
                f"https://api.ashbyhq.com/posting-api/job-board/{parts[0]}?includeCompensation=true", None)
    if host.endswith("greenhouse.io") and parts:
        return ("greenhouse", parts[0], f"https://boards-api.greenhouse.io/v1/boards/{parts[0]}/jobs?content=true", None)
    if host.endswith("lever.co") and parts:
        return ("lever", parts[0], f"https://api.lever.co/v0/postings/{parts[0]}?mode=json", None)
    if host.endswith(".notion.site"):
        return ("notion", host.split(".")[0], jd_url, None)
    return (None, None, jd_url, None)


def company_of(jd_url, kind, account, page, ad, widget):
    """(name, source, home_url) read off the fetched ad, or (None, None, None)."""
    for text in (page, ad):
        org = hiring_org(text)
        if org and not platform(org.get("name")):
            home = org.get("sameAs") or org.get("url")
            home = home[0] if isinstance(home, list) and home else home
            home = home if isinstance(home, str) and home.startswith("http") and not platform_host(home) else None
            return org["name"].strip(), "json-ld", home or website_link(page, jd_url)
    try:
        acct = json.loads(widget) if widget.strip().startswith("{") else {}
    except ValueError:
        acct = {}
    home = website_link(page, jd_url)
    if acct.get("name") and not platform(acct["name"]):
        return acct["name"].strip(), "board-account", home
    site = unplatform(meta(page, "og:site_name"))
    if site and not platform(site):
        return site, "og:site_name", home
    segs = [s.strip() for s in re.split(r"\s+[|\-–—]\s+|\s+at\s+", title(page) or "") if s.strip()]
    if len(segs) >= 2 and not platform(segs[-1]):
        return segs[-1], "title", home
    if account and kind in ("workable", "ashby", "greenhouse", "lever", "notion"):
        return account, "url", home
    return None, None, None


def stop(brief, kind, reason, record):
    record.update(state="STOP", stop=kind, reason=reason)
    write(brief / "captures" / "jd.json", record)
    print(f"STOP {kind}: {reason}", file=sys.stderr)
    return STOP_EXIT


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def client(brief, jd_url):
    kind, account, ad_url, company_url = board(jd_url)
    record = {"jd_url": jd_url, "board": kind, "ad_url": ad_url, "company_url": company_url}
    first = fetch_all(brief, [jd_url, ad_url, company_url], AD_CHROME_TIMEOUT)
    by = {r["url"]: r for r in first}
    record["pages"] = first
    page, ad = by.get(jd_url), by.get(ad_url)
    if not (ok(page) or ok(ad)):
        why = "; ".join(f"{r['url']} {r['state']} {r.get('status')}" for r in (page, ad) if r)
        return stop(brief, "jd-unreachable", f"the job ad did not fetch with a 2xx: {why}", record)
    shown = [(ad_prose(brief, r), r) for r in (page, ad) if ok(r)]
    record["ad_prose"] = max(n for n, _ in shown)
    if record["ad_prose"] < AD_PROSE_MIN:
        how = "; ".join(f"{r['url']} {n} ({fetch_method(brief, r)})" for n, r in shown)
        return stop(brief, "jd-unreachable", f"the job ad fetched but its text never loaded: "
                    f"{record['ad_prose']} prose characters, under {AD_PROSE_MIN} ({how}). A script "
                    f"shell the render could not fill is no ad an agent may read", record)
    name, source, home = company_of(jd_url, kind, account, body(brief, page) if ok(page) else "",
                                    body(brief, ad) if ok(ad) else "",
                                    body(brief, by.get(company_url)) if company_url and ok(by.get(company_url)) else "")
    if not name:
        return stop(brief, "no-company", f"no company name on {jd_url}: no JobPosting hiringOrganization, "
                    "board account, og:site_name, company <title> segment or board account in the URL", record)
    record["company"] = {"name": name, "source": source}
    record["home_url"] = home
    pos = []
    if company_url:
        pos.append({"kind": "company", "url": company_url, "state": "FETCHED" if ok(by.get(company_url)) else "MISSING"})
    if home:
        root = site_root(home)
        wave = fetch_all(brief, [home, root + "llms.txt", root + "sitemap.xml"])
        got = {r["url"]: r for r in wave}
        cands = [l for r in wave if ok(r) for l in links(body(brief, r), final_url(brief, r))]
        done = {canon(u) for u in got}
        cands = [l for l in dict.fromkeys(cands) if same_site(l, home) and not ASSET.search(l)
                 and canon(l) not in done]
        cands = [l for _, l in sorted(enumerate(cands), key=lambda x: (
            not CLIENT_PRIORITY.search(urllib.parse.urlparse(x[1]).path), x[0]))]
        more = fetch_all(brief, cands[:CLIENT_LINKS])
        record["pages"] += wave + more
        for k, u in (("home", home), ("llms", root + "llms.txt")):
            pos.append({"kind": k, "url": u, "state": "FETCHED" if ok(got.get(u)) else "MISSING"})
    record["positioning_pages"] = pos
    record["state"] = "OK"
    write(brief / "captures" / "jd.json", record)
    good = sum(1 for r in record["pages"] if ok(r))
    print(f"PREFETCH CLIENT OK {name} ({source}); home {home or 'not linked from the ad'}; "
          f"{good} of {len(record['pages'])} pages fetched")
    return 0


# ---- rivals ----------------------------------------------------------------------------------

def index_rows(brief):
    path = brief / "pages" / "index.tsv"
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    head = lines[0].split("\t") if lines else []
    return [dict(zip(head, l.split("\t"))) for l in lines[1:]]


def rivals(brief):
    names = json.loads((brief / "names.json").read_text(encoding="utf-8"))
    if not isinstance(names, list) or not all(isinstance(r, dict) and r.get("slug") for r in names):
        raise ValueError("names.json is not a list of rows with a slug")
    nc = load_node_check()
    blocks = nc.blocks(names)
    write(brief / "id-blocks.json", {k: [nc.fmt(a), nc.fmt(z)] for k, (a, z) in blocks.items()})
    by_stem = {pathlib.Path(r.get("path", "")).stem: r for r in index_rows(brief)}
    homes = {}
    for r in names:
        seen = by_stem.get(r.get("page_id"))
        url = (seen or {}).get("url") or f"https://{r['domain']}/"
        homes[r["slug"]] = site_root(url)
    wave = fetch_all(brief, [u for h in homes.values() for u in (h, h + "sitemap.xml")])
    got = {r["url"]: r for r in wave}
    plan, report = [], {}
    for slug, home in homes.items():
        found = [l for u in (home, home + "sitemap.xml") if ok(got.get(u))
                 for l in links(body(brief, got[u]), final_url(brief, got[u]))]
        done = {canon(home), canon(home + "sitemap.xml")}
        found = [l for l in dict.fromkeys(found) if same_site(l, home) and not ASSET.search(l)
                 and canon(l) not in done]
        pick = [l for l in found if PRICING.search(urllib.parse.urlparse(l).path)][:PRICING_MAX]
        pick += [l for l in found if CASES.search(urllib.parse.urlparse(l).path) and l not in pick][:CASES_MAX]
        plan += pick
        report[slug] = {"home": home, "links": pick}
    more = {r["url"]: r for r in fetch_all(brief, plan)}
    for slug, rep in report.items():
        home = rep["home"]
        rep["pages"] = [got.get(home), got.get(home + "sitemap.xml")] + [more.get(l) for l in rep.pop("links")]
        rep["pages"] = [p for p in rep["pages"] if p]
    write(brief / "captures" / "rivals.json", report)
    n = sum(len(v["pages"]) for v in report.values())
    good = sum(1 for v in report.values() for p in v["pages"] if ok(p))
    print(f"PREFETCH RIVALS OK {len(names)} rivals, {good} of {n} pages fetched; id-blocks.json written")
    return 0


def load_fetch():
    spec = importlib.util.spec_from_file_location("intel_fetch", FETCH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_node_check():
    spec = importlib.util.spec_from_file_location("node_check", ROOT / "tools" / "node-check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(argv):
    args = argv[1:]
    if args == ["--selftest"]:
        return selftest()
    try:
        if len(args) in (2, 4) and args[0] == "client":
            brief = pathlib.Path(args[1])
            if len(args) == 4:
                if args[2] != "--jd":
                    raise ValueError("client takes --jd URL")
                jd = args[3]
            else:
                run = pathlib.Path(os.environ.get("RUN_ROOT", "")) / "run.json"
                jd = json.loads(run.read_text(encoding="utf-8")).get("jd_url")
                if not jd:
                    raise ValueError(f"{run} has no jd_url")
            return client(brief, jd)
        if len(args) == 2 and args[0] == "rivals":
            return rivals(pathlib.Path(args[1]))
    except (OSError, ValueError, KeyError) as exc:
        print(f"prefetch: {exc}", file=sys.stderr)
        return 2
    print(__doc__, file=sys.stderr)
    return 2


# ---- selftest --------------------------------------------------------------------------------

FAILS = []


def case(label, good, detail=""):
    print(f"SELFTEST {'OK  ' if good else 'FAIL'} {label}" + ("" if good else f": {detail}"))
    if not good:
        FAILS.append(label)


class _Site(http.server.BaseHTTPRequestHandler):
    pages = {}

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        text = self.pages.get(path)
        if text is None:
            self.send_response(404)
            self.end_headers()
            return
        data = text.replace("{BASE}", f"http://127.0.0.1:{self.server.server_address[1]}").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain" if path.endswith((".txt", ".xml")) else "text/html")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


PROSE = "<p>" + "Acme builds the ledger every finance team reconciles against, every day. " * 8 + "</p>"
SITE = {
    "/jd-good.html": ('<html><head><title>Head of Growth</title><script type="application/ld+json">'
                      '{"@type":"JobPosting","title":"Head of Growth","hiringOrganization":{"@type":"Organization",'
                      '"name":"Acme","sameAs":"{BASE}/"}}</script></head><body>' + PROSE + '</body></html>'),
    "/jd-nameless.html": "<html><head><title>Founding Engineer</title></head><body>" + PROSE + "</body></html>",
    "/": ('<html><head><title>Acme | Ledgers</title></head><body>' + PROSE +
          '<a href="/pricing">Pricing</a><a href="/customers">Customers</a><a href="/logo.png">x</a>'
          '<a href="https://elsewhere.example/">out</a></body></html>'),
    "/pricing": "<html><body>" + PROSE + "</body></html>",
    "/customers": "<html><body>" + PROSE + "</body></html>",
    "/llms.txt": "# Acme\n\nAcme builds the ledger every finance team reconciles against.\n",
    "/sitemap.xml": "<urlset><url><loc>{BASE}/blog/one</loc></url></urlset>",
    "/blog/one": "<html><body>" + PROSE + "</body></html>",
    "/jd-shell.html": (FIXTURES / "notion-ad-shell.html").read_text(encoding="utf-8"),
}


def mirror_site(mirror):
    def put(rel, text):
        p = mirror / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    put("apply.workable.com/acme/j/ABC123/index.html",
        '<html><head><title>Head of Growth - acme</title></head><body>' + PROSE + "</body></html>")
    put("apply.workable.com/api/v2/accounts/acme/jobs/ABC123",
        json.dumps({"title": "Head of Growth", "description": "<p>Own growth.</p>"}))
    put("apply.workable.com/api/v1/widget/accounts/acme",
        json.dumps({"name": "Acme Ledgers", "description": "<p>Acme builds ledgers.</p>", "jobs": []}))
    put("acme.notion.site/founders-associate", '<html><head><title>Founders Associate</title>'
        '<meta property="og:site_name" content="acme on Notion"></head><body>' + PROSE + "</body></html>")
    for host, story in (("rival.example", "customers/bigco"), ("www.other.example", "case-studies/one")):
        put(f"{host}/index.html", f'<html><head><title>{host}</title></head><body>{PROSE}'
            f'<a href="/pricing">Pricing</a><a href="/{story}">Story</a><a href="/careers">Jobs</a></body></html>')
        put(f"{host}/sitemap.xml", f"<urlset><url><loc>https://{host}/plans</loc></url></urlset>")
        for rel in ("pricing", story, "plans"):
            put(f"{host}/{rel}", "<html><body>" + PROSE + "</body></html>")


def run_child(args, brief, extra=None):
    env = dict(os.environ, FETCH_CHROME=str(brief.parent / "no-chrome"), PYTHONDONTWRITEBYTECODE="1")
    env.pop("INTEL_PREFETCH_MIRROR", None)
    env.update(extra or {})
    return subprocess.run([sys.executable, str(pathlib.Path(__file__).resolve())] + args, env=env,
                          capture_output=True, text=True, stdin=subprocess.DEVNULL)


def selftest():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), type("Site", (_Site,), {"pages": SITE}))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        with tempfile.TemporaryDirectory() as t:
            tmp = pathlib.Path(t)
            b = tmp / "good"
            p = run_child(["client", str(b), "--jd", base + "/jd-good.html"], b)
            jd = json.loads((b / "captures" / "jd.json").read_text()) if (b / "captures" / "jd.json").is_file() else {}
            fetched = {r["url"] for r in jd.get("pages", []) if r.get("state") == "FETCHED"}
            case("client: a JD naming its company is OK, with the company and home page off its JSON-LD",
                 p.returncode == 0 and jd.get("state") == "OK" and jd.get("company") == {"name": "Acme", "source": "json-ld"}
                 and jd.get("home_url") == base + "/", (p.returncode, p.stderr[-600:], jd.get("company")))
            case("client: the home page, llms.txt, sitemap and same-site links are fetched; assets and other sites are not",
                 {base + "/", base + "/llms.txt", base + "/sitemap.xml", base + "/pricing", base + "/customers",
                  base + "/blog/one"} <= fetched and not any("logo.png" in u or "elsewhere" in u for u in fetched),
                 sorted(fetched))
            case("client: positioning pages are the home page and llms.txt, both fetched",
                 [(x["kind"], x["state"]) for x in jd.get("positioning_pages", [])] == [("home", "FETCHED"), ("llms", "FETCHED")],
                 jd.get("positioning_pages"))
            case("client: every fetch is indexed in pages/index.tsv",
                 (b / "pages" / "index.tsv").is_file() and len((b / "pages" / "index.tsv").read_text().splitlines()) - 1 == len(jd.get("pages", [])))

            b = tmp / "nameless"
            p = run_child(["client", str(b), "--jd", base + "/jd-nameless.html"], b)
            jd = json.loads((b / "captures" / "jd.json").read_text()) if (b / "captures" / "jd.json").is_file() else {}
            case("client: a JD that names no company is a typed STOP no-company, exit 3",
                 p.returncode == 3 and jd.get("state") == "STOP" and jd.get("stop") == "no-company"
                 and "STOP no-company:" in p.stderr, (p.returncode, p.stderr[-400:], jd))

            b = tmp / "gone"
            p = run_child(["client", str(b), "--jd", base + "/jd-404.html"], b)
            jd = json.loads((b / "captures" / "jd.json").read_text()) if (b / "captures" / "jd.json").is_file() else {}
            case("client: a JD that 404s is a typed STOP jd-unreachable, exit 3",
                 p.returncode == 3 and jd.get("stop") == "jd-unreachable" and "404" in jd.get("reason", ""),
                 (p.returncode, jd))

            # A JS-shell ad whose text never rendered (a real Notion capture, before and after the
            # render): live with no Chrome, then as a saved capture, which is never rendered.
            b = tmp / "shell-live"
            p = run_child(["client", str(b), "--jd", base + "/jd-shell.html"], b)
            jd = json.loads((b / "captures" / "jd.json").read_text()) if (b / "captures" / "jd.json").is_file() else {}
            case("client: a JS-shell ad Chrome cannot render is a typed STOP jd-unreachable naming its prose, exit 3",
                 p.returncode == 3 and jd.get("stop") == "jd-unreachable" and jd.get("ad_prose") == 0
                 and "0 prose characters" in jd.get("reason", ""), (p.returncode, p.stderr[-400:], jd))
            stub = tmp / "chrome-stub"
            stub.write_text(f'#!/bin/sh\necho "$FETCH_CHROME_TIMEOUT" >> "{tmp}/chrome-waits"\nexit 1\n')
            stub.chmod(0o755)
            b = tmp / "shell-wait"
            run_child(["client", str(b), "--jd", base + "/jd-shell.html"], b, {"FETCH_CHROME": str(stub)})
            waits = (tmp / "chrome-waits").read_text().split() if (tmp / "chrome-waits").is_file() else []
            case(f"client: the job ad's render waits AD_CHROME_TIMEOUT ({AD_CHROME_TIMEOUT} s), not fetch.py's default",
                 waits == [str(AD_CHROME_TIMEOUT)], waits)
            mirror = tmp / "mirror"
            mirror_site(mirror)
            for name, want in (("shell", 3), ("rendered", 0)):
                b = tmp / ("notion-" + name)
                (mirror / "ws.notion.site").mkdir(parents=True, exist_ok=True)
                (mirror / "ws.notion.site" / "role").write_bytes((FIXTURES / f"notion-ad-{name}.html").read_bytes())
                p = run_child(["client", str(b), "--jd", "https://ws.notion.site/role"], b,
                              {"INTEL_PREFETCH_MIRROR": str(mirror)})
                jd = json.loads((b / "captures" / "jd.json").read_text()) if (b / "captures" / "jd.json").is_file() else {}
                case(f"client: the {name} Notion ad capture is exit {want}, ad prose {jd.get('ad_prose')}",
                     p.returncode == want and (jd.get("stop") == "jd-unreachable" if want else
                                               jd.get("state") == "OK" and jd.get("ad_prose", 0) >= AD_PROSE_MIN),
                     (p.returncode, p.stderr[-400:], {k: jd.get(k) for k in ("state", "stop", "reason", "ad_prose")}))

            b = tmp / "workable"
            p = run_child(["client", str(b), "--jd", "https://apply.workable.com/acme/j/ABC123/"], b,
                          {"INTEL_PREFETCH_MIRROR": str(mirror)})
            jd = json.loads((b / "captures" / "jd.json").read_text()) if (b / "captures" / "jd.json").is_file() else {}
            index = (b / "pages" / "index.tsv").read_text() if (b / "pages" / "index.tsv").is_file() else ""
            case("client: a Workable job reads its ad from api/v2 and its company from the account widget",
                 p.returncode == 0 and jd.get("board") == "workable"
                 and jd.get("ad_url") == "https://apply.workable.com/api/v2/accounts/acme/jobs/ABC123"
                 and jd.get("company") == {"name": "Acme Ledgers", "source": "board-account"}
                 and "https://apply.workable.com/api/v2/accounts/acme/jobs/ABC123\t" in index
                 and [x["kind"] for x in jd.get("positioning_pages", [])] == ["company"],
                 (p.returncode, p.stderr[-400:], jd))

            b = tmp / "notion"
            p = run_child(["client", str(b), "--jd", "https://acme.notion.site/founders-associate"], b,
                          {"INTEL_PREFETCH_MIRROR": str(mirror)})
            jd = json.loads((b / "captures" / "jd.json").read_text()) if (b / "captures" / "jd.json").is_file() else {}
            case("client: a Notion page's `acme on Notion` site name is the workspace acme, not the platform",
                 p.returncode == 0 and jd.get("company") == {"name": "acme", "source": "og:site_name"},
                 (p.returncode, p.stderr[-400:], jd.get("company")))

            b = tmp / "rivals"
            names = [{"slug": "rival", "name": "Rival", "domain": "rival.example", "page_id": "rival.example-0123abcd"},
                     {"slug": "other", "name": "Other", "domain": "other.example", "page_id": "www.other.example-89abcdef"}]
            (b / "pages").mkdir(parents=True)
            (b / "names.json").write_text(json.dumps(names))
            (b / "pages" / "index.tsv").write_text(
                "url\tfinal_url\tstatus\tfetched_at\tsha256\tbytes\tpath\n"
                "https://rival.example/about\tx\t200\tt\ts\t1\tpages/rival.example-0123abcd.html\n"
                "https://www.other.example/\tx\t200\tt\ts\t1\tpages/www.other.example-89abcdef.html\n")
            p = run_child(["rivals", str(b)], b, {"INTEL_PREFETCH_MIRROR": str(mirror)})
            rep = json.loads((b / "captures" / "rivals.json").read_text()) if (b / "captures" / "rivals.json").is_file() else {}
            got = {s: sorted(urllib.parse.urlparse(x["url"]).path for x in v["pages"] if x["state"] == "FETCHED")
                   for s, v in rep.items()}
            case("rivals: each rival's home, sitemap, pricing and case pages are fetched; careers is not",
                 p.returncode == 0 and got == {"rival": ["/", "/customers/bigco", "/plans", "/pricing", "/sitemap.xml"],
                                               "other": ["/", "/case-studies/one", "/plans", "/pricing", "/sitemap.xml"]},
                 (p.returncode, p.stderr[-400:], got))
            blocks = json.loads((b / "id-blocks.json").read_text()) if (b / "id-blocks.json").is_file() else {}
            case("rivals: id-blocks.json gives the reader, the client and each rival a block, in names.json order",
                 blocks == {"reader": ["C-001", "C-099"], "client": ["C-100", "C-199"],
                            "rival": ["C-200", "C-299"], "other": ["C-300", "C-399"]}, blocks)
            p = run_child(["rivals", str(tmp / "nowhere")], tmp)
            case("rivals: no names.json is exit 2", p.returncode == 2, p.returncode)
    finally:
        srv.shutdown()
    if FAILS:
        print(f"PREFETCH SELFTEST FAIL ({len(FAILS)}): " + "; ".join(FAILS))
        return 1
    print("PREFETCH SELFTEST OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
