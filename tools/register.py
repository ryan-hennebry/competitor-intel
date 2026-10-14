#!/usr/bin/env python3
"""Look up every pool candidate on the UK company register, in code (Globex design § 3 `register`
node, § 10 Q1).

WHY THIS EXISTS. One register agent used to check the pool by hand. The redesign first cut it to the
top 10, then found the cut unsafe: Creator.co, a pick, sat exactly 10th (b2 § 3), and the market
lane has no questions to rank on. So every candidate is looked up, two hops each (the search, then
the matched company's page), 16 at a time: about 64 x 2 hops in under a minute (b2 § 2).

WHAT ONE RUN DOES.
  1. Reads every `$BRIEF_ROOT/pool/*.tsv` but `registers.tsv`: a `name` and `url` per row, one
     candidate per name, and the client from `reader.json` when present. Each gets an evidence
     score from its `axis_*` cells: 2 for one opening "yes", 1 for "partial" or "both", else 0.
  2. Fetches the register's search page for the name, then the page of the result whose name,
     legal suffixes aside, equals the candidate's, both through `tools/fetch.py --json`, so every
     page read is saved and indexed in `pages/` like any other the run reads.
  3. Writes `pool/registers.tsv`, one row per candidate, `state` typed: `matched` (the identifier,
     title, status, incorporation date and address from the company page), `no-match` (the search
     answered; the note lists its first titles), or `blocked` (the register did not answer: a
     BLOCKED or NOT_REACHED fetch, a failed company page, or the cap).
THE CAP. Lookups run highest score first. The top PRIORITY candidates, plus every one tied with the
last of them, are always looked up; any other lookup not finished CAP_S seconds after the start is
`blocked` with the note "over the cap" (§ 10 Q1's fallback: top 12 plus ties). "Not on the
register" is never written for a lookup that did not happen (`references/provenance.md`).

  python3 tools/register.py BRIEF_ROOT [--base URL] [--cap SECONDS] [--jobs N]
  python3 tools/register.py --selftest      offline: a local stub register, fetch.py over loopback

`--base` is the register's origin (the selftest's seam); `--cap` and `--jobs` default to CAP_S and
JOBS.

EXIT CODES. 0 every candidate has a row (blocked rows included: a blocked register is a state, not
a failure of this tool). 2 bad usage, no pool, or no candidate.
"""

import concurrent.futures
import csv
import html
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
FETCH = ROOT / "tools/fetch.py"
BASE = "https://find-and-update.company-information.service.gov.uk"
REGISTER = "UK Companies House"
CAP_S = 60  # design § 10 Q1: every candidate in at most 60 s at 16 concurrent
JOBS = 16
PRIORITY = 12  # the fallback's top 12, plus ties
BACKOFF_CAP = "5"  # fetch.py's per-wait cap here, so one 429 cannot eat the minute
COLUMNS = ("name", "url", "score", "register", "query", "state", "identifier", "title", "company_status",
           "incorporated", "address", "http_code", "page", "note")
SUFFIXES = re.compile(r"\b(limited|ltd|plc|llp|inc|incorporated|llc|uk|gmbh|co)\b\.?", re.I)


def key(name):
    return re.sub(r"[^a-z0-9]", "", SUFFIXES.sub(" ", html.unescape(name or "").lower()))


def score(row):
    total = 0
    for col, cell in row.items():
        if not (col or "").lower().startswith("axis"):
            continue
        cell = (cell or "").strip().lower()
        total += 2 if cell.startswith("yes") else 1 if cell.startswith(("partial", "both")) else 0
    return total


def candidates(root):
    """[(name, url, score)], one per name key, highest score first; the client first of all."""
    seen, out = set(), []
    reader = root / "reader.json"
    if reader.is_file():
        comp = json.loads(reader.read_text(encoding="utf-8")).get("company", {})
        if comp.get("name"):
            seen.add(key(comp["name"]))
            out.append((comp["name"], "https://%s/" % comp.get("domain", ""), 99))
    for tsv in sorted((root / "pool").glob("*.tsv")):
        if tsv.name == "registers.tsv":
            continue
        lines = [ln for ln in tsv.read_text(encoding="utf-8").splitlines() if not ln.startswith("#")]
        for row in csv.DictReader(lines, delimiter="\t"):
            name = (row.get("name") or "").strip()
            if name and key(name) and key(name) not in seen:
                seen.add(key(name))
                out.append((name, (row.get("url") or "").strip(), score(row)))
    return sorted(out, key=lambda c: -c[2])


def strip_scripts(text):
    return re.sub(r"<script\b.*?</script\s*>", "", text, flags=re.S | re.I)


def results(page):
    """[(title, href, crumb, address)] of a search page's company results."""
    out = []
    for li in re.findall(r'<li class="type-company">(.*?)</li>', strip_scripts(page), re.S):
        a = re.search(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', li, re.S)
        crumb = re.search(r'<p class="meta crumbtrail">(.*?)</p>', li, re.S)
        addr = re.findall(r"<p>(.*?)</p>", li, re.S)
        if a:
            clean = lambda s: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s))).strip()
            out.append((clean(a.group(2)), a.group(1), clean(crumb.group(1)) if crumb else "",
                        clean(addr[-1]) if addr else ""))
    return out


def company(page):
    """(status, incorporated, address) from a company page."""
    def field(pattern):
        m = re.search(pattern, page, re.S)
        return re.sub(r"\s+", " ", html.unescape(m.group(1))).strip() if m else ""
    return (field(r'id="company-status">(.*?)</dd>'), field(r'id="company-creation-date">(.*?)</dd>'),
            field(r'id="roa-address">(.*?)</span>'))


def fetch(root, url, deadline):
    """fetch.py --json on one URL: (said dict, page text or None). A timeout is a FAILED state."""
    left = None if deadline is None else deadline - time.monotonic()
    if left is not None and left <= 0:
        return {"state": "CAP", "status": None}, None
    env = dict(os.environ, BRIEF_ROOT=str(root), FETCH_BACKOFF_CAP=BACKOFF_CAP, PYTHONDONTWRITEBYTECODE="1")
    try:
        proc = subprocess.run([sys.executable, str(FETCH), url, "--json"], env=env, capture_output=True,
                              text=True, timeout=left)
    except subprocess.TimeoutExpired:
        return {"state": "CAP", "status": None}, None
    try:
        said = json.loads(proc.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"state": "FAILED", "status": None, "note": proc.stderr.strip()[-200:]}, None
    text = None
    if said.get("state") == "FETCHED" and said.get("path"):
        text = (root / said["path"]).read_text(encoding="utf-8", errors="replace")
    return said, text


def lookup(root, base, name, url, sc, deadline):
    query = "%s/search/companies?q=%s" % (base, urllib.parse.quote_plus(name))
    row = dict.fromkeys(COLUMNS, "")
    row.update(name=name, url=url, score=str(sc), register=REGISTER, query=query)

    def blocked(said, why):
        row.update(state="blocked", http_code=str(said.get("status") or ""), page=said.get("path") or "",
                   note="over the cap: not looked up" if said.get("state") == "CAP" else why)
        return row
    said, page = fetch(root, query, deadline)
    if page is None:
        return blocked(said, "search %s %s" % (said.get("state"), said.get("status") or ""))
    found = results(page)
    hit = next((r for r in found if key(r[0]) == key(name)), None)
    if hit is None:
        row.update(state="no-match", http_code=str(said.get("status")), page=said["path"],
                   note=("%d results; first: %s" % (len(found), "; ".join(r[0] for r in found[:3])))
                   if found else "no results")
        return row
    said2, page2 = fetch(root, urllib.parse.urljoin(base + "/", hit[1]), deadline)
    if page2 is None:
        return blocked(said2, "company page %s %s" % (said2.get("state"), said2.get("status") or ""))
    status, born, addr = company(page2)
    row.update(state="matched", identifier=hit[1].rstrip("/").split("/")[-1], title=hit[0],
               company_status=status, incorporated=born, address=addr or hit[3],
               http_code=str(said2.get("status")), page=said2["path"], note=hit[2])
    return row


def run(root, base=BASE, cap=CAP_S, jobs=JOBS, out=sys.stdout):
    root = pathlib.Path(root)
    if not (root / "pool").is_dir():
        sys.stderr.write("register: %s has no pool/\n" % root)
        return 2
    cands = candidates(root)
    if not cands:
        sys.stderr.write("register: no candidate in %s/pool/*.tsv\n" % root)
        return 2
    cut = cands[min(PRIORITY, len(cands)) - 1][2]
    first = [c for c in cands if c[2] >= cut]
    rest = [c for c in cands if c[2] < cut]
    start = time.monotonic()
    deadline = start + cap
    rows = {}
    lock = threading.Lock()

    def one(c, dl):
        r = lookup(root, base, *c, dl)
        with lock:
            rows[c[0]] = r
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        futs = [pool.submit(one, c, None) for c in first] + [pool.submit(one, c, deadline) for c in rest]
        concurrent.futures.wait(futs)
        for f in futs:
            f.result()
    lines = ["\t".join(COLUMNS)] + ["\t".join(rows[c[0]][k].replace("\t", " ").replace("\n", " ")
                                              for k in COLUMNS) for c in cands]
    (root / "pool/registers.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    states = [rows[c[0]]["state"] for c in cands]
    out.write("REGISTER OK (%d candidates in %.1f s: %d matched, %d no-match, %d blocked; %d always looked "
              "up, score %d and up) -> %s\n" % (len(cands), time.monotonic() - start, states.count("matched"),
                                                states.count("no-match"), states.count("blocked"), len(first),
                                                cut, root / "pool/registers.tsv"))
    return 0


# --- selftest -------------------------------------------------------------------------------------
STUB_COMPANIES = {  # number -> (title, status)
    "00000001": ("ALPHA GRID LIMITED", "Active"),
    "00000002": ("BETA FLEX LTD", "Dissolved"),
}
SEARCH_ITEM = ('<li class="type-company"><h3><a class="govuk-link" href="/company/%s" title="View company">'
               '%s</a></h3><p class="meta crumbtrail"> %s - Incorporated on 1 May 2020 </p>'
               '<p>1 Test Street, London, E1 1AA</p></li>')
TEMPLATE = '<script id="t" type="text/html"><li class="type-company"><h3><a href="{{url}}">{{{title}}}</a></h3></li></script>'


class StubRegister:
    """Loopback stand-in for the register: search and company pages in its markup. `Alpha Grid`
    matches; `Gamma` has results that are other companies; `Zeta` has none; `Busy` is always 429;
    `Slow` answers after `slow` seconds; every other name has no results."""

    def __init__(self, slow=0.0):
        import http.server
        self.hits = []
        hits, companies = self.hits, STUB_COMPANIES

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                hits.append(self.path)
                u = urllib.parse.urlparse(self.path)
                q = urllib.parse.parse_qs(u.query).get("q", [""])[0]
                code, extra = 200, {}
                if u.path == "/search/companies":
                    if q == "Busy":
                        code, extra, body = 429, {"Retry-After": "0"}, "<p>Too many requests</p>"
                    else:
                        if q == "Slow":
                            time.sleep(slow)
                        items = {"Alpha Grid": [SEARCH_ITEM % ("00000001", "ALPHA GRID LIMITED", "00000001")],
                                 "Gamma": [SEARCH_ITEM % ("00000002", "BETA FLEX LTD", "00000002")]}.get(q, [])
                        body = TEMPLATE + ("<ul id='results'>%s</ul>" % "".join(items) if items else
                                           '<article id="no-results"><h2>No results found</h2></article>')
                elif u.path.startswith("/company/") and u.path.split("/")[2] in companies:
                    title, status = companies[u.path.split("/")[2]]
                    body = ('<h1>%s</h1><span class="text data" id="roa-address"> 1 Test Street, London </span>'
                            '<dd class="text data" id="company-status"> %s </dd>'
                            '<dd class="data" id="company-creation-date">1 May 2020</dd>' % (title, status))
                else:
                    code, body = 404, "<p>Not found</p>"
                page = ("<html><body><main>%s<p>%s</p></main></body></html>"
                        % (body, "Register text for the page layer. " * 12)).encode()
                self.send_response(code)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                for k, v in extra.items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(page)))
                self.end_headers()
                self.wfile.write(page)

            def log_message(self, *args):
                pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


POOL = ("name\turl\taxis_1\taxis_2\n"
        "Alpha Grid\thttps://alpha.example/\tyes: a\tyes: b\n"
        "Gamma\thttps://gamma.example/\tyes: a\tpartial\n"
        "Zeta\thttps://zeta.example/\tno\tyes\n"
        "Busy\thttps://busy.example/\tyes\tno\n")


def selftest():
    fails, n = [], 0

    def verdict(label, ok, got=""):
        nonlocal n
        n += 1
        print("SELFTEST %s %s" % ("OK  " if ok else "FAIL", label))
        if not ok:
            fails.append("%s: got %s" % (label, got))

    def table(root):
        lines = (root / "pool/registers.tsv").read_text(encoding="utf-8").splitlines()
        return lines[0].split("\t"), [dict(zip(COLUMNS, ln.split("\t"))) for ln in lines[1:]]

    srv = StubRegister(slow=6.0)
    try:
        with tempfile.TemporaryDirectory(prefix="register-selftest-") as tmp:
            root = pathlib.Path(tmp) / "run"
            (root / "pool").mkdir(parents=True)
            (root / "pool/a.tsv").write_text(POOL, encoding="utf-8")
            (root / "pool/b.tsv").write_text("name\turl\taxis_1\nalpha grid\thttps://dup.example/\tyes\n",
                                             encoding="utf-8")
            (root / "pool/registers.tsv").write_text("name\nStale\n", encoding="utf-8")
            code = run(root, base=srv.base, out=open(os.devnull, "w"))
            head, rows = table(root)
            by = {r["name"]: r for r in rows}
            verdict("one row per pool candidate, deduplicated by name, registers.tsv itself skipped",
                    code == 0 and tuple(head) == COLUMNS and sorted(by) == ["Alpha Grid", "Busy", "Gamma", "Zeta"],
                    (code, sorted(by)))
            a = by.get("Alpha Grid", {})
            verdict("a name whose result matches is `matched`, two hops, the company page read",
                    a.get("state") == "matched" and a.get("identifier") == "00000001"
                    and a.get("company_status") == "Active" and a.get("incorporated") == "1 May 2020"
                    and (root / a.get("page", "-")).is_file(), a)
            g = by.get("Gamma", {})
            verdict("results naming other companies are `no-match`, listing them",
                    g.get("state") == "no-match" and "BETA FLEX LTD" in g.get("note", ""), g)
            z = by.get("Zeta", {})
            verdict("no results is `no-match`, the search page saved",
                    z.get("state") == "no-match" and z.get("note") == "no results" and (root / z["page"]).is_file(), z)
            b = by.get("Busy", {})
            verdict("a register that keeps answering 429 is `blocked`, never `no-match`",
                    b.get("state") == "blocked" and b.get("http_code") == "429"
                    and srv.hits.count("/search/companies?q=Busy") == 3, (b, srv.hits.count("/search/companies?q=Busy")))
            verdict("every row is looked up or typed blocked",
                    all(r["state"] in ("matched", "no-match", "blocked") for r in rows), rows)
            verdict("scores rank the table: 2 a yes, 1 a partial",
                    [r["score"] for r in rows] == ["4", "3", "2", "2"], [r["score"] for r in rows])
            # The cap: 13 high scorers (12 plus a tie) are always looked up; a slow low scorer is not.
            cap = pathlib.Path(tmp) / "cap"
            (cap / "pool").mkdir(parents=True)
            many = "".join("Name %02d\thttps://n%02d.example/\tyes\n" % (i, i) for i in range(13))
            (cap / "pool/a.tsv").write_text("name\turl\taxis_1\n" + many + "Slow\thttps://slow.example/\tno\n",
                                            encoding="utf-8")
            start = time.monotonic()
            code = run(cap, base=srv.base, cap=2, out=open(os.devnull, "w"))
            took = time.monotonic() - start
            _, rows = table(cap)
            by = {r["name"]: r for r in rows}
            verdict("over the cap: the top 12 plus ties are looked up, the rest typed blocked",
                    code == 0 and len(rows) == 14 and all(by["Name %02d" % i]["state"] == "no-match" for i in range(13))
                    and by["Slow"]["state"] == "blocked" and by["Slow"]["note"] == "over the cap: not looked up"
                    and took < 5.5, (code, took, by.get("Slow")))
            empty = pathlib.Path(tmp) / "empty"
            empty.mkdir()
            with open(os.devnull, "w") as null:
                old, sys.stderr = sys.stderr, null
                try:
                    codes = (run(empty, base=srv.base), main(["register.py"]))
                finally:
                    sys.stderr = old
            verdict("no pool, or no BRIEF_ROOT, is exit 2", codes == (2, 2), codes)
    finally:
        srv.close()
    if fails:
        print("SELFTEST RED (%d of %d)" % (len(fails), n))
        for f in fails:
            print("  %s" % f)
        return 1
    print("SELFTEST OK (%d cases)" % n)
    return 0


def main(argv):
    args = argv[1:]
    if args == ["--selftest"]:
        return selftest()
    opts = {"--base": BASE, "--cap": str(CAP_S), "--jobs": str(JOBS)}
    pos = []
    i = 0
    while i < len(args):
        if args[i] in opts and i + 1 < len(args):
            opts[args[i]] = args[i + 1]
            i += 2
            continue
        pos.append(args[i])
        i += 1
    if len(pos) != 1 or pos[0].startswith("-"):
        sys.stderr.write("usage: register.py BRIEF_ROOT [--base URL] [--cap SECONDS] [--jobs N] | --selftest\n")
        return 2
    try:
        return run(pos[0], base=opts["--base"].rstrip("/"), cap=float(opts["--cap"]), jobs=int(opts["--jobs"]))
    except ValueError as exc:
        sys.stderr.write("register: %s\n" % exc)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
