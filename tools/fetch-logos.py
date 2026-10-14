#!/usr/bin/env python3
"""Stage 4's logos: one record per company in $BRIEF_ROOT/logos/logos.json, a gated logo or a
recorded wordmark (`73-web-plan.md` W13). Generalised from T's one-shot script, which typed a
locator for each of seven companies; the stage-4 lead now picks each logo off a list this tool
prints from the company's own saved page.

WHY THIS EXISTS. The page shows each company's logo. A logo found by a search, or typed from
memory, is a fact nobody fetched. A logo here comes only from a page under pages/, and every record
passes brief-check.py's `logo_gate` (the operator, 2026-10-08), imported and restated nowhere: `href` is
in the page's bytes, or for an inline <svg> the logo's bytes are, and `page_sha256` is the page's
pages/index.tsv row. A company with no gated logo gets a wordmark record, and the page sets its
name in type.

MODES.
  fetch-logos.py --find <BRIEF_ROOT> <page_url>        the logo candidates in one saved page
  fetch-logos.py <BRIEF_ROOT> <picks.tsv> [--no-ink]   writes logos/<slug>.<ext> and logos.json
  fetch-logos.py --auto <BRIEF_ROOT> [--no-ink]        picks each logo in code, then as above
  fetch-logos.py --selftest                            offline; reds with the gate dropped

PICKS. A TSV with the header `slug snapshot page_url kind value`, one row per company:
  img       value is a src exactly as --find printed it, verbatim from the page
  svg       value is the byte offset --find printed for an inline <svg>
  wordmark  value says why no logo is used; page_url may be blank
The name comes from snapshots/<snapshot>'s `name`, the owner's own spelling. An img logo is
fetched; one that fails to fetch, or is neither SVG nor PNG, becomes a wordmark record saying why.
A record that fails the gate is a finding, never a quiet wordmark, and a red run leaves no
logos.json behind.

INK. Unless --no-ink, each SVG's ink box is measured in Chrome and written as
logos/<slug>.trim.svg, the root viewBox set to that box: a crop, never a recolour. web.py reads
trim_file, aspect and ink_share where present. A PNG takes its aspect from its header.

AUTO (Globex design § 2 Gap row, find-C F8, find-F F8: a shadowed logo passed every gate). The
companies are reader.json's `company` (the client, from its hosts' home page) and names.json's
rivals (each from its `page_id` page). For each, --find's candidates are tried in rank order and
the first to pass these checks is the pick:
  name   the tag, its inline <svg>'s <title>, or the link wrapping it names the company (its name,
         its name's first word, or its domain's main label, letters and digits compared), or that
         link goes to the site's home page. A customer's logo in the header names someone else.
  pixels (pixel_gate) a PNG's ink box is at least MIN_INK_PX on its short side, the renderer
         drawing a logo about 31 px tall at 2x; an SVG needs no size.
  halo   (pixel_gate) the page draws every logo as a one-colour alpha mask, so a soft drop shadow
         prints as a grey ghost under each letter. A PNG is red when more than HALO_MAX of its
         inked pixels sit in one semi-transparent alpha band (HALO_BAND either side of its peak);
         anti-aliasing spreads over every alpha value, a shadow piles onto one. An SVG is red on
         a <filter>. Measured on the Globex marks: the shadowed source 18.5% (19% semi-transparent),
         its 256 px resample 11%; clean marks 0.1-3.9%, a 128 px resample included.
  ink    (pixel_gate) an SVG is rasterised with PyMuPDF as the page prints it, an image with no
         page CSS, and is red when it draws no ink. An inline <svg> whose site colours it from its
         stylesheet (root `fill="none"`, paths unfilled) prints as nothing; it is never recoloured,
         since the file is verbatim from a fetched page, so the next candidate is tried. The halo
         and soft checks then read the render as they read a PNG.
  soft   (pixel_gate) red when more than SOFT_MAX of the inked pixels lie inside a semi-transparent
         area, semi-transparent SOFT_REACH px out on all four sides: a blurred shadow or a gradient,
         a picture where a mark should be. Anti-aliasing is an edge too thin to count. Measured
         (vandelay run, 2026-10-13): a product illustration picked from a rival's header 15.8%
         as served, 6.9% at 256 px wide; the shadowed Globex source 17.7%; the 21 clean marks
         in the Globex and vandelay run stores and tools/fixtures 0.0%, at most 0.2% when drawn
         64 px tall.
No candidate passing is a wordmark saying why. The picks go to logos/picks.tsv, then picks mode.
Pixels are read, and SVGs rasterised, with PyMuPDF; without it --auto exits 2.

EXIT CODES. 0 every pick has a gated record or a wordmark. 1 findings. 2 bad usage, an unreadable
input, or ink asked for with no Playwright.
"""
import base64
import contextlib
import hashlib
import html
import importlib.util
import io
import json
import pathlib
import re
import shutil
import struct
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tools/fixtures/fetch-logos"
PICK_COLUMNS = ("slug", "snapshot", "page_url", "kind", "value")
KINDS = ("img", "svg", "wordmark")
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
LOGO_WORD = re.compile(rb"logo|brand", re.I)
URL_ATTRS = re.compile(rb'\s(?:src|data-src|data-lazy-src|data-breeze)="([^"]+)"', re.I)
SAVED = ("200", "000")  # fetched, or indexed from a capture (`fetch.py --as-url`)
MIN_INK_PX = 64  # [INFERRED] 2x the tallest logo box the page draws, 31.5 CSS px (logo-audit)
HALO_MAX = 0.06  # [INFERRED] between clean marks (at most 0.039) and the shadowed (0.11 and up)
HALO_BAND = 4  # alpha levels either side of the peak, the width of one shadow's plateau
INK_ALPHA = 9  # alpha at or above which a pixel is ink, as ink_boxes() reads it (> 8)
SVG_PX = 1200  # an SVG's ink box is rasterised this long on its long side
SOFT_MAX = 0.02  # [INFERRED] clean marks at most 0.002 from 64 px tall up; the illustration 0.069 at 256 px wide
SOFT_REACH = 3  # px; anti-aliasing is an edge one or two pixels wide, so it never reaches this far
SEMI = bytes(INK_ALPHA <= v < 247 for v in range(256))  # 1 for an inked, semi-transparent alpha


def _brief_check():
    spec = importlib.util.spec_from_file_location("brief_check", ROOT / "tools/brief-check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BC = _brief_check()  # logo_gate and LOGOS_JSON, written once there
LOGOS_JSON = BC.LOGOS_JSON


def sha(data):
    return hashlib.sha256(data).hexdigest()


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh) competitor-intel"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read()


def page_row(root, page_url):
    """The saved page for page_url: its index row by url or final_url, fetched or captured."""
    rows = [r for r in BC.CC.read_index(root / "pages")
            if page_url and page_url in (r.get("url"), r.get("final_url")) and r.get("status") in SAVED]
    return rows[-1] if rows else None


def candidates(data):
    """Each <img> and inline <svg> that reads as a logo: inside a <header> or <nav>, or with `logo`
    or `brand` in its tag or the 300 bytes before it. A tag naming logo or brand comes first, then
    header and nav, then page order."""
    zones = [m.span() for m in re.finditer(rb"<(header|nav)\b.*?</\1\s*>", data, re.I | re.S)]
    out = []
    for m in re.finditer(rb"<img\b[^>]*>|<svg\b[^>]*>", data, re.I):
        at = m.start()
        zone = any(a <= at < b for a, b in zones)
        if not (zone or LOGO_WORD.search(data[max(0, at - 300):m.end()])):
            continue
        rank = (not LOGO_WORD.search(m.group(0)), not zone)
        tag = re.sub(rb"\s+", b" ", m.group(0))[:160].decode("utf-8", "replace")
        if m.group(0)[:4].lower() == b"<img":
            out += [(rank, "img", u.decode("utf-8", "replace"), tag)
                    for u in URL_ATTRS.findall(m.group(0)) if not u.startswith(b"data:")]
        else:
            out.append((rank, "svg", str(at), tag))
    return [c[1:] for c in sorted(out, key=lambda c: c[0])]


def image_format(raw):
    if raw.startswith(b"\x89PNG\r\n\x1a\n") and raw[12:16] == b"IHDR":
        return "png"
    return "svg" if re.search(rb"<svg\b", raw[:4096]) and not re.search(rb"<html\b", raw[:4096], re.I) else None


def root_tag(svg):
    return re.search(r"<svg\b[^>]*>", svg).group(0)


def with_root(svg, **attrs):
    """The same file with root attributes set (None drops one). Only the root tag changes."""
    tag = root_tag(svg)
    new = tag
    for k, v in attrs.items():
        new = re.sub(rf'\s{k}="[^"]*"', "", new)
        if v is not None:
            new = new.replace("<svg", f'<svg {k}="{v}"', 1)
    if "xmlns=" not in new:
        new = new.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    return svg.replace(tag, new, 1)


def ink_boxes(svgs):
    """T's measure, unchanged: each SVG's ink box in its own viewBox units and the share of that box
    its ink covers, from Chrome's rendering at 2400px. None for a file with no viewBox or no ink."""
    from playwright.sync_api import sync_playwright
    js = """async (src) => { const i = new Image(); i.src = src; await i.decode();
      const c = new OffscreenCanvas(i.naturalWidth, i.naturalHeight), g = c.getContext('2d');
      g.drawImage(i, 0, 0); const d = g.getImageData(0, 0, c.width, c.height).data;
      let x0 = 1e9, y0 = 1e9, x1 = -1, y1 = -1;
      for (let y = 0; y < c.height; y++) for (let x = 0; x < c.width; x++)
        if (d[(y * c.width + x) * 4 + 3] > 8) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }
      if (x1 < 0) return null; let ink = 0;
      for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) ink += d[(y * c.width + x) * 4 + 3] / 255;
      return [x0, y0, x1 + 1, y1 + 1, ink / ((x1 - x0 + 1) * (y1 - y0 + 1))]; }"""
    out = []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        pg = b.new_page()
        pg.set_content("<!doctype html><title>ink</title>")
        for s in svgs:
            vb = re.search(r'viewBox="([^"]+)"', root_tag(s))
            if not vb:
                out.append(None)
                continue
            vx, vy, vw, vh = map(float, vb.group(1).replace(",", " ").split())
            k = 2400 / max(vw, vh)
            probe = with_root(s, width=f"{vw * k:.0f}", height=f"{vh * k:.0f}")
            got = pg.evaluate(js, "data:image/svg+xml;base64," + base64.b64encode(probe.encode()).decode())
            if not got:
                out.append(None)
                continue
            x0, y0, x1, y1, ink = got
            out.append(([round(vx + x0 / k, 2), round(vy + y0 / k, 2), round((x1 - x0) / k, 2),
                         round((y1 - y0) / k, 2)], round(ink, 3)))
        b.close()
    return out


def wordmark(rec, reason):
    rec.update(kind="wordmark", file=None, reason=reason)
    return rec


def build(root, pick, fetch, findings):
    """One pick to one record, writing its logo file; None, with a finding, for a bad pick."""
    slug, snap, page_url, kind, value = (pick[c] for c in PICK_COLUMNS)
    try:
        name = json.loads((root / "snapshots" / snap).read_text(encoding="utf-8"))["name"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        findings.append("%s: no snapshot name in snapshots/%s (%s)" % (slug, snap, exc))
        return None
    rec = {"company": name, "slug": slug, "snapshot": snap, "page_url": page_url or None}
    if kind == "wordmark":
        return wordmark(rec, value)
    row = page_row(root, page_url)
    if row is None:
        findings.append("%s: %r is no saved page in pages/index.tsv; a logo comes from a page this run "
                        "fetched, never a search" % (slug, page_url))
        return None
    data = (root / row["path"]).read_bytes()
    rec.update(page_file=row["path"], page_sha256=row["sha256"])
    if kind == "svg":
        at = int(value) if value.isdigit() else -1
        end = data.find(b"</svg>", at) if at >= 0 and data[at:at + 4].lower() == b"<svg" else -1
        if end < 0 or data.count(b"<svg", at + 4, end):
            findings.append("%s: offset %r in %s opens no single inline <svg>; take it from --find"
                            % (slug, value, row["path"]))
            return None
        raw = data[at:end + len(b"</svg>")]
        rec.update(kind="svg", href=None, resolved_url=None, status=None, fetched_at=None)
    else:
        base = row["final_url"] if row["final_url"].startswith("http") else row["url"]
        resolved = urljoin(base, html.unescape(value))  # as a browser resolves the attribute
        try:
            status, raw = fetch(resolved)
        except Exception as exc:  # any failure to fetch leaves the company a wordmark, saying why
            return wordmark(rec, "fetching %s failed: %s" % (resolved, exc))
        if image_format(raw) is None:
            return wordmark(rec, "%s is neither SVG nor PNG" % resolved)
        rec.update(kind="img", href=value, resolved_url=resolved, status=status,
                   fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    fmt = image_format(raw) or "svg"
    rec.update(file="logos/%s.%s" % (slug, fmt), bytes=len(raw), sha256=sha(raw), format=fmt)
    (root / rec["file"]).write_bytes(raw)
    if fmt == "png":
        w, h = struct.unpack(">II", raw[16:24])
        rec["aspect"] = round(w / h, 3)
    return rec


def read_picks(path):
    lines = [ln for ln in path.read_text(encoding="utf-8").split("\n") if ln.strip()]
    if not lines or tuple(lines[0].split("\t")) != PICK_COLUMNS:
        raise ValueError("%s does not open with the header %s" % (path, "\\t".join(PICK_COLUMNS)))
    return [dict(zip(PICK_COLUMNS, ln.split("\t") + [""] * 5)) for ln in lines[1:]]


def run(root, picks_path, ink=True, fetch=None, out=sys.stdout):
    """Every pick to logos.json. Returns the exit code."""
    root, fetch = pathlib.Path(root), fetch or http_get  # read at call time, so the selftest can swap it
    try:
        picks = read_picks(pathlib.Path(picks_path))
    except (OSError, ValueError) as exc:
        sys.stderr.write("FAIL: %s\n" % exc)
        return 2
    findings, records, seen = [], [], set()
    (root / "logos").mkdir(exist_ok=True)
    for p in picks:
        if not SLUG_RE.match(p["slug"]) or p["slug"] in seen or p["kind"] not in KINDS:
            findings.append("%s: a slug off the pattern, a second row for one slug, or a kind other than "
                            "%s" % (p["slug"] or "<blank>", "/".join(KINDS)))
            continue
        seen.add(p["slug"])
        rec = build(root, p, fetch, findings)
        if rec is not None:
            records.append(rec)
    for rec in records:
        if rec["file"]:
            findings += ["%s: not gated: %s" % (rec["slug"], f) for f in BC.logo_gate(rec, root)]
    target = root / LOGOS_JSON
    if findings:
        for f in findings:
            sys.stderr.write("FAIL: %s\n" % f)
        if target.exists():
            target.unlink()  # a stale logos.json must not outlive a red run
        sys.stderr.write("LOGOS RED (%d finding%s; no %s written)\n"
                         % (len(findings), "" if len(findings) == 1 else "s", LOGOS_JSON))
        return 1
    svg_recs = [r for r in records if r["file"] and r["format"] == "svg"]
    if ink and svg_recs:
        try:
            boxes = ink_boxes([(root / r["file"]).read_text(encoding="utf-8") for r in svg_recs])
        except ImportError:
            sys.stderr.write("FAIL: ink needs Playwright and Chrome; pass --no-ink to skip the crop\n")
            return 2
        for rec, got in zip(svg_recs, boxes):
            if got is None:
                continue
            box, share = got
            svg = (root / rec["file"]).read_text(encoding="utf-8")
            trim = with_root(svg, viewBox=" ".join(map(str, box)), width=None, height=None)
            rec["trim_file"] = "logos/%s.trim.svg" % rec["slug"]
            (root / rec["trim_file"]).write_text(trim, encoding="utf-8")
            rec.update(trim_sha256=sha(trim.encode()), ink_box=box, aspect=round(box[2] / box[3], 3),
                       ink_share=share)
    target.write_text(json.dumps(records, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for rec in records:
        out.write("GATED    %-16s %-4s %s\n" % (rec["slug"], rec["kind"], rec["file"]) if rec["file"]
                  else "WORDMARK %-16s %s\n" % (rec["slug"], rec["reason"]))
    out.write("LOGOS OK (%d records, %d wordmark, in %s)\n"
              % (len(records), sum(not r["file"] for r in records), target))
    return 0


def find(root, page_url, out=sys.stdout):
    row = page_row(pathlib.Path(root), page_url)
    if row is None:
        sys.stderr.write("FAIL: %r is no saved page in %s/pages/index.tsv\n" % (page_url, root))
        return 1
    found = candidates((pathlib.Path(root) / row["path"]).read_bytes())
    out.write("# %d candidates in %s; copy kind and value into picks.tsv\n" % (len(found), row["path"]))
    for kind, value, tag in found:
        out.write("%s\t%s\t%s\n" % (kind, value, tag))
    return 0


# --- auto ----------------------------------------------------------------------------------------
def ink_extent(a, w, h):
    """The ink box (x0, y0, x1, y1) of an alpha plane, pixels at INK_ALPHA and up; None for no ink."""
    clear = bytes(range(INK_ALPHA))
    rows = [y for y in range(h) if a[y * w:(y + 1) * w].strip(clear)]
    if not rows:
        return None
    cols = [(len(r) - len(r.lstrip(clear)), len(r.rstrip(clear))) for r in (a[y * w:(y + 1) * w] for y in rows)]
    return min(s for s, _ in cols), rows[0], max(e for _, e in cols), rows[-1] + 1


def svg_pixmap(raw):
    """The SVG as the page prints it, an image with no page CSS (the root gets an xmlns, as the trim
    does), rasterised by PyMuPDF with its ink box SVG_PX on the long side. (pixmap, None), or (None,
    why) when it does not render."""
    import fitz
    try:
        page = fitz.open(stream=with_root(raw.decode("utf-8", "replace")).encode("utf-8"), filetype="svg")[0]
        r = page.rect
        k = SVG_PX / max(r.width, r.height)
        pm = page.get_pixmap(alpha=True, matrix=fitz.Matrix(k, k))
        box = ink_extent(pm.samples[pm.n - 1::pm.n], pm.width, pm.height)
        if box is None:
            return pm, None
        clip = fitz.Rect(r.x0 + box[0] / k, r.y0 + box[1] / k, r.x0 + box[2] / k, r.y0 + box[3] / k)
        k = SVG_PX / max(clip.width, clip.height)
        return page.get_pixmap(alpha=True, matrix=fitz.Matrix(k, k), clip=clip), None
    except (RuntimeError, ValueError, AttributeError, ZeroDivisionError) as exc:  # fitz's errors subclass RuntimeError
        return None, "the SVG does not render offline (%s)" % exc


def pixel_gate(raw, fmt):
    """Why a logo file fails the ink, pixel-size, halo and soft-area gates; [] when it passes. Pixels
    are read with PyMuPDF, an SVG rasterised by it."""
    import fitz  # PyMuPDF; ImportError is the caller's exit 2
    if fmt == "svg":
        if re.search(rb"<filter\b", raw, re.I):
            return ["the SVG draws a <filter> (a shadow or blur the mask prints as a ghost)"]
        pm, why = svg_pixmap(raw)
        if pm is None:
            return [why]
    else:
        pm = fitz.Pixmap(raw)
    w, h = pm.width, pm.height
    if pm.alpha:
        a = pm.samples[pm.n - 1::pm.n]
        hist = [a.count(bytes([v])) for v in range(256)]
        ink = sum(hist[INK_ALPHA:])
        at = ink_extent(a, w, h)
        box = (at[2] - at[0], at[3] - at[1]) if at else (0, 0)
        lo, hi = INK_ALPHA + HALO_BAND, 250 - HALO_BAND
        peak = max(range(lo, hi), key=lambda v: sum(hist[v - HALO_BAND:v + HALO_BAND + 1]))
        band = sum(hist[peak - HALO_BAND:peak + HALO_BAND + 1]) / ink if ink else 0.0
        # A semi-transparent pixel with semi-transparent pixels SOFT_REACH px out on all four sides.
        m = int.from_bytes(a.translate(SEMI), "little")
        d, row = 8 * SOFT_REACH, 8 * SOFT_REACH * w
        soft = (m & m >> d & m << d & m >> row & m << row).bit_count() / ink if ink else 0.0
    else:
        box, band, peak, soft = (w, h), 0.0, None, 0.0
    if fmt == "svg" and box == (0, 0):
        return ["no ink: the SVG draws nothing visible as an image, without the page's CSS (a fill of "
                "none, or a colour the site's stylesheet sets); recolouring it would alter a fetched file"]
    out = []
    if fmt != "svg" and min(box) < MIN_INK_PX:
        out.append("ink box %dx%d px, under %d px on its short side" % (box[0], box[1], MIN_INK_PX))
    if band > HALO_MAX:
        out.append("halo: %.1f%% of inked pixels sit at alpha %d±%d, over %.0f%% (a soft shadow the "
                   "mask prints as a ghost)" % (band * 100, peak, HALO_BAND, HALO_MAX * 100))
    if soft > SOFT_MAX:
        out.append("soft: %.1f%% of inked pixels lie inside semi-transparent areas, over %.0f%% (a blurred "
                   "shadow or gradient, a picture rather than a mark)" % (soft * 100, SOFT_MAX * 100))
    return out


def alnum(text):
    return re.sub(r"[^a-z0-9]", "", html.unescape(text).lower())


def name_tokens(name, domain):
    toks = {alnum(name)}
    first = alnum(re.split(r"[\s.]", name.strip())[0]) if name.strip() else ""
    if len(first) >= 4:
        toks.add(first)
    labels = [x for x in (domain or "").lower().split(".")[:-1] if x != "www"]
    if labels:
        main = max(labels, key=len)
        if len(main) >= 4:
            toks.add(alnum(main))
    return {t for t in toks if t}


NAME_ATTRS = re.compile(rb'\s(alt|title|aria-label|class|id|src|data-src|href)="([^"]*)"', re.I)


def names_in(tag, tokens):
    """True when one tag names the company. Its words (alt, title, aria-label) must open on a
    token: "Twirl Logo" names Twirl, "A customer on Twirl" does not. Its labels (class, id) and a
    src or href by its path alone (a self-link's host is the company's own domain) need only hold
    one: "wordmark_creator.svg"."""
    for key, val in NAME_ATTRS.findall(tag):
        key, val = key.lower(), html.unescape(val.decode("utf-8", "replace"))
        if key in (b"alt", b"title", b"aria-label"):
            if any(alnum(val).startswith(t) for t in tokens):
                return True
        elif any(t in alnum(urlparse(val).path if key in (b"src", b"data-src", b"href") else val) for t in tokens):
            return True
    return False


def owns(data, at, end, tokens, base):
    """True when the candidate at data[at:end] names the company or links to the site's home."""
    tag = data[at:end]
    named = names_in(tag, tokens)
    if tag[:4].lower() == b"<svg":
        close = data.find(b"</svg>", at)
        title = re.search(rb"<title[^>]*>(.*?)</title>", data[at:close if close > 0 else end], re.I | re.S)
        if title:
            named = named or any(alnum(title.group(1).decode("utf-8", "replace")).startswith(t) for t in tokens)
    opens = [m for m in re.finditer(rb"<a\b[^>]*>", data[max(0, at - 600):at], re.I)]
    home = False
    if opens and b"</a" not in data[max(0, at - 600) + opens[-1].end():at].lower():
        link = opens[-1].group(0)
        named = named or names_in(link, tokens)
        href = re.search(rb'\shref="([^"]*)"', link, re.I)
        if href:
            u = urlparse(urljoin(base, html.unescape(href.group(1).decode("utf-8", "replace"))))
            home = u.path in ("", "/") and u.hostname == urlparse(base).hostname
    return home or named


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def auto_companies(root):
    """[(slug, name, domain, index row)] for the client, then names.json's rivals."""
    rows = [r for r in BC.CC.read_index(root / "pages") if r.get("status") in SAVED]
    reader = json.loads((root / "reader.json").read_text(encoding="utf-8"))
    comp = reader["company"]
    # The home page as fetched or as landed: prefetch asks for http://<host>, which redirects, so
    # url alone missed vandelay.so's home page and left the client a wordmark (2026-10-13).
    home = {"%s://%s%s" % (s, h, p) for h in comp.get("hosts") or [comp["domain"]]
            for s in ("https", "http") for p in ("/", "")}
    client = [r for r in rows if r.get("url") in home or r.get("final_url") in home]
    out = [(slugify(comp["name"]), comp["name"], comp["domain"], client[-1] if client else None)]
    names = json.loads((root / "names.json").read_text(encoding="utf-8")) if (root / "names.json").is_file() else []
    for e in names:
        page = [r for r in rows if pathlib.Path(r.get("path", "")).stem == e.get("page_id")]
        out.append((e["slug"], e["name"], e["domain"], page[-1] if page else None))
    return out


def snapshot_for(root, domain):
    direct = root / "snapshots" / (domain + ".json")
    if direct.is_file():
        return direct.name
    for snap in sorted((root / "snapshots").glob("*.json")):
        try:
            if json.loads(snap.read_text(encoding="utf-8")).get("domain") == domain:
                return snap.name
        except (OSError, ValueError, AttributeError):
            continue
    return domain + ".json"


def auto_pick(root, slug, name, domain, row, fetch, tries=5):
    """One picks.tsv row (a dict) and the reasons each tried candidate failed."""
    snap = snapshot_for(root, domain)
    if row is None:
        return dict(slug=slug, snapshot=snap, page_url="", kind="wordmark",
                    value="auto: no saved home page for %s" % domain), []
    data = (root / row["path"]).read_bytes()
    base = row["final_url"] if row["final_url"].startswith("http") else row["url"]
    tokens, why, tried = name_tokens(name, domain), [], set()
    for kind, value, _ in candidates(data):
        if (kind, value) in tried or len(tried) >= tries:
            continue
        if kind == "svg":
            at = int(value)
            end = data.find(b">", at) + 1
            close = data.find(b"</svg>", at)
            if close < 0 or data.count(b"<svg", at + 4, close):
                continue
        else:
            m = re.search(rb'(src|data-src|data-lazy-src|data-breeze)="' + re.escape(value.encode()) + b'"', data)
            if not m:
                continue
            at = data.rfind(b"<img", 0, m.start())
            end = data.find(b">", m.end()) + 1
        if not owns(data, at, end, tokens, base):
            continue
        tried.add((kind, value))
        if kind == "svg":
            raw, fmt = data[at:close + len(b"</svg>")], "svg"
        else:
            url = urljoin(base, html.unescape(value))
            try:
                _, raw = fetch(url)
            except Exception as exc:  # a fetch that fails moves on to the next candidate
                why.append("%s: fetch failed (%s)" % (value, exc))
                continue
            fmt = image_format(raw)
            if fmt is None:
                why.append("%s: neither SVG nor PNG" % value)
                continue
        failed = pixel_gate(raw, fmt)
        if failed:
            why.append("%s: %s" % (value if kind == "img" else "svg@" + value, "; ".join(failed)))
            continue
        return dict(slug=slug, snapshot=snap, page_url=row["url"], kind=kind, value=value), why
    reason = "auto: no candidate on %s naming %s passed" % (row["url"], name)
    return dict(slug=slug, snapshot=snap, page_url=row["url"], kind="wordmark",
                value=(reason + ": " + " | ".join(why))[:400] if why else reason), why


def auto(root, ink=True, fetch=None, out=sys.stdout):
    """Picks every company's logo in code, writes logos/picks.tsv, then runs picks mode."""
    root, fetch = pathlib.Path(root), fetch or http_get
    cache = {}

    def cached(url):
        if url not in cache:
            cache[url] = fetch(url)
        return cache[url]
    try:
        companies = auto_companies(root)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        sys.stderr.write("FAIL: --auto needs reader.json (and names.json for rivals): %s\n" % exc)
        return 2
    picks = []
    try:
        for slug, name, domain, row in companies:
            pick, why = auto_pick(root, slug, name, domain, row, cached)
            for w in why:
                out.write("REJECT   %-16s %s\n" % (slug, w))
            picks.append(pick)
    except ImportError:
        sys.stderr.write("FAIL: --auto reads PNG pixels with PyMuPDF (pip install pymupdf)\n")
        return 2
    (root / "logos").mkdir(exist_ok=True)
    path = root / "logos/picks.tsv"
    path.write_text("\t".join(PICK_COLUMNS) + "\n" + "".join(
        "\t".join(p[c].replace("\t", " ") for c in PICK_COLUMNS) + "\n" for p in picks), encoding="utf-8")
    return run(root, path, ink=ink, fetch=cached, out=out)


USAGE = ("usage: fetch-logos.py --find <BRIEF_ROOT> <page_url>\n"
         "       fetch-logos.py <BRIEF_ROOT> <picks.tsv> [--no-ink]\n"
         "       fetch-logos.py --auto <BRIEF_ROOT> [--no-ink]\n"
         "       fetch-logos.py --selftest\n")


def main(argv):
    args = argv[1:]
    if args == ["--selftest"]:
        return selftest()
    if len(args) == 3 and args[0] == "--find":
        return find(args[1], args[2])
    ink = "--no-ink" not in args
    args = [a for a in args if a != "--no-ink"]
    if len(args) == 2 and args[0] == "--auto":
        if not (pathlib.Path(args[1]) / "pages/index.tsv").is_file():
            sys.stderr.write(USAGE)
            return 2
        return auto(args[1], ink=ink)
    if len(args) != 2 or args[0].startswith("-") or not (pathlib.Path(args[0]) / "pages/index.tsv").is_file():
        sys.stderr.write(USAGE)
        return 2
    return run(args[0], args[1], ink=ink)


# --- selftest -------------------------------------------------------------------------------------
# The green base is tools/fixtures/fetch-logos/: a run root (three saved pages, four snapshots),
# picks.tsv (one img, one inline svg, one PNG img, one wordmark) and served/, the bytes a stub
# fetcher returns by resolved URL. The real fetcher is never called: every case counts the stub's
# calls, and http_get is swapped for a function that fails the case if reached.
SERVED = {"https://alpha.example/img/alpha-logo.svg?v=2&w=120": "alpha-logo.svg",
          "https://alpha.example/img/alpha-logo-v3.svg": "alpha-logo.svg",
          "https://cdn.gamma.example/logo.png": "logo.png"}


def _pick(who, **cols):
    def fn(text):
        lines = text.split("\n")
        head = lines[0].split("\t")
        for k, ln in enumerate(lines):
            cells = ln.split("\t")
            if cells[0] == who:
                for col, val in cols.items():
                    cells[head.index(col)] = val
                lines[k] = "\t".join(cells)
        return "\n".join(lines)
    return fn


def _touch_page(slug):
    def fn(root):
        path = next(root.glob("pages/%s.example-*.html" % slug))
        path.write_bytes(path.read_bytes() + b" ")
    return fn


RED_CASES = [  # (label, picks edit, root edit, text the finding must hold)
    ("an href not in its page (the substring gate)", _pick("alpha", value="/img/alpha-logo-v3.svg"), None,
     "is not in page_file's bytes"),
    ("a page the run never saved", _pick("alpha", page_url="https://alpha.example/brand"), None,
     "no saved page"),
    ("an svg offset at no <svg>", _pick("beta", value="0"), None, "opens no single inline <svg>"),
    ("a snapshot that does not exist", _pick("gamma", snapshot="nobody.json"), None, "no snapshot name"),
    ("two rows, one slug", _pick("delta", slug="alpha"), None, "a second row for one slug"),
    ("a slug off the pattern", _pick("delta", slug="Delta_Loads"), None, "a slug off the pattern"),
    ("inline bytes under a changed page (the sha256 half)", None, _touch_page("beta"),
     "no longer hash to page_sha256"),
]


def selftest():
    global http_get
    fails, calls, count = [], [], {"red": 0, "green": 0}

    def unreached(url):
        fails.append("the real fetcher was reached for %s" % url)
        raise OSError("offline")

    def stub(served):
        def fetch(url):
            calls.append(url)
            if url not in served:
                raise OSError("404 from the stub")
            got = served[url]
            return 200, got if isinstance(got, bytes) else (FIXTURE / "served" / got).read_bytes()
        return fetch

    def case(picks_fn=None, root_fn=None, served=SERVED, stale=False):
        with tempfile.TemporaryDirectory() as tmp:
            root, picks = pathlib.Path(tmp) / "run", pathlib.Path(tmp) / "picks.tsv"
            shutil.copytree(FIXTURE / "run", root)
            text = (FIXTURE / "picks.tsv").read_text(encoding="utf-8")
            picks.write_text(picks_fn(text) if picks_fn else text, encoding="utf-8")
            if root_fn:
                root_fn(root)
            if stale:
                (root / "logos").mkdir()
                (root / LOGOS_JSON).write_text("[]\n")
            err, out = io.StringIO(), io.StringIO()
            with contextlib.redirect_stderr(err):
                code = run(root, picks, ink=False, fetch=stub(served), out=out)
            path = root / LOGOS_JSON
            recs = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
            gates = [BC.logo_gate(r, root) for r in recs or [] if r["file"]]
            return code, err.getvalue() + out.getvalue(), recs, gates

    def verdict(kind, label, ok, got):
        if ok:
            count[kind] += 1
            sys.stdout.write("SELFTEST %-5s OK  %s\n" % (kind, label))
        else:
            fails.append("%s case %r: got %s" % (kind, label, got))

    http_get = unreached
    code, said, recs, gates = case()
    kinds = [(r["slug"], r["kind"], r.get("format")) for r in recs or []]
    want = [("alpha", "img", "svg"), ("beta", "svg", "svg"), ("gamma", "img", "png"), ("delta", "wordmark", None)]
    verdict("green", "the committed picks: img, inline svg, PNG img, wordmark",
            code == 0 and kinds == want and gates == [[], [], []] and recs[3]["file"] is None
            and recs[2]["company"] == "Gämma" and recs[2]["aspect"] == 3.0 and len(calls) == 2, (code, said, kinds))
    n = len(calls)
    code, said, recs, _ = case(served={k: v for k, v in SERVED.items() if "gamma" not in k})
    verdict("green", "a fetch that fails becomes a wordmark saying why",
            code == 0 and recs[2]["kind"] == "wordmark" and "failed" in recs[2]["reason"] and len(calls) == n + 2,
            (code, said))
    code, said, recs, _ = case(served=dict(SERVED, **{"https://cdn.gamma.example/logo.png": b"<html>no</html>"}))
    verdict("green", "a file neither SVG nor PNG becomes a wordmark",
            code == 0 and "neither SVG nor PNG" in recs[2]["reason"], (code, said))
    for label, picks_fn, root_fn, needle in RED_CASES:
        code, said, recs, _ = case(picks_fn, root_fn, stale=True)
        verdict("red", label, code == 1 and needle in said and recs is None, (code, said))
    for url, want in (("https://alpha.example/", "img\t/img/alpha-logo.svg?v=2&amp;w=120\t"),
                      ("https://beta.example/", "svg\t%s\t" % _pick_value("beta"))):
        out = io.StringIO()
        code = find(FIXTURE / "run", url, out=out)
        first = out.getvalue().split("\n")[1] if code == 0 else ""
        verdict("green", "--find lists %s's logo first" % url, first.startswith(want), out.getvalue())
    with contextlib.redirect_stderr(io.StringIO()):
        codes = (main(["fetch-logos.py"]), main(["fetch-logos.py", str(FIXTURE / "run"), "/no/such.tsv", "--no-ink"]))
    verdict("red", "bad usage and an unreadable picks file exit 2", codes == (2, 2), codes)
    auto_selftest(verdict, unreached)
    http_get = globals()["_http_get"]
    for f in fails:
        sys.stderr.write("SELFTEST FAIL: %s\n" % f)
    if fails:
        sys.stderr.write("SELFTEST RED (%d failure%s)\n" % (len(fails), "" if len(fails) == 1 else "s"))
        return 1
    sys.stdout.write("SELFTEST OK (%d red, %d green; the stub served %d fetches)\n"
                     % (count["red"], count["green"], len(calls)))
    return 0


# --auto's cases. The shadowed fixture is the Globex instance (find-C F8, find-F F8): the run store's
# logos/globex.png, the client's own `logo_transparent.png`, whose alpha-87 drop shadow the page's
# one-colour mask printed as a grey ghost after every gate had passed it.
SHADOWED = FIXTURE / "shadowed/globex-logo-transparent.png"
# Two vandelay picks (2026-10-13) that passed every gate and shipped: the rival's inline <svg>, its
# root `fill="none"` and its paths unfilled, coloured by the site's stylesheet, so it drew nothing on
# our page; and a 3168 x 1440 product illustration (dark cards under blurred shadows) that sat by
# the rival's name in its header.
INKLESS = FIXTURE / "vandelay/tollbit.svg"
SCREENSHOT = FIXTURE / "vandelay/profound.png"


def png(w, h, ink=None):
    """An RGBA PNG, w x h, transparent but for an opaque black box `ink` (x0, y0, x1, y1)."""
    import zlib
    x0, y0, x1, y1 = ink or (0, 0, w, h)
    rows = b"".join(b"\x00" + b"".join(b"\x00\x00\x00\xff" if x0 <= x < x1 and y0 <= y < y1 else b"\x00" * 4
                                       for x in range(w)) for y in range(h))
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


AUTO_PAGES = {  # host -> (company name, home page body)
    "acme.example": ("Acme Grid", '<header><img class="logo" src="/img/client-bolt.png" alt="Bolt Foods">'
                                  '<a href="/"><img src="/img/acme.png" alt="Acme Grid"></a></header>'),
    "shade.example": ("Shade", '<header><img class="logo" src="/shade-logo.png" alt="Shade"></header>'),
    "tiny.example": ("Tiny", '<header><img class="logo" src="/tiny.png" alt="Tiny"></header>'),
    "vector.example": ("Vector Co", '<nav><a href="/" aria-label="Home"><svg class="logo" viewBox="0 0 30 10">'
                                    '<path d="M0 0h30v10H0z"/></svg></a></nav>'),
    "blur.example": ("Blur", '<nav><svg class="logo" viewBox="0 0 30 10"><title>Blur</title><filter id="s">'
                             '<feDropShadow dx="1" dy="1"/></filter><path d="M0 0h30v10H0z"/></svg></nav>'),
    "plain.example": ("Plain", "<main><p>No mark on this page.</p></main>"),
    "hollow.example": ("Hollow", '<nav><a href="/">@INKLESS@</a><a href="/"><img src="/hollow.png" alt="Hollow">'
                                 '</a></nav>'),
    "glossy.example": ("Glossy", '<header><img class="logo" src="/glossy-hero.png" alt="Glossy"></header>'),
}


def auto_root(tmp):
    root = pathlib.Path(tmp) / "auto"
    (root / "pages").mkdir(parents=True)
    (root / "snapshots").mkdir()
    index = ["\t".join(("url", "final_url", "status", "fetched_at", "sha256", "bytes", "path"))]
    names = []
    for host, (name, body) in AUTO_PAGES.items():
        body = body.replace("@INKLESS@", INKLESS.read_text(encoding="utf-8"))
        data = ("<!doctype html><html><head><title>%s</title></head><body>%s</body></html>" % (name, body)).encode()
        path = "pages/%s-%s.html" % (host, sha(data)[:8])
        (root / path).write_bytes(data)
        # The client's row as prefetch writes it: asked as http://<host>, landed on https (vandelay).
        asked = "http://%s" % host if host == "acme.example" else "https://%s/" % host
        index.append("\t".join((asked, "https://%s/" % host, "200", "2026-10-13T09:00:00Z",
                                sha(data), str(len(data)), path)))
        (root / "snapshots" / (host + ".json")).write_text(json.dumps({"domain": host, "name": name}))
        if host != "acme.example":
            names.append({"slug": slugify(name), "name": name, "domain": host, "page_id": pathlib.Path(path).stem})
    (root / "pages/index.tsv").write_text("\n".join(index) + "\n")
    (root / "names.json").write_text(json.dumps(names))
    (root / "reader.json").write_text(json.dumps({"company": {"name": "Acme Grid", "domain": "acme.example",
                                                              "hosts": ["acme.example"]}}))
    return root


def auto_selftest(verdict, unreached):
    """--auto, offline: a stub fetcher serves the images; the real one fails the case if reached."""
    served = {"https://acme.example/img/client-bolt.png": png(300, 100, (10, 10, 290, 90)),
              "https://acme.example/img/acme.png": png(300, 100, (10, 10, 290, 90)),
              "https://shade.example/shade-logo.png": SHADOWED.read_bytes(),
              "https://tiny.example/tiny.png": png(30, 10),
              "https://hollow.example/hollow.png": png(300, 100, (10, 10, 290, 90)),
              "https://glossy.example/glossy-hero.png": SCREENSHOT.read_bytes()}
    calls = []

    def stub(url):
        calls.append(url)
        if url not in served:
            raise OSError("404 from the stub")
        return 200, served[url]
    got = pixel_gate(SHADOWED.read_bytes(), "png")
    verdict("red", "the shadowed Globex logo reds the halo gate", any(g.startswith("halo:") for g in got), got)
    got = pixel_gate(served["https://acme.example/img/acme.png"], "png")
    verdict("green", "a clean 280x80 px mark passes the pixel gates", got == [], got)
    got = pixel_gate(served["https://tiny.example/tiny.png"], "png")
    verdict("red", "a 30x10 px mark reds the size gate", any("under 64 px" in g for g in got), got)
    got = pixel_gate(INKLESS.read_bytes(), "svg")
    verdict("red", "an SVG with fill none on its root and unfilled paths reds the ink gate",
            any(g.startswith("no ink:") for g in got), got)
    got = pixel_gate(SCREENSHOT.read_bytes(), "png")
    verdict("red", "a product illustration under blurred shadows reds the soft-area gate",
            any(g.startswith("soft:") for g in got), got)
    got = [(f.name, pixel_gate(f.read_bytes(), "svg")) for f in sorted(FIXTURE.glob("served/*.svg"))]
    verdict("green", "a filled SVG mark passes the ink and soft-area gates", got and all(g == [] for _, g in got), got)
    with tempfile.TemporaryDirectory() as tmp:
        root = auto_root(tmp)
        out = io.StringIO()
        with contextlib.redirect_stderr(io.StringIO()) as err:
            code = auto(root, ink=False, fetch=stub, out=out)
        said = out.getvalue() + err.getvalue()
        recs = {r["slug"]: r for r in json.loads((root / LOGOS_JSON).read_text())} if code == 0 else {}
        picks = (root / "logos/picks.tsv").read_text().splitlines() if (root / "logos/picks.tsv").exists() else []
        verdict("green", "--auto writes picks.tsv and a gated logos.json, one record a company",
                code == 0 and picks[0] == "\t".join(PICK_COLUMNS) and sorted(recs) ==
                sorted(["acme-grid", "shade", "tiny", "vector-co", "blur", "plain", "hollow", "glossy"]), said)
        verdict("green", "the name check passes over a customer's logo to the client's own",
                recs.get("acme-grid", {}).get("href") == "/img/acme.png"
                and "https://acme.example/img/client-bolt.png" not in calls, (recs.get("acme-grid"), calls))
        verdict("red", "the shadowed logo is refused, so the company gets a wordmark saying why",
                recs.get("shade", {}).get("kind") == "wordmark" and "halo" in recs["shade"].get("reason", ""),
                recs.get("shade"))
        verdict("red", "a mark under the size gate becomes a wordmark",
                recs.get("tiny", {}).get("kind") == "wordmark" and "under 64 px" in recs["tiny"].get("reason", ""),
                recs.get("tiny"))
        verdict("green", "an unnamed inline svg in a link home is the company's own",
                recs.get("vector-co", {}).get("kind") == "svg", recs.get("vector-co"))
        verdict("red", "an svg drawing a <filter> is refused", recs.get("blur", {}).get("kind") == "wordmark"
                and "<filter>" in recs["blur"].get("reason", ""), recs.get("blur"))
        verdict("red", "an inline svg drawing no ink is refused and the next candidate is the pick",
                recs.get("hollow", {}).get("href") == "/hollow.png" and "svg@" in said and "no ink:" in said,
                (recs.get("hollow"), said))
        verdict("red", "the illustration is refused, so the company gets a wordmark saying why",
                recs.get("glossy", {}).get("kind") == "wordmark" and "soft:" in recs["glossy"].get("reason", ""),
                recs.get("glossy"))
        verdict("green", "a page with no candidate gets a wordmark",
                recs.get("plain", {}).get("kind") == "wordmark", recs.get("plain"))
        (root / "reader.json").unlink()
        with contextlib.redirect_stderr(io.StringIO()):
            code = auto(root, ink=False, fetch=unreached, out=io.StringIO())
        verdict("red", "--auto with no reader.json exits 2", code == 2, code)


def _pick_value(slug):
    for ln in (FIXTURE / "picks.tsv").read_text(encoding="utf-8").split("\n"):
        if ln.startswith(slug + "\t"):
            return ln.split("\t")[4]
    return None


_http_get = http_get

if __name__ == "__main__":
    sys.exit(main(sys.argv))
