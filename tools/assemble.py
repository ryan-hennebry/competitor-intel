#!/usr/bin/env python3
"""The assemble step: the author's prose spans merged into the code-built skeleton as brief.json.

WHY THIS EXISTS. The author writes prose only, with Write as its one tool and every input inlined
(design.md § 3, node `author`; b1 timed exactly that shape, SP/measure-model/build_author.py). The
parts no judgement touches come from typed files, never retyped: the map, the entities and the
matrix's columns and cell claim IDs. This code joins the two, then types the result the way the
span-ids node does, so brief.json reaches brief-check already carrying span ids, slots and cmp.

WHAT COMES FROM WHERE (all under BRIEF_ROOT):
  06-shape.json   company (the client's slug), map (axes, answers; each answer's c), matrix
                  columns, row labels and each cell's claim IDs ("Unknown" is a cell with no row)
  names.json      rivals, in its order: name, slug, snapshot <domain>.json
  reader.json     company.name and company.domain; role.title as `role`; role.jd_url as `jd_url`
  logos/logos.json  an entity's `logo` is its slug when exactly one record carries that slug, else
                  null (the wordmark)
  the prose       quick_take lede/body, recommendations, moves_heading, moves, matrix heading,
                  cells (row label -> one t per column, in column order; or, as the typed author
                  writes it, a list of {label, cells}) and legend, open_questions
  departures      optional: [{slot, id, reason}], each allotted evidence-clause ID the author left
                  off the page; written beside the brief as departures.json, which brief-check A1
                  reads as it reads 07-author.md § Forced departures
`run_date` is today in Europe/London, or `--run-date`. `dates` is left to final-build, which stamps
it (D4). A c of one ID is written as a string and an empty list as null: the brief schema's `ref`.

TYPING. backfill-globex.py's assign_span_ids, then assign_slots on the allocation's ICP rows
(brief-check's allotted_slots), then assign_cmp on brief-check's known rows: span-ids.py's chain.

WHAT IT REFUSES (exit 1, one stderr line each, `ASSEMBLE REFUSED <why>`): prose that does not fit
the skeleton: a matrix row the shape has and the prose lacks, or the reverse; a row whose cell count
is not the column count; a move whose rival is no slug of names.json; a prose key the brief does not
take. Content is not graded here: brief-check and claims-check --check are the author's gates.

  python3 tools/assemble.py <prose.json> <BRIEF_ROOT> [--out PATH] [--run-date YYYY-MM-DD]
        writes BRIEF_ROOT/brief.json, or PATH
  python3 tools/assemble.py --selftest
        offline: b1's author-high-1.prose.json on the Globex fixture root assembles to a brief whose
        brief-check findings, and claims-check --check findings on its `web.py --text --authored`
        text, equal tools/fixtures/assemble/expected-reds.tsv exactly; each refusal reds

THE B1 PROSE IS NOT GREEN, and the gates stay as they are. b1's author was prompted before S3's
founder-reader rules existed, so its prose recites Globex's own rows (KR-H), cites job-ad rows (JD),
names "the posting" (PL), repeats C-037 and C-133 across three sections (X1), gives the ICP point no
comparison (X2), drops allotted clauses (A1), and overruns the matrix rail (H1, F1) and a ledger
quantifier (B2). expected-reds.tsv holds each with its reason. Pinning them makes the test exact: an
assembly fault (an untyped span, a lost cell ID, a wrong entity) adds a finding and reds it.

EXIT CODES. 0 written. 1 refused, or --selftest red. 2 could not run: usage, or an input missing or
unreadable.

PRECONDITION: none. Stdlib only, offline.
"""

import contextlib
import copy
import datetime
import importlib.util
import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parent.parent
TZ = "Europe/London"
PROSE_KEYS = ("quick_take", "recommendations", "moves_heading", "moves", "matrix", "open_questions")
OPTIONAL_KEYS = ("departures",)
DEPARTURES = "departures.json"
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
FIX = ROOT / "tools/fixtures/assemble"
GLOBEX_RUN = ROOT / "quality-bar/fixtures/globex/run"
GLOBEX_NAMES = ROOT / "tools/fixtures/schema/good/globex/names.json"
EXPECTED = FIX / "expected-reds.tsv"


class CannotRun(Exception):
    """Exit 2."""


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BC = _load("brief_check", "tools/brief-check.py")
BF = _load("backfill_globex", "tools/backfill-globex.py")


def today():
    from zoneinfo import ZoneInfo
    return datetime.datetime.now(ZoneInfo(TZ)).date().isoformat()


def ref(c):
    """A c in the brief schema's `ref` form: one ID a string, two or more a list, none null."""
    if isinstance(c, list):
        return None if not c else c[0] if len(c) == 1 else list(c)
    return c


def span(s):
    return dict(s, c=ref(s.get("c"))) if isinstance(s, dict) else s


def spans(arr):
    return [span(s) for s in arr] if isinstance(arr, list) else arr


def read_json(path):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CannotRun("cannot read %s (%s)" % (path, exc))


def logo_for(slug, logos):
    """The slug when exactly one record carries it and that record is a logo; a wordmark record is
    null, which web.py sets as the name (G1 grades only a logo, never a wordmark)."""
    recs = [r for r in logos if isinstance(r, dict) and r.get("slug") == slug]
    return slug if len(recs) == 1 and recs[0].get("kind") != "wordmark" else None


def skeleton(root):
    """(the brief's code-built fields, the rival slugs). Raises CannotRun."""
    shape, names, reader = (read_json(root / f) for f in ("06-shape.json", "names.json", "reader.json"))
    logos = read_json(root / "logos/logos.json") if (root / "logos/logos.json").is_file() else []
    try:
        co, role = reader["company"], reader["role"]
        company = {"name": co["name"], "slug": shape["company"], "snapshot": co["domain"] + ".json",
                   "logo": logo_for(shape["company"], logos), "domain": co["domain"]}
        rivals = [{"name": n["name"], "slug": n["slug"], "snapshot": n["domain"] + ".json",
                   "logo": logo_for(n["slug"], logos)} for n in names]
        mp = copy.deepcopy(shape["map"])
        for a in mp["answers"]:
            for axis in ("across", "down"):
                a[axis]["c"] = ref(a[axis]["c"])
        rows = [{"label": r["label"],
                 "cells": [{"c": None, "mark": "unknown"} if cell == "Unknown" else {"c": ref(cell), "mark": "cited"}
                           for cell in r["cells"]]} for r in shape["matrix"]["rows"]]
        skel = {"company": company, "jd_url": role["jd_url"], "role": role["title"], "rivals": rivals,
                "map": {k: v for k, v in mp.items() if k in ("across", "down", "answers")},
                "matrix": {"columns": list(shape["matrix"]["columns"]), "rows": rows}}
    except (KeyError, TypeError, AttributeError) as exc:
        raise CannotRun("the skeleton inputs lack a field (%s: %s)" % (type(exc).__name__, exc))
    return skel, [r["slug"] for r in rivals]


def assemble(prose, root, run_date):
    """(brief, refusal lines)."""
    root = pathlib.Path(root)
    skel, slugs = skeleton(root)
    out = []
    if not isinstance(prose, dict):
        return None, ["the prose is not a JSON object"]
    out += ["prose key %r is not one the author writes (%s)" % (k, ", ".join(PROSE_KEYS + OPTIONAL_KEYS))
            for k in prose if k not in PROSE_KEYS + OPTIONAL_KEYS]
    out += ["prose lacks %r" % k for k in PROSE_KEYS if k not in prose]
    if out:
        return None, out
    pm = prose["matrix"] if isinstance(prose["matrix"], dict) else {}
    cells = pm.get("cells")
    if isinstance(cells, list) and all(isinstance(r, dict) and "label" in r for r in cells):
        cells = {r["label"]: r.get("cells") for r in cells}  # the typed author's list form
    cells = cells if isinstance(cells, dict) else {}
    labels = [r["label"] for r in skel["matrix"]["rows"]]
    width = len(skel["matrix"]["columns"])
    out += ["matrix row %r is in 06-shape.json and not in the prose" % l for l in labels if l not in cells]
    out += ["matrix row %r is in the prose and not in 06-shape.json" % l for l in cells if l not in labels]
    for row in skel["matrix"]["rows"]:
        ts = cells.get(row["label"])
        if row["label"] in cells and (not isinstance(ts, list) or len(ts) != width):
            out.append("matrix row %r has %s cell texts for %d columns"
                       % (row["label"], len(ts) if isinstance(ts, list) else "no list of", width))
    moves = prose["moves"] if isinstance(prose["moves"], list) else []
    out += ["move %d's rival %r is no slug of names.json" % (i, m.get("rival") if isinstance(m, dict) else m)
            for i, m in enumerate(moves) if not isinstance(m, dict) or m.get("rival") not in slugs]
    if out:
        return None, out
    for row in skel["matrix"]["rows"]:
        for cell, t in zip(row["cells"], cells[row["label"]]):
            cell["t"] = t
        row["cells"] = [{"t": c["t"], "c": c["c"], "mark": c["mark"]} for c in row["cells"]]
    brief = {
        "company": skel["company"], "jd_url": skel["jd_url"], "role": skel["role"], "run_date": run_date,
        "rivals": skel["rivals"],
        "quick_take": [{"lede": spans(p.get("lede")), "body": spans(p.get("body"))} if isinstance(p, dict) else p
                       for p in prose["quick_take"]],
        "map": skel["map"],
        "recommendations": [{f: spans(r.get(f)) for f in ("test", "why", "next_step")} if isinstance(r, dict) else r
                            for r in prose["recommendations"]],
        "moves_heading": prose["moves_heading"],
        "moves": [dict(m, change=spans(m.get("change")), meaning=spans(m.get("meaning"))) for m in moves],
        "matrix": {"heading": pm.get("heading"), "columns": skel["matrix"]["columns"], "rows": skel["matrix"]["rows"],
                   "legend": spans(pm.get("legend"))},
        "open_questions": [spans(q) for q in prose["open_questions"]] if isinstance(prose["open_questions"], list)
        else prose["open_questions"],
    }
    ctx = BC.Ctx(root / "brief.json", root, BC.load_schema(), brief=brief)
    known = {cid: ctx.known(cid) for cid in ctx.rows}
    icp = BC.allotted_slots(root).get("icp", [])
    return BF.assign_cmp(BF.assign_slots(BF.assign_span_ids(brief), icp), known), []


def relogo(brief, logos):
    """Re-derive every entity's `logo` from logos.json in place, prose untouched; returns the
    [(slug, old, new)] it changed. A logo record replaced after assembly (S14's gates turned
    vandelay run 2's TollBit and Profound into wordmarks) must reach the page the same way."""
    changed = []
    for e in [brief.get("company") or {}] + list(brief.get("rivals") or []):
        if isinstance(e, dict) and isinstance(e.get("slug"), str):
            new = logo_for(e["slug"], logos)
            if e.get("logo") != new:
                changed.append((e["slug"], e.get("logo"), new))
                e["logo"] = new
    return changed


def main(argv):
    args = argv[1:]
    if args == ["--selftest"]:
        return selftest()
    if len(args) == 2 and args[0] == "--relogo":
        root = pathlib.Path(args[1])
        brief = read_json(root / "brief.json")
        logos = read_json(root / "logos/logos.json") if (root / "logos/logos.json").is_file() else []
        for slug, old, new in relogo(brief, logos):
            print("RELOGO %s: %r -> %r" % (slug, old, new))
        (root / "brief.json").write_text(json.dumps(brief, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        return 0
    opts, pos = {"--out": None, "--run-date": None}, []
    while args:
        if args[0] in opts and len(args) > 1:
            opts[args[0]], args = args[1], args[2:]
        elif args[0].startswith("-"):
            pos = []
            break
        else:
            pos, args = pos + [args[0]], args[1:]
    if len(pos) != 2 or (opts["--run-date"] is not None and not DATE_RE.match(opts["--run-date"])):
        sys.stderr.write(__doc__)
        return 2
    root = pathlib.Path(pos[1])
    out_path = pathlib.Path(opts["--out"]) if opts["--out"] else root / "brief.json"
    try:
        for need in ("claims.jsonl", "pages/index.tsv"):
            if not (root / need).is_file():
                raise CannotRun("no file to read at %s" % (root / need))
        prose = read_json(pos[0])
        brief, refused = assemble(prose, root, opts["--run-date"] or today())
    except CannotRun as exc:
        sys.stderr.write("assemble: %s\n" % exc)
        return 2
    for line in refused:
        sys.stderr.write("ASSEMBLE REFUSED %s\n" % line)
    if refused:
        return 1
    out_path.write_text(json.dumps(brief, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_path.parent / DEPARTURES).write_text(json.dumps({"departures": prose.get("departures") or []},
                                                         indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    n = sum(len(arr) for _, arr in BF.span_fields(brief))
    sys.stdout.write("ASSEMBLE OK %s: %d spans, slots %s\n" % (out_path, n, [p.get("slot") for p in brief["quick_take"]]))
    return 0


# --- selftest -------------------------------------------------------------------------------------
def globex_root(tmp):
    """The Globex fixture root plus the skeleton files b1's author was given (06-shape.json, the
    backfilled names.json) and the run's sources.tsv, which brief-check's L1 reads."""
    root = pathlib.Path(tmp) / "root"
    root.mkdir()
    for p in GLOBEX_RUN.iterdir():
        if not p.name.startswith("brief"):
            (root / p.name).symlink_to(p)
    for f in ("06-shape.json", "sources.tsv"):
        shutil.copy(FIX / f, root / f)
    shutil.copy(GLOBEX_NAMES, root / "names.json")
    return root


def expected_rows():
    lines = EXPECTED.read_text(encoding="utf-8").splitlines()
    return [dict(zip(lines[0].split("\t"), l.split("\t"))) for l in lines[1:] if l.strip()]


def fails_of(gate, stderr):
    """[(gate, rule, message)] from a gate's `FAIL: <rule> <message>` lines; claims-check's
    `<file>:<line>: ` lead is dropped, since the file is a temp path."""
    out = []
    for line in stderr.splitlines():
        if line.startswith("FAIL: ") and " " in line[len("FAIL: "):]:
            rule, msg = line[len("FAIL: "):].split(" ", 1)
            out.append((gate, rule, re.sub(r"^\S*\.md:\d+: ", "", msg)))
    return out


def match_expected(found):
    """(pinned rows no finding matched, findings no pinned row matched): one finding per row."""
    rows, extra = expected_rows(), []
    left = list(rows)
    for gate, rule, msg in found:
        hit = next((r for r in left if (r["gate"], r["rule"]) == (gate, rule) and msg.startswith(r["prefix"])), None)
        if hit is None:
            extra.append("%s %s %s" % (gate, rule, msg[:100]))
        else:
            left.remove(hit)
    return ["%s %s %s" % (r["gate"], r["rule"], r["prefix"]) for r in left], extra


def selftest():
    fails, n = [], [0]
    prose = json.loads((FIX / "author-high-1.prose.json").read_text(encoding="utf-8"))
    cc = _load("claims_check", "tools/claims-check.py")

    def case(label, ok, got):
        n[0] += 1
        if not ok:
            fails.append("%s: %s" % (label, got))

    recs = [{"slug": "a", "kind": "svg"}, {"slug": "w", "kind": "wordmark"},
            {"slug": "d", "kind": "img"}, {"slug": "d", "kind": "img"}]
    got = [logo_for(s, recs) for s in ("a", "w", "d", "x")]
    case("a logo record keys the entity; a wordmark, a duplicate or none is null (vandelay run 2's G1)",
         got == ["a", None, None, None], got)
    b = {"company": {"slug": "a", "logo": "a"}, "rivals": [{"slug": "w", "logo": "w"}, {"slug": "d", "logo": None}]}
    ch = relogo(b, [{"slug": "a", "kind": "svg"}, {"slug": "w", "kind": "wordmark"}, {"slug": "d", "kind": "img"}])
    case("--relogo re-derives each entity's logo from logos.json, a logo that became a wordmark goes null",
         ch == [("w", "w", None), ("d", None, "d")] and b["rivals"][0]["logo"] is None, (ch, b))
    with tempfile.TemporaryDirectory() as tmp:
        root = globex_root(tmp)
        pp = pathlib.Path(tmp) / "prose.json"
        pp.write_text(json.dumps(prose, ensure_ascii=False), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            code = main(["assemble.py", str(pp), str(root), "--run-date", "2026-10-11"])
        case("assemble exits 0 on b1's author-high-1 prose", code == 0, (code, err.getvalue()))
        brief = json.loads((root / "brief.json").read_text(encoding="utf-8")) if code == 0 else {}
        case("every span has an id; every point a slot", brief and all(
            isinstance(s, dict) and "id" in s for _, arr in BF.span_fields(brief) for s in arr)
            and all(p.get("slot") for p in brief["quick_take"]), brief.get("quick_take"))
        cells = [c for r in brief.get("matrix", {}).get("rows", []) for c in r["cells"]]
        case("the matrix keeps the shape's cell IDs: Unknown is the one null cell",
             [c["mark"] for c in cells].count("unknown") == 1 and all((c["c"] is None) == (c["mark"] == "unknown") for c in cells),
             cells[:3])
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            bc_code = BC.main(["brief-check.py", str(root / "brief.json"), str(root)])
        found = fails_of("brief-check", err.getvalue())
        authored = pathlib.Path(tmp) / "authored.md"
        web = subprocess.run([sys.executable, str(ROOT / "build/web.py"), "--text", str(root / "brief.json"), "--authored"],
                             capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        authored.write_text(web.stdout, encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            cc_code = cc.main(["claims-check.py", "--check", str(authored), str(root / "claims.jsonl")])
        found += fails_of("claims-check", err.getvalue())
        case("web.py --text --authored exits 0", web.returncode == 0, web.stderr[-500:])
        unmatched, extra = match_expected(found)
        case("brief-check and claims-check --check red exactly expected-reds.tsv (%d rows)" % len(expected_rows()),
             bc_code == 1 and cc_code == 1 and not unmatched and not extra,
             "pinned rows no finding matched: %s; findings no row matched: %s" % (unmatched, extra))

        # The typed author's forms: matrix cells as a list of {label, cells}, and departures, which
        # land in departures.json, where brief-check A1 reads them as forced departures.
        typed = copy.deepcopy(prose)
        typed["matrix"]["cells"] = [{"label": k, "cells": v} for k, v in prose["matrix"]["cells"].items()]
        gone = ["C-261", "C-262", "C-263"]
        typed["departures"] = [{"slot": "what-changed", "id": i, "reason": "a fixture reason"} for i in gone]
        pp.write_text(json.dumps(typed, ensure_ascii=False), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            code = main(["assemble.py", str(pp), str(root), "--out", str(root / "typed.json"), "--run-date", "2026-10-11"])
        same = code == 0 and json.loads((root / "typed.json").read_text(encoding="utf-8")) == brief
        case("list-form matrix cells assemble to the same brief", same, (code, err.getvalue()[-300:]))
        deps = json.loads((root / "departures.json").read_text(encoding="utf-8")) if code == 0 else {}
        case("departures land in departures.json", [d["id"] for d in deps.get("departures", [])] == gone, deps)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            BC.main(["brief-check.py", str(root / "brief.json"), str(root)])
        a1 = [m for g, r, m in fails_of("brief-check", err.getvalue()) if r == "A1"]
        case("brief-check A1 reads departures.json: the three departed C-261..C-263 reds are gone, the rest stay",
             not [m for m in a1 if any(i in m for i in gone)] and len(a1) == 3, a1)
        (root / "departures.json").unlink()

        for label, mutate, want in (
                ("a matrix row the prose lacks", lambda p: p["matrix"]["cells"].pop("Buying path"), "matrix row 'Buying path' is in 06-shape"),
                ("a row one cell short", lambda p: p["matrix"]["cells"]["Entry price"].pop(), "matrix row 'Entry price' has 6"),
                ("a move on no rival of names.json", lambda p: p["moves"][0].update(rival="acme"), "move 0's rival 'acme'"),
                ("a prose key the author does not write", lambda p: p.update(map={}), "prose key 'map'")):
            bad = copy.deepcopy(prose)
            mutate(bad)
            pp.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
                code = main(["assemble.py", str(pp), str(root), "--out", str(pathlib.Path(tmp) / "bad.json")])
            lines = [l for l in err.getvalue().splitlines() if l.startswith("ASSEMBLE REFUSED ")]
            case(label + " is refused, one line", code == 1 and len(lines) == 1 and want in lines[0]
                 and not (pathlib.Path(tmp) / "bad.json").exists(), (code, err.getvalue()))

    for f in fails:
        sys.stderr.write("SELFTEST FAIL: %s\n" % f)
    if fails:
        sys.stderr.write("SELFTEST RED (%d of %d)\n" % (len(fails), n[0]))
        return 1
    sys.stdout.write("SELFTEST OK (%d cases; b1 author-high-1 assembled; its %d gate reds are exactly expected-reds.tsv)\n"
                     % (n[0], len(expected_rows())))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
