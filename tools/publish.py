#!/usr/bin/env python3
"""Publish: the one route from a PASS verdict to a probed live link (design.md § 3 Publish,
research e-publish § Q5, rulings D4, D7, D10, D15). It replaces tools/deliver.sh once the runner
calls it. Stdlib only.

Usage:
  python3 tools/publish.py BRIEF_ROOT [--push]
  python3 tools/publish.py --unpublish SLUG [--push]     a *-replay slug only (D15)
  python3 tools/publish.py --selftest                    temp bare remote, stub deploy, no network

The slug is brief.json's company.slug, which the verdict already binds; there is no --slug. The site
push is off unless --push is given: the runner passes it per rulings.md D7.

Environment (each has a default; the overrides exist so --selftest never touches the real site):
  SITE_REPO            the site checkout, default ~/site
  PUBLISH_STATE        the lock and the last-deployed marker, default ~/.cache/competitor-intel
  PUBLISH_DEPLOY       the deploy command, default SITE_REPO/deploy.sh (it runs verify.sh, then wrangler)
  PUBLISH_PROBE_BASE   where probes are sent, default https://ryanhennebry.xyz
  PUBLISH_PROBE_TRIES  probe attempts, default 6;  PUBLISH_PROBE_WAIT  seconds between them, default 5

Steps, each refusal one stderr line `PUBLISH REFUSED <code> <reason>`:
  P0  args        BRIEF_ROOT has brief.json, web/index.html, web/og.png                        else 2
  P1  verdict     correctness-<sha256(brief.json)>.md says "Verdict: PASS" and its PAGE: line is
                  sha256(web/index.html)                                                       else 10
  P2  page gates  slug legal and not a top-level name of the site (verify.sh's listing)       else 13
                  canonical == og:url == https://ryanhennebry.xyz/<slug>/ (D10); og:title,
                  og:description, og:image:alt present; og:image is this page's og.png;
                  robots noindex                                                               else 12
                  og:image's ?v= == sha256(web/og.png)[:12]                                    else 11
                  dates.page is today in Europe/London (D4)                                    else 14
  P3  preflight   lock; site on main, clean; fetch; ff-only to origin/main                     else 20
                  foreign-change guard: commits since the last deploy (or origin/main, logged
                  as unanchored) touch only briefs/                                            else 21
                  briefs/<slug>/ absent, or its og:title names this company                    else 13
  P4  pre-probe   live page, card and site tree already equal this brief: ALREADY LIVE, exit 0
  P5  place       web/ minus shots/ to briefs/<slug>/, then the site's verify.sh               else 22
  P6  record      commit briefs/<slug> "brief(<slug>): CONTENT VERIFIED <sha12>" if it changed else 23
  P7  deploy      PUBLISH_DEPLOY --message "publish <slug> site@<sha12>"                       else 30
  P8  push        with --push only: git push origin main                                       else 31, then P9
  P9  probe       with the probe UA, up to PUBLISH_PROBE_TRIES times:
                  GET /<slug>/ is 200                                                          else 40
                  its bytes are web/index.html's (names the og fields that differ)            else 41
                  the exact og:image URL is 200 with web/og.png's bytes                       else 42
                  GET /<slug> is 307 to /<slug>/, or 200                                       else 43
  P11 report      stdout: SHARE <url> / CONTENT VERIFIED <sha12>  site <commit12>  worker <id>
                  and a NOTE when P4 saw an earlier preview of the URL.
SHARE prints only on exit 0 or 31. Exit 2 is usage. The run-store copy (deliver's) is gone:
BRIEF_ROOT already sits in the durable run root, so exit 50 is retired.
"""
import argparse, fcntl, hashlib, html, json, os, re, shutil, subprocess, sys, tempfile, threading, time
import urllib.error, urllib.request
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

SITE = "https://ryanhennebry.xyz"
UA = "ITLPublishProbe/1 (bot; competitor-intel publish)"  # contains "bot": the Worker never alerts on it
TZ = "Europe/London"
SLUG_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
OG_FIELDS = ("og:title", "og:description", "og:image")
REPLAY = "-replay"


class Refused(Exception):
    def __init__(self, code, reason):
        super().__init__(reason)
        self.code, self.reason = code, reason


def refuse(code, reason):
    raise Refused(code, reason)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def today():
    return datetime.now(ZoneInfo(TZ)).date().isoformat()


def note(msg):
    sys.stderr.write(f"NOTE {msg}\n")


class Head(HTMLParser):
    """The share metadata of a page: canonical hrefs, og:* contents and robots values, as lists."""

    def __init__(self, src):
        super().__init__()
        self.tags = {}
        self.feed(src)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "link" and a.get("rel") == "canonical":
            self.tags.setdefault("canonical", []).append(a.get("href") or "")
        elif tag == "meta" and (a.get("property") or a.get("name")):
            self.tags.setdefault(a.get("property") or a.get("name"), []).append(a.get("content") or "")

    def one(self, key):
        v = self.tags.get(key, [])
        return v[0] if len(v) == 1 else None


def git(repo, *args, check=True, env=None):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                       env={**os.environ, **(env or {})})
    if check and r.returncode:
        raise subprocess.CalledProcessError(r.returncode, ["git", *args], r.stdout, r.stderr)
    return r


def last_line(text):
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    fails = [ln for ln in lines if "FAIL" in ln]
    return (fails or lines or ["no output"])[-1].strip()[:200]


def reserved(site):
    """The site's verify.sh rule (company-briefs block): briefs, cdn-cgi, and every root entry with
    and without its extension, read live from the site's listing rather than cached here."""
    out = {"briefs", "cdn-cgi"}
    for e in os.listdir(site):
        if e == "briefs":
            continue
        out |= {e, e[:e.rfind(".")] if "." in e else e}
    return out


# ---- the probe ----

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def fetch(url, follow=True):
    """(status, headers, body) for a GET with the probe UA; status None on a network error. The URL is
    the public one; PUBLISH_PROBE_BASE swaps its origin, so the selftest probes a local server."""
    base = os.environ.get("PUBLISH_PROBE_BASE", SITE).rstrip("/")
    if url.startswith(SITE):
        url = base + url[len(SITE):]
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    opener = urllib.request.build_opener(*([] if follow else [_NoRedirect()]))
    try:
        with opener.open(req, timeout=20) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), e.read() or b""
    except (urllib.error.URLError, OSError):
        return None, {}, b""


def triple(src):
    h = Head(src.decode("utf-8", "replace") if isinstance(src, bytes) else src)
    return tuple(h.one(k) for k in OG_FIELDS)


def probe_once(url, slug, page, card, og_image):
    st, _, body = fetch(url)
    if st != 200:
        return 40, f"{url} answered {st}, want 200"
    if sha(body) != sha(page):
        diff = [k for k, a, b in zip(OG_FIELDS, triple(body), triple(page)) if a != b]
        return 41, f"{url} serves other bytes than web/index.html; og fields differing: {diff or 'none'}"
    st, _, img = fetch(og_image)
    if st != 200 or sha(img) != sha(card):
        return 42, f"{og_image} answered {st}" + (", not web/og.png's bytes" if st == 200 else "")
    st, hdrs, _ = fetch(f"{SITE}/{slug}", follow=False)
    loc = {k.lower(): v for k, v in hdrs.items()}.get("location", "")
    if not (st == 200 or (st == 307 and loc.endswith(f"/{slug}/"))):
        return 43, f"{SITE}/{slug} answered {st} {loc!r}, want 307 to /{slug}/ or 200"
    return 0, ""


def probe(check):
    tries = int(os.environ.get("PUBLISH_PROBE_TRIES", "6"))
    wait = float(os.environ.get("PUBLISH_PROBE_WAIT", "5"))
    code, why = 40, "no probe ran"
    for i in range(max(tries, 1)):
        code, why = check()
        if code == 0:
            return
        if i + 1 < tries:
            time.sleep(wait)  # edge propagation
    refuse(code, why)


# ---- the site ----

def site_paths():
    site = Path(os.environ.get("SITE_REPO", str(Path.home() / "Projects/in-the-loop/ryanhennebry.xyz")))
    state = Path(os.environ.get("PUBLISH_STATE", str(Path.home() / ".cache/competitor-intel")))
    return site, state


_LOCK = None


def preflight(site, state):
    """P3's first half: the lock, a clean main fast-forwarded to origin, and the foreign-change guard."""
    global _LOCK
    state.mkdir(parents=True, exist_ok=True)
    _LOCK = open(state / "publish.lock", "w")
    try:
        fcntl.flock(_LOCK, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        refuse(20, f"another publish holds {state / 'publish.lock'}")
    if git(site, "symbolic-ref", "--short", "HEAD", check=False).stdout.strip() != "main":
        refuse(20, f"{site} is not on main")
    dirty = git(site, "status", "--porcelain").stdout.strip()
    if dirty:  # untracked files included, so deploy.sh's untracked-file refusal cannot fire later
        refuse(20, f"{site} is not clean: {dirty.splitlines()[0]}")
    if git(site, "fetch", "-q", "origin", check=False).returncode:
        refuse(20, "git fetch origin failed")
    if git(site, "merge", "-q", "--ff-only", "origin/main", check=False).returncode:
        refuse(20, "main does not fast-forward to origin/main")
    # deploy.sh ships the whole repo, so nothing but briefs/ may have changed since the last deploy.
    marker = state / "site-deployed"
    anchor = marker.read_text(encoding="utf-8").strip() if marker.is_file() else ""
    if not anchor:
        anchor = "origin/main"
        note("foreign-change guard unanchored: no deploy recorded yet, so origin/main stands in")
    if git(site, "cat-file", "-e", f"{anchor}^{{commit}}", check=False).returncode:
        refuse(21, f"the last deployed commit {anchor} is not in {site}")
    changed = git(site, "diff", "--name-only", f"{anchor}..HEAD").stdout.split()
    foreign = [f for f in changed if not f.startswith("briefs/")]
    if foreign:
        refuse(21, f"undeployed site changes outside briefs/ would ship: {', '.join(foreign[:5])}")
    return marker


def restore(site, rel):
    """Put briefs/<slug> back as HEAD has it: tracked files restored, new ones removed."""
    git(site, "reset", "-q", "HEAD", "--", rel, check=False)
    if git(site, "ls-files", "--", rel).stdout.strip():
        git(site, "checkout", "-q", "HEAD", "--", rel, check=False)
    git(site, "clean", "-fdq", "--", rel, check=False)


def commit(site, rel, msg):
    """P6: commit rel if it changed. Returns True when a commit was made; refuses 23 on failure."""
    if not git(site, "status", "--porcelain", "--", rel).stdout.strip():
        return False
    env = {"ITL_PUBLISH": "1"}
    c = None
    if (site / rel).exists():  # an unpublish's git rm has staged its removal already
        c = git(site, "add", "-A", "--", rel, check=False, env=env)
    if not (c and c.returncode):
        c = git(site, "commit", "-q", "-m", msg, check=False, env=env)
    if c.returncode:
        restore(site, rel)
        refuse(23, f"git commit failed: {last_line(c.stderr + c.stdout)}")
    return True


def deploy(site, marker, slug):
    head = git(site, "rev-parse", "HEAD").stdout.strip()
    cmd = os.environ.get("PUBLISH_DEPLOY") or str(site / "deploy.sh")
    r = subprocess.run([cmd, "--message", f"publish {slug} site@{head[:12]}"], cwd=site, capture_output=True, text=True)
    if r.returncode:
        refuse(30, f"deploy failed (exit {r.returncode}): {last_line(r.stdout + r.stderr)}; "
                   "the commit stands, so a re-run is safe")
    marker.write_text(head + "\n", encoding="utf-8")
    m = re.search(r"Current Version ID:\s*(\S+)", r.stdout + r.stderr)
    return head, m.group(1) if m else "-"


def push(site, wanted):
    """P8. Returns True when the push failed (exit 31 later, after the probe)."""
    if not wanted:
        note("site not pushed: --push is off (rulings.md D7 decides; the runner passes it)")
        return False
    r = git(site, "push", "-q", "origin", "main", check=False)
    if r.returncode:
        sys.stderr.write(f"PUSH FAILED {last_line(r.stderr)}\n")
    return bool(r.returncode)


def tree_matches(web, dest):
    want = {p.relative_to(web): p.read_bytes() for p in web.rglob("*")
            if p.is_file() and p.relative_to(web).parts[0] != "shots"}
    got = ({p.relative_to(dest): p.read_bytes() for p in dest.rglob("*") if p.is_file() and p.name != ".DS_Store"}
           if dest.is_dir() else {})
    return want == got


# ---- the two commands ----

def publish(root, want_push):
    # P0
    root = Path(root)
    for f in ("brief.json", "web/index.html", "web/og.png"):
        if not (root / f).is_file():
            refuse(2, f"no {f} in {root}")
    raw = (root / "brief.json").read_bytes()
    try:
        brief = json.loads(raw)
    except ValueError as exc:
        refuse(2, f"brief.json is not JSON: {exc}")
    page, card = (root / "web/index.html").read_bytes(), (root / "web/og.png").read_bytes()
    bsha = sha(raw)
    # P1
    verdict = root / f"correctness-{bsha}.md"
    if not verdict.is_file():
        others = sorted(p.name for p in root.glob("correctness-*.md"))
        refuse(10, f"no verdict for brief.json's sha {bsha}" + (f"; only {others[0]}, for older bytes" if others else ""))
    lines = verdict.read_text(encoding="utf-8").splitlines()
    if "Verdict: PASS" not in lines:
        refuse(10, f"{verdict.name} does not say Verdict: PASS")
    if f"PAGE: {sha(page)}" not in lines:
        refuse(10, f"{verdict.name}'s PAGE line does not name web/index.html's sha {sha(page)}")
    # P2
    site, state = site_paths()
    if not site.is_dir():
        refuse(20, f"no site repo at {site}")
    slug = (brief.get("company") or {}).get("slug")
    if not isinstance(slug, str) or not SLUG_RE.fullmatch(slug):
        refuse(13, f"slug {slug!r} is not lowercase letters and digits joined by single hyphens")
    if slug in reserved(site):
        refuse(13, f"slug {slug!r} is a top-level name of the site")
    url = f"{SITE}/{slug}/"
    h = Head(page.decode("utf-8", "replace"))
    for key in ("canonical", "og:url"):
        if h.tags.get(key) != [url]:
            refuse(12, f"{key} is {h.tags.get(key)}, want exactly [{url!r}] (D10)")
    for key in ("og:title", "og:description", "og:image:alt"):
        if not (h.one(key) or "").strip():
            refuse(12, f"{key} is missing or empty")
    og_image = h.one("og:image") or ""
    if not og_image.startswith(url + "og.png?v="):
        refuse(12, f"og:image {og_image!r} is not this page's og.png at {url}")
    if "noindex" not in h.tags.get("robots", []):
        refuse(12, 'no <meta name="robots" content="noindex">')
    v = og_image.split("?v=", 1)[1]
    if v != sha(card)[:12]:
        refuse(11, f"og:image ?v={v} is not web/og.png's sha256[:12] {sha(card)[:12]}: the card changed after the build")
    stamp = (brief.get("dates") or {}).get("page")
    if stamp != today():
        refuse(14, f"dates.page is {stamp!r}, not today in {TZ} ({today()}): re-stamp and rebuild")
    # P3
    marker = preflight(site, state)
    rel = f"briefs/{slug}"
    dest = site / rel
    if dest.exists():
        old = dest / "index.html"
        title = html.unescape(Head(old.read_text(encoding="utf-8", errors="replace")).one("og:title") or "") if old.is_file() else ""
        name = brief["company"].get("name", "")
        if not name or not any(n in title for n in {name, name.replace("'", "’")}):
            refuse(13, f"{rel} holds another page (og:title {title!r}), not {name!r}'s")
    # P4
    local = triple(page)
    st, _, live = fetch(url)
    earlier = st == 200 and triple(live) != local
    if st == 200 and sha(live) == sha(page) and tree_matches(root / "web", dest):
        st_img, _, img = fetch(og_image)
        if st_img == 200 and sha(img) == sha(card):
            failed = push(site, want_push and git(site, "rev-list", "--count", "origin/main..HEAD").stdout.strip() != "0")
            head = git(site, "rev-parse", "HEAD").stdout.strip()
            report(url, bsha, head, "-", site, slug, False)
            print("ALREADY LIVE")
            return 31 if failed else 0
    # P5
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(root / "web", dest, ignore=lambda d, names: ["shots"] if Path(d) == root / "web" else [])
    r = subprocess.run([str(site / "verify.sh")], cwd=site, capture_output=True, text=True)
    if r.returncode:
        restore(site, rel)
        refuse(22, f"the site's verify.sh failed on the placed brief: {last_line(r.stdout + r.stderr)}")
    # P6, P7, P8
    commit(site, rel, f"brief({slug}): CONTENT VERIFIED {bsha[:12]}")
    head, worker = deploy(site, marker, slug)
    failed = push(site, want_push)
    # P9
    probe(lambda: probe_once(url, slug, page, card, og_image))
    # P11
    report(url, bsha, head, worker, site, slug, earlier)
    return 31 if failed else 0


def report(url, bsha, head, worker, site, slug, earlier):
    print(f"SHARE {url}")
    print(f"CONTENT VERIFIED {bsha[:12]}  site {head[:12]}  worker {worker}")
    if earlier:
        n = sum(s.startswith(f"brief({slug}):") for s in git(site, "log", "--format=%s").stdout.splitlines())
        print(f"NOTE an earlier preview of this URL may be cached; share {url}?r={n}")


def unpublish(slug, want_push):
    """D15: delete a scratch replay's live page, through the same lock, guard, commit and deploy."""
    if not SLUG_RE.fullmatch(slug or "") or not slug.endswith(REPLAY):
        refuse(13, f"--unpublish takes a *{REPLAY} slug only (D15); {slug!r} is not one")
    site, state = site_paths()
    if not site.is_dir():
        refuse(20, f"no site repo at {site}")
    marker = preflight(site, state)
    rel = f"briefs/{slug}"
    if not git(site, "ls-files", "--", rel).stdout.strip():
        refuse(13, f"{rel} is not on the site; nothing to unpublish")
    git(site, "rm", "-rq", "--", rel)
    commit(site, rel, f"brief({slug}): UNPUBLISHED")
    head, worker = deploy(site, marker, slug)
    failed = push(site, want_push)
    url = f"{SITE}/{slug}/"
    probe(lambda: (0, "") if fetch(url)[0] not in (200, None) else (40, f"{url} still answers 200 or nothing"))
    print(f"UNPUBLISHED {url}  site {head[:12]}  worker {worker}")
    return 31 if failed else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Publish a verified brief to its live URL, then probe it.")
    ap.add_argument("root", nargs="?", help="BRIEF_ROOT")
    ap.add_argument("--push", action="store_true", help="push the site repo after the deploy (D7)")
    ap.add_argument("--unpublish", metavar="SLUG", help="remove a *-replay page (D15)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if bool(a.root) == bool(a.unpublish):
        sys.stderr.write("PUBLISH REFUSED 2 usage: publish.py BRIEF_ROOT [--push] | --unpublish SLUG [--push] | --selftest\n")
        return 2
    try:
        return unpublish(a.unpublish, a.push) if a.unpublish else publish(a.root, a.push)
    except Refused as r:
        sys.stderr.write(f"PUBLISH REFUSED {r.code} {r.reason}\n")
        return r.code


# ---- --selftest: a temp bare remote, a temp site clone, a stub deploy and a local server ----

STUB_VERIFY = """#!/bin/sh
# The selftest's stand-in for the site's verify.sh: its company-briefs block, slash form (D10).
fail=0
for dir in briefs/*/; do
  [ -d "$dir" ] || continue
  slug=$(basename "$dir")
  if grep -Fq "$slug" sitemap.xml; then echo "FAIL briefs/$slug appears in sitemap.xml."; fail=1; fi
  grep -Fq "<link rel=\\"canonical\\" href=\\"https://ryanhennebry.xyz/$slug/\\">" "$dir/index.html" \\
    || { echo "FAIL $dir canonical"; fail=1; }
done
exit $fail
"""

# The stub deploy ships the tracked briefs to the live directory the server reads, as deploy.sh's
# manifest does, and logs its argv. Files in CTL break it the way an edge or wrangler can.
STUB_DEPLOY = """#!{py}
import os, shutil, subprocess, sys
from pathlib import Path
tmp = Path({tmp!r}); live, ctl = tmp / "live", tmp / "ctl"
with open(tmp / "deploy.log", "a") as f:
    f.write(" ".join(sys.argv[1:]) + "\\n")
if (ctl / "deploy-fail").exists():
    print("X [ERROR] Authentication error"); sys.exit(1)
shutil.rmtree(live, ignore_errors=True); live.mkdir()
if not (ctl / "live-nodeploy").exists():
    for f in subprocess.run(["git", "ls-files", "briefs"], capture_output=True, text=True).stdout.split():
        d = live / f.removeprefix("briefs/"); d.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(f, d)
for p in live.glob("*/index.html"):
    if (ctl / "live-alter").exists():
        p.write_text(p.read_text().replace('og:title" content="', 'og:title" content="Stale '))
for p in live.glob("*/og.png"):
    if (ctl / "live-badcard").exists():
        p.write_bytes(b"another card")
print("Current Version ID: stub-" + str(len((tmp / "deploy.log").read_text().splitlines())))
"""


def _page(slug, name, card, canonical=None, v=None):
    url = canonical or f"{SITE}/{slug}/"
    return (f'<!doctype html>\n<title>Competitor intel brief: {html.escape(name)}</title>\n'
            f'<link rel="canonical" href="{url}">\n<meta property="og:url" content="{url}">\n'
            f'<meta property="og:title" content="Competitor intel brief: {html.escape(name)}">\n'
            f'<meta property="og:description" content="A brief.">\n'
            f'<meta property="og:image" content="{SITE}/{slug}/og.png?v={v or sha(card)[:12]}">\n'
            f'<meta property="og:image:alt" content="Competitor intel brief: {html.escape(name)}.">\n'
            f'<meta name="robots" content="noindex">\n<p>{html.escape(name)}</p>\n').encode()


def _brief_root(base, slug, name=None, page_date=None, verdict="PASS", fault=None):
    """A verified brief root: brief.json, web/ (with shots/, which never ships), and its verdict.
    fault: nocard, staleverdict, card-after-build, noslash."""
    name = name or slug.replace("-", " ").title()
    root = Path(tempfile.mkdtemp(dir=base, prefix=f"{slug}-"))
    card = b"\x89PNG\r\n\x1a\n card of " + name.encode()
    brief = {"company": {"name": name, "slug": slug},
             "dates": {"evidence": {"from": page_date or today(), "to": page_date or today()}, "page": page_date or today()}}
    (root / "brief.json").write_text(json.dumps(brief), encoding="utf-8")
    (root / "web/shots").mkdir(parents=True)
    (root / "web/shots/390.png").write_bytes(b"shot")
    page = _page(slug, name, card, canonical=f"{SITE}/{slug}" if fault == "noslash" else None)
    (root / "web/index.html").write_bytes(page)
    (root / "web/og.png").write_bytes(card)
    vsha = sha(b"older bytes") if fault == "staleverdict" else sha((root / "brief.json").read_bytes())
    (root / f"correctness-{vsha}.md").write_text(f"Verdict: {verdict}\nPAGE: {sha(page)}\n", encoding="utf-8")
    if fault == "nocard":
        (root / "web/og.png").unlink()
    if fault == "card-after-build":
        (root / "web/og.png").write_bytes(card + b" redrawn")
    return root


def selftest():
    import http.server
    base = Path(tempfile.mkdtemp(prefix="publish-selftest-"))
    failed, uas, mode = [], [], {"bare": "307"}
    try:
        (base / "ctl").mkdir()
        (base / "live").mkdir()
        (base / "home").mkdir()
        env = {**os.environ, "HOME": str(base / "home"), "GIT_CONFIG_NOSYSTEM": "1", "SITE_REPO": str(base / "site"),
               "PUBLISH_STATE": str(base / "state"), "PUBLISH_DEPLOY": str(base / "deploy.py"),
               "PUBLISH_PROBE_TRIES": "2", "PUBLISH_PROBE_WAIT": "0", "PYTHONDONTWRITEBYTECODE": "1"}
        for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
            env.pop(k, None)
        os.environ.update({k: env[k] for k in ("HOME", "GIT_CONFIG_NOSYSTEM")})

        def sh(*cmd, cwd=None):
            subprocess.run(cmd, cwd=cwd, env=env, check=True, capture_output=True)

        remote, site = base / "remote.git", base / "site"
        sh("git", "init", "-q", "--bare", "-b", "main", str(remote))
        (remote / "hooks/pre-receive").write_text(f'#!/bin/sh\n[ ! -e "{base}/ctl/reject" ] || {{ echo rejected; exit 1; }}\n')
        (remote / "hooks/pre-receive").chmod(0o755)
        sh("git", "clone", "-q", str(remote), str(site))
        for k, v in (("user.name", "selftest"), ("user.email", "selftest@example.invalid"), ("commit.gpgsign", "false")):
            sh("git", "-C", str(site), "config", k, v)
        sh("git", "-C", str(site), "symbolic-ref", "HEAD", "refs/heads/main")
        (site / "index.html").write_text("<!doctype html><title>Home</title>\n")
        (site / "robots.txt").write_text("User-agent: *\nAllow: /\n")
        (site / "sitemap.xml").write_text("<urlset><url><loc>https://ryanhennebry.xyz/listed-co</loc></url></urlset>\n")
        (site / "verify.sh").write_text(STUB_VERIFY)
        (site / "verify.sh").chmod(0o755)
        sh("git", "-C", str(site), "add", "-A")
        sh("git", "-C", str(site), "commit", "-qm", "site")
        sh("git", "-C", str(site), "push", "-q", "origin", "main")
        hook = site / ".git/hooks/pre-commit"
        hook.write_text(f'#!/bin/sh\n[ ! -e "{base}/ctl/nocommit" ] || {{ echo "pre-commit: refused"; exit 1; }}\n')
        hook.chmod(0o755)
        (base / "deploy.py").write_text(STUB_DEPLOY.format(py=sys.executable, tmp=str(base)))
        (base / "deploy.py").chmod(0o755)

        class Live(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # Workers Static Assets' auto-trailing-slash: /<slug> is 307 to /<slug>/
                uas.append(self.headers.get("User-Agent"))
                path = self.path.split("?", 1)[0]
                f = base / "live" / path.lstrip("/")
                if path.endswith("/"):
                    f = f / "index.html"
                if f.is_dir():
                    if mode["bare"] == "307":
                        self.send_response(307)
                        self.send_header("Location", path + "/")
                        self.end_headers()
                        return
                    f = base / "live/none"
                if not f.is_file():
                    self.send_response(404)
                    self.end_headers()
                    return
                body = f.read_bytes()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Live)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        env["PUBLISH_PROBE_BASE"] = f"http://127.0.0.1:{srv.server_address[1]}"
        roots = base / "roots"
        roots.mkdir()

        def head():
            return git(site, "rev-parse", "HEAD").stdout.strip()

        def remote_head():
            return git(remote, "rev-parse", "main").stdout.strip()

        def run(*args):
            r = subprocess.run([sys.executable, str(Path(__file__).resolve()), *map(str, args)], env=env,
                               capture_output=True, text=True)
            return r.returncode, r.stdout, r.stderr

        def case(name, args, want, check=None, ctl=(), still=True):
            """One child run: its exit must be want; SHARE only on 0 or 31; refusals before P5 change
            nothing in the site (still); check returns a reason string when something else is wrong."""
            for c in ctl:
                (base / "ctl" / c).write_text("x")
            h0, r0 = head(), remote_head()
            try:
                code, out, err = run(*args)
            finally:
                for c in ctl:
                    (base / "ctl" / c).unlink()
            why = []
            if code != want:
                why.append(f"exit {code}, want {want}")
            if want not in (0, 31) and not err.startswith(f"PUBLISH REFUSED {want} ") and f"PUBLISH REFUSED {want} " not in err:
                why.append(f"no 'PUBLISH REFUSED {want}' line")
            if ("SHARE " in out) != (want in (0, 31) and "--unpublish" not in args):
                why.append("SHARE printed" if "SHARE " in out else "no SHARE line")
            if still and want not in (0, 31) and (head() != h0 or git(site, "status", "--porcelain").stdout.strip()):
                why.append("the site changed")
            if "--push" not in args and remote_head() != r0:
                why.append("the remote moved without --push")
            if check and not why:
                extra = check(out, err)
                if extra:
                    why.append(extra)
            ok = not why
            print(f"{'ok  ' if ok else 'FAIL'} exit {want:>2} {name}" + ("" if ok else f": {'; '.join(why)}\n    {err.strip()[-400:]}"))
            if not ok:
                failed.append(name)
            return out, err

        yesterday = (datetime.now(ZoneInfo(TZ)) - timedelta(days=1)).date().isoformat()
        case("usage: no web/og.png", [_brief_root(roots, "acme", fault="nocard")], 2)
        case("verdict FAIL", [_brief_root(roots, "acme", verdict="FAIL")], 10)
        case("verdict for older bytes of brief.json", [_brief_root(roots, "acme", fault="staleverdict")], 10)
        case("card: og.png redrawn after the build, ?v= is stale", [_brief_root(roots, "acme", fault="card-after-build")], 11)
        case("canonical without the trailing slash (D10)", [_brief_root(roots, "acme", fault="noslash")], 12)
        case("slug that names a site root file (robots.txt)", [_brief_root(roots, "robots")], 13)
        case("dates.page is yesterday (D4)", [_brief_root(roots, "acme", page_date=yesterday)], 14)
        state = base / "state"
        state.mkdir(exist_ok=True)
        with open(state / "publish.lock", "w") as lk:
            fcntl.flock(lk, fcntl.LOCK_EX)
            case("lock held by another publish", [_brief_root(roots, "acme")], 20)
        (site / "stray.txt").write_text("x")
        case("site tree not clean", [_brief_root(roots, "acme")], 20, still=False,
             check=lambda o, e: "briefs/acme placed" if (site / "briefs/acme").exists() else "")
        (site / "stray.txt").unlink()
        case("site verify.sh fails on the placed brief (slug in the sitemap)", [_brief_root(roots, "listed-co")], 22,
             check=lambda o, e: "briefs/listed-co left behind" if (site / "briefs/listed-co").exists() else "")
        case("commit fails (pre-commit hook)", [_brief_root(roots, "acme")], 23, ctl=["nocommit"],
             check=lambda o, e: "briefs/acme left behind" if (site / "briefs/acme").exists() else "")
        h_before = head()
        acme = _brief_root(roots, "acme")
        case("deploy fails: the commit stands, nothing pushed", [acme], 30, ctl=["deploy-fail"], still=False,
             check=lambda o, e: "" if git(site, "log", "-1", "--format=%s").stdout.startswith("brief(acme): CONTENT VERIFIED")
             and head() != h_before else "no brief commit after exit 30")
        n_commits = int(git(site, "rev-list", "--count", "HEAD").stdout)

        def green(o, e):
            log = (base / "deploy.log").read_text().splitlines()
            bad = []
            if f"SHARE {SITE}/acme/" not in o.splitlines():
                bad.append("SHARE is not the slash URL")
            if int(git(site, "rev-list", "--count", "HEAD").stdout) != n_commits:
                bad.append("a re-run after exit 30 committed again")
            if not log[-1].startswith("--message publish acme site@" + head()[:12]):
                bad.append(f"deploy argv {log[-1]!r}")
            if (base / "live/acme/shots").exists() or not (base / "live/acme/og.png").is_file():
                bad.append("live tree: shots/ shipped or og.png missing")
            if "worker stub-" not in o:
                bad.append("no worker version id")
            return "; ".join(bad)
        case("re-run after exit 30: deploys, probes, prints SHARE; no --push, no push", [acme], 0, check=green)
        n_deploys = len((base / "deploy.log").read_text().splitlines())
        case("same brief again: ALREADY LIVE, no deploy", [acme], 0,
             check=lambda o, e: "" if "ALREADY LIVE" in o and len((base / "deploy.log").read_text().splitlines()) == n_deploys
             else "deployed again or no ALREADY LIVE")
        case("briefs/acme holds another company's page", [_brief_root(roots, "acme", name="Other Co")], 13)
        case("live /<slug>/ never answers 200", [_brief_root(roots, "gamma")], 40, ctl=["live-nodeploy"], still=False)
        case("live page bytes differ (names og:title)", [_brief_root(roots, "delta")], 41, ctl=["live-alter"], still=False,
             check=lambda o, e: "" if "og:title" in e else "the differing og field is not named")
        case("live og:image bytes differ", [_brief_root(roots, "epsilon")], 42, ctl=["live-badcard"], still=False)
        mode["bare"] = "404"
        case("/<slug> neither 307 to /<slug>/ nor 200", [_brief_root(roots, "zeta")], 43, still=False)
        mode["bare"] = "307"
        case("push rejected: page live and probed, SHARE printed", [_brief_root(roots, "eta"), "--push"], 31, ctl=["reject"])
        case("--push: the remote takes main", [_brief_root(roots, "theta"), "--push"], 0,
             check=lambda o, e: "" if remote_head() == head() else "remote main is not the site's HEAD")
        (site / "index.html").write_text("<!doctype html><title>Home, edited</title>\n")
        sh("git", "-C", str(site), "commit", "-qam", "the operator's own edit, not deployed")
        case("an undeployed edit outside briefs/ would ship", [_brief_root(roots, "iota")], 21)
        (state / "site-deployed").write_text(head() + "\n")  # as if the operator deployed his edit himself
        case("--unpublish globex is refused (D15)", ["--unpublish", "globex"], 13)
        case("publish a scratch replay", [_brief_root(roots, "kappa-replay")], 0)
        case("--unpublish kappa-replay removes it", ["--unpublish", "kappa-replay"], 0, still=False,
             check=lambda o, e: "" if not git(site, "ls-files", "briefs/kappa-replay").stdout.strip()
             and f"UNPUBLISHED {SITE}/kappa-replay/" in o else "still tracked or no UNPUBLISHED line")
        if set(uas) != {UA}:
            failed.append("probe UA")
            print(f"FAIL every probe carries {UA!r}: saw {sorted(set(map(str, uas)))}")
        else:
            print(f"ok   every probe ({len(uas)}) carried the probe UA")
        srv.shutdown()
    finally:
        shutil.rmtree(base, ignore_errors=True)
    if failed:
        print(f"PUBLISH SELFTEST FAIL ({len(failed)}): {failed}")
        return 1
    print("PUBLISH SELFTEST OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
