#!/usr/bin/env python3
"""Stage 6's code half: the typed shape node's inlined input, and its answer written as the files
the gates and the author read.

WHY THIS EXISTS (S11; Globex design § 2 R2, § 7). Stage 6 ran as a wrapped `lead` node with the Agent
tool: it read the tools to learn their formats, then ran its own LLM screener and fix loop. On the
vandelay run (2026-10-13) that was 40 turns and 15.5 minutes for a first-round FAIL (N45). Now
one typed call does the judgement, with every input pasted into its prompt, and code does the rest:
this file writes its files, and `tools/budget-check.py --screened` screens them.

  shape.py prep BRIEF_ROOT
      shape-in.md: the reader, the locked thesis, the questions with their changes lines, the
      cohort (the hiring company first), the caps and ceilings budget-check holds the shape to,
      each company's comp-<slug>.md with line numbers and its snapshot fields, and every ledger row
      pre-joined by ID with `known` set by code (tools/back-lane.py's rows)
  shape.py write BRIEF_ROOT
      from shape.json (the node's structured output, references/schemas/shape.schema.json):
      06-shape.json, the map and matrix exactly as budget-check, assemble and brief-check read them;
      06-budget.tsv, `slot<TAB>words<TAB>items`; and 06-allocation.md, the record: its `Shape:` line
      (budget-check --shape-hash), one `- H1′ across|down|row <label> (Q<n>): <decision> | flips:
      <flips>` line per axis and row, the dropped axes and rows, § Departures, then one `### <slot>`
      block per web slot (Need, Claims, ICP, Budget, Evidence clause, Source for stage 7)
  shape.py --selftest
      offline, on the Globex fixture: prep's sections, write's files green on the code screen and
      equal to the shape Globex's author used, and each refusal

A slot's Claims line is the node's claims, then every ID on its evidence clauses, then for map and
matrix the shape's own IDs, each once: an evidence clause is always allotted (brief-check A1,
by-question).
A Need line quotes the reader.json duty its line names, so the text is the posting's own.

WHAT `write` REFUSES (exit 1, one stderr line each, `SHAPE REFUSED <why>`), the rules the schema
cannot hold: slots other than the six web slots once each; a need line no reader.json duty has; an
ICP list outside quick-take; a source range outside its comp-<slug>.md; a departure naming an ID
that leads no evidence clause of its slot. The shape's own rules are budget-check's.

EXIT CODES. 0 written. 1 refused, or --selftest red. 2 could not run: usage, or an input missing or
unreadable.

PRECONDITION: none. Stdlib only, offline.
"""

import contextlib
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
SLOTS = ("quick-take", "map", "recommendations", "what-changed", "matrix", "open-questions")
SNAPSHOT_KEYS = ("name", "threat_assessment", "posture_axis", "posture", "recent_moves", "company_stage")
CLAIM_RE = re.compile(r"C-[0-9]{3,}")
FIXTURE = ROOT / "tools" / "fixtures" / "shape" / "globex.shape.json"
GLOBEX_GOOD = ROOT / "tools" / "fixtures" / "schema" / "good" / "globex"
GLOBEX_RUN = ROOT / "quality-bar" / "fixtures" / "globex" / "run"
GLOBEX_SHAPE = ROOT / "tools" / "fixtures" / "assemble" / "06-shape.json"
GLOBEX_COMP = ROOT / "tools" / "fixtures" / "back-lane" / "comp-globex.md"


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BL = _load("back_lane", "tools/back-lane.py")
BU = _load("budget_check", "tools/budget-check.py")
CannotRun = BL.CannotRun


class Refused(Exception):
    """Exit 1: the answer breaks a rule the schema cannot hold."""


def one_line(text):
    return " ".join(str(text).split())


def unique(ids):
    out = []
    for cid in ids:
        if cid not in out:
            out.append(cid)
    return out


def cohort(root):
    """[slug], the hiring company first, then names.json's order: every comp-<slug>.md."""
    stems = sorted(p.name[5:-3] for p in root.glob("comp-*.md"))
    rivals = [n["slug"] for n in BL.read_json(root / "names.json") if n.get("slug") in stems]
    client = [s for s in stems if s not in rivals]
    if len(client) != 1:
        raise CannotRun("want one comp-<slug>.md that is no names.json rival (the hiring company), got %s" % client)
    return client + rivals


def numbered(path):
    return "".join("%4d  %s\n" % (n, line) for n, line in enumerate(BL.read_text(path).splitlines(), 1))


# --- prep -----------------------------------------------------------------------------------------
def caps_block():
    caps, fields = BU.web_caps(), BU.field_caps()
    slots = "\n".join("| %s | %d | %d |" % (s, caps[s][0], caps[s][1]) for s in SLOTS)
    return ("# CAPS\n\nbudget-check reads these from build/web/brief.schema.json; the gate holds the shape to them.\n\n"
            "| slot | most words | most items |\n|---|---|---|\n" + slots + "\n\n"
            "Items are a slot's list length: quick-take points, map answers (one per company), recommendations, "
            "what-changed moves, matrix rows, open questions. An axis `question` holds %d words at most, `yes` and "
            "`no` %d and %d, a row `label` %d. A row carries at most %d `Unknown` cells and a cell at most %d IDs. "
            "Across the shape and every slot's Claims, ICP and evidence IDs: at most %d distinct claim IDs, %d "
            "distinct URLs, and %d card words (each distinct ID's shown quote, or its gloss, plus %d).\n"
            % (fields["question"], fields["yes"], fields["no"], fields["label"], BU.UNKNOWN_MAX, BU.CELL_IDS_MAX,
               BU.PAGE_IDS_MAX, BU.PAGE_URLS_MAX, BU.CARD_WORDS_MAX, BU.CARD_ID_WORDS))


def prep(root):
    reader, claims, known = BL.ctx(root)
    questions = BL.read_json(root / "questions.json")
    names = {n["slug"]: n for n in BL.read_json(root / "names.json")}
    slugs = cohort(root)
    co = reader.get("company") or {}
    rd = {k: reader.get(k) for k in ("company", "role", "duties", "positioning", "constraints", "known_summary")
          if k in reader}
    qs = [{k: q.get(k) for k in ("id", "text", "changes", "closed_list")} for q in questions.get("questions", [])]
    companies = []
    for slug in slugs:
        domain = names[slug]["domain"] if slug in names else co.get("domain")
        name = names[slug]["name"] if slug in names else co.get("name")
        snap_path = root / "snapshots" / ("%s.json" % domain)
        snap = BL.read_json(snap_path) if snap_path.is_file() else {}
        companies.append("## %s (%s)%s\n\n%s\n```\n%s```\n" % (
            name, slug, ", the hiring company" if slug == slugs[0] else "",
            BL.fence({k: snap.get(k) for k in SNAPSHOT_KEYS if k in snap}) if snap else "No snapshot.\n",
            numbered(root / ("comp-%s.md" % slug))))
    parts = [
        "# READER\n\nThe founder: his company, the role, its duty lines (a slot's `need` is one `line`), his "
        "positioning, his constraints and what he already holds.\n\n" + BL.fence(rd),
        "# THESIS\n\nThe locked candidate. quick-take carries its IDs.\n\n" + BL.fence(BL.locked_candidate(root)),
        "# QUESTIONS\n\nThe locked questions. An axis or row `serves` one `id`; its `decision` comes from that "
        "question's `changes`.\n\n" + BL.fence(qs),
        "# COHORT\n\nEvery company once, by slug; `company`, `columns[0]` and the first answer are the "
        "first.\n\n" + BL.fence([{"slug": s, "name": names[s]["name"] if s in names else co.get("name")} for s in slugs]),
        caps_block(),
        "# COMPANIES\n\nEach company's snapshot fields, then its comp-<slug>.md with line numbers (a slot's "
        "`source` names a range of these).\n\n" + "\n".join(companies),
        "# ROWS\n\nEvery ledger row, pre-joined by ID. `known: true` is the founder's own fact, set by code.\n\n"
        "```\n" + BL.rows_block(list(claims), claims, known) + "```\n",
    ]
    out = BL.write(root / "shape-in.md", "\n".join(parts))
    return "shape-in.md: %d companies, %d rows, %d bytes" % (len(slugs), len(claims), out.stat().st_size)


# --- write ----------------------------------------------------------------------------------------
def refusals(root, ans, reader):
    out = []
    got = [s.get("slot") for s in ans["slots"]]
    if sorted(got) != sorted(SLOTS):
        out.append("slots %s are not the six web slots once each (%s)" % (got, ", ".join(SLOTS)))
    duties = {d.get("line") for d in reader.get("duties") or []}
    departures = {(d["slot"], d["id"]) for d in ans["departures"]}
    leads = set()
    for s in ans["slots"]:
        if s["need"] not in duties:
            out.append("%s: need %s is no reader.json duty line (%s)" % (s["slot"], s["need"], ", ".join(sorted(duties))))
        if s["icp"] and s["slot"] != "quick-take":
            out.append("%s: an ICP list belongs to quick-take alone" % s["slot"])
        leads |= {(s["slot"], e["c"][0]) for e in s["evidence"] if e["c"]}
        src = s.get("source")
        if src:
            path = root / src["file"]
            n = len(BL.read_text(path).splitlines()) if path.is_file() else 0
            if not n or not 1 <= src["from"] <= src["to"] <= n:
                out.append("%s: source %s lines %d-%d is outside the file (%s)" % (
                    s["slot"], src["file"], src["from"], src["to"], "%d lines" % n if n else "absent"))
    for slot, cid in sorted(departures - leads):
        out.append("departure %s %s: %s leads no evidence clause of %s" % (slot, cid, cid, slot))
    return out


def shape_of(ans):
    """06-shape.json: the map and matrix with no `decision` or `flips`, as assemble copies them; an
    empty cell is the string "Unknown" there (the typed answer avoids a two-type union, which the
    CLI's strict schema check warns on)."""
    axis = lambda a: {k: a[k] for k in ("question", "yes", "no", "serves")}
    return {"company": ans["company"],
            "map": {"across": axis(ans["map"]["across"]), "down": axis(ans["map"]["down"]),
                    "answers": ans["map"]["answers"]},
            "matrix": {"columns": ans["matrix"]["columns"],
                       "rows": [{"label": r["label"], "serves": r["serves"],
                                 "cells": [cell or "Unknown" for cell in r["cells"]]} for r in ans["matrix"]["rows"]]}}


def slot_block(slot, s, ans, duties):
    ids = list(s["claims"]) + [c for e in s["evidence"] for c in e["c"] + CLAIM_RE.findall(e["fact"])]
    if slot == "map":
        ids += [c for a in ans["map"]["answers"] for axis in ("across", "down") for c in a[axis]["c"]]
    if slot == "matrix":
        ids += [c for r in ans["matrix"]["rows"] for cell in r["cells"] for c in cell]
    lines = ["### %s" % slot,
             '- Need: "%s" | reader.json duties %s' % (one_line(duties[s["need"]]), s["need"]),
             "- Claims: " + ", ".join(unique(ids))]
    if s["icp"]:
        lines.append("- ICP: " + ", ".join(unique(s["icp"])))
    lines.append("- Budget: %d words, %d items" % (s["words"], s["items"]))
    for e in s["evidence"]:
        label = " (%s)" % one_line(e["label"]) if one_line(e["label"]) else ""
        lines.append("- Evidence clause%s: %s — %s" % (label, ", ".join(e["c"]), one_line(e["fact"])))
    if s.get("source"):
        src = s["source"]
        lines.append("- Source for stage 7: %s lines %d-%d" % (src["file"], src["from"], src["to"]))
    return lines


def write_files(root):
    ans = BL.read_json(root / "shape.json")
    reader = BL.read_json(root / "reader.json")
    try:
        reds = refusals(root, ans, reader)
    except (KeyError, TypeError, IndexError) as exc:
        raise CannotRun("shape.json lacks a field the schema requires (%s: %s)" % (type(exc).__name__, exc))
    if reds:
        raise Refused(reds)
    BL.write(root / "06-shape.json", json.dumps(shape_of(ans), indent=1, ensure_ascii=False) + "\n")
    by_slot = {s["slot"]: s for s in ans["slots"]}
    BL.write(root / "06-budget.tsv", "slot\twords\titems\n"
             + "".join("%s\t%d\t%d\n" % (slot, by_slot[slot]["words"], by_slot[slot]["items"]) for slot in SLOTS))
    try:
        sha = BU.shape_hash(root)
    except BU.Unreadable as exc:
        raise Refused(["06-shape.json: %s" % exc])
    h1 = ["- H1′ %s (%s): %s | flips: %s" % (axis, ans["map"][axis]["serves"], one_line(ans["map"][axis]["decision"]),
                                             one_line(ans["map"][axis]["flips"])) for axis in ("across", "down")]
    h1 += ["- H1′ row %s (%s): %s | flips: %s" % (one_line(r["label"]), r["serves"], one_line(r["decision"]),
                                                 one_line(r["flips"])) for r in ans["matrix"]["rows"]]
    dropped = ['- Dropped %s "%s" (%s): %s%s' % (d["kind"], one_line(d["what"]), d["serves"], one_line(d["reason"]),
                                                 " (%s)" % ", ".join(d["c"]) if d["c"] else "") for d in ans["dropped"]]
    deps = ["- %s %s: %s" % (d["slot"], d["id"], one_line(d["reason"])) for d in ans["departures"]] or ["None."]
    duties = {d["line"]: d["text"] for d in reader.get("duties") or []}
    lines = ["# Stage 6: allocation", "",
             "Written by `tools/shape.py write` from `shape.json`, the shape node's typed answer, for the shape below.",
             "Shape: %s" % sha, "", "## Axes and rows", ""] + h1 + dropped + ["", "## Departures", ""] + deps
    lines += ["", "## The slot blocks"]
    for slot in SLOTS:
        lines += [""] + slot_block(slot, by_slot[slot], ans, duties)
    BL.write(root / "06-allocation.md", "\n".join(lines) + "\n")
    return "06-shape.json, 06-budget.tsv, 06-allocation.md: shape %s, %d rows, %d departures" % (
        sha[:12], len(ans["matrix"]["rows"]), len(ans["departures"]))


# --- selftest -------------------------------------------------------------------------------------
def globex_root(tmp):
    """The Globex fixture as stage 6 sees it: typed reader, questions, names and ledger; 02-questions.md
    rendered from questions.json; comp-globex.md and a one-line comp file per rival; the snapshots;
    a 05-thesis.json locking the repaired spine."""
    root = pathlib.Path(tmp) / "root"
    root.mkdir()
    for f in ("reader.json", "questions.json", "names.json", "claims.jsonl"):
        shutil.copy(GLOBEX_GOOD / f, root / f)
    qs = BL.read_json(root / "questions.json")["questions"]
    (root / "02-questions.md").write_text("".join("### %s. %s\n\n" % (q["id"], q["text"]) for q in qs), encoding="utf-8")
    shutil.copy(GLOBEX_COMP, root / "comp-globex.md")
    for n in BL.read_json(root / "names.json"):
        (root / ("comp-%s.md" % n["slug"])).write_text("# %s (fixture)\n" % n["name"], encoding="utf-8")
    shutil.copytree(GLOBEX_RUN / "snapshots", root / "snapshots")
    cand = BL.RANK.candidate_of(BL.read_json(BL.SCREENS / "items/CTL-spine-b.json"), "CTL-spine")
    (root / "05-thesis.json").write_text(json.dumps({"candidates": [cand], "verdicts": [], "rank": ["CTL-spine"],
                                                     "locked": "CTL-spine"}), encoding="utf-8")
    shutil.copy(FIXTURE, root / "shape.json")
    return root


def selftest():
    fails, n = [], [0]

    def case(label, ok, got=""):
        n[0] += 1
        if not ok:
            fails.append("%s: %s" % (label, str(got)[:600]))

    def run(*argv):
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
            code = main(["shape.py"] + [str(a) for a in argv])
        return code, out.getvalue() + err.getvalue()

    found = BL.SCHEMA.check(ROOT / "references" / "schemas" / "shape.schema.json", FIXTURE)
    case("the Globex fixture answer validates against shape.schema.json", not found, found)
    with tempfile.TemporaryDirectory() as t:
        root = globex_root(t)
        code, out = run("prep", root)
        text = (root / "shape-in.md").read_text(encoding="utf-8") if code == 0 else ""
        heads = re.findall(r"^# ([A-Z]+)$", text, re.M)
        case("prep writes every section once, in order",
             code == 0 and heads == ["READER", "THESIS", "QUESTIONS", "COHORT", "CAPS", "COMPANIES", "ROWS"], (code, out, heads))
        rows = [json.loads(l) for l in text.split("# ROWS", 1)[-1].split("```\n")[1].splitlines() if l.strip()] if text else []
        ledger = [json.loads(l) for l in (root / "claims.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        case("prep inlines every ledger row, each with a code-set known",
             len(rows) == len(ledger) and all(isinstance(r.get("known"), bool) for r in rows), len(rows))
        cohort_json = text.split("# COHORT", 1)[-1].split("```json\n")[1].split("```")[0] if text else "[]"
        case("prep lists the cohort with the hiring company first",
             [c["slug"] for c in json.loads(cohort_json)][:2] == ["globex", "billo"], cohort_json[:200])
        case("prep numbers the hiring company's comp file, so a source range can be named",
             "  88  ## Channel fit" in text, "")
        case("prep carries the caps budget-check holds, read from the schema",
             "| matrix | %d | %d |" % BU.web_caps()["matrix"] in text and "at most %d `Unknown`" % BU.UNKNOWN_MAX in text)
        code, out = run("write", root)
        case("write exits 0 on the Globex answer", code == 0, out)
        case("06-shape.json is the shape Globex's author used",
             code == 0 and BL.read_json(root / "06-shape.json") == BL.read_json(GLOBEX_SHAPE), "")
        reds, _ = BU.screened_reds(root) if code == 0 else ([("none", "")], "")
        case("the code screen (budget-check --screened) is green on what write wrote", not reds, reds)
        reds = BU.web_allocation_reds(root) if code == 0 else [("none", "")]
        case("budget-check --allocation --web is green on what write wrote", not reds, reds)
        alloc, byq = BU.by_question(root) if code == 0 else ({}, [("none", "")])
        case("allocate's --by-question reads the record: six slots, every locked question answered",
             not byq and list(alloc) == list(SLOTS), (byq, list(alloc)))
        alloc_text = (root / "06-allocation.md").read_text(encoding="utf-8") if code == 0 else ""
        case("each evidence clause's IDs are on its slot's Claims line",
             code == 0 and {c for _, c in BU.allocation_claims(root, ("evidence",))}
             <= {c for _, c in BU.allocation_claims(root, ("claims",))}, "")
        case("the Need line quotes the duty", '- Need: "Run Growth initiatives for Globex and our Clients.' in alloc_text, "")
        case("a source range reaches prep-author's comp_ranges",
             BL.comp_ranges(root, alloc_text)[:1] and "lines 88-" in BL.comp_ranges(root, alloc_text)[0], "")
        # Red on revert: write with no H1′ lines, and the code screen reds `decision` on every axis and row.
        kept = alloc_text
        (root / "06-allocation.md").write_text("\n".join(l for l in kept.splitlines() if not l.startswith("- H1′")),
                                                encoding="utf-8")
        reds, _ = BU.screened_reds(root)
        case("a record with no H1′ lines reds decision on both axes and every row",
             [r for r, _ in reds] == ["decision"] * (2 + len(BL.read_json(GLOBEX_SHAPE)["matrix"]["rows"])), reds)
        (root / "06-allocation.md").write_text(kept, encoding="utf-8")
    good = BL.read_json(FIXTURE)
    for label, edit, want in (
            ("a slot missing", lambda a: a["slots"].pop(), "are not the six web slots"),
            ("a slot twice", lambda a: a["slots"].append(dict(a["slots"][0])), "are not the six web slots"),
            ("a need line no duty has", lambda a: a["slots"][0].update(need="L999"), "need L999 is no reader.json duty"),
            ("an ICP list on the map", lambda a: a["slots"][1].update(icp=["C-016"]), "map: an ICP list"),
            ("a source past the file's end", lambda a: [s.update(source={"file": "comp-globex.md", "from": 88, "to": 999})
                                                        for s in a["slots"] if s["slot"] == "recommendations"],
             "outside the file"),
            ("a source in no file", lambda a: [s.update(source={"file": "comp-nobody.md", "from": 1, "to": 2})
                                               for s in a["slots"] if s["slot"] == "recommendations"], "absent"),
            ("a departure naming no lead", lambda a: a["departures"].append({"slot": "map", "id": "C-001", "reason": "x"}),
             "departure map C-001"),
    ):
        with tempfile.TemporaryDirectory() as t:
            root = globex_root(t)
            ans = json.loads(json.dumps(good))
            edit(ans)
            (root / "shape.json").write_text(json.dumps(ans), encoding="utf-8")
            code, out = run("write", root)
            case("write refuses %s" % label, code == 1 and "SHAPE REFUSED" in out and want in out
                 and not (root / "06-allocation.md").exists(), (code, out))
    with tempfile.TemporaryDirectory() as t:
        code, out = run("write", t)
        case("write on a root with no shape.json cannot run", code == 2, (code, out))
    for f in fails:
        print("FAIL " + f)
    if fails:
        print("SHAPE SELFTEST FAIL (%d of %d)" % (len(fails), n[0]))
        return 1
    print("SHAPE SELFTEST OK (%d cases)" % n[0])
    return 0


def main(argv):
    args = argv[1:]
    if args == ["--selftest"]:
        return selftest()
    if len(args) != 2 or args[0] not in ("prep", "write"):
        print(__doc__, file=sys.stderr)
        return 2
    root = pathlib.Path(args[1])
    try:
        print((prep if args[0] == "prep" else write_files)(root))
        return 0
    except Refused as exc:
        for why in exc.args[0]:
            print("SHAPE REFUSED %s" % why, file=sys.stderr)
        return 1
    except CannotRun as exc:
        print("shape.py %s: %s" % (args[0], exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
