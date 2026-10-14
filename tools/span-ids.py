#!/usr/bin/env python3
"""The span-ids node: type an authored brief.json the way the page's gates read it.

WHY THIS EXISTS. While stage 7 is wrapped (design.md section 8, S5), its author writes brief.json
in the pre-S2 shape: no span `id`, no quick-take `slot`, no `cmp` on a comparison half, no `dates`.
S2's schema requires the first two, S3's KR-H and X2 read the last two, and publish.py refuses a page
whose `dates.page` is not today (D4). This node assigns them in code, reusing backfill-globex.py's
assign_span_ids, assign_slots and assign_cmp exactly as tools/fixture-test.py types its fixtures:
slots on the ICP rows stage 6 allotted, cmp on brief-check's own known rows. Ids, slots and cmp
already set are kept, so the step is idempotent and an author may run it too.

DATES. `dates.page` is today in Europe/London. `dates.evidence` is the first and last fetch day of
the pages web.py counts (pages/index.tsv rows with status 200 or 000, less pages read only for a
logo), the window web.py's D4 check compares. `run_date` stays: the schema still requires it.

USAGE
  span-ids.py BRIEF_ROOT          type BRIEF_ROOT/brief.json in place (the span-ids node)
  span-ids.py --check BRIEF_ROOT  brief-check on the brief as this would type it; writes nothing in
                                  BRIEF_ROOT (the wrapped author's gate, so its brief-check reds
                                  come back to the author as a repair)
  span-ids.py --check BRIEF_ROOT --brief FILE
                                  the same on BRIEF_ROOT/FILE: the arbiter's gate grades its patched
                                  copy, brief-proposed.json, typed as final-build will type it

EXIT CODES. 0 typed, or --check green. 1 --check red (brief-check's findings on stderr). 2 could
not run: usage, or brief.json, claims.jsonl or pages/index.tsv unreadable.

PRECONDITION: none. Stdlib only, offline.
"""
import csv
import datetime
import importlib.util
import json
import pathlib
import sys
import tempfile

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parent.parent
TZ = "Europe/London"


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def today():
    from zoneinfo import ZoneInfo
    return datetime.datetime.now(ZoneInfo(TZ)).date().isoformat()


def evidence_days(root):
    """The fetch days of the pages web.py counts: build/web.py render()'s `days`."""
    pages = list(csv.DictReader((root / "pages" / "index.tsv").open(encoding="utf-8"), delimiter="\t"))
    ledger = [json.loads(l) for l in (root / "claims.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    logos = []
    if (root / "logos" / "logos.json").is_file():
        logos = json.loads((root / "logos" / "logos.json").read_text(encoding="utf-8"))
    backs = {c.get("url") for c in ledger}
    logo_only = {r.get("page_url") for r in logos if isinstance(r, dict)} - backs
    ok = [p for p in pages if p.get("status") in ("200", "000")]
    return sorted({p["fetched_at"][:10] for p in ok if p["url"] not in logo_only or p.get("final_url") in backs})


def typed(root, bc, bf, name="brief.json"):
    """brief.json (or `name`) as the node writes it."""
    path = root / name
    ctx = bc.Ctx(path, root, bc.load_schema(), brief=json.loads(path.read_text(encoding="utf-8")))
    known = {cid: ctx.known(cid) for cid in ctx.rows}
    icp = bc.allotted_slots(root).get("icp", [])
    brief = bf.assign_cmp(bf.assign_slots(bf.assign_span_ids(ctx.brief), icp), known)
    days = evidence_days(root)
    if days:
        brief["dates"] = {"evidence": {"from": days[0], "to": days[-1]}, "page": today()}
    return brief


def main(argv):
    args = argv[1:]
    check = args[:1] == ["--check"]
    if check:
        args = args[1:]
    name = "brief.json"
    if check and len(args) == 3 and args[1] == "--brief" and "/" not in args[2]:
        name, args = args[2], args[:1]
    if len(args) != 1 or args[0].startswith("-"):
        sys.stderr.write(__doc__)
        return 2
    root = pathlib.Path(args[0])
    for need in (name, "claims.jsonl", "pages/index.tsv"):
        if not (root / need).is_file():
            sys.stderr.write("span-ids: no file to read at %s\n" % (root / need))
            return 2
    bc, bf = load("brief_check", "tools/brief-check.py"), load("backfill_globex", "tools/backfill-globex.py")
    try:
        brief = typed(root, bc, bf, name)
    except (OSError, ValueError, KeyError) as exc:
        sys.stderr.write("span-ids: cannot type %s: %s: %s\n" % (root / "brief.json", type(exc).__name__, exc))
        return 2
    text = json.dumps(brief, indent=1, ensure_ascii=False) + "\n"
    if check:
        with tempfile.TemporaryDirectory(prefix="span-ids-") as d:
            copy = pathlib.Path(d) / "brief.json"
            copy.write_text(text, encoding="utf-8")
            side = root / (pathlib.Path(name).stem + ".departures.json")
            if name != "brief.json" and side.is_file():  # apply-patches --out's departures (A1)
                (pathlib.Path(d) / "brief.departures.json").write_text(side.read_text(encoding="utf-8"),
                                                                       encoding="utf-8")
            return bc.main(["brief-check.py", str(copy), str(root)])
    (root / "brief.json").write_text(text, encoding="utf-8")
    spans = sum(len(arr) for _, arr in bf.span_fields(brief))
    print("SPAN-IDS OK %s: %d spans with ids, slots %s, %d cmp, dates %s" % (
        root / "brief.json", spans, [p.get("slot") for p in brief.get("quick_take", [])],
        sum(1 for _, arr in bf.span_fields(brief) for s in arr if isinstance(s, dict) and "cmp" in s),
        json.dumps(brief.get("dates"))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
