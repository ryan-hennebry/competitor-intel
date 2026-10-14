#!/usr/bin/env python3
"""Rulings as rows with fixtures: `quality-bar/rulings.tsv`, and the check that each still bites.

WHY THIS EXISTS. A lesson the operator rules in prose recurs (design § 2, R1 and R4). Here a ruling is a
tab-separated row, and it names the fixtures that prove it: rows in
`quality-bar/fixtures/<set>/fixtures.jsonl`, graded by `tools/fixture-test.py`. A ruling whose every
fixture has gone green is a ruling nothing enforces, and `check` reds it.

THE FILE. `quality-bar/rulings.tsv`, header exactly
  id  class  test  example  scope  source  fixture_id  status
`class` is the kind of lesson: `constraint` rows also seed a run's `reader.json` `constraints[]`,
which the FEASIBILITY test reads. `fixture_id` is a comma-separated list of fixture ids. `status` is
`active` or `retired`; only an active ruling is checked.

COMMANDS
  rule.py add --set NAME --id ID --class C --test T --example E --scope S --source SRC
              --fixture JSON [--fixture JSON ...] [--status active|retired]
      Appends one ruling row, and each --fixture (one JSON object, the fixture-test row shape) as a
      line of quality-bar/fixtures/NAME/fixtures.jsonl. The row's fixture_id lists their ids.
      Refuses a ruling id or fixture id already in use, a field holding a tab or newline, and a
      fixture without an id, an owner, and the rules or screen its owner needs. Then re-warms the
      bar cache (`tools/bar-cache.py warm`), since rulings.tsv is in its key; INTEL_BAR_WARM=0 skips.
  rule.py check
      Runs `fixture-test.py --json` and exits 1 naming each active ruling with no red fixture, or
      naming a fixture id that no set holds.
  rule.py --selftest

EXIT CODES. 0 green. 1 findings (check) or a refused add. 2 bad usage, an unreadable or malformed
rulings file, or fixture-test unable to run.

PRECONDITION: none. Stdlib only, offline.
"""

import argparse
import json
import pathlib
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parent.parent
RULINGS = ROOT / "quality-bar/rulings.tsv"
SETS = ROOT / "quality-bar/fixtures"
FIXTURE_TEST = ROOT / "tools/fixture-test.py"
HEADER = ["id", "class", "test", "example", "scope", "source", "fixture_id", "status"]
STATUSES = ("active", "retired")


class Malformed(Exception):
    """The rulings file cannot be read as rulings: exit 2."""


def read_rulings(path=RULINGS):
    try:
        lines = pathlib.Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise Malformed("cannot read %s (%s)" % (path, exc))
    if not lines or lines[0].split("\t") != HEADER:
        raise Malformed("%s: the header is not %s" % (path, "<TAB>".join(HEADER)))
    rows = []
    for n, line in enumerate(lines[1:], 2):
        cells = line.split("\t")
        if len(cells) != len(HEADER):
            raise Malformed("%s:%d has %d cells, want %d" % (path, n, len(cells), len(HEADER)))
        rows.append(dict(zip(HEADER, cells), line=n))
    return rows


def fixture_ids(row):
    return [f.strip() for f in row["fixture_id"].split(",") if f.strip()]


def check_rulings(rows, results):
    """Findings for rulings against fixture-test's rows ({id: status})."""
    out, seen = [], set()
    for r in rows:
        if r["id"] in seen:
            out.append("%s: ruling id used twice" % r["id"])
        seen.add(r["id"])
        if r["status"] not in STATUSES:
            out.append("%s: status %r is not one of %s" % (r["id"], r["status"], ", ".join(STATUSES)))
            continue
        if r["status"] != "active":
            continue
        ids = fixture_ids(r)
        if not ids:
            out.append("%s: names no fixture" % r["id"])
            continue
        unknown = [i for i in ids if i not in results]
        if unknown:
            out.append("%s: no fixture set holds %s" % (r["id"], ", ".join(unknown)))
        red = [i for i in ids if results.get(i) == "red"]
        if not red:
            out.append("%s: no red fixture among %s (%s)" % (
                r["id"], ", ".join(ids), ", ".join("%s %s" % (i, results.get(i, "absent")) for i in ids)))
    return out


def fixture_results():
    """{id: status} from `fixture-test.py --json`; exit 1 there is a verdict, not a failure here."""
    proc = subprocess.run([sys.executable, str(FIXTURE_TEST), "--json"], capture_output=True, text=True)
    if proc.returncode not in (0, 1):
        raise Malformed("fixture-test.py exited %d: %s" % (proc.returncode, proc.stderr.strip()))
    try:
        data = json.loads(proc.stdout)
    except ValueError as exc:
        raise Malformed("fixture-test.py --json printed no JSON (%s)" % exc)
    return {r["id"]: r["status"] for r in data["rows"]}


def cmd_check(rulings=RULINGS, results=None):
    rows = read_rulings(rulings)
    results = fixture_results() if results is None else results
    findings = check_rulings(rows, results)
    for f in findings:
        sys.stderr.write("RULE FINDING  %s\n" % f)
    active = sum(1 for r in rows if r["status"] == "active")
    if findings:
        sys.stderr.write("RULE-CHECK RED (%d finding%s, %d active ruling%s)\n"
                         % (len(findings), "" if len(findings) == 1 else "s", active, "" if active == 1 else "s"))
        return 1
    sys.stdout.write("RULE-CHECK OK (%d active ruling%s, each with a red fixture)\n" % (active, "" if active == 1 else "s"))
    return 0


def refuse(msg):
    sys.stderr.write("RULE ADD REFUSED  %s\n" % msg)
    return 1


def cmd_add(a, rulings=RULINGS, sets=SETS):
    rows = read_rulings(rulings)
    fields = {"id": a.id, "class": a.klass, "test": a.test, "example": a.example, "scope": a.scope,
              "source": a.source, "status": a.status}
    for k, v in fields.items():
        if not v.strip() or "\t" in v or "\n" in v:
            return refuse("%s is empty or holds a tab or newline" % k)
    if a.id in {r["id"] for r in rows}:
        return refuse("ruling id %s is already in %s" % (a.id, pathlib.Path(rulings).name))
    if not a.set or "/" in a.set or a.set.startswith("."):
        return refuse("--set names one folder under quality-bar/fixtures/")
    target = pathlib.Path(sets) / a.set / "fixtures.jsonl"
    taken = set()
    for p in pathlib.Path(sets).glob("*/*.jsonl"):
        taken |= {json.loads(l).get("id") for l in p.read_text(encoding="utf-8").splitlines() if l.strip()}
    new = []
    for raw in a.fixture:
        try:
            fx = json.loads(raw)
        except ValueError as exc:
            return refuse("--fixture is not JSON (%s)" % exc)
        if not isinstance(fx, dict) or not isinstance(fx.get("id"), str) or not fx["id"]:
            return refuse("a fixture needs a string id")
        if fx["id"] in taken or fx["id"] in {f["id"] for f in new}:
            return refuse("fixture id %s is already in use" % fx["id"])
        owner = fx.get("owner")
        parts = owner.split("+") if isinstance(owner, str) else []
        if owner not in ("gate", "screen", "gate+screen", "line-screen"):
            return refuse("fixture %s: owner %r is not gate, screen, gate+screen or line-screen" % (fx["id"], owner))
        if ("gate" in parts) != bool(fx.get("rules")) or ("screen" in parts) != bool(fx.get("screen")):
            return refuse("fixture %s: owner %r needs exactly its rules or screen" % (fx["id"], owner))
        new.append(fx)
    if not new:
        return refuse("a ruling needs at least one --fixture")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        for fx in new:
            fh.write(json.dumps(fx, ensure_ascii=False) + "\n")
    fields["fixture_id"] = ",".join(f["id"] for f in new)
    with pathlib.Path(rulings).open("a", encoding="utf-8") as fh:
        fh.write("\t".join(fields[k] for k in HEADER) + "\n")
    shown = target.relative_to(ROOT) if ROOT in target.parents else target
    sys.stdout.write("RULE ADDED  %s with fixture%s %s in %s\n" % (
        a.id, "" if len(new) == 1 else "s", fields["fixture_id"], shown))
    return 0


# --- selftest -------------------------------------------------------------------------------------
def selftest():
    fails, n = [], 0

    def case(name, ok, why=""):
        nonlocal n
        n += 1
        sys.stdout.write("%s %s%s\n" % ("PASS" if ok else "FAIL", name, "" if ok else " -- " + why))
        if not ok:
            fails.append(name)

    def row(rid, fx, status="active"):
        return dict(zip(HEADER, [rid, "verdict", "t", "e", "s", "src", fx, status]))

    res = {"A1": "red", "A2": "green", "B1": "green", "P1": "pending"}
    case("a ruling with one red fixture is green", check_rulings([row("R", "A2,A1")], res) == [])
    case("a ruling whose fixtures are all green is red", len(check_rulings([row("R", "A2,B1")], res)) == 1)
    case("a pending line-screen fixture is not red", len(check_rulings([row("R", "P1")], res)) == 1)
    case("an unknown fixture id is a finding", any("no fixture set holds" in f for f in check_rulings([row("R", "A1,Z9")], res)))
    case("a retired ruling is not checked", check_rulings([row("R", "B1", "retired")], res) == [])
    case("an unknown status is a finding", len(check_rulings([row("R", "A1", "actve")], res)) == 1)
    case("a ruling naming no fixture is a finding", len(check_rulings([row("R", "")], res)) == 1)
    case("a ruling id twice is a finding", len(check_rulings([row("R", "A1"), row("R", "A1")], res)) == 1)

    with tempfile.TemporaryDirectory() as tmp:
        t = pathlib.Path(tmp)
        rulings, sets = t / "rulings.tsv", t / "fixtures"
        rulings.write_text("\t".join(HEADER) + "\n", encoding="utf-8")
        (sets / "old").mkdir(parents=True)
        (sets / "old" / "fixtures.jsonl").write_text(json.dumps({"id": "F0", "owner": "gate", "rules": ["X"]}) + "\n")
        parser = build_parser()
        fx = json.dumps({"id": "F1", "set": "s", "owner": "gate", "rules": ["KR-H"], "brief": "b.json",
                         "block": "quick_take/0/lede", "spans": [0]})
        base = ["add", "--set", "new", "--id", "R9", "--class", "constraint", "--test", "a test", "--example", "an example",
                "--scope", "lines", "--source", "the operator, today"]
        quiet = lambda argv: _quiet(lambda: cmd_add(parser.parse_args(argv), rulings, sets))  # noqa: E731
        code = quiet(base + ["--fixture", fx])
        got = read_rulings(rulings)
        lines = (sets / "new" / "fixtures.jsonl").read_text().splitlines()
        case("add appends one row and one fixture line", code == 0 and len(got) == 1 and got[0]["fixture_id"] == "F1"
             and got[0]["status"] == "active" and json.loads(lines[0])["id"] == "F1", "exit %d rows %s" % (code, got))
        case("add refuses a ruling id in use", quiet(base + ["--fixture", fx.replace("F1", "F2")]) == 1
             and len(read_rulings(rulings)) == 1)
        other = base[:4] + ["R10"] + base[5:]
        case("add refuses a fixture id in another set", quiet(other + ["--fixture", fx.replace("F1", "F0")]) == 1)
        case("add refuses a fixture whose owner lacks its rules",
             quiet(other + ["--fixture", json.dumps({"id": "F3", "owner": "gate", "rules": []})]) == 1)
        case("add refuses a tab in a field", quiet(other[:8] + ["a\ttab"] + other[9:] + ["--fixture", fx.replace("F1", "F4")]) == 1)
        case("nothing written by a refused add", len(read_rulings(rulings)) == 1
             and len((sets / "new" / "fixtures.jsonl").read_text().splitlines()) == 1)
        rulings.write_text("id\tclass\n", encoding="utf-8")
        try:
            read_rulings(rulings)
            case("a wrong header is malformed", False, "read")
        except Malformed:
            case("a wrong header is malformed", True)

    if fails:
        sys.stdout.write("SELFTEST RED (%d of %d cases failed)\n" % (len(fails), n))
        return 1
    sys.stdout.write("SELFTEST OK (%d cases)\n" % n)
    return 0


def _quiet(fn):
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn()


def build_parser():
    p = argparse.ArgumentParser(prog="rule.py", add_help=True)
    sub = p.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add")
    add.add_argument("--set", required=True)
    add.add_argument("--id", required=True)
    add.add_argument("--class", dest="klass", required=True)
    add.add_argument("--test", required=True)
    add.add_argument("--example", required=True)
    add.add_argument("--scope", required=True)
    add.add_argument("--source", required=True)
    add.add_argument("--status", default="active", choices=STATUSES)
    add.add_argument("--fixture", action="append", default=[], required=True)
    sub.add_parser("check")
    return p


def main(argv):
    if argv[1:] == ["--selftest"]:
        return selftest()
    try:
        a = build_parser().parse_args(argv[1:])
    except SystemExit as exc:
        return 2 if exc.code else 0
    try:
        if a.cmd == "check":
            return cmd_check()
        code = cmd_add(a)
    except Malformed as exc:
        sys.stderr.write("RULE ERROR  %s\n" % exc)
        return 2
    if code == 0:
        # rulings.tsv is in the bar cache's key, so this add made the cached bar stale: re-warm it
        # now, off the run, so the next launch hits (Globex design § 10 Q2). A failed warm costs the
        # next run one bar-gen node, never this add.
        subprocess.run([sys.executable, str(ROOT / "tools" / "bar-cache.py"), "warm"], cwd=ROOT,
                       stdin=subprocess.DEVNULL)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
