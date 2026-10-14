#!/usr/bin/env python3
"""The budget check, in two parts. `--templates` grades the frontmatter of every stage template;
`--allocation` and `--build-log`, space mode, grade a run's space budget before and after writing.

WHY TEMPLATES. A stage template's header names the model its agent runs on and the turn cap
`tools/run-cost.sh --caps` holds that agent's transcript to. A template with no cap is a stage the
tripwire never watches (`--caps` prints `nocap` and moves on), and a model outside the allocation
is spend nobody chose. The allocation is `docs/retro/2026-09-18-northwind/65-model-allocation.md`: Opus
for research, writing and judgement, Sonnet only where a gate goes red on a quality drop, Haiku
nowhere. Caps are tripwires, never kills; this check asks only that each one is set.

THE RULES. A template is RED when its header:

  frontmatter       is missing: line 1 is not exactly `---`, or no exact `---` closes it;
  crlf              carries a carriage return on any header line;
  model             lacks `model:`, or names anything but `opus` or `sonnet`;
  max_turns         lacks `max_turns:`, or its value is not an integer;
  nested_max_turns  is present but unreadable, or its value is not an integer;
  TBD               carries `TBD` on any line, a value nobody has set;
  effort            carries an `effort:` (any node, nested or in a flow map) that is not low,
                    medium, high or xhigh: no node runs at `max` (design.md section 3).

Every rule mirrors how `run-cost.sh`'s `cap_of` reads a header: exact `---` lines, and a key as
the first whitespace-separated token ending in `:`. A header `--caps` cannot read is red here, so
`max_turns:30` with no space, `--- ` with a trailing space and a CRLF file are all red.
`nested_max_turns:` is optional, since only a stage that dispatches subagents carries it.

WHAT IT DOES NOT CHECK: whether a cap fits the stage or the model suits the task. Those are the
allocation's judgement and the replay's measurement.

SPACE MODE. The budget is `$BRIEF_ROOT/06-budget.tsv`: the header `slot<TAB>cm`, then one row per
slot with a cm above 0. A line opening `#` is a note: stage 7 writes one per re-budget it makes. A row is the slot's whole rendered extent, the unit `heights ->` prints,
and both modes read it as it stands. So the `sources` row includes the colophon, about 1.2 cm
that every build adds under the last slot (`S4.1-fix.md` Rc2). The writer's own `sources` text
gets the row minus 1.2 cm, and nothing adds the colophon a second time.

`--allocation BRIEF_ROOT` runs before any prose is written. It is RED on:

  join      a slot in only one of `06-budget.tsv` and `$BRIEF_ROOT/headings.json`;
  capacity  a budget total over CAPACITY_CM.

`--build-log GATE_LOG BRIEF_ROOT` runs after each build, on its `$BRIEF_ROOT/audit/gate-NN.txt`.
It is RED on:

  heights   no `heights ->` line, or more than one. `audit()` prints the line, and
            `build.py --selftest` never runs `audit()`, so this rule is what catches a build that
            stops printing it (`S4.1-fix.md` Rc1);
  absent    a slot printed as `absent`, meaning its heading did not render;
  over      a figure more than TOLERANCE_CM over its row, `sources` included. A budget row with
            no figure, or a figure with no budget row, is also over;
  stranded  a `pages ->` count over GATE 3's limit, no `over` red, and a page, the last
            excepted, whose `gaps ->` figure is over STRAND_CM. For each such page it names the
            slot `opens ->` says opened the next one, that slot's height, and about how much to
            cut to pull it back. The strands are alternatives, listed smallest cut first;
  pages     a `pages ->` count over GATE 3's limit. With no `stranded` red it names every slot
            above its row, with no tolerance and the largest excess first, so the writer knows
            what to cut. With one, it names that red as the cause and no slot.

THE STRANDED SPACE. `brief.css` holds every table whole, so a table that does not fit moves to
the next page with its heading and leaves the rest of the page empty: 9.1 cm under the matrix on
the p14-f1 replay, up to a table's own height. Growth can then fit every tolerance and still make
five pages. The slots over their rows are then innocent, and cutting them leaves the break where
it is (`P14b-verify.md` Required 1). A slot truly OVER still outranks a strand: the strand may
stand in the budgeted layout that fitted, so `stranded` waits until no slot is over
(`P14b-verify-2.md` Required 1). Pulling back any one strand returns the page: on that replay a
2.0 cm cut on p4 alone, or a 4.9 cm cut on p2 alone, gave four pages. So the strands are listed
as alternatives, smallest first (Required 2). The cut is the opener's height minus the gap plus
BREAK_CM, 2.3 cm: 1.2 cm the gaps figure counts below the text area (40 pt against a 26 mm foot
margin) and 1.1 cm of heading margin and table spacing the heights figure omits. It is an
estimate within about 0.5 cm either way. For the 11.5 cm matrix after a 9.1 cm gap it says 4.7:
4.5 cm failed and 4.9 cm worked. For the 7.9 cm sources block after an 8.0 cm gap it says 2.2,
and 2.0 cm worked. The rebuild is the measurement.

THE CAPACITY is a ceiling: 86.8 cm, the exemplar's ten `heights ->` figures (`S4.1-build.md`).
A total alone cannot promise four pages. 87.3 cm fitted with open-questions 0.5 cm over its row,
and the same total made five pages with coverage-notes 0.5 cm over (`P12-verify-2.md` R1).
Where the growth lands decides the page count, which is why `pages` exists. The `gaps ->` space
is not spare. It is lost where a
section breaks to the next page, and adding 12 words to quick-take (88.7 cm, `P12-verify.md` R1;
87.9 cm in `P12-build.md` Fix 1) made five pages. A brief with fewer sections pays fewer margins,
so for it the ceiling is conservative. Two risks stay open: a company name long enough to wrap the
masthead, and a brief heavier in tables than the exemplar. Either can fill five pages under 86.8,
and GATE 3 is what catches that.

THE TOLERANCE. When one section grows, a section nobody edited moves by up to 0.4 cm, because its
page breaks shift (`P12-verify.md` R3, 14 probe builds). 0.5 cm clears that drift. At 0.3 cm the
writer would be told to cut a section they never touched.

Two checks live elsewhere. GATE 3 in `build/build.py` decides the page count; `pages` reads its
`pages ->` line only to name the slots to cut. The limit is read from GATE 3's own
`if doc.page_count > N:` line, so the number is written once. Whether each slot and heading
is a valid catalogue entry is `chosen_headings()`'s job. This tool never imports `build.py`,
because that imports `markdown`, which CI does not install.

WEB MODE. `--allocation --web BRIEF_ROOT` grades the page's allocation before any prose. The page
carries every `web: true` slot of `references/headings.json`, so `06-budget.tsv` is the header
`slot<TAB>words<TAB>items` and one row per web slot, each count a whole number above 0. A slot's
caps are read from `build/web/brief.schema.json`, the one source of them: items is the maxItems of
the slot's list (WEB_FIELDS), and words is the most its fields can hold, every x-maxWords summed
and multiplied out through each maxItems. `$BRIEF_ROOT/06-shape.json` is the map's two axes, each
company's answer on each, the matrix columns and its rows (`references/stages/06-allocation.md`
§ The shape). The cohort is every `$BRIEF_ROOT/comp-<slug>.md`, and the locked questions are the
`### Q<n>.` headings of `$BRIEF_ROOT/02-questions.md`. It is RED on:

  cap       a slot's words or items over its schema cap; more matrix rows or map answers than the
            slot's budgeted items; an axis `question`, `yes` or `no`, or a row `label`, over the
            schema's x-maxWords for that field in `brief.json`;
  cohort    a `company` (the hiring company's slug) outside the cohort; `columns` or the map's
            answers naming a set of companies other than the cohort, once each; `columns` not
            opening with `company`;
  answer    a company with no yes or no on an axis, with no claim ID under its answer, or with a
            non-empty `integration` under a yes; or a yes that brief-check's `carries_yes` refuses,
            resting on a row whose claim says "integration" or on pilots alone (G92 (i));
  split     an axis where every company answers alike, so it places nobody apart;
  question  a matrix row whose `serves` is no locked question;
  unknown   a matrix row with more than UNKNOWN_MAX `Unknown` cells;
  label     a matrix row `label` carrying `:`, `(`, `[` or a spaced dash (LABEL_CUT), where an
            `H1′ row` line's label ends, so no such line could name it (G89);
  name     a map answer's `name` not verbatim in the `claim` of every row its `c` cites, the
            gate `build/web.py` holds the page to (W2-rulings.md G32);
  integration  an `integration` ID whose `claims.jsonl` row the page does not quote, or whose
            `claim` lacks "integration": `web.py`'s 36 R3 test, read through brief-check's
            `shows_quote` so the two cannot drift (G76). An ID with no row is the url rule's;
  url       a claim ID with no `$BRIEF_ROOT/claims.jsonl` row, or whose row has no `url`: its card
            has no source to print, and brief-check C2 reds it (G32). The IDs are the map's, the
            matrix cells', and every `- Claims:` and `- Evidence clause` line of
            `06-allocation.md`, by slot (G39, G42). So an `unfound` row with no URL is ledger
            evidence only, never cited on the page (G40). `Dropped row` and `Qualifiers` lines
            are not read: they cite IDs the page never prints as facts;
  sources   a matrix cell citing more than CELL_IDS_MAX distinct IDs; or, over the url rule's IDs
            and each `- ICP` line's, more than PAGE_IDS_MAX distinct IDs, PAGE_URLS_MAX distinct
            URLs or CARD_WORDS_MAX card words: THE SOURCES CEILINGS (W4-rulings.md G92 (ii), G95).
            The ID and card-word reds list each ID with its card words, heaviest first.

THE SOURCES CEILINGS are live T's own maxima, rounded up, so they hold for any company: 2 IDs a
cell, 60 distinct IDs and 45 distinct URLs a page, 1,500 card words. A card's words are each
distinct ID's shown quote, or its gloss, plus CARD_ID_WORDS. They are [INFERRED], for W21 to
calibrate.

UNKNOWN_MAX is 1, an [INFERRED] threshold that the W18 replay calibrates
(`73-web-plan.md:303`). The shape could not run, exit 2, on a missing key, a cell count other
than the column count, an ID that is not `C-NNN`, or an `integration` list that is missing or
names an ID outside its answer's `c`. That list makes INTEG explicit (`W2-rulings.md` G10): the
claims whose evidence is an integration, not a customer, are named by the allocation instead of
inferred by `build/web.py`.

SHAPE HASH (W4-rulings.md G80, amending G56). A change to a claim ID, axis, row or answer is a
revision; a change to words alone is not. So `Shape: <sha256>` hashes a projection of
`06-shape.json`, never its bytes: `shape_projection` keeps each axis's `serves`; each answer's
company, yes or no, `c` and `integration`; and each row's `serves` with its cells, each keyed by
its column's company. It sorts ID lists, answers and rows, so order is not a revision, and leaves
out every word: `question`, `yes`, `no`, `name`, `label`, `company` and any other key.
`--shape-hash BRIEF_ROOT` prints that line, and `tools/shape.py write` stamps it into
`06-allocation.md` beside the shape it writes.

THE CODE SCREEN (S11; Globex design § 2 R2, § 7 "Stage-6 judgement moves to the author"). Stage 6
was an LLM screener and a fix loop over `06-screen-<N>.md` files; the typed `shape` node replaced
it, and `--screened BRIEF_ROOT` is now the screen: every property of the old screener a script can
decide, run on the shape as it stands, before any prose. The rest of the old screener (H1's
judgement, H1′'s soundness, H3, H3′) is the shape node's own instruction in
`references/stages/06-allocation.md`. It reads `06-shape.json`, `06-allocation.md` (as
`tools/shape.py write` writes it), the locked questions, `claims.jsonl` and, when present,
`reader.json`'s `known_hosts`. No screen file is read. It is RED on:

  screened  `06-allocation.md` with no `Shape:` line, or one naming a hash other than the SHAPE
            HASH now: the record was not written from this shape;
  decision  (H1′) an axis or matrix row with no `- H1′ across|down|row <label> (Q<n>): <decision>
            | flips: <flips>` line in `06-allocation.md`, with a non-empty decision and flip, whose
            Q<n> is the `serves` of that axis or row and a locked question. label_key matches a
            row's label, so a relabel in the shape alone reds here;
  evidence  (H1, H2) a web slot with no `### <slot>` block carrying an `- Evidence clause` line
            that names a claim ID: the slot's non-cuttable fact, which H1 and H2 grade;
  known     (H2) an evidence clause whose first ID, its main fact, is a row the founder already
            holds (the row's `known: true`, else its URL on `reader.json`'s `known_hosts`, as
            `tools/rank.py` decides KNOWN), unless `06-allocation.md` § Departures names that slot
            and ID with a reason (`- <slot> C-NNN: <reason>`).

BY QUESTION (Globex design § 3 `allocate`, find-F F4: a claim added late went back through stage 6
three times). `--allocation --by-question BRIEF_ROOT` prints, as JSON on stdout, each
`06-allocation.md` slot's `- Claims:` and `- ICP` IDs grouped by their `claims.jsonl` row's
`question_id` (null rows under `none`), and each slot's `eligible` IDs: every other ledger row on a
question the slot already serves, allocated by construction. The groups joined are the slot's
record exactly; on the Globex run they give back all six slots. The locked questions are
`questions.json`'s, else `02-questions.md`'s. It is RED, on stderr, on:

  unknown     an allocated ID with no `claims.jsonl` row;
  question    an allocated row whose `question_id` is no locked question;
  unanswered  a locked question no slot allocates a row for.

EXIT CODES. 0 green. 1 one or more red. 2 could not run: bad usage; a missing directory, or one
with no templates, since an empty set is never green; or an unreadable budget, record or log.

USAGE. `budget-check.py --templates [DIR]`, DIR defaulting to `references/stages/`.
`budget-check.py --allocation [--web|--by-question] BRIEF_ROOT`, `--shape-hash BRIEF_ROOT`, `--screened BRIEF_ROOT`
(exit 1 also on a code-screen red)
and `--build-log GATE_LOG BRIEF_ROOT`.
`budget-check.py --selftest` breaks one rule per case in a copy of the fixtures under
`tools/fixtures/budget-check/`, covering every mode. No network, no model call, no run directory.
"""
import hashlib
import importlib.util
import json
import math
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
STAGES = ROOT / "references" / "stages"
FIXTURES = ROOT / "tools" / "fixtures" / "budget-check" / "templates"
SPACE = ROOT / "tools" / "fixtures" / "budget-check" / "space"
MODELS = ("opus", "sonnet")
EFFORTS = ("low", "medium", "high", "xhigh")   # `max` is absent on purpose: see header_reds
BUILD_PY = ROOT / "build" / "build.py"
CAPACITY_CM = 86.8   # the exemplar's total: THE CAPACITY
TOLERANCE_CM = 0.5   # how far a section nobody edited moves when another one grows: THE TOLERANCE
STRAND_CM = 4.0      # a non-last page gap over this is stranded space: audit()'s advisory figure
BREAK_CM = 2.3       # the cut on top of height minus gap: THE STRANDED SPACE
WEB = ROOT / "tools" / "fixtures" / "budget-check" / "web"
SCHEMA = ROOT / "build" / "web" / "brief.schema.json"
CATALOGUE = ROOT / "references" / "headings.json"
UNKNOWN_MAX = 1      # [INFERRED] Unknown cells a matrix row may carry; W18 calibrates it
# THE SOURCES CEILINGS (W4-rulings.md G92 (ii)): live T's own maxima, rounded up, so they hold for
# any company. [INFERRED]: W21 calibrates them.
CELL_IDS_MAX = 2     # claim IDs a matrix cell may cite: T's most is 2
PAGE_IDS_MAX = 60    # distinct claim IDs a page may cite: T cites 60
PAGE_URLS_MAX = 45   # distinct source URLs a page may print: T prints 43
CARD_WORDS_MAX = 1500  # words the page's source cards may hold: T's come to 1,394
CARD_ID_WORDS = 8    # what each distinct ID's card adds to its shown quote or gloss
# WEB MODE: slot -> (the brief.json fields its words come from, the dotted path of its item list).
WEB_FIELDS = {
    "quick-take": (("quick_take",), "quick_take"),
    "recommendations": (("recommendations",), "recommendations"),
    "what-changed": (("moves", "moves_heading"), "moves"),
    "open-questions": (("open_questions",), "open_questions"),
    "matrix": (("matrix",), "matrix.rows"),
    "map": (("map",), "map.answers"),
}
CLAIM_ID = re.compile(r"C-[0-9]{3,}")


def header(text):
    """(pairs, lines) for the closed `---` block at line 1, or None when there is none."""
    lines = text.split("\n")
    if lines[0] != "---":
        return None
    for end in range(1, len(lines)):
        if lines[end] == "---":
            pairs = {}
            for line in lines[1:end]:
                words = line.split()
                if words and words[0].endswith(":"):
                    pairs.setdefault(words[0][:-1], " ".join(words[1:]))
            return pairs, lines[1:end]
    return None


def header_reds(text):
    """Every rule a template's header breaks, as (rule, detail) pairs."""
    parsed = header(text)
    if parsed is None:
        return [("frontmatter", "no block from an exact --- at line 1 to an exact --- closing it")]
    pairs, lines = parsed
    reds = []
    if any("\r" in line for line in lines):
        reds.append(("crlf", "a carriage return in the header, which --caps cannot read"))
    model = pairs.get("model")
    if model not in MODELS:
        why = "missing" if model is None else f"'{model}' is not one of {', '.join(MODELS)}"
        reds.append(("model", why))
    turns = pairs.get("max_turns")
    if turns is None or not turns.isdigit() or not turns.isascii():
        reds.append(("max_turns", "missing" if turns is None else f"'{turns}' is not an integer"))
    nested = pairs.get("nested_max_turns")
    if nested is None:
        if any(line.split() and line.split()[0].startswith("nested_max_turns") for line in lines):
            reds.append(("nested_max_turns", "present but not read as `nested_max_turns: N`"))
    elif not nested.isdigit() or not nested.isascii():
        reds.append(("nested_max_turns", f"'{nested}' is not an integer"))
    # No node runs at `max` (design.md section 3, node table): it cost 7-11x high and bought no
    # verdict stability. Every `effort` key is read, nested node entries and flow maps included.
    for line in lines:
        if line.lstrip().startswith("#"):
            continue
        for m in re.finditer(r"(?:^|[\s{,])(effort):\s*([^\s,}\]]+)", line):
            if m.group(2) not in EFFORTS:
                reds.append(("effort", f"'{m.group(2)}' is not one of {', '.join(EFFORTS)}"))
    unset = [line.strip() for line in lines if "TBD" in line]
    if unset:
        reds.append(("TBD", "; ".join(unset)))
    return reds


def check_templates(directory):
    """(reds, count): reds as (file, rule, detail) triples, count the templates read."""
    files = sorted(pathlib.Path(directory).glob("*.md"))
    reds = []
    for path in files:
        # Bytes, not read_text(): universal newlines would turn CRLF into LF and hide it.
        for rule, detail in header_reds(path.read_bytes().decode("utf-8")):
            reds.append((path.name, rule, detail))
    return reds, len(files)


def templates(directory):
    directory = pathlib.Path(directory)
    if not directory.is_dir():
        print(f"budget-check: --templates: directory not found: {directory}", file=sys.stderr)
        return 2
    reds, count = check_templates(directory)
    if count == 0:
        print(f"budget-check: --templates: no *.md templates in {directory}", file=sys.stderr)
        return 2
    for name, rule, detail in reds:
        print(f"RED {name} {rule}: {detail}")
    if reds:
        print(f"BUDGET-CHECK FAIL (--templates: {len(reds)} red across {count} template(s))")
        return 1
    print(f"BUDGET-CHECK OK (--templates: {count} template(s))")
    return 0


class Unreadable(Exception):
    """A budget, record or build log this tool cannot read: exit 2, never a verdict."""


def read_budget(root):
    """{slot: cm} from `06-budget.tsv`: a `slot<TAB>cm` header, then one finite cm > 0 per slot.
    A line opening `#` is a note, skipped: stage 7 records each re-budget it makes there."""
    path = pathlib.Path(root) / "06-budget.tsv"
    if not path.is_file():
        raise Unreadable(f"no budget at {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "slot\tcm":
        raise Unreadable(f"{path}: line 1 must be the header slot<TAB>cm")
    budget = {}
    for n, line in enumerate(lines[1:], 2):
        if line.startswith("#"):
            continue
        cells = line.split("\t")
        try:
            cm = float(cells[1]) if len(cells) == 2 and cells[0] else None
        except ValueError:
            cm = None
        if cm is None or not math.isfinite(cm) or cm <= 0 or cells[0] in budget:
            raise Unreadable(f"{path}:{n}: want a new slot, a tab, and a cm above 0; got {line!r}")
        budget[cells[0]] = cm
    if not budget:
        raise Unreadable(f"{path}: no slot rows")
    return budget


def read_slots(root):
    """The slot IDs `$BRIEF_ROOT/headings.json` records. Their catalogue validity is
    `chosen_headings()`'s to grade, in the build."""
    path = pathlib.Path(root) / "headings.json"
    try:
        return [entry["slot"] for entry in json.loads(path.read_text(encoding="utf-8"))["sections"]]
    except (OSError, ValueError, KeyError, TypeError) as err:
        raise Unreadable(f"{path}: no readable sections[].slot list ({err})") from err


def figures(line):
    """{slot: cm or 'absent'} from one `heights ->` line."""
    out = {}
    for token in line.split("->", 1)[1].split():
        slot, _, value = token.rpartition(":")
        try:
            cm = value if value == "absent" else float(value.removesuffix("cm"))
        except ValueError:
            cm = None
        if not slot or slot in out or cm is None or not value.endswith(("cm", "absent")):
            raise Unreadable(f"heights -> token {token!r} is not slot:N.Ncm or slot:absent")
        out[slot] = cm
    return out


def allocation_reds(root):
    """(rule, detail) pairs for a budget before any prose is written."""
    budget, slots = read_budget(root), read_slots(root)
    reds = []
    only = sorted(set(budget) ^ set(slots))
    if only:
        reds.append(("join", f"slot(s) {only} in only one of 06-budget.tsv and headings.json"))
    total = round(sum(budget.values()), 2)
    if total > CAPACITY_CM:
        reds.append(("capacity", f"budget total {total}cm is over the {CAPACITY_CM}cm ceiling"))
    return reds


def load_json(path):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise Unreadable(f"{path}: not readable JSON ({err})") from err


def web_caps():
    """{slot: (words, items)}, every number read from the schema: WEB MODE."""
    schema = load_json(SCHEMA)
    defs = schema.get("$defs", {})

    def node(n):
        while "$ref" in n and "x-maxWords" not in n and "maxItems" not in n:
            n = defs[n["$ref"].rsplit("/", 1)[1]]
        return n

    def words(n):
        if "x-maxWords" in n:
            return n["x-maxWords"]
        n = node(n)
        if "properties" in n:
            return sum(words(p) for p in n["properties"].values())
        if "items" in n:
            each = words(n["items"])
            if each and "maxItems" not in n:
                raise Unreadable(f"{SCHEMA}: a list of capped text carries no maxItems")
            return n.get("maxItems", 0) * each
        return 0

    try:
        web = [s["id"] for s in load_json(CATALOGUE)["slots"] if s.get("web")]
        if sorted(web) != sorted(WEB_FIELDS):
            raise Unreadable(f"{CATALOGUE}: web slots {sorted(web)} are not WEB_FIELDS' {sorted(WEB_FIELDS)}")
        caps = {}
        for slot, (fields, path) in WEB_FIELDS.items():
            listed = schema
            for key in path.split("."):
                listed = node(node(listed)["properties"][key])
            caps[slot] = (sum(words(schema["properties"][f]) for f in fields), listed["maxItems"])
    except (KeyError, TypeError) as err:
        raise Unreadable(f"{SCHEMA} or {CATALOGUE}: a cap cannot be read ({err!r})") from err
    return caps


def read_web_budget(root, slots):
    """{slot: (words, items)} from `06-budget.tsv`, one row per web slot: WEB MODE."""
    path = pathlib.Path(root) / "06-budget.tsv"
    if not path.is_file():
        raise Unreadable(f"no budget at {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "slot\twords\titems":
        raise Unreadable(f"{path}: line 1 must be the header slot<TAB>words<TAB>items")
    budget = {}
    for n, line in enumerate(lines[1:], 2):
        if line.startswith("#"):
            continue
        cells = line.split("\t")
        if (len(cells) != 3 or cells[0] in budget or not all(c.isascii() and c.isdigit()
                                                             and int(c) > 0 for c in cells[1:])):
            raise Unreadable(f"{path}:{n}: want a new slot, then words and items above 0; got {line!r}")
        budget[cells[0]] = (int(cells[1]), int(cells[2]))
    if sorted(budget) != sorted(slots):
        raise Unreadable(f"{path}: rows {sorted(budget)} are not the web slots {sorted(slots)}")
    return budget


def ids_of(value, where):
    """The claim IDs of a list of `C-NNN` strings; anything else is unreadable."""
    if not isinstance(value, list) or not all(isinstance(c, str) and CLAIM_ID.fullmatch(c) for c in value):
        raise Unreadable(f"06-shape.json: {where}: want a list of C-NNN claim IDs, got {value!r}")
    return value


def field_caps():
    """{field: x-maxWords} for the shape's own words, as `brief.json` will hold them."""
    defs = load_json(SCHEMA).get("$defs", {})
    try:
        axis = defs["axis"]["properties"]
        label = defs["matrix"]["properties"]["rows"]["items"]["properties"]["label"]
        return {"question": axis["question"]["x-maxWords"], "yes": axis["yes"]["x-maxWords"],
                "no": axis["no"]["x-maxWords"], "label": label["x-maxWords"]}
    except (KeyError, TypeError) as err:
        raise Unreadable(f"{SCHEMA}: a shape word cap cannot be read ({err!r})") from err


def read_shape(root):
    """(map, matrix) from `06-shape.json`, every key the rules read checked first: WEB MODE."""
    shape = load_json(pathlib.Path(root) / "06-shape.json")
    try:
        smap, matrix, shape["company"] = shape["map"], shape["matrix"], str(shape["company"])
        for axis in ("across", "down"):
            smap[axis]["serves"]
        for entry in smap["answers"]:
            for axis in ("across", "down"):
                an, where = entry[axis], f"{entry['company']} {axis}"
                an["answer"], an["name"]
                cs = ids_of(an["c"], where + " c")
                if not set(ids_of(an["integration"], where + " integration")) <= set(cs):
                    raise Unreadable(f"06-shape.json: {where}: integration {an['integration']} is not within c {cs}")
        for row in matrix["rows"]:
            row["label"], row["serves"]
            if len(row["cells"]) != len(matrix["columns"]):
                raise Unreadable(f"06-shape.json: row {row['label']!r}: {len(row['cells'])} cells for "
                                 f"{len(matrix['columns'])} columns")
            for cell in row["cells"]:
                if cell != "Unknown":
                    ids_of(cell, f"row {row['label']!r} cell")
    except (KeyError, TypeError) as err:
        raise Unreadable(f"06-shape.json: missing or malformed {err!r}") from err
    return shape["company"], smap, matrix


def shape_projection(root):
    """SHAPE HASH: the part of `06-shape.json` G56 calls a revision, by identity, never by place.
    Each axis is its `serves`; each answer is its company's yes or no with its `c` and
    `integration`; each row is its `serves` and its cells, each keyed by its column's company.
    ID lists, answers and rows are sorted, so an order change is not a revision. Words are left out:
    `question`, `yes`, `no`, `name`, `label`, `company` and any other key."""
    _, smap, matrix = read_shape(root)
    pick = lambda an: [str(an["answer"]), sorted(an["c"]), sorted(an["integration"])]
    cell = lambda c: c if c == "Unknown" else sorted(c)
    canon = lambda v: json.dumps(v, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return canon({
        "axes": [str(smap[axis]["serves"]) for axis in ("across", "down")],
        "answers": sorted(([str(e["company"]), pick(e["across"]), pick(e["down"])] for e in smap["answers"]), key=canon),
        "rows": sorted(({"serves": str(r["serves"]),
                         "cells": sorted(([str(col), cell(c)] for col, c in zip(matrix["columns"], r["cells"])), key=canon)}
                        for r in matrix["rows"]), key=canon),
    })


def shape_hash(root):
    """The sha256 of `shape_projection`: what 06-allocation.md's `Shape:` line records (G80)."""
    return hashlib.sha256(shape_projection(root).encode("ascii")).hexdigest()


def read_claims(root):
    """{id: row} from `$BRIEF_ROOT/claims.jsonl`; the two ledger rules read nothing else (G32)."""
    path = pathlib.Path(root) / "claims.jsonl"
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, ValueError) as err:
        raise Unreadable(f"no readable ledger at {path} ({err})") from err
    return {r["id"]: r for r in rows if isinstance(r, dict) and isinstance(r.get("id"), str)}


_BC = []


def brief_check():
    """`tools/brief-check.py`, for its `shows_quote` (G76). Loaded on first call, never at import:
    brief-check loads this file at import, so a load here would recurse."""
    if not _BC:
        sys.dont_write_bytecode = True  # no tools/__pycache__/ left in the tree
        spec = importlib.util.spec_from_file_location("brief_check", ROOT / "tools" / "brief-check.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _BC.append(mod)
    return _BC[0]


# The `06-allocation.md` lines that cite claim IDs, by kind: what a slot carries, the quick take's
# ICP paragraph, and the slot's non-cuttable fact, with or without its parenthesis
# (`- Evidence clause (rec 1, ...)`). brief-check A1 reads all three (G41); the url rule reads
# claims and evidence (G42).
CLAIM_LINES = {"claims": "- Claims:", "icp": "- ICP", "evidence": "- Evidence clause"}


def allocation_claims(root, kinds=("claims",)):
    """(slot, claim ID) for every ID on a line of `kinds`, keys of CLAIM_LINES, in
    `06-allocation.md`, under its `### <slot>` heading (G39, G41, G42)."""
    path = pathlib.Path(root) / "06-allocation.md"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as err:
        raise Unreadable(f"no allocation record at {path} ({err})") from err
    prefixes = tuple(CLAIM_LINES[k] for k in kinds)
    slot, out = None, []
    for line in lines:
        if line.startswith("### "):
            slot = line[4:].strip()
        elif line.startswith(prefixes):
            out += [(slot, cid) for cid in re.findall(r"\bC-\d{3,}\b", line)]
    return out


def locked_questions(root):
    """The Q<n> of every `### Q<n>.` heading in `02-questions.md`."""
    path = pathlib.Path(root) / "02-questions.md"
    try:
        found = re.findall(r"^### (Q[1-9])\. ", path.read_text(encoding="utf-8"), re.M)
    except OSError as err:
        raise Unreadable(f"no locked questions at {path} ({err})") from err
    if not found:
        raise Unreadable(f"{path}: no `### Q<n>.` heading, so no locked question")
    return set(found)


# --- allocation by question ID (Globex design § 3 `allocate`; find-F F4) --------------------------
NONE_Q = "none"  # the group of a row whose question_id is null: the reader's own facts, a late row


def questions_of(root):
    """The locked question IDs: `questions.json` when the run wrote one, else 02-questions.md's."""
    path = pathlib.Path(root) / "questions.json"
    if path.is_file():
        try:
            return {q["id"] for q in json.loads(path.read_text(encoding="utf-8"))["questions"]}
        except (OSError, ValueError, KeyError, TypeError) as err:
            raise Unreadable(f"{path} has no readable questions[].id ({err})") from err
    return locked_questions(root)


def by_question(root):
    """(allocation, reds). The allocation is, per `06-allocation.md` slot in record order, its
    `- Claims:` and `- ICP` IDs grouped by each row's `question_id` (NONE_Q for null), every
    group in record order, so the groups joined give back the slot's IDs exactly; and `eligible`,
    the ledger's other rows on the slot's questions, which the slot holds by construction: a row
    an extractor adds late on a question the slot already serves needs no new allocation."""
    claims, locked = read_claims(root), questions_of(root)
    slots, reds = {}, []
    for slot, cid in allocation_claims(root, ("claims", "icp")):
        ids = slots.setdefault(slot, [])
        if cid not in ids:
            ids.append(cid)
    out = {}
    for slot, ids in slots.items():
        groups = {}
        for cid in ids:
            row = claims.get(cid)
            if row is None:
                reds.append(("unknown", f"{slot}: {cid} has no claims.jsonl row"))
                continue
            q = row.get("question_id") or NONE_Q
            if q != NONE_Q and q not in locked:
                reds.append(("question", f"{slot}: {cid} answers {q}, which is no locked question "
                                         f"({', '.join(sorted(locked))})"))
            groups.setdefault(q, []).append(cid)
        served = {q for q in groups if q != NONE_Q}
        eligible = sorted((cid for cid, r in claims.items() if r.get("question_id") in served and cid not in ids),
                          key=lambda c: int(c[2:]) if c[2:].isdigit() else 0)
        out[slot] = {"questions": sorted(served), "claims": groups, "eligible": eligible}
    answered = {q for a in out.values() for q in a["questions"]}
    for q in sorted(locked - answered):
        reds.append(("unanswered", f"{q} is locked and no slot allocates a row answering it"))
    return out, reds


def by_question_cli(root):
    """`--allocation --by-question`: the allocation as JSON on stdout, then the verdict."""
    try:
        alloc, reds = by_question(root)
    except Unreadable as err:
        print(f"budget-check: --allocation --by-question: {err}", file=sys.stderr)
        return 2
    print(json.dumps({"slots": alloc}, indent=1))
    for rule, detail in reds:
        print(f"RED {rule}: {detail}", file=sys.stderr)
    if reds:
        print(f"BUDGET-CHECK FAIL (--allocation --by-question: {len(reds)} red)", file=sys.stderr)
        return 1
    print(f"BUDGET-CHECK OK (--allocation --by-question: {len(alloc)} slots, "
          f"{sum(len(i) for a in alloc.values() for i in a['claims'].values())} IDs by question)", file=sys.stderr)
    return 0


# A list marker before a line: `-`, `*`, `+` or `1.` (G88, G90).
BULLET = r"\s*(?:(?:[-*+]|\d+[.)])\s+)?"
# G90: after `Shape`, any text up to the first run of exactly 64 hex digits in either case, the key
# in any case. Only the exact projection hash matches, so a looser parse cannot turn a revision green.
SHAPE_LINE_RE = re.compile(BULLET + r"[*_\s]*Shape\b.*?(?<![0-9a-fA-F])([0-9a-fA-F]{64})(?![0-9a-fA-F])", re.I)
# A row label ends at the first LABEL_CUT, so the `label` rule keeps that character out of the
# shape's labels (G89).
LABEL_CUT = r"(?::|\(|\[|\s[-–—]\s)"
# THE CODE SCREEN's H1′ line, as `tools/shape.py write` writes it.
H1_LINE_RE = re.compile(r"^- H1′ (across|down|row (.+?)) \((Q[0-9]+)\): (.*?) \| flips: (.*)$")
DEPARTURE_RE = re.compile(r"^- ([a-z-]+) (C-[0-9]{3,}): \S")
VERDICT_TAIL_RE = re.compile(r"\s+(?:pass|fail)$")


def label_key(text):
    """A row label as the H1′ check compares it: every run of non-word characters (emphasis,
    quotes, commas, hyphens) one space, collapsed and casefolded, with a trailing verdict word
    dropped, so `“Maker deal”, PASS` and `maker-deal` are `maker deal`."""
    key = re.sub(r"[\W_]+", " ", text).strip().casefold()
    return VERDICT_TAIL_RE.sub("", key).strip()


_RANK = []


def rank():
    """`tools/rank.py`, for `known_fn`: KNOWN decided as the lock decides it. Loaded on first call."""
    if not _RANK:
        sys.dont_write_bytecode = True
        spec = importlib.util.spec_from_file_location("rank", ROOT / "tools" / "rank.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _RANK.append(mod)
    return _RANK[0]


def allocation_sections(root):
    """(lines before the first `### `, {slot: its block's lines}, departures {(slot, ID)}) from
    `06-allocation.md`."""
    path = pathlib.Path(root) / "06-allocation.md"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as err:
        raise Unreadable(f"no allocation record at {path} ({err})") from err
    head, blocks, slot, section = [], {}, None, None
    departures = set()
    for line in lines:
        if line.startswith("## "):
            section = line[3:].strip()
        if line.startswith("### "):
            slot = line[4:].strip()
            blocks.setdefault(slot, [])
        elif slot is None:
            head.append(line)
            m = DEPARTURE_RE.match(line)
            if m and section == "Departures":
                departures.add((m.group(1), m.group(2)))
        else:
            blocks[slot].append(line)
    return head, blocks, departures


def screened_reds(root):
    """THE CODE SCREEN: (rule, detail) pairs for the shape and its record as they stand, and the
    SHAPE HASH it screened."""
    _, smap, matrix = read_shape(root)
    now = shape_hash(root)
    head, blocks, departures = allocation_sections(root)
    reds = []
    shas = [m.group(1).lower() for line in head for m in [SHAPE_LINE_RE.match(line)] if m]
    if not shas:
        reds.append(("screened", "06-allocation.md has no `Shape:` line: tools/shape.py write did not write it"))
    elif shas[0] != now:
        reds.append(("screened", f"06-allocation.md records shape {shas[0]}; the shape now is {now}: "
                                 f"a revision the record never saw, so the shape node answers again"))
    locked = questions_of(root)
    lines = {}
    for line in head:
        m = H1_LINE_RE.match(line)
        if m:
            key = m.group(1) if m.group(2) is None else ("row", label_key(m.group(2)))
            lines.setdefault(key, (m.group(3), m.group(4).strip(), m.group(5).strip()))
    items = [(axis, f"the {axis} axis", smap[axis]["serves"]) for axis in ("across", "down")]
    items += [(("row", label_key(str(r["label"]))), f"row {r['label']!r}", r["serves"]) for r in matrix["rows"]]
    for key, what, serves in items:
        got = lines.get(key)
        if got is None:
            reds.append(("decision", f"{what}: no `H1′` line in 06-allocation.md names the decision it changes"))
        elif got[0] != serves or serves not in locked:
            reds.append(("decision", f"{what} serves {serves!r} and its H1′ line names {got[0]}; the locked "
                                     f"questions are {', '.join(sorted(locked))}"))
        elif not got[1] or not got[2]:
            reds.append(("decision", f"{what}: its H1′ line names no " + ("decision" if not got[1] else "flip")))
    claims = read_claims(root)
    reader = pathlib.Path(root) / "reader.json"
    known = rank().known_fn(load_json(reader) if reader.is_file() else {}, claims)
    for slot in WEB_FIELDS:
        clauses = [CLAIM_ID.findall(line) for line in blocks.get(slot, []) if line.startswith(CLAIM_LINES["evidence"])]
        clauses = [ids for ids in clauses if ids]
        if not clauses:
            reds.append(("evidence", f"{slot}: no `- Evidence clause` line names a claim ID, so the slot "
                                     f"carries no fact the screen can grade"))
        for ids in clauses:
            if known(ids[0]) and (slot, ids[0]) not in departures:
                reds.append(("known", f"{slot}: the evidence clause leads with {ids[0]}, a row the founder "
                                      f"already holds; lead with a row new to him, or name it under "
                                      f"§ Departures with the reason"))
    return reds, now


def web_allocation_reds(root):
    """(rule, detail) pairs for the page's allocation before any prose: WEB MODE."""
    caps = web_caps()
    budget, (company, smap, matrix) = read_web_budget(root, caps), read_shape(root)
    fields = field_caps()
    locked = locked_questions(root)
    cohort = sorted(p.name[5:-3] for p in pathlib.Path(root).glob("comp-*.md"))
    if not cohort:
        raise Unreadable(f"{root}: no comp-<slug>.md, so no cohort")
    reds = []
    for slot, (words, items) in budget.items():
        if words > caps[slot][0] or items > caps[slot][1]:
            reds.append(("cap", f"{slot}: {words} words and {items} items against the schema's "
                                f"{caps[slot][0]} and {caps[slot][1]}"))
    for slot, have in (("matrix", len(matrix["rows"])), ("map", len(smap["answers"]))):
        if have > budget[slot][1]:
            reds.append(("cap", f"{slot}: {have} in the shape against {budget[slot][1]} items budgeted"))
    named = [(f"{axis} {f}", f, str(smap[axis][f])) for axis in ("across", "down") for f in ("question", "yes", "no")]
    named += [(f"row {row['label']!r} label", "label", str(row["label"])) for row in matrix["rows"]]
    for where, f, text in named:
        if len(text.split()) > fields[f]:
            reds.append(("cap", f"{where}: {len(text.split())} words against the schema's {fields[f]}"))
    if company not in cohort:
        reds.append(("cohort", f"company {company!r} has no comp-<slug>.md in {cohort}"))
    listed = (("columns", list(matrix["columns"])), ("answers", [e["company"] for e in smap["answers"]]))
    for what, slugs in listed:
        if sorted(slugs) != cohort:
            reds.append(("cohort", f"{what} {slugs} are not the cohort {cohort}, once each"))
    if matrix["columns"][:1] != [company]:
        reds.append(("cohort", f"columns open with {matrix['columns'][:1]}, not the hiring company {company!r}"))
    by_co = {entry["company"]: entry for entry in smap["answers"]}
    claims = read_claims(root)
    for axis in ("across", "down"):
        for co in cohort:
            an = by_co.get(co, {}).get(axis, {})
            if an.get("answer") not in ("yes", "no") or not an.get("c"):
                reds.append(("answer", f"{co} has no yes or no with a claim ID on {axis}: {an or 'no entry'}"))
            elif an["answer"] == "yes" and an.get("integration"):
                reds.append(("answer", f"{co} lists integration {an['integration']} under a yes on {axis}; "
                                       f"INTEG belongs under a no only"))
            elif an["answer"] == "yes" and not brief_check().carries_yes([claims[c] for c in an["c"] if c in claims]):
                reds.append(("answer", f"{co} rests a yes on {axis} on {an['c']}: an integration, or pilots only, "
                                       f"names no customer, so the answer is no (G92 (i))"))
        given = {by_co[co][axis]["answer"] for co in cohort if co in by_co}
        if len(given) < 2:
            reds.append(("split", f"every company answers {sorted(given)} on {axis}, so it places nobody apart"))
    for row in matrix["rows"]:
        if row["serves"] not in locked:
            reds.append(("question", f"row {row['label']!r} serves {row['serves']!r}, not one of {sorted(locked)}"))
        unknown = sum(cell == "Unknown" for cell in row["cells"])
        if unknown > UNKNOWN_MAX:
            reds.append(("unknown", f"row {row['label']!r} has {unknown} Unknown cells, over {UNKNOWN_MAX}"))
        if re.search(LABEL_CUT, str(row["label"])):
            reds.append(("label", f"row {row['label']!r} carries ':', '(', '[' or a spaced dash, where a "
                                  f"`H1′ row` line's label ends; two words never need one"))
    cited = []
    for entry in smap["answers"]:
        for axis in ("across", "down"):
            an, where = entry[axis], f"{entry['company']} {axis}"
            cs = ids_of(an["c"], where + " c")
            cited += [(where, cid) for cid in cs]
            name = an.get("name")
            for cid in cs if name else []:
                if cid in claims and name not in str(claims[cid].get("claim", "")):
                    reds.append(("name", f"{where}: the name {name!r} is not verbatim in {cid}'s claim"))
            for cid in an["integration"]:  # G76: the page's own test, `web.py`'s 36 R3
                row = claims.get(cid)
                if not row:
                    continue  # the url rule reds an ID with no row
                quoted, says = brief_check().shows_quote(row), "integration" in str(row.get("claim", ""))
                if not (quoted and says):
                    reds.append(("integration", f"{where}: {cid} is listed, but the page "
                                 f"{'quotes' if quoted else 'glosses'} it and its claim "
                                 f"{'says' if says else 'lacks'} \"integration\"; list only a quoted row whose claim says it"))
    for row in matrix["rows"]:
        for col, cell in zip(matrix["columns"], row["cells"]):
            if cell != "Unknown":
                cited += [(f"row {row['label']!r} {col}", cid) for cid in ids_of(cell, "cell")]
    cited += [(f"slot {slot}", cid) for slot, cid in allocation_claims(root)]
    cited += [(f"slot {slot} evidence clause", cid) for slot, cid in allocation_claims(root, ("evidence",))]
    for where, cid in cited:
        if not str(claims.get(cid, {}).get("url", "")).strip():
            reds.append(("url", f"{where}: {cid} " + ("has no claims.jsonl row" if cid not in claims
                                                      else "has no url, so its card has no source")))
    cells = [(f"row {row['label']!r} {col}", cell) for row in matrix["rows"]
             for col, cell in zip(matrix["columns"], row["cells"]) if cell != "Unknown"]
    # The ceilings also count each `- ICP` line's IDs: A1 lets the quick take cite them (G95, Rec 3).
    page = [cid for _, cid in cited] + [cid for _, cid in allocation_claims(root, ("icp",))]
    return reds + sources_reds(cells, page, claims)


def sources_reds(cells, cited, claims):
    """THE SOURCES CEILINGS (G92 (ii)): `cells` as (where, IDs), `cited` every ID the page will
    cite, `claims` the ledger by ID. An ID with no row is the url rule's, so it counts as an ID
    and adds no URL or card words. A card shows a row's quote when brief-check's `shows_quote`
    says the page quotes it, else its gloss, plus CARD_ID_WORDS for its label, host and date.
    The ID and card-word reds list every cited ID with its card words, heaviest first, so one
    pass can choose the cuts (G95, Rec 2)."""
    reds = [("sources", f"{where}: {len(set(cell))} claim IDs, over {CELL_IDS_MAX} a cell")
            for where, cell in cells if len(set(cell)) > CELL_IDS_MAX]
    ids, rows = set(cited), [claims[cid] for cid in sorted(set(cited)) if cid in claims]
    urls = {str(r.get("url", "")).strip() for r in rows} - {""}
    card = {cid: len(str(r.get("quote") if brief_check().shows_quote(r) else r.get("gloss") or "").split())
            + CARD_ID_WORDS for cid, r in ((cid, claims[cid]) for cid in ids if cid in claims)}
    words = sum(card.values())
    heaviest = ", ".join(f"{cid} {card.get(cid, 0)}" for cid in sorted(ids, key=lambda c: (-card.get(c, 0), c)))
    for what, have, cap, listed in (("distinct claim IDs", len(ids), PAGE_IDS_MAX, True),
                                    ("distinct source URLs", len(urls), PAGE_URLS_MAX, False),
                                    ("card words", words, CARD_WORDS_MAX, True)):
        if have > cap:
            reds.append(("sources", f"the page cites {have} {what}, over {cap}; cut the weakest "
                                    f"sources (G92 (ii))" + (f". Card words by ID: {heaviest}" if listed else "")))
    return reds


def build_log_reds(log, root):
    """(rule, detail) pairs for one build's gate log against the budget."""
    budget = read_budget(root)
    try:
        text = pathlib.Path(log).read_text(encoding="utf-8")
    except OSError as err:
        raise Unreadable(f"no build log at {log} ({err})") from err
    lines = [line for line in text.splitlines() if line.startswith("heights ->")]
    if len(lines) != 1:
        return [("heights", f"want one `heights ->` line in {log}, got {len(lines)}")]
    got = figures(lines[0])
    reds = []
    absent = [slot for slot, cm in got.items() if cm == "absent"]
    if absent:
        reds.append(("absent", f"slot(s) {absent} did not render"))
    for slot in sorted(set(budget) | set(got)):
        cm, limit = got.get(slot), round(budget.get(slot, 0) + TOLERANCE_CM, 2)
        if cm is None or slot not in budget or (cm != "absent" and cm > limit):
            shown = "no figure" if cm is None else f"{cm}cm"
            reds.append(("over", f"{slot}: {shown} against a limit of {limit}cm "
                                 f"(budget {budget.get(slot, 'none')})"))
    count, most = pages_of(text, log), page_limit()
    if count > most:
        stranded = stranded_red(got, pages_line(text, log, "gaps"), pages_line(text, log, "opens"),
                                count - most)
        # A slot truly over its row outranks a strand: the strand may already stand in the
        # budgeted layout, which fitted (P14b-verify-2 Required 1). So the strand is the cause
        # only when no `over` red stands, and the next build names it if the cuts leave it.
        if stranded and not any(rule == "over" for rule, _ in reds):
            reds.append(("stranded", stranded))
            reds.append(("pages", f"{count} pages, over GATE 3's {most}; the cause is the space "
                                  f"stranded at a page break, named by `stranded` above"))
            return reds
        grown = sorted(((round(cm - budget[s], 2), s) for s, cm in got.items()
                        if s in budget and cm != "absent" and round(cm - budget[s], 2) > 0),
                       key=lambda pair: -pair[0])
        named = ", ".join(f"{s} +{d:.1f}cm" for d, s in grown) or "no slot is over its row"
        reds.append(("pages", f"{count} pages, over GATE 3's {most}; over their rows: {named}"))
    return reds


def pages_line(text, log, name):
    """{page: value} from the log's one `gaps ->` (cm) or `opens ->` (slot) line."""
    found = [line.split("->", 1)[1].split() for line in text.splitlines()
             if line.startswith(name + " ") and "->" in line]
    if len(found) != 1:
        raise Unreadable(f"want one `{name} ->` line in {log}, got {len(found)}")
    out = {}
    for token in found[0]:
        page, _, value = token.partition(":")
        if not (page[:1] == "p" and page[1:].isdigit() and value):
            raise Unreadable(f"{name} -> token {token!r} is not pN:value")
        out[int(page[1:])] = float(value.removesuffix("cm")) if name == "gaps" else value
    return out


def stranded_red(got, gaps, opens, over_by=1):
    """The `stranded` detail, or None when no page but the last strands over STRAND_CM.
    Each strand is an ALTERNATIVE: pulling back any one section returns its page, so the
    strands are listed smallest cut first and joined by `or` (P14b-verify-2 Required 2)."""
    last = max(gaps)
    named = []
    for page, gap in sorted(gaps.items()):
        if page == last or gap <= STRAND_CM:
            continue
        slot = opens.get(page + 1, "-")
        cm = got.get(slot)
        if isinstance(cm, float):
            cut = max(round(cm - gap + BREAK_CM, 1), 0.1)
            named.append((cut, f"cut about {cut}cm from {slot} or from p{page} above it: p{page} "
                               f"strands {gap}cm and {slot} ({cm}cm) moved to p{page + 1}"))
        else:
            named.append((math.inf, f"p{page} strands {gap}cm before p{page + 1}, opened by "
                                    f"{slot}"))
    if not named:
        return None
    named.sort(key=lambda pair: pair[0])
    lead = ("any one of these returns the page, smallest cut first; rebuild after the first"
            if over_by == 1 else f"{over_by} pages over, and each of these returns at most one, "
            f"smallest cut first; rebuild after each")
    return f"{lead}: " + "; or ".join(text for _, text in named)


def pages_of(text, log):
    """The page count from the log's one `pages ->` line, GATE 3's own print."""
    found = [line.split("->", 1)[1].strip() for line in text.splitlines()
             if line.startswith("pages ->")]
    if len(found) != 1 or not found[0].isdigit():
        raise Unreadable(f"want one `pages -> N` line in {log}, got {found}")
    return int(found[0])


def page_limit():
    """GATE 3's limit, read from `build/build.py`'s own comparison so the number is written once."""
    try:
        text = BUILD_PY.read_text(encoding="utf-8")
    except OSError as err:
        raise Unreadable(f"GATE 3's page limit is unreadable: {err}") from err
    found = re.findall(r"^ +if doc\.page_count > (\d+):$", text, re.M)
    if len(found) != 1:
        raise Unreadable(f"{BUILD_PY}: want one `if doc.page_count > N:` (GATE 3), got {found}")
    return int(found[0])


def space(mode, reds_of, *args):
    try:
        reds = reds_of(*args)
    except Unreadable as err:
        print(f"budget-check: --{mode}: {err}", file=sys.stderr)
        return 2
    for rule, detail in reds:
        print(f"RED {rule}: {detail}")
    if reds:
        print(f"BUDGET-CHECK FAIL (--{mode}: {len(reds)} red)")
        return 1
    print(f"BUDGET-CHECK OK (--{mode}: {sum(read_budget(args[-1]).values()):.1f}cm budgeted)")
    return 0


def web(root):
    try:
        reds = web_allocation_reds(root)
    except Unreadable as err:
        print(f"budget-check: --allocation --web: {err}", file=sys.stderr)
        return 2
    for rule, detail in reds:
        print(f"RED {rule}: {detail}")
    if reds:
        print(f"BUDGET-CHECK FAIL (--allocation --web: {len(reds)} red)")
        return 1
    print(f"BUDGET-CHECK OK (--allocation --web: {len(WEB_FIELDS)} slots within the schema's caps)")
    return 0


def shape_hash_cli(root):
    """`--shape-hash`: the `Shape:` line `tools/shape.py write` stamps into 06-allocation.md (G80)."""
    try:
        print(f"Shape: {shape_hash(root)}")
    except Unreadable as err:
        print(f"budget-check: --shape-hash: {err}", file=sys.stderr)
        return 2
    return 0


def screened(root):
    try:
        reds, sha = screened_reds(root)
    except Unreadable as err:
        print(f"budget-check: --screened: {err}", file=sys.stderr)
        return 2
    for rule, detail in reds:
        print(f"RED {rule}: {detail}")
    if reds:
        print(f"BUDGET-CHECK FAIL (--screened: {len(reds)} red)")
        return 1
    print(f"BUDGET-CHECK OK (--screened: the code screen passes shape {sha[:12]})")
    return 0


# One case per rule: (label, fixture file, old text, new text, the one rule it must red).
CASES = (
    ("no opening ---", "01-plain.md", "---\nstage:", "stage:", "frontmatter"),
    ("model deleted", "01-plain.md", "model: opus\n", "", "model"),
    ("model: haiku", "01-plain.md", "model: opus", "model: haiku", "model"),
    ("max_turns deleted", "01-plain.md", "max_turns: 15\n", "", "max_turns"),
    ("max_turns not an integer", "03-dispatch.md", "max_turns: 30", "max_turns: thirty", "max_turns"),
    ("max_turns:30, no space", "03-dispatch.md", "max_turns: 30", "max_turns:30", "max_turns"),
    ("name: TBD", "03-dispatch.md", "name: dispatch", "name: TBD", "TBD"),
    ("--- with a trailing space", "01-plain.md", "---\nstage:", "--- \nstage:", "frontmatter"),
    ("closing --- with a trailing space", "01-plain.md", "\n---\n\n", "\n--- \n\n", "frontmatter"),
    ("CR on the max_turns line", "01-plain.md", "max_turns: 15\n", "max_turns: 15\r\n", "crlf"),
    ("nested cap not an integer", "03-dispatch.md", "nested_max_turns: 20", "nested_max_turns: twenty",
     "nested_max_turns"),
    ("nested_max_turns:20, no space", "03-dispatch.md", "nested_max_turns: 20", "nested_max_turns:20",
     "nested_max_turns"),
    ("effort: max", "01-plain.md", "max_turns: 15\n", "max_turns: 15\neffort: max\n", "effort"),
    ("nested regen at max", "01-plain.md", "max_turns: 15\n",
     "max_turns: 15\neffort: high\nnodes:\n  - node: x\n    regen: {exit: 3, node: y, effort: max}\n", "effort"),
)


# Space mode, one edit to the space fixture per case: (label, file, old, new, mode, the rules it
# must red). An empty tuple is a boundary that must stay green.
SPACE_CASES = (
    ("slot only in the record", "06-budget.tsv", "matrix\t11.2\n", "", "allocation", ("join",)),
    ("slot only in the budget", "06-budget.tsv", "sources\t7.9\n", "sources\t6.9\nextra\t1.0\n",
     "allocation", ("join",)),
    ("total 86.9cm", "06-budget.tsv", "quick-take\t9.9", "quick-take\t10.0", "allocation",
     ("capacity",)),
    ("five-page build, 12 words added: 88.7cm (P12-verify R1)", "06-budget.tsv", "quick-take\t9.9",
     "quick-take\t11.8", "allocation", ("capacity",)),
    ("heights line deleted", "gate-01.txt", "heights -> ", "", "build-log", ("heights",)),
    ("heights line twice", "gate-01.txt", "\n\nGATE", "\nheights -> sources:7.9cm\n\nGATE",
     "build-log", ("heights",)),
    ("slot absent", "gate-01.txt", "open-questions:3.5cm", "open-questions:absent", "build-log",
     ("absent",)),
    ("matrix 0.6cm over", "gate-01.txt", "matrix:11.2cm", "matrix:11.8cm", "build-log", ("over",)),
    ("matrix 0.5cm over, at tolerance", "gate-01.txt", "matrix:11.2cm", "matrix:11.7cm",
     "build-log", ()),
    ("untouched what-changed drifts 0.4cm (P12-verify R3)", "gate-01.txt", "what-changed:12.8cm",
     "what-changed:13.2cm", "build-log", ()),
    ("sources 0.5cm over, at tolerance", "gate-01.txt", "sources:7.9cm", "sources:8.4cm",
     "build-log", ()),
    ("sources 0.6cm over: no second colophon allowance", "gate-01.txt", "sources:7.9cm",
     "sources:8.5cm", "build-log", ("over",)),
    # The real five-page build of P12-build.md Fix 1: quick-take grew 0.6cm, and matrix and
    # open-questions, untouched, drifted 0.3cm each. Only quick-take is over.
    ("five-page build log (P12-build Fix 1)", "gate-01.txt",
     ("pages -> 4", "quick-take:9.9cm recommendations:9.4cm what-changed:12.8cm "
      "threat-landscape:7.7cm open-questions:3.5cm say-do:9.3cm matrix:11.2cm"),
     ("pages -> 5", "quick-take:10.5cm recommendations:9.3cm what-changed:12.8cm "
      "threat-landscape:7.7cm open-questions:3.8cm say-do:9.3cm matrix:11.5cm"),
     "build-log", ("over", "pages")),
    ("budget row with no figure", "gate-01.txt", " matrix:11.2cm", "", "build-log", ("over",)),
    # GATE 3's line, `pages`. Growth on the last page can make five pages inside every tolerance.
    ("five pages, coverage-notes 0.5cm over: 87.3cm (P12-verify-2 R1)", "gate-01.txt",
     ("pages -> 4", "coverage-notes:6.2cm"), ("pages -> 5", "coverage-notes:6.7cm"), "build-log",
     ("pages",)),
    ("four pages, coverage-notes 0.5cm over", "gate-01.txt", "coverage-notes:6.2cm",
     "coverage-notes:6.7cm", "build-log", ()),
    ("five pages, sources 0.4cm over, matrix 0.1cm (P12-verify-2 R1)", "gate-01.txt",
     ("pages -> 4", "matrix:11.2cm", "sources:7.9cm"),
     ("pages -> 5", "matrix:11.3cm", "sources:8.3cm"), "build-log", ("pages",)),
    ("five pages, no slot over its row", "gate-01.txt", "pages -> 4", "pages -> 5", "build-log",
     ("pages",)),
    # THE STRANDED SPACE. The budget is exactly 86.8cm, coverage-notes is 0.5cm over, inside its
    # tolerance, and the matrix, held whole, left 9.1cm on p2 (P14b-verify.md Required 1).
    ("five pages at 86.8cm, matrix held whole strands 9.1cm (P14b-verify R1)", "gate-01.txt",
     ("pages -> 4", "p2:1.9cm p3:2.3cm p4:1.5cm", "coverage-notes:6.2cm",
      "p3:open-questions p4:stage-reach"),
     ("pages -> 5", "p2:9.1cm p3:1.3cm p4:8.6cm p5:15.0cm", "coverage-notes:6.7cm",
      "p3:matrix p4:stage-reach p5:sources"), "build-log", ("stranded", "pages")),
    # A slot truly over outranks the strand the budgeted layout may already carry
    # (P14b-verify-2 Required 1): coverage-notes 2.0cm over, the same 9.1cm strand on p2.
    ("a 9.1cm strand and coverage-notes 2.0cm over, five pages", "gate-01.txt",
     ("pages -> 4", "p2:1.9cm p3:2.3cm p4:1.5cm", "coverage-notes:6.2cm",
      "p3:open-questions p4:stage-reach"),
     ("pages -> 5", "p2:9.1cm p3:1.3cm p4:8.6cm p5:15.0cm", "coverage-notes:8.2cm",
      "p3:matrix p4:stage-reach p5:sources"), "build-log", ("over", "pages")),
    ("four pages, matrix held whole strands 9.1cm", "gate-01.txt",
     ("p2:1.9cm p3:2.3cm", "p3:open-questions"), ("p2:9.1cm p3:1.3cm", "p3:matrix"),
     "build-log", ()),
    ("a stage-7 re-budget note is skipped", "06-budget.tsv", "matrix\t11.2\n",
     "# stage 7: matrix 10.7 -> 11.2, measured 10.7 + 0.5\nmatrix\t11.2\n", "allocation", ()),
)


# Web mode, one edit to the web fixture per case: (label, file, old, new, the rules it must red).
# "unreadable" is exit 2. An empty tuple is a boundary that must stay green.
ACROSS_YES = ('"yes", "name": "Flexibility Register", "c": ["C-002"]',
              '"yes", "name": "Flexibility Register", "c": ["C-004"]',
              '"yes", "name": "Flexibility Register", "c": ["C-013"]')
HEATWELL_YES = '"down": {"answer": "yes", "name": "Heatwell", "c": ["C-003"]'  # the base's one yes on C-003
WEB_CASES = (
    ("matrix words one over the cap", "06-budget.tsv", "matrix\t160", "matrix\t273", ("cap",)),
    ("matrix words at the cap", "06-budget.tsv", "matrix\t160", "matrix\t272", ()),
    ("open-questions items one over the cap", "06-budget.tsv", "open-questions\t50\t2",
     "open-questions\t50\t3", ("cap",)),
    ("a budget row with no words", "06-budget.tsv", "map\t36", "map\t0", ("unreadable",)),
    ("a web slot with no budget row", "06-budget.tsv", "map\t36\t7\n", "", ("unreadable",)),
    ("a company with no answer on either axis", "06-shape.json", '{"company": "zephyr"',
     '{"company": "zephyr-gone"', ("cohort", "answer", "answer")),
    ("an answer that is neither yes nor no", "06-shape.json",
     '"down": {"answer": "no", "name": null, "c": ["C-016"]',
     '"down": {"answer": "maybe", "name": null, "c": ["C-016"]', ("answer",)),
    ("an answer with no claim ID", "06-shape.json", '"c": ["C-016"], "integration": []',
     '"c": [], "integration": []', ("answer",)),
    ("every company answers no across", "06-shape.json", ACROSS_YES,
     tuple(old.replace('"yes"', '"no"') for old in ACROSS_YES), ("split",)),
    ("a row serving no locked question", "06-shape.json", '"serves": "Q3"', '"serves": "Q7"',
     ("question",)),
    ("a row's question killed in 02-questions.md", "02-questions.md", "### Q3. ", "- Q3. ",
     ("question",)),
    ("two Unknown cells in a row", "06-shape.json", '["C-001"], ["C-004"], ["C-006"], "Unknown"',
     '["C-001"], "Unknown", ["C-006"], "Unknown"', ("unknown",)),
    ("an integration claim under a yes", "06-shape.json", '"c": ["C-003"], "integration": []',
     '"c": ["C-003"], "integration": ["C-003"]', ("answer", "integration")),
    # G76: a listed row must be one the page quotes, and its claim must say integration.
    ("an integration claim within its answer, glossed and silent", "06-shape.json",
     '"c": ["C-005"], "integration": []', '"c": ["C-005"], "integration": ["C-005"]', ("integration",)),
    ("a listed row the page glosses, its claim saying integration", "06-shape.json",
     '"c": ["C-005"], "integration": []', '"c": ["C-005", "C-020"], "integration": ["C-020"]',
     ("integration",)),
    ("a listed row the page quotes, its claim saying integration", "06-shape.json",
     '"c": ["C-005"], "integration": []', '"c": ["C-005", "C-019"], "integration": ["C-019"]', ()),
    ("an integration claim outside its answer", "06-shape.json", '"c": ["C-005"], "integration": []',
     '"c": ["C-005"], "integration": ["C-099"]', ("unreadable",)),
    ("no integration field (G10)", "06-shape.json", '"c": ["C-005"], "integration": []',
     '"c": ["C-005"]', ("unreadable",)),
    ("a row one cell short", "06-shape.json", ', ["C-013"], ["C-017"]]}\n  ]', ', ["C-017"]]}\n  ]',
     ("unreadable",)),
    ("a cell that is neither IDs nor Unknown", "06-shape.json", '"Unknown"', '"unknown"', ("unreadable",)),
    ("no locked question at all", "02-questions.md", "### Q", "#### Q", ("unreadable",)),
    # W14-verify Recommended 1: the shape's own caps and its cohort, each red alone.
    ("more matrix rows than budgeted", "06-budget.tsv", "matrix\t160\t4", "matrix\t160\t3", ("cap",)),
    ("more map answers than budgeted", "06-budget.tsv", "map\t36\t7", "map\t36\t6", ("cap",)),
    ("an axis question over 9 words", "06-shape.json", '"question": "does it name a maker as a customer"',
     '"question": "does it name a maker or a carmaker as a paying customer"', ("cap",)),
    ("an axis question at 9 words", "06-shape.json", '"question": "does it name a maker as a customer"',
     '"question": "does it name a maker as a paying customer"', ()),
    ("a yes header over 6 words", "06-shape.json", '"yes": "Names a maker"',
     '"yes": "Names a maker as a paying customer"', ("cap",)),
    ("a no header over 6 words", "06-shape.json", '"no": "Names no maker"',
     '"no": "Names no maker as a paying customer"', ("cap",)),
    ("a row label over 2 words", "06-shape.json", '"label": "Who pays"', '"label": "Who pays them"',
     ("cap",)),
    ("columns missing a company, another twice", "06-shape.json", ', "mistral", "lumen"]', ', "lumen", "lumen"]',
     ("cohort",)),
    ("columns naming a company outside the cohort", "06-shape.json", ', "mistral", "lumen"]',
     ', "mistral-sa", "lumen"]', ("cohort",)),
    ("the hiring company not first in columns", "06-shape.json", '["coopelec", "brightwater",',
     '["brightwater", "coopelec",', ("cohort",)),
    ("an eighth answer outside the cohort", "06-shape.json", '   {"company": "brightwater",',
     '   {"company": "nobody", "across": {"answer": "no", "name": null, "c": ["C-005"], "integration": []},'
     ' "down": {"answer": "no", "name": null, "c": ["C-005"], "integration": []}},\n   {"company": "brightwater",',
     ("cap", "cohort")),
    ("a hiring company outside the cohort", "06-shape.json", '"company": "coopelec",',
     '"company": "coopelec-sa",', ("cohort", "cohort")),
    ("no hiring company named", "06-shape.json", ' "company": "coopelec",\n', "", ("unreadable",)),
    # G32: the two ledger checks, each red alone.
    ("a yes name in no cited claim", "06-shape.json", '"yes", "name": "Flexibility Register", "c": ["C-002"]',
     '"yes", "name": "Grid Register", "c": ["C-002"]', ("name",)),
    ("a cited row with no url, in a cell, a slot and its evidence clause", "claims.jsonl",
     '"url": "https://zephyr.example/news/installers"', '"url": ""', ("url", "url", "url")),
    ("a cited ID with no ledger row", "06-shape.json", '["C-001"], ["C-004"], ["C-006"], "Unknown"',
     '["C-001"], ["C-099"], ["C-006"], "Unknown"', ("url",)),
    ("no claims.jsonl", "claims.jsonl", None, None, ("unreadable",)),
    # W15-verify-2: each half of the two ledger rules red alone (G39).
    ("a yes name in its first cited claim, not its second", "06-shape.json",
     '"yes", "name": "Flexibility Register", "c": ["C-002"]', '"yes", "name": "Flexibility Register", "c": ["C-002", "C-001"]',
     ("name",)),
    ("a map-only ID with no url", "claims.jsonl", '"id": "C-015", "subject": "Øresund Flex", "claim": "The Flexibility Register names no Øresund Flex lead party.", "qualifier": "company-stated, as of 2026-10-01", "scope": "1 page read", "metric": "Øresund Flex:fixture", "quote": "", "url": "https://register.example/lead-parties"', '"id": "C-015", "subject": "Øresund Flex", "claim": "The Flexibility Register names no Øresund Flex lead party.", "qualifier": "company-stated, as of 2026-10-01", "scope": "1 page read", "metric": "Øresund Flex:fixture", "quote": "", "url": ""', ("url",)),
    ("a slot claim ID with no ledger row", "06-allocation.md", "- Claims: OQ1 C-011", "- Claims: OQ1 C-011, C-099",
     ("url",)),
    ("no 06-allocation.md", "06-allocation.md", None, None, ("unreadable",)),
    # W15-verify-3 Recommended 2 (G42): an evidence clause is read by slot, its ID mid-line; the
    # Dropped row and Qualifiers lines are not.
    ("an evidence-clause ID with no ledger row, mid-line", "06-allocation.md", "- Claims: OQ1 C-011",
     "- Claims: OQ1 C-011\n- Evidence clause (OQ1): C-011 with C-099, from its own page (C-011)", ("url",)),
    ("Dropped row and Qualifiers lines are not read", "06-allocation.md", "- Claims: OQ1 C-011",
     "- Claims: OQ1 C-011\n- Dropped row: C-099\n- Qualifiers to carry into cells: C-098", ()),
    # G89: a label character where an `H1′ row` line's label ends.
    ("a shape label with a bracket", "06-shape.json", '"label": "Who pays"', '"label": "Fleet (B2B)"', ("label",)),
    ("a shape label with a colon", "06-shape.json", '"label": "Who pays"', '"label": "Q3: fleet"', ("label",)),
    ("a shape label with a spaced dash", "06-shape.json", '"label": "Who pays"', '"label": "Pay — go"',
     ("cap", "label")),
    # G92 (i): a yes rests on no integration, and not on pilots alone. C-019's claim says
    # integration; C-021 is a pilot by its qualifier, C-022 by its claim ("Pilot homes").
    ("a yes on a customer and an integration", "06-shape.json", HEATWELL_YES, HEATWELL_YES.replace(
        '["C-003"]', '["C-003", "C-019"]'), ("answer",)),
    ("a yes on a pilot alone, by its qualifier", "06-shape.json", HEATWELL_YES,
     HEATWELL_YES.replace("C-003", "C-021"), ("answer",)),
    ("a yes on a customer and a pilot", "06-shape.json", HEATWELL_YES, HEATWELL_YES.replace(
        '["C-003"]', '["C-003", "C-021"]'), ()),
    ("a yes on a pilot alone, by its capitalised claim", "06-shape.json", HEATWELL_YES,
     HEATWELL_YES.replace("C-003", "C-022"), ("answer",)),
    ("a yes on an ID with no ledger row is the url rule's", "06-shape.json", HEATWELL_YES,
     HEATWELL_YES.replace("C-003", "C-099"), ("url",)),
    ("Autopilot is no pilot", "claims.jsonl", "as its heat-pump partner.",
     "as its heat-pump partner on its Autopilot tariff.", ()),
    ("integrated is not integration", "claims.jsonl", "as its heat-pump partner.",
     "as its heat-pump partner, integrated with its app.", ()),
    # G95 (Nice 1): the quote is not read, so a French "pilotons" (we control) is no pilot.
    ("a quote saying pilotons is no pilot", "claims.jsonl", '"quote": "Heatwell, our heat-pump partner"',
     '"quote": "Heatwell, our heat-pump partner; nous pilotons"', ()),
    # G92 (ii): a cell's distinct IDs; the page ceilings are CEILING_CASES below.
    ("a cell given 3 IDs", "06-shape.json", '"cells": [["C-001"], ["C-005"]',
     '"cells": [["C-001", "C-002", "C-003"], ["C-005"]', ("sources",)),
    ("a cell naming one ID twice is 2 IDs", "06-shape.json", '"cells": [["C-001"], ["C-005"]',
     '"cells": [["C-001", "C-001", "C-002"], ["C-005"]', ()),
)
# G92 (ii), each page ceiling patched to the fixture's own count (green) and one under it (red):
# (label, constant, value, file, old, new, the rules it must red); file None is the fixture as is.
CEILING_CASES = (
    ("distinct IDs at the fixture's 18", "PAGE_IDS_MAX", 18, None, None, None, ()),
    ("distinct IDs one under", "PAGE_IDS_MAX", 17, None, None, None, ("sources",)),
    ("distinct URLs at the fixture's 12", "PAGE_URLS_MAX", 12, None, None, None, ()),
    ("distinct URLs one under", "PAGE_URLS_MAX", 11, None, None, None, ("sources",)),
    ("card words at the fixture's 265", "CARD_WORDS_MAX", 265, None, None, None, ()),
    ("card words one under", "CARD_WORDS_MAX", 264, None, None, None, ("sources",)),
    ("an emptied url is no URL", "PAGE_URLS_MAX", 11, "claims.jsonl",
     '"url": "https://zephyr.example/news/installers"', '"url": ""', ("url", "url", "url")),
    ("an ID with no ledger row still counts", "PAGE_IDS_MAX", 18, "06-allocation.md",
     "- Claims: OQ1 C-011", "- Claims: OQ1 C-011, C-099", ("url", "sources")),
    # G95 (Rec 3): an `- ICP` line's ID is one the page may cite, so it counts.
    ("an ICP line's ID counts", "PAGE_IDS_MAX", 18, "06-allocation.md",
     "- Claims: C-001, C-012 (thesis); C-002 (subordinate)",
     "- Claims: C-001, C-012 (thesis); C-002 (subordinate)\n- ICP: C-019", ("sources",)),
    # Its card words count too: C-019's quote is 5 words, plus 8, so 278 against 277.
    ("an ICP line's ID adds its card words", "CARD_WORDS_MAX", 277, "06-allocation.md",
     "- Claims: C-001, C-012 (thesis); C-002 (subordinate)",
     "- Claims: C-001, C-012 (thesis); C-002 (subordinate)\n- ICP: C-019", ("sources",)),
)
# G95 (Rec 2): the ID and card-word reds list every cited ID with its card words, heaviest first,
# ties by ID. This is the fixture's listing.
LISTING = ("Card words by ID: C-008 18, C-011 18, C-012 18, C-015 18, C-018 18, C-005 17, C-006 17, "
           "C-014 17, C-016 17, C-010 13, C-003 12, C-004 12, C-007 12, C-009 12, C-013 12, C-017 12, "
           "C-001 11, C-002 11")
G92_NUMBERS = {"CELL_IDS_MAX": 2, "PAGE_IDS_MAX": 60, "PAGE_URLS_MAX": 45, "CARD_WORDS_MAX": 1500,
               "CARD_ID_WORDS": 8}  # G92 (ii)'s ceilings as ruled (G95, Nice 2)


def _set(path, value):
    """An edit to the parsed `06-shape.json`: set the dotted `path` (list indices as digits) to
    `value`, or call `value` on the node there when it is callable."""
    def edit(shape):
        *head, last = path.split(".")
        node = shape
        for key in head:
            node = node[int(key)] if key.isdigit() else node[key]
        last = int(last) if last.isdigit() else last
        node[last] = value(node[last]) if callable(value) else value
    return edit


_H = "054ff78a82d192ebc35a941babb50c3109ab86d6e9d7843fc307f430702c88a0"  # the fixture record's Shape
_A = "06-allocation.md"
_QT_EVIDENCE = "- Evidence clause: C-001 — Coopélec runs"
_OQ_EVIDENCE = "- Evidence clause: C-011 — the Flexibility"
_KNOWN = ('"id": "C-011", ', '"id": "C-011", "known": true, ')  # Calder's register row, the founder's own
# THE CODE SCREEN, one case per edit set: (label, [(file, edit, ...)], the rules it must red). An
# edit is one or more `_set`s on `06-shape.json`, (old, new) text on another file (new may be a
# function of the case directory), None to delete the file, or ("", text) to write a new one.
# Words and order are green; a revision (G56) and each screen property red alone.
SCREENED_CASES = (
    ("an axis's question, yes and no edited", [("06-shape.json", _set("map.across.question", "is it listed"),
                                                _set("map.across.yes", "Listed"), _set("map.across.no", "Unlisted"))], ()),
    ("a yes name and the hiring company edited", [("06-shape.json", _set("map.answers.0.across.name", "Register"),
                                                   _set("company", "coopelec-sa"))], ()),
    ("rows, answers and IDs reordered", [("06-shape.json", _set("matrix.rows.2.cells.2", lambda c: c[::-1]),
                                          _set("matrix.rows", lambda r: r[::-1]),
                                          _set("map.answers", lambda a: a[::-1]))], ()),
    ("columns and their cells permuted together", [("06-shape.json", _set("matrix.columns", lambda c: c[::-1]))]
     + [("06-shape.json", _set(f"matrix.rows.{i}.cells", lambda c: c[::-1])) for i in range(4)], ()),
    # S11: the old LLM screen's files are not read: none is needed, and a FAIL one changes nothing.
    ("an old screen file, a FAIL on another shape", [("06-screen-2.md", "", "Verdict: FAIL\nShape: " + "0" * 64 + "\n")], ()),
    # screened: the record was written from another shape.
    ("an answer flipped", [("06-shape.json", _set("map.answers.3.down.answer", "yes"))], ("screened",)),
    ("an answer's claim ID changed", [("06-shape.json", _set("map.answers.3.down.c", ["C-009"]))], ("screened",)),
    ("two answers' companies swapped", [("06-shape.json", _set("map.answers.3.company", "calder"),
                                         _set("map.answers.4.company", "zephyr"))], ("screened",)),
    ("an integration ID listed", [("06-shape.json", _set("map.answers.1.down.integration", ["C-005"]))], ("screened",)),
    ("a cell's claim ID changed", [("06-shape.json", _set("matrix.rows.0.cells.0", ["C-001"]))], ("screened",)),
    ("an Unknown cell filled", [("06-shape.json", _set("matrix.rows.3.cells.3", ["C-008"]))], ("screened",)),
    ("a row dropped", [("06-shape.json", _set("matrix.rows", lambda r: r[:3]))], ("screened",)),
    ("no Shape line", [(_A, "Shape: 054f", "Shapes 054f")], ("screened",)),
    ("the file's raw sha256, G56's old form", [(_A, _H, lambda case: hashlib.sha256((case / "06-shape.json").read_bytes()).hexdigest())],
     ("screened",)),
    ("a 65-digit hex run is no hash", [(_A, _H, _H + "0")], ("screened",)),
    ("a later Shape line naming another shape", [(_A, "## Axes and rows", "Shape: " + "0" * 64 + "\n## Axes and rows")], ()),
    # decision (H1′): every axis and row names its decision and flip, on the question it serves.
    ("a row label edited in the shape alone", [("06-shape.json", _set("matrix.rows.2.label", "Who charges"))], ("decision",)),
    ("a row label edited in the shape and its H1′ line", [("06-shape.json", _set("matrix.rows.2.label", "Who charges")),
                                                          (_A, "H1′ row Who pays (", "H1′ row Who charges (")], ()),
    ("an axis serving another question", [("06-shape.json", _set("map.down.serves", "Q3"))], ("screened", "decision")),
    ("an axis and its H1′ line serving another question", [("06-shape.json", _set("map.down.serves", "Q3")),
                                                           (_A, "H1′ down (Q2)", "H1′ down (Q3)")], ("screened",)),
    ("a row serving another question", [("06-shape.json", _set("matrix.rows.3.serves", "Q2"))], ("screened", "decision")),
    ("the axes swapped", [("06-shape.json", _set("map", lambda m: {**m, "across": m["down"], "down": m["across"]}))],
     ("screened", "decision", "decision")),
    ("no H1′ line for a row", [(_A, "- H1′ row Who pays (Q3)", "- H1 row Who pays (Q3)")], ("decision",)),
    ("no H1′ line for an axis", [(_A, "- H1′ across (Q1)", "- across (Q1)")], ("decision",)),
    ("an H1′ line naming no flip", [(_A, "| flips: homes paying a rival flips it toward partners", "| flips: ")], ("decision",)),
    ("an H1′ line naming no decision", [(_A, "(Q2): which makers the client approaches first | flips: a yes",
                                         "(Q2):  | flips: a yes")], ("decision",)),
    ("Q2 killed in 02-questions.md: its axis and row", [("02-questions.md", "### Q2. ", "- Q2. ")], ("decision", "decision")),
    # evidence (H1, H2): every web slot carries its non-cuttable fact.
    ("a slot with no evidence clause", [(_A, _OQ_EVIDENCE, "- Note: C-011 — the Flexibility")], ("evidence",)),
    ("an evidence clause naming no ID", [(_A, "- Evidence clause: C-009 — Zephyr", "- Evidence clause: Zephyr")], ("evidence",)),
    # known (H2): the clause's main fact is new to the founder, or a departure names it.
    ("a lead row the founder holds", [("claims.jsonl", *_KNOWN)], ("known",)),
    ("a lead row on a known host", [("reader.json", "", '{"known_hosts": ["register.example"]}')], ("known", "known")),
    ("a held row second in the clause", [("claims.jsonl", *_KNOWN),
                                         (_A, _OQ_EVIDENCE, "- Evidence clause: C-010, C-011 — the Flexibility")], ()),
    ("a held lead a departure names", [("claims.jsonl", *_KNOWN),
                                       (_A, "## Departures\n\nNone.", "## Departures\n\n- open-questions C-011: the open question is his own")], ()),
    ("a departure in another slot", [("claims.jsonl", *_KNOWN),
                                     (_A, "## Departures\n\nNone.", "## Departures\n\n- quick-take C-011: elsewhere")], ("known",)),
    ("a departure outside § Departures", [("claims.jsonl", *_KNOWN),
                                          (_A, "## Departures", "- open-questions C-011: a stray line\n\n## Departures")], ("known",)),
    ("no 06-shape.json", [("06-shape.json", None)], ("unreadable",)),
    ("no 06-allocation.md", [(_A, None)], ("unreadable",)),
)


def web_selftest(tmp, fails):
    if web_allocation_reds(WEB):
        fails.append(f"web green base: reds {web_allocation_reds(WEB)}")
    for n, (label, name, old, new, rules) in enumerate(WEB_CASES):
        case = pathlib.Path(tmp) / f"web{n}"
        shutil.copytree(WEB, case)
        if old is None:  # the file itself removed, or each of a tuple of them
            for gone in name if isinstance(name, tuple) else (name,):
                (case / gone).unlink()
            try:
                got = tuple(rule for rule, _ in web_allocation_reds(case))
            except Unreadable:
                got = ("unreadable",)
            if got != rules:
                fails.append(f"{label}: want web reds {rules}, got {got}")
            continue
        target = case / name
        text = target.read_text(encoding="utf-8")
        edits = list(zip(old, new)) if isinstance(old, tuple) else [(old, new)]
        missing = [o for o, _ in edits if o not in text]
        if missing:
            fails.append(f"{label}: fixture {name} lacks {missing!r}")
            continue
        for o, w in edits:
            text = text.replace(o, w, 1) if name != "02-questions.md" else text.replace(o, w)
        target.write_text(text, encoding="utf-8")
        try:
            got = tuple(rule for rule, _ in web_allocation_reds(case))
        except Unreadable:
            got = ("unreadable",)
        except Exception as err:  # a deleted comparison can crash the next line; that is red too
            got = (f"raised {type(err).__name__}: {err}",)
        if got != rules:
            fails.append(f"{label}: want web reds {rules}, got {got}")
    for n, (label, const, value, name, old, new, rules) in enumerate(CEILING_CASES):
        case, kept = pathlib.Path(tmp) / f"ceiling{n}", globals()[const]
        shutil.copytree(WEB, case)
        if name:
            text = (case / name).read_text(encoding="utf-8")
            if old not in text:
                fails.append(f"{label}: fixture {name} lacks {old!r}")
                continue
            (case / name).write_text(text.replace(old, new, 1), encoding="utf-8")
        globals()[const] = value
        try:
            got = tuple(rule for rule, _ in web_allocation_reds(case))
        finally:
            globals()[const] = kept
        if got != rules:
            fails.append(f"{label}: want web reds {rules}, got {got}")
    for const in ("PAGE_IDS_MAX", "CARD_WORDS_MAX"):  # each listing red, its listing in full
        kept, globals()[const] = globals()[const], 0
        try:
            got = [d for rule, d in web_allocation_reds(WEB) if rule == "sources"]
        finally:
            globals()[const] = kept
        if len(got) != 1 or not got[0].endswith(LISTING):
            fails.append(f"{const} red: want it to end {LISTING!r}, got {got}")
    # The URL red lists nothing, and a rowless ID is listed at 0 (W18-fix12-verify-2.md Nice 2).
    case = pathlib.Path(tmp) / "listing"
    shutil.copytree(WEB, case)
    alloc = case / "06-allocation.md"
    alloc.write_text(alloc.read_text(encoding="utf-8").replace("- Claims: OQ1 C-011", "- Claims: OQ1 C-011, C-099"),
                     encoding="utf-8")
    kept = (PAGE_IDS_MAX, PAGE_URLS_MAX)
    globals()["PAGE_IDS_MAX"], globals()["PAGE_URLS_MAX"] = 0, 0
    try:
        got = [d for rule, d in web_allocation_reds(case) if rule == "sources"]
    finally:
        globals()["PAGE_IDS_MAX"], globals()["PAGE_URLS_MAX"] = kept
    if (len(got) != 2 or not got[0].endswith(LISTING + ", C-099 0")
            or not got[1].endswith("sources (G92 (ii))")):
        fails.append(f"listing: want the ID red to end with C-099 0 and the URL red unlisted, got {got}")
    got = {k: globals()[k] for k in G92_NUMBERS}
    if got != G92_NUMBERS:
        fails.append(f"G92's ceilings: want {G92_NUMBERS}, got {got}")


def screened_selftest(tmp, fails):
    base = screened_reds(WEB)
    if base != ([], _H):
        fails.append(f"screened green base: {base}")
    for n, (label, edits, rules) in enumerate(SCREENED_CASES):
        case = pathlib.Path(tmp) / f"screened{n}"
        shutil.copytree(WEB, case)
        try:
            for name, *edit in edits:
                target = case / name
                if edit == [None]:
                    target.unlink()
                elif name == "06-shape.json":
                    shape = json.loads(target.read_text(encoding="utf-8"))
                    for change in edit:
                        change(shape)
                    target.write_text(json.dumps(shape, ensure_ascii=False, indent=1), encoding="utf-8")
                elif edit[0] == "":
                    target.write_text(edit[1], encoding="utf-8")
                else:
                    old, new = edit
                    text = target.read_text(encoding="utf-8")
                    if old not in text:
                        raise LookupError(f"fixture {name} lacks {old!r}")
                    target.write_text(text.replace(old, new(case) if callable(new) else new, 1), encoding="utf-8")
            got = tuple(rule for rule, _ in screened_reds(case)[0])
        except Unreadable:
            got = ("unreadable",)
        except Exception as err:  # a broken edit or a crash in the rule is red too
            got = (f"raised {type(err).__name__}: {err}",)
        if got != rules:
            fails.append(f"{label}: want screened reds {rules}, got {got}")


def space_selftest(tmp, fails):
    base = [allocation_reds(SPACE), build_log_reds(SPACE / "gate-01.txt", SPACE)]
    if base != [[], []]:
        fails.append(f"space green base: reds {base}")
    for n, (label, name, old, new, mode, rules) in enumerate(SPACE_CASES):
        case = pathlib.Path(tmp) / f"space{n}"
        shutil.copytree(SPACE, case)
        target = case / name
        text = target.read_text()
        edits = list(zip(old, new)) if isinstance(old, tuple) else [(old, new)]
        missing = [o for o, _ in edits if o not in text]
        if missing:
            fails.append(f"{label}: fixture {name} lacks {missing!r}")
            continue
        for o, w in edits:
            text = text.replace(o, w, 1)
        target.write_text(text)
        try:
            reds = (allocation_reds(case) if mode == "allocation"
                    else build_log_reds(case / "gate-01.txt", case))
            got = tuple(rule for rule, _ in reds)
        except Exception as err:  # a deleted comparison can crash the next line; that is red too
            got = (f"raised {type(err).__name__}: {err}",)
        if got != rules:
            fails.append(f"{label}: want {mode} reds {rules}, got {got}")


# --by-question on the Globex run (2026-10-11): its stage-6 record, and its ledger and questions as
# the S2 backfill typed them, question_id included.
BYQ_ALLOCATION = ROOT / "quality-bar" / "fixtures" / "globex" / "run" / "06-allocation.md"
BYQ_LEDGER = ROOT / "tools" / "fixtures" / "schema" / "good" / "globex"
BYQ_CASES = 8


def by_question_selftest(tmp, fails):
    def root_of(name, edit=None):
        root = pathlib.Path(tmp) / name
        root.mkdir()
        shutil.copy(BYQ_ALLOCATION, root / "06-allocation.md")
        for f in ("claims.jsonl", "questions.json"):
            shutil.copy(BYQ_LEDGER / f, root / f)
        if edit:
            edit(root)
        return root

    def rows_edit(fn):
        def edit(root):
            rows = [json.loads(ln) for ln in (root / "claims.jsonl").read_text(encoding="utf-8").splitlines()]
            (root / "claims.jsonl").write_text("".join(json.dumps(r) + "\n" for r in fn(rows)), encoding="utf-8")
        return edit
    root = root_of("byq")
    alloc, reds = by_question(root)
    want = {}
    for slot, cid in allocation_claims(root, ("claims", "icp")):
        if cid not in want.setdefault(slot, []):
            want[slot].append(cid)
    got = {slot: [c for ids in a["claims"].values() for c in ids] for slot, a in alloc.items()}
    if reds or list(got) != list(want) or any(sorted(got[s]) != sorted(want[s]) for s in want):
        fails.append(f"by-question: the groups do not give back 06-allocation.md's claim sets: {reds} {got}")
    claims = read_claims(root)
    if any(claims[c].get("question_id", None) not in (None if q == NONE_Q else q,)
           for a in alloc.values() for q, ids in a["claims"].items() for c in ids):
        fails.append("by-question: an ID sits in a group other than its row's question_id")
    m = alloc.get("map", {}).get("claims", {})
    if (sorted(m) != ["Q1", "Q2"] or len(m["Q1"]) != 9 or len(m["Q2"]) != 7
            or alloc["quick-take"]["claims"].get(NONE_Q) != ["C-257", "C-019", "C-022", "C-016", "C-062"]):
        fails.append(f"by-question: map groups {dict((q, len(v)) for q, v in m.items())}, quick-take none "
                     f"{alloc.get('quick-take', {}).get('claims', {}).get(NONE_Q)}")
    late = {"id": "C-900", "question_id": "Q2", "subject": "Late Co", "claim": "x"}
    alloc, reds = by_question(root_of("late", rows_edit(lambda rows: rows + [late])))
    if reds or "C-900" not in alloc["map"]["eligible"] or "C-900" in alloc["what-changed"]["eligible"]:
        fails.append(f"by-question: a late Q2 row is not eligible for the map alone: {reds}")
    for name, edit, rule in (
            ("unknown", rows_edit(lambda rows: [r for r in rows if r["id"] != "C-099"]), "unknown"),
            ("question", rows_edit(lambda rows: [dict(r, question_id="Q9") if r["id"] == "C-081" else r
                                                 for r in rows]), "question"),
            ("unanswered", lambda root: (root / "questions.json").write_text(json.dumps({"questions": [
                {"id": q} for q in ("Q1", "Q2", "Q3", "Q4", "Q5")]})), "unanswered")):
        _, reds = by_question(root_of(name, edit))
        if not reds or {r for r, _ in reds} != {rule}:
            fails.append(f"by-question {name}: want {rule!r} reds alone, got {reds}")
    rc, out = cli("--allocation", "--by-question", root)
    if rc != 0 or '"slots"' not in out or "BUDGET-CHECK OK (--allocation --by-question: 6 slots" not in out:
        fails.append(f"cli --allocation --by-question: want exit 0 and the JSON, got {rc}: {out[-300:]!r}")


def cli(*args):
    proc = subprocess.run([sys.executable, str(pathlib.Path(__file__).resolve()), *map(str, args)],
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def selftest():
    fails = []
    reds, count = check_templates(FIXTURES)
    nested = [p.name for p in FIXTURES.glob("*.md") if "nested_max_turns:" in p.read_text()]
    if reds or count < 2 or not nested:
        fails.append(f"green base: {count} template(s), nested in {nested}, reds {reds}")
    with tempfile.TemporaryDirectory() as tmp:
        for n, (label, name, old, new, rule) in enumerate(CASES):
            case = pathlib.Path(tmp) / f"case{n}"
            shutil.copytree(FIXTURES, case)
            target = case / name
            text = target.read_text()
            if old not in text:
                fails.append(f"{label}: fixture {name} lacks {old!r}")
                continue
            target.write_text(text.replace(old, new, 1))
            got = [(f, r) for f, r, _ in check_templates(case)[0]]
            if got != [(name, rule)]:
                fails.append(f"{label}: want exactly [({name}, {rule})], got {got}")
        # The CLI, as a child process, so an exit code the functions never produce is seen.
        empty = pathlib.Path(tmp) / "empty"
        empty.mkdir()
        for want, args, marker in (
            (0, ("--templates", FIXTURES), "BUDGET-CHECK OK"),
            (1, ("--templates", pathlib.Path(tmp) / "case2"), "RED 01-plain.md model"),
            (2, ("--templates", empty), "no *.md templates"),
            (2, ("--templates", pathlib.Path(tmp) / "absent"), "directory not found"),
            (2, ("--bogus",), "usage"),
        ):
            rc, out = cli(*args)
            if rc != want or marker not in out:
                fails.append(f"cli {args[0]} {args[1:]}: want exit {want} and {marker!r}, got {rc}: {out!r}")
        space_selftest(tmp, fails)

        def built(prefix):
            """(gate log, BRIEF_ROOT) of the one space case whose label starts with prefix."""
            [n] = [i for i, c in enumerate(SPACE_CASES) if c[0].startswith(prefix)]
            case = pathlib.Path(tmp) / f"space{n}"
            return case / "gate-01.txt", case
        # The space modes' CLI, green, red and could-not-run, again as a child process.
        for want, args, marker in (
            (0, ("--allocation", SPACE), "BUDGET-CHECK OK (--allocation"),
            (0, ("--build-log", SPACE / "gate-01.txt", SPACE), "BUDGET-CHECK OK (--build-log"),
            (1, ("--allocation", pathlib.Path(tmp) / "space2"), "RED capacity"),
            (1, ("--build-log", pathlib.Path(tmp) / "space4" / "gate-01.txt",
                 pathlib.Path(tmp) / "space4"), "RED heights"),
            (1, ("--build-log", *built("five pages, coverage-notes")),
             "over their rows: coverage-notes +0.5cm"),
            (1, ("--build-log", *built("five-page build log")),
             "over their rows: quick-take +0.6cm, open-questions +0.3cm, matrix +0.3cm"),
            (1, ("--build-log", *built("five pages, sources")),
             "over their rows: sources +0.4cm, matrix +0.1cm"),
            (1, ("--build-log", *built("five pages at 86.8cm")),
             "RED stranded: any one of these returns the page, smallest cut first; rebuild "
             "after the first: cut about 1.6cm from sources or from p4 above it: p4 strands "
             "8.6cm and sources (7.9cm) moved to p5; or cut about 4.4cm from matrix or from p2 "
             "above it: p2 strands 9.1cm and matrix (11.2cm) moved to p3\nRED pages: 5 pages, "
             "over GATE 3's 4; the cause is the space stranded"),
            (1, ("--build-log", *built("a 9.1cm strand and coverage-notes")),
             "RED over: coverage-notes: 8.2cm against a limit of 6.7cm (budget 6.2)\nRED pages: "
             "5 pages, over GATE 3's 4; over their rows: coverage-notes +2.0cm\nBUDGET-CHECK"),
            (2, ("--allocation", empty), "06-budget.tsv"),
            (2, ("--build-log", pathlib.Path(tmp) / "absent.txt", SPACE), "absent.txt"),
        ):
            rc, out = cli(*args)
            if rc != want or marker not in out:
                fails.append(f"cli {args[0]} {args[1:]}: want exit {want} and {marker!r}, got {rc}: {out!r}")
        web_selftest(tmp, fails)
        # Web mode's CLI, green, red and could-not-run, as a child process.
        for want, args, marker in (
            (0, ("--allocation", "--web", WEB), "BUDGET-CHECK OK (--allocation --web: 6 slots"),
            (1, ("--allocation", "--web", pathlib.Path(tmp) / "web0"),
             "RED cap: matrix: 273 words and 4 items against the schema's 272 and 6\nBUDGET-CHECK FAIL"),
            (2, ("--allocation", "--web", empty), "06-budget.tsv"),
        ):
            rc, out = cli(*args)
            if rc != want or marker not in out:
                fails.append(f"cli {args[0]} {args[1:]}: want exit {want} and {marker!r}, got {rc}: {out!r}")
        screened_selftest(tmp, fails)
        by_question_selftest(tmp, fails)
        # G80's hash and THE CODE SCREEN as a child process. The record's Shape line is what
        # --shape-hash prints.
        at = lambda label: pathlib.Path(tmp) / f"screened{[c[0] for c in SCREENED_CASES].index(label)}"
        for want, args, marker in (
            (0, ("--shape-hash", WEB), f"Shape: {_H}\n"),
            (0, ("--screened", WEB), f"BUDGET-CHECK OK (--screened: the code screen passes shape {_H[:12]})"),
            (1, ("--screened", at("an answer flipped")), "RED screened: 06-allocation.md records shape 054ff78a"),
            (1, ("--screened", at("no Shape line")), "RED screened: 06-allocation.md has no `Shape:` line"),
            # A revision `--allocation --web` passes is still red here: the screen is code, so it never goes stale.
            (0, ("--allocation", "--web", at("an answer flipped")), "BUDGET-CHECK OK (--allocation --web"),
            (1, ("--screened", at("a lead row the founder holds")),
             "RED known: open-questions: the evidence clause leads with C-011"),
            (2, ("--screened", empty), "06-shape.json"),
            (2, ("--shape-hash", empty), "06-shape.json"),
        ):
            rc, out = cli(*args)
            if rc != want or marker not in out or (args[0] == "--shape-hash" and rc == 0 and out != marker):
                fails.append(f"cli {args[0]} {args[1:]}: want exit {want} and {marker!r}, got {rc}: {out!r}")
    for fail in fails:
        print(f"FAIL {fail}")
    total = (1 + len(CASES) + 5 + 1 + len(SPACE_CASES) + 11 + 1 + len(WEB_CASES) + len(CEILING_CASES) + 3 + 4
             + 1 + len(SCREENED_CASES) + 8 + BYQ_CASES)
    if fails:
        print(f"BUDGET-CHECK SELFTEST FAIL ({len(fails)} of {total} case(s))")
        return 1
    print(f"BUDGET-CHECK SELFTEST OK ({total} cases)")
    return 0


def main(argv):
    if argv[1:] == ["--selftest"]:
        return selftest()
    if len(argv) in (2, 3) and argv[1] == "--templates":
        return templates(argv[2] if len(argv) == 3 else STAGES)
    if len(argv) == 3 and argv[1] == "--allocation":
        return space("allocation", allocation_reds, argv[2])
    if len(argv) == 4 and argv[1:3] == ["--allocation", "--web"]:
        return web(argv[3])
    if len(argv) == 4 and argv[1:3] == ["--allocation", "--by-question"]:
        return by_question_cli(argv[3])
    if len(argv) == 3 and argv[1] == "--shape-hash":
        return shape_hash_cli(argv[2])
    if len(argv) == 3 and argv[1] == "--screened":
        return screened(argv[2])
    if len(argv) == 4 and argv[1] == "--build-log":
        return space("build-log", build_log_reds, argv[2], argv[3])
    print("budget-check: usage: budget-check.py --templates [DIR] | --allocation [--web|--by-question] BRIEF_ROOT"
          " | --shape-hash BRIEF_ROOT | --screened BRIEF_ROOT | --build-log GATE_LOG BRIEF_ROOT | --selftest",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
