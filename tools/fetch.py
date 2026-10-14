#!/usr/bin/env python3
"""Fetch one page into the run's page store, with a text layer an agent can grep.

USAGE.
    BRIEF_ROOT=output/runs/<client>-<date> python3 tools/fetch.py URL [--as-url ORIGINAL] [--json]
    python3 tools/fetch.py --selftest

WHY THIS EXISTS. WebFetch hands a page to a smaller model and returns its summary: `67-mechanics`
section 3 measured it returning 0.7% of each page. What an agent cannot see it reports as absent,
and the Northwind homepage's logo wall carried `alt=""` on every logo, so even a full text dump read the
16 customer names as missing. This script saves the raw body, writes a text layer that keeps each
image's alt, title and filename stem where the image sits, and indexes the fetch so a later gate can
ask whether a URL was really fetched.

WHAT ONE CALL DOES.
  1. `curl -L --max-time 30` the URL into `$BRIEF_ROOT/pages/<host>-<sha8 of body>.html`.
  2. Writes `<same stem>.txt`: NFC, whitespace collapsed, one table row per line with cells joined
     ` | `, each `<img>` as its own line `[img-file] <alt> | <title> | <stem>`, and the page's
     `<meta name=description>` and `og:description` fenced where they sit (the head, so first):
     `[meta-description] <text> [/meta-description]`. The closing fence stops a quote running
     from meta text into the body. Reporting a match inside it as meta is booked to
     `claims-check`, which does not read the fence yet.
  3. RENDER. A live HTML page is rendered with headless Chrome `--dump-dom` (`build/build.py`'s
     binary, sandbox on, killed after CHROME_TIMEOUT) when it is a SHELL: prose under THIN_CHARS,
     an empty mount-point `<div>` (MOUNT_IDS), or prose under SHELL_PROSE_CAP with inline script
     over SHELL_RATIO times it. Prose is every line but `[img-file]` and meta lines. Chrome's
     `--log-net-log` gives the main frame's real status and final URL, never Chrome's own
     background downloads (`main_frame()`; `render()` lists the outcomes). The layer with more prose is kept, so a short rendered "Job not found" beats curl's
     empty shell: it is the page's truth. Never kept: Chrome's own error page, a non-2xx main frame
     or one that navigated off the URL (`chrome-failed`, curl's layer stands), and a wall shown to
     the headless browser alone (BLOCKED, `status` `<code>-headless-<why>`, exit 3). Thresholds
     are [INFERRED]. A saved `file://` capture and a non-HTML body are never rendered.
  4. Appends `url, final_url, status, fetched_at, sha256, bytes, path` to `pages/index.tsv` under
     `fcntl.flock`, writing the header row first when the file is new; `index.tsv` keeps
     `claims-check.py`'s header. And `path, method, prose` to `pages/methods.tsv` the same way:
     `method` is `curl`, `chrome` (the DOM is the saved body), `curl-richer` (rendered, curl kept),
     `chrome-failed`, `chrome-unverified` or `chrome-wall`; `prose` is the kept layer's prose
     chars. Under THIN_CHARS, stderr says so: the layer could not be confirmed complete. Every
     render that is not a clean `chrome` or `curl-richer` prints a RENDER line naming why.
  5. A 401, 403, 429, 451, 503 or 999 is BLOCKED (`references/provenance.md` rule 4: a 451 and a
     bot wall's 503 are refusals to serve): the row and the `.html` are written, no `.txt`, exit 3.
     A 429 or 503 is first asked again (RETRY), up to MAX_TRIES requests, after the response's
     `Retry-After` or a doubling BACKOFF_BASE, each wait capped at BACKOFF_CAP; only the last
     response is saved and indexed, and the BLOCKED line then says how many tries it took.
  6. Any other status that is not 2xx, and not the `000` curl reports for `file://`, is NOT
     REACHED: row and `.html`, no `.txt`, exit 4. Exit 4 is recorded as blocked, never as absent,
     unless the status is 404 on a canonical path, which the caller judges; either way a missing
     page must never yield a text layer an agent can quote from as "reached, value not on it".

`--as-url ORIGINAL` fetches a saved capture (a `file://` URL) and indexes it under the URL it was
captured from: `url` is ORIGINAL, `final_url` is the `file://` path curl actually read, so the row
never claims a live fetch that did not happen. The `<host>` in the filename is ORIGINAL's host.

`--json` adds one JSON line on stdout, after any other output: `url`, `status`, `tries`, `waits`,
`path`, `exit` and `state`, the exit code typed as FETCHED, FAILED, BLOCKED, NOT_REACHED or
UNVERIFIED, so a caller reads a blocked page as a state rather than parsing stderr.

Exit codes: 0 fetched, 1 fetch failed (no row written), 2 usage, 3 blocked, 4 not reached,
5 fetched from a render whose net-log was unreadable (`chrome-unverified`: `.txt` written, the
status and final URL unconfirmed; a stderr RENDER line says so).
"""
import email.utils
import fcntl
import hashlib
import shutil
import html.parser
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.parse
from datetime import datetime, timezone

BLOCKED = {"401", "403", "429", "451", "503", "999"}
# Backoff (Globex design § 2 Gap row): a 429 or 503 is asked again, up to MAX_TRIES requests in all,
# after the response's `Retry-After` (seconds or an HTTP-date) or, with none, BACKOFF_BASE doubling;
# every wait is capped at BACKOFF_CAP seconds, so one URL waits at most 60 s. FETCH_BACKOFF_CAP is
# the test seam. A status still 429 or 503 after the last try is BLOCKED, exit 3, as before.
RETRY = {"429", "503"}
MAX_TRIES = 3
BACKOFF_BASE = 2
BACKOFF_CAP = float(os.environ.get("FETCH_BACKOFF_CAP") or 30)
# `--json` prints one typed line on stdout: the state of the fetch, keyed to the exit code.
STATES = {0: "FETCHED", 1: "FAILED", 3: "BLOCKED", 4: "NOT_REACHED", 5: "UNVERIFIED"}
NOT_REACHED_SAMPLES = ("404", "500")  # the selftest's stand-ins for "any other non-2xx"
INDEX_COLUMNS = ("url", "final_url", "status", "fetched_at", "sha256", "bytes", "path")
METHOD_COLUMNS = ("path", "method", "prose")
THIN_CHARS = 200  # [INFERRED]: an Ashby job shell yields 0 prose chars, kaluza.com/platform 6,759
# [INFERRED] A page is a script shell when inline script outweighs its prose SHELL_RATIO times AND
# its prose is under SHELL_PROSE_CAP. Measured on 16 live pages (P8b Fix 2): kaluza.com/careers,
# roles in the DOM only, has 1,097 prose at ratio 13.7; the four ratio-only false retries (8.0 to
# 33.6) all carry 2,131 prose or more, and gained 1-12% or a consent dialog from a render.
SHELL_RATIO = 5
SHELL_PROSE_CAP = 1500
MOUNT_IDS = ("root", "app", "__next", "__nuxt", "___gatsby", "svelte")
CHROME_TIMEOUT = int(os.environ.get("FETCH_CHROME_TIMEOUT") or 20)  # seconds; env is the test seam
# Chrome's own pages: net errors (DNS, refused, timeout) and interstitials (TLS).
CHROME_PAGE_MARKS = ('id="main-frame-error"', 'class="neterror"', "interstitial-wrapper")
# The second wall signal, after the net-log's status. Lowercase, read from the DOM's text, and a
# wall only when curl's text lacks it: a vendor's own words, and its markup tokens.
WALL_PHRASES = ("verifying you are human", "verify you are human", "checking your browser",
                "checking if the site connection is secure", "complete the security check",
                "enable javascript and cookies to continue", "press & hold", "are you a robot",
                "performing security verification", "pardon our interruption",
                "please enable js and disable any ad blocker", "access denied")
WALL_MARKS = ("_cf_chl_opt", "captcha-delivery.com", "_incapsula_resource", "px-captcha")
WALL_PROSE_MAX = 1000  # [INFERRED] the round-3 walls ran 60-300 prose chars
# build/build.py's binary. FETCH_CHROME overrides it so the selftest can fake Chrome offline.
_MAC_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CHROME = (os.environ.get("FETCH_CHROME") or (_MAC_CHROME if os.path.exists(_MAC_CHROME) else None)
          or shutil.which("google-chrome") or shutil.which("chromium") or _MAC_CHROME)
META_DESCRIPTIONS = {("name", "description"): "[meta-description]",
                     ("property", "og:description"): "[og-description]"}
SKIP_TAGS = {"script", "style", "noscript", "template", "svg", "head"}
BLOCK_TAGS = {
    "address", "article", "aside", "blockquote", "br", "dd", "div", "dl", "dt", "fieldset",
    "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr",
    "li", "main", "nav", "ol", "p", "pre", "section", "table", "ul", "button", "label", "option",
}


def collapse(text):
    return re.sub(r"\s+", " ", text).strip()


def img_source(attrs):
    """The URL naming the real image, for any site's markup rather than one CMS's. A lazy loader's
    `data-src` beats its placeholder `src`; a `data:` URI names nothing; an image carrying only
    `srcset` is named by that set's first entry."""
    candidates = [attrs.get("data-src", ""), attrs.get("src", "")]
    candidates.append((attrs.get("srcset", "").split(",")[0].split() or [""])[0])
    for url in candidates:
        url = url.strip()
        if url and not url.lower().startswith("data:"):
            return url
    return ""


def img_stem(src):
    """The image's filename without directory, query or extension, percent-decoded. An image proxy
    (`/_next/image?url=%2Flogos%2Facme.png`) names the real file in its `url=` parameter."""
    parsed = urllib.parse.urlparse(src or "")
    inner = urllib.parse.parse_qs(parsed.query).get("url")
    path = urllib.parse.urlparse(inner[0]).path if inner else parsed.path
    return os.path.splitext(urllib.parse.unquote(os.path.basename(path)))[0]


class TextLayer(html.parser.HTMLParser):
    """Collects lines. Text accumulates in `buf` until a block boundary flushes it. Inside a table
    row, text goes to the current cell instead, and `</tr>` emits the row as one line. An `<img>`
    flushes the text before it and becomes its own line, so it sits under whatever heading precedes
    it; inside a table row its line lands before the row's line, which is emitted at the row's end."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines, self.buf, self.skip, self.row, self.cell = [], [], 0, None, None

    def flush(self):
        line = collapse("".join(self.buf))
        self.buf = []
        if line:
            self.lines.append(line)

    def end_cell(self):
        if self.row is not None and self.cell is not None:
            self.row.append(collapse("".join(self.cell)))
        self.cell = None

    def end_row(self):
        self.end_cell()
        line = " | ".join(c for c in self.row or [] if c)
        if line:
            self.lines.append(line)
        self.row = None

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "meta":  # before the skip test: a description sits in the skipped `<head>`
            for (key, value), label in META_DESCRIPTIONS.items():
                if a.get(key, "").lower() == value and collapse(a.get("content", "")):
                    self.flush()
                    self.lines.append("%s %s [/%s" % (label, collapse(a["content"]), label[1:]))
            return
        if tag in SKIP_TAGS:
            self.skip += 1
        if self.skip:
            return
        if tag == "img":
            self.flush()
            self.lines.append("[img-file] %s | %s | %s" % (
                collapse(a.get("alt", "")), collapse(a.get("title", "")),
                collapse(img_stem(img_source(a)))))
        elif tag == "tr":
            if self.row is not None:
                self.end_row()
            self.flush()
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.end_cell()
            self.cell = []
        elif tag in BLOCK_TAGS and self.row is None:
            self.flush()

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag in SKIP_TAGS:
            self.skip = max(0, self.skip - 1)

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag in ("td", "th"):
            self.end_cell()
        elif tag == "tr" and self.row is not None:
            self.end_row()
        elif tag in BLOCK_TAGS and self.row is None:
            self.flush()

    def handle_data(self, data):
        if self.skip:
            return
        if self.row is None:
            self.buf.append(data)
        else:
            if self.cell is None:
                self.cell = []
            self.cell.append(data)


def text_layer(body):
    """Bytes of an HTML page to its text layer: a list of lines, each NFC-normalised."""
    parser = TextLayer()
    parser.feed(body.decode("utf-8", errors="replace"))
    parser.close()
    if parser.row is not None:
        parser.end_row()
    parser.flush()
    return [unicodedata.normalize("NFC", line) for line in parser.lines]


def is_thin(lines):
    """True when the prose, every line but the `[img-file]` and meta lines, is under THIN_CHARS.
    Meta lines do not count: a JavaScript shell still carries its description."""
    return prose_chars(lines) < THIN_CHARS


def prose_chars(lines):
    """Characters on every line but the `[img-file]` and meta lines."""
    labels = ("[img-file] ",) + tuple(l + " " for l in META_DESCRIPTIONS.values())
    return sum(len(l) for l in lines if not l.startswith(labels))


def is_shell(body, lines):
    """Whether curl's HTML looks like a page JavaScript fills in: thin prose, inline script over
    SHELL_RATIO times the prose, or an empty mount-point `<div>` a framework renders into."""
    text = body.decode("utf-8", errors="replace")
    prose = prose_chars(lines)
    script = sum(len(s) for s in re.findall(r"<script\b[^>]*>(.*?)</script\s*>", text, re.S | re.I))
    mount = re.search(r"<div\b[^>]*\bid=[\"'](?:%s)[\"'][^>]*>\s*</div>"
                      % "|".join(re.escape(m) for m in MOUNT_IDS), text, re.I)
    return (prose < THIN_CHARS or mount is not None
            or (prose < SHELL_PROSE_CAP and script > SHELL_RATIO * prose))


def chrome_dom(url):
    """(DOM bytes or None, main_frame()'s (final URL, status) or None, why the DOM is None). A
    failed render is never an error: the curl body stands. The sandbox stays on: this runs
    third-party JavaScript. Chrome's stdout is a file, not a pipe, so a process that inherits it
    (Chrome's crash reporter calls setsid and leaves the group) can never hold the fetch open;
    CHROME_TIMEOUT bounds the wait on Chrome itself."""
    with tempfile.TemporaryDirectory(prefix="fetch-chrome-") as tmp:
        net, out = os.path.join(tmp, "netlog.json"), os.path.join(tmp, "dom.html")
        before = crash_handlers()
        with open(out, "wb") as fh:
            try:
                proc = subprocess.Popen(
                    [CHROME, "--headless", "--disable-gpu", "--virtual-time-budget=10000",
                     "--log-net-log=" + net, "--dump-dom", url],
                    stdout=fh, stderr=subprocess.DEVNULL, start_new_session=True)
            except OSError as err:
                return None, None, "Chrome did not start (%s)" % err
            try:
                proc.wait(timeout=CHROME_TIMEOUT)
                why = "Chrome exited %d" % proc.returncode if proc.returncode else None
            except subprocess.TimeoutExpired:
                why = "Chrome outlived %d s and was killed" % CHROME_TIMEOUT
            if why:
                reap(proc, before)
                return None, None, why
        with open(out, "rb") as fh:
            dom = fh.read()
        if not dom.strip():
            return None, None, "Chrome printed no DOM"
        return dom, main_frame(net, url), None


def reap(proc, before):
    """Kill what a failed render left: Chrome's process group, then any crash reporter that was
    not running `before` it started. A process that has already exited is not an error. Nothing
    outside can hold the fetch open: Chrome's stdout is a file."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        pass
    proc.wait()
    for pid in crash_handlers() - before - {os.getpid()}:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def crash_handlers():
    """PIDs of running Chrome crash reporters from CHROME's install directory (as given or with
    symlinks resolved). Chrome double-forks its reporter through a setsid child, so it leaves the
    render's process group, and no flag stops it (`--disable-crash-reporter`, `--disable-breakpad`,
    `--disable-crashpad-for-testing` and `CHROME_HEADLESS` all measured). Its args match any
    Chrome's reporter, the user's own browser's included: chrome_dom() takes the set before a
    render, and reap() kills only what is new since."""
    homes = set()
    for path in (CHROME, os.path.realpath(CHROME)):
        homes.add(path[:path.find(".app/") + 5] if ".app/" in path else os.path.dirname(path) + "/")
    # pgrep, not ps: macOS's ps is setuid, and a sandboxed run cannot exec it. Full args are
    # `-lf` on macOS and `-af` on Linux (macOS's -a means ancestors).
    flags = "-lf" if sys.platform == "darwin" else "-af"
    try:
        out = subprocess.run(["pgrep", flags, "crashpad_handler"],
                             capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return set()
    found = set()
    for line in out.splitlines():
        parts = line.split(None, 1)
        if (len(parts) == 2 and parts[0].isdigit()
                and any(home in parts[1] for home in homes)):
            found.add(int(parts[0]))
    return found




def main_frame(path, target=None):
    """The main frame's last navigation in a Chrome net-log: (URL, HTTP status), or None when the
    log is missing, unreadable or names no main-frame request. An HTTP redirect restarts the same
    request with a new URL; a JavaScript navigation opens a new one. Either way the last
    `URL_REQUEST_START_JOB` of type "main frame" is where the page ended up, counting only the
    page's own navigations. Chrome also downloads its own models in the background, typed "main
    frame" too (a 20 s render ended "at" optimizationguide-pa.googleapis.com). Each request's
    `REQUEST_ALIVE` names the Chrome feature that made it (`traffic_annotation`), and every
    navigation, script ones included, shares one (measured). So the page's first request (on
    `target` when one matches, else the first) fixes the annotation, and a later main-frame
    request counts only when it carries the same. A log with no annotations counts them all."""
    try:
        with open(path, encoding="utf-8") as fh:
            log = json.load(fh)
        types = log["constants"]["logEventTypes"]
        start, headers = types["URL_REQUEST_START_JOB"], types["HTTP_TRANSACTION_READ_RESPONSE_HEADERS"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    events = log.get("events", [])
    alive = types.get("REQUEST_ALIVE")
    feature = {e["source"]["id"]: e["params"]["traffic_annotation"] for e in events
               if e.get("type") == alive and "traffic_annotation" in (e.get("params") or {})}
    navs = [e for e in events if e.get("type") == start
            and (e.get("params") or {}).get("request_type") == "main frame"]
    first = next((e for e in navs if target and same_page(e["params"].get("url"), target)),
                 navs[0] if navs else None)
    page = feature.get(first["source"]["id"]) if first else None
    navs = {id(e) for e in navs if feature.get(e["source"]["id"]) == page}
    sid, url, status = None, None, None
    for event in events:
        params = event.get("params") or {}
        if id(event) in navs:
            sid, url, status = event["source"]["id"], params.get("url"), None
        elif event.get("type") == headers and sid is not None and event["source"]["id"] == sid:
            lines = params.get("headers") or [""]
            status = (str(lines[0]).split() + ["", ""])[1]
    return (url, status) if url and status else None


def same_page(a, b):
    """Two URLs name one page: scheme and host case-folded, an empty path as `/`, no fragment."""
    pa, pb = urllib.parse.urlsplit(a or ""), urllib.parse.urlsplit(b or "")
    key = lambda p: (p.scheme.lower(), p.netloc.lower(), p.path or "/", p.query)
    return key(pa) == key(pb)


def append_index(pages, fields, name="index.tsv", columns=INDEX_COLUMNS):
    """Append one row to `pages/<name>`. The exclusive flock covers the is-it-new check and the
    header, so two writers on a fresh store cannot both write a header, and each row is one write."""
    index = os.path.join(pages, name)
    with open(index, "a", encoding="utf-8") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            if os.fstat(fh.fileno()).st_size == 0:
                fh.write("\t".join(columns) + "\n")
            fh.write("\t".join(str(f).replace("\t", " ").replace("\n", " ") for f in fields) + "\n")
            fh.flush()
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def write_atomic(path, data):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".fetch-")
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)


def retry_after(headers):
    """Seconds the last response in curl's `-D` dump asks to wait, from `Retry-After` as seconds
    or as an HTTP-date (a past date reads 0); None when absent or unreadable."""
    blocks = [b for b in re.split(r"\r?\n\r?\n", headers or "") if b.strip()]
    if not blocks:
        return None
    value = None
    for line in blocks[-1].splitlines():
        name, _, rest = line.partition(":")
        if name.strip().lower() == "retry-after":
            value = rest.strip()
    if value is None:
        return None
    if value.isdigit():
        return float(value)
    try:
        when = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when is None:
        return None
    return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())


def curl(url, header_file=None):
    """Returns (body, status, content_type, final_url), or raises RuntimeError naming curl's
    failure. With `header_file`, curl dumps every response's headers there (`-D`)."""
    fd, tmp = tempfile.mkstemp(prefix="fetch-body-")
    os.close(fd)
    try:
        dump = ["-D", header_file] if header_file else []
        proc = subprocess.run(
            ["curl", "-sS", "-L", "--max-time", "30", "-o", tmp] + dump +
            ["-w", "%{http_code}\t%{content_type}\t%{url_effective}", "--", url],
            capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError("curl exit %d: %s" % (proc.returncode, proc.stderr.strip()))
        status, ctype, final_url = (proc.stdout.split("\t", 2) + ["", ""])[:3]
        with open(tmp, "rb") as fh:
            return fh.read(), status.strip(), ctype.strip().lower(), final_url.strip()
    finally:
        os.unlink(tmp)


def curl_backoff(url):
    """curl() asked again on a 429 or 503 (RETRY), MAX_TRIES requests in all, each wait the last
    response's Retry-After or BACKOFF_BASE doubling, capped at BACKOFF_CAP. A `file://` read is
    asked once. Returns curl()'s four values, the request count and the waits."""
    fd, head = tempfile.mkstemp(prefix="fetch-head-")
    os.close(fd)
    tries, waits = 0, []
    try:
        while True:
            body, status, ctype, final_url = curl(url, head)
            tries += 1
            if status not in RETRY or tries >= MAX_TRIES or url.lower().startswith("file:"):
                return body, status, ctype, final_url, tries, waits
            with open(head, encoding="latin-1") as fh:
                asked = retry_after(fh.read())
            wait = min(BACKOFF_CAP, BACKOFF_BASE * 2 ** (tries - 1) if asked is None else asked)
            waits.append(wait)
            time.sleep(wait)
    finally:
        os.unlink(head)


def render(url, body, lines):
    """Chrome's render of `url` (curl's final URL) against curl's body. Returns (method, body,
    lines, wall, note): the layer to keep, for a wall the reason `status` gets, and a note for
    stderr. In order:
    - no DOM, or Chrome's own error page: `chrome-failed`, curl's layer stands, note says why;
    - with a readable net-log: a BLOCKED main-frame status is `chrome-wall` (`headless-<status>`);
      any other non-2xx, or a final URL off `url` (a script navigating to a 404 or a login page),
      is `chrome-failed`;
    - is_wall(): `chrome-wall` (`headless-wall`);
    - else the layer with more prose: `chrome` or `curl-richer`. With no readable net-log (missing,
      truncated, or a Chrome whose log shape drifted) the DOM's status and URL are unverified: a
      kept DOM is `chrome-unverified`, and the note names the tool fault either way.
    A wall keeps the DOM as the saved evidence and never gets a text layer."""
    dom, net, why = chrome_dom(url)
    if dom is None:
        return "chrome-failed", body, lines, None, why
    raw = dom.decode("utf-8", errors="replace")
    if any(mark in raw for mark in CHROME_PAGE_MARKS):
        return "chrome-failed", body, lines, None, "Chrome showed its own error page"
    dom_lines = text_layer(dom)
    note = None
    if net is None:
        note = "Chrome's net-log is missing or unreadable (a tool fault): status and URL unverified"
    elif net[1] in BLOCKED:
        return "chrome-wall", dom, dom_lines, "headless-" + net[1], None
    elif not net[1].startswith("2") or not same_page(net[0], url):
        return "chrome-failed", body, lines, None, "the main frame ended %s at %s" % net[::-1]
    if is_wall(dom_lines, raw, lines, body):
        return "chrome-wall", dom, dom_lines, "headless-wall", note
    if prose_chars(dom_lines) > prose_chars(lines):
        return ("chrome-unverified" if note else "chrome"), dom, dom_lines, None, note
    return "curl-richer", body, lines, None, note


def is_wall(dom_lines, dom_raw, lines, body):
    """A wall shown to the headless browser alone: a WALL_PHRASES phrase in a short DOM's text
    (walls are short: under WALL_PROSE_MAX), or a WALL_MARKS token in its markup, case-folded, and
    either one absent from curl's page."""
    dom_text, curl_text = " ".join(dom_lines).lower(), " ".join(lines).lower()
    raw, curl_raw = dom_raw.lower(), body.decode("utf-8", errors="replace").lower()
    return ((prose_chars(dom_lines) < WALL_PROSE_MAX
             and any(p in dom_text and p not in curl_text for p in WALL_PHRASES))
            or any(m in raw and m not in curl_raw for m in WALL_MARKS))


def fetch(url, as_url, brief_root, said=None):
    """One fetch. Returns the exit code: 0 fetched, 3 blocked, 4 not reached, 5 unverified.
    `said`, a dict, receives the indexed URL, status, request count, waits and saved path."""
    body, status, ctype, final_url, tries, waits = curl_backoff(url)
    blocked = status in BLOCKED
    reached = not blocked and (status.startswith("2") or status == "000")
    method, lines = "curl", []
    if reached:
        lines = text_layer(body)
        live_html = "html" in ctype and not url.lower().startswith("file:")
        if live_html and is_shell(body, lines):
            method, body, lines, wall, note = render(final_url or url, body, lines)
            if note:
                print("RENDER %s %s: %s" % (method, url, note), file=sys.stderr)
            if wall:
                status, blocked, reached = status + "-" + wall, True, False
    indexed = as_url or url
    sha = hashlib.sha256(body).hexdigest()
    host = urllib.parse.urlparse(indexed).hostname or "local"
    pages = os.path.join(brief_root, "pages")
    os.makedirs(pages, exist_ok=True)
    html_path = os.path.join(pages, "%s-%s.html" % (host, sha[:8]))
    write_atomic(html_path, body)
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rel = os.path.relpath(html_path, brief_root)
    append_index(pages, (indexed, final_url, status, fetched_at, sha, len(body), rel))
    prose = prose_chars(lines) if reached else "-"
    append_index(pages, (rel, method, prose), "methods.tsv", METHOD_COLUMNS)
    if said is not None:
        said.update(url=indexed, status=status, tries=tries, waits=waits, path=rel)
    if blocked:
        print("BLOCKED %s %s -> %s%s" % (status, indexed, rel,
                                         " after %d tries" % tries if tries > 1 else ""), file=sys.stderr)
        return 3
    if not reached:
        print("NOT REACHED %s %s -> %s" % (status, indexed, rel), file=sys.stderr)
        return 4
    txt = "\n".join(lines) + "\n"
    write_atomic(html_path[:-len(".html")] + ".txt", txt.encode("utf-8"))
    print("FETCHED %s %s %s -> %s" % (status, method, indexed, rel))
    if prose < THIN_CHARS:
        print("THIN %s: %d prose chars (%s); could not confirm the layer is complete"
              % (indexed, prose, method), file=sys.stderr)
    return 5 if method == "chrome-unverified" else 0


# --- selftest -------------------------------------------------------------------------------------
# Offline. The capture and what it must yield live in `tools/fixtures/fetch/`: the `.expected.tsv`
# beside the capture carries the heading, the logo names and the non-logo stem as `kind<TAB>value`
# rows, so the tool's code carries no company's names. The fixture's filename is the one capture
# this selftest reads.
FIXTURES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "tools", "fixtures", "fetch")
CAPTURE = os.path.join(FIXTURES, "www-northwind-energy-home.html")
EXPECTED = os.path.join(FIXTURES, "www-northwind-energy-home.expected.tsv")
FAILS = []


def check(case, ok, detail=""):
    if ok:
        print("SELFTEST OK   %s" % case)
    else:
        print("SELFTEST FAIL %s: %s" % (case, detail))
        FAILS.append(case)


def read_expected():
    exp = {"heading": [], "logo": [], "non-logo": []}
    with open(EXPECTED, encoding="utf-8") as fh:
        for line in fh:
            if line.strip() and not line.startswith("#"):
                kind, _, value = line.rstrip("\n").partition("\t")
                exp[kind].append(value)
    return exp


def img_stem_of(line):
    return line.rsplit(" | ", 1)[-1] if line.startswith("[img-file] ") else None


def case_logo_wall(lines, exp):
    """Each expected logo is an `[img-file]` line in the unbroken run of image lines that directly
    follows the heading line, so the wall keeps its heading in the text layer."""
    heads = [i for i, l in enumerate(lines) if l == exp["heading"][0]]
    if len(heads) != 1:
        return check("logo wall keeps its heading", False,
                     "heading %r found %d times, want 1" % (exp["heading"][0], len(heads)))
    run, i = [], heads[0] + 1
    while i < len(lines) and lines[i].startswith("[img-file] "):
        run.append(img_stem_of(lines[i]).lower())
        i += 1
    missing = [n for n in exp["logo"] if not any(n.lower() in s for s in run)]
    check("logo wall keeps its heading (%d names)" % len(exp["logo"]),
          len(exp["logo"]) == 16 and not missing,
          "want 16 expected names, have %d; missing after the heading: %s"
          % (len(exp["logo"]), ", ".join(missing) or "none"))


def case_non_logo(lines, exp):
    stem = exp["non-logo"][0]
    hits = [l for l in lines if stem in l]
    stray = [l for l in hits if not l.startswith("[img-file] ")]
    check("non-logo stem only on [img-file] lines", hits and not stray,
          "%d hits, %d not on an [img-file] line" % (len(hits), len(stray)))


def run_child(tmp, args, path_prefix=None, chrome=None, extra=None):
    """This file as a child process, so `main()` and the argument dispatch are exercised too.
    FETCH_CHROME is always set, to the stub or to a missing path, so no child runs real Chrome."""
    env = dict(os.environ, BRIEF_ROOT=tmp, FETCH_CHROME=chrome or os.path.join(tmp, "no-chrome"),
               **(extra or {}))
    if path_prefix:
        env["PATH"] = path_prefix + os.pathsep + env["PATH"]
    return subprocess.run([sys.executable, os.path.abspath(__file__)] + args,
                          env=env, capture_output=True, text=True)


def index_rows(tmp):
    with open(os.path.join(tmp, "pages", "index.tsv"), encoding="utf-8") as fh:
        return [l.rstrip("\n").split("\t") for l in fh]


def case_file_fetch(tmp, lines):
    original = "https://capture.invalid/home"
    proc = run_child(tmp, ["file://" + CAPTURE, "--as-url", original])
    with open(CAPTURE, "rb") as fh:
        want = hashlib.sha256(fh.read()).hexdigest()
    rows = index_rows(tmp) if proc.returncode == 0 else []
    body = rows[1:]
    ok = (proc.returncode == 0 and rows and rows[0] == list(INDEX_COLUMNS) and len(body) == 1
          and body[0][0] == original and body[0][1].startswith("file://") and body[0][4] == want)
    txt = os.path.join(tmp, body[0][6][:-len(".html")] + ".txt") if ok else ""
    ok = ok and os.path.isfile(txt)
    if ok:
        with open(txt, encoding="utf-8") as fh:
            ok = fh.read().splitlines() == lines
    check("file:// fetch appends one index row whose sha256 matches", ok,
          "exit %d, rows %r, stderr %s" % (proc.returncode, rows[1:], proc.stderr.strip()))


STUB_CURL = """#!/bin/sh
out=
while [ $# -gt 0 ]; do case "$1" in -o) out="$2"; shift;; esac; shift; done
if [ -n "$STUB_BODY_FILE" ]; then cat "$STUB_BODY_FILE" > "$out"
else printf '<p>page %s</p>' "$STUB_STATUS" > "$out"; fi
printf '%s\\t%s\\t%s' "$STUB_STATUS" "${STUB_CTYPE-text/html}" "${STUB_FINAL_URL:-https://b.invalid/}"
"""
STUB_CHROME = """#!/bin/sh
printf '%s\\n' "$*" >> "$STUB_CHROME_LOG"
net=
for a in "$@"; do case "$a" in --log-net-log=*) net="${a#--log-net-log=}";; esac; done
[ -z "$STUB_CHROME_SLEEP" ] || sleep "$STUB_CHROME_SLEEP"
[ -z "$STUB_NETLOG_FILE" ] || [ -z "$net" ] || cp "$STUB_NETLOG_FILE" "$net"
[ -n "$STUB_DOM_FILE" ] || exit 1
cat "$STUB_DOM_FILE"
exit "${STUB_CHROME_EXIT:-0}"
"""


# Chrome's crash reporter, as measured: double-forked through a setsid child, so it leaves the
# process group, with that child's pid as its group id. `hang`: it keeps the stdout it inherited
# and the parent hangs (a timed-out render). `exit`: the same, but the parent exits 1 at once.
# `detach`: it closes stdout, as the real one does, and the parent hangs. The parent records the
# escaped pid.
STUB_ESCAPE = """#!%s
import os, sys, time
mode = os.environ.get("STUB_ESCAPE_MODE")
here = os.path.dirname(os.path.abspath(__file__))


def spawn(script, close_stdout=False):
    r, w = os.pipe()
    if os.fork() == 0:
        os.setsid()
        pid = os.fork()
        if pid == 0:
            if close_stdout:
                os.close(1)
            os.execv(sys.executable, [sys.executable, script])
        os.write(w, str(pid).encode())
        os._exit(0)
    os.close(w)
    return os.read(r, 32).decode()


# First pid: the reporter, which must die. Then bystanders, which must live: a process from
# Chrome's home not named a reporter (a concurrent render's), and a reporter from elsewhere.
pids = [spawn(os.path.join(here, "chrome_crashpad_handler"), mode == "detach")]
if mode == "detach":
    pids += [spawn(os.path.join(here, "bystander")), spawn(os.environ["STUB_ELSEWHERE_HANDLER"])]
with open(os.environ["STUB_ESCAPE_PIDFILE"], "w") as fh:
    fh.write(" ".join(pids))
if mode in ("hang", "detach"):
    time.sleep(60)
sys.exit(1)
"""


def make_stub(tmp):
    """A stub curl for PATH and a stub Chrome for FETCH_CHROME. Curl honours `-o` and `-w`, answers
    `$STUB_STATUS` and `$STUB_CTYPE` (default text/html), and writes `$STUB_BODY_FILE` when set.
    Chrome logs its arguments to `$STUB_CHROME_LOG`, prints `$STUB_DOM_FILE` and exits
    `$STUB_CHROME_EXIT`, or exits 1 with no file. All offline."""
    stub_dir = os.path.join(tmp, "stub")
    os.makedirs(stub_dir)
    os.makedirs(os.path.join(tmp, "elsewhere"))
    sleeper = "import time\ntime.sleep(30)\n"
    for name, script in (("curl", STUB_CURL), ("chrome", STUB_CHROME),
                         ("chrome-escape", STUB_ESCAPE % sys.executable),
                         ("chrome_crashpad_handler", sleeper), ("bystander", sleeper),
                         ("../elsewhere/chrome_crashpad_handler", sleeper)):
        with open(os.path.join(stub_dir, name), "w") as fh:
            fh.write(script)
        os.chmod(os.path.join(stub_dir, name), 0o755)
    return stub_dir


def case_status(tmp, stub_dir, code, want_exit):
    """One stubbed fetch answering `code`: one row carrying it, and a `.txt` only on exit 0."""
    root = os.path.join(tmp, "status-" + code)
    os.environ["STUB_STATUS"] = code
    try:
        proc = run_child(root, ["https://b.invalid/"], path_prefix=stub_dir, extra={"FETCH_BACKOFF_CAP": "0"})
    finally:
        del os.environ["STUB_STATUS"]
    pages = os.path.join(root, "pages")
    rows = index_rows(root) if os.path.exists(os.path.join(pages, "index.tsv")) else []
    txts = [f for f in os.listdir(pages) if f.endswith(".txt")] if rows else ["?"]
    ok = (proc.returncode == want_exit and len(rows) == 2 and rows[1][2] == code
          and len(txts) == (1 if want_exit == 0 else 0))
    check("%s: one row, %s, exit %d" % (code, ".txt" if want_exit == 0 else "no .txt", want_exit),
          ok, "exit %d, rows %r, txt files %r" % (proc.returncode, rows, txts))


def page(inner, head=""):
    return "<html><head>%s</head><body>%s</body></html>" % (head, inner)


# Synthetic pages, each built to pin one branch. SHELL's only text is a description long enough
# that counting meta lines as prose would call it full.
SHELL = page('<div id="root"></div>',
             '<meta name="description" content="%s">' % ("Open roles board " * 15))
RENDERED = page("<p>%s</p>" % ("The rendered posting text. " * 10))
FULL = page("<p>%s</p>" % ("Server rendered prose. " * 10))
SCRIPTY = page("<p>%s</p><script>%s</script>" % ("Some server prose. " * 16, "x=1;" * 900))
LOGOS = page("".join('<img alt="Partner logo number %d, a long alt text">' % i for i in range(12)))
NETERR = page('<div id="main-frame-error"><p>%s</p></div>' % ("This site can't be reached. " * 10))
INTERSTITIAL = page('<div class="interstitial-wrapper"><p>%s</p></div>'
                    % ("Your connection is not private. " * 10))
WALL = page("<p>Verifying you are human. This may take a few seconds.</p>")
ON_TOPIC = page('<div id="app"></div><p>How to verify you are human on our site.</p>')
LIVE = "https://b.invalid/"
RENDER_CASES = (  # name, url, curl body, content type, DOM, Chrome exit -> exit, method, .txt line
    ("rendered", LIVE, SHELL, "text/html", RENDERED, 0, 0, "chrome", "The rendered posting"),
    ("chrome-fails", LIVE, SHELL, "text/html", None, 1, 0, "chrome-failed", "[/meta-description]"),
    ("chrome-exit-1", LIVE, SHELL, "text/html", RENDERED, 1, 0, "chrome-failed", "Open roles"),
    ("dom-short-truth", LIVE, SHELL, "text/html", page("<p>Job not found</p>"), 0, 0, "chrome",
     "Job not found"),
    ("curl-richer", LIVE, SCRIPTY, "text/html", page("<p>Short.</p>"), 0, 0, "curl-richer",
     "Some server prose."),
    ("script-ratio", LIVE, SCRIPTY, "text/html", RENDERED * 2, 0, 0, "chrome",
     "The rendered posting"),
    ("logo-only", LIVE, LOGOS, "text/html", RENDERED, 0, 0, "chrome", "The rendered posting"),
    ("neterror", LIVE, SHELL, "text/html", NETERR, 0, 0, "chrome-failed", "Open roles"),
    ("neterror-body", LIVE, SHELL, "text/html", NETERR.replace("<body>", '<body class="neterror">')
     .replace('id="main-frame-error"', 'id="frame"'), 0, 0, "chrome-failed", "Open roles"),
    ("interstitial", LIVE, SHELL, "text/html", INTERSTITIAL, 0, 0, "chrome-failed", "Open roles"),
    ("wall-words-in-both", LIVE, ON_TOPIC, "text/html", page(RENDERED + "verify you are human"),
     0, 0, "chrome", "The rendered posting"),
    ("xml-body", LIVE, '<?xml version="1.0"?><feed><t>x</t></feed>', "application/xml",
     RENDERED, 0, 0, "curl", "x"),
    ("full", LIVE, FULL, "text/html", RENDERED, 0, 0, "curl", "Server rendered prose."),
    ("script-heavy-full", LIVE, page("<p>%s</p><script>%s</script>" % (
        "Server rendered prose. " * 70, "x=1;" * 3000)), "text/html", RENDERED, 0, 0, "curl",
     "Server rendered prose."),
    ("mount-point", LIVE, page('<div id="__next"> </div><p>%s</p>' % ("Menu item. " * 25)),
     "text/html", RENDERED * 2, 0, 0, "chrome", "The rendered posting"),
    ("file-capture", "file:///capture.invalid/shell.html", SHELL, "text/html", RENDERED, 0, 0,
     "curl", "Open roles"),
)


WALLED = "200-headless-wall"
UNREAD = "net-log is missing or unreadable"
NET_CASES = (  # (a RENDER_CASES row, keyword overrides): the net-log, wall-mark and timeout branches
    (("net-403", LIVE, SHELL, "text/html", RENDERED, 0, 3, "chrome-wall", None),
     {"net": [(LIVE, "403")], "want_status": "200-headless-403"}),
    (("net-500", LIVE, SHELL, "text/html", RENDERED, 0, 0, "chrome-failed", "Open roles"),
     {"net": [(LIVE, "500")]}),
    (("net-js-404", LIVE, SHELL, "text/html", RENDERED, 0, 0, "chrome-failed", "Open roles"),
     {"net": [(LIVE, "200"), (LIVE + "missing", "404")]}),
    (("net-js-login", LIVE, SHELL, "text/html", RENDERED, 0, 0, "chrome-failed", "Open roles"),
     {"net": [(LIVE, "200"), (LIVE + "login", "200")]}),
    (("net-redirect-home", LIVE, SHELL, "text/html", RENDERED, 0, 0, "chrome", "The rendered"),
     {"net": [(LIVE + "old", "301"), (LIVE, "200")]}),
    (("net-bare-host", "https://b.invalid", SHELL, "text/html", RENDERED, 0, 0, "chrome",
      "The rendered"), {"net": [(LIVE, "200")]}),
    (("net-missing", LIVE, SHELL, "text/html", RENDERED, 0, 5, "chrome-unverified",
      "The rendered"), {"net": "none", "want_note": UNREAD}),
    (("net-truncated", LIVE, SHELL, "text/html", RENDERED, 0, 5, "chrome-unverified",
      "The rendered"), {"net": "truncated", "want_note": UNREAD}),
    (("net-drifted", LIVE, SHELL, "text/html", RENDERED, 0, 5, "chrome-unverified",
      "The rendered"), {"net": "drifted", "want_note": UNREAD}),
    (("net-missing-curl-richer", LIVE, SCRIPTY, "text/html", page("<p>Short.</p>"), 0, 0,
      "curl-richer", "Some server prose."), {"net": "none", "want_note": UNREAD}),
    (("net-other-host", LIVE, SHELL, "text/html", RENDERED, 0, 0, "chrome-failed", "Open roles"),
     {"net": [("https://login.invalid/", "200")], "want_note": "ended 200 at"}),
    (("net-other-query", LIVE, SHELL, "text/html", RENDERED, 0, 0, "chrome-failed", "Open roles"),
     {"net": [(LIVE + "?next=1", "200")]}),
    (("net-other-scheme", LIVE, SHELL, "text/html", RENDERED, 0, 0, "chrome-failed", "Open roles"),
     {"net": [("http://b.invalid/", "200")]}),
    (("net-redirect-one-request", LIVE, SHELL, "text/html", RENDERED, 0, 0, "chrome",
      "The rendered"), {"net": [(LIVE + "old", "301"), (LIVE, "200")], "one_request": True}),
    # Real Chrome 155 net-logs of a 27 s local render (trimmed to main-frame requests): Chrome's
    # own model downloads, typed "main frame", land after the page. The first keeps the DOM; the
    # second's script navigation to /landed is still caught past them.
    (("net-background-download", "http://127.0.0.1:8766/", SHELL, "text/html", RENDERED, 0, 0,
      "chrome", "The rendered"), {"net": "background-download.netlog.json"}),
    (("net-background-download-js-nav", "http://127.0.0.1:8767/", SHELL, "text/html", RENDERED,
      0, 0, "chrome-failed", "Open roles"), {"net": "background-download-js-nav.netlog.json",
                                             "want_note": "ended 200 at http://127.0.0.1:8767/landed"}),
    (("wall-phrase", LIVE, SHELL, "text/html", WALL, 0, 3, "chrome-wall", None),
     {"want_status": WALLED}),
    (("wall-phrase-long-page", LIVE, SHELL, "text/html", page("<p>Fix access denied errors "
      "across every app. %s</p>" % ("Guide text. " * 90)), 0, 0, "chrome", "Fix access denied"), {}),
    (("wall-mark", LIVE, SHELL, "text/html", RENDERED.replace("<body>", "<body><script>"
      "window._cf_chl_opt={}</script>"), 0, 3, "chrome-wall", None), {"want_status": WALLED}),
    (("wall-mark-case", LIVE, SHELL, "text/html", RENDERED.replace("<body>", '<body><script '
      'src="/_Incapsula_Resource?SWJIYLWA=1"></script>'), 0, 3, "chrome-wall", None),
     {"want_status": WALLED}),
    (("wall-mark-in-both", LIVE, SHELL.replace("<body>", "<body><script>window._cf_chl_opt={}"
      "</script>"), "text/html", RENDERED.replace("<body>", "<body><script>window._cf_chl_opt={}"
      "</script>"), 0, 0, "chrome", "The rendered"), {}),
    (("timeout", LIVE, SHELL, "text/html", RENDERED, 0, 0, "chrome-failed", "Open roles"),
     {"env": {"STUB_CHROME_SLEEP": "30", "FETCH_CHROME_TIMEOUT": "1"}, "max_seconds": 10,
      "want_note": "outlived 1 s"}),
    (("escape-hang", LIVE, SHELL, "text/html", RENDERED, 0, 0, "chrome-failed", "Open roles"),
     {"env": {"STUB_ESCAPE_MODE": "hang", "FETCH_CHROME_TIMEOUT": "1"}, "max_seconds": 8,
      "stub": "chrome-escape", "want_note": "outlived 1 s"}),
    (("escape-exit", LIVE, SHELL, "text/html", RENDERED, 0, 0, "chrome-failed", "Open roles"),
     {"env": {"STUB_ESCAPE_MODE": "exit", "FETCH_CHROME_TIMEOUT": "1"}, "max_seconds": 8,
      "stub": "chrome-escape", "want_note": "Chrome exited 1"}),
    (("escape-detach", LIVE, SHELL, "text/html", RENDERED, 0, 0, "chrome-failed", "Open roles"),
     {"env": {"STUB_ESCAPE_MODE": "detach", "FETCH_CHROME_TIMEOUT": "1"}, "max_seconds": 8,
      "stub": "chrome-escape", "want_note": "outlived 1 s"}),
)


def wall_fixture_cases():
    """NET_CASES rows for real Chrome's captures in `walls/` (`wall-server.py`), per `wall-cases.tsv`."""
    with open(os.path.join(FIXTURES, "wall-cases.tsv"), encoding="utf-8") as fh:
        rows = [l.rstrip("\n").split("\t") for l in fh if l.strip() and not l.startswith("#")]
    out = []
    for case, want_exit, method, status, line in rows:
        base = "walls/" + case
        out.append(((case + "-captured", "http://127.0.0.1:8765/" + case, base + ".curl.html",
                     "text/html; charset=utf-8", base + ".dom.html", 0, int(want_exit), method,
                     {"-": None, "(empty)": ""}.get(line, line)),
                    {"net": base + ".netlog.json", "want_status": status}))
    return out


def stub_file(tmp, name, data):
    """`data` is markup, or a fixture filename ending `.html`. Returns a path the stubs can cat."""
    if data.endswith(".html") and "<" not in data:
        return os.path.join(FIXTURES, data)
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(data)
    return path


def make_netlog(tmp, name, chain, one_request=False, damage=None):
    """A net-log in Chrome's shape (numbering from a real capture) holding one main-frame request
    per (url, status) in `chain`, in order, as a script navigation would leave it; or, with
    `one_request`, one request restarted per hop, as an HTTP redirect leaves it. `damage`:
    "truncated" cuts the file in half (a crash), "drifted" renames `request_type`."""
    types = {"URL_REQUEST_START_JOB": 135, "HTTP_TRANSACTION_READ_RESPONSE_HEADERS": 244}
    events = []
    for n, (url, status) in enumerate(chain, 1):
        sid = 1 if one_request else n
        events.append({"type": 135, "source": {"id": sid},
                       "params": {"url": url, "request_type": "main frame", "method": "GET"}})
        events.append({"type": 244, "source": {"id": sid},
                       "params": {"headers": ["HTTP/1.1 %s X" % status, "content-type: text/html"]}})
    # The page's own requests come after, as in any real log: a reader must skip them.
    events.append({"type": 135, "source": {"id": 99},
                   "params": {"url": "https://cdn.invalid/app.js", "request_type": "other"}})
    events.append({"type": 244, "source": {"id": 99}, "params": {"headers": ["HTTP/1.1 200 OK"]}})
    text = json.dumps({"constants": {"logEventTypes": types}, "events": events})
    if damage == "truncated":
        text = text[:len(text) // 2]
    elif damage == "drifted":
        text = text.replace('"request_type"', '"initiator_type"')
    path = os.path.join(tmp, name + ".netlog.json")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def case_render(tmp, stub_dir, name, url, body, ctype, dom, chrome_exit, want_exit, want_method,
                want_txt, net=None, want_status="200", env=None, max_seconds=None,
                one_request=False, stub="chrome", want_note=""):
    """One fetch through the stubs. Chrome runs, sandboxed, only for a live HTML shell, and the
    `methods.tsv` row, exit code, status and `.txt` match the case. `want_txt` None: no `.txt`.
    `net`: a (url, status) chain for the stub's net-log (default: `url` answering 200), a fixture
    path, "none" for no net-log, or "truncated" or "drifted" for a damaged one. A `chrome-failed`
    or `chrome-unverified` case also needs its stderr RENDER line, holding `want_note`."""
    root = os.path.join(tmp, "render-" + name)
    log = root + "-chrome.log"
    want_calls = 0 if want_method == "curl" or stub != "chrome" else 1
    if net == "none":
        netlog = ""
    elif net in ("truncated", "drifted"):
        netlog = make_netlog(tmp, name, [(url, "200")], damage=net)
    elif isinstance(net, str):
        netlog = os.path.join(FIXTURES, net)
    else:
        netlog = make_netlog(tmp, name, net or [(url, "200")], one_request)
    extra = dict({"STUB_STATUS": "200", "STUB_CTYPE": ctype, "STUB_CHROME_LOG": log,
                  "STUB_CHROME_EXIT": str(chrome_exit), "STUB_FINAL_URL": url,
                  "STUB_NETLOG_FILE": netlog, "STUB_ESCAPE_PIDFILE": root + "-escape.pid",
                  "STUB_ELSEWHERE_HANDLER": os.path.join(tmp, "elsewhere", "chrome_crashpad_handler"),
                  "STUB_BODY_FILE": stub_file(tmp, name + ".body", body),
                  "STUB_DOM_FILE": stub_file(tmp, name + ".dom", dom) if dom else ""}, **(env or {}))
    # A reporter already running before the fetch (the user's browser's) must outlive it.
    earlier = None
    if stub == "chrome-escape":
        earlier = subprocess.Popen([sys.executable, os.path.join(stub_dir, "chrome_crashpad_handler")],
                                   start_new_session=True)
    started = time.time()
    proc = run_child(root, [url], path_prefix=stub_dir, chrome=os.path.join(stub_dir, stub),
                     extra=extra)
    elapsed = time.time() - started
    earlier_lived = earlier is None or earlier.poll() is None
    if earlier is not None:
        earlier.kill()
        earlier.wait()
    if (want_method in ("chrome-failed", "chrome-unverified")
            and "RENDER %s %s: " % (want_method, url) not in proc.stderr):
        want_note = "RENDER %s %s: (missing)" % (want_method, url)
    pages = os.path.join(root, "pages")
    rows = index_rows(root) if os.path.exists(os.path.join(pages, "index.tsv")) else [[]]
    methods = []
    if os.path.exists(os.path.join(pages, "methods.tsv")):
        with open(os.path.join(pages, "methods.tsv"), encoding="utf-8") as fh:
            methods = [l.rstrip("\n").split("\t") for l in fh]
    calls = open(log).read().splitlines() if os.path.exists(log) else []
    path = rows[-1][6] if len(rows) == 2 else ""
    txt = ""
    if path and os.path.exists(os.path.join(root, path[:-len(".html")] + ".txt")):
        txt = open(os.path.join(root, path[:-len(".html")] + ".txt"), encoding="utf-8").read()
    kept = [l for l in txt.splitlines()] if txt else []
    ok = (proc.returncode == want_exit and len(methods) == 2 and methods[1][:2] == [path, want_method]
          and methods[1][2] == (str(prose_chars(kept)) if want_txt is not None else "-")
          and len(calls) == want_calls and len(rows) == 2 and rows[1][2] == want_status
          and all("--dump-dom" in c and url in c and "--no-sandbox" not in c
                  and "--virtual-time-budget=10000" in c and "--log-net-log=" in c for c in calls)
          and (txt == "" if want_txt is None else want_txt in txt)
          and (max_seconds is None or elapsed < max_seconds) and want_note in proc.stderr
          and escaped_child_dead(extra["STUB_ESCAPE_PIDFILE"]) and earlier_lived)
    if ok and want_method in ("chrome", "chrome-wall", "chrome-unverified"):
        with open(extra["STUB_DOM_FILE"], "rb") as fh:
            ok = rows[1][4] == hashlib.sha256(fh.read()).hexdigest()
    if ok and want_txt is not None and methods[1][2].isdigit() and int(methods[1][2]) < THIN_CHARS:
        ok = "could not confirm the layer is complete" in proc.stderr
    check("render %s -> %s, exit %d, %d Chrome call(s)" % (name, want_method, want_exit, want_calls),
          ok, "exit %d, methods %r, calls %r, status %r, txt %r, %.1fs, stderr %s"
          % (proc.returncode, methods, calls, rows[-1][2:3], txt[:80], elapsed,
             proc.stderr.strip()[-200:]))


def escaped_child_dead(pidfile):
    """True when no escape stub ran, or the reporter it forked out of the process group is gone
    within 3 s of the fetch returning (a zombie counts: the kill landed), while every bystander
    it listed after the reporter is still alive. The test then ends the bystanders."""
    if not os.path.exists(pidfile):
        return True
    with open(pidfile) as fh:
        pids = [int(p) for p in fh.read().split()]
    if not pids:
        return False
    pid, bystanders = pids[0], pids[1:]
    alive = all(alive_pid(b) for b in bystanders)
    for b in bystanders:
        try:
            os.kill(b, signal.SIGKILL)
        except OSError:
            pass
    if not alive:
        return False
    for _ in range(30):
        if not alive_pid(pid):
            return True
        time.sleep(0.1)
    return False


def alive_pid(pid):
    """The process exists and is not a zombie (a zombie's kill has landed; on Linux a subreaper
    may never reap it). `ps` is not used because a sandboxed run cannot exec it."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    try:
        with open("/proc/%d/stat" % pid) as fh:
            return fh.read().rsplit(")", 1)[1].split()[0] != "Z"
    except (OSError, IndexError):
        return True


def render_fixture_cases():
    """RENDER_CASES rows for the live captures listed in `render-cases.tsv`."""
    with open(os.path.join(FIXTURES, "render-cases.tsv"), encoding="utf-8") as fh:
        rows = [l.rstrip("\n").split("\t") for l in fh if l.strip() and not l.startswith("#")]
    return [(name, LIVE, curl_body, "text/html; charset=utf-8", dom, 0, 0, method, line)
            for name, curl_body, dom, method, line in rows]


def unverified_fixture_cases():
    """Each captured page Chrome wins, replayed with no net-log: the DOM is still kept, as
    `chrome-unverified`, exit 5, never curl's shell saved as a clean exit 0."""
    return [((case[0] + "-no-netlog",) + case[1:6] + (5, "chrome-unverified", case[8]),
             {"net": "none", "want_note": UNREAD})
            for case in render_fixture_cases() if case[7] == "chrome"]


def case_meta():
    markup = ('<head><title>T</title><meta name="Description" content=" A  shell&#39;s text ">'
              '<meta property="og:description" content="Og text">'
              '<meta name="twitter:description" content="Tw"></head><body><p>Body</p></body>')
    got = text_layer(markup.encode())
    want = ["[meta-description] A shell's text [/meta-description]",
            "[og-description] Og text [/og-description]", "Body"]
    check("meta and og descriptions reach the text layer", got == want, "got %r" % got)


def case_lock_held(tmp):
    """Deterministic: this process holds LOCK_EX on the index while a forked child appends. A
    child that finishes inside a second wrote through the lock, so the lock is missing."""
    pages = os.path.join(tmp, "held", "pages")
    os.makedirs(pages)
    with open(os.path.join(pages, "index.tsv"), "a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        pid = os.fork()
        if pid == 0:
            append_index(pages, ("u", "f", "200", "t", "s" * 64, 0, "p"))
            os._exit(0)
        waited, done = 0.0, 0
        while waited < 1.0 and not done:
            done, _ = os.waitpid(pid, os.WNOHANG)
            if not done:
                time.sleep(0.05)
                waited += 0.05
        fcntl.flock(fh, fcntl.LOCK_UN)
    if not done:
        os.waitpid(pid, 0)
    rows = index_rows(os.path.join(tmp, "held"))
    check("a held lock makes a second writer wait", not done and len(rows) == 2,
          "child %s while the lock was held; %d lines after release"
          % ("finished" if done else "waited", len(rows)))


IMG_SHAPES = (  # (markup, stem the text layer must carry), one per image idiom beyond plain `src`
    ('<img src="/_next/image?url=%2Flogos%2Facme-grid.png&w=256">', "acme-grid"),
    ('<img src="data:image/gif;base64,R0lGOD" data-src="/l/acme-lazy.png">', "acme-lazy"),
    ('<img src="/spacer.gif" data-src="/l/acme-deferred.svg">', "acme-deferred"),
    ('<img srcset="/l/acme-set.png 1x, /l/acme-set@2x.png 2x">', "acme-set"),
    ('<img src="data:image/png;base64,iVBORw0KGgo">', ""),
)


def case_img_sources():
    for markup, want in IMG_SHAPES:
        got = text_layer(markup.encode())
        check("image stem %r" % (want or "(data: URI, no stem)"),
              got == ["[img-file]  |  | %s" % want], "got %r" % got)


def case_two_writers(tmp, n=300):
    """Two forked writers append n rows each to a fresh store: one header, 2n whole rows."""
    pages = os.path.join(tmp, "race", "pages")
    os.makedirs(pages)
    pids = []
    for w in range(2):
        pid = os.fork()
        if pid == 0:
            for k in range(n):
                append_index(pages, ("u%d-%d" % (w, k), "f", "200", "t", "s" * 64, k, "p"))
            os._exit(0)
        pids.append(pid)
    for pid in pids:
        os.waitpid(pid, 0)
    with open(os.path.join(pages, "index.tsv"), encoding="utf-8") as fh:
        rows = [l.rstrip("\n").split("\t") for l in fh]
    heads = sum(1 for r in rows if r == list(INDEX_COLUMNS))
    whole = sum(1 for r in rows[1:] if len(r) == len(INDEX_COLUMNS))
    check("two writers: one header, %d whole rows" % (2 * n),
          rows and rows[0] == list(INDEX_COLUMNS) and heads == 1 and whole == 2 * n
          and len(rows) == 2 * n + 1,
          "%d header rows, %d whole rows, %d lines" % (heads, whole, len(rows)))


class BackoffServer:
    """A local HTTP server for the backoff cases, offline: `/flaky` answers 429 with
    `Retry-After: 1` once, then 200; `/always` answers 429 with `Retry-After: 1` every time;
    `/capped` answers 503 with `Retry-After: 120` every time. `hits` counts requests per path."""

    def __init__(self):
        import http.server
        import threading
        hits = self.hits = {}
        prose = page("<p>%s</p>" % ("A served page with enough prose to keep. " * 10)).encode()

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                hits[self.path] = hits.get(self.path, 0) + 1
                if self.path == "/flaky" and hits[self.path] > 1:
                    code, after = 200, None
                else:
                    code, after = {"/flaky": (429, "1"), "/always": (429, "1"),
                                   "/capped": (503, "120")}.get(self.path, (404, None))
                body = prose if code == 200 else b"<p>slow down</p>"
                self.send_response(code)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                if after:
                    self.send_header("Retry-After", after)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.httpd = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.base = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def case_backoff(tmp):
    """Real curl against the local server: a 429 then a 200 is fetched after waiting the
    Retry-After; an always-429 is BLOCKED after MAX_TRIES, having waited its 1 s twice rather than
    the 2 + 4 s default; a 503 asking 120 s waits only the cap."""
    srv = BackoffServer()
    try:
        for name, cap, want_exit, want_hits, want_state, want_status, min_s, max_s in (
                ("flaky", None, 0, 2, "FETCHED", "200", 1.0, 20.0),
                ("always", None, 3, MAX_TRIES, "BLOCKED", "429", 2.0, 5.5),
                ("capped", "1", 3, MAX_TRIES, "BLOCKED", "503", 2.0, 10.0)):
            root = os.path.join(tmp, "backoff-" + name)
            extra = {"FETCH_BACKOFF_CAP": cap} if cap else {}
            start = time.monotonic()
            proc = run_child(root, [srv.base + "/" + name, "--json"], extra=extra)
            took = time.monotonic() - start
            index = os.path.join(root, "pages", "index.tsv")
            rows = index_rows(root) if os.path.exists(index) else []
            try:
                said = json.loads(proc.stdout.strip().splitlines()[-1])
            except (ValueError, IndexError):
                said = {}
            ok = (proc.returncode == want_exit and srv.hits.get("/" + name) == want_hits
                  and len(rows) == 2 and rows[1][2] == want_status and min_s <= took < max_s
                  and said.get("state") == want_state and said.get("tries") == want_hits)
            check("backoff %s: exit %d, %d tries, %s, %.0f-%.0f s"
                  % (name, want_exit, want_hits, want_state, min_s, max_s), ok,
                  "exit %d, hits %r, rows %r, %.1f s, stdout %r, stderr %s"
                  % (proc.returncode, srv.hits, rows[1:], took, proc.stdout, proc.stderr.strip()))
    finally:
        srv.close()


def case_retry_after():
    for label, header, want in (
            ("seconds", "HTTP/1.1 429 x\r\nRetry-After: 7\r\n\r\n", 7.0),
            ("the last response's", "HTTP/1.1 301 x\r\nRetry-After: 9\r\n\r\n"
                                    "HTTP/1.1 503 x\r\nretry-after: 2\r\n\r\n", 2.0),
            ("absent", "HTTP/1.1 429 x\r\n\r\n", None),
            ("a past HTTP-date", "HTTP/1.1 429 x\r\nRetry-After: Wed, 21 Oct 2015 07:28:00 GMT\r\n\r\n", 0.0),
            ("unreadable", "HTTP/1.1 429 x\r\nRetry-After: soon\r\n\r\n", None)):
        got = retry_after(header)
        check("Retry-After %s reads %r" % (label, want), got == want, "got %r" % got)


def selftest():
    lines = text_layer(open(CAPTURE, "rb").read())
    exp = read_expected()
    case_logo_wall(lines, exp)
    case_non_logo(lines, exp)
    with tempfile.TemporaryDirectory(prefix="fetch-selftest-") as tmp:
        case_file_fetch(os.path.join(tmp, "file"), lines)
        stub_dir = make_stub(tmp)
        case_status(tmp, stub_dir, "200", 0)
        for code in ("401", "403", "429", "451", "503", "999"):
            case_status(tmp, stub_dir, code, 3)
        for code in NOT_REACHED_SAMPLES:
            case_status(tmp, stub_dir, code, 4)
        for case in RENDER_CASES + tuple(render_fixture_cases()):
            case_render(tmp, stub_dir, *case)
        for case, overrides in (NET_CASES + tuple(wall_fixture_cases())
                                + tuple(unverified_fixture_cases())):
            case_render(tmp, stub_dir, *case, **overrides)
        check("CHROME_TIMEOUT defaults to 20 s", "FETCH_CHROME_TIMEOUT" in os.environ
              or CHROME_TIMEOUT == 20, "CHROME_TIMEOUT is %r" % CHROME_TIMEOUT)
        case_lock_held(tmp)
        case_two_writers(tmp)
        case_backoff(tmp)
    case_retry_after()
    case_img_sources()
    case_meta()
    if FAILS:
        print("SELFTEST FAIL: %d case(s): %s" % (len(FAILS), "; ".join(FAILS)))
        return 1
    print("SELFTEST OK: all cases")
    return 0


def main(argv):
    if argv == ["--selftest"]:
        return selftest()
    as_json = "--json" in argv[1:]
    argv = argv[:1] + [a for a in argv[1:] if a != "--json"]
    as_url = None
    if len(argv) == 3 and argv[1] == "--as-url":
        as_url = argv[2]
    elif len(argv) != 1 or argv[0].startswith("-"):
        print("usage: fetch.py URL [--as-url ORIGINAL] [--json] | fetch.py --selftest", file=sys.stderr)
        return 2
    brief_root = os.environ.get("BRIEF_ROOT", "")
    if not brief_root:
        print("fetch.py: BRIEF_ROOT is required", file=sys.stderr)
        return 2
    said = {"url": as_url or argv[0], "status": None, "tries": None, "waits": [], "path": None}
    try:
        code = fetch(argv[0], as_url, brief_root, said)
    except RuntimeError as err:
        print("fetch.py: %s: %s" % (argv[0], err), file=sys.stderr)
        code = 1
    if as_json:
        print(json.dumps(dict(said, state=STATES[code], exit=code)))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
