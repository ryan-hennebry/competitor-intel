#!/usr/bin/env python3
"""The changed spans between two briefs, keyed by stable span id and span hash.

WHY THIS EXISTS. Today every closure binds to the whole file: one unrelated edit re-stamps every
ledger row and re-runs the whole verifier (f-dataflow § 5). With a stable span `id` (S2) and a span
hash, span-verify reads only the spans a patch changed, an unchanged hash keeps its PASS row in
verify.jsonl, and the verdict node checks every current hash has one (design.md § 2 R2, § 3).

THE SPAN HASH is sha256 of the span's canonical JSON with `id` left out: keys sorted, no spaces,
UTF-8 (`ensure_ascii=False`). So t, c, q, g and cmp are the span; moving it keeps its id, and any
edit to its text or its rows is a new hash. The spans are the ones assign_span_ids gives ids to
(backfill-globex.py span_fields: quick take, recommendations, moves, open questions, legend), so the
two files read one set.

OUTPUT. One line per changed span, `<span_id>\t<old hash>\t<new hash>`, in B's page order, then the
spans only A holds. `-` stands for a side that lacks the span: `-` old is a span added, `-` new a
span removed. Nothing printed means nothing changed. `--hashes` prints `<span_id>\t<hash>` for every
span of one brief, the rows verify.jsonl and the verdict node key on.

  python3 tools/span-diff.py A.json B.json     the spans that differ from A to B
  python3 tools/span-diff.py --hashes B.json   every span's id and hash
  python3 tools/span-diff.py --selftest        offline: synthetic cases, then Globex's brief-08.json
                                               to brief.json with backfilled ids

EXIT CODES. 0 listed (an empty list included). 1 --selftest red. 2 could not run: usage, an
unreadable brief, a span with no id, or one id on two spans.

PRECONDITION: none. Stdlib only, offline.
"""

import copy
import hashlib
import importlib.util
import io
import json
import pathlib
import contextlib
import sys

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parent.parent
SYNTHETIC = ROOT / "tools/fixtures/web/synthetic.json"
GLOBEX = ROOT / "quality-bar/fixtures/globex/run"
HASH_LEN = 64


class Untyped(Exception):
    """A brief whose spans cannot be keyed: exit 2."""


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_BF = []


def backfill():
    if not _BF:
        _BF.append(_load("backfill_globex", "tools/backfill-globex.py"))
    return _BF[0]


def span_hash(span):
    """sha256 of the span's canonical JSON, id excluded (verify-row.schema.json's span_hash)."""
    body = {k: v for k, v in span.items() if k != "id"}
    text = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def spans(brief):
    """{span_id: span} in page order. Raises Untyped on a span with no id or an id used twice."""
    out = {}
    for key, arr in backfill().span_fields(brief):
        for j, s in enumerate(arr if isinstance(arr, list) else []):
            if not isinstance(s, dict) or not isinstance(s.get("id"), str):
                raise Untyped("%s[%d] has no span id; type the brief first (tools/span-ids.py)" % (key, j))
            if s["id"] in out:
                raise Untyped("span id %r is on two spans" % s["id"])
            out[s["id"]] = s
    return out


def hashes(brief):
    """{span_id: span hash} in page order."""
    return {i: span_hash(s) for i, s in spans(brief).items()}


def diff(a, b):
    """[(span_id, old hash or None, new hash or None)] for every span whose hash differs from brief
    a to brief b: b's page order, then the spans only a holds."""
    ha, hb = hashes(a), hashes(b)
    out = [(i, ha.get(i), h) for i, h in hb.items() if ha.get(i) != h]
    return out + [(i, h, None) for i, h in ha.items() if i not in hb]


def read(path):
    try:
        brief = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Untyped("cannot read %s (%s)" % (path, exc))
    if not isinstance(brief, dict):
        raise Untyped("%s is not a JSON object" % path)
    return brief


def main(argv):
    args = argv[1:]
    if args == ["--selftest"]:
        return selftest()
    try:
        if len(args) == 2 and args[0] == "--hashes":
            for i, h in hashes(read(args[1])).items():
                sys.stdout.write("%s\t%s\n" % (i, h))
            return 0
        if len(args) == 2 and not any(a.startswith("-") for a in args):
            for i, old, new in diff(read(args[0]), read(args[1])):
                sys.stdout.write("%s\t%s\t%s\n" % (i, old or "-", new or "-"))
            return 0
    except Untyped as exc:
        sys.stderr.write("span-diff: %s\n" % exc)
        return 2
    sys.stderr.write(__doc__)
    return 2


# --- selftest -------------------------------------------------------------------------------------
def selftest():
    fails, n = [], [0]

    def case(label, ok, got):
        n[0] += 1
        if not ok:
            fails.append("%s: got %r" % (label, got))

    base = json.loads(SYNTHETIC.read_text(encoding="utf-8"))
    ids = list(spans(base))
    case("synthetic brief has spans", len(ids) >= 5, len(ids))
    case("A to A lists nothing", diff(base, copy.deepcopy(base)) == [], diff(base, base))

    edited = copy.deepcopy(base)
    edited["quick_take"][0]["lede"][0]["t"] += " Still."
    got = diff(base, edited)
    case("one span's t edited lists exactly that span", [g[0] for g in got] == ["qt.0.lede.0"]
         and all(g[1] and g[2] and g[1] != g[2] for g in got), got)

    recited = copy.deepcopy(base)
    recited["recommendations"][0]["why"][0]["c"] = "C-999"
    got = diff(base, recited)
    case("a span's rows changed lists that span", [g[0] for g in got] == [base["recommendations"][0]["why"][0]["id"]], got)

    moved = copy.deepcopy(base)  # an id is identity, not place: swapping two spans' places changes no hash
    arr = moved["recommendations"][0]["why"]
    if len(arr) >= 2:
        arr[0], arr[1] = arr[1], arr[0]
        case("two spans swapped in place list nothing", diff(base, moved) == [], diff(base, moved))

    added = copy.deepcopy(base)
    added["quick_take"][0]["body"].append({"id": "qt.0.body.99", "t": " New.", "c": None})
    case("an added span lists with old -", diff(base, added) == [("qt.0.body.99", None, span_hash({"t": " New.", "c": None}))],
         diff(base, added))

    removed = copy.deepcopy(base)
    gone = removed["quick_take"][0]["body"].pop()
    case("a removed span lists with new -", diff(base, removed) == [(gone["id"], span_hash(gone), None)], diff(base, removed))

    case("the hash leaves id out", span_hash({"id": "qt.0.lede.0", "t": "x", "c": None})
         == span_hash({"id": "rec.1.why.2", "t": "x", "c": None}), None)
    case("the hash keys sorted", span_hash({"t": "x", "c": "C-001"}) == span_hash({"c": "C-001", "t": "x"}), None)

    untyped = copy.deepcopy(base)
    del untyped["quick_take"][0]["lede"][0]["id"]
    twice = copy.deepcopy(base)
    twice["quick_take"][0]["body"][0]["id"] = twice["quick_take"][0]["lede"][0]["id"]
    for label, bad in (("a span with no id", untyped), ("one id on two spans", twice)):
        try:
            diff(base, bad)
            case(label + " is exit 2", False, "no Untyped")
        except Untyped:
            case(label + " is exit 2", True, None)

    # Globex: brief-08.json (the author's page before the fixer) to brief.json (the shipped page),
    # each with ids from backfill-globex.py assign_span_ids. The oracle compares span dicts directly,
    # not hashes: a listed span differs or exists on one side only, and every unlisted span is equal.
    bf = backfill()
    a = bf.assign_span_ids(json.loads((GLOBEX / "brief-08.json").read_text(encoding="utf-8")))
    b = bf.assign_span_ids(json.loads((GLOBEX / "brief.json").read_text(encoding="utf-8")))
    sa, sb = spans(a), spans(b)
    strip = lambda s: {k: v for k, v in s.items() if k != "id"} if s else None  # noqa: E731
    want = [i for i in list(sb) + [i for i in sa if i not in sb] if strip(sa.get(i)) != strip(sb.get(i))]
    got = diff(a, b)
    case("Globex brief-08 to brief: exactly the spans whose content differs, in order", [g[0] for g in got] == want,
         ([g[0] for g in got], want))
    same = [i for i in sb if i in sa and strip(sa[i]) == strip(sb[i])]
    case("Globex brief-08 to brief: unchanged spans exist and none is listed",
         bool(same) and not set(same) & {g[0] for g in got}, same)
    case("Globex brief-08 to brief: removed spans list with new -",
         all((g[2] is None) == (g[0] not in sb) and (g[1] is None) == (g[0] not in sa) for g in got), got)

    # The CLI: one line per changed span; --hashes one line per span, each hash 64 hex.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        pa, pb = pathlib.Path(tmp) / "a.json", pathlib.Path(tmp) / "b.json"
        pa.write_text(json.dumps(a, ensure_ascii=False), encoding="utf-8")
        pb.write_text(json.dumps(b, ensure_ascii=False), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = main(["span-diff.py", str(pa), str(pb)])
        lines = out.getvalue().splitlines()
        case("CLI diff exit 0, one line per changed span", code == 0 and [l.split("\t")[0] for l in lines] == want,
             (code, lines[:3]))
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = main(["span-diff.py", "--hashes", str(pb)])
        rows = [l.split("\t") for l in out.getvalue().splitlines()]
        case("CLI --hashes: every span, id and a 64-hex hash", code == 0 and [r[0] for r in rows] == list(sb)
             and all(len(r) == 2 and len(r[1]) == HASH_LEN and int(r[1], 16) >= 0 for r in rows), rows[:2])
        pu = pathlib.Path(tmp) / "u.json"
        pu.write_text(json.dumps(untyped), encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()):
            code = main(["span-diff.py", str(pa), str(pu)])
        case("CLI on an untyped brief exits 2", code == 2, code)

    for f in fails:
        sys.stderr.write("SELFTEST FAIL: %s\n" % f)
    if fails:
        sys.stderr.write("SELFTEST RED (%d of %d)\n" % (len(fails), n[0]))
        return 1
    sys.stdout.write("SELFTEST OK (%d cases; Globex brief-08 to brief: %d of %d spans changed)\n"
                     % (n[0], len(want), len(set(sa) | set(sb))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
