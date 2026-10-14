#!/usr/bin/env python3
"""The claims ledger lint. It grades `claims.jsonl`, and it grades a brief against `claims.jsonl`.

WHY THIS EXISTS. On the Northwind run a false sentence was delivered: "Enode reaches your seven partners
without signing them". Five of the seven had dated partnership announcements. Nothing was
fabricated. The research said "signing anything *further*"; the orchestrator's prompt said "The
manufacturer signs nothing"; a reviewer relayed that wording; the next prompt carried it; the brief
printed it. One qualifier fell off at the first hop and four more hops carried the sentence to the
page. GATE 4 in `build/build.py` checks that a cited URL appears in some snapshot. It cannot check
that the sentence is on that page, and no gate in this repository checked that a number in the
brief came from anywhere at all.

THE ABSTRACTION. Facts leave research as ROWS, not as prose: one JSON object per line, each with an
id, the narrowest claim its evidence carries, the qualifier that makes it true, the bound, the
source's own words, and the URL fetched. Prompts then carry claim IDs and paths, never a restated
fact, so there is no hop at which a sentence is retyped and a word can drop. This script is what
makes that ledger worth carrying: `--ledger` grades the ledger's own shape, and `--check` grades
every numeral and every quantifier in the brief against it.

TWO MODES, AND WHY THEY ARE ONE FILE. The ledger rules (L1-L10) and the brief rules (B1-B3) share
the same reader of the same file format, and the brief rules are meaningless against a ledger that
has not passed the ledger rules -- `--check` therefore runs L1-L10 first and reports both sets. A
second script would be a second copy of the row parser.

ONE RULE IS ASKED FOR RATHER THAN ALWAYS ON -- half of one, exactly. L10's FLOOR, the ledger
carries at least one client-owned row, is true of a finished research ledger and false of the seed
ledger the reader-frame stage writes before any cohort company has been read. A rule that reds a
legitimate intermediate is a rule its own caller learns to skip, so the floor runs under
`--require-client-rows` and the stage that owes the rows passes it. L10's ROW half -- a `not named`
row names the register it was read off and the bound of that closed list -- is unconditional, like
every other rule: an absence nobody could check is wrong in the seed ledger too, and a seed ledger
carries no absence rows to red.

A THIRD MODE, AND WHY IT IS NOT A GREP. `--client-row` resolves the one client-owned row for a
company by its `subject` field. It lives here because the alternative is every reader writing its
own substring search over the line, and a substring search answers three questions wrongly: a row
whose `quote` names a second company is returned for that company, a name that is a strict prefix
of another's returns the longer company's row, and a row that never spells its company in free text
is invisible to every search. The field is typed, so the resolution is equality, and the tie-break
lives in one place rather than in whichever order a reader's eye fell.

`--ledger` runs at the end of stage 4, which is the moment a dropped qualifier is still cheap: after
authoring, the same defect costs a fixer pass and a re-verification. `--check` runs inside the
author (stage 7) and again for the truth critic (stage 8).

WHAT IT DELIBERATELY DOES NOT CHECK, each absent rather than forgotten:

  1. WHETHER A CLAIM IS TRUE. Whether Enode really signs nobody is the judgement the truth critic is
     dispatched for. What is mechanical is whether the sentence's numbers and quantifiers exist in
     a row at all, which is the hop where the Northwind defect entered.
  2. WHETHER A URL WAS FETCHED. That is provenance rule 1 and the snapshot's `sources` list, which
     is generated from the fetch log. This script reads no network.
  3. WHETHER THE QUOTE IS ON THE PAGE, UNLESS HANDED THE PAGES. Without `--pages` it checks only
     that an evidence row's quote is non-empty (L5). With `--pages <dir>`, the page store
     `tools/fetch.py` writes, it reads that store and still no network: L11 finds the row's URL in
     `index.tsv` on a reached fetch that `methods.tsv` does not mark `chrome-unverified`, L12 finds the quote in that fetch's `.txt`, and L13 reds a
     stitched quote. Those three rules stop a research sentence or a paraphrase from wearing a
     citation. Without them, a quote only had to be non-empty.
  4. THE PROSE. Register, rhythm and labels are `tools/voice-lint.sh` and the critics.

FAIL-CLOSED, AND COLLECT-EVERY-FINDING. Every violation is collected and only then does the script
exit non-zero, the discipline `audit()`, `tools/score-check.sh` and `tools/ci-gates.sh` all hold: a
ledger that breaks four rules reports four. A zero exit is the evidence, never the printed output.

EXIT CODES. 0 green. 1 findings. 2 the script could not do its job -- bad usage, missing file,
unreadable file. A missing ledger is a 2 and never a 0, because "no ledger" must not read as "no
findings".

PRECONDITION: none beyond the files existing. No network, no MKT1 call, no browser, no run
directory, no environment variable. `BRIEF_ROOT` is read only to default a path.
"""

import contextlib
import io
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile
import unicodedata
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent

# The row contract, written once. `references/methodology.md` carries the same twelve fields in
# prose and that file is the standard a human reads; this tuple is what the check reads, and the
# selftest pins every name in it, so a field added here without a case is a selftest failure.
REQUIRED_FIELDS = ("id", "subject", "claim", "qualifier", "scope", "metric", "quote", "url",
                   "source", "state", "exclusive", "lang")
# L16 and B4, the operator's 2026-09-25 ruling (`43-rulings.md:83-92`): the brief quotes English only. A
# row's `lang` is the ISO 639-1 code of its `quote`; a non-`en` row that owes a quote keeps the
# original as proof and carries `gloss`, an English rewording the brief prints without quote marks.
# A quote mark is a double quote in any form, a guillemet, or a single quote that opens a word; `'`
# and `’` inside or after a word are apostrophes (`company's`, `partners’`) and stay legal.
EN = "en"
LANG_RE = re.compile(r"^[a-z]{2}$")  # the shape of an ISO 639-1 code; which codes exist is not graded
GLOSS_QUOTE_RE = re.compile(r"[\"“”„‟«»‹›‘‚‛]|(?<!\w)['’]")
# B4's passage: the brief sets a quote in double curly quotes (`references/brief-contract.md`), and
# a passage may run across a line break.
CURLY_RE = re.compile(r"“([^“”]*)”")
# L17, name spelling (`73-web-plan.md:191-196`): one name spelled two ways prints twice on the page,
# as a logo label and as a matrix column. A name is a maximal run of tokens each holding a capital,
# joined by single spaces ("My Energi", "Ev Dot Energy"), or any other single token. A token inside a
# run is read only as the whole run, so an acronym ("EV") never meets one word of a longer name
# ("Ev Dot Energy"); the cost is a variant written inside a longer run. Two narrowings keep that
# cost small: a run opening a field or a sentence is also read without its first word ("The Volt
# Wise"), and a run ends at a possessive, whose `'s` is dropped ("Solax's"). Two names sharing a key (case,
# spaces and hyphens dropped) are one name spelled differently, unless they split into the same
# words and differ only in each word's first letter: sentence and title case, which "energy" and
# "Energy" share with every common word. `quote` is left out: it is the page's words, verbatim, and
# two pages may spell one name two ways that no row can respell.
NAME_FIELDS = ("subject", "claim", "qualifier", "scope", "metric", "gloss")
NAME_TOKEN_RE = re.compile(r"[^\W_](?:[\w.&'’-]*[^\W_])?")
NAME_SPLIT_RE = re.compile(r"[\s-]+")
NAME_POSSESSIVE_RE = re.compile(r"['’]s$")
NAME_SENTENCE_END = ".!?:;"
# `named` and `not named` are the client-owned row's two states: a page or register the client
# controls names a cohort company, or it does not. They are a second axis on the same row shape, not
# a second file, so they live in this vocabulary. A `named` row is evidence and carries its quote and
# URL under L5 exactly as `verified` does; a `not named` row is an absence read off a closed list and
# carries neither.
STATES = ("verified", "unfound", "blocked", "named", "not named")
# The states whose row asserts something was on a page, and which therefore owe a quote and a URL
# under L5. The other three record an absence or a refusal and owe neither.
EVIDENCE_STATES = ("verified", "named")
# The client-owned states, in the order the resolver's tie-break reads them: a `named` row outranks
# a `not named` one, because a page naming the company is evidence and a closed list that does not
# is an absence. Stage 4 writes ONE client-owned row per subject and L8 grades that, so the
# tie-break decides only a ledger already carrying a finding -- but it decides it the same way
# twice, which is what a substring grep over the line could never promise.
CLIENT_STATES = ("named", "not named")
# What a `not named` row owes INSTEAD of the quote and URL L5 asks an evidence row for. A bounded
# absence is a reading of a closed list, so it carries the list -- `source`, the register it was
# read off, in this run's own files -- and the list's own bound in `scope`.
# `references/stages/04-research.md` step 8 states the pair as "the register named and the absence
# bounded"; without it `exclusive: true` was the whole assertion, and that is a literal an author
# types rather than evidence. Measured in `59-verify.md` item 2b: a row with every other field the
# empty string exited 0 and satisfied L10's floor on its own.
ABSENCE_EVIDENCE = ("source", "scope")
ID_RE = re.compile(r"^C-\d{3,}$")

# L20-L22, the typed row (`references/schemas/claims-row.schema.json`), graded under `--typed`: the
# runner's merge writes these fields, and a ledger from a run before the runner carries none, so the
# flag is asked for, as L10's floor is. `kind` names what the row is, and each kind allows only the
# states that say it; `known` is code's, from the row's URL host (`row_known`).
QUESTION_ID_RE = re.compile(r"^Q[1-9]\d*$")
KIND_STATES = {"evidence": ("verified", "named", "blocked"),
               "absence": ("unfound", "not named"),
               "join": ("named", "not named")}


def row_known(url, domain, known_hosts):
    """A row is known to the founder when its URL's host is the company's domain or a subdomain of
    it, or one of `known_hosts` exactly: a job ad on a shared platform host matches only itself."""
    host = (urllib.parse.urlparse(url or "").hostname or "").lower()
    if not host:
        return False
    domain = (domain or "").lower()
    return bool(domain) and (host == domain or host.endswith("." + domain)) or host in set(known_hosts)


def check_typed(path, rows, reader=None):
    """L20-L22 for every row. `reader` is reader.json's dict; with it, L22 also holds `known` to the
    host rule."""
    findings = []
    company = reader.get("company", {}) if isinstance(reader, dict) else {}
    for n, obj in rows:
        where, rid = "%s:%d" % (path, n), obj.get("id", "<no id>")
        qid = obj.get("question_id", "<absent>")
        if qid is not None and not (isinstance(qid, str) and QUESTION_ID_RE.match(qid)):
            findings.append(("L20", "%s: row %s has question_id %r; a row names the questions.json "
                                    "question it answers, Q<n>, or null before questions exist" %
                             (where, rid, qid)))
        kind, state = obj.get("kind", "<absent>"), obj.get("state")
        if kind not in KIND_STATES:
            findings.append(("L21", "%s: row %s has kind %r, want one of %s" %
                             (where, rid, kind, "/".join(KIND_STATES))))
        elif state not in KIND_STATES[kind]:
            findings.append(("L21", "%s: row %s is kind %s in state %r; a %s row is %s" %
                             (where, rid, kind, state, kind, " or ".join(KIND_STATES[kind]))))
        known = obj.get("known", "<absent>")
        if not isinstance(known, bool):
            findings.append(("L22", "%s: row %s has known %r; code sets it true or false from the "
                                    "url's host" % (where, rid, known)))
        elif reader is not None:
            want = row_known(obj.get("url"), company.get("domain"), reader.get("known_hosts", []))
            if known != want:
                findings.append(("L22", "%s: row %s has known %s, but its url's host makes it %s "
                                        "(company domain %r, known_hosts)" %
                                 (where, rid, known, want, company.get("domain"))))
    return findings

# The page store `tools/fetch.py` writes, read under `--pages`. The header is that script's
# INDEX_COLUMNS, restated rather than imported so this lint loads no fetcher; an index whose header
# differs is a store this file cannot read, which is exit 2 and never a row matched by position.
INDEX_COLUMNS = ("url", "final_url", "status", "fetched_at", "sha256", "bytes", "path")
REACHED_RE = re.compile(r"^2\d\d$")
# `fetch.py`'s sidecar `pages/methods.tsv`. A path whose last row says `chrome-unverified` was
# rendered with no readable net-log (fetch.py exit 5): its index row carries curl's 2xx, but the
# DOM's status and final URL are unconfirmed, so L11 counts it as not reached until re-fetched.
METHOD_COLUMNS = ("path", "method", "prose")
UNVERIFIED = "chrome-unverified"
# A table row as a quote: cells joined by ` | ` (the text layer's own join) or ` / `.
CELL_SPLIT_RE = re.compile(r" \| | / ")
IMG_PREFIX = "[img-file] "
ELISION_RE = re.compile(r"\.\.\.|…")

# The quantifier vocabulary is the one the bar line names: "Every number, absence and quantifier =
# a claim ID with its qualifier". Kept to that list rather than widened, because every word here
# fails a brief closed and a word that fires on ordinary prose would be a rule people learn to
# ignore. `N of M` is not in this list; it is rule B3, which needs the pair and not the word.
QUANTIFIERS = ("no", "none", "only", "all", "first", "every")
QUANT_RE = re.compile(r"\b(" + "|".join(QUANTIFIERS) + r")\b", re.IGNORECASE)

# A numeral token: digits, with thousands separators and a decimal tail, so `15,000` and `1.5` are
# one token each and not three. The `%`, `£` and `$` around it are not part of the token: the
# ledger may write `15,000+` where the brief writes `15,000`, and the plus is the qualifier's job.
NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
N_OF_M_RE = re.compile(r"\b(\d+)\s+of\s+(\d+)\b")

# L14-L15. A metric is `<entity>:<counted thing>`, both halves present. A scope numeral that counts
# the evidence read (`1 page read`, `22 fetched pages`, `1 press release`) bounds the reading, not
# the subject, so it owes no metric and is no count; at most one word may sit between the numeral
# and the unit. On the Northwind replay it was 24 of 48 rows' only numeral.
METRIC_RE = re.compile(r"^[^:\s][^:]*:\s*\S")
# `k of N` in a scope, with at most one word on either side of `of`: `7 of 8`, `1 posting of 12`,
# `0 of these 4`. Wider than B3's N_OF_M_RE, which matches the brief's own bare pair.
SCOPE_PAIR_RE = re.compile(r"\d[\d,]*\s+(?:[^\s\d]+\s+)?of\s+(?:[^\s\d]+\s+)?(\d[\d,]*)")
EVIDENCE_UNIT_RE = re.compile(
    r"\s+(?:\S+\s+)?(pages?|posts?|releases?|quotes?|sources?|captures?|articles?|urls?)\b",
    re.IGNORECASE)
# A date in a scope is when, never how many (`Sep 2026: 8 partners` counts 8): an ISO date, a
# month-name date, a quarter or half, or a year after a time preposition. Blanked before reading.
_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
SCOPE_DATE_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b|\b(?:\d{1,2}\s+)?" + _MONTH + r"\s+(?:\d{1,2},?\s+)?(?:19|20)\d{2}\b"
    r"|\b(?:Q[1-4]|H[12]|FY)\s*(?:19|20)\d{2}\b"
    r"|\b(?:in|since|by|until|before|after|as of)\s+(?:19|20)\d{2}\b", re.IGNORECASE)
# L14 reds a count written in words, which no rule could compare (`seven of eight partners`).
# `one` is left out: `one page` and `no one` are prose, not counts.
WORD_NUM_RE = re.compile(r"\b(?:two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
                         r"(?:thir|four|fif|six|seven|eigh|nine)teen|twenty|thirty|forty|fifty|"
                         r"sixty|seventy|eighty|ninety|hundred|thousand|dozen)\b", re.IGNORECASE)


def _stem(word):
    return word.casefold().rstrip("s")


def scope_count(scope, thing=""):
    """The count a scope bounds, or None: N in `k of N` (the population, so `7 of 8` and `9 listed`
    contradict), else the numeral itself; the first one that is not a date or an evidence count
    wins. A unit the metric's counted `thing` names is the subject, so it counts (`8 job posts`)."""
    scope = SCOPE_DATE_RE.sub(lambda d: " " * len(d.group()), scope)
    named = {_stem(w) for w in re.findall(r"\w+", thing)}
    for m in NUM_RE.finditer(scope):
        pair = SCOPE_PAIR_RE.match(scope, m.start())
        tok, end = (pair.group(1), pair.end()) if pair else (m.group(), m.end())
        unit = EVIDENCE_UNIT_RE.match(scope, end)
        if not unit or _stem(unit.group(1)) in named:
            return norm_num(tok)
    return None


def metric_key(metric):
    """One key per spelling: case, runs of space and the space around `:` all fold."""
    return re.sub(r"\s*:\s*", ":", " ".join(metric.split())).casefold()

# EXEMPTIONS, and why each one. A fenced block is machinery being shown, not a claim. A URL's digits
# are part of an address. An ISO date is the document stamp and the snapshot's `captured`, both
# machine-read fields with their own gates (`tools/date-stamp.sh`, GATE 4). Nothing else is exempt:
# a table cell's number is checked exactly as a sentence's is, because the bar's TRUTH line says
# tables carry the prose's caveat, and the Northwind table cell that rounded off its prose caveat is the
# top recurring defect of the last three runs.
FENCE_RE = re.compile(r"^```", re.MULTILINE)
CODE_SPAN_RE = re.compile(r"`[^`\n]*`")
URL_RE = re.compile(r"https?://\S+")
ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")

RULES = ("L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9", "L10", "L11", "L12", "L13", "L14",
         "L15", "L16", "L17", "L18", "L19", "L20", "L21", "L22", "B1", "B2", "B3", "B4")
# L19, W2-rulings.md G38: an `en` evidence row whose quote is a page fragment owes a gloss, the
# card's words in its place. The fragment test is `build/web.py`'s `quote_is_fragment`, not restated.
# L18, W2-rulings.md G31: a gloss is page text, printed on a card, so it meets the page's voice rules.
# The rules are not restated here: L18 runs `build/web.py`'s own page lint, `page_lints`, on every
# gloss in one file, as the cards share one page. The page allows one semicolon across all its text
# (`quality-bar/04-banned-patterns.tsv`, threshold 2), and the author's prose owns it, so the file
# opens on a line that spends it: any semicolon in a gloss reds.
GLOSS_LINT_SPENT = "The author holds the one semicolon; no gloss takes it."

# Typographic quotes fold to their ASCII forms on both sides of L12: a page sets `’` where an
# extractor types `'`, and the words are the same words (`P9-verify-2.md`, C-046).
QUOTE_FOLD = str.maketrans({"‘": "'", "’": "'", "‚": "'", "‛": "'",
                            "“": '"', "”": '"', "„": '"', "‟": '"'})


def strip_exempt(text):
    """The brief with the exempt regions blanked, line count preserved.

    Blanked and not deleted: findings name a line number, and a deletion would shift every number
    after the first fenced block, which is exactly the kind of quietly wrong report that makes a
    lint get ignored.
    """
    out = []
    in_fence = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append("")
            continue
        if in_fence:
            out.append("")
            continue
        line = CODE_SPAN_RE.sub(" ", line)
        line = URL_RE.sub(" ", line)
        line = ISO_DATE_RE.sub(" ", line)
        out.append(line)
    return out


def norm_num(tok):
    """`15,000` and `15000` are the same number. Commas are presentation."""
    return tok.replace(",", "")


def read_ledger(path):
    """Parse the ledger. Returns (rows, findings) where rows are the objects that parsed.

    A line that does not parse is an L1 finding AND is dropped from rows, so a malformed line
    cannot also generate five downstream findings about its missing fields.
    """
    findings = []
    rows = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        # Exit 2, written out rather than left to `SystemExit`. A `SystemExit` carrying a string
        # prints it and exits 1, and 1 is "findings" -- which a caller of `--client-row` reads as
        # "no row, nobody asked the question". A ledger present and unreadable is the script
        # failing to do its job, which is the sentence exit 2 exists to say.
        sys.stderr.write("FAIL: cannot read ledger %s (%s)\n" % (path, exc))
        raise SystemExit(2)
    for n, line in enumerate(text.split("\n"), start=1):
        if not line.strip():
            continue
        if line.strip().startswith("Status:"):
            # Stage 4 writes `Status: IN PROGRESS` as its first action and deletes it when the
            # first row lands. A ledger still carrying it is an unfinished ledger, and the finding
            # says so rather than reporting it as unparseable JSON.
            findings.append(("L1", "%s:%d: ledger still carries its IN PROGRESS marker" %
                             (path, n)))
            continue
        try:
            obj = json.loads(line)
        except ValueError as exc:
            findings.append(("L1", "%s:%d: line is not JSON (%s)" % (path, n, exc)))
            continue
        if not isinstance(obj, dict):
            findings.append(("L1", "%s:%d: line is JSON but not an object" % (path, n)))
            continue
        rows.append((n, obj))
    return rows, findings


def check_ledger(path, require_client_rows=False, pages=None, captures=None, typed=False, reader=None):
    """L1-L10 and L14-L18, and L11-L13 when `pages` is given, and L20-L22 when `typed` is. Returns a
    list of (rule, message). `reader` is reader.json's dict, which L22 reads under `typed`.

    `require_client_rows` turns L10 on: the research stage owes the client's side of the ledger,
    and the seed ledger written before it does not. `pages` is the fetch store L11-L13 read, and
    `captures` the one directory a `file://` capture may be indexed from (see `reached`).
    """
    rows, findings = read_ledger(path)
    if not rows and not findings:
        findings.append(("L1", "%s: ledger holds no rows" % path))
    seen = {}
    owned = {}
    counts = {}
    for n, obj in rows:
        where = "%s:%d" % (path, n)
        rid = obj.get("id", "<no id>")

        missing = [f for f in REQUIRED_FIELDS if f not in obj]
        if missing:
            findings.append(("L2", "%s: row %s is missing field(s): %s" %
                             (where, rid, ", ".join(missing))))

        if not isinstance(rid, str) or not ID_RE.match(rid or ""):
            findings.append(("L3", "%s: id %r is not of the form C-nnn" % (where, rid)))
        elif rid in seen:
            findings.append(("L3", "%s: id %s already used at line %d" % (where, rid, seen[rid])))
        else:
            seen[rid] = n

        state = obj.get("state")
        if state not in STATES:
            findings.append(("L4", "%s: row %s has state %r, want one of %s" %
                             (where, rid, state, "/".join(STATES))))

        if state in EVIDENCE_STATES:
            if not str(obj.get("quote", "")).strip():
                findings.append(("L5", "%s: row %s is %s with no quote" % (where, rid, state)))
            if not str(obj.get("url", "")).strip():
                findings.append(("L5", "%s: row %s is %s with no url" % (where, rid, state)))

        # L16. A non-English quote never reaches the brief; its `gloss` does, unquoted, after a lead
        # the page derives from `lang` (W2-rulings G8). A row that owes no quote owes no gloss, and a
        # row missing `lang` is L2's finding, not this one. A `lang` that is no two-letter code is
        # named as such, rather than asked for a gloss (G7).
        lang = obj.get("lang")
        if "lang" in obj and not (isinstance(lang, str) and LANG_RE.match(lang)):
            findings.append(("L16", "%s: row %s has lang %r, which is not an ISO 639-1 code: two "
                                    "lower-case letters, such as en or fr" % (where, rid, lang)))
        elif state in EVIDENCE_STATES and "lang" in obj and lang != EN:
            gloss = str(obj.get("gloss", ""))
            if not gloss.strip():
                findings.append(("L16", "%s: row %s quotes in lang %r with no gloss; an English "
                                        "rewording goes in gloss, and the page's lead names the "
                                        "language" % (where, rid, lang)))
            elif GLOSS_QUOTE_RE.search(gloss):
                findings.append(("L16", "%s: row %s gloss %r holds a quote mark; a gloss is a "
                                        "rewording, printed without quote marks" %
                                 (where, rid, gloss[:80])))

        claim = str(obj.get("claim", ""))
        carries = bool(NUM_RE.search(claim)) or bool(QUANT_RE.search(claim))
        if carries and not (str(obj.get("qualifier", "")).strip() or
                            str(obj.get("scope", "")).strip()):
            findings.append(("L6", "%s: row %s carries a number or quantifier with neither a "
                                   "qualifier nor a scope" % (where, rid)))

        # L14. A number says what it counts. `metric` is `<entity>:<counted thing>`, keyed on the
        # counted thing and not the row's subject: the Northwind ledger's six "9 partners" rows had five
        # subjects, so no rule keyed on `subject` could see they were one count (`68-review-2` Q3).
        # The claim's numeral always owes one; the scope's only when it counts the subject.
        scope = str(obj.get("scope", ""))
        metric = str(obj.get("metric", "")).strip()
        count = scope_count(scope, metric.partition(":")[2])
        if (NUM_RE.search(claim) or count is not None or metric) and not METRIC_RE.match(metric):
            findings.append(("L14", "%s: row %s has metric %r; a numeral in the claim, or a count "
                                    "of the subject in the scope, names what it counts as "
                                    "<entity>:<thing>" % (where, rid, metric)))
        elif metric and count is not None:
            counts.setdefault(metric_key(metric), []).append((rid, count))
        if not re.search(r"\d", scope) and WORD_NUM_RE.search(scope):
            findings.append(("L14", "%s: row %s scope %r writes its count in words; write the "
                                    "count in digits" % (where, rid, scope)))

        # L7. The typed subject is what makes a row findable at all. A blank one passes L2 -- the
        # key is there -- and leaves the row reachable only by searching its free text, which is
        # the resolution a `quote` naming a second company and a name that is a strict prefix of
        # another both answer wrongly.
        subject = obj.get("subject")
        if not isinstance(subject, str) or not subject.strip():
            findings.append(("L7", "%s: row %s has subject %r; every row names the one company it "
                                   "is about, and is resolved by that field" % (where, rid,
                                                                                subject)))
        elif state in CLIENT_STATES:
            owned.setdefault(subject.strip(), []).append(rid)

        # L9. `exclusive` is what says a closed list was read, and a `not named` row IS that
        # reading: the absence is the finding. Without this the field is prose in the schema and
        # a row can record an absence nobody bounded.
        if state == "not named" and obj.get("exclusive") is not True:
            findings.append(("L9", "%s: row %s is not named with exclusive %r; the absence is read "
                                   "off a closed list, so the row carries true" %
                             (where, rid, obj.get("exclusive"))))

        # L10, the row half. `not named` is outside EVIDENCE_STATES, so L5 asks it for nothing, and
        # L2 accepts every other field as the empty string: the absence row could assert an absence
        # nobody could check. The register and the bound are what make it readable, and they are
        # graded here rather than at the floor below because the finding belongs on the row.
        if state == "not named":
            for field in ABSENCE_EVIDENCE:
                if not str(obj.get(field, "")).strip():
                    findings.append(("L10", "%s: row %s is not named with an empty %s; a bounded "
                                            "absence names the register it was read off (source) "
                                            "and the bound of that closed list (scope)" %
                                     (where, rid, field)))

    # L8. One client-owned row per subject, so the resolver has one answer rather than a tie-break
    # to fall back on. Reported per subject and not per row: two rows are one finding.
    for subject in sorted(owned):
        ids = owned[subject]
        if len(ids) > 1:
            findings.append(("L8", "%s: subject %r carries %d client-owned rows (%s); stage 4 "
                                   "writes one" % (path, subject, len(ids),
                                                   ", ".join(str(i) for i in ids))))

    # L15. One metric, one count: two rows whose scopes bound one population at different sizes are
    # a contradiction the brief would print twice. Reported per metric, every ID named.
    for metric in sorted(counts):
        if len({c for _, c in counts[metric]}) > 1:
            findings.append(("L15", "%s: metric %r carries different counts: %s; reconcile to one "
                                    "count; give the rows separate metrics only if they count "
                                    "different things" % (path, metric, ", ".join(
                                        "%s (%s)" % (r, c) for r, c in counts[metric]))))

    # L10, the floor, and the other half of the rule graded on the row above. At least one
    # client-owned row, so the client's side of the ledger has a producer and not only a reader.
    # Without it a research stage that writes none is green here and green at every gate after it,
    # and `--client-row` then answers exit 1 for every company -- which the screen reads, correctly,
    # as "nobody asked". A run whose client-owned pages name no cohort company states that as a
    # `not named` row off the closed list it read, which L9 binds to `exclusive` true and the row
    # half binds to its register and bound: the absence is a row carrying its evidence, and neither
    # an empty ledger nor an empty row is a way to say it. The floor is one row; one row per cohort
    # company is the stage's own bar, because this file cannot see the cohort.
    if require_client_rows and not owned:
        findings.append(("L10", "%s: the ledger carries no client-owned row; the client's own "
                                "pages answer `named` or `not named` for each cohort company, and "
                                "a page naming none is a `not named` row read off that closed "
                                "list, never an absent row" % path))
    findings.extend(check_names(path, rows))
    findings.extend(check_glosses(path, rows))
    findings.extend(check_fragments(path, rows))
    if typed:
        findings.extend(check_typed(path, rows, reader))
    if pages is not None:
        findings.extend(check_pages(path, rows, pathlib.Path(pages), captures))
    return findings


def name_key(name):
    return re.sub(r"[\s-]", "", name).casefold()


def initial_case_only(a, b):
    """True when two same-key names split into the same words and differ only in first letters."""
    wa, wb = NAME_SPLIT_RE.split(a), NAME_SPLIT_RE.split(b)
    return len(wa) == len(wb) and all(x[1:] == y[1:] for x, y in zip(wa, wb))


def name_spellings(rows):
    """key -> spelling -> ids of the rows writing it, over NAME_FIELDS of every parsed row.

    Every parsed row, including one L2 flags: a row missing `lang` still prints its names.
    """
    seen = {}
    for _, obj in rows:
        rid = str(obj.get("id", "<no id>"))
        for field in NAME_FIELDS:
            text = obj.get(field)
            if not isinstance(text, str):
                continue
            toks = list(NAME_TOKEN_RE.finditer(text))
            i = 0
            while i < len(toks):
                j = i
                if any(c.isupper() for c in toks[i].group()):
                    while (j + 1 < len(toks) and any(c.isupper() for c in toks[j + 1].group())
                           and not NAME_POSSESSIVE_RE.search(toks[j].group())
                           and text[toks[j].end():toks[j + 1].start()] == " "):
                        j += 1
                spans = [text[toks[i].start():toks[j].end()]]
                before = text[:toks[i].start()].rstrip()
                if j > i and (not before or before[-1] in NAME_SENTENCE_END):
                    spans.append(text[toks[i + 1].start():toks[j].end()])
                i = j + 1
                for span in spans:
                    span = NAME_POSSESSIVE_RE.sub("", span)
                    if any(c.isalpha() for c in span):
                        seen.setdefault(name_key(span), {}).setdefault(span, set()).add(rid)
    return seen


def spelling_clash(names):
    """True when a key's spellings are one name written two ways. A key no spelling capitalises is
    a common word ("signup", "sign-up"), not a name; an all-capitals token against an all-lowercase
    one is an acronym or a caveat tag against a common word ("TIME" and "time", "INFERRED" and
    "inferred"). Both were measured as false L17s on the first six-extractor ledger (vandelay,
    2026-10-13); a brand written lowercase ("Voltwise", "voltwise") still clashes."""
    if not any(any(c.isupper() for c in n) for n in names):
        return False
    return any(not initial_case_only(a, b) and not (a.isupper() and b.islower() or
                                                     a.islower() and b.isupper())
               for a in names for b in names if a < b)


def check_names(path, rows):
    """L17: one finding per name spelled more than one way, naming every spelling and its rows."""
    findings = []
    for _, spellings in sorted(name_spellings(rows).items()):
        names = sorted(spellings)
        if spelling_clash(names):
            findings.append(("L17", "%s: one name spelled %d ways: %s; respell every row to the "
                                    "owner's own spelling, from that company's snapshot" %
                             (path, len(names), "; ".join(
                                 "%r (%s)" % (n, ", ".join(sorted(spellings[n])))
                                 for n in names))))
    return findings


def read_index(pages):
    """`pages/index.tsv` as a list of dicts keyed by INDEX_COLUMNS. Unreadable or foreign is exit 2."""
    index = pages / "index.tsv"
    try:
        lines = [ln for ln in index.read_text(encoding="utf-8").split("\n") if ln.strip()]
    except OSError as exc:
        sys.stderr.write("FAIL: cannot read fetch index %s (%s)\n" % (index, exc))
        raise SystemExit(2)
    if not lines or tuple(lines[0].split("\t")) != INDEX_COLUMNS:
        sys.stderr.write("FAIL: %s does not open with the header %s\n" %
                         (index, "\\t".join(INDEX_COLUMNS)))
        raise SystemExit(2)
    return [dict(zip(INDEX_COLUMNS, ln.split("\t"))) for ln in lines[1:]]


def read_methods(pages):
    """`pages/methods.tsv` as `{path: its last method}`. Absent is `{}`: a store written before the
    sidecar has none. A foreign header is exit 2, as for the index."""
    sidecar = pages / "methods.tsv"
    if not sidecar.exists():
        return {}
    try:
        lines = [ln for ln in sidecar.read_text(encoding="utf-8").split("\n") if ln.strip()]
    except OSError as exc:
        sys.stderr.write("FAIL: cannot read method index %s (%s)\n" % (sidecar, exc))
        raise SystemExit(2)
    if not lines or tuple(lines[0].split("\t")) != METHOD_COLUMNS:
        sys.stderr.write("FAIL: %s does not open with the header %s\n" %
                         (sidecar, "\\t".join(METHOD_COLUMNS)))
        raise SystemExit(2)
    return {cells[0]: cells[1] for cells in (ln.split("\t") for ln in lines[1:]) if len(cells) > 1}


def reached(entry, captures):
    """Whether an index row is a fetch that reached its page, so a quote may be read off it.

    A 2xx did. So does `000`, the status curl reports for `file://`, only when that file lies
    under `captures`: `fetch.py --as-url` indexes any local file under any URL, and without a named
    directory a hand-made file could stand in for the page it claims to be (`P8-verify.md` Rec3).
    A blocked, absent or failed fetch never did; provenance rule 4 records it and quotes nothing.
    """
    if REACHED_RE.match(entry.get("status", "")):
        return True
    final = entry.get("final_url", "")
    if entry.get("status") != "000" or captures is None or not final.startswith("file://"):
        return False
    local = pathlib.Path(urllib.parse.unquote(urllib.parse.urlparse(final).path)).resolve()
    return local.is_relative_to(pathlib.Path(captures).resolve())


def norm(text):
    """NFC, typographic quotes to ASCII, whitespace collapse. Never an accent fold: `Electricite` is
    not `Électricité`."""
    text = unicodedata.normalize("NFC", text).translate(QUOTE_FOLD)
    return re.sub(r"\s+", " ", text).strip()


def fold(text):
    """Case- and space-folded, for image lines only: a filename stem spells a name its own way, and
    on any site `-` and `_` stand in for its spaces (`grid-flex-logo`, `home_battery`)."""
    return "".join(re.sub(r"[-_]", " ", norm(text)).casefold().split())


def page_units(lines):
    """The text layer as one sequence of units: each table row's ` | ` cells, each other line whole.
    Two units are adjacent when nothing but a line break or a cell border lies between them."""
    units = []
    for ln in lines:
        cells = [ln] if ln.startswith(IMG_PREFIX) else ln.split(" | ")
        units.extend(c for c in (norm(c) for c in cells) if c)
    return units


def joined_on_page(q, lines):
    """A quote whose fragments the extractor joined with ` | ` or ` / `. They pass only in order and
    adjacent: the first ends a unit, each middle one IS the next unit, the last starts the one after.
    So a long line is no licence to stitch its start to its end (`P9-verify.md` R1)."""
    frags = [norm(f) for f in CELL_SPLIT_RE.split(q)]
    n = len(frags)
    if n < 2 or not all(frags):
        return False
    units = page_units(lines)
    return any(units[k].endswith(frags[0]) and units[k + n - 1].startswith(frags[-1])
               and all(units[k + i] == frags[i] for i in range(1, n - 1))
               for k in range(len(units) - n + 1))


def quote_on_page(quote, lines):
    """L12's three readings of one quote against one text layer, any one of which is enough."""
    q = norm(quote)
    if q in norm("\n".join(lines)) or joined_on_page(q, lines):
        return True
    return any(ln.startswith(IMG_PREFIX) and fold(q) in fold(ln) for ln in lines)


def check_elision(quote, texts):
    """L13, the one place an elided quote is graded. Returns the finding messages, or [].

    F3 IS UNRULED (`70-plan.md` § Needs the operator). This body is the plan's default: every quote holding
    `...` or `…` reds, so an extractor writes one row per contiguous passage. The alternative
    (`68-review-2` Q4: every segment 4 or more words, all in one text block) replaces this body
    alone; `texts`, the reached fetches' text layers, is passed so it needs no other edit.
    """
    return ["quote holds an elision; write one row per contiguous passage"]


def check_pages(path, rows, pages, captures=None):
    """L11-L13 for every row in a state that owes a quote.

    `not named`, `blocked` and `unfound` rows are exempt: they record an absence or a refusal and
    carry no quote by design, which is L5's split too. A row with no URL is skipped, since L5
    already reports it.
    """
    index, methods = read_index(pages), read_methods(pages)
    findings = []
    for n, obj in rows:
        if obj.get("state") not in EVIDENCE_STATES:
            continue
        where, rid = "%s:%d" % (path, n), obj.get("id", "<no id>")
        url, quote = str(obj.get("url", "")).strip(), str(obj.get("quote", ""))
        if not url:
            continue
        hits = [e for e in index if url in (e.get("url"), e.get("final_url"))]
        ok = [e for e in hits if reached(e, captures)]
        live = [e for e in ok if methods.get(e.get("path")) != UNVERIFIED]
        if not live:
            codes = sorted({e.get("status", "") for e in hits})
            why = ("is not a url or final_url in %s" % (pages / "index.tsv") if not hits else
                   "was rendered %s (fetch.py exit 5, status and final URL unconfirmed); "
                   "re-fetch it" % UNVERIFIED if ok else
                   "was never reached (status %s)%s" % (", ".join(codes), "; a file:// capture "
                   "counts only from under --captures" if "000" in codes else ""))
            findings.append(("L11", "%s: row %s cites %s, which %s" % (where, rid, url, why)))
            continue
        texts = []
        for e in live:
            txt = pages / (pathlib.PurePath(e.get("path", "")).stem + ".txt")
            try:
                texts.append(txt.read_text(encoding="utf-8").split("\n"))
            except OSError:
                findings.append(("L12", "%s: row %s cites %s, whose text layer %s is missing" %
                                 (where, rid, url, txt)))
        if ELISION_RE.search(quote):
            for msg in check_elision(quote, texts):
                findings.append(("L13", "%s: row %s %s" % (where, rid, msg)))
            continue
        if texts and not any(quote_on_page(quote, lines) for lines in texts):
            findings.append(("L12", "%s: row %s quote %r is not on %s's text layer" %
                             (where, rid, quote[:80], url)))
    return findings


def resolve_client_row(path, subject):
    """The one client-owned row for `subject`, or None. Ties broken by CLIENT_STATES then id.

    Resolution is field equality on `subject`, which is what a substring search over the line
    cannot be: the free text of one row names other companies, and one company's name is a strict
    prefix of another's.
    """
    rows, _ = read_ledger(path)
    want = subject.strip()
    hits = [obj for _, obj in rows
            if isinstance(obj.get("subject"), str) and obj["subject"].strip() == want
            and obj.get("state") in CLIENT_STATES]
    hits.sort(key=lambda o: (CLIENT_STATES.index(o["state"]), str(o.get("id", ""))))
    return hits


def ledger_tokens(path):
    """The numerals, quantifiers and `N of M` pairs the ledger vouches for."""
    rows, _ = read_ledger(path)
    nums, quants, pairs = set(), set(), set()
    for _, obj in rows:
        blob = " ".join(str(obj.get(f, "")) for f in ("claim", "qualifier", "scope", "quote"))
        for tok in NUM_RE.findall(blob):
            nums.add(norm_num(tok))
        for tok in QUANT_RE.findall(blob):
            quants.add(tok.lower())
        for a, b in N_OF_M_RE.findall(blob):
            pairs.add((a, b))
    return nums, quants, pairs


def en_quotes(path):
    """The normalised `quote` of every `en` row: the only words B4 lets the brief set in quotes."""
    rows, _ = read_ledger(path)
    return [norm(str(obj.get("quote", ""))) for _, obj in rows if obj.get("lang") == EN]


def curly_passages(text):
    """(line, passage) for each `“...”` outside a fenced block or code span. URLs and dates stay
    in: a passage is compared whole, so a date inside it is part of what must be verbatim."""
    lines = []
    in_fence = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            lines.append("")
        else:
            lines.append("" if in_fence else CODE_SPAN_RE.sub(" ", line))
    body = "\n".join(lines)
    return [(body.count("\n", 0, m.start()) + 1, m.group(1)) for m in CURLY_RE.finditer(body)]


def check_brief(brief_path, ledger_path):
    """B1-B4. Every numeral and quantifier in the brief traces to a row, and every quote to an `en`
    row's `quote`."""
    findings = check_ledger(ledger_path)
    try:
        text = brief_path.read_text(encoding="utf-8")
    except OSError as exc:
        # The same exit as an unreadable ledger, for the same reason: the file is there and the
        # script could not read it, which is 2 and never a count of findings.
        sys.stderr.write("FAIL: cannot read brief %s (%s)\n" % (brief_path, exc))
        raise SystemExit(2)
    nums, quants, pairs = ledger_tokens(ledger_path)

    for i, line in enumerate(strip_exempt(text), start=1):
        for tok in NUM_RE.findall(line):
            if norm_num(tok) not in nums:
                findings.append(("B1", "%s:%d: numeral %s is in no ledger row" %
                                 (brief_path, i, tok)))
        for tok in QUANT_RE.findall(line):
            if tok.lower() not in quants:
                findings.append(("B2", "%s:%d: quantifier \"%s\" is in no ledger row" %
                                 (brief_path, i, tok)))
        for a, b in N_OF_M_RE.findall(line):
            if (a, b) not in pairs:
                findings.append(("B3", "%s:%d: the bound \"%s of %s\" is in no ledger row's scope" %
                                 (brief_path, i, a, b)))
    # B4. A curly-quoted passage is a quotation, and the brief quotes English only and verbatim: a
    # non-English source is printed as its row's gloss, without quote marks.
    quotes = en_quotes(ledger_path)
    for i, passage in curly_passages(text):
        p = norm(passage)
        if not p or not any(p in q for q in quotes):
            findings.append(("B4", "%s:%d: quoted passage “%s” is not verbatim in any "
                                   "`en` row's quote; quote an `en` row, or print a non-`en` row's "
                                   "gloss unquoted" % (brief_path, i, passage[:80])))
    return findings


def report(findings, what):
    if findings:
        for rule, msg in findings:
            sys.stderr.write("FAIL: %s %s\n" % (rule, msg))
        sys.stderr.write("CLAIMS-CHECK RED (%d finding%s in %s)\n" %
                         (len(findings), "" if len(findings) == 1 else "s", what))
        return 1
    sys.stdout.write("CLAIMS-CHECK-OK (0 findings in %s)\n" % what)
    return 0


def report_client_row(path, subject):
    """Stdout carries the resolved row and nothing else, so a caller can read it as data.

    Exit 1 is NO ROW and not a finding: nobody asked the question about this company, which the
    screen reads as an unknown side rather than as an absence. The losing ids of a tie go to
    stderr, because a screener that is handed one row of two must be told the other exists.
    """
    hits = resolve_client_row(path, subject)
    if not hits:
        sys.stderr.write("NO CLIENT-OWNED ROW for %r in %s\n" % (subject, path))
        return 1
    sys.stdout.write(json.dumps(hits[0], ensure_ascii=False) + "\n")
    if len(hits) > 1:
        sys.stderr.write("NOTE: %d client-owned rows for %r; %s wins the tie-break, %s did not\n" %
                         (len(hits), subject, hits[0].get("id"),
                          ", ".join(str(o.get("id")) for o in hits[1:])))
    return 0


# --- selftest ---------------------------------------------------------------------------------
# Every rule is proved red on its own fixture, from an INDEPENDENT literal rather than by iterating
# the constant it tests: a loop over `REQUIRED_FIELDS` cannot see a field deleted from
# `REQUIRED_FIELDS`, because deleting it would delete its own case at the same time and mutate
# green. The reverse loop closes the other direction -- a name added to a constant and pinned by no
# case is a failure too. `tools/score-check.sh` holds the same discipline and the same reason.

GREEN_ROWS = [
    {"id": "C-001", "subject": "Enode",
     "claim": "Enode names 7 hardware partners on its own partners page",
     "qualifier": "publicly listed", "scope": "7 of 7 listed",
     "metric": "Enode:hardware partners listed", "quote": "Our partners",
     "url": "https://enode.com/partners", "source": "comp-enode.md:12", "state": "verified",
     "exclusive": False, "lang": "en"},
    {"id": "C-002", "subject": "Enode", "claim": "5 of 7 have dated partnership announcements",
     "qualifier": "further agreements not stated", "scope": "5 of 7",
     "metric": "Enode:partners with a dated announcement",
     "quote": "announced a partnership", "url": "https://enode.com/blog/x",
     "source": "comp-enode.md:88", "state": "verified", "exclusive": False,
     "lang": "en"},
    {"id": "C-003", "subject": "Kraken", "claim": "No GB supplier holds the licence",
     "qualifier": "as of the register read", "scope": "all 12 listed",
     "metric": "register:parties listed", "quote": "Parties", "url": "https://elexon.example/parties",
     "source": "comp-kraken.md:30", "state": "verified", "exclusive": True,
     "lang": "en"},
]

# The resolver's fixtures name their companies in lowercase placeholder form on purpose: what these
# cases test is the SHAPE of a name -- one a strict prefix of another, one appearing only inside a
# second row's quote -- and a real name would read as a claim about a real company.
CLIENT_ROW = {"id": "C-101", "subject": "company-a", "claim": "A client-owned page names it",
              "qualifier": "company-stated", "scope": "1 of 1 directory",
              "metric": "client:directories read", "quote": "company-a", "url": "https://client.example/partners",
              "source": "01-client.md:4", "state": "named", "exclusive": False,
              "lang": "en"}

# L11-L13's page store: `index.tsv` and one text layer, in `fetch.py`'s own shapes, naming a
# placeholder site. Its index holds one reached page and three fetches that never reached theirs.
PAGES_FIXTURE = ROOT / "tools" / "fixtures" / "claims-pages"
SITE = "https://www.example-grid.test"
PAGE = SITE + "/partners"


def page_row(rid, quote, url=PAGE, **kw):
    """A verified row citing the fixture page, so a case differs from the green base in one field."""
    return dict({"id": rid, "subject": "company-a", "claim": "The page says it",
                 "qualifier": "as fetched", "scope": "one page", "metric": "", "quote": quote,
                 "url": url,
                 "source": "comp-a.md:1", "state": "verified", "exclusive": False,
                 "lang": "en"}, **kw)


def _write_ledger(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


_WEB = []


def _web():
    """build/web.py, loaded once on first use: L18's page lint and L19's fragment test."""
    if _WEB:
        return _WEB[0]
    import importlib.util
    spec = importlib.util.spec_from_file_location("web_page_lint", ROOT / "build/web.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _WEB.append(mod)
    return mod


def check_fragments(path, rows):
    """L19: an `en` row that owes a quote, shows a fragment, and carries no gloss."""
    owing = [(n, obj) for n, obj in rows if obj.get("state") in EVIDENCE_STATES and obj.get("lang") == EN
             and not str(obj.get("gloss", "")).strip() and str(obj.get("quote", "")).strip()]
    if not owing:
        return []
    test = _web().quote_is_fragment
    return [("L19", "%s:%d: row %s quotes a page fragment, %r, with no gloss; the card prints the gloss "
                    "in its place, an English rewording of the quote" % (path, n, obj.get("id"), obj["quote"][:60]))
            for n, obj in owing if test(obj["quote"])]


def check_glosses(path, rows):
    """L18: every row's gloss through the page's own lint (see GLOSS_LINT_SPENT)."""
    glossed = [(n, obj) for n, obj in rows if isinstance(obj.get("gloss"), str) and obj["gloss"].strip()]
    if not glossed:
        return []
    findings = []
    with tempfile.TemporaryDirectory() as d:
        f = pathlib.Path(d) / "glosses.md"
        blocks = [GLOSS_LINT_SPENT] + [re.sub(r"\s+", " ", obj["gloss"]).strip() for _, obj in glossed]
        f.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
        results = _web().page_lints(f)
    at = re.compile(r"(?: at )?" + re.escape(str(f)) + r":(\d+):(?: |$)")
    for tool, (rc, out) in results.items():
        fails = [ln for ln in out.splitlines() if ln.startswith("FAIL")]
        if rc not in (0, 1) or (rc == 1) != bool(fails):
            findings.append(("L18", "%s: %s could not grade the glosses (exit %d): %s" %
                             (path, tool, rc, out.strip()[-200:])))
            continue
        for ln in fails:
            m = at.search(ln)
            k = (int(m.group(1)) - 3) // 2 if m else -1  # block k sits on line 3 + 2k
            if not 0 <= k < len(glossed):
                findings.append(("L18", "%s: %s: %s" % (path, tool, ln)))
                continue
            n, obj = glossed[k]
            findings.append(("L18", "%s:%d: row %s gloss fails the page's voice lint (%s): %s; a gloss "
                                    "is page text: reword it from its quote" %
                             (path, n, obj.get("id"), tool, at.sub("", ln.replace("FAIL: ", "", 1)))))
    return findings


def _rules_hit(findings):
    return sorted({r for r, _ in findings})


def selftest():
    hit = set()
    cases = 0

    def expect_red(label, findings, rule):
        nonlocal cases
        if rule not in _rules_hit(findings):
            sys.stderr.write("SELFTEST FAIL: %s did not go red on %s; got %s\n" %
                             (label, rule, _rules_hit(findings) or "<no findings>"))
            raise SystemExit(1)
        hit.add(rule)
        cases += 1
        sys.stdout.write("SELFTEST red OK   %-46s -> %s\n" % (label, rule))

    def expect_green(label, findings):
        nonlocal cases
        if findings:
            sys.stderr.write("SELFTEST FAIL: %s should be green; got %s\n" %
                             (label, [m for _, m in findings]))
            raise SystemExit(1)
        cases += 1
        sys.stdout.write("SELFTEST green OK %-46s\n" % label)

    def expect_row(label, ledger, subject, want_id):
        """The resolver returns exactly `want_id` for `subject`; None means it returns nothing."""
        nonlocal cases
        hits = resolve_client_row(ledger, subject)
        got = hits[0].get("id") if hits else None
        if got != want_id:
            sys.stderr.write("SELFTEST FAIL: %s resolved %r to %s, want %s\n" %
                             (label, subject, got, want_id))
            raise SystemExit(1)
        cases += 1
        sys.stdout.write("SELFTEST green OK %-46s -> %s\n" % (label, want_id or "no row"))

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="claims-check-selftest."))
    led = tmp / "claims.jsonl"
    brief = tmp / "briefing.md"

    _write_ledger(led, GREEN_ROWS)
    expect_green("clean ledger", check_ledger(led))

    # --- L1 -------------------------------------------------------------------------------------
    led.write_text(json.dumps(GREEN_ROWS[0]) + "\nnot json at all\n", encoding="utf-8")
    expect_red("L1 line is not JSON", check_ledger(led), "L1")

    led.write_text(json.dumps(GREEN_ROWS[0]) + "\n[1, 2]\n", encoding="utf-8")
    expect_red("L1 line is JSON but not an object", check_ledger(led), "L1")

    led.write_text("Status: IN PROGRESS\n" + json.dumps(GREEN_ROWS[0]) + "\n", encoding="utf-8")
    expect_red("L1 ledger still marked IN PROGRESS", check_ledger(led), "L1")

    led.write_text("\n\n", encoding="utf-8")
    expect_red("L1 ledger holds no rows", check_ledger(led), "L1")

    # --- L2, every required field red by its own absence ----------------------------------------
    # The literal list is independent of REQUIRED_FIELDS on purpose; the reverse loop below is what
    # catches a field added to the constant and pinned by no case here.
    pinned = ["id", "subject", "claim", "qualifier", "scope", "metric", "quote", "url", "source",
              "state", "exclusive", "lang"]
    for field in pinned:
        row = dict(GREEN_ROWS[0])
        del row[field]
        _write_ledger(led, [row])
        fs = check_ledger(led)
        if not any(r == "L2" and ("missing field(s): " + field) in m for r, m in fs):
            sys.stderr.write("SELFTEST FAIL: deleting field %r did not report it under L2; got %s\n"
                             % (field, [m for _, m in fs]))
            raise SystemExit(1)
    for field in REQUIRED_FIELDS:
        if field not in pinned:
            sys.stderr.write("SELFTEST FAIL: REQUIRED_FIELDS carries %r, which no case pins\n"
                             % field)
            raise SystemExit(1)
    if len(pinned) != 12:
        sys.stderr.write("SELFTEST FAIL: the pinned field list holds %d names, want 12\n"
                         % len(pinned))
        raise SystemExit(1)
    hit.add("L2")
    cases += 1
    sys.stdout.write("SELFTEST red OK   %-46s -> L2 (each of %d fields)\n" %
                     ("L2 required field missing", len(pinned)))

    # --- L3 -------------------------------------------------------------------------------------
    row = dict(GREEN_ROWS[0], id="enode-partners")
    _write_ledger(led, [row])
    expect_red("L3 id is not C-nnn", check_ledger(led), "L3")

    _write_ledger(led, [GREEN_ROWS[0], dict(GREEN_ROWS[1], id="C-001")])
    expect_red("L3 duplicate id", check_ledger(led), "L3")

    # --- L4, every state red by its own absence from the vocabulary -----------------------------
    _write_ledger(led, [dict(GREEN_ROWS[0], state="probably")])
    expect_red("L4 state outside the vocabulary", check_ledger(led), "L4")
    # The literal list again, independent of STATES for the same reason as the field list above: a
    # state deleted from STATES must not delete its own case, and the reverse loop catches a state
    # added to STATES that no case pins.
    pinned_states = ["verified", "unfound", "blocked", "named", "not named"]
    for st in pinned_states:
        if st not in STATES:
            sys.stderr.write("SELFTEST FAIL: the pinned state %r is not in STATES\n" % st)
            raise SystemExit(1)
    for st in STATES:
        if st not in pinned_states:
            sys.stderr.write("SELFTEST FAIL: STATES carries %r, which no case pins\n" % st)
            raise SystemExit(1)
    for st in STATES:
        row = dict(GREEN_ROWS[0], state=st, quote="q", url="https://e/x")
        _write_ledger(led, [row])
        if any(r == "L4" for r, _ in check_ledger(led)):
            sys.stderr.write("SELFTEST FAIL: state %r is in STATES but went red under L4\n" % st)
            raise SystemExit(1)

    # --- L5 -------------------------------------------------------------------------------------
    _write_ledger(led, [dict(GREEN_ROWS[0], quote="")])
    expect_red("L5 verified row with no quote", check_ledger(led), "L5")
    _write_ledger(led, [dict(GREEN_ROWS[0], url="")])
    expect_red("L5 verified row with no url", check_ledger(led), "L5")
    # A blocked row legitimately has neither, and must NOT be red: without this case L5 would be a
    # rule that bans recording a refusal, which is the opposite of provenance rule 4.
    _write_ledger(led, [dict(GREEN_ROWS[0], state="blocked", quote="", url="")])
    if any(r == "L5" for r, _ in check_ledger(led)):
        sys.stderr.write("SELFTEST FAIL: a blocked row with no quote went red under L5\n")
        raise SystemExit(1)
    cases += 1
    sys.stdout.write("SELFTEST green OK %-46s\n" % "L5 exempts a blocked row")
    # A `named` row is the client-owned side's evidence and owes the same quote and URL a verified
    # row owes: without this case the new state would be a way to assert a page said something with
    # nothing behind it.
    _write_ledger(led, [dict(GREEN_ROWS[0], state="named", quote="")])
    expect_red("L5 named row with no quote", check_ledger(led), "L5")
    # Its `not named` twin is an absence off a closed list. Red here would ban recording that the
    # client's own pages are silent, which is the finding the client's side of KNOWN rests on.
    _write_ledger(led, [dict(GREEN_ROWS[0], state="not named", quote="", url="", exclusive=True)])
    if any(r == "L5" for r, _ in check_ledger(led)):
        sys.stderr.write("SELFTEST FAIL: a not-named row with no quote went red under L5\n")
        raise SystemExit(1)
    cases += 1
    sys.stdout.write("SELFTEST green OK %-46s\n" % "L5 exempts a not-named row")

    # --- L6 -------------------------------------------------------------------------------------
    _write_ledger(led, [dict(GREEN_ROWS[1], qualifier="", scope="")])
    expect_red("L6 number with neither qualifier nor scope", check_ledger(led), "L6")
    _write_ledger(led, [dict(GREEN_ROWS[2], qualifier="", scope="")])
    expect_red("L6 quantifier with neither qualifier nor scope", check_ledger(led), "L6")
    # A claim with no number and no quantifier needs neither, or L6 would force paperwork onto
    # every row and the field would fill with noise.
    _write_ledger(led, [dict(GREEN_ROWS[0], claim="Enode sells to hardware makers",
                             qualifier="", scope="")])
    if any(r == "L6" for r, _ in check_ledger(led)):
        sys.stderr.write("SELFTEST FAIL: a plain claim went red under L6\n")
        raise SystemExit(1)
    cases += 1
    sys.stdout.write("SELFTEST green OK %-46s\n" % "L6 exempts a claim with no number")

    # --- L7, the typed subject ------------------------------------------------------------------
    # A blank subject passes L2 -- the key is present -- and is the state in which a row can only be
    # found by searching its own free text. That is the search this rule exists to make unnecessary.
    _write_ledger(led, [dict(GREEN_ROWS[0], subject="   ")])
    expect_red("L7 subject is blank", check_ledger(led), "L7")
    _write_ledger(led, [dict(GREEN_ROWS[0], subject=None)])
    expect_red("L7 subject is not a string", check_ledger(led), "L7")

    # --- L8, one client-owned row per subject ---------------------------------------------------
    _write_ledger(led, [CLIENT_ROW,
                        dict(CLIENT_ROW, id="C-102", state="not named", quote="", url="",
                             exclusive=True)])
    expect_red("L8 two client-owned rows, one subject", check_ledger(led), "L8")
    # Two client-owned rows for DIFFERENT subjects are the ordinary ledger -- stage 4 writes one per
    # cohort company -- and red here would ban the shape the rule exists to serve.
    _write_ledger(led, [CLIENT_ROW, dict(CLIENT_ROW, id="C-102", subject="company-b")])
    if any(r == "L8" for r, _ in check_ledger(led)):
        sys.stderr.write("SELFTEST FAIL: two subjects with one client-owned row each went red\n")
        raise SystemExit(1)
    cases += 1
    sys.stdout.write("SELFTEST green OK %-46s\n" % "L8 allows one row per subject")
    # Many RESEARCH rows about one company are ordinary too: only the client-owned states are
    # capped, because only they are what the screen resolves a single answer out of.
    _write_ledger(led, [GREEN_ROWS[0], GREEN_ROWS[1]])
    if any(r == "L8" for r, _ in check_ledger(led)):
        sys.stderr.write("SELFTEST FAIL: two verified rows about one subject went red under L8\n")
        raise SystemExit(1)
    cases += 1
    sys.stdout.write("SELFTEST green OK %-46s\n" % "L8 caps only the client-owned states")

    # --- L9, a not-named row is read off a closed list -------------------------------------------
    _write_ledger(led, [dict(CLIENT_ROW, id="C-103", state="not named", quote="", url="",
                             exclusive=False)])
    expect_red("L9 not-named row that is not exclusive", check_ledger(led), "L9")
    _write_ledger(led, [dict(CLIENT_ROW, id="C-103", state="not named", quote="", url="",
                             exclusive=True)])
    if any(r == "L9" for r, _ in check_ledger(led)):
        sys.stderr.write("SELFTEST FAIL: a not-named row carrying exclusive true went red\n")
        raise SystemExit(1)
    cases += 1
    sys.stdout.write("SELFTEST green OK %-46s\n" % "L9 exempts an exclusive not-named row")
    # The other states are not bound: a verified row records what a page said, not a closed list,
    # and forcing `exclusive` onto it would make the field mean nothing.
    _write_ledger(led, [dict(CLIENT_ROW, id="C-103", exclusive=False)])
    if any(r == "L9" for r, _ in check_ledger(led)):
        sys.stderr.write("SELFTEST FAIL: a named row with exclusive false went red under L9\n")
        raise SystemExit(1)
    cases += 1
    sys.stdout.write("SELFTEST green OK %-46s\n" % "L9 binds the not-named state only")

    # --- L10, the client's side exists at all ----------------------------------------------------
    # A ledger of research rows only is the state the whole client-owned mechanism dies in: every
    # rule above grades the rows that ARE there, so writing none is green, and the resolver then
    # answers "no row" for every company. Under the flag it is a finding.
    _write_ledger(led, GREEN_ROWS)
    expect_red("L10 ledger carries no client-owned row",
               check_ledger(led, require_client_rows=True), "L10")
    # The same ledger without the flag is the seed ledger the reader-frame stage grades before any
    # cohort company has been read. Red here would red a legitimate intermediate, and a rule that
    # reds its own caller's correct file is a rule that gets skipped.
    if any(r == "L10" for r, _ in check_ledger(led)):
        sys.stderr.write("SELFTEST FAIL: a research-only ledger went red under L10 unasked\n")
        raise SystemExit(1)
    cases += 1
    sys.stdout.write("SELFTEST green OK %-46s\n" % "L10 is asked for, not always on")
    # One `named` row answers it: the client's own page names that company.
    _write_ledger(led, [GREEN_ROWS[0], CLIENT_ROW])
    if any(r == "L10" for r, _ in check_ledger(led, require_client_rows=True)):
        sys.stderr.write("SELFTEST FAIL: a ledger carrying a named row went red under L10\n")
        raise SystemExit(1)
    cases += 1
    sys.stdout.write("SELFTEST green OK %-46s\n" % "L10 is answered by a named row")
    # And a `not named` row answers it too -- the bounded absence, carrying `exclusive` true. This
    # is the case that makes the rule fixable by a run that genuinely found nothing: it records the
    # closed list it read, rather than leaving the ledger silent.
    _write_ledger(led, [GREEN_ROWS[0], dict(CLIENT_ROW, id="C-104", state="not named",
                                            quote="", url="", exclusive=True)])
    if any(r == "L10" for r, _ in check_ledger(led, require_client_rows=True)):
        sys.stderr.write("SELFTEST FAIL: a bounded absence did not answer L10\n")
        raise SystemExit(1)
    cases += 1
    sys.stdout.write("SELFTEST green OK %-46s\n" % "L10 is answered by a bounded absence")

    # L10's ROW half. THE MEASURED HOLE (`59-verify.md` item 2b): `not named` is outside
    # EVIDENCE_STATES, so L5 asks the row for no quote and no URL, and L2 tests presence alone --
    # so this row, every field but the state and `exclusive` an empty string, exited 0 with zero
    # findings and satisfied the floor above on its own. One line was the whole client side.
    hollow = {"id": "C-999", "subject": "x", "claim": "", "qualifier": "", "scope": "",
              "metric": "", "quote": "", "url": "", "source": "", "state": "not named",
              "exclusive": True, "lang": "en"}
    _write_ledger(led, [hollow])
    expect_red("L10 hollow absence row", check_ledger(led, require_client_rows=True), "L10")
    # And unconditionally: the row is unreadable in the seed ledger too, and a hole a caller can
    # reach by dropping one flag is a hole.
    expect_red("L10 hollow absence row, flag unasked", check_ledger(led), "L10")
    # One field at a time, so a rule that graded only the register, or only the bound, leaves a case
    # green. Each pinned literally rather than looped over ABSENCE_EVIDENCE, which would delete its
    # own case when a field is dropped from the constant.
    for field in ("source", "scope"):
        _write_ledger(led, [dict(CLIENT_ROW, id="C-105", state="not named", quote="", url="",
                                 exclusive=True, **{field: "   "})])
        fs = check_ledger(led)
        if not any(r == "L10" and ("empty " + field) in m for r, m in fs):
            sys.stderr.write("SELFTEST FAIL: a not-named row with a blank %s did not red under "
                             "L10; got %s\n" % (field, [m for _, m in fs]))
            raise SystemExit(1)
        cases += 1
        sys.stdout.write("SELFTEST red OK   %-46s -> L10\n" % ("L10 absence row with no " + field))
    for field in ABSENCE_EVIDENCE:
        if field not in ("source", "scope"):
            sys.stderr.write("SELFTEST FAIL: ABSENCE_EVIDENCE carries %r, which no case pins\n"
                             % field)
            raise SystemExit(1)
    # The other states owe neither field to this rule: a `blocked` row records a refusal, and
    # forcing a closed list's bound onto it would red the shape provenance rule 4 exists to keep.
    _write_ledger(led, [dict(GREEN_ROWS[0], id="C-106", state="blocked", quote="", url="",
                             scope="", source="")])
    if any(r == "L10" for r, _ in check_ledger(led)):
        sys.stderr.write("SELFTEST FAIL: a blocked row with no source went red under L10\n")
        raise SystemExit(1)
    cases += 1
    sys.stdout.write("SELFTEST green OK %-46s\n" % "L10 binds the not-named state only")

    # --- L14, a numeral names what it counts ------------------------------------------------------
    # The claim half and the scope half each red on their own, and so does a metric missing a half.
    _write_ledger(led, [dict(GREEN_ROWS[0], scope="all listed", metric="")])
    expect_red("L14 numeral in the claim only, empty metric", check_ledger(led), "L14")
    _write_ledger(led, [dict(CLIENT_ROW, claim="A client-owned page names it", metric=" ")])
    expect_red("L14 numeral in the scope only, blank metric", check_ledger(led), "L14")
    for bad_metric in ("partners", "company-a:", ":partners"):
        _write_ledger(led, [dict(GREEN_ROWS[0], metric=bad_metric)])
        expect_red("L14 metric %r lacks a half" % bad_metric, check_ledger(led), "L14")
    _write_ledger(led, [page_row("C-118", "q")])
    expect_green("L14 exempts a row holding no numeral", check_ledger(led))
    # A scope that counts the evidence read bounds the reading, not the subject: it owes nothing.
    for ev in ("1 page read", "22 fetched pages", "1 press release", "3 posts (blog)",
               "2 Pages read", "as of Sep 2026"):
        _write_ledger(led, [page_row("C-119", "q", scope=ev)])
        expect_green("L14 exempts an evidence count, %r" % ev, check_ledger(led))
    # One word may sit before the unit, not two (C-027's shape fails closed); and a count written
    # in words is one no rule can compare.
    for sc in ("3 other own-site sources", "seven of eight partners"):
        _write_ledger(led, [page_row("C-119", "q", scope=sc)])
        expect_red("L14 owes a metric or digits, %r" % sc, check_ledger(led), "L14")

    # --- L15, one metric carries one count ----------------------------------------------------------
    # The replay's C-017 / C-020 shape: two rows about different subjects bound one list, and in
    # `k of N` the count is N. The metric key folds case, space runs and the space around `:`.
    # The message says reconcile: separate metrics are how an 8-against-9 error ships.
    pair = [dict(CLIENT_ROW, id="C-017", subject="company-b", scope="7 of 8 partners",
                 claim="Seven of the eight partners the client names appear in its registry",
                 metric="company-a:named partners"),
            dict(CLIENT_ROW, id="C-020", subject="company-c", state="not named", quote="",
                 url="", exclusive=True, claim="Not among the 9 distinct partners named",
                 scope="9 distinct partners listed", metric="Company-A :  named partners")]
    _write_ledger(led, pair)
    fs = check_ledger(led)
    expect_red("L15 `7 of 8` against 9 on one metric", fs, "L15")
    if not any(r == "L15" and "C-017 (8)" in m and "C-020 (9)" in m and "reconcile to one count"
               in m and "split the metric" not in m for r, m in fs):
        sys.stderr.write("SELFTEST FAIL: L15 did not name C-017 (8) and C-020 (9) and say "
                         "reconcile; got %s\n" % fs)
        raise SystemExit(1)
    # A date is not the count, and a unit the metric names is the subject, not the evidence.
    for label, a, b, m in (("a leading date", "Sep 2026: 8 partners", "Sep 2026: 9 partners",
                            "company-a:named partners"),
                           ("an evidence unit the metric names", "8 job posts", "9 job posts",
                            "company-a:job posts")):
        _write_ledger(led, [dict(pair[0], scope=a, metric=m), dict(pair[1], scope=b, metric=m)])
        expect_red("L15 8 against 9 behind " + label, check_ledger(led), "L15")
    # Green: the corrected `7 of 9`; 9 against 9, where a later numeral must not stand in for the
    # first; and two `k of N` rows with one N.
    for label, a, b in (("`7 of 9` against 9", "7 of 9 partners", "9 distinct partners listed"),
                        ("9 against 9", "9 partners named, 3 added in 2025", "9 listed"),
                        ("`5 of 7` against `7 of 7`", "5 of 7", "7 of 7 listed"),
                        ("`1 posting of 12` against 12", "1 posting of 12", "all 12 listed"),
                        ("`7 of the 9` against 9", "7 of the 9 partners", "9 listed"),
                        ("a dated 9 against 9", "as of 14 Sep 2026, 9 partners", "9 listed"),
                        ("`1,500` against `1500`", "1,200 of 1,500 installers", "1500 listed"),
                        ("a row with no count", "1 page read", "9 listed")):
        _write_ledger(led, [dict(pair[0], scope=a), dict(pair[1], scope=b)])
        expect_green("L15 one metric, " + label, check_ledger(led))

    # --- L16, a non-English quote carries an unquoted English gloss -------------------------------
    # The ruling's shape (`43-rulings.md:83-92`): the French quote stays as proof, and the gloss
    # rewords it in English and holds no quote mark. The page's lead names the language, from
    # `lang`, so the gloss does not (W2-rulings G8).
    fr_row = dict(page_row("C-301", "Nous travaillons avec Électricité Réseau"),
                  claim="The page says it works with Électricité Réseau", lang="fr",
                  gloss="Its page says it works with Électricité Réseau")
    _write_ledger(led, [fr_row])
    expect_green("L16 non-en quote row with a gloss", check_ledger(led))
    no_gloss = dict(fr_row)
    del no_gloss["gloss"]
    _write_ledger(led, [no_gloss])
    expect_red("L16 non-en quote row with no gloss", check_ledger(led), "L16")
    _write_ledger(led, [dict(fr_row, gloss="  ")])
    expect_red("L16 non-en quote row, blank gloss", check_ledger(led), "L16")
    for mark in ("“works with”", '"works with"', "'works with'", "«travaillons»", "‘works’"):
        _write_ledger(led, [dict(fr_row, gloss="Its page says it %s them" % mark)])
        expect_red("L16 gloss holding %s" % mark, check_ledger(led), "L16")
    # An apostrophe is not a quote mark: an English gloss writes possessives.
    _write_ledger(led, [dict(fr_row, gloss="The company's page names its partners’ grid")])
    expect_green("L16 allows an apostrophe in a gloss", check_ledger(led))
    # A row that owes no quote owes no gloss, and a row missing `lang` is L2's finding alone.
    blocked_fr = dict(no_gloss, state="blocked", quote="", url="")
    _write_ledger(led, [blocked_fr])
    expect_green("L16 exempts a non-en row owing no quote", check_ledger(led))
    no_lang = dict(fr_row)
    del no_lang["lang"]
    _write_ledger(led, [no_lang])
    if _rules_hit(check_ledger(led)) != ["L2"]:
        sys.stderr.write("SELFTEST FAIL: a row with no lang should red L2 alone; got %s\n" %
                         _rules_hit(check_ledger(led)))
        raise SystemExit(1)
    cases += 1
    sys.stdout.write("SELFTEST green OK %-46s\n" % "L16 leaves a missing lang to L2")
    # G7: a `lang` that is no two-letter code is named as one, on any row, never asked for a gloss.
    for bad, row in (("EN", fr_row), ("English", fr_row), ("en-GB", fr_row), ("", fr_row),
                     (None, fr_row), ("French", blocked_fr)):
        _write_ledger(led, [dict(row, lang=bad)])
        msgs = [m for r, m in check_ledger(led) if r == "L16"]
        if not msgs or not all("not an ISO 639-1 code" in m and "gloss" not in m for m in msgs):
            sys.stderr.write("SELFTEST FAIL: lang %r should red L16 as no ISO 639-1 code; got %s\n"
                             % (bad, msgs))
            raise SystemExit(1)
        expect_red("L16 lang %r is no ISO 639-1 code" % bad, check_ledger(led), "L16")

    # --- L18, a gloss meets the page's voice rules (G31) -----------------------------------------
    # web.py's page lint on the glosses: a process subject, a semicolon (the page's one is the
    # author's) and an LLM tell each red, and the finding names the row that carries it.
    for label, gloss in (("a process subject", "No carmaker is named on the 17 pages read"),
                         ("one semicolon", "It works with Électricité Réseau; it names no carmaker"),
                         ("an ai-smell tell", "It offers a robust grid service to Électricité Réseau")):
        _write_ledger(led, [dict(fr_row, id="C-302"), dict(fr_row, gloss=gloss)])
        found = check_ledger(led)
        expect_red("L18 gloss with %s" % label, found, "L18")
        if not all("row C-301 gloss" in m for r, m in found if r == "L18") or _rules_hit(found) != ["L18"]:
            sys.stderr.write("SELFTEST FAIL: L18 should name row C-301 alone; got %s\n" % found)
            raise SystemExit(1)
    _write_ledger(led, [dict(fr_row, id="C-302"), dict(fr_row, gloss="It works with Électricité Réseau and names no carmaker")])
    expect_green("L18 two clean glosses", check_ledger(led))

    # --- L19, a fragment quote owes a gloss (G38) ------------------------------------------------
    en_row = page_row("C-303", "Northwind works with [Enode](https://enode.com/) on EVs", claim="It works with Enode",
                      lang="en")
    _write_ledger(led, [en_row])
    expect_red("L19 a Markdown-link quote with no gloss", check_ledger(led), "L19")
    _write_ledger(led, [dict(en_row, quote="Plans | Pricing | Contact")])
    expect_red("L19 a pipe-joined fragment with no gloss", check_ledger(led), "L19")
    _write_ledger(led, [dict(en_row, gloss="It works with Enode on EVs")])
    expect_green("L19 the fragment row with its gloss", check_ledger(led))
    _write_ledger(led, [dict(en_row, quote="Northwind works with Enode on EVs")])
    expect_green("L19 a whole-sentence quote owes no gloss", check_ledger(led))

    # --- L17, one name, one spelling -------------------------------------------------------------
    # The oracle's shape (`P20-verify-2.md:123-126`): one brand split, capitalised and lowercase
    # across rows, in placeholder names. One finding names every spelling and its rows.
    def named(rid, claim, **kw):
        return page_row(rid, "q", claim=claim, **kw)
    trio = [named("C-401", "The strip shows Volt Wise and Pod"),
            named("C-402", "Testimonials come from Pod, Voltwise and Easel"),
            named("C-403", "It worked with voltwise on the first asset")]
    _write_ledger(led, trio)
    fs = check_ledger(led)
    expect_red("L17 one name split, capitalised, lowercase", fs, "L17")
    want = "'Volt Wise' (C-401); 'Voltwise' (C-402); 'voltwise' (C-403)"
    l17 = [m for r, m in fs if r == "L17"]
    if len(l17) != 1 or want not in l17[0] or "owner's own spelling" not in l17[0]:
        sys.stderr.write("SELFTEST FAIL: L17 did not report one finding naming %s; got %s\n" %
                         (want, l17))
        raise SystemExit(1)
    # A row L2 flags still prints its names, so L17 reads it: the oracle ledger has no `lang`, so
    # every row reds L2, and L17 must grade those rows as they are.
    no_lang_trio = trio[:2] + [dict(trio[2])]
    del no_lang_trio[2]["lang"]
    _write_ledger(led, no_lang_trio)
    fs = check_ledger(led)
    expect_red("L17 reads a row L2 has flagged", fs, "L17")
    if "L2" not in _rules_hit(fs) or not any(r == "L17" and "'voltwise' (C-403)" in m
                                             for r, m in fs):
        sys.stderr.write("SELFTEST FAIL: L17 skipped the row L2 flagged; got %s\n" % fs)
        raise SystemExit(1)
    for label, a, b in (("an inner capital", "VoltWise", "Voltwise"),
                        ("a hyphen", "Volt-Wise", "VoltWise")):
        _write_ledger(led, [named("C-401", a + " names it"), named("C-402", "It names " + b)])
        expect_red("L17 " + label, check_ledger(led), "L17")
    for field in ("subject", "claim", "qualifier", "scope", "metric", "gloss"):
        _write_ledger(led, [named("C-401", "VoltWise names it"),
                            dict(named("C-402", "It names it"), **{field: "Voltwise:x list"})])
        expect_red("L17 reads %s" % field, check_ledger(led), "L17")
    # Green: sentence and title case on a common word, and the page's own words in `quote`.
    for label, a, b in (("sentence case", "Grid operators sign it", "It signs the grid operator"),
                        ("title case", "It bids in the Balancing Mechanism",
                         "It holds no balancing-mechanism unit"),
                        ("a common word two ways", "Its sign-up form", "Its signup page"),
                        ("an acronym against a common word", "A quote from TIME's COO",
                         "It saves time"),
                        ("a caveat tag against a common word", "budget line [INFERRED]",
                         "status inferred from subdomains")):
        _write_ledger(led, [named("C-401", a), named("C-402", b)])
        expect_green("L17 allows " + label, check_ledger(led))
    _write_ledger(led, [named("C-401", "It runs on NGINX"), named("C-402", "or on Nginx")])
    expect_red("L17 capitals against title case", check_ledger(led), "L17")
    _write_ledger(led, [page_row("C-401", "voltwise", claim="VoltWise names it")])
    expect_green("L17 leaves quote to the page", check_ledger(led))
    # The oracle's EV/Ev shape, in placeholders: an acronym against one word of a longer name is
    # two names, while the same brand in two stylings, each standing alone, is one.
    _write_ledger(led, [named("C-401", "It lists makes on its VW tab"),
                        named("C-402", "No unit carries the Vw Dot Grid name")])
    expect_green("L17 an acronym against a longer name", check_ledger(led))
    _write_ledger(led, [named("C-401", "It serves BMW and VOLTA drivers"),
                        named("C-402", "It lists Audi, Volta, Nissan")])
    expect_red("L17 one brand in two stylings", check_ledger(led), "L17")
    # The run reading's two narrowings: a sentence's first word drops off a run, and a possessive
    # ends a run and loses its `'s`.
    for label, a in (("a run opening a sentence", "Its partner is listed. The Volt Wise app pairs"),
                     ("a possessive inside a run", "It pairs with Volt Wise's Grid Hub"),
                     ("a possessive alone", "It pairs with Volt-Wise’s app")):
        _write_ledger(led, [named("C-401", a), named("C-402", "It names Voltwise")])
        expect_red("L17 reads " + label, check_ledger(led), "L17")
    # The first word drops at a field's start and after each sentence mark, never mid-sentence.
    _write_ledger(led, [named("C-401", "The Volt Wise app pairs"), named("C-402", "It names Voltwise")])
    expect_red("L17 reads a run opening a field", check_ledger(led), "L17")
    for mark in (".", "!", "?", ":", ";"):
        _write_ledger(led, [named("C-401", "It is listed%s The Volt Wise app pairs" % mark),
                            named("C-402", "It names Voltwise")])
        expect_red("L17 reads a run after %r" % mark, check_ledger(led), "L17")
    _write_ledger(led, [named("C-401", "It is listed, The Volt Wise app pairs"),
                        named("C-402", "It names Voltwise")])
    expect_green("L17 keeps a mid-sentence run whole", check_ledger(led))

    # --- the resolver, one case per class a substring search answers wrongly ---------------------
    # A strict prefix. A search for `company-a` over the line returns both rows here; the field is
    # typed, so equality returns one, and the longer name returns the longer company's row.
    #
    # The two rows are arranged so a WEAKENED equality is caught rather than passed over: the
    # longer company holds the `named` row and the lower id, so a resolver matching on a prefix
    # rather than the whole field wins the tie-break with the WRONG row and this case reports it.
    # MEASURED: with `==` swapped for `startswith`, the arrangement the other way round leaves both
    # assertions green, which is a case that proves nothing.
    _write_ledger(led, [dict(CLIENT_ROW, id="C-101", subject="company-ab"),
                        dict(CLIENT_ROW, id="C-102", subject="company-a", state="not named",
                             quote="", url="", exclusive=True)])
    expect_green("two subjects, one a prefix of the other", check_ledger(led))
    expect_row("a strict-prefix name gets its own row", led, "company-a", "C-102")
    expect_row("the longer name gets the longer row", led, "company-ab", "C-101")

    # A quote names the company beside the one the row is about. L5 forces a `named` row to carry a
    # verbatim quote, and a client-controlled page's words name whoever they name.
    _write_ledger(led, [dict(CLIENT_ROW, quote="company-a replaced company-b in our stack")])
    expect_row("a company named only inside a quote", led, "company-b", None)

    # A row that never spells its company anywhere in its free text. Stage 4 writes these and no
    # rule requires otherwise, so a search finds nothing and the side reads as never asked.
    _write_ledger(led, [dict(CLIENT_ROW, id="C-104", subject="company-c", state="not named",
                             claim="The directory the client controls does not name it",
                             quote="", url="", exclusive=True)])
    expect_row("a row that never spells its company", led, "company-c", "C-104")

    # A research row is not a client-owned row, whatever its subject: the client's side is decided
    # on the two client-owned states alone.
    _write_ledger(led, [GREEN_ROWS[0]])
    expect_row("a verified row is not the client-owned one", led, "Enode", None)

    # No row at all, which is the case the screen reads as an unknown side.
    _write_ledger(led, [CLIENT_ROW])
    expect_row("a company with no client-owned row", led, "company-z", None)

    # THE TIE-BREAK, both directions. L8 reds both of these ledgers; the resolver answers them the
    # same way every time anyway, which is what stops the side being decided by which row a reader
    # happened to see first.
    _write_ledger(led, [dict(CLIENT_ROW, id="C-101", state="not named", quote="", url="",
                             exclusive=True),
                        dict(CLIENT_ROW, id="C-102")])
    expect_row("named outranks not named", led, "company-a", "C-102")
    _write_ledger(led, [dict(CLIENT_ROW, id="C-109"), dict(CLIENT_ROW, id="C-102")])
    expect_row("the lowest id wins between equals", led, "company-a", "C-102")

    # THE COMMAND CONTRACT, through main() and not the resolver, because what stage 5 reads is an
    # exit code and one line on stdout. Three codes with three meanings -- a row, no row, could not
    # do the job -- and stdout carrying the row ALONE is what lets the caller read it as data.
    _write_ledger(led, [CLIENT_ROW])
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc_hit = main(["claims-check.py", "--client-row", "company-a", str(led)])
        stdout_hit = out.getvalue()
        rc_miss = main(["claims-check.py", "--client-row", "company-z", str(led)])
        rc_absent = main(["claims-check.py", "--client-row", "company-a", str(tmp / "none.jsonl")])
        rc_usage = main(["claims-check.py", "--client-row"])
    lines = [ln for ln in stdout_hit.split("\n") if ln.strip()]
    if (rc_hit, rc_miss, rc_absent, rc_usage) != (0, 1, 2, 2):
        sys.stderr.write("SELFTEST FAIL: --client-row exits are %s, want (0, 1, 2, 2)\n" %
                         ((rc_hit, rc_miss, rc_absent, rc_usage),))
        raise SystemExit(1)
    if len(lines) != 1 or json.loads(lines[0]).get("id") != "C-101":
        sys.stderr.write("SELFTEST FAIL: --client-row stdout is %r, want the one row\n" %
                         stdout_hit)
        raise SystemExit(1)
    cases += 1
    sys.stdout.write("SELFTEST green OK %-46s -> %s\n" %
                     ("--client-row exits 0 / 1 / 2", "one row on stdout"))

    # THE FLAG IS WIRED, through main() and not the function, because what the research stage runs
    # is a command line. A flag parsed and dropped leaves L10 unreachable from every caller, which
    # is the rule shipping inert.
    noclient = tmp / "noclient.jsonl"
    _write_ledger(noclient, GREEN_ROWS)
    _write_ledger(led, [GREEN_ROWS[0], CLIENT_ROW])
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc_none = main(["claims-check.py", "--ledger", str(noclient), "--require-client-rows"])
        rc_unasked = main(["claims-check.py", "--ledger", str(noclient)])
        rc_owned = main(["claims-check.py", "--ledger", str(led), "--require-client-rows"])
        # A misspelt flag is usage, so it cannot read as "no" and pass a ledger the caller meant
        # to have graded.
        rc_typo = main(["claims-check.py", "--ledger", str(led), "--require-client-row"])
    if (rc_none, rc_unasked, rc_owned, rc_typo) != (1, 0, 0, 2):
        sys.stderr.write("SELFTEST FAIL: --ledger exits are %s, want (1, 0, 0, 2)\n" %
                         ((rc_none, rc_unasked, rc_owned, rc_typo),))
        raise SystemExit(1)
    if "L10" not in err.getvalue():
        sys.stderr.write("SELFTEST FAIL: --require-client-rows exited 1 without naming L10; "
                         "stderr was %r\n" % err.getvalue())
        raise SystemExit(1)
    cases += 1
    sys.stdout.write("SELFTEST green OK %-46s -> %s\n" %
                     ("--require-client-rows reds an empty side", "L10"))
    noclient.unlink()

    # A LEDGER PRESENT AND UNREADABLE IS EXIT 2. `SystemExit` carrying a string exits 1, and 1 is
    # the code `--client-row` uses for "no row, nobody asked" -- so the reason reaching the reader
    # would be the wrong one. A directory is the unreadable file every user has, root included; a
    # `chmod 000` fixture would be readable by root and this case would pass without running.
    try:
        # Its own message goes to stderr; swallowed here so the selftest's output is its cases.
        with contextlib.redirect_stderr(io.StringIO()):
            read_ledger(tmp)
    except SystemExit as exc:
        rc_unreadable = exc.code
    else:
        rc_unreadable = "no SystemExit"
    if rc_unreadable != 2:
        sys.stderr.write("SELFTEST FAIL: an unreadable ledger exits %r, want 2\n" % rc_unreadable)
        raise SystemExit(1)
    cases += 1
    sys.stdout.write("SELFTEST green OK %-46s -> %s\n" % ("an unreadable ledger exits 2", "2"))

    # --- the brief rules ------------------------------------------------------------------------
    _write_ledger(led, GREEN_ROWS)
    brief.write_text(
        "# Brief\n\n"
        "Enode lists 7 hardware partners, and 5 of 7 carry a dated announcement.\n"
        "No GB supplier holds the licence.\n", encoding="utf-8")
    expect_green("clean brief against the clean ledger", check_brief(brief, led))

    brief.write_text("# Brief\n\nEnode reaches 15,000 installers.\n", encoding="utf-8")
    expect_red("B1 numeral in no ledger row", check_brief(brief, led), "B1")

    brief.write_text("# Brief\n\nEnode is the first to reach them.\n", encoding="utf-8")
    expect_red("B2 quantifier in no ledger row", check_brief(brief, led), "B2")

    brief.write_text("# Brief\n\n5 of 12 listed parties are registered.\n", encoding="utf-8")
    expect_red("B3 bound in no ledger row's scope", check_brief(brief, led), "B3")

    # THE COMMA CASE. The ledger may write a thousands separator where the brief does not, or the
    # reverse. Without normalisation B1 would fire on the punctuation and the rule would be noise.
    _write_ledger(led, [dict(GREEN_ROWS[0], claim="15,000 installers", scope="15,000")])
    brief.write_text("# Brief\n\nIt reaches 15000 installers.\n", encoding="utf-8")
    if any(r == "B1" for r, _ in check_brief(brief, led)):
        sys.stderr.write("SELFTEST FAIL: 15000 went red against a ledger row carrying 15,000\n")
        raise SystemExit(1)
    cases += 1
    sys.stdout.write("SELFTEST green OK %-46s\n" % "B1 normalises thousands separators")

    # THE EXEMPTIONS, each proved to blank its region. Each of these is red without the exemption,
    # because none of these numerals is in the ledger.
    _write_ledger(led, GREEN_ROWS)
    for label, body in (
        ("a fenced block", "# Brief\n\n```\nport 8080 and 9999\n```\n"),
        ("a code span", "# Brief\n\nSet `timeout 4242` before running.\n"),
        ("a URL", "# Brief\n\nSee https://example.com/post/31415 for the record.\n"),
        ("an ISO date", "# Brief\n\nCaptured 2026-09-18.\n"),
    ):
        brief.write_text(body, encoding="utf-8")
        fs = [m for r, m in check_brief(brief, led) if r == "B1"]
        if fs:
            sys.stderr.write("SELFTEST FAIL: %s was not exempt from B1; got %s\n" % (label, fs))
            raise SystemExit(1)
        cases += 1
        sys.stdout.write("SELFTEST green OK %-46s\n" % ("B1 exempts " + label))

    # A TABLE CELL IS NOT EXEMPT. The top recurring defect of the last three runs is a table cell
    # rounding off the prose's caveat, so the one thing this lint must not do is stop at the pipe.
    brief.write_text("# Brief\n\n| Company | Partners |\n|---|---|\n| Enode | 4242 |\n",
                     encoding="utf-8")
    if not any(r == "B1" for r, _ in check_brief(brief, led)):
        sys.stderr.write("SELFTEST FAIL: a numeral inside a table cell was not checked\n")
        raise SystemExit(1)
    cases += 1
    sys.stdout.write("SELFTEST red OK   %-46s -> B1\n" % "B1 reads inside a table cell")

    # LINE NUMBERS SURVIVE A FENCED BLOCK. Blanking rather than deleting is what makes the report
    # usable; without it every finding after the first fence points at the wrong line.
    # The fixture's own line numbering, so the expectation is readable rather than counted twice:
    # 1 `# Brief`, 2 blank, 3 fence open, 4 `1`, 5 `2`, 6 fence close, 7 blank, 8 the sentence.
    brief.write_text("# Brief\n\n```\n1\n2\n```\n\nIt reaches 4242 installers.\n",
                     encoding="utf-8")
    fs = [m for r, m in check_brief(brief, led) if r == "B1"]
    if not fs or ":8:" not in fs[0]:
        sys.stderr.write("SELFTEST FAIL: line number after a fenced block is wrong; got %s\n" % fs)
        raise SystemExit(1)
    cases += 1
    sys.stdout.write("SELFTEST green OK %-46s\n" % "line numbers survive a fenced block")

    # --- B4, the brief quotes English only, verbatim ---------------------------------------------
    # The plan's pass (`73-web-plan.md:188-189`): one French quote row; its passage curly-quoted
    # reds, and its gloss printed unquoted greens.
    _write_ledger(led, GREEN_ROWS + [fr_row])
    brief.write_text("# Brief\n\nIt says “Nous travaillons avec Électricité Réseau”.\n",
                     encoding="utf-8")
    fs = check_brief(brief, led)
    expect_red("B4 a curly-quoted French passage", fs, "B4")
    if not any(r == "B4" and ":3:" in m for r, m in fs):
        sys.stderr.write("SELFTEST FAIL: B4 did not name line 3; got %s\n" % fs)
        raise SystemExit(1)
    brief.write_text("# Brief\n\n" + fr_row["gloss"] + ".\n", encoding="utf-8")
    expect_green("B4 the French row's gloss, unquoted", check_brief(brief, led))
    brief.write_text("# Brief\n\nEnode calls it “an open grid”.\n", encoding="utf-8")
    expect_red("B4 an English passage in no row's quote", check_brief(brief, led), "B4")
    brief.write_text("# Brief\n\nIt says “” here.\n", encoding="utf-8")
    expect_red("B4 an empty passage", check_brief(brief, led), "B4")
    # Verbatim, across a line break and inside a longer quote; a code span is machinery.
    brief.write_text("# Brief\n\nEnode “announced a\npartnership”. Run `say “x”`.\n",
                     encoding="utf-8")
    expect_green("B4 an en passage across a line break", check_brief(brief, led))

    # --- L11-L13, a quote read off a page this run fetched -------------------------------------
    # The store is the committed fixture, copied so the capture cases can index an absolute path.
    # One row per ledger, so each case is red or green on its own row alone.
    store = tmp / "store"
    shutil.copytree(PAGES_FIXTURE, store)
    pages = store / "pages"

    def graded(row, captures=None):
        _write_ledger(led, [row])
        return check_ledger(led, pages=pages, captures=captures)

    # Green: plain (NFD, doubled spaces, across a line break), a table row through ` / `, a logo
    # stem in another case and spacing, and a redirect cited by its final_url.
    expect_green("L12 plain quote across a line break",
                 graded(page_row("C-201", unicodedata.normalize(
                     "NFD", "Réseau depuis  2019.\n Our partner network spans"))))
    expect_green("L12 table row, cells on one line",
                 graded(page_row("C-202", "Partner Alpha / France | 2021",
                                 gloss="Partner Alpha, in France, since 2021")))  # a fragment owes one (L19)
    expect_green("L12 image line, case and space folded",
                 graded(page_row("C-203", "sun grid")))
    expect_green("L11 a final_url is in the index",
                 graded(page_row("C-204", "Trusted by", url=PAGE + "/")))
    # The exemption: an absence or a refusal carries no quote, and the URL it names was never read.
    expect_green("L11-L13 exempt a not-named row",
                 graded(dict(CLIENT_ROW, id="C-205", state="not named", quote="",
                             url=PAGE + "-register", exclusive=True)))
    expect_green("L11-L13 exempt a blocked row",
                 graded(page_row("C-206", "a refusal", url=SITE + "/team", state="blocked")))

    # Red: the C-017 shape, a research sentence citing a page it never came from; accents stripped;
    # text-line case folding; cells on two lines; and an elided quote whose segments ARE on the page.
    expect_red("L12 a research sentence", graded(page_row(
        "C-211", "of the eight partners the client names, seven appear in its registry")), "L12")
    expect_red("L12 accent-stripped quote",
               graded(page_row("C-212", "travaillons avec Electricite Reseau")), "L12")
    expect_red("L12 case folding off an image line",
               graded(page_row("C-213", "partner ALPHA")), "L12")
    expect_red("L12 table cells on two lines",
               graded(page_row("C-214", "Partner Alpha | Contact")), "L12")
    expect_red("L13 elided quote", graded(page_row(
        "C-215", "Nous travaillons avec ... depuis 2019.")), "L13")
    expect_red("L13 elided quote, one character",
               graded(page_row("C-216", "Nous travaillons avec … depuis 2019.")), "L13")

    # Fix 1 R1 (`P9-verify.md`): fragments joined by ` / ` or ` | ` pass only in order and adjacent
    # -- consecutive lines, or consecutive cells of one table row -- so a long line is no licence
    # to stitch. A join across a line break stays green, since the extractor typed the separator.
    expect_green("L12 fragments across a line break",
                 graded(page_row("C-217", "partner network spans / three continents")))
    expect_red("L12 fragments out of order",
               graded(page_row("C-218", "France | Partner Alpha")), "L12")
    expect_red("L12 fragments skipping a cell",
               graded(page_row("C-219", "Partner Alpha | 2021")), "L12")
    expect_red("L12 fragments stitched out of one prose line",
               graded(page_row("C-220", "Nous travaillons / depuis 2019.")), "L12")
    # A middle fragment is a whole unit, in its own place: cut short, or swapped, it reds.
    expect_red("L12 a middle fragment cut short",
               graded(page_row("C-229", "Partner Alpha | Fran | 2021")), "L12")
    expect_red("L12 middle fragments swapped",
               graded(page_row("C-230", "Alpha | 2021 | France | Partner Beta")), "L12")
    # The edges (`P9-verify-2.md` Rec 1): the first fragment ENDS its unit and the last STARTS its
    # own, so a word dropped at the seam reds. `in` for either test would green these.
    expect_red("L12 first fragment short of its unit's end",
               graded(page_row("C-234", "partner network / three continents")), "L12")
    expect_red("L12 last fragment past its unit's start",
               graded(page_row("C-235", "partner network spans / continents")), "L12")
    # Typographic quotes fold on both sides (`P9-verify-2.md`, C-046): a page's `’` against a typed
    # `'`, the reverse, and double quotes, in plain text and across a join.
    for label, page, quote in (
            ("page curly, quote straight", ["We’re the “first” grid"], "We're the \"first\" grid"),
            ("page straight, quote curly", ["We're the \"first\" grid"], "We’re the “first” grid"),
            ("across a join", ["Partner’s name", "Since 2021"], "Partner's name / Since 2021")):
        expect_green("L12 quote fold, " + label,
                     [] if quote_on_page(quote, page) else [("L12", "not on the page")])
    # R2: a logo stem spells a name with `-` or `_` for its spaces, on any site.
    expect_green("L12 image stem joined by hyphens", graded(page_row("C-225", "Grid Flex")))
    expect_green("L12 image stem joined by underscores",
                 graded(page_row("C-226", "Home Battery")))
    # A reached fetch with no text layer is a finding, never a silent pass.
    expect_red("L12 reached fetch with no text layer",
               graded(page_row("C-227", "Trusted by", url=SITE + "/careers")), "L12")

    # L11 red: a URL no fetch indexed, then each index row that never reached its page. The fixture's
    # `000` row is an https fetch, which real curl never reports; only a `file://` read gets `000`.
    expect_red("L11 URL missing from the index",
               graded(page_row("C-221", "Trusted by", url=SITE + "/about")), "L11")
    for rid, tail, status in (("C-222", "/team", "403"), ("C-223", "/pricing", "404"),
                              ("C-224", "/legacy", "000 over https"), ("C-228", "/moved", "301")):
        expect_red("L11 index row never reached (%s)" % status,
                   graded(page_row(rid, "Trusted by", url=SITE + tail)), "L11")

    # `--as-url` captures (`P8-verify.md` Rec3): a `file://` read counts only from the named
    # directory, so a file made anywhere else cannot stand in for the page it is indexed under.
    capdir = store / "captures"
    capdir.mkdir()
    with open(pages / "index.tsv", "a", encoding="utf-8") as fh:
        for tail, local in (("/capture", capdir / "partners.html"),
                            ("/elsewhere", store / "partners.html")):
            fh.write("\t".join((SITE + tail, "file://" + str(local), "000", "2026-09-24T10:01:00Z",
                                "0" * 64, "2048", "pages/www.example-grid.test-1a2b3c4d.html"))
                     + "\n")
    expect_green("L11 a capture under --captures",
                 graded(page_row("C-231", "Trusted by", url=SITE + "/capture"), capdir))
    expect_red("L11 a capture with no --captures",
               graded(page_row("C-232", "Trusted by", url=SITE + "/capture")), "L11")
    expect_red("L11 a capture outside --captures",
               graded(page_row("C-233", "Trusted by", url=SITE + "/elsewhere"), capdir), "L11")

    # fetch.py exit 5 (`P8b-verify-4.md` Rec 1): a render with no readable net-log keeps curl's 200
    # in the index, so only `methods.tsv` says it is unconfirmed. Its last row per path wins.
    shutil.copy(pages / "www.example-grid.test-1a2b3c4d.txt", pages / "www.example-grid.test-2b3c.txt")
    with open(pages / "index.tsv", "a", encoding="utf-8") as fh:
        fh.write("\t".join((SITE + "/rendered", SITE + "/rendered", "200", "2026-09-24T10:02:00Z",
                            "2b3c" + "0" * 60, "2048", "pages/www.example-grid.test-2b3c.html"))
                 + "\n")
    methods = pages / "methods.tsv"
    methods.write_text("path\tmethod\tprose\npages/www.example-grid.test-1a2b3c4d.html\tcurl\t300\n"
                       "pages/www.example-grid.test-2b3c.html\tchrome-unverified\t300\n",
                       encoding="utf-8")
    expect_green("L11 a curl row beside an unverified one",
                 graded(page_row("C-236", "Trusted by")))
    fs = graded(page_row("C-237", "Trusted by", url=SITE + "/rendered"))
    expect_red("L11 a chrome-unverified render", fs, "L11")
    if not any("chrome-unverified" in m and "re-fetch" in m for _, m in fs):
        sys.stderr.write("SELFTEST FAIL: L11 did not name chrome-unverified and re-fetch; got %s\n"
                         % fs)
        raise SystemExit(1)
    with open(methods, "a", encoding="utf-8") as fh:
        fh.write("pages/www.example-grid.test-2b3c.html\tchrome\t300\n")
    expect_green("L11 a re-fetch confirms the render",
                 graded(page_row("C-238", "Trusted by", url=SITE + "/rendered")))
    saved = methods.read_text(encoding="utf-8")
    methods.write_text("path\tstatus\n", encoding="utf-8")
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            read_methods(pages)
        sys.stderr.write("SELFTEST FAIL: a foreign methods.tsv header did not exit 2\n")
        raise SystemExit(1)
    except SystemExit as exc:
        if exc.code != 2:
            raise
    cases += 1
    sys.stdout.write("SELFTEST green OK %-46s\n" % "foreign methods.tsv header exits 2")
    methods.write_text(saved, encoding="utf-8")

    # THE FLAGS ARE WIRED, through main(): a green and a red ledger, a valued flag with no value,
    # --captures alone, and a pages directory holding no index.
    _write_ledger(led, [page_row("C-241", "Trusted by")])
    bad = tmp / "bad.jsonl"
    _write_ledger(bad, [page_row("C-242", "Trusted by", url=SITE + "/about")])
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        got = (main(["claims-check.py", "--ledger", str(led), "--pages", str(pages)]),
               main(["claims-check.py", "--ledger", str(bad), "--pages", str(pages)]),
               main(["claims-check.py", "--ledger", str(led), "--pages"]),
               main(["claims-check.py", "--ledger", str(led), "--captures", str(capdir)]),
               main(["claims-check.py", "--ledger", str(led), "--pages", str(capdir)]))
    if got != (0, 1, 2, 2, 2) or "L11" not in err.getvalue():
        sys.stderr.write("SELFTEST FAIL: --pages exits are %s, want (0, 1, 2, 2, 2) with L11 "
                         "named\n" % (got,))
        raise SystemExit(1)
    cases += 1
    sys.stdout.write("SELFTEST green OK %-46s -> %s\n" % ("--pages exits 0 / 1 / 2", "L11"))
    bad.unlink()

    # A store whose index header is not fetch.py's is unreadable, exit 2: matching its rows by
    # position would read a status out of whatever column sits third.
    foreign = pages / "index.tsv"
    foreign.write_text("url\tstatus\tfinal_url\n%s\t200\t%s\n" % (PAGE, PAGE), encoding="utf-8")
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            read_index(pages)
    except SystemExit as exc:
        rc_foreign = exc.code
    else:
        rc_foreign = "no SystemExit"
    if rc_foreign != 2:
        sys.stderr.write("SELFTEST FAIL: a foreign index header exits %r, want 2\n" % rc_foreign)
        raise SystemExit(1)
    cases += 1
    sys.stdout.write("SELFTEST green OK %-46s -> %s\n" % ("a foreign index header exits 2", "2"))
    shutil.rmtree(store)

    # --- L20-L22, the typed row, asked for by --typed ---------------------------------------------
    # A placeholder company on client.example; its job ad sits on a shared host, so only that host
    # is known there, never its suffix.
    reader = {"company": {"domain": "client.example"}, "known_hosts": ["client.example", "client.jobs.example"]}

    def typed_row(rid, url, **kw):
        return dict(page_row(rid, "Our partners", url=url),
                    **dict({"question_id": "Q1", "page_id": None, "kind": "evidence", "stage": "extract-a",
                            "known": row_known(url, "client.example", reader["known_hosts"])}, **kw))
    typed_ok = [typed_row("C-201", "https://www.client.example/a"),
                typed_row("C-202", "https://client.jobs.example/role"),
                typed_row("C-203", "https://rival.example/x"),
                typed_row("C-204", "https://other.jobs.example/role", question_id=None)]
    _write_ledger(led, [dict(r) for r in GREEN_ROWS])
    expect_green("L20-L22 are asked for, not always on", check_ledger(led))
    _write_ledger(led, typed_ok)
    if [r["known"] for r in typed_ok] != [True, True, False, False]:
        sys.stderr.write("SELFTEST FAIL: row_known keyed a suffix of the shared job host, or missed "
                         "a subdomain; got %s\n" % [r["known"] for r in typed_ok])
        raise SystemExit(1)
    expect_green("L20-L22 typed rows, the host rule held", check_ledger(led, typed=True, reader=reader))
    for label, change, rule in (
            ("L20 question_id that is no Q<n>", {"question_id": "question 1"}, "L20"),
            ("L20 question_id absent", {"question_id": None, "_drop": "question_id"}, "L20"),
            ("L21 kind outside the three", {"kind": "fact"}, "L21"),
            ("L21 an absence row in an evidence state", {"kind": "absence"}, "L21"),
            ("L22 known that is no boolean", {"known": "yes"}, "L22"),
            ("L22 known against the host rule", {"known": False}, "L22")):
        row = dict(typed_ok[0], **{k: v for k, v in change.items() if k != "_drop"})
        row.pop(change.get("_drop", "_none"), None)
        _write_ledger(led, [row] + typed_ok[1:])
        fs = check_ledger(led, typed=True, reader=reader)
        expect_red(label, fs, rule)
        if _rules_hit(fs) != [rule]:
            sys.stderr.write("SELFTEST FAIL: %s red more than %s: %s\n" % (label, rule, _rules_hit(fs)))
            raise SystemExit(1)
    row = dict(typed_ok[0], known=False)
    _write_ledger(led, [row])
    expect_green("L22 without a reader grades the type only", check_ledger(led, typed=True))

    # --- every rule pinned ----------------------------------------------------------------------
    for rule in RULES:
        if rule not in hit:
            sys.stderr.write("SELFTEST FAIL: RULES carries %s, which no case proves red\n" % rule)
            raise SystemExit(1)

    for path in (led, brief):
        path.unlink()
    tmp.rmdir()

    sys.stdout.write("CLAIMS-CHECK SELFTEST OK (%d cases, %d rules)\n" % (cases, len(RULES)))
    return 0


USAGE = """usage:
  claims-check.py --ledger [path] [--require-client-rows] [--pages <dir> [--captures <dir>]]
                                           grade the ledger's shape (default
                                           $BRIEF_ROOT/claims.jsonl); the flag adds L10, which reds
                                           a ledger carrying no client-owned row; --pages adds
                                           L11-L13 against fetch.py's store, and --captures names
                                           the one directory a file:// capture may come from
                       [--typed [--reader <reader.json>]]
                                           --typed adds L20-L22 on question_id, kind and known,
                                           the fields the runner's merge writes; --reader holds
                                           known to the url's host
  claims-check.py --check <brief> [ledger] grade a brief against the ledger
  claims-check.py --client-row <company> [ledger]
                                           print the one client-owned row whose `subject` is that
                                           company; exit 1 is no such row, never a finding
  claims-check.py --selftest               prove every rule red on its own fixture
"""


def default_ledger():
    root = os.environ.get("BRIEF_ROOT")
    if root:
        return pathlib.Path(root).expanduser() / "claims.jsonl"
    return ROOT / "claims.jsonl"


def main(argv):
    if len(argv) < 2:
        sys.stderr.write(USAGE)
        return 2
    mode = argv[1]
    if mode == "--selftest":
        return selftest()
    if mode == "--ledger":
        # The flag is read wherever it sits, so the path stays the argument a caller quotes and the
        # order of the two cannot be got wrong.
        rest = argv[2:]
        require, typed, paths, valued = False, False, [], {"--pages": None, "--captures": None,
                                                           "--reader": None}
        # A misspelt flag is usage and not a silent pass: the whole point of L10 is that the run
        # asking for it gets it, and `--require-client-row` quietly meaning "no" is the defect back.
        # A valued flag with no value, or `--captures` with no `--pages` to apply it to, is usage too.
        i = 0
        while i < len(rest):
            a = rest[i]
            if a == "--require-client-rows":
                require = True
            elif a == "--typed":
                typed = True
            elif a in valued and i + 1 < len(rest) and not rest[i + 1].startswith("--"):
                valued[a] = rest[i + 1]
                i += 1
            elif a.startswith("--"):
                sys.stderr.write(USAGE)
                return 2
            else:
                paths.append(a)
            i += 1
        pages, captures = valued["--pages"], valued["--captures"]
        if (captures is not None and pages is None) or (valued["--reader"] is not None and not typed):
            sys.stderr.write(USAGE)
            return 2
        led = pathlib.Path(paths[0]) if paths else default_ledger()
        if not led.is_file():
            sys.stderr.write("FAIL: no ledger to grade at %s\n" % led)
            return 2
        if pages is not None and not (pathlib.Path(pages) / "index.tsv").is_file():
            sys.stderr.write("FAIL: no fetch index to grade against at %s/index.tsv\n" % pages)
            return 2
        reader = None
        if valued["--reader"] is not None:
            try:
                reader = json.loads(pathlib.Path(valued["--reader"]).read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                sys.stderr.write("FAIL: cannot read reader.json at %s (%s)\n" % (valued["--reader"], exc))
                return 2
        return report(check_ledger(led, require_client_rows=require, pages=pages,
                                   captures=captures, typed=typed, reader=reader), str(led))
    if mode == "--client-row":
        if len(argv) < 3 or not argv[2].strip():
            sys.stderr.write(USAGE)
            return 2
        led = pathlib.Path(argv[3]) if len(argv) > 3 else default_ledger()
        if not led.is_file():
            sys.stderr.write("FAIL: no ledger to read at %s\n" % led)
            return 2
        return report_client_row(led, argv[2])
    if mode == "--check":
        if len(argv) < 3:
            sys.stderr.write(USAGE)
            return 2
        brief = pathlib.Path(argv[2])
        led = pathlib.Path(argv[3]) if len(argv) > 3 else default_ledger()
        if not brief.is_file():
            sys.stderr.write("FAIL: no brief to grade at %s\n" % brief)
            return 2
        if not led.is_file():
            sys.stderr.write("FAIL: no ledger to grade against at %s\n" % led)
            return 2
        return report(check_brief(brief, led), "%s against %s" % (brief, led))
    sys.stderr.write(USAGE)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
