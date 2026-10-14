#!/usr/bin/env python3
"""The brief.json lint: a brief.json against `build/web/brief.schema.json` and the run it cites.

WHY THIS EXISTS. Stage 7 writes data, not prose: `$BRIEF_ROOT/brief.json`, which `build/web.py`
renders (`73-web-plan.md` § The contract, W4 `:106-125`). Every fact the page prints reaches it as
a span `{"t", "c"}`, so the page is only as honest as the link from each span to its ledger row.
This script grades that link before anything renders.

THE RULES, each tagged in its finding:
  S   the schema, plus the references its dialect cannot state: a slug naming no company, a map
      missing a company, a row whose cells do not match the columns, a cell whose `mark` disagrees
      with its `c`, a span both `q` and `g`, a span `id` two spans carry, a `cmp` naming no other
      span of its own field.
  C1  a `c` absent from claims.jsonl.
  C2  a cited row whose `url` is no `url` or `final_url` in pages/index.tsv: L11's match. Whether
      the fetch reached its page is `claims-check.py --pages`'s question, not this one.
  N1  a numeral in a text that is in no numeral of its rows' claim, quote, qualifier or scope
      (T:para-s.json `_about`, plus `scope` by ruling A). A text citing nothing holds no digit.
  Q1  a `q` span whose t is not verbatim in the quote of an `en` row it cites.
  Q2  a curly quote in a text that is not a `q` span, or a straight double quote in any text
      (W2-rulings.md G29). An apostrophe is not a quote.
  Q3  a `g` span whose t is not verbatim in the gloss of a non-`en` row it cites.
  M1  a map answer that is neither yes nor no.
  M2  an axis on which every company gives one answer: it separates nobody.
  M3  a map answer's `integration` ID that is not in its own `c`: the INTEG lead `build/web.py`
      prints before that source would sit on a card that does not show it (W2-rulings.md G10).
  M4  a non-empty `integration` under a yes: the card would print its yes line and then call its
      own evidence an integration, not a customer (36 R3).
  U1  a matrix cell marked `unknown` whose t does not open "Unknown" or "Not known": a finding
      worded as a cited No ("Brands not named") reads as one (W4-rulings.md G77 (ii)).
  P1  a span stating a count of pages the run read ("absent from 3 Calder pages", "On 12 of its
      pages"): process on the page (RF7, G77 (iii)). Its test is PAGES_RE, a numeral then at
      most three words, then "pages".
  R1  a Quick take body span restating its lede (W4-rulings.md G91 (i)): the lede cites exactly
      one row X, the span cites only X, and the span adds no digit run and no capitalised
      non-initial word absent from the lede, nor a company or rival name, matched in any case.
      A body adds a new figure, name or fact.
  L2  a legend sentence whose text before its colon holds two or more distinct matrix-cell or
      map-label texts: labels merged into a fragment (G91 (ii)). A multi-word label matches in
      any case, a one-word label by case, so a common noun is no label. One label, or none,
      stays green; a label found only inside a longer label it hit, in any case, counts as that one.
  D1  an ID on two or more chips of one prose section: the quick take, the recommendations, the
      moves, the open questions or the matrix legend (W4-rulings.md G92 (iii)). `chips` places
      them as `build/web.py` does: a sentence citing anything is one chip.
  G1  a logo key without a gated record in $BRIEF_ROOT/logos/logos.json (`logo_gate`).
  H1  an authored heading (`moves_heading`, `matrix.heading`) the page cannot carry (G34): over
      RAIL_MAX characters, or not in the spine headings' sentence case, where a word after the first
      opens on a capital and is no acronym, no word of a company's name and no word the
      ledger's claims capitalise past their first word (a proper noun).
  L1  $BRIEF_ROOT/sources.tsv off stage 4's contract (`04-research.md` § Page inputs): a header
      other than `url<TAB>label`, a row without two columns, a URL twice, an empty label, a label
      over 31 characters, or a distinct claims.jsonl `url` with no row (W2-rulings.md G17).
  A1  slot drift from stage 6's allocation (W2-rulings.md G41), graded only where $BRIEF_ROOT holds
      06-shape.json, the web allocation; a fixture root or a run before W14 has none to drift
      from. A slot's `c` or `integration` ID that is on none of that slot's `- Claims:` or ICP
      lines in 06-allocation.md, nor, for the map and the matrix, in 06-shape.json; or a slot's
      `- Evidence clause` ID the slot no longer cites and no table row under 07-author.md
      § Forced departures names in that slot: the row's cell under the header `Field`, found by
      name with case and markup ignored, opens with the slot id, `slot` before it allowed
      (W3-rulings.md G58); or a row there under no header with a `Field` column, which names no
      slot. The slots and their fields are budget-check's WEB_FIELDS, and the lines are its
      `allocation_claims`, so the two tools read one allocation one way. The typed author records
      the same excuse as data: each `{slot, id}` in $BRIEF_ROOT/departures.json (assemble.py writes
      it from the prose's `departures`) names that ID in that slot, as a § Forced departures row does.
  F1  a matrix that would scroll at 1248 px and up, where the template hangs it at MATRIX_PX
      (W2-rulings.md G46). Its measure is the matrix's min-content width, modelled offline: per
      column, the widest piece that cannot break plus the cell's padding, summed. A piece is a
      word (a hyphenated word stays whole, as `web.py` wraps it nowrap); a cited cell's last word
      carries its no-break space and source-number chip, numbered as the page numbers its URLs.
      Advances are the face's default instance, read from its hmtx with struct; headers scale by
      the face's measured 500 and 600 weight ratios. Over MATRIX_FIT reds.

  The founder-reader rules (Globex design.md § 2 R1a, R1b and Gap rows; § 4). They grade prose spans
  only, never matrix cells or the map's names. A row is KNOWN when the ledger types it `known`, else
  by claims-check's host rule on the client's domain and known hosts. Those facts, the job ad's URL
  and the role title come from the brief (`company.domain`, `jd_url`, `role`), else from
  $BRIEF_ROOT/reader.json; a legacy brief with neither keys KR-H and JD on nothing.
  KR-H a span every row of which is known, unless its `cmp` names a span of its field citing a row
      that is not: the founder's own fact appears only as a comparison half (R1b).
  JD  a span citing a row read off the job ad (its URL's host is the JD's, exactly), unless it is a
      `cmp` comparison half (D13).
  NC  a span citing nothing that names the founder's company. Its numeral half is N1's.
  PL  a span or authored heading naming the job ad: "posting", "job post", "job description", "this
      role", the role title or the JD's host.
  X1  one claim ID in X1_MIN or more prose sections: D1 counts within one section only.
  X2  an allotted quick-take slot no point carries (`icp`, when 06-allocation.md's quick-take section
      has an ICP line), or an `icp` point holding no known span with a `cmp` pair: the ICP slot is a
      comparison (D14). The `slot` enum itself is the schema's, S.
  M5  a map `no` answer citing a verified row whose `metric` is `<party>:<thing>` for a party other
      than the answering company, whose claim holds a figure, and whose thing contains the axis's
      `metric`: the no denies its own evidence. An axis with no `metric` is not graded.
  VL  a sentence in the verdict lexicon VERDICT_RES. WARN only: printed as `WARN:`, never counted in
      the exit code; the runner logs it from stderr. The lexicon was fitted to the Globex fixtures.
  X3  `--proposal` only (PROPOSAL_RULES): a field a patch list changes, over the schema's x-maxWords.
      `--proposal <patches.json> <brief.json> <BRIEF_ROOT>` lays design.md § 3's patches
      ({span_id, fix_old, fix_new, c[]}) on a copy of the brief; a patch naming no span, or whose
      fix_old is not that span's text, is exit 2.

THE DIGEST. RULE_DIGEST holds one author-facing sentence per rule above (None, with the reason, for
a rule no authored text can break). `--rules-digest` prints it, and back-lane.py inlines it into the
author's and the arbiter's input, so a prompt states every rule its gate grades. The selftest reds
a rule with no entry.

LEDGER SHAPE IS NOT GRADED HERE: `claims-check.py --ledger` owns it. This file imports that
script's ledger reader, index reader and normaliser, so the two read one file one way.

THE VALIDATOR is `tools/schema.py`'s, shared with every typed artefact. It knows exactly its
dialect's keywords, and a keyword it does not know is exit 2, so the schema cannot carry a bound
nobody enforces. `jsonschema` is not a CI dependency.

EXIT CODES. 0 green. 1 findings. 2 the script could not do its job: bad usage, a missing or
unreadable claims.jsonl, index or schema, or an unknown schema keyword.

PRECONDITION: none. No network, no browser, no environment variable.
"""

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import pathlib
import re
import shutil
import struct
import sys
import tempfile
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "build/web/brief.schema.json"
FIXTURES = ROOT / "tools/fixtures/web"
# Pinned by the operator's 2026-10-08 ruling (`W4-build.md` § Rulings applied, 2): a list, as T has it.
LOGOS_JSON = "logos/logos.json"
# H1's rail cap. Measured 2026-10-09 in Chrome and WebKit at 1440 and 1024 on the contents rail,
# 60 random word phrases per length (W15-build.md § Fix round 1): to 23 characters every phrase fits
# two lines; at 26, 13% wrap to three; at 29 ("Which Rival Moves Need Action", gate-01) 77% do. 26 is
# live T's longest rail heading, "Where each rival is moving", and the cap is T's own edge. It is
# necessary, not sufficient: web-check's layout.rail stays the gate.
RAIL_MAX = 26
HEADING_WORD_RE = re.compile(r"[^\W\d_][\w’'-]*")
SOURCES_TSV = "sources.tsv"
SOURCES_HEADER = "url\tlabel"
LABEL_MAX = 31  # live T's longest label, the contract's cap; build/web.py reds the same bound


def _claims_check():
    spec = importlib.util.spec_from_file_location("claims_check", ROOT / "tools/claims-check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CC = _claims_check()


def _budget_check():
    sys.dont_write_bytecode = True  # no tools/__pycache__/ left in the tree
    spec = importlib.util.spec_from_file_location("budget_check", ROOT / "tools/budget-check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BU = _budget_check()  # WEB_FIELDS, allocation_claims, read_shape: A1 reads the allocation as it does
SHAPE = "06-shape.json"
READER = "reader.json"  # the typed reader frame (design.md § 3); KR-H, JD and PL fall back to it
ALLOCATION = "06-allocation.md"
AUTHOR = "07-author.md"
DEPARTURES = "departures.json"  # the typed author's forced departures (tools/assemble.py writes it)
FORCED = "Forced departures"  # stage 7 step 3's section of 07-author.md
CLAIM_ID_RE = re.compile(r"\bC-\d{3,}\b")
# F1's inputs (G46), each read from the template or the face it names. From 1248 px the matrix is
# 800 wide (`template.html` .tbl--mx; web-check `judge_matrix`). Cells set 400 at 16 px, headers
# 500, the hiring company's 600 (`strong`), chips 500 at 12 with 4 px padding a side, a 16 px floor
# (border-box) and 2 px either side of each U+2009. Cell padding is 7 a side, none outside the
# first and last columns. W500 and W600 are the face's own advance ratios to 400 over [A-Za-z0-9],
# measured with fontTools on 2026-10-09.
FONT = ROOT / "build/web/assets/plex-sans-var-latin.ttf"
WEB_PY = ROOT / "build/web.py"
MATRIX_PX = 800
TD_PX, CHIP_PX, CHIP_PAD, CHIP_MIN, SEP_PX, CELL_PAD = 16, 12, 8, 16, 4, 7
W500, W600 = 1.0208, 1.0342
# The cap on the model. Calibrated 2026-10-09 against Chrome's own min-content width at 1440 on four
# pages (W16-build.md § Rulings applied, G46). The model reads 785.3, 791.5 and 792.0 on three that
# fit (Chrome 788.0, 795.0, 795.8), and 938.5 on one that scrolls (Chrome 940.5). Chrome reads 1.9
# to 3.8 px over the model, so the cap is MATRIX_PX less 4. WebKit reads narrower on every page.
MATRIX_FIT = MATRIX_PX - 4
DIGITS_RE = re.compile(r"\d+")
# A quote mark: a double curly quote, a guillemet, an opening single quote, or a `’` no letter
# precedes. `’` after a letter is an apostrophe (`company’s`, `partners’`) and stays legal.
CURLY_RE = re.compile(r"[“”„‟«»‹›‘‚‛]|(?<!\w)’")
ANSWERS = ("yes", "no")
AXES = ("across", "down")

# --- the validator: tools/schema.py's, the one every typed artefact is graded by ------------------
def _schema_tool():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("schema_tool", ROOT / "tools/schema.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SC = _schema_tool()
SchemaError, validate, words = SC.SchemaError, SC.validate, SC.words


def load_schema(path=SCHEMA):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SchemaError("cannot read %s (%s)" % (path, exc))


# --- walking a brief, whatever its shape ---------------------------------------------------------
# Every rule but S reads the brief through these, and each tolerates a malformed brief by skipping
# what is not the right type, so one red shape never hides the other rules' findings.
def lst(d, key):
    v = d.get(key) if isinstance(d, dict) else None
    return v if isinstance(v, list) else []


def obj(d, key):
    v = d.get(key) if isinstance(d, dict) else None
    return v if isinstance(v, dict) else {}


def ids(c):
    """A `c` as a list of IDs: null is [], one ID is [it], an array is its strings."""
    if isinstance(c, str):
        return [c]
    return [x for x in c if isinstance(x, str)] if isinstance(c, list) else []


def shows_quote(row):
    """Whether the page quotes this ledger row on its card (G76): a row not `unfound`, in `en` (a
    row with no lang is `en`, as `build/web.py` reads it), with no gloss. Any other row prints its
    gloss behind a lead. The one test: `web.py` picks a card's evidence line by it, and
    budget-check's `integration` rule holds stage 6's lists to it (36 R3)."""
    return (row.get("state") not in ("unfound", "blocked") and row.get("lang", CC.EN) == CC.EN
            and not row.get("gloss"))


PILOT_RE = re.compile(r"\bpilot", re.I)


def carries_yes(rows):
    """Whether these ledger rows can carry a map yes (W4-rulings.md G92 (i)): no claim says
    "integration", `web.py`'s 36 R3 test, and not every row is a pilot by its claim or qualifier.
    An integration or a pilot is not a customer. The quote is not read: a French quote can say
    "pilotons" (we control). No rows is nothing to judge, so True; a missing ID is budget-check's
    url rule. budget-check's `answer` rule calls it."""
    if any("integration" in str(r.get("claim", "")) for r in rows):
        return False
    return not (rows and all(PILOT_RE.search("%s %s" % (r.get("claim", ""), r.get("qualifier", "")))
                             for r in rows))


def span_arrays(brief):
    """(where, spans) for every span array, in page order; a malformed one is []."""
    for i, p in enumerate(lst(brief, "quick_take")):
        for f in ("lede", "body"):
            yield "quick_take[%d].%s" % (i, f), lst(p, f)
    for i, r in enumerate(lst(brief, "recommendations")):
        for f in ("test", "why", "next_step"):
            yield "recommendations[%d].%s" % (i, f), lst(r, f)
    for i, m in enumerate(lst(brief, "moves")):
        for f in ("change", "meaning"):
            yield "moves[%d].%s" % (i, f), lst(m, f)
    for i, q in enumerate(lst(brief, "open_questions")):
        yield "open_questions[%d]" % i, q if isinstance(q, list) else []
    yield "matrix.legend", lst(obj(brief, "matrix"), "legend")


def texts(brief):
    """Every text that can carry a fact, as (where, t, c, q, g): each span, each matrix cell, and
    each map answer's name."""
    for where, arr in span_arrays(brief):
        for j, s in enumerate(arr):
            if isinstance(s, dict) and isinstance(s.get("t"), str):
                yield ("%s[%d]" % (where, j), s["t"], s.get("c"), s.get("q") is True,
                       s.get("g") is True)
    mx = obj(brief, "matrix")
    for i, row in enumerate(lst(mx, "rows")):
        for j, cell in enumerate(lst(row, "cells")):
            if isinstance(cell, dict) and isinstance(cell.get("t"), str):
                yield ("matrix.rows[%d].cells[%d]" % (i, j), cell["t"], cell.get("c"), False, False)
    for i, a in enumerate(lst(obj(brief, "map"), "answers")):
        for axis in AXES:
            ans = obj(a, axis)
            if ans:
                name = ans.get("name")
                yield ("map.answers[%d].%s" % (i, axis), name if isinstance(name, str) else "",
                       ans.get("c"), False, False)


def entities(brief):
    """The hiring company, then each rival, as the dicts that are dicts."""
    return [e for e in [brief.get("company")] + lst(brief, "rivals") if isinstance(e, dict)]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def logo_gate(record, root):
    """Whether one logos.json record is gated. The operator's ruling of 2026-10-08 (`W4-build.md`
    § Rulings applied, 2), written once: W13's `fetch-logos.py` imports this and restates none of it. Returns the
    failures; [] means gated.

    Both branches: `page_sha256` is the sha256 of page_file's pages/index.tsv row and of its bytes
    now, and `sha256` is the logo file's. Then, with `href` set, href is a substring of page_file's
    bytes; with `href` null (an inline <svg>), the logo file's bytes are. Either way the logo comes
    verbatim from a page the run fetched (provenance rule 1).
    """
    root = pathlib.Path(root)
    if not isinstance(record, dict):
        return ["the record is not an object"]

    def inside(key):
        rel = record.get(key)
        if not isinstance(rel, str) or not rel:
            return None
        p = (root / rel).resolve()
        return p if p.is_relative_to(root.resolve()) and p.is_file() else None

    page, logo = inside("page_file"), inside("file")
    if page is None or logo is None:
        return ["%s %r is no file inside the run" % (("page_file", record.get("page_file"))
                                                     if page is None else ("file", record.get("file")))]
    page_bytes, logo_bytes = page.read_bytes(), logo.read_bytes()
    fails = []
    want = record.get("page_sha256")
    rows = [e for e in CC.read_index(root / "pages") if e.get("path") == record.get("page_file")]
    if not rows or any(e.get("sha256") != want for e in rows):
        fails.append("page_sha256 is not the sha256 of page_file's pages/index.tsv row")
    if sha(page_bytes) != want:
        fails.append("page_file's bytes no longer hash to page_sha256")
    if not logo_bytes or sha(logo_bytes) != record.get("sha256"):
        fails.append("the logo file is empty or does not hash to sha256")
    href = record.get("href")
    if href is None:
        if logo_bytes not in page_bytes:
            fails.append("href is null and the logo file's bytes are not in page_file's bytes")
    elif not isinstance(href, str) or not href:
        fails.append("href is neither null nor a non-empty string")
    elif href.encode("utf-8") not in page_bytes:
        fails.append("href %r is not in page_file's bytes" % href)
    return fails


# --- the rules ------------------------------------------------------------------------------------
class Ctx:
    """One check's inputs, read once. The ledger and index readers are claims-check's own, so an
    unreadable or foreign file is that script's exit 2."""

    def __init__(self, brief_path, root, schema, brief=None):
        """`brief`, when given, is the parsed brief and `brief_path` is not read (fixture-test grades
        a brief it has typed in memory)."""
        self.root, self.schema, self.parse_error = pathlib.Path(root), schema, None
        self.brief_path = pathlib.Path(brief_path) if brief_path else None
        self._client = None
        try:
            self.brief = brief if brief is not None else json.loads(pathlib.Path(brief_path).read_text(encoding="utf-8"))
        except ValueError as exc:
            self.parse_error, self.brief = "brief.json is not JSON (%s)" % exc, {}
        if not isinstance(self.brief, dict):
            self.parse_error, self.brief = "brief.json is not a JSON object", {}
        self.rows = {}
        for _, row in CC.read_ledger(self.root / "claims.jsonl")[0]:
            if isinstance(row.get("id"), str):
                self.rows.setdefault(row["id"], row)
        self.index = CC.read_index(self.root / "pages")

    def cited(self, c):
        return [self.rows[i] for i in ids(c) if i in self.rows]

    def client(self):
        """The founder's facts the reader rules key on: {name, short, domain, known_hosts, jd_host,
        role}. Each comes from the brief (`company.domain`, `jd_url`, `role`) or, where the brief
        lacks it, from $BRIEF_ROOT/reader.json (`company.domain`, `known_hosts`, `role.jd_url`,
        `role.title`). With neither, KR-H, JD and PL's per-run terms have nothing to key on, so a
        legacy brief is graded as before. Read once: typing a brief never changes them."""
        if self._client is None:
            try:
                reader = json.loads((self.root / READER).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                reader = {}
            reader = reader if isinstance(reader, dict) else {}
            co, rco, role = obj(self.brief, "company"), obj(reader, "company"), obj(reader, "role")
            pick = lambda *vals: next((v for v in vals if isinstance(v, str) and v.strip()), None)  # noqa: E731
            jd_url = pick(self.brief.get("jd_url"), role.get("jd_url"))
            jd_host = (urllib.parse.urlparse(jd_url).hostname or "").lower() if jd_url else ""
            self._client = {
                "name": pick(co.get("name"), rco.get("name")), "short": pick(co.get("short")),
                "domain": (pick(co.get("domain"), rco.get("domain")) or "").lower() or None,
                "known_hosts": sorted({h.lower() for h in lst(reader, "known_hosts") if isinstance(h, str)}
                                      | ({jd_host} if jd_host else set())),
                "jd_host": jd_host or None, "role": pick(self.brief.get("role"), role.get("title"))}
        return self._client

    def known(self, cid):
        """Whether row `cid` is a fact the founder already holds (R1b): its typed `known` when the
        ledger carries one, else claims-check's host rule on the client's domain and known hosts. A
        row absent from the ledger is not known."""
        row = self.rows.get(cid)
        if row is None:
            return False
        if isinstance(row.get("known"), bool):
            return row["known"]
        cl = self.client()
        return CC.row_known(row.get("url"), cl["domain"], cl["known_hosts"])

    def jd_row(self, cid):
        """Whether row `cid` was read off the job ad itself: its URL's host is the JD's, exactly."""
        url = str((self.rows.get(cid) or {}).get("url") or "")
        host = (urllib.parse.urlparse(url).hostname or "").lower()
        return bool(host) and host == self.client()["jd_host"]

    def logos(self):
        path = self.root / LOGOS_JSON
        try:
            records = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return None, "%s cannot be read (%s)" % (LOGOS_JSON, exc)
        return (records, None) if isinstance(records, list) else (None, "%s is not a list" % LOGOS_JSON)


def rule_S(ctx):
    if ctx.parse_error:
        return [ctx.parse_error]
    out, b = [], ctx.brief
    validate(b, ctx.schema, ctx.schema.get("$defs", {}), "brief", out)
    slugs = [e.get("slug") for e in entities(b) if isinstance(e.get("slug"), str)]
    known = set(slugs)
    if len(slugs) != len(known):
        out.append("brief: a slug names more than one company: %s" % sorted(slugs))
    mx = obj(b, "matrix")
    cols = lst(mx, "columns")
    out += ["matrix.columns[%d]: %r names no company" % (i, s) for i, s in enumerate(cols) if s not in known]
    for i, row in enumerate(lst(mx, "rows")):
        cells = lst(row, "cells")
        if len(cells) != len(cols):
            out.append("matrix.rows[%d]: %d cells for %d columns" % (i, len(cells), len(cols)))
        for j, cell in enumerate(cells):
            mark = cell.get("mark") if isinstance(cell, dict) else None
            if mark in ("cited", "unknown") and (mark == "unknown") != (cell.get("c") is None):
                out.append("matrix.rows[%d].cells[%d]: mark %r with c %r; unknown is exactly the cell "
                           "that cites nothing" % (i, j, mark, cell.get("c")))
    out += ["moves[%d]: rival %r names no company" % (i, m["rival"]) for i, m in enumerate(lst(b, "moves"))
            if isinstance(m, dict) and isinstance(m.get("rival"), str) and m["rival"] not in known]
    answered = [a.get("company") for a in lst(obj(b, "map"), "answers") if isinstance(a, dict)]
    out += ["map.answers: %r answers %d times, want once" % (s, answered.count(s))
            for s in sorted(known) if answered.count(s) != 1]
    out += ["map.answers: %r names no company" % s for s in answered if isinstance(s, str) and s not in known]
    out += ["%s: a span is both q and g" % w for w, _, _, q, g in texts(b) if q and g]
    # A span id is a key (design.md § 3): one span each, and a cmp names another span of its field.
    seen = {}
    for where, arr in span_arrays(b):
        here = {s.get("id") for s in arr if isinstance(s, dict)}
        for j, s in enumerate(arr):
            sid = s.get("id") if isinstance(s, dict) else None
            if isinstance(sid, str) and seen.setdefault(sid, "%s[%d]" % (where, j)) != "%s[%d]" % (where, j):
                out.append("%s[%d]: span id %r is also %s's" % (where, j, sid, seen[sid]))
            if isinstance(s, dict) and "cmp" in s and (s["cmp"] == sid or s["cmp"] not in here):
                out.append("%s[%d]: cmp %r names no other span of this field" % (where, j, s["cmp"]))
    return out


def rule_C1(ctx):
    return ["%s: %s is not in claims.jsonl" % (w, i)
            for w, _, c, _, _ in texts(ctx.brief) for i in ids(c) if i not in ctx.rows]


def rule_C2(ctx):
    urls = {e.get("url") for e in ctx.index} | {e.get("final_url") for e in ctx.index}
    out, seen = [], set()
    for w, _, c, _, _ in texts(ctx.brief):
        for i in ids(c):
            if i in ctx.rows and i not in seen:
                seen.add(i)
                url = str(ctx.rows[i].get("url", "")).strip()
                if not url or url not in urls:
                    out.append("%s: row %s cites %r, which is no url or final_url in pages/index.tsv"
                               % (w, i, url))
    return out


# N1's sources: `73-web-plan.md:115` names claim, quote and qualifier. Ruling A (2026-10-08) adds
# `scope`, a field of the cited row as in claims-check's B1: live T prints C-262's scope numeral in
# "All but 6 plans", and C-262's claim writes "six".
N1_FIELDS = ("claim", "quote", "qualifier", "scope")


def numerals(text):
    """Whole digit runs by value, so `9` and the `09` of an ISO date are one numeral, and `24` is
    never found inside `2024`."""
    return [str(int(d)) for d in DIGITS_RE.findall(text)]


def rule_N1(ctx):
    out = []
    for w, t, c, _, _ in texts(ctx.brief):
        digits, rows = numerals(t), ctx.cited(c)
        if digits and not ids(c):
            out.append("%s: digit run(s) %s in a text that cites no row" % (w, digits))
        elif digits and rows:
            src = set(numerals(" ".join(str(r.get(f, "")) for r in rows for f in N1_FIELDS)))
            missing = [d for d in digits if d not in src]
            if missing:
                out.append("%s: digit run(s) %s are in no claim, quote, qualifier or scope of %s"
                           % (w, missing, ids(c)))
    return out


def holds(rows, field, t, lang_ok):
    """Whether t, normalised as claims-check's B4 does, is verbatim in `field` of a row whose lang
    passes `lang_ok`. A missing lang passes neither test: it fails closed both ways."""
    want = CC.norm(t)
    return bool(want) and any(lang_ok(r.get("lang")) and want in CC.norm(str(r.get(field) or ""))
                              for r in rows)


def rule_Q1(ctx):
    out = []
    for w, t, c, q, _ in texts(ctx.brief):
        if q and not ids(c):
            out.append("%s: a q span cites no row" % w)
        elif q and ctx.cited(c) and not holds(ctx.cited(c), "quote", t, lambda lang: lang == CC.EN):
            out.append("%s: q span %r is not verbatim in the quote of an en row it cites (%s)"
                       % (w, t[:60], ids(c)))
    return out


def rule_Q2(ctx):
    out = ["%s: curly quote %r in a text that is not a q span; a quotation goes through q" % (w, m.group(0))
           for w, t, _, q, _ in texts(ctx.brief) if not q for m in [CURLY_RE.search(t)] if m]
    # G29: a straight " sets a passage in quotes that B4 and Q1 never see, since both read only the
    # curly pair; in any text, q spans included, it reds.
    return out + ["%s: a straight double quote; a quotation is a q span, printed in curly quotes" % w
                  for w, t, _, _, _ in texts(ctx.brief) if '"' in t]


def rule_Q3(ctx):
    out = []
    for w, t, c, _, g in texts(ctx.brief):
        if g and not ids(c):
            out.append("%s: a g span cites no row" % w)
        elif g and ctx.cited(c) and not holds(ctx.cited(c), "gloss", t,
                                              lambda lang: isinstance(lang, str) and lang != CC.EN):
            out.append("%s: g span %r is not verbatim in the gloss of a non-en row it cites (%s)"
                       % (w, t[:60], ids(c)))
    return out


def rule_M1(ctx):
    return ["map.answers[%d].%s: answer %r is neither yes nor no" % (i, axis, obj(a, axis).get("answer"))
            for i, a in enumerate(lst(obj(ctx.brief, "map"), "answers")) for axis in AXES
            if obj(a, axis) and obj(a, axis).get("answer") not in ANSWERS]


def rule_M2(ctx):
    answers = lst(obj(ctx.brief, "map"), "answers")
    out = []
    for axis in AXES:
        given = [json.dumps(obj(a, axis).get("answer")) for a in answers if obj(a, axis)]
        if len(given) > 1 and len(set(given)) == 1:
            out.append("map.%s: every company answers %s, so the axis separates nobody" % (axis, given[0]))
    return out


def rule_M3(ctx):
    return ["map.answers[%d].%s: integration %s is not in its c %s" % (i, axis, x, ids(obj(a, axis).get("c")))
            for i, a in enumerate(lst(obj(ctx.brief, "map"), "answers")) for axis in AXES
            for x in lst(obj(a, axis), "integration") if x not in ids(obj(a, axis).get("c"))]


def rule_M4(ctx):
    return ["map.answers[%d].%s: integration %s under a yes; INTEG belongs under a no only" % (i, axis, lst(obj(a, axis), "integration"))
            for i, a in enumerate(lst(obj(ctx.brief, "map"), "answers")) for axis in AXES
            if obj(a, axis).get("answer") == "yes" and lst(obj(a, axis), "integration")]


UNKNOWN_OPENS = re.compile(r"(Unknown|Not known)\b")


def rule_U1(ctx):
    return ["matrix.rows[%d].cells[%d]: an unknown cell reads %r; open it \"Unknown\" or \"Not known\""
            % (i, j, cell.get("t")) for i, row in enumerate(lst(obj(ctx.brief, "matrix"), "rows"))
            for j, cell in enumerate(lst(row, "cells")) if isinstance(cell, dict)
            and cell.get("mark") == "unknown" and not UNKNOWN_OPENS.match(str(cell.get("t", "")).lstrip())]


# A numeral, at most three words (a word may hold an inner dot, as a domain-style name does, but no
# comma or end stop), then "pages". Plural only, as D-004 measured: "one page per agent" and "5 logos
# on its partner page" stay green. A year, or a day before its month, is a date, not a count.
NUMBER_WORDS = ("one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
                "fifteen|sixteen|seventeen|eighteen|nineteen|twenty|a dozen|dozens")
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
PAGES_RE = re.compile(r"\b(?:(?!(?:19|20)\d\d\b)(?!\d{1,2}\s+(?:%s)\b)\d[\d,]*|%s)\b"
                      r"(?:\s+[^\s,;:!?]*[^\s.,;:!?]){0,3}?\s+pages\b" % (MONTHS, NUMBER_WORDS), re.I)


def rule_P1(ctx):
    return ["%s: %r states a count of pages read; say what is unknown, not how much was read (RF7)"
            % (w, m.group(0)) for w, t, _, _, _ in texts(ctx.brief) for m in [PAGES_RE.search(t)] if m]


SENTENCE_END_RE = re.compile(r"[.!?]\s+$")


def word_key(w):
    """A word as R1 compares it: lower case, a possessive 's dropped, so "Calder's" is "calder"."""
    return re.sub(r"[’']s$", "", w).lower()


def has_name(name, text):
    """Whether a company name sits in text on word edges, in any case ("lumen.io", "LUMEN.IO")."""
    return bool(re.search(r"(?<!\w)%s(?!\w)" % re.escape(name), text, re.I))


def new_names(body, start, end, lede, names):
    """The names in body[start:end] that the lede lacks, as word_keys. A name is a word holding any
    capital ("heatGrid") that opens no sentence of the joined body, so a span continuing a sentence
    is read in place; or a company or rival name in any case ("lumen.io") (W18-fix11-verify.md
    Rec 2)."""
    out = {word_key(m.group(0)) for m in HEADING_WORD_RE.finditer(body, start, end)
           if any(ch.isupper() for ch in m.group(0)) and body[:m.start()].strip()
           and not SENTENCE_END_RE.search(body[:m.start()])}
    out -= {word_key(w) for w in HEADING_WORD_RE.findall(lede)}
    return out | {n.lower() for n in names if has_name(n, body[start:end]) and not has_name(n, lede)}


def rule_R1(ctx):
    out = []
    names = {e[k] for e in entities(ctx.brief) for k in ("name", "short") if isinstance(e.get(k), str)}
    for i, p in enumerate(lst(ctx.brief, "quick_take")):
        lede = [s for s in lst(p, "lede") if isinstance(s, dict)]
        cited = {x for s in lede for x in ids(s.get("c"))}
        if len(cited) != 1:
            continue
        lt = "".join(s["t"] for s in lede if isinstance(s.get("t"), str))
        spans = [s if isinstance(s, dict) and isinstance(s.get("t"), str) else {"t": ""}
                 for s in lst(p, "body")]
        body, ends = "", []
        for s in spans:
            body += s["t"]
            ends.append(len(body))
        for j, s in enumerate(spans):
            t, start = s["t"], ends[j] - len(s["t"])
            if (t and set(ids(s.get("c"))) == cited and not set(numerals(t)) - set(numerals(lt))
                    and not new_names(body, start, ends[j], lt, names)):
                out.append("quick_take[%d].body[%d]: %r restates its lede's only row %s, adding no "
                           "figure or name; a body adds a new figure, name or fact to its lede"
                           % (i, j, t.strip(), min(cited)))
    return out


def labels(brief):
    """Every matrix-cell text and map-axis label (`yes`, `no`), stripped, the empty ones dropped."""
    out = {c["t"].strip() for row in lst(obj(brief, "matrix"), "rows") for c in lst(row, "cells")
           if isinstance(c, dict) and isinstance(c.get("t"), str)}
    out |= {obj(obj(brief, "map"), axis)[k].strip() for axis in AXES for k in ANSWERS
            if isinstance(obj(obj(brief, "map"), axis).get(k), str)}
    return out - {""}


def rule_L2(ctx):
    legend = "".join(s["t"] for s in lst(obj(ctx.brief, "matrix"), "legend")
                     if isinstance(s, dict) and isinstance(s.get("t"), str))
    # A multi-word label in any case: mid-sentence a merged label is lower-cased (W18-fix11-verify.md
    # Rec 1). A one-word label by case, so a common noun ("partner", "tariff") is no label (-verify-2
    # Rec 2).
    out, known = [], labels(ctx.brief)
    for sent in re.split(r"(?<=[.!?])\s+", legend.strip()):
        head = sent.split(":", 1)[0] if ":" in sent else None
        hit = [x for x in known if head and re.search(r"(?<!\w)%s(?!\w)" % re.escape(x), head,
                                                      re.I if " " in x else 0)]
        # A label inside a longer one it hit is that one label: "Utilities pay" is not two. Labels
        # differing only by case are one. Containment ignores case, as the match does (-verify-3 Nice 1).
        hit = sorted({x.lower() for x in hit
                      if not any(x.lower() != y.lower() and x.lower() in y.lower() for y in hit)})
        if len(hit) >= 2:
            out.append("matrix.legend: %r lists %d labels %s before its colon; write each qualifier as "
                       "its own sentence with a verb" % (sent, len(hit), hit))
    return out


CHIP_END_RE = re.compile(r"[.?!][”’)]?(?=\s|$)")


def chips(blocks):
    """The chips a prose section prints, as sets of IDs, placed as `build/web.py` places them (§8):
    a run of spans on one `c` closes with its IDs; the IDs go to the sentence they close in, a
    question's to the next sentence; a sentence citing anything is one chip. A block is one `p`,
    `li` or `td`, its spans in order. A `q` span's printed quotes move no sentence end, so are
    left out."""
    out = []
    for block in blocks:
        text, refs = "", []
        for k, s in enumerate(block):
            text += s["t"]
            nxt = block[k + 1] if k + 1 < len(block) else None
            if s.get("c") is not None and (nxt is None or nxt.get("c") != s.get("c")):
                refs.append((len(text), ids(s["c"])))
        ends = [(m.end(), text[m.start()] == "?") for m in CHIP_END_RE.finditer(text)]
        got = [set() for _ in ends]
        for pos, cids in refs:
            k = next((k for k, (e, _) in enumerate(ends) if e >= pos), None)
            if k is not None:  # claims after the last sentence end: web.py's own error
                got[k] |= set(cids)
        for k, (_, question) in enumerate(ends[:-1]):
            if question and got[k]:
                got[k + 1] |= got[k]
                got[k] = set()
        out += [g for g in got if g]
    return out


def prose_sections(brief):
    """{section: its blocks}, each block a list of span dicts: the page's chipped prose. The quick
    take's lede and body, and a recommendation's test, why and next step, are one block apiece,
    joined at their seams as `web.py` joins them; a move's change and meaning are two."""
    sp = lambda arr: [s for s in arr if isinstance(s, dict) and isinstance(s.get("t"), str)]
    gap = [{"t": " ", "c": None}]

    def seam(arr):
        arr = [dict(s) for s in sp(arr)]
        if arr:
            arr[0]["t"], arr[-1]["t"] = arr[0]["t"].lstrip(), arr[-1]["t"].rstrip()
        return arr
    return {
        "quick_take": [seam(lst(p, "lede")) + gap + seam(lst(p, "body")) for p in lst(brief, "quick_take")],
        "recommendations": [seam(lst(r, "test")) + gap + seam(lst(r, "why")) + [{"t": " Next step: ", "c": None}]
                            + sp(lst(r, "next_step")) for r in lst(brief, "recommendations")],
        "moves": [sp(lst(m, f)) for m in lst(brief, "moves") for f in ("change", "meaning")],
        "open_questions": [sp(q) for q in lst(brief, "open_questions") if isinstance(q, list)],
        "matrix.legend": [sp(lst(obj(brief, "matrix"), "legend"))],
    }


def rule_D1(ctx):
    out = []
    for section, blocks in prose_sections(ctx.brief).items():
        count = {}
        for chip in chips(blocks):
            for cid in chip:
                count[cid] = count.get(cid, 0) + 1
        out += ["%s: %s is on %d chips; one chip per ID per prose section (W4-rulings.md G92 (iii))"
                % (section, cid, n) for cid, n in sorted(count.items()) if n > 1]
    return out


def rule_G1(ctx):
    out, records, err = [], None, None
    for e in entities(ctx.brief):
        key = e.get("logo")
        if not isinstance(key, str):
            continue
        if records is None and err is None:
            records, err = ctx.logos()
        who = "%s (logo %r)" % (e.get("name"), key)
        hits = [r for r in records or [] if isinstance(r, dict) and r.get("slug") == key]
        if err:
            out.append("%s: %s" % (who, err))
        elif len(hits) != 1:
            out.append("%s: %d records in %s carry that slug, want 1" % (who, len(hits), LOGOS_JSON))
        else:
            out += ["%s: not gated: %s" % (who, f) for f in logo_gate(hits[0], ctx.root)]
    return out


def rule_H1(ctx):
    names = {w for e in entities(ctx.brief) for f in ("name", "short") if isinstance(e.get(f), str)
             for w in HEADING_WORD_RE.findall(e[f])}
    # A proper noun keeps its capital in sentence case. The ledger names them: a word the run's own
    # claims capitalise past their first word (a place, a register, a partner) may open on one here.
    for row in ctx.rows.values():
        names |= set(HEADING_WORD_RE.findall(str(row.get("claim", "")))[1:])
    out = []
    for where, text in (("moves_heading", ctx.brief.get("moves_heading")),
                        ("matrix.heading", obj(ctx.brief, "matrix").get("heading"))):
        if not isinstance(text, str) or not text:
            continue
        if len(text) > RAIL_MAX:
            out.append("%s %r: %d characters, over the rail's %d" % (where, text, len(text), RAIL_MAX))
        words = HEADING_WORD_RE.findall(text)
        if words and not words[0][0].isupper():
            out.append("%s %r: a heading opens on a capital" % (where, text))
        title = [w for w in words[1:] if w[0].isupper() and not w.isupper() and w not in names]
        if title:
            out.append("%s %r: %s capitalised; the page's headings are sentence case ('Open questions')"
                       % (where, text, ", ".join(title)))
    return out


def rule_L1(ctx):
    path = ctx.root / SOURCES_TSV
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        return ["%s cannot be read (%s)" % (SOURCES_TSV, exc)]
    if not lines or lines[0] != SOURCES_HEADER:
        return ["%s header is %r, want %r" % (SOURCES_TSV, lines[0] if lines else "", SOURCES_HEADER)]
    out, seen = [], {}
    for n, line in enumerate(lines[1:], start=2):
        cols = line.split("\t")
        if len(cols) != 2:
            out.append("%s:%d: %d columns, want 2" % (SOURCES_TSV, n, len(cols)))
            continue
        url, label = cols
        if url in seen:
            out.append("%s:%d: %s already has a row, at line %d" % (SOURCES_TSV, n, url, seen[url]))
        seen.setdefault(url, n)
        if not label.strip():
            out.append("%s:%d: an empty label for %s" % (SOURCES_TSV, n, url))
        elif len(label) > LABEL_MAX:
            out.append("%s:%d: label over %d characters: %r" % (SOURCES_TSV, n, LABEL_MAX, label))
    cited = sorted({r["url"] for r in ctx.rows.values() if isinstance(r.get("url"), str) and r["url"].strip()})
    return out + ["%s has no row for %s, which claims.jsonl cites" % (SOURCES_TSV, u) for u in cited if u not in seen]


def slot_cites(brief):
    """{web slot: [(where, claim ID)]}: every `c` under each slot's fields in budget-check's
    WEB_FIELDS. `integration` is skipped: M3 holds it inside its answer's `c`."""
    out = {}

    def walk(node, where, slot):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "c":
                    out[slot] += [(where, i) for i in ids(v)]
                elif k != "integration":
                    walk(v, "%s.%s" % (where, k), slot)
        elif isinstance(node, list):
            for j, x in enumerate(node):
                walk(x, "%s[%d]" % (where, j), slot)
    for slot, (fields, _) in BU.WEB_FIELDS.items():
        out[slot] = []
        for f in fields:
            walk(brief.get(f), f, slot)
    return out


def forced_rows(root):
    """The table rows under 07-author.md's § Forced departures heading, to the next heading at its
    level or above. A row anywhere else in the file names nothing; no file names nothing."""
    try:
        lines = (root / AUTHOR).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    rows, level = [], None
    for line in lines:
        head = re.match(r"(#+)\s", line)
        if head and level and len(head.group(1)) <= level:
            level = None
        if head and FORCED in line:
            level = len(head.group(1))
        elif level and line.startswith("|"):
            rows.append(line)
    return rows


def forced_pairs(root):
    """((slot, ID) pairs, headless) for the rows under § Forced departures. The slot is the first
    word of the row's cell in the column its table's header names `Field`, or its second when the
    first is `slot` (W3-rulings.md G58), so a row excuses its ID in its own slot only. The column is
    found by name, never by position: a header is the row above a `|---|` row, and its cell matches
    `field` with case, `*`, `_` and backticks ignored. `headless` counts the rows under a header
    with no such cell, or under none; they name nothing, and A1 reds them by the column's name."""
    rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in forced_rows(root)]
    sep = [all(re.fullmatch(r":?-+:?", c) for c in cells) for cells in rows]
    pairs, field, headless = set(), None, 0
    for n, cells in enumerate(rows):
        if sep[n]:
            continue
        if n + 1 < len(rows) and sep[n + 1]:
            keys = [c.strip("*_` ").lower() for c in cells]
            field = keys.index("field") if "field" in keys else None
            continue
        if field is None:
            headless += 1
            continue
        words = cells[field].split() if field < len(cells) else []
        words = words[1:] if words[:1] == ["slot"] else words
        slot = words[0].strip(",:`") if words else ""
        pairs.update((slot, cid) for cid in CLAIM_ID_RE.findall("|".join(cells)))
    return pairs, headless


def typed_departures(root, name=DEPARTURES):
    """{(slot, ID)} from $BRIEF_ROOT/departures.json, `{"departures": [{slot, id, reason}]}`; an
    absent or unreadable file, or an entry without a slot and an ID, names nothing."""
    try:
        doc = json.loads((root / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    rows = doc.get("departures") if isinstance(doc, dict) else None
    return {(d["slot"], d["id"]) for d in rows or [] if isinstance(d, dict)
            and isinstance(d.get("slot"), str) and isinstance(d.get("id"), str)}


def sidecar_departures(ctx):
    """The departures apply-patches --out wrote beside a proposed brief: <stem>.departures.json."""
    p = ctx.brief_path
    return typed_departures(p.parent, p.stem + ".departures.json") if p is not None else set()


def rule_A1(ctx):
    if not (ctx.root / SHAPE).is_file():
        return []
    try:
        allowed = {}
        for slot, cid in BU.allocation_claims(ctx.root, ("claims", "icp")):
            allowed.setdefault(slot, set()).add(cid)
        _, smap, matrix = BU.read_shape(ctx.root)
        allowed.setdefault("map", set()).update(
            i for e in smap["answers"] for axis in AXES for i in e[axis]["c"])
        allowed.setdefault("matrix", set()).update(
            i for row in matrix["rows"] for cell in row["cells"] if cell != "Unknown" for i in cell)
        evidence = BU.allocation_claims(ctx.root, ("evidence",))
    except BU.Unreadable as exc:
        return ["the allocation cannot be read: %s" % exc]
    cites = slot_cites(ctx.brief)
    named, headless = forced_pairs(ctx.root)
    named = named | typed_departures(ctx.root) | sidecar_departures(ctx)
    out = ["slot %s: %s cites %s, on none of the slot's `- Claims:` or ICP lines in %s%s"
           % (slot, where, cid, ALLOCATION, " nor in %s" % SHAPE if slot in ("map", "matrix") else "")
           for slot, pairs in cites.items() for where, cid in pairs if cid not in allowed.get(slot, set())]
    if headless:
        out.append("%s § %s: %d row(s) sit under no header with a `Field` column, so they name no "
                   "slot; head the column that names the slot `Field`" % (AUTHOR, FORCED, headless))
    for slot, cid in dict.fromkeys(evidence):
        if slot in cites and cid not in {c for _, c in cites[slot]} and (slot, cid) not in named:
            out.append("slot %s: evidence-clause %s is off the page, and no forced departure names it in "
                       "this slot: no %s entry (the prose's `departures`) and no row whose `Field` cell under "
                       "%s § %s opens with this slot" % (slot, cid, DEPARTURES, AUTHOR, FORCED))
    return out


_FACE = {}


def face(path=FONT):
    """(units per em, advances by glyph, {codepoint: glyph}) of a TrueType face, by struct alone:
    the head, hhea, hmtx and cmap (format 4 or 12) tables."""
    if path in _FACE:
        return _FACE[path]
    d = pathlib.Path(path).read_bytes()
    tab = {}
    for i in range(struct.unpack(">H", d[4:6])[0]):
        tag, _, off, _ = struct.unpack(">4sIII", d[12 + 16 * i:28 + 16 * i])
        tab[tag] = off
    upm = struct.unpack(">H", d[tab[b"head"] + 18:tab[b"head"] + 20])[0]
    n = struct.unpack(">H", d[tab[b"hhea"] + 34:tab[b"hhea"] + 36])[0]
    adv = [struct.unpack(">H", d[tab[b"hmtx"] + 4 * i:tab[b"hmtx"] + 4 * i + 2])[0] for i in range(n)]
    co, cmap = tab[b"cmap"], {}
    for i in range(struct.unpack(">H", d[co + 2:co + 4])[0]):
        so = co + struct.unpack(">I", d[co + 8 + 8 * i:co + 12 + 8 * i])[0]
        fmt = struct.unpack(">H", d[so:so + 2])[0]
        if fmt == 12:
            for g in range(struct.unpack(">I", d[so + 12:so + 16])[0]):
                a, b, s = struct.unpack(">III", d[so + 16 + 12 * g:so + 28 + 12 * g])
                for c in range(a, b + 1):
                    cmap.setdefault(c, s + c - a)
        elif fmt == 4:
            seg = struct.unpack(">H", d[so + 6:so + 8])[0] // 2
            ends = struct.unpack(">%dH" % seg, d[so + 14:so + 14 + 2 * seg])
            s0 = so + 16 + 2 * seg
            starts = struct.unpack(">%dH" % seg, d[s0:s0 + 2 * seg])
            deltas = struct.unpack(">%dh" % seg, d[s0 + 2 * seg:s0 + 4 * seg])
            r0 = s0 + 4 * seg
            ros = struct.unpack(">%dH" % seg, d[r0:r0 + 2 * seg])
            for k in range(seg):
                for c in range(starts[k], min(ends[k], 0xFFFE) + 1):
                    if not ros[k]:
                        g = (c + deltas[k]) & 0xFFFF
                    else:
                        p = r0 + 2 * k + ros[k] + 2 * (c - starts[k])
                        g = struct.unpack(">H", d[p:p + 2])[0]
                        g = (g + deltas[k]) & 0xFFFF if g else 0
                    cmap.setdefault(c, g)
    _FACE[path] = (upm, adv, cmap)
    return _FACE[path]


def px(text, size, scale=1.0):
    """The advance width of `text` at `size` px in the default instance, times `scale`."""
    upm, adv, cmap = face()
    return sum(adv[min(cmap.get(ord(ch), 0), len(adv) - 1)] for ch in text) * size / upm * scale


def source_numbers(brief, rows):
    """{url: number}: one per URL, ranked by first citation in the page's order (`web.py` §17):
    quick take, the map (the hiring company first), recommendations, moves, matrix, legend, open
    questions."""
    order = []

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "c":
                    order.extend(ids(v))
                elif k != "integration":
                    walk(v)
        elif isinstance(node, list):
            for x in node:
                walk(x)
    co = obj(brief, "company").get("slug")
    answers = sorted(lst(obj(brief, "map"), "answers"), key=lambda a: a.get("company") != co)
    mx = obj(brief, "matrix")
    for part in (lst(brief, "quick_take"), answers, lst(brief, "recommendations"), lst(brief, "moves"),
                 lst(mx, "rows"), lst(mx, "legend"), lst(brief, "open_questions")):
        walk(part)
    num = {}
    for cid in order:
        url = (rows.get(cid) or {}).get("url")
        if isinstance(url, str) and url.strip() and url not in num:
            num[url] = len(num) + 1
    return num


def matrix_floors(brief, rows, why=False):
    """[(column header, px)]: each matrix column's min-content width, padding included (F1). With
    why, [(header, px, what sets it)]: the word, and the chip glued to it, a repair must shorten."""
    corner = re.search(r'^MATRIX_CORNER = "([^"]*)"', WEB_PY.read_text(encoding="utf-8"), re.M).group(1)
    mx, co = obj(brief, "matrix"), obj(brief, "company").get("slug")
    names = {e.get("slug"): e.get("short") or e.get("name") or "" for e in entities(brief)}
    cols, num = lst(mx, "columns"), source_numbers(brief, rows)
    out = []
    for k in range(len(cols) + 1):
        head = corner if k == 0 else names.get(cols[k - 1], "")
        cands = [(px(p, TD_PX, W600 if k and cols[k - 1] == co else W500), "header %r" % p) for p in head.split()]
        for row in lst(mx, "rows"):
            if k == 0:
                cands += [(px(p, TD_PX), "row label %r" % p) for p in str(row.get("label", "")).split()]
                continue
            cell = lst(row, "cells")[k - 1] if k - 1 < len(lst(row, "cells")) else {}
            toks = str(cell.get("t", "")).split()
            words = [px(p, TD_PX) for p in toks] or [0]
            got = sorted({num[r["url"]] for r in (rows.get(i) for i in ids(cell.get("c"))) if r and r.get("url") in num})
            chip = ""
            if cell.get("mark") == "cited" and got:
                text = "".join(str(n) for n in got)
                words[-1] += px("\u00a0", TD_PX) + max(CHIP_MIN, CHIP_PAD + px(text, CHIP_PX, W500)
                                                       + (len(got) - 1) * (px("\u2009", CHIP_PX, W500) + SEP_PX))
                chip = " + a %d-source chip" % len(got)
            label = row.get("label", "")
            cands += [(w, "row %r word %r%s" % (label, toks[j] if j < len(toks) else "", chip if j == len(words) - 1 else ""))
                      for j, w in enumerate(words)]
        best, what = max(cands or [(0, "")], key=lambda x: x[0])
        width = best + (CELL_PAD if k in (0, len(cols)) else 2 * CELL_PAD)
        out.append((head, width, what) if why else (head, width))
    return out


def rule_F1(ctx):
    floors = matrix_floors(ctx.brief, ctx.rows, why=True)
    total = sum(w for _, w, _ in floors)
    if total <= MATRIX_FIT:
        return []
    return ["the matrix needs %.1f px, over the %d px it may take at 1248 px and up (MATRIX_FIT) by %.1f px, "
            "so it scrolls. Shorten the word that sets a wide column, or move one of its cell's claim IDs to "
            "another cell: per column %s" % (total, MATRIX_FIT, total - MATRIX_FIT, "; ".join(
                "%s %.1f px set by %s" % f for f in floors))]


# --- the founder-reader rules (Globex design.md § 2 R1a, R1b and Gap rows; § 4) ----------------------
SECTION_RE = re.compile(r"^(quick_take|recommendations|moves|open_questions|matrix\.legend)")
PL_TERMS = ("posting", "job post", "job description", "this role")
X1_MIN = 3  # sections one claim ID may reach before it reads as a repeat (design.md § 2 Gap)
# VL's lexicon, find-G § 6's banned-pattern row. FITTED to the Globex fixtures, so its recall on a new
# run is unknown: a tripwire beside the stance screen, never that screen (design.md § 4, § 7).
VERDICT_RES = [re.compile(p, re.I) for p in (
    r"\bparity\b", r"\bnot an? (edge|advantage|wedge|moat)\b", r"\bnot (a )?differen\w*",
    r"\bnot set \w+( \w+)? apart\b", r"\bdo(es)? not set \w+( \w+)? apart\b", r"\bleaves? \w+ behind\b",
    r"\bclaims? (the same|most)\b", r"\bmake the difference\b")]
WARN_RULES = ("VL",)  # printed and logged by the runner from stderr, never counted in the exit code


def prose_spans(brief):
    """(field where, its span array, index, span) for every prose span with a string t. Matrix cells
    and the map are not prose: the reader rules never grade them."""
    for where, arr in span_arrays(brief):
        for j, s in enumerate(arr):
            if isinstance(s, dict) and isinstance(s.get("t"), str):
                yield where, arr, j, s


def compared(ctx, arr, s):
    """Whether span s is a comparison half: its `cmp` names another span of its field that cites a
    row the founder does not already hold (KR-H, D13, D14)."""
    want = s.get("cmp")
    if not isinstance(want, str):
        return False
    return any(isinstance(x, dict) and x is not s and x.get("id") == want
               and any(not ctx.known(c) for c in ids(x.get("c"))) for x in arr)


def rule_KRH(ctx):
    out = []
    for where, arr, j, s in prose_spans(ctx.brief):
        own = ids(s.get("c"))
        if own and all(ctx.known(c) for c in own) and not compared(ctx, arr, s):
            out.append("%s[%d]: every row it cites (%s) sits on the founder's own hosts, so it tells the "
                       "founder what the founder already holds; such a span appears only as a `cmp` "
                       "comparison half beside a span citing a rival row%s"
                       % (where, j, ", ".join(own), " (its cmp %r names none)" % s["cmp"] if "cmp" in s else ""))
    return out


def rule_JD(ctx):
    if not ctx.client()["jd_host"]:
        return []
    out = []
    for where, arr, j, s in prose_spans(ctx.brief):
        jd = [c for c in ids(s.get("c")) if ctx.jd_row(c)]
        if jd and not compared(ctx, arr, s):
            out.append("%s[%d]: cites the job ad (%s); the page may cite a job-ad row only as a `cmp` "
                       "comparison half beside a rival row (D13)" % (where, j, ", ".join(jd)))
    return out


def rule_NC(ctx):
    cl = ctx.client()
    names = [n for n in (cl["name"], cl["short"]) if n]
    out = []
    for where, _, j, s in prose_spans(ctx.brief):
        if ids(s.get("c")):
            continue
        hit = [n for n in names if has_name(n, s["t"])]
        if hit:
            out.append("%s[%d]: %r names the founder's company (%s) and cites no row; c is null only on "
                       "connective text with no numeral, name or quote (brief-contract.md)"
                       % (where, j, s["t"].strip(), hit[0]))
    return out


def rule_PL(ctx):
    cl = ctx.client()
    terms = list(PL_TERMS) + [x for x in (cl["role"], cl["jd_host"]) if x]
    pat = re.compile("|".join(r"(?<!\w)%s(?!\w)" % re.escape(w) for w in terms), re.I)
    texts_ = [("%s[%d]" % (where, j), s["t"]) for where, _, j, s in prose_spans(ctx.brief)]
    texts_ += [(w, t) for w, t in (("moves_heading", ctx.brief.get("moves_heading")),
                                   ("matrix.heading", obj(ctx.brief, "matrix").get("heading"))) if isinstance(t, str)]
    return ["%s: %r names the job ad (%r); the page speaks about the market, never about the posting "
            "it answers" % (w, t.strip(), m.group(0)) for w, t in texts_ for m in [pat.search(t)] if m]


def rule_X1(ctx):
    found = {}
    for where, _, j, s in prose_spans(ctx.brief):
        sec = SECTION_RE.match(where).group(1)
        for c in ids(s.get("c")):
            found.setdefault(c, {}).setdefault(sec, []).append("%s[%d]" % (where, j))
    return ["%s: cited in %d prose sections (%s), at %s; one fact makes one point, so a row in %d or more "
            "sections reads as a repeat" % (c, len(secs), ", ".join(secs), ", ".join(u for us in secs.values() for u in us), X1_MIN)
            for c, secs in sorted(found.items()) if len(secs) >= X1_MIN]


def allotted_slots(root):
    """{slot: [claim ID]}: the quick-take slots stage 6 allots beyond the thesis. `icp` when
    06-allocation.md's quick-take section carries an ICP line naming a row. No allocation, none."""
    if not (root / ALLOCATION).is_file():
        return {}
    try:
        icp = [cid for slot, cid in BU.allocation_claims(root, ("icp",)) if slot == "quick-take"]
    except BU.Unreadable:
        return {}
    return {"icp": icp} if icp else {}


def rule_X2(ctx):
    points = [p for p in lst(ctx.brief, "quick_take") if isinstance(p, dict)]
    out = ["quick_take: stage 6 allots an %s point (its rows %s) and no point carries slot %s"
           % (slot, ", ".join(rows), slot) for slot, rows in sorted(allotted_slots(ctx.root).items())
           if slot not in {p.get("slot") for p in points}]
    for i, p in enumerate(lst(ctx.brief, "quick_take")):
        if not isinstance(p, dict) or p.get("slot") != "icp":
            continue
        pairs = [s for f in ("lede", "body") for s in lst(p, f) if isinstance(s, dict) and ids(s.get("c"))
                 and all(ctx.known(c) for c in ids(s.get("c"))) and compared(ctx, lst(p, f), s)]
        if not pairs:
            out.append("quick_take[%d]: an icp point is a comparison (D14): it needs a span citing the "
                       "founder's own buyer rows whose `cmp` names a span citing a rival's" % i)
    return out


def rule_M5(ctx):
    m, out = obj(ctx.brief, "map"), []
    who = {e.get("slug"): {str(e.get(k)).lower() for k in ("name", "short") if isinstance(e.get(k), str)}
           for e in entities(ctx.brief)}
    for i, a in enumerate(lst(m, "answers")):
        for axis in AXES:
            metric, ans = obj(m, axis).get("metric"), obj(a, axis)
            if not isinstance(metric, str) or not metric.strip() or ans.get("answer") != "no":
                continue
            for cid in ids(ans.get("c")):
                row = ctx.rows.get(cid) or {}
                party, sep, thing = str(row.get("metric", "")).partition(":")
                party = party.strip()
                if (not sep or not party or row.get("state") != "verified"
                        or not DIGITS_RE.search(str(row.get("claim", "")))
                        or party.lower() in who.get(a.get("company"), set()) | {str(row.get("subject", "")).lower()}):
                    continue
                if re.search(r"(?<!\w)%s(?!\w)" % re.escape(metric.strip()), thing, re.I):
                    out.append("map.answers[%d].%s: %s answers no on %r, yet its row %s states %s for %s; "
                               "a no cannot cite the result it denies" % (i, axis, a.get("company"),
                                                                          metric, cid, thing.strip(), party))
    return out


def rule_VL(ctx):
    out = []
    for where, arr in span_arrays(ctx.brief):
        text, bounds = "", []
        for j, s in enumerate(arr):
            if isinstance(s, dict) and isinstance(s.get("t"), str):
                bounds.append((j, len(text), len(text) + len(s["t"])))
                text += s["t"]
        cuts = [0] + [mm.end() for mm in CHIP_END_RE.finditer(text)] + [len(text)]
        for a, b in zip(cuts, cuts[1:]):
            sent = text[a:b]
            if sent.strip() and any(p.search(sent) for p in VERDICT_RES):
                spans = ", ".join("%s[%d]" % (where, j) for j, x, y in bounds if x < b and y > a)
                out.append("%s: %r reads as a verdict on the founder (VL tripwire: logged, never counted)"
                           % (spans, sent.strip()))
    return out


def rule_X3(ctx):
    """A proposed edit over its field's x-maxWords cap. The cap is the schema's, read by the one
    validator; `ctx.touched`, when set, limits the grade to the fields a proposal changed."""
    found, out = [], []
    validate(ctx.brief, ctx.schema, ctx.schema.get("$defs", {}), "brief", found)
    touched = getattr(ctx, "touched", None)
    for msg in found:
        m = re.match(r"brief\.(\S+): (\d+) words, over the cap of (\d+)$", msg)
        if m and (touched is None or m.group(1) in touched):
            out.append("%s: a proposed text of %s words, over its field's cap of %s; a fix stays inside "
                       "the cap of the text it replaces (X3)" % m.groups())
    return out


# One registry: the order findings print in, and the list the selftest proves case by case.
RULES = (("S", rule_S), ("C1", rule_C1), ("C2", rule_C2), ("N1", rule_N1), ("Q1", rule_Q1),
         ("Q2", rule_Q2), ("Q3", rule_Q3), ("M1", rule_M1), ("M2", rule_M2), ("M3", rule_M3), ("M4", rule_M4),
         ("U1", rule_U1), ("P1", rule_P1), ("R1", rule_R1), ("L2", rule_L2), ("D1", rule_D1), ("G1", rule_G1),
         ("H1", rule_H1), ("L1", rule_L1), ("A1", rule_A1), ("F1", rule_F1),
         ("KR-H", rule_KRH), ("JD", rule_JD), ("NC", rule_NC), ("PL", rule_PL), ("X1", rule_X1),
         ("X2", rule_X2), ("M5", rule_M5), ("VL", rule_VL))
# Rules graded on a proposed edit, not a page: `--proposal` runs them on the brief a patch list
# would leave. fixture-test reads both registries.
PROPOSAL_RULES = (("X3", rule_X3),)

# What each rule asks of the text, one sentence apiece, for the agents who write it: back-lane.py
# inlines `rules_digest()` into the author's input and the arbiter's RULES, so their prompts state
# exactly the rules this file grades (vandelay run 2: arbiter-repair red on P1, which no prompt
# stated). A rule no authored text can break is (tag, None, why). The selftest reds a rule in RULES
# or PROPOSAL_RULES without an entry.
RULE_DIGEST = (
    ("S", "Each field holds at most its word cap, counted on its spans' texts joined and split on "
          "whitespace; code builds and checks the rest of the shape (slugs, cells per column, span ids, `cmp`)."),
    ("C1", "Every ID in a span's `c` is a row of ROWS, copied exactly."),
    ("C2", None, "a cited row's url against pages/index.tsv is the ledger's join (merge.py); no text repairs it"),
    ("N1", "Every digit run in a text is a numeral of a row that text cites, in its claim, quote, qualifier or "
           "scope, compared by value; a text citing nothing holds no digit."),
    ("Q1", "A `q` span cites a row, and its t is verbatim in the `quote` of an `en` row it cites."),
    ("Q2", "Curly quotation marks appear only in a `q` span, and no text holds a straight double quote; an "
           "apostrophe is no quote."),
    ("Q3", "A `g` span cites a row, and its t is verbatim in the `gloss` of a non-English row it cites."),
    ("M1", None, "the map's answers print from 06-shape.json; no authored text reaches them"),
    ("M2", None, "the map's answers print from 06-shape.json; no authored text reaches them"),
    ("M3", None, "the map's integration IDs print from 06-shape.json; no authored text reaches them"),
    ("M4", None, "the map's integration IDs print from 06-shape.json; no authored text reaches them"),
    ("U1", "A matrix cell the shape leaves Unknown opens its text \"Unknown\" or \"Not known\"."),
    ("P1", "Say what is unknown, never how much the run read: no numeral or number word sits within three "
           "words before \"pages\" (\"on 12 of its pages\", \"Five rivals' pages\"); a year or a day-month "
           "date there is a date."),
    ("R1", "A quick-take body adds a figure, name or fact to its lede: a body span citing only the lede's "
           "one row brings a numeral or a name the lede lacks."),
    ("L2", "In the matrix legend, the text before a sentence's colon names at most one matrix-cell or map "
           "label; write each qualifier as its own sentence with a verb."),
    ("D1", "Within one prose section (quick take, recommendations, moves, open questions, matrix legend) "
           "each claim ID sits on one sentence: a sentence citing anything prints one source chip."),
    ("G1", None, "logos are fetched and keyed by code (fetch-logos.py, assemble.py)"),
    ("H1", "`moves_heading` and `matrix.heading` hold at most %d characters, open on a capital and stay in "
           "sentence case: a later word takes a capital only as an acronym, a word of a company's name or a "
           "proper noun the rows capitalise." % RAIL_MAX),
    ("L1", None, "sources.tsv is stage 4's, written by code before any page text"),
    ("A1", "A slot cites only the claim IDs its allocation allots (its `- Claims:` and ICP lines; for the "
           "map and matrix, the shape's too), and each slot's evidence-clause IDs stay cited in that slot "
           "or are named in a `departures` entry {slot, id, reason}."),
    ("F1", "The matrix fits %d px: its columns' widths, each set by the column's longest unbroken word (a "
           "cited cell's last word carries its source chip), sum within it, so cell words stay short and "
           "are joined by spaces, never by `/`." % MATRIX_FIT),
    ("KR-H", "A span citing only rows marked `known: true` (the founder's own facts) appears only as a "
             "comparison half, beside a span of its field citing a rival row."),
    ("JD", "A row read off the job ad is cited only in such a comparison half."),
    ("NC", "A span naming the founder's company cites a row; `c` is empty only on connective text with "
           "no numeral, name or quote."),
    ("PL", "The page speaks about the market, never the job ad: no span or heading says \"posting\", "
           "\"job post\", \"job description\", \"this role\", the role title or the ad's host."),
    ("X1", "One claim ID is cited in at most %d prose sections." % (X1_MIN - 1)),
    ("X2", "Where the allocation's quick take has an ICP line, one quick-take point carries those rows "
           "as a comparison: a span citing the founder's own buyer rows beside a span citing a rival's."),
    ("M5", None, "the map's answers and their rows come from 06-shape.json; no authored text reaches them"),
    ("VL", "Describe what rivals do and leave the verdict to the founder; a verdict phrase (\"parity\", "
           "\"not an edge\", \"does not set it apart\") logs a warning, never a red."),
    ("X3", "A patch's `fix_new` keeps its field within the cap: at most the words PAGE gives its span "
           "(\"N words, at most M\")."),
)


def rules_digest():
    """The rule digest the author and arbiter prompts inline: a lead line, then `- TAG: sentence` per
    rule an authored text can break, in RULES order, the proposal rules last."""
    return "".join(["The gates grade the page on these rules; each red names its tag.\n"]
                   + ["- %s: %s\n" % (e[0], e[1]) for e in RULE_DIGEST if e[1] is not None])


def check(brief_path, root, schema=None):
    """Every finding as (rule, message). Raises SchemaError; claims-check's readers exit 2."""
    ctx = Ctx(brief_path, root, load_schema() if schema is None else schema)
    return [(tag, msg) for tag, fn in RULES for msg in fn(ctx)]


def report(findings, what):
    for tag, msg in findings:
        if tag in WARN_RULES:
            sys.stderr.write("WARN: %s %s\n" % (tag, msg))
    findings = [(tag, msg) for tag, msg in findings if tag not in WARN_RULES]
    for tag, msg in findings:
        sys.stderr.write("FAIL: %s %s\n" % (tag, msg))
    if findings:
        sys.stderr.write("BRIEF-CHECK RED (%d finding%s in %s)\n"
                         % (len(findings), "" if len(findings) == 1 else "s", what))
        return 1
    sys.stdout.write("BRIEF-CHECK-OK (0 findings in %s)\n" % what)
    return 0


# --- selftest -------------------------------------------------------------------------------------
# The green base is the committed fixture pair, tools/fixtures/web/synthetic.json against
# tools/fixtures/web/synthetic/. Each red case mutates a copy of one or both and must red exactly its
# own rule; a rule with no case is a selftest failure, so a rule added without one cannot ship.
def _rewrite_json(path, fn):
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _ledger(root, rid, **kw):
    path = root / "claims.jsonl"
    rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    for r in rows:
        if r["id"] == rid:
            r.update(kw)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def _logo(slug, **kw):
    def fn(root):
        _rewrite_json(root / LOGOS_JSON, lambda recs: [r.update(kw) for r in recs if r["slug"] == slug])
    return fn


def _index(root, match, **cols):
    """Rewrite columns of the pages/index.tsv row whose url is `match`."""
    path = root / "pages/index.tsv"
    lines = path.read_text(encoding="utf-8").splitlines()
    head = lines[0].split("\t")
    for k, ln in enumerate(lines[1:], start=1):
        cells = ln.split("\t")
        if cells[0] == match:
            for col, val in cols.items():
                cells[head.index(col)] = val
            lines[k] = "\t".join(cells)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _record(root, slug):
    return next(r for r in json.loads((root / LOGOS_JSON).read_text(encoding="utf-8")) if r["slug"] == slug)


def _page_outside(root):
    """A page outside the run, consistent in every other respect: its index row, hashes and href."""
    rec = _record(root, "coopelec")
    data = (root / rec["page_file"]).read_bytes()
    (root.parent / "outside.html").write_bytes(data)
    rel = "../outside.html"
    with open(root / "pages/index.tsv", "a", encoding="utf-8") as f:
        f.write("\t".join(["https://outside.example/", "https://outside.example/", "200",
                           "2026-10-01T09:00:00Z", sha(data), str(len(data)), rel]) + "\n")
    _logo("coopelec", page_file=rel)(root)


def _page_unindexed(root):
    """A saved page with no pages/index.tsv row, its bytes and hashes otherwise the record's own
    (W4-verify-2 Recommended 1: the `not rows` half of logo_gate, red on it alone)."""
    rec = _record(root, "coopelec")
    rel = "pages/unindexed.html"
    (root / rel).write_bytes((root / rec["page_file"]).read_bytes())
    _logo("coopelec", page_file=rel)(root)


def _drop_company(b, slug):
    """Remove a rival's entity, column and cells, leaving its map answer behind."""
    k = b["matrix"]["columns"].index(slug)
    b["rivals"] = [e for e in b["rivals"] if e["slug"] != slug]
    del b["matrix"]["columns"][k]
    for row in b["matrix"]["rows"]:
        del row["cells"][k]


def _duplicate_slug(b):
    """Two entities share one slug, and nothing else about the brief is wrong."""
    _drop_company(b, "oresund")
    b["map"]["answers"] = [a for a in b["map"]["answers"] if a["company"] != "oresund"]
    b["rivals"].insert(1, {"name": "Øresund Flex", "slug": "brightwater", "snapshot": "x.json", "logo": None})


def _new_inline_bytes(root):
    data = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="9" height="9"/></svg>'
    recs = json.loads((root / LOGOS_JSON).read_text(encoding="utf-8"))
    rec = next(r for r in recs if r["href"] is None)
    (root / rec["file"]).write_bytes(data)
    _logo(rec["slug"], sha256=sha(data))(root)


def _sources(fn):
    """A root mutator rewriting sources.tsv's lines through fn(lines) -> lines."""
    def go(root):
        path = root / SOURCES_TSV
        path.write_text("\n".join(fn(path.read_text(encoding="utf-8").splitlines())) + "\n", encoding="utf-8")
    return go


def _label(n, label):
    """sources.tsv line n (0 is the header) with its label replaced."""
    return _sources(lambda ls: ls[:n] + [ls[n].split("\t")[0] + "\t" + label] + ls[n + 1:])


def _set(path, value):
    """A mutator setting brief[path...] = value; path is a tuple of keys and indexes."""
    def fn(b):
        node = b
        for k in path[:-1]:
            node = node[k]
        node[path[-1]] = value
    return fn


def _allocated(evidence=None, icp=None, author=None, unlink=None, departures=None, sidecar=False):
    """A root mutator for A1: the fixture root plus a 06-shape.json and 06-allocation.md that allot
    each web slot exactly the IDs the committed base cites there, its first ID the slot's evidence
    clause. `evidence` {slot: ID} replaces a slot's evidence-clause ID; `icp` moves that slot's last
    ID from its Claims line to an ICP line; `author` is 07-author.md's text; `unlink` removes a file;
    `departures` [(slot, ID)] is the typed author's departures.json, or with `sidecar` the
    brief.departures.json apply-patches --out writes beside a proposed brief."""
    def go(root):
        base = json.loads((FIXTURES / "synthetic.json").read_text(encoding="utf-8"))
        m, mx = base["map"], base["matrix"]
        shape = {"company": base["company"]["slug"],
                 "map": {"across": m["across"], "down": m["down"], "answers": [
                     dict({ax: dict(a[ax], c=ids(a[ax]["c"])) for ax in AXES}, company=a["company"])
                     for a in m["answers"]]},
                 "matrix": {"columns": mx["columns"], "rows": [
                     {"label": r["label"], "serves": "Q1", "cells": [ids(c.get("c")) or "Unknown" for c in r["cells"]]}
                     for r in mx["rows"]]}}
        (root / SHAPE).write_text(json.dumps(shape, ensure_ascii=False), encoding="utf-8")
        lines = []
        for slot, pairs in slot_cites(base).items():
            got = list(dict.fromkeys(c for _, c in pairs))
            lines += ["### %s" % slot, "- Claims: %s" % ", ".join(got[:-1] if slot == icp else got)]
            lines += ["- ICP paragraph: the buyer (%s)" % got[-1]] if slot == icp else []
            lines += ["- Evidence clause: %s — a fixture fact" % (evidence or {}).get(slot, got[0])]
        (root / ALLOCATION).write_text("\n".join(lines) + "\n", encoding="utf-8")
        if author is not None:
            (root / AUTHOR).write_text(author, encoding="utf-8")
        if departures is not None:
            # the sidecar sits beside the brief, which the selftest writes next to the root
            (root.parent / "brief.departures.json" if sidecar else root / DEPARTURES).write_text(json.dumps({"departures": [
                {"slot": sl, "id": i, "reason": "a fixture reason"} for sl, i in departures]}), encoding="utf-8")
        if unlink:
            (root / unlink).unlink()
    return go


REC_ID = "C-006"  # cited by the base's recommendations only, never by its quick take
FORCED_HEAD = "| # | Field | Before | After | Red |\n|---|---|---|---|---|\n"
NO_FIELD = ("## Forced departures (step 3)\n\n" + FORCED_HEAD.replace("Field", "Field or slot")
            + "| 1 | slot quick-take | C-004 | dropped | C2 |\n")
FORCED_ROW = "| 1 | slot quick-take, body | C-006 | dropped | brief-check C2 |\n"
SIX_CHIPS = ["C-001", "C-004", "C-006", "C-009", "C-010", "C-013"]
# F1's model pinned per column to 0.01 px (G47), so no constant drifts unseen: the base (two
# columns floored by a 500 header), the hiring company's 600 header, a six-number chip, and the
# corner header flooring column 0 under one-letter labels.
F1_PINS = [
    ("the base", None, [86.47, 102.22, 100.34, 100.56, 109.07, 88.78, 88.94, 115.57]),
    ("a 600 header floors its column", _set(("company", "short"), "Coopérativeélec"),
     [86.47, 134.56, 100.34, 100.56, 109.07, 88.78, 88.94, 115.57]),
    ("a six-number chip floors its column", _set(("matrix", "rows", 0, "cells", 1, "c"), SIX_CHIPS),
     [86.47, 102.22, 154.17, 100.56, 109.07, 88.78, 88.94, 115.57]),
    ("the corner floors column 0", lambda b: [r.update(label="A") for r in b["matrix"]["rows"]],
     [53.52, 102.22, 100.34, 100.56, 109.07, 88.78, 88.94, 115.57]),
]
QT1 = ("quick_take", 1, "body")  # the base's quoted paragraph: [0] two IDs, [2] the q span
CLIENT_HOST = "coopelec.example"  # the host of the base company's rows C-001 and C-003
JD_URL = "https://calder.example/careers"  # a job ad on the host of C-010, which only the matrix cites


def _domain(b):
    b["company"]["domain"] = CLIENT_HOST


def _reader(**company):
    """A root mutator writing reader.json with `company` and no brief-side facts."""
    def go(root):
        (root / READER).write_text(json.dumps({"company": company, "known_hosts": []}), encoding="utf-8")
    return go


def _paired(b):
    """The base typed for KR-H: the client's domain set, and its three C-001 spans each a `cmp`
    comparison half beside the rival span qt.1.body.0 (C-004, C-013)."""
    _domain(b)
    for s in b["quick_take"][1]["body"][1:]:
        s["cmp"] = "qt.1.body.0"


GLOSS = ("quick_take", 0, "body", 0)  # the base's g span, citing the fr row C-012
RED_CASES = [
    ("S", "an unknown top-level field", lambda b: b.update(extra=1), None),
    ("S", "a matrix cell over its word cap (Cause A)",
     _set(("matrix", "rows", 0, "cells", 0, "t"), "Says yes, no unit, so far"), None),
    ("S+D1", "a section over its item cap", lambda b: b.update(quick_take=b["quick_take"] * 2), None),
    ("S", "a column naming no company", _set(("matrix", "columns", 1), "nobody"), None),
    ("S", "a row with a cell missing", lambda b: b["matrix"]["rows"][0]["cells"].pop(), None),
    ("S", "a map missing a company", lambda b: b["map"]["answers"].pop(), None),
    ("S", "two spans sharing one id",
     lambda b: b["quick_take"][0]["body"][0].update(id=b["quick_take"][0]["lede"][0]["id"]), None),
    ("S", "a cmp naming a span of another field",
     lambda b: b["quick_take"][0]["body"][0].update(cmp=b["quick_take"][0]["lede"][0]["id"]), None),
    ("S", "an unknown cell that cites", _set(("matrix", "rows", 3, "cells", 3, "c"), "C-001"), None),
    ("C1", "a c absent from claims.jsonl", _set(QT1 + (0, "c"), "C-999"), None),
    ("C2", "a cited row whose url is not in the index", None,
     lambda root: (_ledger(root, "C-010", url="https://calder.example/never-fetched"),  # labelled, so L1 holds
                   _sources(lambda ls: ls + ["https://calder.example/never-fetched\tCalder page"])(root))),
    ("N1", "a digit its row does not carry",
     _set(("recommendations", 0, "why", 1, "t"), " Nordvent already chose it in 2024."), None),
    ("N1", "a digit in a text that cites nothing",
     _set(("quick_take", 0, "lede", 0, "t"), "Mistral Réseaux runs 7 regions."), None),
    ("Q1", "a q span not verbatim in its quote", _set(QT1 + (2, "t"), "home batteries galore"), None),
    ("Q1+D1", "a q span quoting a non-en row", _set(QT1 + (2,), {"t": "Nous pilotons", "c": "C-012", "q": True}),
     None),
    ("Q1", "a q span citing nothing", _set(QT1 + (2,), {"t": "home batteries", "c": None, "q": True}), None),
    ("Q2", "a curly quote outside a q span", _set(QT1 + (3, "t"), " across “Burgundy”."), None),
    ("Q2", "a straight-double-quoted passage (G29)", _set(QT1 + (3, "t"), ' across "Burgundy".'), None),
    ("Q3", "a g span citing an en row", None, lambda root: _ledger(root, "C-012", lang="en")),
    ("Q3", "a g span not verbatim in its gloss",
     _set(GLOSS + ("t",), " Mistral Réseaux says it controls many heaters."), None),
    ("M1", "a map answer neither yes nor no", _set(("map", "answers", 0, "across", "answer"), "maybe"), None),
    ("M2", "an axis every company answers alike",
     lambda b: [a.update(across={"answer": "no", "name": None, "c": a["across"]["c"], "integration": []})
                for a in b["map"]["answers"]], None),
    ("M3", "an integration ID outside its answer's c", _set(("map", "answers", 1, "down", "integration"), ["C-001"]),
     None),
    ("M4", "an integration ID under a yes", _set(("map", "answers", 0, "down", "integration"), ["C-003"]), None),
    # G77 (ii) and (iii): an unknown cell worded as a cited No; process on the page, in each form.
    ("U1", "an unknown cell worded as a cited No", _set(("matrix", "rows", 3, "cells", 3, "t"), "Brands not named"),
     None),
    ("P1", "a legend counting the pages read", _set(("matrix", "legend", 0, "t"),
                                                    "None found on twelve Calder pages, so a deal may exist."), None),
    ("P1", "a count of pages with three words between", _set(("matrix", "legend", 0, "t"),
                                                             "Unknown: none of twelve Calder pricing tier pages says."), None),
    ("P1", "a count by digit, its row holding the numeral", _set(("matrix", "legend", 0),
                                           {"t": "Brightwater Grid names no maker on 1 of its pages.", "c": "C-005"}), None),
    ("P1", "a sentence-initial count, capitalised", _set(("matrix", "legend", 0, "t"),
                                                         "Sixteen Calder pages name no maker."), None),
    # G91: a body span restating its single-row lede; a legend fragment of merged labels.
    ("R1+D1", "a body span restating its single-row lede", lambda b: (
     b["quick_take"][0]["lede"][0].update(c="C-012"),
     b["quick_take"][0]["body"].append({"t": " It runs those homes itself.", "c": "C-012"})), None),
    ("R1+D1", "a possessive lede name, then a second sentence", lambda b: (b["quick_take"][0]["lede"][0].update(
        c="C-012"), b["quick_take"][0]["body"].append(
        {"t": " Mistral Réseaux’s homes are its own. They run at scale.", "c": "C-012"})), None),
    ("R1+D1", "a body repeating its lede's figure", lambda b: (b["quick_take"][0]["lede"][0].update(
        t="Mistral Réseaux already runs heaters in 12 regions.", c="C-012"),
        b["quick_take"][0]["body"].append({"t": " It runs them in 12 regions.", "c": "C-012"})), None),
    ("L2", "a legend sentence merging two cell labels before a colon",
     _set(("matrix", "legend", 0, "t"), "Not listed and On register: on its own pages."), None),
    ("L2", "a legend sentence merging two map labels before a colon",
     _set(("matrix", "legend", 0, "t"), "Names a maker or Names no maker: as its site says."), None),
    # W18-fix11-verify.md Rec 1, Rec 3 and Nice 2.
    ("L2", "two labels merged before a colon, lower-cased mid-sentence",
     _set(("matrix", "legend", 0, "t"), "Not listed and on register: on its own pages."), None),
    ("L2", "the fragment in a legend's second span", _set(("matrix", "legend"), [
        {"t": "Unknown: no page the run read answers it. ", "c": None},
        {"t": "Not listed and On register: on its own pages.", "c": None}]), None),
    ("R1+D1", "a two-span lede citing its row in the second span", lambda b: (
     b["quick_take"][0].update(lede=[{"t": "Mistral Réseaux ", "c": None},
                                     {"t": "already runs French homes at scale.", "c": "C-012"}]),
     b["quick_take"][0]["body"].append({"t": " It runs those homes itself.", "c": "C-012"})), None),
    ("R1+D1", "a body date equal by value to the lede's (01 and 1)", lambda b: (
     b["quick_take"][0]["lede"][0].update(t="As of 2026-10-01, Mistral Réseaux runs heaters.", c="C-012"),
     b["quick_take"][0]["body"].append({"t": " It ran them on 1/10/2026.", "c": "C-012"})), None),
    # W18-fix11-verify-2.md Rec 1 and Nice 1-2: names counted in the span's own text only; the
    # lede's text read whole; a name matched on word edges.
    ("R1+D1", "names in an earlier span, then a restating span", lambda b: (
     b["quick_take"][0]["lede"][0].update(c="C-012"), b["quick_take"][0]["body"].extend([
         {"t": " It works with Calder and øresund flex,", "c": None},
         {"t": " and it runs those homes itself.", "c": "C-012"}])), None),
    ("R1+D1", "a two-span lede, its row's words in the second span", lambda b: (
     b["quick_take"][0].update(lede=[{"t": "Mistral Réseaux ", "c": None},
                                     {"t": "already runs French homes.", "c": "C-012"}]),
     b["quick_take"][0]["body"].append({"t": " It runs French homes itself.", "c": "C-012"})), None),
    ("R1+D1", "a company name inside a longer word", lambda b: (
     b["quick_take"][0]["lede"][0].update(c="C-012"),
     b["quick_take"][0]["body"].append({"t": " It runs those homes, as coopélecs do.", "c": "C-012"})), None),
    ("R1+D1", "a restating span opening the body", lambda b: (b["quick_take"][0]["lede"][0].update(c="C-012"),
     b["quick_take"][0].update(body=[{"t": " It runs those homes itself.", "c": "C-012"}])), None),
    ("R1+D1", "a capitalised word the lede holds in lower case", lambda b: (
     b["quick_take"][0]["lede"][0].update(c="C-012"),
     b["quick_take"][0]["body"].append({"t": " It runs those Homes itself.", "c": "C-012"})), None),
    # W18-fix11-verify-3.md Nice 1: two case variants of one label are one, never zero.
    ("L2", "two case variants of a label, and another label", lambda b: (
     b["matrix"]["rows"][0]["cells"][3].update(t="Not Listed"),
     b["matrix"]["legend"][0].update(t="Not listed and Unknown: as sites say.")), None),
    # G92 (iii): one chip per ID per prose section. A lede and its body citing one row in two
    # sentences is two chips, so the R1 cases above red D1 too; R1 alone needs one sentence.
    ("R1", "a lede and its restating body in one sentence", lambda b: b["quick_take"][0].update(
        lede=[{"t": "Mistral Réseaux runs French homes at scale:", "c": "C-012"}],
        body=[{"t": " it runs those homes itself.", "c": "C-012"}]), None),
    ("D1", "one row on two sentences, the last ending its block", _set(("matrix", "legend"), [
        {"t": "Unknown: no page the run read answers it. ", "c": None},
        {"t": "Zephyr Loads opened its app to installers.", "c": "C-009"},
        {"t": " Installers now sell it", "c": None}, {"t": " for Zephyr Loads.", "c": "C-009"}]), None),
    ("D1", "one row on two moves", _set(("moves", 1, "meaning"), [
        {"t": "Zephyr Loads opened its app to installers.", "c": "C-009"}]), None),
    ("D1", "one row on two open questions", lambda b: b["open_questions"].append(
        [{"t": "Will Calder Systems register?", "c": None},
         {"t": " The flexibility register names no lead party for it.", "c": "C-011"}]), None),
    ("D1", "a sentence closing inside a bracket, then the same row", _set(("recommendations", 0, "why"), [
        {"t": " Øresund Flex trades in 3 markets (its own words.)", "c": "C-006"},
        {"t": " It trades", "c": None}, {"t": " in its own name.", "c": "C-006"}]), None),
    # G95 (Rec 1): a recommendation's next step is in its block, so re-citing its why row reds.
    ("D1", "a next step citing its why row", _set(("recommendations", 0, "next_step"), [
        {"t": "ask Heatwell which makers it would introduce, as Nordvent did.", "c": "C-007"}]), None),
    ("U1", "an unknown cell opening on a longer word", _set(("matrix", "rows", 3, "cells", 3, "t"), "Unknowns named"),
     None),
    ("S", "required: an answer without integration (G10)", lambda b: b["map"]["answers"][1]["down"].pop("integration"),
     None),
    ("G1", "a logo key with no record", _set(("rivals", 0, "logo"), "nobody"), None),
    ("G1", "an href not in its page (href branch)", None,
     _logo("brightwater", href="https://cdn.brightwater.example/other.svg")),
    ("G1", "inline bytes not in their page (inline branch)", None, _new_inline_bytes),
    ("G1", "a page_sha256 off its index row", None, _logo("coopelec", page_sha256="0" * 64)),
    ("G1", "a logo file off its sha256", None, _logo("calder", sha256="0" * 64)),
    ("G1", "no logos.json", None, lambda root: (root / LOGOS_JSON).unlink()),
    # W4-verify Recommended 1: each guard below has a case that reds on it alone.
    ("G1", "an index row off page_sha256, the page itself unchanged", None,
     lambda root: _index(root, _record(root, "coopelec")["page_url"], sha256="0" * 64)),
    ("G1", "page bytes changed under a matching index row", None,
     lambda root: (root / _record(root, "coopelec")["page_file"]).open("ab").write(b" ")),
    ("G1", "a page_file outside the run", None, _page_outside),
    ("G1", "a page_file with no index row", None, _page_unindexed),
    ("S", "two companies share a slug", _duplicate_slug, None),
    ("S", "a move naming no company", _set(("moves", 0, "rival"), "nobody"), None),
    ("S", "a map answer naming no company", lambda b: _drop_company(b, "lumen"), None),
    ("S+Q3", "a span both q and g", _set(QT1 + (2, "g"), True), None),
    ("Q3", "a g span citing nothing", _set(GLOSS, {"t": " Mistral Réseaux runs heaters.", "c": None, "g": True}), None),
    ("S", "required: run_date missing", lambda b: b.pop("run_date"), None),
    ("S", "pattern: a run_date not ISO", _set(("run_date",), "2026/10/01"), None),
    ("S", "enum: an action off the list", _set(("moves", 0, "action"), "ignore"), None),
    ("S", "const: q false", _set(QT1 + (2, "q"), False), None),
    ("S", "minItems: no open question", _set(("open_questions",), []), None),
    ("S", "uniqueItems: a column twice", _set(("matrix", "columns", 1), "coopelec"), None),
    # W12-verify Recommended 4: moves_heading carries matrix.heading's checks (G3), each red alone.
    ("S", "x-maxWords: a moves_heading over 5 words", _set(("moves_heading",), "Who is now moving and why"), None),
    ("S", "minLength: an empty moves_heading", _set(("moves_heading",), ""), None),
    ("S", "required: moves_heading missing", lambda b: b.pop("moves_heading"), None),
    # G34: an authored heading the rail and the spine's case can carry, each guard red alone.
    ("H1", "a Title Case moves heading", _set(("moves_heading",), "Who Moved, What to Do"), None),
    ("H1", "a matrix heading over the rail's 26 characters",
     _set(("matrix", "heading"), "Which rival moves need action"), None),
    ("H1", "a heading opening lower case", _set(("moves_heading",), "who is moving where"), None),
    ("H1", "a heading at 27 characters, one over the rail", _set(("moves_heading",), "Who is moving into Burgundy"), None),
    # G17: stage 4's sources.tsv contract, each guard red alone.
    ("L1", "no sources.tsv", None, lambda root: (root / SOURCES_TSV).unlink()),
    ("L1", "a sources.tsv header off the contract", None, _sources(lambda ls: ["url\tname"] + ls[1:])),
    ("L1", "a ledger url with no sources.tsv row", None, _sources(lambda ls: ls[:1] + ls[2:])),
    ("L1", "a url with two sources.tsv rows", None, _sources(lambda ls: ls + ls[1:2])),
    ("L1", "a sources.tsv row without two columns", None, _sources(lambda ls: ls[:1] + [ls[1] + "\tx"] + ls[2:])),
    ("L1", "an empty label", None, _label(1, " ")),
    ("L1", "a label of 32 characters", None, _label(1, "L" * 32)),
    # G41: slot drift, each half red alone, on an allocation that allots the base exactly.
    ("A1", "a slot citing an ID off its allocation lines", lambda b: b["quick_take"][1]["body"][0].update(
        c=["C-004", "C-013", REC_ID]), _allocated()),
    ("A1", "a dropped evidence-clause ID no forced row names", None, _allocated(evidence={"quick-take": REC_ID})),
    ("A1", "a forced row outside § Forced departures names nothing", None,
     _allocated(evidence={"quick-take": REC_ID},
                author="## Forced departures (step 3)\n\n## Step 5 checks\n\n" + FORCED_HEAD + FORCED_ROW)),
    # G58: a forced row excuses its ID in its own slot only.
    ("A1", "an ID forced in one slot, dropped from another's evidence clause", None,
     _allocated(evidence={"quick-take": REC_ID}, author="## Forced departures (step 3)\n\n" + FORCED_HEAD
                + FORCED_ROW.replace("slot quick-take", "slot recommendations"))),
    # The Field column is found by its header's name; a table with none names nothing.
    ("A1", "a forced table with no Field header names nothing", None,
     _allocated(evidence={"quick-take": REC_ID}, author="## Forced departures (step 3)\n\n"
                + FORCED_HEAD.replace("Field", "Where") + FORCED_ROW)),
    ("A1", "a forced table with no Field column reds by itself", None, _allocated(author=NO_FIELD)),
    ("A1", "a shape with no 06-allocation.md", None, _allocated(unlink=ALLOCATION)),
    ("A1", "a departures.json entry in another slot names nothing", None,
     _allocated(evidence={"quick-take": REC_ID}, departures=[("recommendations", REC_ID)])),
    # G46: the base's matrix models at 792.0 of 796; each half of a column's floor reds alone.
    ("F1", "one long word widens a column past the cap", _set(("matrix", "rows", 0, "cells", 1, "t"), "Supplier-agnostic"),
     None),
    ("F1", "a chip of six source numbers widens a column past the cap",
     _set(("matrix", "rows", 0, "cells", 1, "c"), SIX_CHIPS), None),
    # W16-verify Recommended 1 (G47): within 2 px of the cap, the model at 797.6.
    ("F1", "a row label 1.6 px over the cap", _set(("matrix", "rows", 0, "label"), "Registeringi"), None),
    # The founder-reader rules (Globex design.md § 2 R1b and Gap rows). The base names no client domain
    # and no job ad, so they key on nothing there; each case supplies what its rule keys on.
    ("KR-H", "spans citing only the founder's own rows, with no cmp", _domain, None),
    ("KR-H", "a cmp naming a span that cites no rival row", lambda b: (
     _domain(b), b["quick_take"][1]["body"][1].update(cmp="qt.1.body.3")), None),
    ("KR-H", "the client's domain read from reader.json", None, _reader(domain=CLIENT_HOST)),
    ("JD", "a span citing the job ad beside a rival row", lambda b: (
     b.update(jd_url=JD_URL), b["recommendations"][0]["why"][0].update(c=["C-006", "C-010"])), None),
    ("NC", "the founder's name in a span citing nothing",
     _set(("quick_take", 0, "lede", 0, "t"), "Coopélec already runs French homes at scale."), None),
    ("PL", "a span naming the job post", _set(("recommendations", 0, "test", 0, "t"),
                                              "Sign heat-pump makers before Øresund Flex reaches them, as the job post asks."), None),
    ("PL", "the role title the brief names", lambda b: (
     b.update(role="Flexibility Lead"), b["recommendations"][0]["next_step"][0].update(
         t="ask Heatwell which makers it would introduce to a flexibility lead.")), None),
    ("X1", "one row in three prose sections", lambda b: (
     b["matrix"]["legend"][0].update(c="C-009"), b["open_questions"][0][0].update(c="C-009")), None),
    ("X2", "an icp slot the allocation allots and no point carries", None, _allocated(icp="quick-take")),
    ("X2", "an icp point with no comparison pair (D14)", lambda b: b["quick_take"][1].update(slot="icp"), None),
    ("M5", "a no answer citing a named party's figure on the axis metric",
     _set(("map", "across", "metric"), "lead party"),
     lambda root: _ledger(root, "C-015", state="verified", metric="Nordvent:lead party seats",
                          claim="The Flexibility Register lists Nordvent as lead party for 3 Øresund Flex sites.")),
    ("VL", "a verdict sentence, warned and never counted", _set(("recommendations", 0, "why", 1, "t"),
                                                               " Nordvent already chose it, so Coopélec has parity at best."), None),
]
# G92 (iii): an R1 green case cites the lede's row again in the body, so D1 reds it as two chips;
# the case grades R1, and the "R1+D1" red cases show the two together.
D1_ASIDE = ("D1",)
GREEN_CASES = [
    ("an apostrophe is not a quote", _set(("quick_take", 0, "lede", 0, "t"), "Mistral Réseaux’s homes run at scale.")),
    ("7 is the 07 of an ISO date (C-006 carries no other 7)",
     _set(("recommendations", 0, "why", 0, "t"), " Øresund Flex says it trades in its own name in 3 markets, as of 7 September.")),
    ("an integration ID within its answer's c", _set(("map", "answers", 1, "down", "integration"), ["C-005"])),
    ("a numeral only in its row's scope (C-010, ruling A)", _set(("matrix", "rows", 2, "cells", 4, "t"), "5 tiers")),
    ("an unknown cell opening Not known (U1)", _set(("matrix", "rows", 3, "cells", 3, "t"), "Not known")),
    ("a count of logos on one page (P1)",
     _set(("matrix", "legend", 0, "t"), "Unknown: Calder shows five logos on its page.")),
    ("a count four words before pages (P1)",
     _set(("matrix", "legend", 0, "t"), "Unknown: five makers on its partner pages go unnamed.")),
    ("one page, singular, as D-004 measured (P1)", _set(("matrix", "legend", 0, "t"), "Its partner list fits on one page.")),
    ("a day before its month is a date (P1)",
     _set(("matrix", "legend", 0), {"t": "As of 2 September its app pages name installers.", "c": "C-009"})),
    ("a year is a date (P1)", _set(("matrix", "legend", 0), {"t": "Since 2026 its pages name installers.", "c": "C-009"})),
    ("an unknown cell with a leading space (U1)", _set(("matrix", "rows", 3, "cells", 3, "t"), " Unknown")),
    ("a single-row lede whose body adds 40,000 and 12 (R1)", _set(("quick_take", 0, "lede", 0, "c"), "C-012"), D1_ASIDE),
    ("a single-row lede whose body adds only a name (R1)", lambda b: (b["quick_take"][0]["lede"][0].update(
        c="C-012"), b["quick_take"][0]["body"].append({"t": " Its homes sit in Burgundy.", "c": "C-012"})), D1_ASIDE),
    ("a two-row lede, its body citing the same two (R1)", lambda b: b["quick_take"][1]["lede"][0].update(
        t="Brightwater Grid and Mistral Réseaux hold register seats.", c=["C-004", "C-013"]), D1_ASIDE),
    ("a body span citing the lede's row and another (R1)", lambda b: b["quick_take"][1]["lede"][0].update(
        t="Brightwater Grid and Mistral Réseaux hold register seats.", c="C-004"), D1_ASIDE),
    ("one label before a legend colon (L2)", _set(("matrix", "legend", 0, "t"), "Not listed: on its own pages.")),
    ("two labels after a legend colon (L2)",
     _set(("matrix", "legend", 0, "t"), "Unknown: the On register and Not listed cells differ.")),
    ("two labels in a legend sentence with no colon (L2)",
     _set(("matrix", "legend", 0, "t"), "Not listed and On register cite each register.")),
    ("a label inside a longer label (L2)",
     _set(("matrix", "legend", 0, "t"), "Utilities pay: as its site says.")),
    # W18-fix11-verify-3.md Nice 1: containment ignores case, as the match does.
    ("a label written lower-case in its cell, capitalised in the legend (L2)", lambda b: (
     b["matrix"]["rows"][1]["cells"][4].update(t="utilities pay"),
     b["matrix"]["legend"][0].update(t="Utilities pay: as its site says."))),
    # W18-fix11-verify-2.md Rec 2 and Nice 2.
    ("one-word labels as common nouns, by case (L2)",
     _set(("matrix", "legend", 0, "t"), "Both utilities and installers set tariffs: no register lists them.")),
    ("two labels differing only by case are one (L2)", lambda b: (
     b["matrix"]["rows"][0]["cells"][3].update(t="Not Listed"),
     b["matrix"]["legend"][0].update(t="Not listed: as sites say."))),
    ("a rival's short name, lower-cased (R1)", lambda b: (
     b["quick_take"][0]["lede"][0].update(c="C-012"),
     b["quick_take"][0]["body"].append({"t": " It beats zephyrloads there.", "c": "C-012"})), D1_ASIDE),
    ("the hiring company's name, lower-cased (R1)", lambda b: (
     b["quick_take"][0]["lede"][0].update(c="C-012"),
     b["quick_take"][0]["body"].append({"t": " It beats coopélec there.", "c": "C-012"})), D1_ASIDE),
    ("a label inside a longer word (L2)",
     _set(("matrix", "legend", 0, "t"), "Unknowns and Not listed: as sites say.")),
    # W18-fix11-verify.md Rec 2, Rec 3 and Nice 2.
    ("a label at the end of a longer word (L2)",
     _set(("matrix", "legend", 0, "t"), "NonUtilities and Not listed: as sites say.")),
    ("two labels in a sentence before the colon's sentence (L2)",
     _set(("matrix", "legend", 0, "t"), "Not listed and On register cite registers. Unknown: no page says.")),
    ("two labels between a sentence's two colons (L2)",
     _set(("matrix", "legend", 0, "t"), "Unknown: Not listed and On register mean what they say: no more.")),
    ("a body span with a null c under a single-row lede (R1)", lambda b: (
     b["quick_take"][0]["lede"][0].update(c="C-012"),
     b["quick_take"][0]["body"].append({"t": " It runs those homes itself.", "c": None})), D1_ASIDE),
    ("a body adding only a non-ASCII capital (R1)", lambda b: (
     b["quick_take"][0]["lede"][0].update(c="C-012"),
     b["quick_take"][0]["body"].append({"t": " Its homes sit near Évian.", "c": "C-012"})), D1_ASIDE),
    ("a body adding only a name with an inner capital (R1)", lambda b: (
     b["quick_take"][0]["lede"][0].update(c="C-012"),
     b["quick_take"][0]["body"].append({"t": " It sells through heatGrid.", "c": "C-012"})), D1_ASIDE),
    ("a body adding only a rival's name, lower-cased (R1)", lambda b: (
     b["quick_take"][0]["lede"][0].update(c="C-012"),
     b["quick_take"][0]["body"].append({"t": " It beats øresund flex there.", "c": "C-012"})), D1_ASIDE),
    ("a name opening a span that continues a sentence (R1)", lambda b: (
     b["quick_take"][0]["lede"][0].update(c="C-012"),
     b["quick_take"][0]["body"].extend([{"t": " It runs homes,", "c": None},
                                        {"t": " Calder too.", "c": "C-012"}])), D1_ASIDE),
    # G92 (iii): what `chips` counts as one chip, or as no repeat.
    ("one row twice in one sentence is one chip (D1)", _set(("recommendations", 0, "why"), [
        {"t": " Øresund Flex trades in 3 markets", "c": "C-006"}, {"t": " and", "c": None},
        {"t": " in its own name.", "c": "C-006"}])),
    ("a dot inside a word ends no sentence (D1)", _set(("recommendations", 0, "why"), [
        {"t": " Øresund Flex trades in 3 markets", "c": "C-006"}, {"t": " on oresund.example", "c": None},
        {"t": " in its own name.", "c": "C-006"}])),
    ("a question's row goes to the next sentence (D1)", _set(("open_questions", 0), [
        {"t": "Does Calder Systems hold a seat under another name?", "c": "C-011"},
        {"t": " The flexibility register", "c": None}, {"t": " names no lead party for it.", "c": "C-011"}])),
    ("one row in two sections (D1)", _set(("open_questions", 0, 1, "c"), "C-006")),
    ("a run of spans on one row closes once, across sentences (D1)", _set(("matrix", "legend"), [
        {"t": "Zephyr Loads opened its app to installers.", "c": "C-009"},
        {"t": " Installers sell it.", "c": "C-009"}])),
]
# C2's final_url half: the row's url is only the index row's final_url.
GREEN_ROOT_CASES = [
    ("a cited url found as an index row's final_url",
     lambda root: _index(root, "https://calder.example/pricing", url="https://calder.example/pricing?ref=x")),
    ("a label of exactly 31 characters (L1's edge)", _label(1, "L" * 31)),
    ("an allocation that allots every slot what it cites (A1)", _allocated()),
    ("an ID allotted on its slot's ICP line only (A1)", _allocated(icp="quick-take"), ("X2",)),
    ("a dropped evidence-clause ID a § Forced departures row names (A1)",
     _allocated(evidence={"quick-take": REC_ID}, author="# Stage 7\n\n## Forced departures (step 3)\n\n"
                + FORCED_HEAD + FORCED_ROW + "\n## Step 5\n")),
    ("a dropped evidence-clause ID the typed author's departures.json names (A1)",
     _allocated(evidence={"quick-take": REC_ID}, departures=[("quick-take", REC_ID)])),
    ("a dropped evidence-clause ID the arbiter's departures beside the brief name (A1)",
     _allocated(evidence={"quick-take": REC_ID}, departures=[("quick-take", REC_ID)], sidecar=True)),
    ("a `Field` header in backticks and bold, beside a short row (A1)",
     _allocated(evidence={"quick-take": REC_ID}, author="## Forced departures (step 3)\n\n"
                + FORCED_HEAD.replace("Field", "**`Field`**") + "| 2 |\n" + FORCED_ROW)),
    ("a forced table with no # column (A1)",
     _allocated(evidence={"quick-take": REC_ID}, author="## Forced departures (step 3)\n\n"
                "| Field | Before | After | Red that forced it |\n|---|---|---|---|\n"
                "| quick-take, body | C-006 | dropped | brief-check C2 |\n")),
]
GREEN_CASES += [
    ("the founder's own spans as cmp halves beside a rival span (KR-H)", _paired),
    ("an icp point holding a cmp pair (X2, D14)", lambda b: (_paired(b), b["quick_take"][1].update(slot="icp"))),
    ("a job-ad row as a cmp half beside a rival row (JD, D13)", lambda b: (
     b.update(jd_url=JD_URL), b["recommendations"][0].update(why=[
         {"id": "rec.0.why.0", "t": " Calder Systems sells to utilities,", "c": "C-010", "cmp": "rec.0.why.1"},
         {"id": "rec.0.why.1", "t": " while Nordvent already chose Øresund Flex.", "c": "C-007"}]))),
    ("an axis metric with no named party's figure under a no (M5)", _set(("map", "across", "metric"), "lead party")),
    ("a rival's name in a span citing nothing (NC)", _set(("open_questions", 0, 0, "t"), "Does Calder Systems hold a seat?")),
    ("a row in two prose sections (X1)", _set(("matrix", "legend", 0, "c"), "C-009")),
    ("a row label 1.7 px under the F1 cap", _set(("matrix", "rows", 0, "label"), "Registrants")),
    ("a capital only the company's name covers", _set(("matrix", "heading"), "Where Coopérative leads")),
    ("a heading at the rail's 26 characters, a ledger proper noun in it", _set(("moves_heading",), "Which rivals win Burgundy?")),
    ("a company name and an acronym inside a heading",
     _set(("matrix", "heading"), "Where GB sees Øresund Flex")),
]


def _coverage(base, root):
    """What the green base must exercise, or its green proves less than it says."""
    t = list(texts(base))
    keys = [e.get("logo") for e in entities(base)]
    recs = [r for r in json.loads((root / LOGOS_JSON).read_text(encoding="utf-8")) if r.get("slug") in keys]
    cells = [c for row in lst(obj(base, "matrix"), "rows") for c in lst(row, "cells")]
    return {"a q span": any(x[3] for x in t), "a g span": any(x[4] for x in t),
            "a text citing two rows": any(isinstance(x[2], list) for x in t),
            "a text citing nothing": any(x[2] is None for x in t),
            "an unknown cell": any(c.get("mark") == "unknown" for c in cells),
            "a wordmark logo": None in keys, "an href logo": any(r.get("href") for r in recs),
            "an inline logo": any(r.get("href") is None for r in recs)}


def selftest():
    global BF
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("backfill_globex", ROOT / "tools/backfill-globex.py")
    BF = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(BF)
    schema = load_schema()
    base = json.loads((FIXTURES / "synthetic.json").read_text(encoding="utf-8"))
    fails, hit, count = [], set(), {"red": 0, "green": 0}

    def run(brief, root_fn=None, sch=schema):
        # A case's added spans take ids as the runner's span-ids node gives them, so each case reds
        # on its own rule; tools/fixtures/schema/ holds the span missing its id.
        brief = BF.assign_span_ids(brief) if isinstance(brief, dict) else brief
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp) / "root"
            shutil.copytree(FIXTURES / "synthetic", root)
            if root_fn:
                root_fn(root)
            path = pathlib.Path(tmp) / "brief.json"
            path.write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")
            return check(path, root, sch)

    def verdict(kind, label, ok, got):
        if ok:
            count[kind] += 1
            sys.stdout.write("SELFTEST %-5s OK  %s\n" % (kind, label))
        else:
            fails.append("%s case %r: got %s" % (kind, label, got))

    lacking = [k for k, v in _coverage(base, FIXTURES / "synthetic").items() if not v]
    if lacking:
        fails.append("the green base no longer exercises: %s" % lacking)
    found = run(base)
    verdict("green", "the committed synthetic pair", not found, found)
    for label, fn, *aside in GREEN_CASES:
        b = copy.deepcopy(base)
        fn(b)
        found = [f for f in run(b) if f[0] not in (aside[0] if aside else ())]
        verdict("green", label, not found, found)
    for label, root_fn, *aside in GREEN_ROOT_CASES:
        found = [f for f in run(copy.deepcopy(base), root_fn) if f[0] not in (aside[0] if aside else ())]
        verdict("green", label, not found, found)
    for rule, label, brief_fn, root_fn in RED_CASES:
        b = copy.deepcopy(base)
        if brief_fn:
            brief_fn(b)
        found = run(b, root_fn)
        tags = sorted({tag for tag, _ in found})
        want = sorted(rule.split("+"))
        if tags == want and len(want) == 1:
            hit.add(rule)
        verdict("red", "%-4s %s" % (rule, label), tags == want, found)
    # F1 names the word that sets the wide column, the repair the author can make (vandelay run 2:
    # a red listing only pixel totals left the author's repair unable to act).
    b = copy.deepcopy(base)
    _set(("matrix", "rows", 0, "cells", 1, "t"), "Supplier-agnostic")(b)
    found = run(b, None)
    verdict("red", "F1   the red names the word that sets the wide column",
            any("set by row" in m and "'Supplier-agnostic'" in m for t, m in found if t == "F1"), found)
    # The headless red names the missing column, the repair the author can make.
    found = run(copy.deepcopy(base), _allocated(author=NO_FIELD))
    verdict("red", "A1   the headless red names the `Field` column",
            any("`Field` column" in m for _, m in found), found)
    fails += ["rule %s has no red case" % tag for tag, _ in RULES if tag not in hit]
    rows = Ctx(FIXTURES / "synthetic.json", FIXTURES / "synthetic", schema).rows
    for label, fn, want in F1_PINS:
        b = copy.deepcopy(base)
        if fn:
            fn(b)
        got = [round(w, 2) for _, w in matrix_floors(b, rows)]
        verdict("green", "F1 pin: %s" % label, got == want, got)
    bad = copy.deepcopy(schema)
    bad["properties"]["run_date"]["maxLength"] = 10
    try:
        run(base, sch=bad)
        verdict("red", "a schema keyword the validator does not enforce", False, "no SchemaError")
    except SchemaError:
        verdict("red", "a schema keyword the validator does not enforce", True, None)
    with contextlib.redirect_stderr(io.StringIO()):
        codes = (main(["brief-check.py"]),
                 main(["brief-check.py", str(FIXTURES / "synthetic.json"), str(FIXTURES / "no-such-root")]))
    verdict("red", "bad usage and a missing root exit 2", codes == (2, 2), codes)
    # VL warns and is never counted: a brief red only by VL exits 0.
    b = copy.deepcopy(base)
    _set(("recommendations", 0, "why", 1, "t"), " Nordvent already chose it, so Coopélec has parity at best.")(b)
    with contextlib.redirect_stderr(io.StringIO()) as err, contextlib.redirect_stdout(io.StringIO()):
        code = report(run(b), "a VL-only brief")
    verdict("red", "VL   a VL-only brief exits 0 and prints its WARN", code == 0 and "WARN: VL" in err.getvalue(),
            (code, err.getvalue()))
    # X3, the proposal rule (`--proposal`): graded on the brief a patch list leaves, on the fields
    # it touched only.
    lede = base["quick_take"][0]["lede"][0]
    for label, patches, want in (
            ("X3   a fix_new over its field's cap", [{"span_id": lede["id"], "fix_old": lede["t"],
                                                     "fix_new": " ".join(["word"] * 15), "c": []}], ["X3"]),
            ("X3   a fix_new inside its field's cap", [{"span_id": lede["id"], "fix_old": lede["t"],
                                                       "fix_new": "Mistral Réseaux runs French homes.", "c": []}], []),
            ("X3   a proposal off the fields over cap elsewhere", [{"span_id": lede["id"], "fix_old": lede["t"],
                                                                   "fix_new": "Mistral Réseaux runs French homes.", "c": []}],
             "untouched")):
        with tempfile.TemporaryDirectory() as tmp:
            bp, pp = pathlib.Path(tmp) / "brief.json", pathlib.Path(tmp) / "patches.json"
            b = copy.deepcopy(base)
            if want == "untouched":  # another field over its cap: the proposal is graded on its own fields
                b["recommendations"][0]["next_step"][0]["t"] = " ".join(["word"] * 14)
                want = []
            bp.write_text(json.dumps(b, ensure_ascii=False), encoding="utf-8")
            pp.write_text(json.dumps(patches, ensure_ascii=False), encoding="utf-8")
            tags = sorted({t for t, _ in proposal(pp, bp, FIXTURES / "synthetic", schema)})
        if tags == ["X3"]:
            hit.add("X3")
        verdict("red" if want else "green", label, tags == want, tags)
    with tempfile.TemporaryDirectory() as tmp:
        bp, pp = pathlib.Path(tmp) / "brief.json", pathlib.Path(tmp) / "patches.json"
        bp.write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")
        pp.write_text(json.dumps([{"span_id": lede["id"], "fix_old": "not its text", "fix_new": "x"}]), encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()):
            code = main(["brief-check.py", "--proposal", str(pp), str(bp), str(FIXTURES / "synthetic")])
    verdict("red", "X3   a fix_old that is not its span's text exits 2", code == 2, code)
    fails += ["proposal rule %s has no red case" % tag for tag, _ in PROPOSAL_RULES if tag not in hit]
    # The digest the author and arbiter prompts inline (back-lane.py): every graded rule has an
    # entry, a sentence or None with the reason no authored text can break it.
    entries = globals().get("RULE_DIGEST", ())
    tags = [e[0] for e in entries]
    graded = [tag for tag, _ in RULES + PROPOSAL_RULES]
    fails += ["rule %s has no RULE_DIGEST entry: a sentence, or None with a reason" % t for t in graded if t not in tags]
    fails += ["RULE_DIGEST %r names no rule, or names it twice" % t for t in tags if t not in graded or tags.count(t) > 1]
    fails += ["RULE_DIGEST %s: want (tag, sentence) or (tag, None, reason)" % e[0] for e in entries
              if not ((len(e) == 2 and isinstance(e[1], str) and e[1].strip())
                      or (len(e) == 3 and e[1] is None and isinstance(e[2], str) and e[2].strip()))]
    with contextlib.redirect_stdout(io.StringIO()) as out:
        code = main(["brief-check.py", "--rules-digest"])
    verdict("green", "--rules-digest prints one line per authored rule", code == 0 and entries
            and out.getvalue() == rules_digest() and all(
                ("- %s: " % e[0] in out.getvalue()) == (e[1] is not None) for e in entries), (code, out.getvalue()[:200]))
    for f in fails:
        sys.stderr.write("SELFTEST FAIL: %s\n" % f)
    if fails:
        sys.stderr.write("SELFTEST RED (%d failure%s)\n" % (len(fails), "" if len(fails) == 1 else "s"))
        return 1
    sys.stdout.write("SELFTEST OK (%d red, %d green)\n" % (count["red"], count["green"]))
    return 0


USAGE = ("usage: brief-check.py <brief.json> <BRIEF_ROOT>\n"
         "       brief-check.py --proposal <patches.json> <brief.json> <BRIEF_ROOT>\n"
         "       brief-check.py --rules-digest\n"
         "       brief-check.py --selftest\n")


class Unappliable(Exception):
    """A patch list that cannot be laid on its brief: exit 2, since nothing can be graded."""


def apply_proposal(brief, patches):
    """(the brief a patch list would leave, the field wheres it touched). A patch is design.md § 3's
    {span_id, fix_old, fix_new, c[]}: the span whose `id` is span_id, whose t is exactly fix_old,
    takes fix_new, and `c` when the patch carries one."""
    out, touched = copy.deepcopy(brief), set()
    if isinstance(patches, dict) and list(patches) == ["patches"]:  # the arbiter's object root
        patches = patches["patches"]
    if not isinstance(patches, list):
        raise Unappliable("patches.json is neither a list nor {\"patches\": [...]}")
    spans = {s.get("id"): (where, s) for where, arr in span_arrays(out) for s in arr if isinstance(s, dict)}
    for n, p in enumerate(patches):
        if not isinstance(p, dict) or not isinstance(p.get("fix_new"), str):
            raise Unappliable("patches[%d] is no object with a string fix_new" % n)
        if p.get("span_id") not in spans:
            raise Unappliable("patches[%d]: span id %r is in no field of the brief" % (n, p.get("span_id")))
        where, s = spans[p["span_id"]]
        if s.get("t") != p.get("fix_old"):
            raise Unappliable("patches[%d]: fix_old is not span %s's text" % (n, p["span_id"]))
        s["t"] = p["fix_new"]
        if "c" in p:
            c = [x for x in p["c"] if isinstance(x, str)] if isinstance(p["c"], list) else p["c"]
            s["c"] = (c[0] if len(c) == 1 else c or None) if isinstance(c, list) else c
        touched.add(where)
    return out, touched


def proposal(patches_path, brief_path, root, schema=None):
    """PROPOSAL_RULES' findings on the brief a patch list would leave, graded on the fields it
    touched. Raises Unappliable, SchemaError."""
    schema = load_schema() if schema is None else schema
    try:
        patches = json.loads(pathlib.Path(patches_path).read_text(encoding="utf-8"))
        brief = json.loads(pathlib.Path(brief_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Unappliable("cannot read the proposal (%s)" % exc)
    patched, touched = apply_proposal(brief, patches)
    ctx = Ctx(brief_path, root, schema, brief=patched)
    ctx.touched = touched
    return [(tag, msg) for tag, fn in PROPOSAL_RULES for msg in fn(ctx)]


def main(argv):
    if argv[1:] == ["--selftest"]:
        return selftest()
    if argv[1:] == ["--rules-digest"]:
        sys.stdout.write(rules_digest())
        return 0
    if len(argv) == 5 and argv[1] == "--proposal":
        try:
            if not (pathlib.Path(argv[4]) / "claims.jsonl").is_file():
                raise Unappliable("no file to read at %s" % (pathlib.Path(argv[4]) / "claims.jsonl"))
            return report(proposal(argv[2], argv[3], argv[4]), "the proposal %s on %s" % (argv[2], argv[3]))
        except (Unappliable, SchemaError) as exc:
            sys.stderr.write("FAIL: %s\n" % exc)
            return 2
    if len(argv) != 3 or argv[1].startswith("-"):
        sys.stderr.write(USAGE)
        return 2
    brief, root = pathlib.Path(argv[1]), pathlib.Path(argv[2])
    for need in (brief, root / "claims.jsonl", root / "pages/index.tsv"):
        if not need.is_file():
            sys.stderr.write("FAIL: no file to read at %s\n" % need)
            return 2
    try:
        findings = check(brief, root)
    except SchemaError as exc:
        sys.stderr.write("FAIL: the schema %s is unusable: %s\n" % (SCHEMA, exc))
        return 2
    return report(findings, "%s against %s" % (brief, root))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
