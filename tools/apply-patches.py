#!/usr/bin/env python3
"""The apply node: the arbiter's patches.json laid on brief.json, in code, or refused whole.

WHY THIS EXISTS. The fixer agent used to edit the page itself, so a stale old text, an uncited
number or a fix over its field's cap reached the operator before any check (Globex CAP1: a 15-word lede fix
against a 14-word cap, approved, then blocked; find-D F3). Now the arbiter only proposes, and this
code applies (design.md § 2 R2, § 3 node `apply`).

WHAT IT REFUSES, every refusal collected, one stderr line each, `APPLY REFUSED <what>: <why>`:
  shape     a patch off references/schemas/patches.schema.json (tools/schema.py, the one validator)
  span      a span_id that is no span of the brief, or two patches on one span
  fix_old   fix_old that is not the span's t exactly (the page moved under the arbiter)
  numeral   a fix_new holding a numeral (brief-check's `numerals`) with c empty
  X3        a changed field over its x-maxWords cap: brief-check's PROPOSAL_RULES on the brief the
            patches leave (`apply_proposal`, the `--proposal` code), graded on the touched fields only
A refused set writes nothing; there is no partial apply.

THE APPLY is brief-check's `apply_proposal`: t takes fix_new and c takes the patch's c (one ID as a
string, two or more as a list, none as null, the brief schema's `ref`). A fix_new of "" deletes the
span. The span keeps its id, so span-diff and verify.jsonl key on it after the edit.

THE ROOT. The arbiter emits `{"patches": [...]}` (patches.schema.json): `claude --json-schema`
returns an object. A bare array is read too. An optional `departures` list names each allotted
evidence clause the patches take off the page: applied in place it joins departures.json; under
--out it goes to <out stem>.departures.json, where brief-check A1 reads it beside that brief.

  python3 tools/apply-patches.py <patches.json> <brief.json> <BRIEF_ROOT>   apply in place
  python3 tools/apply-patches.py <patches.json> <brief.json> <BRIEF_ROOT> --out PATH
        the same refusals; the applied brief goes to PATH and brief.json is untouched (the arbiter's
        gate, so a refusal returns to the arbiter as its one repair before the apply node runs)
  python3 tools/apply-patches.py --selftest

EXIT CODES. 0 applied (an empty list included). 1 refused. 2 could not run: usage, an unreadable
patches.json or brief.json, no claims.jsonl in BRIEF_ROOT, or a root that is neither form.

PRECONDITION: none. Stdlib only, offline.
"""

import contextlib
import copy
import importlib.util
import io
import json
import pathlib
import shutil
import sys
import tempfile

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "references/schemas/patches.schema.json"
FIXTURES = ROOT / "quality-bar/fixtures/globex/fixtures.jsonl"


class CannotRun(Exception):
    """Exit 2."""


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BC = _load("brief_check", "tools/brief-check.py")
SCHEMA = _load("schema", "tools/schema.py")


def patch_list(doc):
    """The patch list from either root. Raises CannotRun on any other."""
    if isinstance(doc, dict) and "patches" in doc and set(doc) <= {"patches", "departures"} \
            and isinstance(doc["patches"], list):
        return doc["patches"]
    if isinstance(doc, list):
        return doc
    raise CannotRun('patches.json is neither {"patches": [...]} nor a list')


def refusals(brief, patches, brief_path, root):
    """Every refusal line for this patch list on this brief."""
    out = []
    sch = SCHEMA.load_schema(SCHEMA_PATH)
    shape = []
    SCHEMA.validate({"patches": patches}, sch, sch.get("$defs", {}), "$", shape, SCHEMA_PATH.parent)
    out += ["shape %s" % s for s in shape]
    if shape:
        return out  # the checks below read the fields the schema guarantees
    spans = {s["id"]: s for _, arr in BC.span_arrays(brief) for s in arr if isinstance(s, dict) and "id" in s}
    seen, ok = set(), []
    for n, p in enumerate(patches):
        sid, bad = p["span_id"], []
        if sid not in spans:
            bad.append("span %s: patches[%d] names no span of the brief" % (sid, n))
        elif sid in seen:
            bad.append("span %s: patches[%d] is a second patch on this span" % (sid, n))
        elif spans[sid].get("t") != p["fix_old"]:
            bad.append("fix_old %s: patches[%d]'s fix_old %r is not the span's text %r"
                       % (sid, n, p["fix_old"][:60], str(spans[sid].get("t"))[:60]))
        digits = BC.numerals(p["fix_new"])
        if digits and not p["c"]:
            bad.append("numeral %s: patches[%d]'s fix_new holds %s and cites no row (c is empty)" % (sid, n, digits))
        seen.add(sid)
        out += bad
        if not bad:
            ok.append(p)
    patched, touched = BC.apply_proposal(brief, ok)
    ctx = BC.Ctx(brief_path, root, BC.load_schema(), brief=patched)
    ctx.touched = touched
    out += ["%s %s" % (tag, msg) for tag, fn in BC.PROPOSAL_RULES for msg in fn(ctx)]
    return out


def applied(brief, patches):
    """The brief the patches leave, a fix_new of "" deleting its span."""
    out, _ = BC.apply_proposal(brief, patches)
    for _, arr in BC.span_arrays(out):
        arr[:] = [s for s in arr if not (isinstance(s, dict) and s.get("t") == "")]
    return out


def departures_of(doc):
    """[{slot, id, reason}] the patch set takes off the page; refusal lines for a malformed one."""
    deps = doc.get("departures", []) if isinstance(doc, dict) else []
    ok = isinstance(deps, list) and all(isinstance(d, dict) and isinstance(d.get("slot"), str)
                                        and isinstance(d.get("id"), str) and d.get("reason") for d in deps)
    return (deps, []) if ok else ([], ["shape departures: each entry needs slot, id and reason"])


def merged_departures(root, deps):
    """departures.json's entries plus deps, one per (slot, id)."""
    try:
        have = json.loads((root / "departures.json").read_text(encoding="utf-8")).get("departures") or []
    except (OSError, ValueError, AttributeError):
        have = []
    seen = {(d.get("slot"), d.get("id")) for d in have if isinstance(d, dict)}
    return {"departures": have + [d for d in deps if (d["slot"], d["id"]) not in seen]}


def run(patches_path, brief_path, root, out_path=None):
    """(refusal lines, patch count). Writes out_path (default brief_path) only when nothing is
    refused."""
    root = pathlib.Path(root)
    if not (root / "claims.jsonl").is_file():
        raise CannotRun("no file to read at %s" % (root / "claims.jsonl"))
    try:
        doc = json.loads(pathlib.Path(patches_path).read_text(encoding="utf-8"))
        patches = patch_list(doc)
        brief = json.loads(pathlib.Path(brief_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CannotRun("cannot read the inputs (%s)" % exc)
    if not isinstance(brief, dict):
        raise CannotRun("%s is not a JSON object" % brief_path)
    deps, bad = departures_of(doc)
    refused = bad + refusals(brief, patches, brief_path, root)
    if not refused:
        text = json.dumps(applied(brief, patches), indent=1, ensure_ascii=False) + "\n"
        target = pathlib.Path(out_path or brief_path)
        target.write_text(text, encoding="utf-8")
        if deps or out_path:
            side = target.with_name(target.stem + ".departures.json") if out_path else root / "departures.json"
            side.write_text(json.dumps(merged_departures(root, deps), indent=1, ensure_ascii=False) + "\n",
                            encoding="utf-8")
    return refused, len(patches)


def main(argv):
    args = argv[1:]
    if args == ["--selftest"]:
        return selftest()
    out = None
    if len(args) == 5 and args[3] == "--out":
        out, args = args[4], args[:3]
    if len(args) != 3 or any(a.startswith("-") for a in args):
        sys.stderr.write(__doc__)
        return 2
    try:
        refused, n = run(*args, out_path=out)
    except (CannotRun, BC.Unappliable, BC.SchemaError) as exc:
        sys.stderr.write("apply-patches: %s\n" % exc)
        return 2
    for line in refused:
        sys.stderr.write("APPLY REFUSED %s\n" % line)
    if refused:
        sys.stderr.write("APPLY RED (%d refusal%s; %s unchanged)\n" % (len(refused), "" if len(refused) == 1 else "s", args[1]))
        return 1
    sys.stdout.write("APPLY OK %d patch%s on %s%s\n" % (n, "" if n == 1 else "es", args[1],
                                                       " into %s" % out if out else ""))
    return 0


# --- selftest -------------------------------------------------------------------------------------
def selftest():
    """Offline, on the Globex CAP1 fixture's brief typed as span-ids types it."""
    fails, n = [], [0]
    rows = [json.loads(l) for l in FIXTURES.read_text(encoding="utf-8").splitlines() if l.strip()]
    cap1 = next(r for r in rows if r["id"] == "CAP1")
    root = ROOT / pathlib.Path(cap1["brief"]).parent
    bf = _load("backfill_globex", "tools/backfill-globex.py")
    brief = bf.assign_span_ids(json.loads((ROOT / cap1["brief"]).read_text(encoding="utf-8")))
    node = brief
    for k in cap1["block"].split("/"):
        node = node[int(k)] if k.isdigit() else node[k]
    target = node[cap1["spans"][0]]
    lede = target  # CAP1's span: the first quick-take lede
    rec = brief["recommendations"][0]["next_step"][0]

    def patch(span, new, c=(), fix_old=None, finding="F-1"):
        return {"span_id": span["id"], "fix_old": span["t"] if fix_old is None else fix_old, "fix_new": new,
                "c": list(c), "finding_ids": [finding]}

    def case(label, doc, want_code, want_kinds, check=None):
        """want_kinds: every refusal line's leading word, in order (the whole output, not its first line)."""
        n[0] += 1
        with tempfile.TemporaryDirectory() as tmp:
            bp, pp = pathlib.Path(tmp) / "brief.json", pathlib.Path(tmp) / "patches.json"
            before = json.dumps(brief, indent=1, ensure_ascii=False) + "\n"
            bp.write_text(before, encoding="utf-8")
            pp.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()) as err, contextlib.redirect_stdout(io.StringIO()):
                code = main(["apply-patches.py", str(pp), str(bp), str(root)])
            after = bp.read_text(encoding="utf-8")
        lines = [l[len("APPLY REFUSED "):] for l in err.getvalue().splitlines() if l.startswith("APPLY REFUSED ")]
        kinds = [l.split(" ")[0] for l in lines]
        ok = code == want_code and kinds == want_kinds
        ok = ok and ((after == before) if want_code else (check is None or check(json.loads(after))))
        if not ok:
            fails.append("%s: exit %s, refusals %s" % (label, code, lines or err.getvalue()[-300:]))

    def span_t(b, sid):
        return [s.get("t") for _, arr in BC.span_arrays(b) for s in arr if s.get("id") == sid]

    # CAP1: the fix_new the operator approved, 15 words against the lede's 14 (fixtures.jsonl), cited as the
    # fixture cites it. X3 alone refuses it.
    cap = patch(lede, cap1["override"][str(cap1["spans"][0])], cap1["claims"], finding="CAP1")
    case("CAP1, the cap fixture: refused by X3 alone", {"patches": [cap]}, 1, ["X3"])
    case("CAP1 under a bare array root", [cap], 1, ["X3"])
    case("a fix_old that is not the span's text", {"patches": [patch(rec, "Ask Miniclip first.", fix_old="Ask Miniclip.")]},
         1, ["fix_old"])
    case("a numeral without c", {"patches": [patch(rec, "Ask Miniclip for 3 returns.")]}, 1, ["numeral"])
    case("three refusals, one line each", {"patches": [cap, patch(rec, "Ask for 3.", fix_old="stale")]}, 1,
         ["fix_old", "numeral", "X3"])
    case("a span id the brief lacks", {"patches": [dict(patch(rec, "x"), span_id="rec.9.why.0")]}, 1, ["span"])
    case("two patches on one span", {"patches": [patch(rec, "Ask Miniclip."), patch(rec, "Ask them.")]}, 1, ["span"])
    case("a patch off the schema (no finding_ids)", {"patches": [dict(patch(rec, "x"), finding_ids=[])]}, 1, ["shape"])

    short = " ".join(lede["t"].split()[:3])
    case("a fix inside the cap, cited numeral: applied", {"patches": [patch(lede, short, ["C-133"]),
                                                                      patch(rec, "Ask for 3 returns.", ["C-037", "C-133"])]},
         0, [], lambda b: span_t(b, lede["id"]) == [short] and span_t(b, rec["id"]) == ["Ask for 3 returns."]
         and [s.get("c") for _, a in BC.span_arrays(b) for s in a if s.get("id") == rec["id"]] == [["C-037", "C-133"]])
    case("one ID in c is written as a string", [patch(rec, "Ask for 3 returns.", ["C-037"])], 0, [],
         lambda b: [s.get("c") for _, a in BC.span_arrays(b) for s in a if s.get("id") == rec["id"]] == ["C-037"])
    body = brief["quick_take"][0]["body"]
    if len(body) >= 2:
        case("an empty fix_new deletes the span", {"patches": [patch(body[-1], "")]}, 0, [],
             lambda b: span_t(b, body[-1]["id"]) == [] and len(b["quick_take"][0]["body"]) == len(body) - 1)
    case("an empty list changes nothing", {"patches": []}, 0, [], lambda b: b == brief)

    for label, doc, want in (("--out: the applied brief goes to PATH, brief.json untouched",
                              {"patches": [patch(rec, "Ask for 3 returns.", ["C-037"])]}, 0),
                             ("--out on CAP1: refused, neither file written", {"patches": [cap]}, 1)):
        n[0] += 1
        with tempfile.TemporaryDirectory() as tmp:
            bp, pp, op = (pathlib.Path(tmp) / f for f in ("brief.json", "patches.json", "proposed.json"))
            before = json.dumps(brief)
            bp.write_text(before, encoding="utf-8")
            pp.write_text(json.dumps(doc), encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                code = main(["apply-patches.py", str(pp), str(bp), str(root), "--out", str(op)])
            ok = code == want and bp.read_text(encoding="utf-8") == before and op.exists() == (want == 0)
            if ok and want == 0:
                ok = span_t(json.loads(op.read_text(encoding="utf-8")), rec["id"]) == ["Ask for 3 returns."]
        if not ok:
            fails.append("%s: exit %s" % (label, code))

    dep = {"slot": "quick-take", "id": "C-133", "reason": "KR-H forced it off"}
    for label, out in (("departures under --out land in <out stem>.departures.json", "proposed.json"),
                       ("departures applied in place join the root's departures.json", None)):
        n[0] += 1
        with tempfile.TemporaryDirectory() as tmp:
            r = pathlib.Path(tmp) / "root"
            shutil.copytree(root, r, symlinks=True)
            (r / "departures.json").write_text(json.dumps({"departures": [dict(dep, id="C-001")]}), encoding="utf-8")
            bp, pp = r / "brief.json", r / "patches.json"
            bp.write_text(json.dumps(brief), encoding="utf-8")
            pp.write_text(json.dumps({"patches": [patch(rec, "Ask for 3 returns.", ["C-037"])], "departures": [dep]}),
                          encoding="utf-8")
            argv = ["apply-patches.py", str(pp), str(bp), str(r)] + (["--out", str(r / out)] if out else [])
            with contextlib.redirect_stderr(io.StringIO()) as err, contextlib.redirect_stdout(io.StringIO()):
                code = main(argv)
            side = r / ("proposed.departures.json" if out else "departures.json")
            got = json.loads(side.read_text(encoding="utf-8")).get("departures") if side.is_file() else None
            base = json.loads((r / "departures.json").read_text(encoding="utf-8"))["departures"]
        if code != 0 or [d["id"] for d in got or []] != ["C-001", "C-133"] or (out and len(base) != 1):
            fails.append("%s: exit %s, %s %s" % (label, code, got, err.getvalue()[-200:]))

    with tempfile.TemporaryDirectory() as tmp:
        bp, pp = pathlib.Path(tmp) / "brief.json", pathlib.Path(tmp) / "patches.json"
        bp.write_text(json.dumps(brief), encoding="utf-8")
        pp.write_text(json.dumps({"fixes": []}), encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()):
            code = main(["apply-patches.py", str(pp), str(bp), str(root)])
        n[0] += 1
        if code != 2:
            fails.append("a root that is neither form: exit %s, want 2" % code)

    for f in fails:
        sys.stderr.write("SELFTEST FAIL: %s\n" % f)
    if fails:
        sys.stderr.write("SELFTEST RED (%d of %d)\n" % (len(fails), n[0]))
        return 1
    sys.stdout.write("SELFTEST OK (%d cases)\n" % n[0])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
