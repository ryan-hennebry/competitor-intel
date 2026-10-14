#!/usr/bin/env python3
"""The Labels critic's input: every label in a brief, each with its children.

`quality-bar/06-critique-rubric.md:10` gives the Labels critic this dump and one check: every h2,
column header, row label and bold claim-header covers all its children and names what they share.
Those four are CLASSES. The dump is a tree, two spaces per level:

  h2: <heading>                  children: its claim-headers, tables, h3s, overlines, items, paras
    claim-header: <bold lead>    child: body: <the rest of the paragraph>
    table: <col> | <col> | ...
      column-header: <col>       children: cell: <each cell under it>
      row-label: <first cell>    children: <col>: <each other cell in the row>
    h3: <heading>                children: every block after it, to the next h3 or h2
    overline: <text>             children: every block after it, to the next overline, h3 or h2

THE QUOTE. Every label in LABELS has a first child `source: <line>`: everything after `source: `
is the brief's own line, byte for byte, markup and all -- the heading line, the table's header row,
the row, or the paragraph's first line. `tools/critique-check.py` keeps a quote only when it is
verbatim in the brief, or a whole line when it is short, so a critic quotes from `source:`, never
from a label or child, whose text is display text. Display text drops tags, link targets and
emphasis, and reads `<br>` as ` / `. A bold-led paragraph or list item is a claim-header. Text
before the first h2 (the masthead) is skipped. Nothing is truncated. No section name is known here:
the tree comes from the markdown alone, for any company's brief.

THE PAGE (`--brief`, `73-web-plan.md` W16). A page's labels live in its `brief.json`, not in
markdown: the two authored headings, each map axis with its yes and no labels, and the matrix's
columns and row labels. The template's fixed headings are not the run's to rename, so they are not
dumped. Every label's first child is `pointer: <RFC 6901 JSON pointer>`, the string the fixer
edits: the critic copies it into its row's `location` and quotes the label from the page text.

  h2: <moves_heading>            children: move: <company>: <its change>
  h2: <matrix.heading>           children: the matrix's labels below
    column-header: <company>     children: cell: <each cell under it>
    row-label: <label>           children: <company>: <each cell in the row>
  map-axis: <question>           children: its two axis-labels
    axis-label: <yes or no>      children: company: <name> (<answer's name>), each placed there

Usage: label-fit.py [BRIEF]    default build/briefing.md; the dump to stdout, counts to stderr
       label-fit.py --brief BRIEF_JSON
                               the page's labels from a brief.json, the same tree and counts
       label-fit.py --cells BRIEF [PRE-FIX-BRIEF]
                               the cell cap of `07-author.md` step 3, run before a build, on the
                               matrix (the widest table). Alone: its width, each column's longest
                               piece plus 3, summed, within WIDTH_CAP. With the brief that last
                               rendered at `scale 100%`: also no piece longer than its column's
                               longest piece there.
       label-fit.py --selftest
Exit 0 dumped, or every cell within the cap; 1 no h2 found, or a piece over the cap, each named;
2 unreadable or empty input, or a brief.json missing a field the dump reads.
"""
import contextlib
import html
import importlib.util
import io
import json
import pathlib
import re
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT = ROOT / "build" / "briefing.md"
FIXTURE = ROOT / "tools" / "fixtures" / "label-fit"
CLASSES = ("h2", "column-header", "row-label", "claim-header")
BRIEF_CLASSES = ("h2", "map-axis", "axis-label", "column-header", "row-label")  # --brief's labels
WEB_FIXTURE = ROOT / "tools" / "fixtures" / "web" / "synthetic.json"
LABELS = CLASSES + ("h3", "overline")  # every kind that carries a `source:` child
CLAIM = re.compile(r"^\*\*(.+?)\*\*\s*(.*)$", re.S)
LIST = re.compile(r"^(?:\d+[.)]|[-*+])\s+")
SEP = re.compile(r"^\|?\s*:?-{3,}")
SKIP = re.compile(r"^</?div\b[^>]*>$|^<hr\b[^>]*>$")
HEAD = re.compile(r"^(#{2,6})\s+(.*?)\s*#*$")
OVERLINE = re.compile(r'^<p\b[^>]*\bclass="[^"]*\boverline\b[^"]*"[^>]*>(.*)</p>$')


def untag(text):
    return re.sub(r"<[^>]+>", "", re.sub(r"<br\s*/?>", " / ", text))


def clean(text):
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", untag(text)).replace("*", "")
    return re.sub(r"\s+", " ", text).strip()


def cells(row):
    row = row.strip()
    row = row[1:] if row.startswith("|") else row
    row = row[:-1] if row.endswith("|") and not row.endswith("\\|") else row
    return [clean(c.replace("\\|", "|")) for c in re.split(r"(?<!\\)\|", row)]


def blocks(lines):
    """Yield (kind, payload, raw) in order: ('h2' | 'h3', heading, its line) or ('block',
    [(raw line, stripped line), ...], None). Div and hr lines break blocks."""
    buf = []
    for raw in lines + [""]:
        s = "" if SKIP.match(raw.strip()) else raw.strip()
        head = HEAD.match(s)
        if head or not s:
            if buf:
                yield "block", buf, None
            buf = []
            if head:
                yield ("h2" if len(head.group(1)) == 2 else "h3"), clean(head.group(2)), raw
        else:
            buf.append((raw, s))


def table(lines, emit):
    """Emit a pipe table; False when it holds no row but separators, so the caller falls back."""
    rows = [(raw, cells(s)) for raw, s in lines if not SEP.match(s)]
    if not rows:
        return False
    (head_raw, head), body = rows[0], rows[1:]
    emit(1, "table", " | ".join(head))
    for i, col in enumerate(head):
        emit(2, "column-header", col, head_raw)
        for _, row in body:
            emit(3, "cell", row[i] if i < len(row) else "")
    for raw, row in body:
        emit(2, "row-label", row[0], raw)
        for col, cell in zip(head[1:], row[1:]):
            emit(3, col, cell)
    return True


def para(lines, emit, plain="para"):
    text = " ".join(s for _, s in lines)
    lead = CLAIM.match(untag(text).strip())
    if lead:
        emit(1, "claim-header", clean(lead.group(1)), lines[0][0])
        if clean(lead.group(2)):
            emit(2, "body", clean(lead.group(2)))
    else:
        emit(1, plain, clean(text))


def items(lines, emit):
    found = []
    for raw, s in lines:
        if LIST.match(s) or not found:
            found.append([(raw, LIST.sub("", s))])
        else:
            found[-1].append((raw, s))
    for item in found:
        para(item, emit, "item")


def dump(text):
    """Return (dump lines, per-class counts) for a brief's markdown."""
    out, counts, seen_h2 = [], dict.fromkeys(CLASSES, 0), False
    sub = [0, 0]  # an open h3, an open overline: each nests what follows one level deeper

    def emit(depth, kind, value, raw=None):
        depth += sum(sub)
        out.append("%s%s: %s" % ("  " * depth, kind, value))
        if raw is not None:
            out.append("%ssource: %s" % ("  " * (depth + 1), raw))
        if kind in counts:
            counts[kind] += 1

    for kind, payload, raw in blocks(text.splitlines()):
        first = payload[0][1] if kind == "block" else ""
        over = OVERLINE.match(first) if kind == "block" and len(payload) == 1 else None
        if kind == "h2":
            seen_h2, sub[:] = True, [0, 0]
            emit(0, "h2", payload, raw)
        elif not seen_h2:
            continue
        elif kind == "h3":
            sub[:] = [0, 0]
            emit(1, "h3", payload, raw)
            sub[0] = 1
        elif over:
            sub[1] = 0
            emit(1, "overline", clean(over.group(1)), payload[0][0])
            sub[1] = 1
        elif first.startswith("|") and table(payload, emit):
            continue
        elif LIST.match(first):
            items(payload, emit)
        else:
            para(payload, emit)
    return out, counts


def run(path, stdout=sys.stdout, stderr=sys.stderr):
    try:
        text = pathlib.Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as err:
        stderr.write("LABEL-FIT ERROR: cannot read %s: %s\n" % (path, err))
        return 2
    if not text.strip():
        stderr.write("LABEL-FIT ERROR: %s is empty\n" % path)
        return 2
    out, counts = dump(text)
    if not counts["h2"]:
        stderr.write("LABEL-FIT RED: no h2 in %s, so no label to dump\n" % path)
        return 1
    stdout.write("\n".join(out) + "\n")
    stderr.write("LABEL-FIT OK (%s)\n" % ", ".join("%d %s" % (counts[c], c) for c in CLASSES))
    return 0


def joined(spans):
    """A span array as the page joins it: each `t` in order, whitespace collapsed."""
    return re.sub(r"\s+", " ", "".join(s["t"] for s in spans)).strip()


def brief_dump(b):
    """(dump lines, per-class counts) for a brief.json, in page order: the map, then the moves
    heading, then the matrix. A missing field raises KeyError, IndexError or TypeError."""
    out, counts = [], dict.fromkeys(BRIEF_CLASSES, 0)
    # A column's label is the name the page prints, `short` where set, else `name` (`web.py`
    # `shown`), and the pointer is that field (W16-verify Recommended 6).
    names = {e["slug"]: e.get("short") or e["name"] for e in [b["company"]] + b["rivals"]}
    key = lambda e: "short" if e.get("short") else "name"
    where = dict([(b["company"]["slug"], "/company/" + key(b["company"]))]
                 + [(e["slug"], "/rivals/%d/%s" % (k, key(e))) for k, e in enumerate(b["rivals"])])

    def emit(depth, kind, value, pointer=None):
        out.append("%s%s: %s" % ("  " * depth, kind, value))
        if pointer is not None:
            out.append("%spointer: %s" % ("  " * (depth + 1), pointer))
        if kind in counts:
            counts[kind] += 1

    for axis in ("across", "down"):
        ax = b["map"][axis]
        emit(0, "map-axis", ax["question"], "/map/%s/question" % axis)
        for side in ("yes", "no"):
            emit(1, "axis-label", ax[side], "/map/%s/%s" % (axis, side))
            for a in b["map"]["answers"]:
                if a[axis]["answer"] == side:
                    emit(2, "company", "%s (%s)" % (names[a["company"]], a[axis].get("name") or "no name"))
    emit(0, "h2", b["moves_heading"], "/moves_heading")
    for mv in b["moves"]:
        emit(1, "move", "%s: %s" % (names[mv["rival"]], joined(mv["change"])))
    mx = b["matrix"]
    cols = [names[slug] for slug in mx["columns"]]
    emit(0, "h2", mx["heading"], "/matrix/heading")
    for k, col in enumerate(cols):
        emit(1, "column-header", col, where[mx["columns"][k]])
        for row in mx["rows"]:
            emit(2, "cell", row["cells"][k]["t"])
    for i, row in enumerate(mx["rows"]):
        emit(1, "row-label", row["label"], "/matrix/rows/%d/label" % i)
        for col, cell in zip(cols, row["cells"]):
            emit(2, col, cell["t"])
    return out, counts


def run_brief(path, stdout=sys.stdout, stderr=sys.stderr):
    try:
        b = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        out, counts = brief_dump(b)
    except (OSError, UnicodeDecodeError, ValueError, KeyError, IndexError, TypeError, AttributeError) as err:
        stderr.write("LABEL-FIT ERROR: cannot dump the labels of %s: %r\n" % (path, err))
        return 2
    stdout.write("\n".join(out) + "\n")
    stderr.write("LABEL-FIT OK (%s)\n" % ", ".join("%d %s" % (counts[c], c) for c in BRIEF_CLASSES))
    return 0


def resolve(doc, pointer):
    """RFC 6901, for the plain keys and indexes --brief prints."""
    for part in pointer.split("/")[1:]:
        doc = doc[int(part)] if isinstance(doc, list) else doc[part]
    return doc


# --cells: `07-author.md` step 3's cell cap, before any build. The longest unbreakable piece of any
# cell, header included, is its column's floor, and the floors plus padding set the matrix's width:
# one long word widens it past the text column and `audit()` reds `scale`. The WIDTH is the sum of
# each column's floor plus 3, so the cap scales with the column count. WIDTH_CAP 91 is [INFERRED]
# from four briefs: the exemplar 90 (7 columns) and P20's final 90 (8) rendered at 100%; P20's
# fixer build 93 rendered at 98% and its first author build 99 at 94%.
WIDTH_CAP = 91
PAD = 3
BREAK = re.compile(r"(?<=[-­])")  # a hyphen or soft hyphen is a line-break opportunity


def pieces(cell):
    return [p for w in html.unescape(cell).split() for p in BREAK.split(w) if p]


def matrices(text):
    """The brief's widest tables, in order: the matrix is the one with a column per company."""
    found = []
    for kind, payload, _ in blocks(text.splitlines()):
        if kind == "block" and payload[0][1].startswith("|"):
            rows = [cells(s) for _, s in payload if not SEP.match(s)]
            if rows:
                found.append(rows)
    wide = max((len(t[0]) for t in found), default=0)
    return [t for t in found if len(t[0]) == wide]


def floors(rows):
    """{column header: its longest piece}, over every row, the header row included."""
    out = {}
    for i, col in enumerate(rows[0]):
        found = [p for r in rows for p in pieces(r[i] if i < len(r) else "")]
        out[col] = max(found, key=len) if found else ""
    return out


def width(rows):
    return sum(len(p) + PAD for p in floors(rows).values())


def cell_reds(text, ref=None):
    """(red lines, cells read). Alone: each matrix's width within WIDTH_CAP. With `ref`, the brief
    that last rendered at 100%: no piece longer than its column's floor there, and the width within
    the larger of the cap and the ref's width, which catches an added column."""
    reds, n, refs = [], 0, matrices(ref) if ref is not None else []
    for k, rows in enumerate(matrices(text)):
        n += sum(len(r) for r in rows)
        cap = max(WIDTH_CAP, width(refs[k])) if k < len(refs) else WIDTH_CAP
        if width(rows) > cap:
            reds.append("cell-width: matrix %d is %d wide, over the cap of %d; the longest piece per "
                        "column: %s" % (k + 1, width(rows), cap, ", ".join(
                            '"%s" %d' % (p, len(p)) for p in floors(rows).values())))
        old = floors(refs[k]) if k < len(refs) else {}
        for row in rows:
            for col, cell in zip(rows[0], row):
                for p in pieces(cell):
                    if col in old and len(p) > len(old[col]):
                        reds.append('cell-width: matrix %d, row "%s", column "%s": "%s" is %d '
                                    "characters, over the column's %d in the pre-fix brief"
                                    % (k + 1, row[0], col, p, len(p), len(old[col])))
    return reds, n


def run_cells(path, ref=None, stdout=sys.stdout, stderr=sys.stderr):
    texts = []
    for p in [path] + ([ref] if ref else []):
        try:
            texts.append(pathlib.Path(p).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as err:
            stderr.write("LABEL-FIT ERROR: cannot read %s: %s\n" % (p, err))
            return 2
    if ref and not matrices(texts[1]):
        stderr.write("LABEL-FIT ERROR: the pre-fix brief %s holds no table\n" % ref)
        return 2
    reds, n = cell_reds(texts[0], texts[1] if ref else None)
    stdout.write("".join(r + "\n" for r in reds))
    what = "width cap and the column floors of %s" % ref if ref else "width cap of %d" % WIDTH_CAP
    if reds:
        stdout.write("LABEL-FIT CELLS RED (%d finding(s) over the %s)\n" % (len(reds), what))
        return 1
    stdout.write("LABEL-FIT CELLS OK (%d matrix cell(s) within the %s)\n" % (n, what))
    return 0


# One case per class on the fixture: a label and one child that must sit under it.
CHECKS = (
    ("h2", "Threat Map", "table: Rival | Threat | Gap"),
    ("column-header", "Threat", "cell: HIGH"),
    ("row-label", "Tessel", "Gap: No customs module | no bonded store"),
    ("claim-header", "Is Quayside licensed?", "body: Its register entry lists no permission."),
    ("claim-header", "Price in public before Tessel does.",
     "body: Tessel’s page still says contact sales, per its “pricing” tab."),
    ("h3", "Method", "item: Does Tessel bill per lane?"),
    ("overline", "Primary", "para: tessel.example / Quayside FAQ"),
)


def children(out, i):
    depth = len(out[i]) - len(out[i].lstrip())
    kids = []
    for line in out[i + 1:]:
        if len(line) - len(line.lstrip()) <= depth:
            break
        kids.append(line.strip())
    return kids


def quote_cases(out, brief, case):
    """Every label's `source:` is a whole line of the brief, and critique-check keeps it as a quote.
    The display-text control proves the grader is live: a short label alone is dropped."""
    spec = importlib.util.spec_from_file_location("critique_check", ROOT / "tools" / "critique-check.py")
    cc = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True  # no `tools/__pycache__/` left in the tree, as critique-check
    spec.loader.exec_module(cc)

    def quote_drops(quote):
        fields = ["L1", "labels", "", "MINOR", quote, "-", "", "", "", ""]
        return [why for rule, why in cc.row_drops(fields, brief, set()) if rule == "quote"]

    lines, sources = brief.split("\n"), []
    for i, line in enumerate(out):
        kind, pad = line.strip().split(": ", 1)[0], line[:len(line) - len(line.lstrip())]
        if kind in LABELS:
            nxt = out[i + 1] if i + 1 < len(out) else ""
            head = pad + "  source: "
            case("source: %r's first child is its source line" % line.strip(),
                 nxt.startswith(head) and nxt[len(head):] in lines)
            sources.append(nxt[len(head):])
    bad = [q for q in sources if quote_drops(q)]
    case("critique-check keeps every source: quote (dropped: %r)" % bad[:2], sources and not bad)
    case("critique-check drops the short display label 'Rival' (the control)",
         bool(quote_drops("Rival")))


def cell_cases(case):
    """--cells: each case names the one rule it proves; a red must name its piece."""
    real = lambda path: cell_reds(path.read_text(encoding="utf-8"))[0]
    # The calibration: the exemplar at 100% (90 wide), P20's fixer build at 98% (93), its first
    # author build at 94% (99). Each red names the piece that widened it.
    case("cells: the exemplar, 90 wide over 7 columns, is green", real(ROOT / "build" / "briefing.md") == [])
    red = real(FIXTURE / "cells-fixer-98.md")
    case("cells: P20's 98% build is red at 93, naming its piece", len(red) == 1
         and "is 93 wide" in red[0] and '"Powervault," 11' in red[0])
    red = real(FIXTURE / "cells-author-94.md")
    case("cells: P20's 94% build is red at 99, naming its piece", len(red) == 1
         and "is 99 wide" in red[0] and '"Flexitricity," 13' in red[0])
    head = "## M\n\n| Test | Tessel | Quayside |\n|---|---|---|\n"
    lint = lambda body, ref=None: cell_reds(head + body, ref)[0]
    case("cells: a short matrix is green", lint("| Lanes | Yes, stated | None found |\n") == [])
    long3 = "| %s | %s | %s |\n" % (("Quay-side-harbour-master-ships",) * 2 + ("Tide&shy;watchers&shy;harbourside",))
    case("cells: a hyphen and &shy; are break points (99 wide unbroken)", lint(long3) == [])
    narrow = "## N\n\n| A | B |\n|---|---|\n| %s | %s |\n\n" % ("W" * 45, "V" * 45)
    case("cells: only the widest table is graded, wherever it sits",
         cell_reds(narrow + head + "| Lanes | Yes | No |\n")[0] == [])
    ref = head + "| Lanes | Yes | No |\n"
    red = lint("| Lanes | Pilotage | No |\n", ref)
    case("cells: with a pre-fix brief, a piece over its column's floor is red, under the cap",
         len(red) == 1 and '"Pilotage" is 8' in red[0] and lint("| Lanes | Pilotage | No |\n") == [])
    case("cells: with a pre-fix brief, the header is part of the floor",
         lint("| Lanes | Yes | Tidewate |\n", ref) == [])
    with tempfile.TemporaryDirectory(prefix="label-fit-cells.") as tmp:
        good, bad = pathlib.Path(tmp) / "good.md", FIXTURE / "cells-author-94.md"
        good.write_text(head + "| Lanes | Yes | Listed |\n", encoding="utf-8")
        for name, args, want in (("green", (good,), 0), ("red", (bad,), 1),
                                 ("missing pre-fix brief", (good, pathlib.Path(tmp) / "no.md"), 2),
                                 ("pre-fix brief with no table", (good, pathlib.Path(tmp) / "no.md"), 2)):
            if name == "pre-fix brief with no table":
                (pathlib.Path(tmp) / "no.md").write_text("## A\n\nNo table.\n", encoding="utf-8")
            got = run_cells(*args, stdout=io.StringIO(), stderr=io.StringIO())
            case("cells CLI: %s exits %d (got %d)" % (name, want, got), got == want)


def brief_cases(case):
    """--brief on the synthetic page fixture: the golden dump, each class with a child that must
    sit under it, every pointer resolving to its own label, and fail-closed exits."""
    b = json.loads(WEB_FIXTURE.read_text(encoding="utf-8"))
    out, counts = brief_dump(b)
    golden = (FIXTURE / "synthetic.expected.txt").read_text(encoding="utf-8")
    case("brief: the dump of synthetic.json is synthetic.expected.txt", "\n".join(out) + "\n" == golden)
    for cls in BRIEF_CLASSES:
        case("brief: class %s counted on the fixture" % cls, counts[cls] > 0)
    case("brief: one row-label per matrix row", counts["row-label"] == len(b["matrix"]["rows"]))
    short = b["company"]["short"]
    hit = [i for i, line in enumerate(out) if line.strip() == "column-header: %s" % short]
    case("brief: a column header is the short name the page prints, at /company/short",
         len(hit) == 1 and out[hit[0] + 1].strip() == "pointer: /company/short")
    row, col = b["matrix"]["rows"][2], b["company"].get("short") or b["company"]["name"]
    checks = (("row-label", row["label"], "%s: %s" % (col, row["cells"][0]["t"])),
              ("column-header", col, "cell: %s" % row["cells"][0]["t"]),
              ("axis-label", b["map"]["across"]["no"], "company: ZephyrLoads (no name)"),
              ("map-axis", b["map"]["down"]["question"], "axis-label: %s" % b["map"]["down"]["yes"]),
              ("h2", b["matrix"]["heading"], "row-label: %s" % row["label"]))
    for cls, label, child in checks:
        hits = [i for i, line in enumerate(out) if line.strip() == "%s: %s" % (cls, label)]
        case("brief: %s %r holds %r" % (cls, label, child), any(child in children(out, i) for i in hits))
    bad = []
    for i, line in enumerate(out):
        kind, value = line.strip().split(": ", 1)
        if kind in BRIEF_CLASSES:
            nxt = out[i + 1].strip() if i + 1 < len(out) else ""
            if not nxt.startswith("pointer: ") or resolve(b, nxt[len("pointer: "):]) != value:
                bad.append(line.strip())
    case("brief: every label's pointer resolves to that label (off: %r)" % bad[:2], not bad)
    with tempfile.TemporaryDirectory(prefix="label-fit-brief.") as tmp:
        for name, text in (("not JSON", "## A\n"), ("no matrix", json.dumps(dict(b, matrix=None)))):
            path = pathlib.Path(tmp) / name.replace(" ", "-")
            path.write_text(text, encoding="utf-8")
            got = run_brief(path, io.StringIO(), io.StringIO())
            case("brief CLI: %s exits 2 (got %d)" % (name, got), got == 2)


def selftest():
    fails, n = [], [0]

    def case(name, ok):
        n[0] += 1
        if not ok:
            fails.append(name)
            sys.stderr.write("SELFTEST FAIL: %s\n" % name)

    brief = (FIXTURE / "brief.md").read_text(encoding="utf-8")
    out, counts = dump(brief)
    golden = (FIXTURE / "brief.expected.txt").read_text(encoding="utf-8")
    case("golden: the dump of brief.md is brief.expected.txt", "\n".join(out) + "\n" == golden)
    for cls in CLASSES:
        case("class %s: counted on the fixture" % cls, counts[cls] > 0)
    for cls, label, child in CHECKS:
        hits = [i for i, line in enumerate(out) if line.strip() == "%s: %s" % (cls, label)]
        case("class %s: %r holds %r" % (cls, label, child),
             any(child in children(out, i) for i in hits))
    case("masthead: nothing before the first h2 is dumped",
         out[:1] and out[0].startswith("h2: ") and not any("Prepared for" in s for s in out))
    with tempfile.TemporaryDirectory(prefix="label-fit-selftest.") as tmp:
        for name, text, want in (("empty input", " \n", 2), ("no h2", "# Title\n\nBody.\n", 1),
                                 ("missing file", None, 2), ("non-UTF-8", b"## A\n\xff\n", 2),
                                 ("separator-only table", "## A\n\n|---|---|\n", 0)):
            path = pathlib.Path(tmp) / name.replace(" ", "-")
            if isinstance(text, bytes):
                path.write_bytes(text)
            elif text is not None:
                path.write_text(text, encoding="utf-8")
            sink = io.StringIO()
            with contextlib.redirect_stderr(sink):
                try:
                    got = run(path, io.StringIO(), sink)
                except Exception:  # a crash is a red case, named, not a traceback
                    got = -1
            case("fail closed: %s exits %d (got %d)" % (name, want, got), got == want)
    quote_cases(out, brief, case)
    cell_cases(case)
    brief_cases(case)
    if fails:
        sys.stderr.write("LABEL-FIT SELFTEST RED (%d of %d cases)\n" % (len(fails), n[0]))
        return 1
    print("LABEL-FIT SELFTEST OK (%d cases)" % n[0])
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--selftest"]:
        sys.exit(selftest())
    if args[:1] == ["--cells"] and len(args) in (2, 3):
        sys.exit(run_cells(*args[1:]))
    if args[:1] == ["--cells"]:
        sys.stderr.write("LABEL-FIT ERROR: usage: label-fit.py --cells BRIEF [PRE-FIX-BRIEF]\n")
        sys.exit(2)
    if args[:1] == ["--brief"]:
        if len(args) != 2:
            sys.stderr.write("LABEL-FIT ERROR: usage: label-fit.py --brief BRIEF_JSON\n")
            sys.exit(2)
        sys.exit(run_brief(args[1]))
    sys.exit(run(args[0] if args else DEFAULT))
