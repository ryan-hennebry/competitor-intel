#!/usr/bin/env python3
"""The back lane's code steps: each agent's inlined input, the founder majority, and verify.jsonl.

WHY THIS EXISTS. From the author on, every agent node gets its inputs pasted into the prompt by
the runner (`inline:`), never fetched with tools (design.md § 3: the author has Write only, the
critics, arbiter and span-verify Read or nothing). Joining rows by ID, cutting the page into lines
and spans, and keying a verdict to a span hash are bookkeeping, so code does them here and every
agent spends its turns on judgement (b1 § 2: bookkeeping was about 15% of the author's thinking).

  back-lane.py author BRIEF_ROOT
      author-in.md: the reader, the locked thesis, 06-allocation.md whole, 06-budget.tsv, the caps,
      brief-check's rules digest (`--rules-digest`), the shape, the rival slugs, every allotted or
      thesis-cited row pre-joined by ID with `known` set by code (as SP/measure-model/build_author.py
      did for b1), then the founder card, the voice card, the refusals and the exemplars
  back-lane.py critics BRIEF_ROOT
      brief-author.json (the author's page, span-diff's base) and critic-in/{founder,truth,voice,
      redteam}.md: founder is tools/line-screen.py's batch over every authored line; truth every span
      with its rows; voice and redteam the page by span id with their cards
  back-lane.py founder BRIEF_ROOT
      findings/founder.json: line-screen's decide() over findings/founder-{a,b,c}.json (a test is red
      on a line when 2 of the screeners that answered say no, plus NEW(code) and LEAD(code)); one
      finding per red test, on the span holding the quote
  back-lane.py arbiter BRIEF_ROOT [--repair [--out NAME]]
      findings.json (every critic's findings, numbered F-001..) and arbiter-in.md: the findings,
      brief-check's reds on the page as it stands (none after a green author; a replay from an older
      page carries some), brief-check's rules digest, the page by span with each field's cap and each
      span's most words, the rows. --repair: arbiter-repair-in.md, the spans whose last verify.jsonl
      row at their hash is FAIL, with each FAIL's note, and no findings or gate reds; --out names
      the file instead, one per repair round (arbiter-repair-r2-in.md)
  back-lane.py span-verify BRIEF_ROOT --base FILE [--tag T]
      span-verify[-T]-set.json and span-verify[-T]-in.md: the spans that changed from FILE, their
      field neighbours, every span citing a row a changed span cites, and every span with no
      verify.jsonl row at its hash
  back-lane.py rows BRIEF_ROOT VERDICTS --by NAME [--need SETFILE]
      a gate: VERDICTS' `spans` holds one PASS or FAIL per span of brief.json (or per span id in
      SETFILE), each a span of the brief, each FAIL with a note; then appends a verify.jsonl row per
      verdict at the span's hash now (span-diff.py's). A red writes nothing
  back-lane.py repair-needed BRIEF_ROOT
      exit 0 when a span's last verify.jsonl row at its hash is FAIL (the repair round's `when`)
  back-lane.py --selftest
      offline, on the Globex fixture root and the synthetic brief

EXIT CODES. 0 written (or repair needed). 1 a gate red (rows), --selftest red, or no repair needed.
2 could not run: usage, or an input missing or unreadable.

PRECONDITION: none. Stdlib only, offline.
"""

import contextlib
import copy
import datetime
import importlib.util
import io
import json
import pathlib
import re
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parent.parent
TZ = "Europe/London"
ROW_KEYS = ("id", "subject", "claim", "qualifier", "metric", "quote", "url", "state", "lang", "gloss", "scope",
            "kind", "question_id")
COPIES = ("a", "b", "c")
CRITICS = ("founder", "truth", "voice", "redteam")
CLAIM_RE = re.compile(r"C-[0-9]{3,}")


class CannotRun(Exception):
    """Exit 2."""


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SD = _load("span_diff", "tools/span-diff.py")
LS = _load("line_screen", "tools/line-screen.py")
RANK = LS.RANK
SCHEMA = _load("schema", "tools/schema.py")


def now():
    from zoneinfo import ZoneInfo
    return datetime.datetime.now(ZoneInfo(TZ)).isoformat(timespec="seconds")


def read_json(path, default=None):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        if default is not None:
            return default
        raise CannotRun("cannot read %s (%s)" % (path, exc))


def read_text(path):
    try:
        return pathlib.Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise CannotRun("cannot read %s (%s)" % (path, exc))


def fence(x):
    return "```json\n" + json.dumps(x, indent=1, ensure_ascii=False) + "\n```\n"


def ids_of(c):
    return LS.ids_of(c)


def ctx(root):
    """(reader, claims, known) for a BRIEF_ROOT."""
    reader = read_json(root / "reader.json")
    claims = RANK.read_claims(root / "claims.jsonl")
    if not claims:
        raise CannotRun("no claims.jsonl rows in %s" % root)
    return reader, claims, RANK.known_fn(reader, claims)


def trim(row, known):
    out = {k: row[k] for k in ROW_KEYS if k in row and row[k] not in ("", None)}
    out["known"] = known(row["id"], row.get("known"))
    return out


def rows_block(cids, claims, known):
    """One JSON row per line, pre-joined by ID, in ID order; an ID with no row is listed as such."""
    order = sorted(set(cids), key=lambda c: int(c[2:]) if c[2:].isdigit() else 0)
    lines = [json.dumps(trim(claims[c], known), ensure_ascii=False) if c in claims
             else json.dumps({"id": c, "missing": "no claims.jsonl row"}) for c in order]
    return "\n".join(lines) + "\n"


def brief_spans(brief):
    """[(field key, index, span)] for every span, span-diff's set and order."""
    return [(key, j, s) for key, arr in SD.backfill().span_fields(brief)
            for j, s in enumerate(arr if isinstance(arr, list) else [])]


def page_by_span(brief, caps=False):
    """The page as text, one span per line under its field: `id | c | text`. With caps, each field
    heading carries its word count against its cap, and each capped span `id | c | N words, at most
    M | text`: M is the most words its fix_new may hold while the rest of its field stands (X3)."""
    out, cur = [], None
    arrays = {}
    for key, _, s in brief_spans(brief):
        arrays.setdefault(key, []).append(s)
    words = {key: SCHEMA.words(arr) for key, arr in arrays.items()}  # the schema's own count
    cap = field_caps() if caps else {}
    for key, _, s in brief_spans(brief):
        limit = cap.get(cap_key(key))
        if key != cur:
            head = "## %s" % key
            if limit is not None:
                head += " (%d of %d words)" % (words[key], limit)
            out.append(head)
            cur = key
        extra = " cmp=%s" % s["cmp"] if s.get("cmp") else ""
        n = len(s.get("t", "").split())
        room = " | %d words, at most %d" % (n, max(0, n + limit - words[key])) if limit is not None else ""
        out.append("%s | %s%s%s | %s" % (s.get("id"), ",".join(ids_of(s.get("c"))) or "-", extra, room, s.get("t", "")))
    return "\n".join(out) + "\n"


CAPPED_PAGE = ("Every span: `span id | claim IDs | N words, at most M | text`, each field with its word count "
               "and cap. M is the most words the span's `fix_new` may hold while the rest of its field stands "
               "(X3).\n\n")


_BC = []


def rules_digest():
    """brief-check's RULE_DIGEST as text: the one statement of the rules its gate grades."""
    if not _BC:
        _BC.append(_load("brief_check", "tools/brief-check.py"))
    return _BC[0].rules_digest()


def cap_key(key):
    """qt.0.lede -> qt.lede; oq.1 -> oq; legend -> legend."""
    parts = key.split(".")
    return ".".join(p for p in parts if not p.isdigit())


def field_caps():
    """{cap key: x-maxWords} from build/web/brief.schema.json, the one source of the caps."""
    s = read_json(ROOT / "build/web/brief.schema.json")
    d = s["$defs"]
    return {"qt.lede": d["point"]["properties"]["lede"]["x-maxWords"],
            "qt.body": d["point"]["properties"]["body"]["x-maxWords"],
            "rec.test": d["rec"]["properties"]["test"]["x-maxWords"],
            "rec.why": d["rec"]["properties"]["why"]["x-maxWords"],
            "rec.next_step": d["rec"]["properties"]["next_step"]["x-maxWords"],
            "move.change": d["move"]["properties"]["change"]["x-maxWords"],
            "move.meaning": d["move"]["properties"]["meaning"]["x-maxWords"],
            "oq": s["properties"]["open_questions"]["items"]["x-maxWords"],
            "legend": d["matrix"]["properties"]["legend"]["x-maxWords"]}


def cited(brief):
    return [c for _, _, s in brief_spans(brief) for c in ids_of(s.get("c"))]


def write(path, text):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# --- author ---------------------------------------------------------------------------------------
def locked_candidate(root):
    thesis = read_json(root / "05-thesis.json")
    locked = thesis.get("locked")
    for c in thesis.get("candidates") or []:
        if isinstance(c, dict) and c.get("id") == locked:
            return c
    raise CannotRun("05-thesis.json locks %r and holds no candidate with that id" % locked)


SOURCE_LINE = re.compile(r"Source for stage 7:(.*)")
SOURCE_PART = re.compile(r"(comp-[a-z0-9-]+\.md)|lines? (\d+)-(\d+)")


def comp_ranges(root, alloc):
    """The comp-<slug>.md line ranges the allocation's `Source for stage 7` lines name, as text
    blocks: the derivation a distribution claim prints with (b1 inlined comp-globex.md:74-105)."""
    out, seen = [], set()
    for m in SOURCE_LINE.finditer(alloc):
        current = None
        for part in SOURCE_PART.finditer(m.group(1)):
            if part.group(1):
                current = part.group(1)
            elif current and (current, part.group(2)) not in seen and (root / current).is_file():
                seen.add((current, part.group(2)))
                lo, hi = int(part.group(2)), int(part.group(3))
                lines = read_text(root / current).splitlines()[lo - 1:hi]
                out.append("## %s lines %d-%d\n\n%s\n" % (current, lo, hi, "\n".join(lines)))
    return out


CAP_NAMES = (("qt.lede", "quick_take[].lede"), ("qt.body", "quick_take[].body"), ("rec.test", "recommendations[].test"),
             ("rec.why", "recommendations[].why"), ("rec.next_step", "recommendations[].next_step"),
             ("move.change", "moves[].change"), ("move.meaning", "moves[].meaning"),
             ("oq", "open_questions[]"), ("legend", "matrix.legend"))


def caps_block():
    """Every prose field's word cap, from brief.schema.json. The runner strips x-maxWords from the
    schema it passes `--json-schema` (the CLI rejects the keyword), so the author sees the caps here."""
    caps = field_caps()
    rows = ["| %s | %d |" % (name, caps[key]) for key, name in CAP_NAMES]
    return ("# CAPS\n\nHard word caps per field, counted on the field's spans joined; the gate reds a field "
            "over its cap. Headings (`moves_heading`, `matrix.heading`): 5 words and 26 characters. A matrix "
            "cell: 5 words at most, 1 to 3 as a rule.\n\n| field | words |\n|---|---|\n" + "\n".join(rows) + "\n")


def author(root):
    reader, claims, known = ctx(root)
    alloc = read_text(root / "06-allocation.md")
    shape = read_json(root / "06-shape.json")
    names = read_json(root / "names.json")
    cand = locked_candidate(root)
    ids = CLAIM_RE.findall(alloc + json.dumps(shape)) + [e["id"] for e in cand.get("evidence", [])]
    rd = {k: reader.get(k) for k in ("company", "role", "recipient", "duties", "positioning", "constraints",
                                     "known_summary") if k in reader}
    if isinstance(rd.get("recipient"), dict):
        rd["recipient"] = {k: rd["recipient"].get(k) for k in ("name", "title")}
    parts = [
        "# READER\n\nThe founder you write for: his company, the role, his duties and positioning lines, "
        "and what he already knows.\n\n" + fence(rd),
        "# THESIS\n\nThe locked candidate the page argues. Its headline is the page's first lede.\n\n" + fence(cand),
        "# ALLOCATION\n\n" + alloc.rstrip("\n") + "\n",
        "# BUDGET\n\n```\n" + read_text(root / "06-budget.tsv").rstrip("\n") + "\n```\n",
        caps_block(),
        "# RULES\n\n" + rules_digest(),
        "# SOURCES FOR THE AUTHOR\n\nThe line ranges the allocation's `Source for stage 7` lines name.\n\n"
        + ("\n".join(comp_ranges(root, alloc)) or "None named.\n"),
        "# SHAPE\n\nCode prints the map and the matrix's columns and cell IDs from this; you write the matrix "
        "cell texts, one per column in this column order, under each row label verbatim.\n\n" + fence(shape),
        "# NAMES\n\nThe rivals, by slug. A move's `rival` is one of these slugs.\n\n"
        + fence([{"slug": n["slug"], "name": n["name"]} for n in names]),
        "# ROWS\n\nEvery row the allocation, the shape or the thesis cites, pre-joined by ID. `known: true` is "
        "the founder's own fact (his site, posting or filings), set by code.\n\n```\n"
        + rows_block(ids, claims, known) + "```\n",
        "# FOUNDER CARD\n\n" + read_text(ROOT / "quality-bar/founder-card.md"),
        "# VOICE CARD\n\n" + read_text(ROOT / "quality-bar/02-voice-card.md"),
        "# REFUSALS\n\n" + read_text(ROOT / "quality-bar/03-refusals.md"),
        "# EXEMPLARS\n\nRead last: the cadence to write in.\n\n" + read_text(ROOT / "quality-bar/05-exemplars.md"),
    ]
    out = write(root / "author-in.md", "\n".join(parts))
    return "author-in.md: %d rows, %d bytes" % (len(set(ids)), out.stat().st_size)


# --- critics --------------------------------------------------------------------------------------
def critics(root):
    reader, claims, known = ctx(root)
    brief = read_json(root / "brief.json")
    SD.spans(brief)  # a typed brief, or exit 2
    shutil.copyfile(root / "brief.json", root / "brief-author.json")
    items, page, rows = LS.page_items(brief, claims, known)
    write(root / "critic-in/founder.md", LS.prompt_of(reader, rows, page, items))
    page_text = page_by_span(brief)
    ids = cited(brief)
    index = {}
    for line in read_text(root / "pages/index.tsv").splitlines()[1:]:
        cols = line.split("\t")
        if len(cols) > 1:
            index.setdefault(cols[0], line)
    urls = sorted({claims[c].get("url") for c in ids if c in claims and claims[c].get("url")})
    head = read_text(root / "pages/index.tsv").splitlines()[:1]
    write(root / "critic-in/truth.md", "\n".join([
        "# PAGE\n\nEvery span of brief.json: `span id | claim IDs | text`, by field.\n\n" + page_text,
        "# ROWS\n\nEvery row the page cites, pre-joined by ID; `known` is set by code.\n\n```\n"
        + rows_block(ids, claims, known) + "```\n",
        "# PAGES\n\nThe fetch index rows for the cited URLs (paths are under %s); Read a page when a row's "
        "quote does not settle a clause.\n\n```\n%s\n```\n" % (root, "\n".join(head + [index[u] for u in urls if u in index]))]))
    write(root / "critic-in/voice.md", "\n".join([
        "# PAGE\n\n" + page_text,
        "# VOICE CARD\n\n" + read_text(ROOT / "quality-bar/02-voice-card.md"),
        "# EXEMPLARS\n\n" + read_text(ROOT / "quality-bar/05-exemplars.md")]))
    write(root / "critic-in/redteam.md", "\n".join([
        "# PAGE\n\n" + page_text,
        "# READER\n\n" + fence({k: reader.get(k) for k in ("company", "role", "recipient", "known_summary")}),
        "# SHOTS\n\nThe built page's screenshots are the PNG files under %s/web/shots/; Read them for H7.\n"
        % root,
        "# HIRING RUBRIC\n\n" + read_text(ROOT / "quality-bar/01-hiring-rubric.md")]))
    return "critic-in/: founder %d lines, truth %d rows" % (len(items), len(set(ids)))


# --- the founder majority -------------------------------------------------------------------------
def founder(root):
    reader, claims, known = ctx(root)
    brief = read_json(root / "brief.json")
    items, _, _ = LS.page_items(brief, claims, known)
    by_copy = {}
    for c in COPIES:
        doc = read_json(root / ("findings/founder-%s.json" % c), {})
        if doc:
            by_copy[c] = (doc.get("verdicts") or [], None)
    if not by_copy:
        raise CannotRun("no findings/founder-<a|b|c>.json: every founder critic failed")
    decided = LS.decide(items, by_copy, known)
    lines = {LS.line_id(where, idx): spans for where, idx, spans in LS.lines_of(brief)}
    out = []
    for d in decided:
        spans = lines.get(d["item"]) or []
        reds = [(t, x["quotes"], "%d of %d screeners" % (x["n"], x["of"])) for t, x in d["tests"].items() if x["red"]]
        reds += [(code.replace("(code)", "-code"), [], detail) for code, detail in d["code"]]
        for test, quotes, why in reds:
            quote = next((q for q in quotes if q and q in d["text"]), d["text"])
            span = next((s for s in spans if quote in s.get("t", "")), spans[0] if spans else {})
            out.append({"critic": "founder", "span_id": span.get("id", "?"), "rule": test, "severity": "BLOCKER",
                        "quote": quote, "note": "%s red on line %s (%s)" % (test, d["item"], why)})
    write(root / "findings/founder.json", json.dumps({"findings": out}, indent=1, ensure_ascii=False) + "\n")
    return "findings/founder.json: %d findings from %d screeners on %d lines" % (len(out), len(by_copy), len(items))


# --- the arbiter ----------------------------------------------------------------------------------
def last_rows(root):
    """{(span_id, span_hash): last verify.jsonl row}."""
    out = {}
    path = root / "verify.jsonl"
    if path.is_file():
        for line in read_text(path).splitlines():
            if line.strip():
                r = json.loads(line)
                out[(r["span_id"], r["span_hash"])] = r
    return out


def failing(root, brief):
    """[(span_id, row)] for every span whose last row at its hash now is FAIL."""
    last = last_rows(root)
    return [(i, last[(i, h)]) for i, h in SD.hashes(brief).items() if (i, h) in last and last[(i, h)]["verdict"] == "FAIL"]


SLOT_KEYS = {"quick-take": ("qt.",), "recommendations": ("rec.",), "what-changed": ("move.",),
             "open-questions": ("oq.",), "matrix": ("legend",)}


def slot_allotments(root):
    """[{slot, spans, ids, evidence}]: each prose slot's allotted claim IDs (06-allocation.md's
    `- Claims:` and ICP lines) and its evidence-clause IDs, which stay cited in the slot, as
    brief-check A1 reads both, beside the span-id prefixes the slot covers."""
    bu = _load("budget_check", "tools/budget-check.py")
    try:
        pairs = bu.allocation_claims(root, ("claims", "icp"))
        ev = bu.allocation_claims(root, ("evidence",))
    except bu.Unreadable:
        return []
    out = {}
    for slot, cid in pairs:
        if slot in SLOT_KEYS and cid not in out.setdefault(slot, []):
            out[slot].append(cid)
    return [{"slot": k, "spans": "%s*" % " ".join(SLOT_KEYS[k]), "ids": v,
             "evidence": list(dict.fromkeys(c for sl, c in ev if sl == k))} for k, v in out.items()]


def gate_reds(root):
    """brief-check's FAIL lines on BRIEF_ROOT/brief.json, numbered G-001..: the arbiter's gate runs
    brief-check on the patched page, so a red already on the page is the arbiter's to fix."""
    bc = _load("brief_check", "tools/brief-check.py")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
        bc.main(["brief-check.py", str(root / "brief.json"), str(root)])
    fails = [l[len("FAIL: "):] for l in err.getvalue().splitlines() if l.startswith("FAIL: ")]
    return [{"id": "G-%03d" % n, "red": f} for n, f in enumerate(fails, 1)]


def arbiter(root, repair=False, out="arbiter-repair-in.md"):
    reader, claims, known = ctx(root)
    brief = read_json(root / "brief.json")
    SD.spans(brief)
    rules = ("# RULES\n\nA patch rewrites one span: `fix_old` is its text exactly as it stands, `fix_new` the "
             "new text, `c` the rows it rests on, each with a `url`, `finding_ids` the findings it answers. An "
             "empty fix_new deletes the span. The gate lays the patches on a copy of the page. ALLOTTED lists "
             "each slot's allotted and evidence-clause IDs (A1).\n\n" + rules_digest()
             + "\n# ALLOTTED\n\nEach prose slot's allotted claim IDs, by the span ids it covers.\n\n"
             + fence(slot_allotments(root)))
    allotted = CLAIM_RE.findall(read_text(root / "06-allocation.md")) if (root / "06-allocation.md").is_file() else []
    rd = {k: reader.get(k) for k in ("company", "positioning", "known_summary", "duties")}
    if repair:
        fails = failing(root, brief)
        if not fails:
            raise CannotRun("no span's last verify.jsonl row at its hash is FAIL: there is nothing to repair")
        listed = [{"id": "R-%03d" % n, "span_id": i, "by": r["by"], "note": r["note"]} for n, (i, r) in enumerate(fails, 1)]
        text = "\n".join([
            "# REPAIR\n\nThese spans failed their truth read. Patch these spans and no others; each patch "
            "answers the R- id of its span.\n\n" + fence(listed), rules,
            "# PAGE\n\n" + CAPPED_PAGE + page_by_span(brief, caps=True),
            "# ROWS\n\n```\n" + rows_block(cited(brief) + allotted, claims, known) + "```\n",
            "# READER\n\n" + fence(rd)])
        write(root / out, text)
        return "%s: %d failing spans" % (out, len(listed))
    found, n = [], 0
    for critic in CRITICS:
        doc = read_json(root / ("findings/%s.json" % critic), {})
        for f in doc.get("findings") or []:
            n += 1
            found.append(dict({"id": "F-%03d" % n}, **f))
    write(root / "findings.json", json.dumps({"findings": found}, indent=1, ensure_ascii=False) + "\n")
    reds = gate_reds(root)
    text = "\n".join([
        "# FINDINGS\n\nEvery critic's finding, numbered. Critics that wrote nothing found nothing or failed: "
        "%s.\n\n" % ", ".join(c for c in CRITICS if not (root / ("findings/%s.json" % c)).is_file()) + fence(found),
        "# GATE REDS\n\nbrief-check's reds on the page as it stands; the gate runs brief-check on the patched "
        "page, so answer each with a patch, citing its G- id.\n\n" + (fence(reds) if reds else "None.\n"),
        rules,
        "# PAGE\n\n" + CAPPED_PAGE + page_by_span(brief, caps=True),
        "# ROWS\n\nEvery row the page cites or the allocation allots, pre-joined by ID.\n\n```\n"
        + rows_block(cited(brief) + allotted, claims, known) + "```\n",
        "# READER\n\n" + fence(rd)])
    write(root / "arbiter-in.md", text)
    return "arbiter-in.md: %d findings, %d gate reds" % (len(found), len(reds))


# --- span-verify ----------------------------------------------------------------------------------
def verify_set(root, brief, base):
    """{span_id: [reasons]} in page order: changed from base, the changed spans' field neighbours,
    every span citing a row a changed span cites (old or new c), and every span with no row at its
    hash now."""
    now_spans = brief_spans(brief)
    old = SD.spans(base)
    changed = [i for i, _, _ in SD.diff(base, brief)]
    hit = {}

    def add(sid, why):
        hit.setdefault(sid, [])
        if why not in hit[sid]:
            hit[sid].append(why)
    rows = set()
    for sid in changed:
        for s in (old.get(sid), SD.spans(brief).get(sid)):
            if s:
                rows |= set(ids_of(s.get("c")))
    arrays = {}
    for key, j, s in now_spans:
        arrays.setdefault(key, []).append(s)
    for key, arr in arrays.items():
        for j, s in enumerate(arr):
            if s["id"] in changed:
                add(s["id"], "changed")
                for k in (j - 1, j + 1):
                    if 0 <= k < len(arr):
                        add(arr[k]["id"], "neighbour of %s" % s["id"])
    for _, _, s in now_spans:
        shared = sorted(rows & set(ids_of(s.get("c"))))
        if shared and s["id"] not in changed:
            add(s["id"], "cites %s, as a changed span does" % ", ".join(shared))
    last = last_rows(root)
    for sid, h in SD.hashes(brief).items():
        if (sid, h) not in last:
            add(sid, "no verify.jsonl row at its hash")
    order = [s["id"] for _, _, s in now_spans]
    return {sid: hit[sid] for sid in order if sid in hit}


def span_verify(root, base_path, tag=None):
    reader, claims, known = ctx(root)
    brief = read_json(root / "brief.json")
    base = read_json(base_path)
    todo = verify_set(root, brief, base)
    stem = "span-verify" + ("-%s" % tag if tag else "")
    write(root / ("%s-set.json" % stem), json.dumps({"spans": list(todo)}, indent=1) + "\n")
    spans = SD.spans(brief)
    old = SD.spans(base)
    listed = []
    for sid, why in todo.items():
        s = spans[sid]
        entry = {"span_id": sid, "text": s.get("t"), "c": ids_of(s.get("c")), "why": why}
        if sid in old and old[sid].get("t") != s.get("t"):
            entry["was"] = old[sid].get("t")
        listed.append(entry)
    rows = [c for e in listed for c in e["c"]]
    text = "\n".join([
        "# SPANS\n\nGive each span below one verdict. `was` is its text before the patch.\n\n" + fence(listed),
        "# PAGE\n\nThe whole page by span, for each span's neighbours and the section it sits in.\n\n" + page_by_span(brief),
        "# ROWS\n\n```\n" + rows_block(rows, claims, known) + "```\n",
        "# GATES\n\nfinal-build sealed: schema, brief-check, claims-check --check, voice-lint, ai-smell and "
        "web-check all exited 0 on this page.\n"])
    write(root / ("%s-in.md" % stem), text)
    return "%s-in.md: %d spans to read" % (stem, len(listed))


# --- verify.jsonl ---------------------------------------------------------------------------------
def rows(root, verdicts_path, by, need_path=None):
    """(red lines, rows appended)."""
    brief = read_json(root / "brief.json")
    hashes = SD.hashes(brief)
    doc = read_json(verdicts_path)
    got = doc.get("spans") if isinstance(doc, dict) else None
    if not isinstance(got, list):
        return ["%s holds no `spans` list" % verdicts_path], 0
    need = list(hashes) if need_path is None else read_json(need_path).get("spans", [])
    reds, seen = [], {}
    for n, v in enumerate(got):
        if not isinstance(v, dict) or v.get("verdict") not in ("PASS", "FAIL") or not isinstance(v.get("span_id"), str):
            reds.append("spans[%d] is no {span_id, verdict PASS|FAIL, note}" % n)
            continue
        sid = v["span_id"]
        if sid not in hashes:
            reds.append("spans[%d]: %s is no span of brief.json" % (n, sid))
        elif sid in seen:
            reds.append("spans[%d]: %s has a second verdict" % (n, sid))
        elif v["verdict"] == "FAIL" and not str(v.get("note", "")).strip():
            reds.append("spans[%d]: %s is FAIL with no note" % (n, sid))
        seen[sid] = v
    reds += ["%s has no verdict: every span listed must get PASS or FAIL" % sid for sid in need if sid not in seen]
    if reds:
        return reds, 0
    at = now()
    with open(root / "verify.jsonl", "a", encoding="utf-8") as f:
        for sid, v in seen.items():
            f.write(json.dumps({"span_id": sid, "span_hash": hashes[sid], "verdict": v["verdict"], "by": by,
                                "at": at, "note": str(v.get("note", ""))}, ensure_ascii=False) + "\n")
    return [], len(seen)


# --- main -----------------------------------------------------------------------------------------
def main(argv):
    args = argv[1:]
    if args == ["--selftest"]:
        return selftest()
    try:
        if len(args) == 2 and args[0] in ("author", "critics", "founder", "arbiter", "repair-needed"):
            root = pathlib.Path(args[1])
            if args[0] == "repair-needed":
                fails = failing(root, read_json(root / "brief.json"))
                for sid, r in fails:
                    print("FAIL %s by %s: %s" % (sid, r["by"], r["note"]))
                print("REPAIR %s" % ("NEEDED (%d spans)" % len(fails) if fails else "NOT NEEDED"))
                return 0 if fails else 1
            print({"author": author, "critics": critics, "founder": founder, "arbiter": arbiter}[args[0]](root))
            return 0
        if len(args) in (3, 5) and args[0] == "arbiter" and args[2] == "--repair" \
                and (len(args) == 3 or (args[3] == "--out" and "/" not in args[4])):
            print(arbiter(pathlib.Path(args[1]), repair=True, out=args[4] if len(args) == 5 else "arbiter-repair-in.md"))
            return 0
        if args[:1] == ["span-verify"] and len(args) in (4, 6) and args[2] == "--base" \
                and (len(args) == 4 or args[4] == "--tag"):
            root = pathlib.Path(args[1])
            print(span_verify(root, root / args[3], args[5] if len(args) == 6 else None))
            return 0
        if args[:1] == ["rows"] and len(args) in (5, 7) and args[3] == "--by" and (len(args) == 5 or args[5] == "--need"):
            root = pathlib.Path(args[1])
            reds, n = rows(root, args[2], args[4], args[6] if len(args) == 7 else None)
            for r in reds:
                sys.stderr.write("ROWS RED %s\n" % r)
            if reds:
                sys.stderr.write("ROWS RED (%d); verify.jsonl unchanged\n" % len(reds))
                return 1
            print("ROWS OK %d verify.jsonl rows by %s" % (n, args[4]))
            return 0
    except (CannotRun, SD.Untyped, LS.Unreadable, RANK.Unreadable) as exc:
        sys.stderr.write("back-lane: %s\n" % exc)
        return 2
    sys.stderr.write(__doc__)
    return 2


# --- selftest -------------------------------------------------------------------------------------
GLOBEX_RUN = ROOT / "quality-bar/fixtures/globex/run"
GLOBEX_GOOD = ROOT / "tools/fixtures/schema/good/globex"
ASSEMBLE = ROOT / "tools/fixtures/assemble"
SCREENS = ROOT / "quality-bar/fixtures/globex/screens"


def globex_root(tmp):
    """The Globex fixture root as the back lane sees it after the author: typed reader and names, the
    shape and allocation b1's author read, a 05-thesis.json locking the repaired spine, and b1's
    author-high-1 prose assembled into brief.json."""
    root = pathlib.Path(tmp) / "root"
    root.mkdir()
    for p in GLOBEX_RUN.iterdir():
        if not p.name.startswith("brief") and p.name != "reader.json":
            (root / p.name).symlink_to(p)
    for f in ("reader.json", "names.json"):
        shutil.copy(GLOBEX_GOOD / f, root / f)
    for f in ("06-shape.json", "sources.tsv"):
        shutil.copy(ASSEMBLE / f, root / f)
    shutil.copy(ROOT / "tools/fixtures/back-lane/comp-globex.md", root / "comp-globex.md")
    (root / "06-budget.tsv").write_text("slot\twords\titems\nquick-take\t150\t3\n", encoding="utf-8")
    cand = RANK.candidate_of(read_json(SCREENS / "items/CTL-spine-b.json"), "CTL-spine")
    (root / "05-thesis.json").write_text(json.dumps({"candidates": [cand], "verdicts": [], "rank": ["CTL-spine"],
                                                     "locked": "CTL-spine"}), encoding="utf-8")
    asm = _load("assemble", "tools/assemble.py")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        code = asm.main(["assemble.py", str(ASSEMBLE / "author-high-1.prose.json"), str(root), "--run-date", "2026-10-11"])
    if code != 0:
        raise CannotRun("the selftest root did not assemble (exit %s)" % code)
    return root


def selftest():
    fails, n = [], [0]

    def case(label, ok, got=""):
        n[0] += 1
        if not ok:
            fails.append("%s: %s" % (label, str(got)[:400]))

    def run(*argv):
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
            code = main(["back-lane.py"] + [str(a) for a in argv])
        return code, out.getvalue() + err.getvalue()

    # the schema files the runner passes stay equal to their sources
    fs = read_json(ROOT / "references/schemas/finding.schema.json")
    finding = {k: v for k, v in fs.items() if k not in ("$schema", "$id", "title")}
    for name in ("findings", "truth"):
        case("%s.schema.json's finding is finding.schema.json's" % name,
             read_json(ROOT / ("references/schemas/%s.schema.json" % name))["$defs"]["finding"] == finding)
    lv = read_json(ROOT / "references/schemas/line-verdicts.schema.json")
    case("line-verdicts.schema.json is line-screen.py's line_schema()",
         {k: v for k, v in lv.items() if k not in ("$schema", "$id", "title", "description")} == LS.line_schema())

    with tempfile.TemporaryDirectory() as tmp:
        root = globex_root(tmp)
        brief = read_json(root / "brief.json")
        ids = list(SD.hashes(brief))

        # brief-check's own digest, one sentence per rule it grades: P1 is the rule run 2's
        # arbiter-repair broke while no prompt stated it.
        bc = _load("brief_check", "tools/brief-check.py")
        digest = bc.rules_digest() if hasattr(bc, "rules_digest") else ""
        p1 = next((l for l in digest.splitlines() if l.startswith("- P1: ")), "")
        case("brief-check's digest carries P1's sentence", bool(p1), digest[:200])

        code, out = run("author", root)
        text = (root / "author-in.md").read_text(encoding="utf-8") if code == 0 else ""
        heads = re.findall(r"^# ([A-Z ]+)$", text, re.M)
        case("author: author-in.md carries every section in order", code == 0 and heads == [
            "READER", "THESIS", "ALLOCATION", "BUDGET", "CAPS", "RULES", "SOURCES FOR THE AUTHOR", "SHAPE", "NAMES",
            "ROWS", "FOUNDER CARD", "VOICE CARD",
            "REFUSALS", "EXEMPLARS"], (code, out, heads))
        rules_in = text.split("\n# RULES\n", 1)[-1].split("\n# SOURCES FOR THE AUTHOR\n", 1)[0]
        case("author: brief-check's rules digest is inlined whole under RULES, P1 with it",
             bool(p1) and digest in rules_in and p1 in rules_in, rules_in[:300])
        rows_part = text.split("# ROWS", 1)[-1].split("# FOUNDER CARD", 1)[0]
        joined = [json.loads(l) for l in rows_part.splitlines() if l.startswith("{")]
        want = set(CLAIM_RE.findall((root / "06-allocation.md").read_text(encoding="utf-8")
                                    + (root / "06-shape.json").read_text(encoding="utf-8")))
        case("author: every allotted ID is pre-joined once, with code's known",
             {r["id"] for r in joined} >= want and len(joined) == len({r["id"] for r in joined})
             and all(isinstance(r.get("known"), bool) for r in joined), (len(joined), len(want)))
        case("author: the caps are inlined, the schema's own (the CLI strips x-maxWords)",
             "| recommendations[].next_step | 13 |" in text and "| quick_take[].lede | 14 |" in text)
        case("author: the comp-globex.md ranges the allocation names are inlined",
             "## comp-globex.md lines 88-105" in text and "## comp-globex.md lines 74-86" in text,
             re.findall(r"^## comp-.*$", text, re.M))
        known = {r["id"]: r["known"] for r in joined}
        case("author: a client-site row is known, a rival's is not", known.get("C-018") is True and known.get("C-193") is False,
             {k: known.get(k) for k in ("C-018", "C-193")})

        code, out = run("critics", root)
        fm = (root / "critic-in/founder.md").read_text(encoding="utf-8") if code == 0 else ""
        case("critics: the founder batch is line-screen's prompt over every line",
             code == 0 and fm.startswith("Screen every item in ITEMS against CARD") and "# PAGE" in fm
             and (root / "brief-author.json").read_bytes() == (root / "brief.json").read_bytes(), out)
        tm = (root / "critic-in/truth.md").read_text(encoding="utf-8") if code == 0 else ""
        case("critics: the truth page lists every span id", all(("\n%s | " % i) in tm for i in ids),
             [i for i in ids if ("\n%s | " % i) not in tm][:3])

        # founder majority: three recorded screeners in the ls-g layout, one test red 2 of 3 on a line
        items, _, _ = LS.page_items(brief, RANK.read_claims(root / "claims.jsonl"), ctx(root)[2])
        target = items[0]
        for k, copy_ in enumerate(COPIES):
            vs = []
            for it in items:
                v = {"item": it["id"]}
                for t in LS.L_TESTS:
                    v[t] = {"pass": True, "quote": it["text"][:30], "why": "fixture"}
                if it is target and k < 2:
                    v["STANCE"] = {"pass": False, "quote": it["text"][:30], "why": "fixture red"}
                vs.append(v)
            write(root / ("findings/founder-%s.json" % copy_), json.dumps({"verdicts": vs}))
        code, out = run("founder", root)
        got = read_json(root / "findings/founder.json", {}).get("findings", []) if code == 0 else []
        stance = [f for f in got if f["rule"] == "STANCE"]
        case("founder: a 2-of-3 STANCE red is one finding on the line's span; no other model red",
             code == 0 and len(stance) == 1 and stance[0]["span_id"] in ids and stance[0]["quote"] == target["text"][:30]
             and all(f["rule"] in ("STANCE", "NEW-code", "LEAD-code") for f in got), got[:3])
        bad = SCHEMA.load_schema(ROOT / "references/schemas/findings.schema.json")
        errs = []
        SCHEMA.validate({"findings": got}, bad, bad.get("$defs", {}), "$", errs, ROOT / "references/schemas")
        case("founder: findings/founder.json validates against findings.schema.json", not errs, errs[:3])

        # truth rows: every span PASS but one FAIL; coverage is a gate
        truth = {"findings": [], "spans": [{"span_id": i, "verdict": "PASS", "note": ""} for i in ids]}
        truth["spans"][1] = {"span_id": ids[1], "verdict": "FAIL", "note": "plural unsupported"}
        tp = write(root / "findings/truth.json", json.dumps(dict(truth, spans=truth["spans"][:-1])))
        code, out = run("rows", root, tp, "--by", "critic-truth")
        case("rows: a span with no verdict reds and writes nothing",
             code == 1 and ids[-1] in out and not (root / "verify.jsonl").exists(), out)
        write(tp, json.dumps(dict(truth, spans=truth["spans"] + [{"span_id": "qt.9.lede.0", "verdict": "PASS", "note": ""}])))
        code, out = run("rows", root, tp, "--by", "critic-truth")
        case("rows: a verdict on no span of the brief reds", code == 1 and "qt.9.lede.0" in out, out)
        write(tp, json.dumps(truth))
        code, out = run("rows", root, tp, "--by", "critic-truth")
        vrows = [json.loads(l) for l in (root / "verify.jsonl").read_text().splitlines()] if code == 0 else []
        case("rows: one row per span at its hash", code == 0 and len(vrows) == len(ids)
             and all(r["span_hash"] == SD.hashes(brief)[r["span_id"]] for r in vrows), out)
        bad = SCHEMA.check(ROOT / "references/schemas/verify-row.schema.json", root / "verify.jsonl")
        case("rows: verify.jsonl validates against verify-row.schema.json", not bad, bad[:3])

        code, out = run("repair-needed", root)
        case("repair-needed: exit 0 and the FAIL span named while its hash fails", code == 0 and ids[1] in out, out)

        # the arbiter's input carries every critic's finding
        for critic in ("voice", "redteam"):
            write(root / ("findings/%s.json" % critic), json.dumps({"findings": [
                {"critic": critic, "span_id": ids[0], "rule": "P4", "severity": "MINOR", "quote": "x", "note": "kit-%s" % critic}]}))
        code, out = run("arbiter", root)
        am = (root / "arbiter-in.md").read_text(encoding="utf-8") if code == 0 else ""
        case("arbiter: findings from every critic that wrote, numbered, and each field's cap",
             code == 0 and "kit-voice" in am and "kit-redteam" in am and '"F-001"' in am
             and re.search(r"## qt\.0\.lede \(\d+ of 14 words\)", am), out)
        case("arbiter: each slot's allotted IDs are listed (A1)", '"slot": "quick-take"' in am and '"C-195"' in am)
        gates = am.split("# GATE REDS", 1)[-1].split("# RULES", 1)[0]
        case("arbiter: brief-check's reds on the page are listed as G- ids (b1's prose reds KR-H)",
             '"G-001"' in gates and "KR-H" in gates, gates[:300])
        rules_am = am.split("\n# RULES\n", 1)[-1].split("\n# ALLOTTED\n", 1)[0]
        case("arbiter: brief-check's rules digest is inlined whole under RULES, P1 with it",
             bool(p1) and digest in rules_am and p1 in rules_am, rules_am[:300])
        # Each span line names the most words its fix_new may hold with the rest of its field as it
        # stands (X3): run 2's repair took a 14-of-14 lede to 15 from a field total alone.
        lede = brief["quick_take"][0]["lede"]
        room = len(lede[0]["t"].split()) + field_caps()["qt.lede"] - SCHEMA.words(lede)
        limit = re.compile(r"^%s \| [^\n|]* \| %d words, at most %d \| " % (
            re.escape(lede[0]["id"]), len(lede[0]["t"].split()), room), re.M)
        case("arbiter: each span line shows its words and the most its fix_new may hold (X3)",
             bool(limit.search(am)), [l for l in am.splitlines() if l.startswith(lede[0]["id"])])
        code, out = run("arbiter", root, "--repair")
        rm = (root / "arbiter-repair-in.md").read_text(encoding="utf-8") if code == 0 else ""
        case("arbiter --repair: the FAIL span alone, with its note", code == 0 and '"R-001"' in rm
             and "plural unsupported" in rm and '"R-002"' not in rm, out)
        case("arbiter --repair: brief-check's rules digest is inlined whole, P1 with it",
             bool(p1) and digest in rm and p1 in rm, rm[:300])
        case("arbiter --repair: each span line shows its words and the most its fix_new may hold (X3)",
             bool(limit.search(rm)), [l for l in rm.splitlines() if l.startswith(lede[0]["id"])])
        code, out = run("arbiter", root, "--repair", "--out", "arbiter-repair-r2-in.md")
        case("arbiter --repair --out: a later round's input under its own name, the same text (S13)",
             code == 0 and read_text(root / "arbiter-repair-r2-in.md") == rm, out)

        # span-verify: a patched span, its neighbours and the spans sharing its rows
        patched = copy.deepcopy(brief)
        sp = SD.spans(patched)
        target_id = ids[1]
        sp[target_id]["t"] = sp[target_id]["t"].rstrip() + " now."
        write(root / "brief.json", json.dumps(patched, ensure_ascii=False))
        code, out = run("span-verify", root, "--base", "brief-author.json")
        got = read_json(root / "span-verify-set.json", {}).get("spans", []) if code == 0 else []
        want = verify_set(root, patched, brief)
        same = [i for i, s in SD.spans(patched).items()
                if set(ids_of(s.get("c"))) & set(ids_of(sp[target_id].get("c"))) and i != target_id]
        case("span-verify: the changed span, its neighbours and same-row spans; no unchanged PASS span besides",
             code == 0 and got and got[0] in (ids[0], target_id) and target_id in got and ids[0] in got
             and set(same) <= set(got) and got == list(want)
             and all(set(w) <= {"changed"} or not w[0].startswith("no verify") for w in want.values()), (out, got))
        code, out = run("repair-needed", root)
        case("repair-needed: exit 1 once the FAIL span's hash moved", code == 1, out)

    for f in fails:
        sys.stderr.write("SELFTEST FAIL: %s\n" % f)
    if fails:
        sys.stderr.write("SELFTEST RED (%d of %d)\n" % (len(fails), n[0]))
        return 1
    sys.stdout.write("SELFTEST OK (%d cases)\n" % n[0])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
