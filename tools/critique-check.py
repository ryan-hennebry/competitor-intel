#!/usr/bin/env python3
"""The findings-ledger lint. It decides which critique rows count, before the fixer applies any.

Written after reading `~/.claude/skills/writing-for-agents/SKILL.md`: the ledger is a document
agents write and agents read, so its rules live in one place, here, and the rubric points at them.

WHY THIS EXISTS. `quality-bar/06-critique-rubric.md` lines 16-30 fix the finding row and state
three rules a critic's row must meet: no quote, no deduction; the rule is named; a new claim in a
fix carries claim IDs. A rule stated in prose and graded by nobody is a rule a critic under
deadline breaks, and the fixer then applies a paraphrased quote, a rule nobody wrote, or a number
nobody sourced. This script is the grader, `63-s4-scope.md` step S4.6.

THE ROW. Ten tab-separated fields, in the rubric's order (`COLUMNS`). An optional first line naming
them is the header and is skipped. A blank line is skipped. Anything else is a row.

THE DROPS. A row is DROPPED -- it counts for nothing, the fixer never applies it -- when:

  columns    it does not carry exactly ten fields, so no other rule can read it;
  quote      its `quote` is not a verbatim substring of `briefing.md`, or is too short to locate
             the defect: under `QUOTE_MIN` letters or digits and not a whole line of the brief.
             A quote exists to point the fixer at the place. A short string is verbatim by
             coincidence: a critic with nothing to quote types `-`, `None` or `N/A`, and a
             brief's rules and table cells carry exactly those. A real finding can always quote
             more of its sentence or row; a heading cannot, so a whole line is kept at any length
             that holds a letter or digit (`|---|---|` does not);
  rule_id    its `rule_id` is not DEFINED in `quality-bar/` (a pillar heading, a refusal or rubric
             table row, a regex id) nor run as code by `tools/voice-lint.sh` (`dup_row_date`,
             R1-R4), or names a rhythm signal R1-R4 above MINOR, which the rubric rules
             advisory; an empty `rule_id` is the rubric's candidate rule and is kept only at
             severity MINOR;
  severity   its `severity` is not one of the rubric's three, `SEVERITIES`, case and all: the
             pass rule counts BLOCKER and MATERIAL by name, so `HIGH` or `blocker` counts as
             neither;
  claim_ids  its `fix_new` carries a numeral or quantifier the brief does not already carry at
             `fix_old`, and its `claim_ids` carries no claim ID. `fix_old`'s claims count as the
             brief's only when `fix_old` is verbatim in the brief: the critic writes that field
             too, and a `fix_old` the brief lacks would otherwise excuse any number it repeats;
  status     (the fixer's) its `status` is `fixed@<hex>` and the hex is under 12 characters or
             is not the start of the sha256 of the brief named on the command line, the post-fix
             `briefing.md`: a hash the tool cannot tie to the bytes closes nothing;
  space      (the fixer's) it is closed, its `fix_new` has more words than its `fix_old`, and
             `09-space.tsv` beside the ledger has no line `<id>\t<slot cut>` naming where the
             words came from (the runbook's "each fix names its space source");
  route      (stage 8's) its `status` is `routed@5` and its `quote` is not a verbatim substring
             of the LOCKED THESIS: the `## Locked thesis` section of `05-thesis.md` beside the
             ledger, from that exact heading line to the next `#` or `##` heading. A `routed@5`
             row with no such file or section is exit 2, never a drop: a misnamed heading would
             otherwise send every thesis row to the fixer unseen. The operator's ruling of 2026-09-25, "route by thesis quote": a
             rule type alone (RF1, H2) sent every P20 route-5 row to stage 5, and none quoted
             the thesis;
  fix_old    (the fixer's, page path, W3-rulings.md G58 (ii)) it is `fixed@`, and its `fix_old`
             is not in the text its `location` JSON pointer names in `brief-08.json` beside the
             ledger, nor, on a repair, in `brief-10.json`. A string is its own text, a span's is
             its `t`, a span array's is its `t` values joined with "", and an object's is its
             string and array fields so read, joined with " " in key order (W4-rulings.md G85).
             A `fixed@` row with no `brief-08.json` is exit 2.

THE RE-CHECK (W4-rulings.md G75, G85-G87; the page path). One more rule, `recheck`, owned by
`fixer`, grades `09-recheck.md` beside the ledger, not a ledger row. A FAIL row's line is NAMED by
an item of `09-fixer.md` § Rejected (a `- ` bullet with its wrapped lines, one reason each) where
it stands as a whole word; a row with an empty line cell is named by `09-recheck.md:N`, its line
in that file (G87). A FAIL row's fix column should be one double-quoted string, straight or
curly, the whole replacement with nothing outside the quotes and more than whitespace inside. In
that form, the string, stripped and with its whitespace collapsed as `web.py --text --authored`
prints text, must be in the text, or an item naming the line must not give the reason
`re-check form` (G75: a step-4 lint reds the verbatim fix). Out of that form, an item naming the
line must give the reason `re-check form` (G86 (ii)): stage 9 leaves the line, and stage 10
grades it. The text is `09-text.md`, or on a repair either it or `09-text-10.md` (G86 (iii)). A
FAIL row with neither file is exit 2. Each drop counts once against `fixer`, never in the
dropped-row count. With no `09-recheck.md` there is nothing to grade.

WHICH BYTES. The quote and claim rules grade stage 8's bytes, the brief the critics read. Stage 9
copies it to `briefing-08.md` beside the ledger before its first edit; when that file exists every
row is graded against it, so a fix that rewrites a quoted sentence neither drops that row nor
hides a neighbour quoting the same sentence. The `status` rule always hashes the named brief.

THE PAGE (`73-web-plan.md` W16). Name a `.json` brief, `$BRIEF_ROOT/brief.json`, and the page path
holds. The quote and claim rules grade `08-text.md` beside the ledger, the page text stage 8 wrote
and its critics read, which no later stage edits; with no such file the run is exit 2. The `status`
rule hashes the named `brief.json`'s bytes, as `shasum -a 256` does, and nothing else: a `fixed@`
naming the page text, a `briefing.md` or any other file closes nothing. The `space` rule is off,
because a fix that breaks a slot's schema cap reds at `brief-check.py` before any build, and that
replaces `09-space.tsv` as the space source.

TEMPLATE TEXT (W2-rulings.md G45). The page prints strings no `brief.json` field holds: the run
line, the fixed headings, Also built by Ryan, which the operator ruled fixed on 2026-10-09. Stage 9 closes a
row on one as `ruled@template`. The `status` rule keeps it only on the page path, and only when its
quote is inside a line of `08-template.md` beside the ledger: `web.py --text PAGE --template`, the
lines the template prints (G49, amending G45 and G47). It must also sit inside no string value of
the named `brief.json`, and hold none as a whole word (G51): the h1, the run line and the matrix
header interpolate company names, which are the brief's. Nor may every occurrence of it in those
lines overlap a value the line holds as a whole word (G55), so a quote taking the last word of a
two-word company name in the h1 drops. So a quote of a whole h1, run line or header row drops; quote
only the template words around a name. The run line's reformatted date and counts match no
`brief.json` string, so a quote of them stays `ruled@template`: the ruled residual (W3-rulings.md
G59). Template text is tested by what it is, so an authored line, a whole matrix row, a source line
or an evidence panel so marked is a `status` drop against the fixer. A `ruled@template` row with no
`08-template.md` is exit 2. A kept one is closed, never open.

A NEW CLAIM, mechanically. "Claim" is `tools/claims-check.py`'s definition, imported rather than
copied: a numeral or a quantifier from its vocabulary, with the same exempt regions (URLs, ISO
dates, code spans). "New" is the rubric's word: a fix that rewords a sentence and keeps its
"3 of 5" adds no claim, and demanding IDs for it would drop the rewording the voice critic exists
to write.

DROPS COUNT AGAINST THE CRITIC. The report prints drops per critic, as the rubric asks, and the
count of kept rows still open, which the fixer stage reads; a `status`, `space`, `fix_old` or
`recheck` drop counts against `fixer`, a `route` drop against `router`. A row is closed by
`fixed@<sha>` as the `status` rule reads it, and `routed@5` takes it off the fixer's count: stage 8, and only stage 8, gives that
state to a thesis-level row, which stage 5's re-lock reads and the fixer never closes; a HELD
re-lock sets it back to `open`. It is reported as routed, not open.

REPAIRABLE (W4-rulings.md G74). A dropped row is repairable when its quote locates and its only
drops are `rule_id` or `claim_ids`: the finding is placed and only its labels are wrong. The
report prints `N repairable`. Stage 8's lead re-maps each before it exits and is done at
`0 repairable`, so a sound finding filed under an undefined id reaches the fixer.

WHAT IT DOES NOT CHECK: whether the finding is right, whether a `fix_old` the brief lacks can be
applied (it only loses its claim baseline), whether a claim ID exists in `claims.jsonl`, whether
a `09-space.tsv` cut was really made, the critic vocabulary. None is in step S4.6, and the first is the
critics' judgement, not a lint's. Nor does it catch a placeholder the brief itself carries at
`QUOTE_MIN` letters or more, such as an absence cell reading `Not found`: that quote is verbatim
and long enough, and only a reader of the finding can tell it points nowhere. Off the page path, or
on a row not yet `fixed@`, it does not check that `fix_old` is the text at `location`: there a
fabricated `fix_old` verbatim elsewhere in the bytes the claim rule grades can excuse a numeral
it repeats (W3-rulings.md G58). An empty `fix_old` sits in any field. A re-check line that is a
bare number, such as `59`, is named by that number anywhere in a § Rejected item. A re-check fix
is graded as a substring of the whole text, so a short one, such as a 1-to-3-word cell, passes
wherever the page already holds those words, applied or not (G75's wording).

EXIT CODES. 0 no row dropped. 1 one or more rows dropped. 2 the script could not do its job: bad
usage (including no ledger argument with `BRIEF_ROOT` unset, since a ledger belongs to a run and
the checkout holds none), a missing or unreadable brief, ledger or `quality-bar/` file, a
`routed@5` row beside no `05-thesis.md` `## Locked thesis` section, a page `fixed@` row beside
no readable `brief-08.json`, a re-check FAIL row beside no stage 9 text, or a ledger with no rows.
A critique wave always writes rows (three weakest sentences per critic), so no rows is never
green.

PRECONDITION: none beyond the files. No network, no model call, no run directory.
"""

import collections
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
BAR = ROOT / "quality-bar"

COLUMNS = ("id", "critic", "rule_id", "severity", "quote", "location", "fix_old", "fix_new",
           "claim_ids", "status")
RULES = ("columns", "quote", "rule_id", "severity", "claim_ids", "status", "space", "route",
         "fix_old", "recheck")
# The rules a critic never breaks, and who does: their drops count against that owner.
OWNERS = {"status": "fixer", "space": "fixer", "route": "router", "fix_old": "fixer",
          "recheck": "fixer"}
# G74: the drops stage 8's lead re-maps before it exits. A row whose drops all sit in this set
# is repairable; a quote drop, or any other, leaves it a drop on its critic.
REPAIRABLE = frozenset({"rule_id", "claim_ids"})
# `quality-bar/06-critique-rubric.md`'s "Severities:" line, and `SEVERITIES` in
# `tools/critic-fixture-test.sh`, which grades a session's expected file rather than a ledger.
SEVERITIES = ("BLOCKER", "MATERIAL", "MINOR")
CANDIDATE_SEVERITY = "MINOR"
# What a quote is counted in: letters and digits, in any script. `\w` alone would count `_`.
QUOTE_WORD_RE = re.compile(r"[^\W_]")
# The fewest a quote may hold, unless it is a whole line. Measured on three exemplar briefs: of
# each brief's one-to-three-word strings under 8, 12-18% occur three or more times; from 8 up,
# 1-3%. 8 is the least that also clears the absence cells those briefs carry (`None` 4, `Unknown`
# 7). The shortest of 174 real critic quotes, from two waves on one of them, holds 15.
QUOTE_MIN = 8
# `fixed@` plus hex is a claim to have closed the row; the `status` rule decides whether it holds.
# 12 hex is the least that names one file among a run's builds (`70-plan.md` P17).
FIXED_RE = re.compile(r"^fixed@([0-9a-f]+)$")
SHA_MIN = 12
# Beside the ledger: stage 8's bytes, which stage 9 copies before its first edit, and the fixer's
# space sources, one `<row id>\t<slot cut>` line per growing fix.
BEFORE = "briefing-08.md"
SPACE = "09-space.tsv"
# The page path: a brief named with this suffix is `brief.json`, and its critics read this file.
PAGE_SUFFIX = ".json"
PAGE_TEXT = "08-text.md"
# G45, G49: a row on a fixed template string, closed by stage 9; graded against the template's lines.
RULED = "ruled@template"
TEMPLATE_TEXT = "08-template.md"
# G58 (ii), G85 (i): a page `fixed@` row's `fix_old` is read at its `location` in stage 8's data,
# the first; on a repair, the second, the data the repair started from, also counts.
DATA_08, DATA_10 = "brief-08.json", "brief-10.json"
# G75 (ii), G85 (iii), G86: the re-check's FAIL rows, graded against the fixer's text and
# § Rejected. A repair rewrites `09-text.md` and keeps stage 9's text as `09-text-10.md`; a fix in
# either counts as present (G86 (iii)).
RECHECK = "09-recheck.md"
RECHECK_TEXT = ("09-text.md", "09-text-10.md")
FIXER = "09-fixer.md"
REJECTED_HEAD = "## Rejected"
# The fix column's one form: one double-quoted string, the whole replacement, nothing outside it.
# A curly pair may hold curly quotes (G87), as a fix quoting the page's own `“ ”` does.
RECHECK_FIX_RE = re.compile(r'^(?:"([^"]+)"|“(.+)”)$')
# G86 (ii): the reason a § Rejected item gives for a FAIL whose column breaks that form.
FORM_REASON_RE = re.compile(r"re-check\s+form")
# A § Rejected item: a `- ` bullet and the lines it wraps onto.
ITEM_RE = re.compile(r"\n(?=[-*] )")

# The four files that DEFINE a rule id, and the shape each defines it in. The same four shapes as
# `rule_exists` in `tools/critic-fixture-test.sh`, parsed by field rather than grepped: a grep for
# the bare id matches it wherever it is merely MENTIONED (`03-refusals.md` cites P4 as a reason),
# and a table's header cell (`ID`) or a TSV's header field (`id`) names a column, not a rule.
PILLARS = "02-voice-card.md"
TABLES = ("03-refusals.md", "01-hiring-rubric.md")
REGEXES = "04-banned-patterns.tsv"
PILLAR_RE = re.compile(r"^## ([^\s.]+)\. ")
SEPARATOR_RE = re.compile(r"^\|\s*:?-{3,}")
# The fifth source, outside `quality-bar/`: the rules `tools/voice-lint.sh` runs as code, not as
# TSV rows. Each is defined where it prints, `print("FAIL\t<id>\t...")` or `print("SIGNAL\t<id>\t...")`
# (`dup_row_date`, the rhythm signals R1-R4), so the id is read off that line and never copied here.
# The rubric blocks on any voice-lint hit, and a hit this lint could not name was dropped (P16-verify
# R1). A lint file carrying no such line is exit 2: its print form changed, and the ids went with it.
VOICE_LINT = HERE / "voice-lint.sh"
# A SIGNAL id is advisory, as the rubric rules the rhythm signals, so it is booked at MINOR only.
LINT_ID_RE = re.compile(r'print\("(FAIL|SIGNAL)\\t([A-Za-z][A-Za-z0-9_]*)\\t')
# The state stage 8, and only stage 8, gives a thesis-level row. Stage 5's re-lock reads it, and
# it is never the fixer's to close or to write.
ROUTED = "routed@5"
# Beside the ledger: stage 5's file, whose `## Locked thesis` section is the only text a routed
# row may quote. A re-lock that CHANGES the thesis writes the new one in the same section.
THESIS = "05-thesis.md"
THESIS_HEAD = "## Locked thesis"
HEADING_RE = re.compile(r"^#{1,2} ")


class Unusable(Exception):
    """The script could not do its job. Exit 2, never a count of drops."""


def _load_claims_check():
    """`tools/claims-check.py`, imported by path because its name carries a hyphen.

    Imported, not copied, so a claim means the same thing to the author's gate and to this one.
    A missing sibling is exit 2: a lint that cannot say what a claim is cannot grade a fix.
    """
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location("claims_check", HERE / "claims-check.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except (OSError, ImportError, SyntaxError) as exc:
        sys.stderr.write("FAIL: cannot load tools/claims-check.py (%s)\n" % exc)
        raise SystemExit(2)
    return mod


CLAIMS = _load_claims_check()


def read_text(path, what):
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise Unusable("cannot read %s %s (%s)" % (what, path, exc))


def lint_ids(lint=VOICE_LINT):
    """(every code id `lint` prints, the advisory SIGNAL ones among them)."""
    found = LINT_ID_RE.findall(read_text(lint, "voice-lint"))
    if not found:
        raise Unusable("%s carries no print(\"FAIL\\t<id>\\t or SIGNAL line to read a rule id "
                       "from" % lint)
    return {i for _, i in found}, {i for kind, i in found if kind == "SIGNAL"}


def rule_ids(bar, lint=VOICE_LINT):
    """Every rule id `bar` DEFINES, in the four shapes named at `PILLARS`, plus `lint`'s code ids."""
    ids = set(lint_ids(lint)[0])
    for line in read_text(bar / PILLARS, "quality-bar file").split("\n"):
        m = PILLAR_RE.match(line)
        if m:
            ids.add(m.group(1))
    for name in TABLES:
        body = False
        for line in read_text(bar / name, "quality-bar file").split("\n"):
            if not line.startswith("|"):
                body = False
            elif SEPARATOR_RE.match(line):
                body = True
            elif body:
                ids.add(line.split("|")[1].strip())
    header = True
    for line in read_text(bar / REGEXES, "quality-bar file").split("\n"):
        if not line.strip() or line.startswith("#"):
            continue
        if header:
            header = False
            continue
        ids.add(line.split("\t")[0])
    return ids


def claim_tokens(text):
    """The numerals and quantifiers `text` asserts, by `tools/claims-check.py`'s rules."""
    blanked = " ".join(CLAIMS.strip_exempt(text))
    nums = {CLAIMS.norm_num(t) for t in CLAIMS.NUM_RE.findall(blanked)}
    return nums | {t.lower() for t in CLAIMS.QUANT_RE.findall(blanked)}


def carries_claim_id(field):
    return any(CLAIMS.ID_RE.match(t) for t in re.split(r"[,;\s]+", field))


def closed(status, sha):
    """True when `status` is `fixed@` plus SHA_MIN or more hex that `sha` starts with."""
    m = FIXED_RE.match(status)
    return bool(m and len(m.group(1)) >= SHA_MIN and sha.startswith(m.group(1)))


def space_sources(path):
    """{row id: slot cut} from `09-space.tsv`; an absent file names none."""
    if not path.exists():
        return {}
    out = {}
    for line in read_text(path, "space sources").split("\n"):
        fields = line.split("\t")
        if line.startswith("#") or len(fields) < 2 or not fields[1].strip():
            continue
        out[fields[0]] = fields[1]
    return out


def locked_thesis(path):
    """The `## Locked thesis` section of `path`, heading excluded, or None when there is none."""
    return section(path, THESIS_HEAD)


def section(path, head):
    """The section of `path` under the line reading exactly `head`, to the next `#` or `##`
    heading, heading excluded; None when `path` or that line is absent."""
    if not path.exists():
        return None
    lines, inside = [], False
    for line in read_text(path, "section %r of" % head).split("\n"):
        if line.rstrip() == head:
            inside = True
        elif inside and HEADING_RE.match(line):
            break
        elif inside:
            lines.append(line)
    return "\n".join(lines) if inside else None


def route_drops(row, thesis):
    """The `route` rule: a `routed@5` row quotes the locked thesis, verbatim."""
    if row["status"] != ROUTED:
        return []
    if thesis is None:
        raise Unusable("row %s is routed@5, and the %s beside the ledger has no line reading "
                       "exactly %r to grade its quote against" % (row["id"], THESIS, THESIS_HEAD))
    if row["quote"] not in thesis:
        return [("route", "routed@5, and quote %r is not verbatim in %s %r; route it to 9"
                 % (row["quote"], THESIS, THESIS_HEAD))]
    return []


def pointer(doc, ptr):
    """The node JSON pointer `ptr` names in `doc`, or None when it names none."""
    if not ptr.startswith("/"):
        return None
    node = doc
    for part in ptr[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        elif isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node


def field_text(node):
    """A field's text: a string itself, a span's `t`, a span array's `t` values joined as
    `web.py:422` joins them, and an object's string and array fields so read, joined with " " in
    key order (G85 (i)). None for anything else."""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(x["t"] for x in node if isinstance(x, dict) and isinstance(x.get("t"), str))
    if isinstance(node, dict):
        if isinstance(node.get("t"), str):
            return node["t"]
        return " ".join(t for t in (field_text(v) for v in node.values()
                                    if isinstance(v, (str, list))) if t)
    return None


def fix_old_drops(row, data):
    """G58 (ii): a page `fixed@` row's `fix_old` sits in the text its `location` names in
    `brief-08.json`, or, on a repair, in `brief-10.json`. `data` is [(name, parsed)], 08 first."""
    if not FIXED_RE.match(row["status"]):
        return []
    if not data:
        raise Unusable("row %s is fixed@, and no %s sits beside the ledger to read its fix_old at "
                       "its location" % (row["id"], DATA_08))
    for _, doc in data:
        text = field_text(pointer(doc, row["location"]))
        if text is not None and row["fix_old"] in text:
            return []
    return [("fix_old", "fixed@, and fix_old %r is not in the field location %r names in %s"
             % (row["fix_old"], row["location"], " or ".join(n for n, _ in data)))]


def recheck_drops(folder):
    """G75 (ii), G85 (iii), G86: each FAIL row of `09-recheck.md` beside the ledger is applied
    or rejected. A fix in the one quoted form is in the text (`09-text.md`, or on a repair
    `09-text-10.md`), or a § Rejected item naming its line gives a reason other than
    `re-check form`; a fix out of that form has an item naming its line that gives that reason.
    As (rule, message); an absent re-check names none."""
    path = folder / RECHECK
    if not path.exists():
        return []
    items = ITEM_RE.split(section(folder / FIXER, REJECTED_HEAD) or "")
    texts, out = None, []
    for n, line in enumerate(read_text(path, "re-check").split("\n"), start=1):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not line.lstrip().startswith("|") or len(cells) < 5 or cells[2] != "FAIL":
            continue
        where, fix = "%s:%d row %s (fixer)" % (path, n, cells[0]), "|".join(cells[4:]).strip()
        # G87: a row with no line cell is named by its own place, `09-recheck.md:N`.
        ref = cells[0] or "%s:%d" % (RECHECK, n)
        naming = [i for i in items if re.search(r"(?<!\w)" + re.escape(ref) + r"(?!\w)", i)]
        m = RECHECK_FIX_RE.match(fix)
        if m and not (m.group(1) or m.group(2)).strip():
            m = None  # quotes round whitespace alone: collapsed, it would sit in any text
        if not m:
            if not any(FORM_REASON_RE.search(i) for i in naming):
                out.append(("recheck", "%s FAIL fix %r is not one double-quoted string, and no "
                            "%s § Rejected item names line %r with the reason `re-check form`"
                            % (where, fix, FIXER, ref)))
            continue
        if texts is None:
            texts = [read_text(folder / name, "fixer text") for name in RECHECK_TEXT
                     if (folder / name).exists()]
            if not texts:
                raise Unusable("%s has FAIL rows, and neither %s sits beside it"
                               % (path, " nor ".join(RECHECK_TEXT)))
        # G87: `--authored` strips and collapses whitespace (`web.py:317`), so the fix is too.
        want = re.sub(r"\s+", " ", m.group(1) or m.group(2)).strip()
        if (not any(want in t for t in texts)
                and not any(not FORM_REASON_RE.search(i) for i in naming)):
            out.append(("recheck", "%s FAIL fix %s is in neither %s, and no %s § Rejected item "
                        "names line %r for a lint" % (where, fix, " nor ".join(RECHECK_TEXT),
                                                      FIXER, ref)))
    return out


def value_words(v, text):
    """The spans where `brief.json` value `v` stands as a whole word in `text`; none for a blank
    value. The word boundary is load-bearing: a plain substring would find the values "no" in "not"
    and "act" in "action", inside legitimate template lines."""
    if not v.strip():
        return []
    return [m.span() for m in re.finditer(r"(?<!\w)" + re.escape(v) + r"(?!\w)", text)]


def brief_value(quote, values):
    """The `brief.json` value `quote` sits inside, or holds as a whole word, else None (G51)."""
    for v in values:
        if quote in v or value_words(v, quote):
            return v
    return None


def overlapped_value(quote, lines, values):
    """A `brief.json` value that every occurrence of `quote` in a template line overlaps, where
    that line holds it as a whole word, else None (G55): a quote that takes the last word of a
    company name in the h1 is the brief's. One occurrence clear of every value is template text."""
    hit = None
    for line in lines:
        spans = [(s, e, v) for v in values for s, e in value_words(v, line)]
        i = line.find(quote)
        while i != -1:
            v = next((v for s, e, v in spans if s < i + len(quote) and i < e), None)
            if v is None:
                return None
            hit = hit or v
            i = line.find(quote, i + 1)
    return hit


def brief_strings(node):
    """Every string value in a parsed `brief.json`, keys excluded."""
    if isinstance(node, dict):
        return [s for v in node.values() for s in brief_strings(v)]
    if isinstance(node, list):
        return [s for v in node for s in brief_strings(v)]
    return [node] if isinstance(node, str) else []


def fixer_drops(row, sha, space, page=False, template=None):
    """The `status` and `space` rules, on a ten-field row; `space` is off on the page path."""
    if row["status"] == RULED:
        if not page:
            return [("status", "%s is the page path's; a markdown brief has no template string" % RULED)]
        if template is None:
            raise Unusable("row %s is %s, and no %s sits beside the ledger to grade it against"
                           % (row["id"], RULED, TEMPLATE_TEXT))
        text, values = template
        lines = [line for line in text.split("\n") if line.strip() and row["quote"] in line]
        if not lines:
            return [("status", "%s, but quote %r is inside no line of %s, the template's own text; "
                     "fix it at its field" % (RULED, row["quote"], TEMPLATE_TEXT))]
        value = brief_value(row["quote"], values)
        if value is not None:
            return [("status", "%s, but quote %r holds or sits inside brief.json value %r; fix it at "
                     "that field" % (RULED, row["quote"], value))]
        value = overlapped_value(row["quote"], lines, values)
        if value is not None:
            return [("status", "%s, but quote %r takes part of brief.json value %r in its template "
                     "line; fix it at that field" % (RULED, row["quote"], value))]
        return []
    m = FIXED_RE.match(row["status"])
    if m and not closed(row["status"], sha):
        return [("status", "status %r is not the first %d or more hex of the brief's sha256 %s"
                 % (row["status"], SHA_MIN, sha))]
    if (m and not page and len(row["fix_new"].split()) > len(row["fix_old"].split())
            and row["id"] not in space):
        return [("space", "closed fix grows %d words to %d and %s names no slot cut for %s" %
                 (len(row["fix_old"].split()), len(row["fix_new"].split()), SPACE, row["id"]))]
    return []


def row_drops(fields, text, known, signals=frozenset(), sha="", space=None, thesis=None, page=False,
              template=None, data=None):
    """Every rule this row breaks, as (rule, reason). Empty means the row is kept."""
    if len(fields) != len(COLUMNS):
        return [("columns", "carries %d fields, want %d: %s" %
                 (len(fields), len(COLUMNS), " ".join(COLUMNS)))]
    row = dict(zip(COLUMNS, fields))
    out = []
    held = len(QUOTE_WORD_RE.findall(row["quote"]))
    if not held:
        out.append(("quote", "quote %r carries no letter or digit; no quote, no deduction" %
                    row["quote"]))
    elif held < QUOTE_MIN and row["quote"] not in text.split("\n"):
        out.append(("quote", "quote %r holds %d letters or digits, under %d, and is not a whole "
                    "line: too short to locate the defect; quote more of its sentence or row" %
                    (row["quote"], held, QUOTE_MIN)))
    elif row["quote"] not in text:
        out.append(("quote", "quote is not verbatim in the brief: %r" % row["quote"]))
    if not row["rule_id"]:
        if row["severity"] != CANDIDATE_SEVERITY:
            out.append(("rule_id", "names no rule at severity %r; a candidate rule is logged at %s"
                        % (row["severity"], CANDIDATE_SEVERITY)))
    elif row["rule_id"] not in known:
        out.append(("rule_id", "rule_id %r is defined nowhere in quality-bar/" % row["rule_id"]))
    elif row["rule_id"] in signals and row["severity"] != CANDIDATE_SEVERITY:
        out.append(("rule_id", "rule_id %r is an advisory rhythm signal, booked at %s only, not %r"
                    % (row["rule_id"], CANDIDATE_SEVERITY, row["severity"])))
    if row["severity"] not in SEVERITIES:
        out.append(("severity", "severity %r is not one of %s" %
                    (row["severity"], " ".join(SEVERITIES))))
    old = claim_tokens(row["fix_old"]) if row["fix_old"] in text else set()
    new = claim_tokens(row["fix_new"]) - old
    if new and not carries_claim_id(row["claim_ids"]):
        out.append(("claim_ids", "fix_new adds %s and claim_ids carries no claim ID" %
                    ", ".join(sorted(new))))
    out += fixer_drops(row, sha, space or {}, page, template) + route_drops(row, thesis)
    return out + (fix_old_drops(row, data) if page else [])


def stage_data(folder):
    """[(name, parsed)] for `brief-08.json` beside the ledger, then `brief-10.json` when a repair
    wrote it; empty when there is no `brief-08.json`."""
    out = []
    for name in (DATA_08, DATA_10):
        if not (folder / DATA_08).exists() or not (folder / name).exists():
            continue
        try:
            out.append((name, json.loads((folder / name).read_bytes().decode("utf-8"))))
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            raise Unusable("cannot read %s as JSON (%s)" % (folder / name, exc))
    return out


Result = collections.namedtuple("Result",
                                "rows kept drops by_critic open routed candidates repairable")


def grade(brief, ledger, bar=BAR):
    """Grade every row of `ledger` against `brief` and `bar`. Raises Unusable for exit 2."""
    page = brief.suffix == PAGE_SUFFIX
    if page:
        try:
            sha = hashlib.sha256(brief.read_bytes()).hexdigest()
        except OSError as exc:
            raise Unusable("cannot read brief %s (%s)" % (brief, exc))
        text = read_text(ledger.parent / PAGE_TEXT, "stage 8 page text")
        try:
            values = brief_strings(json.loads(brief.read_bytes().decode("utf-8")))
        except (UnicodeDecodeError, ValueError) as exc:
            raise Unusable("brief %s is not JSON (%s)" % (brief, exc))
        template = ((read_text(ledger.parent / TEMPLATE_TEXT, "stage 8 template text"), values)
                    if (ledger.parent / TEMPLATE_TEXT).exists() else None)
    else:
        text, template = read_text(brief, "brief"), None
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    before = ledger.parent / BEFORE
    if before.exists() and not page:
        text = read_text(before, "stage 8 brief")
    space = space_sources(ledger.parent / SPACE)
    thesis = locked_thesis(ledger.parent / THESIS)
    known = rule_ids(bar)
    signals = lint_ids()[1]
    rows = []
    for n, line in enumerate(read_text(ledger, "ledger").split("\n"), start=1):
        if not line.strip():
            continue
        fields = line.split("\t")
        if tuple(fields) == COLUMNS:
            continue
        rows.append((n, fields))
    if not rows:
        raise Unusable("ledger %s holds no rows" % ledger)

    data = stage_data(ledger.parent) if page else None
    kept, drops, repairable = [], [], 0
    by_critic = collections.Counter()
    for n, fields in rows:
        found = row_drops(fields, text, known, signals, sha, space, thesis, page, template, data)
        if not found:
            kept.append(dict(zip(COLUMNS, fields)))
            continue
        if {rule for rule, _ in found} <= REPAIRABLE:
            repairable += 1
        critic = fields[1] if len(fields) > 1 and fields[1] else "<no critic>"
        # Once per owner per row: the critic, and each of `OWNERS` whose rule the row broke.
        for owner in {OWNERS.get(rule, critic) for rule, _ in found}:
            by_critic[owner] += 1
        where = "%s:%d row %s (%s)" % (ledger, n, fields[0] or "<no id>", critic)
        drops.extend((rule, "%s %s" % (where, why)) for rule, why in found)
    # A re-check row is no ledger row: it adds a drop against `fixer`, never to the row count.
    rechecked = recheck_drops(ledger.parent) if page else []
    drops.extend(rechecked)
    if rechecked:
        by_critic[OWNERS["recheck"]] += len(rechecked)
    routed = sum(1 for r in kept if r["status"] == ROUTED)
    open_rows = sum(1 for r in kept if not closed(r["status"], sha) and r["status"] != RULED) - routed
    candidates = sum(1 for r in kept if not r["rule_id"])
    return Result(len(rows), kept, drops, by_critic, open_rows, routed, candidates, repairable)


def summary(res):
    critics = ", ".join("%s %d" % kv for kv in sorted(res.by_critic.items())) or "none"
    return ("%d of %d rows dropped; drops by critic: %s; %d kept, %d open, %d routed to stage 5, "
            "%d candidate rule(s), %d repairable" % (
                res.rows - len(res.kept), res.rows, critics, len(res.kept), res.open, res.routed,
                res.candidates, res.repairable))


def report(res, what):
    if res.drops:
        for rule, msg in res.drops:
            sys.stderr.write("DROP %s %s\n" % (rule, msg))
        sys.stderr.write("CRITIQUE-CHECK RED (%s) in %s\n" % (summary(res), what))
        return 1
    sys.stdout.write("CRITIQUE-CHECK-OK (%s) in %s\n" % (summary(res), what))
    return 0


# --- selftest ------------------------------------------------------------------------------------
# The committed pair under `tools/fixtures/critique-check/` is the green base, graded against the
# live `quality-bar/`. Every red case is that pair with ONE field spoiled, so a red case proves the
# field and not the scaffolding. The four definition shapes are proved on a temporary bar written
# from literals, so a rule retired from `quality-bar/` cannot turn a shape case green or red.
# Every rule in RULES must be hit by a literal case: a loop over RULES could not see a rule deleted
# from it, because the deletion would take its own case with it.

FIXTURE = HERE / "fixtures" / "critique-check"
TEMP_BAR = {
    PILLARS: "# Card\n\n## P1. A pillar\n\nProse naming P9 in passing.\n\n## Word discipline\n",
    TABLES[0]: "| ID | Refusal | Why |\n|---|---|---|\n| RF1 | Never do x. | P9 |\n",
    TABLES[1]: "| ID | Line |\n|---|---|\n| H1 | A line. |\n",
    REGEXES: "# a comment line\nid\tpattern\nsome_regex\t\\bx\\b\n",
}


def selftest():
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="critique-check-selftest."))
    try:
        return _selftest(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _fail(msg):
    sys.stderr.write("SELFTEST FAIL: %s\n" % msg)
    raise SystemExit(1)


def _dropped(res, row_id):
    return {rule for rule, msg in res.drops if " row %s (" % row_id in msg}


def _selftest(tmp):
    brief, led = FIXTURE / "briefing.md", tmp / "ledger.tsv"
    base = [line.split("\t") for line in
            read_text(FIXTURE / "findings-ledger.tsv", "fixture").rstrip("\n").split("\n")]
    hit, cases = set(), [0]
    shutil.copy(FIXTURE / SPACE, tmp / SPACE)
    shutil.copy(FIXTURE / THESIS, tmp / THESIS)

    def run(rows, bar=BAR):
        led.write_text("".join("\t".join(r) + "\n" for r in rows), encoding="utf-8")
        return grade(brief, led, bar)

    def spoil(**by_row):
        rows = [list(r) for r in base]
        for r in rows:
            for field, value in by_row.get(r[0].replace("-", "_"), {}).items():
                if field == "drop_last":
                    r.pop()
                elif field == "append":
                    r.append(value)
                else:
                    r[COLUMNS.index(field)] = value
        return rows

    # A crash is a red case too, and it names the case rather than leaving a traceback to read.
    def graded(label, rows, bar=BAR):
        try:
            return run(rows, bar)
        except Exception as exc:  # noqa: BLE001 -- any exception, reported under the case's name
            _fail("%s: grading raised %r" % (label, exc))

    def red(label, rows, row_id, rule, bar=BAR):
        res = graded(label, rows, bar)
        if rule not in _dropped(res, row_id):
            _fail("%s: row %s was not dropped under %s; drops: %s" %
                  (label, row_id, rule, res.drops))
        hit.add(rule)
        cases[0] += 1
        sys.stdout.write("SELFTEST red OK   %-44s -> %s\n" % (label, rule))

    def kept(label, rows, row_id, bar=BAR):
        res = graded(label, rows, bar)
        if _dropped(res, row_id):
            _fail("%s: row %s was dropped: %s" % (label, row_id, res.drops))
        cases[0] += 1
        sys.stdout.write("SELFTEST green OK %-44s\n" % label)

    # The base. F-02 keeps "3 of 5" and adds an ISO date, so it adds no claim; F-05 is a candidate
    # rule at MINOR; F-03 is the one closed row. A blank line and the header are skipped.
    try:
        res = grade(brief, FIXTURE / "findings-ledger.tsv")
    except Exception as exc:  # noqa: BLE001
        _fail("committed fixture: grading raised %r" % (exc,))
    if res.drops or res.rows != 5 or res.open != 4 or res.candidates != 1:
        _fail("the committed fixture is not green, 5 rows, 4 open, 1 candidate: %s" % (res,))
    cases[0] += 1
    sys.stdout.write("SELFTEST green OK %-44s -> %s\n" % ("committed fixture", summary(res)))
    kept("fix keeps its claim, adds a date", base, "F-02")
    kept("candidate rule at MINOR", base, "F-05")

    red("row short of a field", spoil(F_01={"drop_last": 1}), "F-01", "columns")
    red("quote not verbatim", spoil(F_01={"quote": "This analysis finds a rival"}), "F-01",
        "quote")
    red("quote empty", spoil(F_01={"quote": ""}), "F-01", "quote")
    red("rule_id defined nowhere", spoil(F_01={"rule_id": "RF999"}), "F-01", "rule_id")
    red("candidate rule above MINOR", spoil(F_05={"severity": "MATERIAL"}), "F-05", "rule_id")
    red("fix adds a numeral, no claim ID",
        spoil(F_04={"fix_new": "Every listed reseller sells in 2 regions."}), "F-04",
        "claim_ids")
    red("fix adds a quantifier, no claim ID",
        spoil(F_01={"fix_new": "Only the rival prices per site."}), "F-01", "claim_ids")
    red("claim_ids carries no claim ID", spoil(F_03={"claim_ids": "TBD"}), "F-03", "claim_ids")

    # A quote must carry a letter or digit. Every placeholder here is verbatim in the fixture
    # brief's table, so the substring test cannot drop it and only the content rule can. `_` is
    # the one `\w` would pass. `|---|---|` is a whole line, so the whole-line rule below cannot
    # keep it. A near-verbatim quote is not verbatim: case, spacing.
    fixture_text = read_text(brief, "fixture")
    for n, q in enumerate((" ", "-", "--", "|", ".", "_", "|---|", "|---|---|")):
        if q not in fixture_text:
            _fail("placeholder %r is not in the fixture brief; its case would prove nothing" % q)
        row_id = ("F-02", "F-03", "F-04", "F-05")[n % 4]
        red("placeholder quote %r" % q, spoil(**{row_id.replace("-", "_"): {"quote": q}}),
            row_id, "quote")
    # A quote must locate: QUOTE_MIN letters or digits, or a whole line. `None` (4) and `Unknown`
    # (7) are the fixture's absence cells, the second also with its pipes (11 characters) and
    # `ice_list` holds 7 letters in 8 `\w`. `The rival` holds exactly 8, `## Rivals` is a heading
    # line of 6, and `None published` is a real quote holding `None`.
    for q, want in (("None", 4), ("Unknown", 7), ("| Unknown |", 7), ("ice_list", 7),
                    ("The rival", 8), ("## Rivals", 6), ("None published", 13)):
        if q not in fixture_text or len(re.findall(r"[^\W_]", q)) != want:  # not QUOTE_WORD_RE
            _fail("%r is not in the fixture brief at %d letters; its case would prove nothing"
                  % (q, want))
    red("absence cell quoted: None", spoil(F_02={"quote": "None"}), "F-02", "quote")
    red("absence cell quoted: Unknown", spoil(F_05={"quote": "Unknown"}), "F-05", "quote")
    red("absence cell with its pipes", spoil(F_03={"quote": "| Unknown |"}), "F-03", "quote")
    red("underscore is not a letter: ice_list", spoil(F_04={"quote": "ice_list"}), "F-04",
        "quote")
    kept("quote of exactly 8 letters", spoil(F_01={"quote": "The rival"}), "F-01")
    kept("short heading, quoted as its whole line", spoil(F_04={"quote": "## Rivals"}), "F-04")
    kept("quote holding None", spoil(F_03={"quote": "None published"}), "F-03")
    red("quote differs in case", spoil(F_04={"quote": "every reseller on that list"}), "F-04",
        "quote")
    red("quote differs in spacing", spoil(F_02={"quote": "3 of 5  listed"}), "F-02", "quote")
    red("row long by a field", spoil(F_02={"append": "extra"}), "F-02", "columns")
    red("rule_id differs in case", spoil(F_04={"rule_id": "p4"}), "F-04", "rule_id")
    red("severity outside the three", spoil(F_02={"severity": "HIGH"}), "F-02", "severity")
    red("severity in lower case", spoil(F_03={"severity": "blocker"}), "F-03", "severity")
    red("claim_ids carries C-TBD", spoil(F_03={"claim_ids": "C-TBD"}), "F-03", "claim_ids")
    red("claim_ids carries C-14", spoil(F_03={"claim_ids": "C-14"}), "F-03", "claim_ids")
    # `fix_old` is the claim baseline only where the brief carries it. Here fix_old is fix_new,
    # a sentence the brief lacks and the quote is not, and it adds a number nobody sourced.
    same = "Every listed reseller sells in 12 regions."
    red("fix_old not in the brief excuses nothing",
        spoil(F_04={"fix_old": same, "fix_new": same}), "F-04", "claim_ids")
    # And the baseline is fix_old, not the quote: this quote carries no number, fix_old's does.
    kept("fix_old, not the quote, holds the claim",
         spoil(F_02={"quote": "listed resellers as partners"}), "F-02")

    # The four shapes, on the temporary bar. P9 is only mentioned, `ID` and `id` are headers, and
    # `Word` heads a section that is not a pillar: none of them is defined.
    bar = tmp / "bar"
    bar.mkdir()
    for name, body in TEMP_BAR.items():
        (bar / name).write_text(body, encoding="utf-8")
    for rid in ("P1", "RF1", "H1", "some_regex"):
        kept("defined rule %s" % rid, spoil(F_01={"rule_id": rid}), "F-01", bar)
    for rid in ("P9", "ID", "id", "Word"):
        red("undefined rule %s" % rid, spoil(F_01={"rule_id": rid}), "F-01", "rule_id", bar)

    # The fifth source, `voice-lint.sh`'s code checks, read off the live lint. `dup_row_date` is a
    # BLOCKING hit the rubric blocks on; dropping a critic's row for citing it was P16-verify R1.
    kept("voice-lint code id dup_row_date", spoil(F_01={"rule_id": "dup_row_date"}), "F-01")
    kept("dup_row_date at BLOCKER", spoil(F_01={"rule_id": "dup_row_date", "severity": "BLOCKER"}),
         "F-01")
    # A rhythm signal is advisory: kept at MINOR, dropped above it.
    kept("voice-lint signal R2 at MINOR", spoil(F_01={"rule_id": "R2", "severity": "MINOR"}), "F-01")
    red("signal R2 at BLOCKER", spoil(F_01={"rule_id": "R2", "severity": "BLOCKER"}), "F-01",
        "rule_id")
    red("signal R2 at MATERIAL", spoil(F_01={"rule_id": "R2"}), "F-01", "rule_id")
    # An id is read off its print line only: a comment naming one defines nothing. A lint with no
    # print line is refused, never read as defining nothing.
    lint = tmp / "voice-lint.sh"
    lint.write_text('# names dup_mention\nprint("FAIL\\tsome_code\\tx\\t%d" % n)\n'
                    'print("SIGNAL\\tR9\\tx\\t0\\t")\n', encoding="utf-8")
    got = rule_ids(BAR, lint)
    if (not {"some_code", "R9"} <= got or "dup_mention" in got or "dup_row_date" in got
            or lint_ids(lint)[1] != {"R9"}):
        _fail("lint ids from a temporary lint: want some_code and R9 in, dup_mention and "
              "dup_row_date out; got %s" % {k: k in got for k in
                                            ("some_code", "R9", "dup_mention", "dup_row_date")})
    cases[0] += 1
    sys.stdout.write("SELFTEST green OK %-44s\n" % "lint ids read off print lines only")
    lint.write_text("# no print line\n", encoding="utf-8")
    try:
        rule_ids(BAR, lint)
    except Unusable:
        cases[0] += 1
        sys.stdout.write("SELFTEST green OK %-44s -> unusable\n" % "lint with no print line")
    else:
        _fail("a voice-lint with no print line was read as defining no code id")

    kept("claim_ids lists two IDs", spoil(F_03={"claim_ids": "C-014 C-015"}), "F-03")

    # Drops count against the critic, once per row however many rules it breaks. A row too short
    # to name its critic, or naming none, is counted rather than lost.
    res = graded("drops counted per critic",
                 spoil(F_01={"quote": "x"}, F_02={"quote": "x"},
                       F_03={"quote": "x", "rule_id": "x"}, F_04={"critic": "", "quote": "x"})
                 + [["one field"]])
    want = {"truth": 2, "voice": 1, "<no critic>": 2}
    if dict(res.by_critic) != want or _dropped(res, "F-03") != {"quote", "rule_id"}:
        _fail("drops by critic: want %s and both F-03 rules; got %s, %s" %
              (want, dict(res.by_critic), res.drops))
    cases[0] += 1
    sys.stdout.write("SELFTEST green OK %-44s -> %s\n" % ("drops counted per critic",
                                                           summary(res)))

    # G74: a placed row whose only drop is its label is repairable; an unplaced one is not. The
    # last three guard the set's other edges: `claim_ids` is in it, `severity` and the fixer-owned
    # `status` are not (W18-fix3-verify-2.md Nice 1).
    for label, row_id, spoilt, want in (
            ("a bad status is not repairable", "F_01",
             {"rule_id": "RF999", "status": "fixed@" + "0" * 12}, 0),
            ("undefined rule_id is repairable", "F_01", {"rule_id": "RF999"}, 1),
            ("unlocatable quote is not repairable", "F_01",
             {"rule_id": "RF999", "quote": "x" * 9}, 0),
            ("claim_ids alone is repairable", "F_04",
             {"fix_new": "Every listed reseller sells in 2 regions."}, 1),
            ("a bad severity is not repairable", "F_01", {"rule_id": "RF999", "severity": "HIGH"},
             0)):
        res = graded(label, spoil(**{row_id: spoilt}))
        if res.repairable != want or "%d repairable" % want not in summary(res):
            _fail("%s: want %d repairable; got %s" % (label, want, summary(res)))
        cases[0] += 1
        sys.stdout.write("SELFTEST green OK %-44s -> %d repairable\n" % (label, want))

    # A row is closed only by `fixed@<sha>`.
    for status in ("fixed@", "fixed@XYZ1234", "done"):
        if graded("status %r" % status, spoil(F_03={"status": status})).open != 5:
            _fail("status %r counted as closed" % status)
        cases[0] += 1
    sys.stdout.write("SELFTEST green OK %-44s\n" % "only fixed@<sha> closes a row")

    # `route`: a routed row quotes the fixture's `## Locked thesis` section, as F-02 does. F-01's
    # quote sits in the section before it and F-04's in the one after, so each is red.
    red("routed row quotes a candidate", spoil(F_01={"status": ROUTED}), "F-01", "route")
    red("routed row quotes past the section", spoil(F_04={"status": ROUTED}), "F-04", "route")
    # A routed row with no section to grade it is exit 2, never a drop: no thesis file, and a
    # heading that is not exactly `## Locked thesis` (one of three real thesis files wrote this).
    thesis_text = read_text(FIXTURE / THESIS, "fixture")
    for label, body in (("routed row, no 05-thesis.md", None),
                        ("routed row, heading not exact", thesis_text.replace(
                            THESIS_HEAD + "\n", THESIS_HEAD + " (step 7)\n"))):
        (tmp / THESIS).unlink()
        if body is not None:
            (tmp / THESIS).write_text(body, encoding="utf-8")
        try:
            run(spoil(F_02={"status": ROUTED}))
        except Unusable:
            cases[0] += 1
            sys.stdout.write("SELFTEST green OK %-44s -> unusable\n" % label)
        else:
            _fail("%s was graded instead of refused" % label)
        finally:
            shutil.copy(FIXTURE / THESIS, tmp / THESIS)
    # `routed@5`, exactly, on a thesis quote, takes a row off the open count onto the routed one.
    res = graded("status routed@5", spoil(F_02={"status": ROUTED}))
    if _dropped(res, "F-02"):
        _fail("routed@5 on a quote of the locked thesis was dropped: %s" % res.drops)
    if res.open != 3 or res.routed != 1:
        _fail("status routed@5: want 3 open and 1 routed; got %s" % summary(res))
    cases[0] += 1
    for status in ("routed@6", "routed@", "Routed@5", "routed@5 "):
        res = graded("status %r" % status, spoil(F_02={"status": status}))
        if res.open != 4 or res.routed != 0:
            _fail("status %r was read as routed: %s" % (status, summary(res)))
        cases[0] += 1
    sys.stdout.write("SELFTEST green OK %-44s\n" % "only routed@5 routes a row")

    # `status`: a `fixed@` hash closes a row only as the start of the named brief's sha256, 12 hex
    # or more. F-03's committed hash is the fixture brief's first 12.
    sha = hashlib.sha256(fixture_text.encode("utf-8")).hexdigest()
    red("fixed@ with 7 hex, the old floor", spoil(F_03={"status": "fixed@" + sha[:7]}), "F-03",
        "status")
    red("fixed@ 12 hex, not the brief's", spoil(F_03={"status": "fixed@" + "0" * 12}), "F-03",
        "status")
    if graded("full sha", spoil(F_03={"status": "fixed@" + sha})).open != 4:
        _fail("fixed@ with the brief's full sha256 did not close F-03")
    cases[0] += 1
    sys.stdout.write("SELFTEST green OK %-44s\n" % "fixed@ with the full sha256 closes")
    # `space`: a closed fix that grows names its slot cut in 09-space.tsv; F-03 does. F-04 has no
    # line there; a fix that shrinks needs none.
    red("growing closed fix, no slot cut",
        spoil(F_04={"status": "fixed@" + sha[:12],
                    "fix_new": "Every listed reseller sells in one region of the country."}),
        "F-04", "space")
    kept("shrinking closed fix, no slot cut", spoil(F_01={"status": "fixed@" + sha[:12]}), "F-01")
    # Which bytes: with `briefing-08.md` beside the ledger, quotes read it and the hash reads the
    # named brief. F-01's sentence is rewritten in the post-fix brief, so F-01 is kept only by
    # stage 8's bytes, and F-03's hash, stage 8's, no longer closes anything.
    post = tmp / "post.md"
    post.write_text(fixture_text.replace(base[1][6], base[1][7]), encoding="utf-8")
    shutil.copy(brief, tmp / BEFORE)
    led.write_text("".join("\t".join(r) + "\n" for r in base), encoding="utf-8")
    res = grade(post, led)
    (tmp / BEFORE).unlink()
    if _dropped(res, "F-01") or _dropped(res, "F-03") != {"status"}:
        _fail("post-fix brief with briefing-08.md: want F-01 kept, F-03 on status; got %s"
              % res.drops)
    cases[0] += 1
    sys.stdout.write("SELFTEST green OK %-44s\n" % "quotes read briefing-08.md, hash the brief")

    # Exit 2 is "could not do its job", never a pass: a ledger holding only its header, and a bar
    # missing one defining file.
    for label, rows, use_bar in (("ledger with no rows", base[:1], BAR),
                                 ("bar file missing", base, tmp / "no-bar")):
        try:
            run(rows, use_bar)
        except Unusable:
            cases[0] += 1
            sys.stdout.write("SELFTEST green OK %-44s -> unusable\n" % label)
        else:
            _fail("%s was graded instead of refused" % label)
    (tmp / "binary.md").write_bytes(b"\xff\xfe\x00")
    try:
        grade(tmp / "binary.md", FIXTURE / "findings-ledger.tsv")
    except Unusable:
        cases[0] += 1
        sys.stdout.write("SELFTEST green OK %-44s -> unusable\n" % "brief not UTF-8")
    except Exception as exc:  # noqa: BLE001
        _fail("brief not UTF-8: grading raised %r" % (exc,))
    else:
        _fail("a brief that is not UTF-8 was graded instead of refused")

    # The page path (W16): a `.json` brief. Quotes read 08-text.md beside the ledger; `fixed@` closes
    # only on brief.json's own sha256. The page text here is the fixture brief's bytes, and a stale
    # briefing.md sits beside it, so the committed F-03, fixed@ the first 12 hex of briefing.md's
    # sha256, is the hash of both, and on this path closes nothing.
    web = tmp / "web"
    web.mkdir()
    shutil.copy(brief, web / PAGE_TEXT)
    shutil.copy(brief, web / "briefing.md")
    page_json, web_led = web / "brief.json", web / "findings-ledger.tsv"
    shutil.copy(ROOT / "tools" / "fixtures" / "web" / "synthetic.json", page_json)
    page_sha = hashlib.sha256(page_json.read_bytes()).hexdigest()
    # G58 (ii): stage 8's data held F-03's and F-04's old text where brief.json holds the new, and
    # each row's location names that field. A case that sets no pointer gets these.
    data08 = json.loads(page_json.read_text(encoding="utf-8"))
    data08["recommendations"][0]["why"][1]["t"] = " " + base[3][6] + "."
    data08["quick_take"][0]["body"][0]["t"] = " " + base[4][6]
    (web / DATA_08).write_text(json.dumps(data08, ensure_ascii=False), encoding="utf-8")
    at = {"F-03": "/recommendations/0/why/1", "F-04": "/quick_take/0/body"}

    def paged(label, rows, place=True):
        rows = [r[:5] + [at[r[0]]] + r[6:] if place and r[0] in at and len(r) == len(COLUMNS)
                and not r[5].startswith("/") else r for r in rows]
        web_led.write_text("".join("\t".join(r) + "\n" for r in rows), encoding="utf-8")
        try:
            return grade(page_json, web_led)
        except Exception as exc:  # noqa: BLE001
            _fail("%s: grading raised %r" % (label, exc))

    def page_case(label, ok, res):
        if not ok:
            _fail("%s: %s; drops %s" % (label, summary(res), res.drops))
        cases[0] += 1
        sys.stdout.write("SELFTEST page OK  %-44s -> %s\n" % (label, summary(res)))

    res = paged("page: fixed@ a briefing.md hash", base)
    page_case("page: fixed@ a briefing.md hash closes nothing", _dropped(res, "F-03") == {"status"}, res)
    res = paged("page: fixed@ brief.json", spoil(F_03={"status": "fixed@" + page_sha[:12]}))
    page_case("page: fixed@ brief.json's sha closes", not res.drops and res.open == 4, res)
    res = paged("page: growing fix", spoil(F_04={"status": "fixed@" + page_sha, "fix_new":
                                                 "Every listed reseller sells in one region of the country."}))
    page_case("page: a growing closed fix needs no 09-space.tsv", not _dropped(res, "F-04"), res)
    only_json = "Mistral Réseaux already runs French homes at scale."
    if only_json not in page_json.read_text(encoding="utf-8") or only_json in fixture_text:
        _fail("%r must be in brief.json and not in the page text" % only_json)
    # A stray PDF-era briefing-08.md beside the run holds the quote; the page path never reads it.
    (web / BEFORE).write_text(page_json.read_text(encoding="utf-8"), encoding="utf-8")
    res = paged("page: quote in brief.json only", spoil(F_01={"quote": only_json}))
    (web / BEFORE).unlink()
    page_case("page: a quote is graded on 08-text.md alone", "quote" in _dropped(res, "F-01"), res)
    # G45, G49: `ruled@template` closes a row only when its quote is inside a line of 08-template.md.
    # Here F-02's quote is the one template line; F-01's quote is authored text.
    (web / TEMPLATE_TEXT).write_text("Skip to content\n\n" + base[2][4] + "\n", encoding="utf-8")
    res = paged("page: ruled@template, a template quote", spoil(F_02={"status": RULED}))
    page_case("page: ruled@template on a template quote closes", not _dropped(res, "F-02") and res.open == 3, res)
    res = paged("page: ruled@template, an authored quote", spoil(F_01={"status": RULED}))
    page_case("page: ruled@template on an authored quote is a status drop", _dropped(res, "F-01") == {"status"}, res)
    # G47: a whole table row is no template line.
    row_line = "| Another reseller | Unknown |"
    if row_line not in fixture_text.split("\n"):
        _fail("%r is not a whole line of the fixture brief; the row case would prove nothing" % row_line)
    res = paged("page: ruled@template, a whole row", spoil(F_04={"quote": row_line, "status": RULED}))
    page_case("page: ruled@template on a whole authored row is a status drop", _dropped(res, "F-04") == {"status"}, res)
    # G51: a template line that interpolates a brief.json value is template only outside it: the
    # matrix header row holds the companies' names, so a name alone so marked is a status drop and
    # the whole row is kept.
    header = "Test , Coopélec , Brightwater Grid , Øresund Flex"
    (web / TEMPLATE_TEXT).write_text("Skip to content\n\n" + base[2][4] + "\n\n" + header + "\n", encoding="utf-8")
    (web / PAGE_TEXT).write_text(fixture_text + "\n" + header + "\n", encoding="utf-8")
    if "Brightwater Grid" not in brief_strings(json.loads(page_json.read_text(encoding="utf-8"))):
        _fail("the name case needs 'Brightwater Grid' as a brief.json value")
    res = paged("page: ruled@template, a company name", spoil(F_04={"quote": "Brightwater Grid", "status": RULED}))
    page_case("page: ruled@template on a brief.json name is a status drop", _dropped(res, "F-04") == {"status"}, res)
    if "Brightwater" in brief_strings(json.loads(page_json.read_text(encoding="utf-8"))):
        _fail("the part-of-a-name case needs 'Brightwater' to be no brief.json value of its own")
    res = paged("page: ruled@template, part of a name", spoil(F_04={"quote": "Brightwater", "status": RULED}))
    page_case("page: ruled@template on part of a brief.json name is a status drop", _dropped(res, "F-04") == {"status"}, res)
    res = paged("page: ruled@template, the header row", spoil(F_04={"quote": header, "status": RULED}))
    page_case("page: ruled@template on the whole header row is a status drop", _dropped(res, "F-04") == {"status"}, res)
    # W16-verify-4 Recommended 2: containment runs one way, the quote inside a template line.
    part = base[2][4][: len(base[2][4]) // 2 + 4].rstrip()
    res = paged("page: ruled@template, part of a template line", spoil(F_04={"quote": part, "status": RULED}))
    page_case("page: ruled@template on part of a template line closes", not _dropped(res, "F-04"), res)
    # The word boundary: the moves header holds "act" (a brief.json action) only inside "action".
    moves = "Company , Change or silence , What it means and action"
    (web / TEMPLATE_TEXT).write_text("Skip to content\n\n" + base[2][4] + "\n\n" + header + "\n\n" + moves + "\n",
                                     encoding="utf-8")
    (web / PAGE_TEXT).write_text(fixture_text + "\n" + moves + "\n", encoding="utf-8")
    if "act" not in brief_strings(json.loads(page_json.read_text(encoding="utf-8"))):
        _fail("the word-boundary case needs the brief.json value 'act'")
    res = paged("page: ruled@template, the moves header", spoil(F_04={"quote": moves, "status": RULED}))
    page_case("page: ruled@template on the moves header closes (act is not a word in it)", not _dropped(res, "F-04"), res)
    # W16-verify-5 Nice 2: a blank brief.json string is no value; " , " would otherwise hold it.
    blank = json.loads(page_json.read_text(encoding="utf-8"))
    blank["blank"] = ""
    page_json.write_text(json.dumps(blank, ensure_ascii=False), encoding="utf-8")
    res = paged("page: ruled@template, a blank value", spoil(F_04={"quote": moves, "status": RULED}))
    shutil.copy(ROOT / "tools" / "fixtures" / "web" / "synthetic.json", page_json)
    page_case("page: ruled@template beside a blank brief.json value closes", not _dropped(res, "F-04"), res)
    # The left boundary: "contact" ends in the value "act", which is no word of the line.
    tmpl = "Skip to content\n\n" + base[2][4] + "\n\n" + header + "\n\n" + moves + "\n"
    contact = "Write to the contact desk"
    (web / TEMPLATE_TEXT).write_text(tmpl + "\n" + contact + "\n", encoding="utf-8")
    (web / PAGE_TEXT).write_text(fixture_text + "\n" + contact + "\n", encoding="utf-8")
    res = paged("page: ruled@template, a word ending in a value", spoil(F_04={"quote": contact, "status": RULED}))
    page_case("page: ruled@template on a word ending in a value closes", not _dropped(res, "F-04"), res)
    # G55: a quote taking part of two names in the header row drops; one occurrence clear of every
    # value is template text, so it closes. None of these words is a brief.json value of its own.
    span, clear = "Grid , Øresund", "Power Grid , Øresund straits"
    if {"Grid", "Øresund", "Power", "straits", span} & set(brief_strings(blank)):
        _fail("the overlap cases need no brief.json value among their words")
    (web / PAGE_TEXT).write_text(fixture_text + "\n" + header + "\n" + clear + "\n", encoding="utf-8")
    res = paged("page: ruled@template, part of two names", spoil(F_04={"quote": span, "status": RULED}))
    page_case("page: ruled@template on a quote overlapping names is a status drop", _dropped(res, "F-04") == {"status"}, res)
    (web / TEMPLATE_TEXT).write_text(tmpl + "\n" + clear + "\n", encoding="utf-8")
    res = paged("page: ruled@template, once clear of names", spoil(F_04={"quote": span, "status": RULED}))
    page_case("page: ruled@template on a quote clear of names once closes", not _dropped(res, "F-04"), res)
    # Touching is not overlapping: a quote that starts at the character after a name's end closes.
    touch, after = "Brightwater Grid-side notes for buyers", "-side notes for buyers"
    if {"side", "notes", "for", "buyers"} & set(brief_strings(blank)):
        _fail("the touching case needs no brief.json value among its words")
    (web / TEMPLATE_TEXT).write_text(tmpl + "\n" + touch + "\n", encoding="utf-8")
    (web / PAGE_TEXT).write_text(fixture_text + "\n" + touch + "\n", encoding="utf-8")
    res = paged("page: ruled@template, touching a name", spoil(F_04={"quote": after, "status": RULED}))
    page_case("page: ruled@template on a quote touching a name closes", not _dropped(res, "F-04"), res)
    (web / TEMPLATE_TEXT).write_text(tmpl, encoding="utf-8")
    wider = "Skip to content and more"
    (web / PAGE_TEXT).write_text(fixture_text + "\n" + header + "\n" + wider + "\n", encoding="utf-8")
    res = paged("page: ruled@template, a line holding a template line", spoil(F_04={"quote": wider, "status": RULED}))
    page_case("page: ruled@template on a line holding a template line is a status drop",
              _dropped(res, "F-04") == {"status"}, res)
    (web / PAGE_TEXT).write_text(fixture_text, encoding="utf-8")
    # G49: an evidence panel's line is on the page and in no authored line, yet no template prints it.
    panel = "Paraphrased: the rival lists its resellers on one page."
    (web / PAGE_TEXT).write_text(fixture_text + "\n" + panel + "\n", encoding="utf-8")
    res = paged("page: ruled@template, an evidence panel", spoil(F_05={"quote": panel, "status": RULED}))
    (web / PAGE_TEXT).write_text(fixture_text, encoding="utf-8")
    page_case("page: ruled@template on an evidence panel is a status drop", _dropped(res, "F-05") == {"status"}, res)
    res = graded("pdf: ruled@template", spoil(F_02={"status": RULED}))
    page_case("pdf: ruled@template off the page path is a status drop", _dropped(res, "F-02") == {"status"}, res)
    (web / TEMPLATE_TEXT).unlink()
    web_led.write_text("".join("\t".join(r) + "\n" for r in spoil(F_02={"status": RULED})), encoding="utf-8")
    try:
        grade(page_json, web_led)
        _fail("page: a ruled@template row with no 08-template.md was graded")
    except Unusable:
        cases[0] += 1
        sys.stdout.write("SELFTEST page OK  %-44s -> unusable\n" % "page: ruled@template, no 08-template.md")

    def page_red(label, rows, row_id, rule, place=True):
        res = paged(label, rows, place)
        page_case(label, rule in _dropped(res, row_id) and res.by_critic["fixer"] >= 1, res)
        hit.add(rule)

    # G58 (ii): F-03's fix_old sits at why/1 in brief-08.json; at why/0, it is found only elsewhere.
    closes = "fixed@" + page_sha[:12]
    page_red("page: fix_old found only elsewhere",
             spoil(F_03={"status": closes, "location": "/recommendations/0/why/0"}), "F-03", "fix_old")
    res = paged("page: fix_old at its location", spoil(F_03={"status": closes}))
    page_case("page: fix_old at its location is kept", not res.drops, res)
    page_red("page: fix_old with no pointer", spoil(F_03={"status": closes}), "F-03", "fix_old", False)
    past = "/recommendations/%d" % len(data08["recommendations"])  # one past the array's end
    page_red("page: fix_old at a pointer past the end", spoil(F_03={"status": closes, "location": past}),
             "F-03", "fix_old")
    # A span array's `t` values are joined with "", an object's fields with " " (G85 (i)).
    rec = data08["recommendations"][0]
    for label, loc, old in (
            ("page: fix_old across spans, array joined", "/recommendations/0/why",
             rec["why"][0]["t"][-10:] + rec["why"][1]["t"][:19]),
            ("page: fix_old across fields, object joined", "/recommendations/0",
             rec["test"][0]["t"][-13:] + " " + rec["why"][0]["t"][:13])):
        res = paged(label, spoil(F_03={"status": closes, "location": loc, "fix_old": old}))
        page_case(label, not res.drops, res)
    # On a repair, brief-10.json's text at the location counts too; brief-08.json is required.
    data10 = json.loads(json.dumps(data08))
    data10["recommendations"][0]["why"][1]["t"] = " a live integration in 5 working days."
    (web / DATA_10).write_text(json.dumps(data10, ensure_ascii=False), encoding="utf-8")
    repaired = spoil(F_03={"status": closes, "fix_old": "a live integration in 5 working days"})
    res = paged("page: fix_old in brief-10.json", repaired)
    page_case("page: fix_old in brief-10.json on a repair is kept", not res.drops, res)
    (web / DATA_10).unlink()
    page_red("page: fix_old in brief-10.json, none written", repaired, "F-03", "fix_old")
    (web / DATA_08).rename(web / "moved.json")
    web_led.write_text("".join("\t".join(r) + "\n" for r in spoil(F_03={"status": closes})),
                       encoding="utf-8")
    try:
        grade(page_json, web_led)
        _fail("page: a fixed@ row with no brief-08.json was graded")
    except Unusable:
        cases[0] += 1
        sys.stdout.write("SELFTEST page OK  %-44s -> unusable\n" % "page: fixed@, no brief-08.json")
    (web / "moved.json").rename(web / DATA_08)

    # G75 (ii), G85 (iii)-(iv): re-check line `7 s1` FAILs; its fix is one double-quoted string in
    # stage 9's text, or its line is under § Rejected. The PASS row's column is never read.
    green, present, absent = spoil(F_03={"status": closes}), base[4][4], "A sentence no page holds."

    def rechecked(label, fix, rejected="", layout="none", text09=fixture_text, text10=None,
                  line="7 s1"):
        (web / RECHECK).write_text(
            "| line | entity | PASS or FAIL | rule id | the fix |\n|---|---|---|---|---|\n"
            "| 3 s1 | Rival | PASS | P4 | not a quoted string |\n"
            "| %s | Rival | FAIL | P6 | %s |\n" % (line, fix), encoding="utf-8")
        (web / FIXER).write_text("# Stage 9\n\n## Rejected\n\n%s\n\n## Layout\n\n%s\n"
                                 % (rejected, layout), encoding="utf-8")
        # Literal names, not RECHECK_TEXT: a swapped tuple must not swap the case with it.
        for name, body in (("09-text-10.md", text10), ("09-text.md", text09)):
            if body is None:
                (web / name).unlink(missing_ok=True)
            else:
                (web / name).write_text(body, encoding="utf-8")
        return paged(label, green)

    for label, kw in (("recheck: the fix absent", {"fix": '"%s"' % absent}),
                      ("recheck: 17 s1 does not name 7 s1",
                       {"fix": '"%s"' % absent, "rejected": "- 17 s1: lint red"}),
                      ("recheck: 7 s1 named outside § Rejected",
                       {"fix": '"%s"' % absent, "layout": "- 7 s1"}),
                      ("recheck: text outside the quotes", {"fix": 'Cut, or: "%s"' % present}),
                      ("recheck: two quoted strings", {"fix": '"%s" or "%s"' % (present, present)}),
                      ("recheck: empty quotes", {"fix": '""'}),
                      ("recheck: bad form, rejected for a lint",
                       {"fix": "Cut it", "rejected": "- 7 s1: lint red"}),
                      # G86 (ii): the form reason clears a form break only, item by item.
                      ("recheck: good form, rejected for re-check form",
                       {"fix": '"%s"' % absent, "rejected": "- 7 s1: re-check form"}),
                      ("recheck: re-check form in another item",
                       {"fix": "Cut it", "rejected": "- 7 s1: lint red\n- 9 s2: re-check form"}),
                      # G87 Nice 4, Nice 3: the line's right edge, and quotes round spaces alone.
                      ("recheck: 7 s10 does not name 7 s1",
                       {"fix": "Cut it", "rejected": "- 7 s10: re-check form"}),
                      ("recheck: quotes round spaces", {"fix": '"   "'})):
        res = rechecked(label, **kw)
        page_case(label, _dropped(res, "7 s1") == {"recheck"} and res.by_critic["fixer"] == 1, res)
        hit.add("recheck")
    # G86 (i): a cut or merge is one whole-line row; an inner quote is curly, as the page prints it.
    line3 = "It names 3 of 5 listed resellers as partners."
    inner = "Its page says “one week” for a live integration."
    for label, kw in (("recheck: the fix present", {"fix": '"%s"' % present}),
                      ("recheck: the fix present, curly quotes", {"fix": "“%s”" % present}),
                      ("recheck: a whole-line fix present", {
                          "fix": '"%s"' % line3, "line": "3", "text09": fixture_text.replace(
                              fixture_text.split("\n")[2], line3)}),
                      ("recheck: a curly inner quote present", {
                          "fix": '"%s"' % inner, "text09": fixture_text + inner + "\n"}),
                      ("recheck: 7 s1 under § Rejected",
                       {"fix": '"%s"' % absent, "rejected": "- 7 s1: brief-check reds it"}),
                      ("recheck: bad form, rejected for re-check form",
                       {"fix": "Cut it", "rejected": "- 7 s1: re-check form, no replacement"}),
                      ("recheck: re-check form on an item's wrapped line",
                       {"fix": "Cut it", "rejected": "- 7 s1: the column breaks the\n  re-check form"}),
                      # G87: the phrase may wrap; "re-check" alone is no form reason; an empty
                      # line cell is named by its place (header, separator, PASS, then row 4); a
                      # curly pair may hold curly quotes; a fix's whitespace is collapsed.
                      ("recheck: re-check form wrapped inside the phrase", {
                          "fix": "Cut it", "rejected": "- 7 s1: out of the re-check\n  form"}),
                      ("recheck: re-check alone is a lint reason", {
                          "fix": '"%s"' % absent, "rejected": "- 7 s1: brief-check reds re-check 7 s1"}),
                      ("recheck: an empty line cell named by its place", {
                          "fix": "Cut it", "line": "", "rejected": "- 09-recheck.md:4: re-check form"}),
                      ("recheck: a curly pair holding curly quotes", {
                          "fix": "“%s”" % inner, "text09": fixture_text + inner + "\n"}),
                      ("recheck: a fix's whitespace collapsed", {
                          "fix": '" %s  "' % present.replace(" list ", "  list ")}),
                      # G86 (iii): on a repair, a fix in either text is present.
                      ("recheck: repair, fix in stage 9's copy", {
                          "fix": '"%s"' % absent, "text10": fixture_text + absent}),
                      ("recheck: repair, fix in the repaired text", {
                          "fix": '"%s"' % absent, "text09": fixture_text + absent,
                          "text10": fixture_text})):
        res = rechecked(label, **kw)
        page_case(label, not res.drops and "fixer" not in res.by_critic, res)
    rechecked("recheck: setup for no stage 9 text", '"%s"' % present)
    (web / "09-text.md").unlink()
    try:
        grade(page_json, web_led)
        _fail("recheck: a FAIL row with no 09-text.md or 09-text-10.md was graded")
    except Unusable:
        cases[0] += 1
        sys.stdout.write("SELFTEST page OK  %-44s -> unusable\n" % "recheck: no stage 9 text")
    for name in (RECHECK, FIXER) + RECHECK_TEXT:
        (web / name).unlink(missing_ok=True)
    paged("page: green for the CLI", spoil(F_03={"status": "fixed@" + page_sha[:12]}))
    (web / PAGE_TEXT).unlink()
    try:
        grade(page_json, web_led)
        _fail("page: a brief.json with no 08-text.md beside its ledger was graded")
    except Unusable:
        cases[0] += 1
        sys.stdout.write("SELFTEST page OK  %-44s -> unusable\n" % "page: no 08-text.md")
    shutil.copy(brief, web / PAGE_TEXT)

    # The CLI, as a child process, because the exit code is what a caller reads. The last case is
    # a copy of this file with no `claims-check.py` beside it, which must refuse, not crash.
    spoilt = tmp / "run" / "findings-ledger.tsv"
    spoilt.parent.mkdir()
    spoilt.write_text("".join("\t".join(r) + "\n" for r in spoil(F_01={"quote": "x"})),
                      encoding="utf-8")
    me = pathlib.Path(__file__).resolve()
    lone = tmp / "lone" / "tools" / me.name
    lone.parent.mkdir(parents=True)
    shutil.copy(me, lone)
    fx_ledger = FIXTURE / "findings-ledger.tsv"
    for want, argv, root, marker in (
            (0, [me, "--check", brief, fx_ledger], None, "CRITIQUE-CHECK-OK"),
            (0, [me, "--check", page_json, web_led], None, "CRITIQUE-CHECK-OK"),
            (1, [me, "--check", brief, spoilt], None, "CRITIQUE-CHECK RED"),
            (1, [me, "--check", brief], spoilt.parent, "CRITIQUE-CHECK RED"),
            (2, [me, "--check", tmp / "absent.md", spoilt], None, "FAIL: cannot read brief"),
            (2, [me], None, "usage:"),
            (2, [me, "--check", brief], None, "BRIEF_ROOT is not set"),
            (2, [lone, "--selftest"], None, "cannot load tools/claims-check.py")):
        env = {k: v for k, v in os.environ.items() if k != "BRIEF_ROOT"}
        if root:
            env["BRIEF_ROOT"] = str(root)
        proc = subprocess.run([sys.executable] + [str(a) for a in argv], env=env,
                              capture_output=True, text=True)
        if proc.returncode != want or marker not in proc.stdout + proc.stderr:
            _fail("CLI exited %d, want %d with %r; got %s" %
                  (proc.returncode, want, marker, proc.stdout + proc.stderr))
        cases[0] += 1
        sys.stdout.write("SELFTEST green OK %-44s -> exit %d\n" % ("CLI " + marker[:38], want))

    for rule in RULES:
        if rule not in hit:
            _fail("RULES carries %s, which no case proves red" % rule)
    if hit - set(RULES):
        _fail("a case proved %s red, which RULES does not carry" % sorted(hit - set(RULES)))
    sys.stdout.write("CRITIQUE-CHECK SELFTEST OK (%d cases, %d rules)\n" % (cases[0], len(RULES)))
    return 0

USAGE = """usage:
  critique-check.py --check <briefing.md> [ledger]
                          grade the ledger (default $BRIEF_ROOT/findings-ledger.tsv; exit 2 when
                          neither is given) against the brief and quality-bar/; exit 1 when any
                          row is dropped
  critique-check.py --selftest
                          prove every drop rule red on its own case
"""


def default_ledger():
    """`$BRIEF_ROOT/findings-ledger.tsv`, or None: a ledger belongs to a run, not the checkout."""
    root = os.environ.get("BRIEF_ROOT")
    return pathlib.Path(root).expanduser() / "findings-ledger.tsv" if root else None


def main(argv):
    if len(argv) == 2 and argv[1] == "--selftest":
        return selftest()
    if len(argv) not in (3, 4) or argv[1] != "--check":
        sys.stderr.write(USAGE)
        return 2
    brief = pathlib.Path(argv[2])
    ledger = pathlib.Path(argv[3]) if len(argv) == 4 else default_ledger()
    if ledger is None:
        sys.stderr.write("FAIL: no ledger named and BRIEF_ROOT is not set\n" + USAGE)
        return 2
    try:
        return report(grade(brief, ledger), "%s against %s" % (ledger, brief))
    except Unusable as exc:
        sys.stderr.write("FAIL: %s\n" % exc)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
