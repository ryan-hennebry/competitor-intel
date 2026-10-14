#!/usr/bin/env python3
"""The verdict node: verify.jsonl and the gate exits in, correctness-<sha>.md out.

WHY THIS EXISTS. The final verifier used to re-read the whole page after every edit and bind its
verdict to the whole file (f-dataflow § 5). Now span-verify writes one verify.jsonl row per span
hash it reads, an unchanged hash keeps its PASS, and this code node passes the page only when every
span hash in brief.json has a PASS row and every gate exited 0 (design.md § 3, node `verdict`).

THE RULE. For each span of brief.json (tools/span-diff.py's span set and span hash), the last
verify.jsonl row naming that span id at that hash decides: PASS passes it; FAIL, or no row at all,
is a refusal. A PASS for an older hash of the span counts for nothing. Every `--gate NAME=EXIT`
must be 0.

OUTPUT. On a pass, `$BRIEF_ROOT/correctness-<sha256(brief.json)>.md`, the file publish.py P1 reads:
  Verdict: PASS
  PAGE: <sha256(web/index.html)>
then one `SPANS:` line and a `GATE <name>: 0` line per gate. On a refusal it writes nothing and
prints one stderr line per refusal: `VERDICT REFUSED <span_id> <hash12>: <why>` or
`VERDICT REFUSED gate <name> exited <n>`.

  python3 tools/verdict.py BRIEF_ROOT [--gate NAME=EXIT ...] [--gate-record PATH ...] [--stop]
`--gate-record` reads a sentinel record the runner wrote (`<run root>/state/done/<node>`, JSON with
`node` and `gate_exit`) as the gate NAME=EXIT of that node, so the verdict node grades the gate
exit the runner recorded for final-build rather than one typed into its command. `--stop` ends a
refusal's stderr with one `STOP unverified: <span ids>; <gates>` line, the runner's typed stop, so a
run that ends at verdict-final names the spans on its report's second line (S13).
  python3 tools/verdict.py --selftest

EXIT CODES. 0 pass, file written. 1 refused. 2 could not run: usage, no brief.json, verify.jsonl or
web/index.html, a verify.jsonl row off references/schemas/verify-row.schema.json, or an untyped
brief.

PRECONDITION: none. Stdlib only, offline.
"""

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import pathlib
import re
import sys
import tempfile

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parent.parent
ROW_SCHEMA = ROOT / "references/schemas/verify-row.schema.json"
SYNTHETIC = ROOT / "tools/fixtures/web/synthetic.json"
GATE_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)=(-?[0-9]+)$")


class CannotRun(Exception):
    """Exit 2."""


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SD = _load("span_diff", "tools/span-diff.py")
SCHEMA = _load("schema", "tools/schema.py")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_rows(path):
    """verify.jsonl's rows in file order. Raises CannotRun on a row off the schema."""
    try:
        bad = SCHEMA.check(ROW_SCHEMA, path)
        found, _ = SCHEMA.instances(path)
    except (OSError, SCHEMA.SchemaError) as exc:
        raise CannotRun("cannot read %s (%s)" % (path, exc))
    if bad and bad != ["%s: holds no instance" % path]:
        raise CannotRun("verify.jsonl is off its schema: " + "; ".join(bad[:3]))
    return [inst for _, inst in found]


def refusals(brief, rows, gates):
    """Every refusal line for this brief, these verify rows and these (name, exit) gates."""
    last = {}
    for r in rows:
        last[(r["span_id"], r["span_hash"])] = r
    out = []
    for sid, h in SD.hashes(brief).items():
        r = last.get((sid, h))
        if r is None:
            out.append("%s %s: no verify.jsonl row at this hash" % (sid, h[:12]))
        elif r["verdict"] != "PASS":
            out.append("%s %s: last row is %s by %s (%s)" % (sid, h[:12], r["verdict"], r["by"], r["note"]))
    out += ["gate %s exited %d" % (name, code) for name, code in gates if code != 0]
    return out


def run(root, gates):
    """(refusal lines, path written or None). Raises CannotRun."""
    root = pathlib.Path(root)
    for need in ("brief.json", "verify.jsonl", "web/index.html"):
        if not (root / need).is_file():
            raise CannotRun("no file to read at %s" % (root / need))
    raw = (root / "brief.json").read_bytes()
    try:
        brief = json.loads(raw)
        if not isinstance(brief, dict):
            raise ValueError("not a JSON object")
        refused = refusals(brief, read_rows(root / "verify.jsonl"), gates)
    except (ValueError, SD.Untyped) as exc:
        raise CannotRun("brief.json: %s" % exc)
    if refused:
        return refused, None
    n = len(SD.spans(brief))
    out = root / ("correctness-%s.md" % sha(raw))
    lines = ["Verdict: PASS", "PAGE: %s" % sha((root / "web/index.html").read_bytes()),
             "SPANS: %d span hashes, each with a PASS row in verify.jsonl" % n]
    lines += ["GATE %s: %d" % g for g in gates]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return [], out


def main(argv):
    args = argv[1:]
    if args == ["--selftest"]:
        return selftest()
    if not args or args[0].startswith("-"):
        sys.stderr.write(__doc__)
        return 2
    root, gates, rest = args[0], [], args[1:]
    stop = "--stop" in rest
    rest = [a for a in rest if a != "--stop"]
    while rest:
        if rest[0] == "--gate-record" and len(rest) > 1:
            try:
                rec = json.loads(pathlib.Path(rest[1]).read_text(encoding="utf-8"))
                gates.append((str(rec["node"]), int(rec["gate_exit"])))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                sys.stderr.write("verdict: --gate-record %s is no sentinel record (%s)\n" % (rest[1], exc))
                return 2
            rest = rest[2:]
            continue
        m = GATE_RE.match(rest[1]) if rest[0] == "--gate" and len(rest) > 1 else None
        if not m:
            sys.stderr.write(__doc__)
            return 2
        gates.append((m.group(1), int(m.group(2))))
        rest = rest[2:]
    try:
        refused, out = run(root, gates)
    except CannotRun as exc:
        sys.stderr.write("verdict: %s\n" % exc)
        return 2
    for line in refused:
        sys.stderr.write("VERDICT REFUSED %s\n" % line)
    if refused:
        sys.stderr.write("VERDICT RED (%d refusal%s)\n" % (len(refused), "" if len(refused) == 1 else "s"))
        if stop:
            spans = [l.split(" ", 1)[0] for l in refused if not l.startswith("gate ")]
            gates_red = [l for l in refused if l.startswith("gate ")]
            sys.stderr.write("STOP unverified: %s\n" % "; ".join(
                (["no PASS at the current hash for " + ", ".join(spans)] if spans else []) + gates_red))
        return 1
    sys.stdout.write("VERDICT PASS %s\n" % out)
    return 0


# --- selftest -------------------------------------------------------------------------------------
def selftest():
    fails, n = [], [0]
    base = json.loads(SYNTHETIC.read_text(encoding="utf-8"))
    at = "2026-10-13T07:10:00Z"

    def rows_for(brief, verdict="PASS"):
        return [{"span_id": i, "span_hash": h, "verdict": verdict, "by": "span-verify-1", "at": at, "note": ""}
                for i, h in SD.hashes(brief).items()]

    def case(label, brief, rows, gates, want_code, want_lines):
        """want_lines: the refusal lines' leading tokens, exactly (whole output, not the first line)."""
        n[0] += 1
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "web").mkdir()
            (root / "web/index.html").write_text("<p>page</p>\n", encoding="utf-8")
            (root / "brief.json").write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")
            (root / "verify.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            argv = ["verdict.py", str(root)] + [x for g in gates for x in ("--gate", g)]
            with contextlib.redirect_stderr(io.StringIO()) as err, contextlib.redirect_stdout(io.StringIO()):
                code = main(argv)
            got = [l[len("VERDICT REFUSED "):].split(":")[0] for l in err.getvalue().splitlines()
                   if l.startswith("VERDICT REFUSED ")]
            written = sorted(p.name for p in root.glob("correctness-*.md"))
            want_file = ["correctness-%s.md" % sha((root / "brief.json").read_bytes())] if want_code == 0 else []
            body = (root / want_file[0]).read_text(encoding="utf-8").splitlines() if written == want_file and want_file else []
        ok = code == want_code and got == want_lines and written == want_file
        if want_code == 0:
            ok = ok and body[:2] == ["Verdict: PASS", "PAGE: %s" % sha(b"<p>page</p>\n")]
        if not ok:
            fails.append("%s: exit %s, refusals %s, files %s" % (label, code, got, written))

    ids = list(SD.spans(base))
    first = ids[0]
    h0 = SD.hashes(base)[first]
    case("every hash PASS: exit 0, correctness-<sha>.md with PAGE", base, rows_for(base), ["brief-check=0"], 0, [])
    case("one span with no row", base, [r for r in rows_for(base) if r["span_id"] != first], [], 1,
         ["%s %s" % (first, h0[:12])])
    edited = copy.deepcopy(base)
    edited["quick_take"][0]["lede"][0]["t"] += " Still."
    h1 = SD.hashes(edited)[first]
    case("an edited span whose PASS is for its old hash (unverified hash)", edited, rows_for(base), [], 1,
         ["%s %s" % (first, h1[:12])])
    case("the edited span verified at its new hash", edited, rows_for(base) + rows_for(edited)[:1], [], 0, [])
    fail_rows = rows_for(base)
    fail_rows[0] = dict(fail_rows[0], verdict="FAIL", note="plural unsupported")
    case("a FAIL row", base, fail_rows, [], 1, ["%s %s" % (first, h0[:12])])
    case("a FAIL after a PASS at one hash: the last row decides", base, rows_for(base) + fail_rows[:1], [], 1,
         ["%s %s" % (first, h0[:12])])
    case("a PASS after a FAIL at one hash", base, fail_rows + rows_for(base)[:1], [], 0, [])
    case("a gate exit 1", base, rows_for(base), ["brief-check=0", "web-check=1"], 1, ["gate web-check exited 1"])
    case("a PASS row on another span's id does not carry", base,
         [dict(r, span_id=ids[1]) if r["span_id"] == first else r for r in rows_for(base)], [], 1,
         ["%s %s" % (first, h0[:12])])

    # --gate-record: the runner's sentinel record supplies the gate exit
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        (root / "web").mkdir()
        (root / "web/index.html").write_text("x", encoding="utf-8")
        (root / "brief.json").write_text(json.dumps(base), encoding="utf-8")
        (root / "verify.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows_for(base)), encoding="utf-8")
        good, bad = root / "rec-good", root / "rec-bad"
        good.write_text(json.dumps({"node": "final-build", "attempt": 1, "gate_exit": 0}), encoding="utf-8")
        bad.write_text(json.dumps({"node": "final-build", "attempt": 1, "gate_exit": 1}), encoding="utf-8")
        for label, argv, want in (("a gate record with exit 0 passes and is printed", ["--gate-record", str(good)], 0),
                                  ("a gate record with exit 1 refuses", ["--gate-record", str(bad)], 1),
                                  ("a missing gate record cannot run", ["--gate-record", str(root / "none")], 2)):
            n[0] += 1
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                code = main(["verdict.py", str(root)] + argv)
            written = list(root.glob("correctness-*.md"))
            body = written[0].read_text(encoding="utf-8") if written else ""
            if code != want or (want == 0 and "GATE final-build: 0" not in body):
                fails.append("%s: exit %s" % (label, code))
            for w in written:
                w.unlink()

    # --stop: a refusal's stderr ends on the runner's typed STOP line, naming the failing span
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        (root / "web").mkdir()
        (root / "web/index.html").write_text("x", encoding="utf-8")
        (root / "brief.json").write_text(json.dumps(base), encoding="utf-8")
        failed = [dict(r, verdict="FAIL", note="kit") if r["span_id"] == first else r for r in rows_for(base)]
        (root / "verify.jsonl").write_text("".join(json.dumps(r) + "\n" for r in failed), encoding="utf-8")
        for label, argv, want in (("--stop ends a refusal on a STOP line naming the span", ["--stop"], True),
                                  ("no STOP line without --stop", [], False)):
            n[0] += 1
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = main(["verdict.py", str(root)] + argv)
            tail = err.getvalue().splitlines()[-1:] or [""]
            got = tail[0].startswith("STOP unverified: ") and first in tail[0]
            if code != 1 or got != want:
                fails.append("%s: exit %s, last line %r" % (label, code, tail[0]))

    # exit 2: a row off the schema, a missing verify.jsonl, a bad --gate
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        (root / "web").mkdir()
        (root / "web/index.html").write_text("x", encoding="utf-8")
        (root / "brief.json").write_text(json.dumps(base), encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()):
            missing = main(["verdict.py", str(root)])
            (root / "verify.jsonl").write_text(json.dumps(dict(rows_for(base)[0], verdict="OK")) + "\n", encoding="utf-8")
            off = main(["verdict.py", str(root)])
            badgate = main(["verdict.py", str(root), "--gate", "web-check"])
        for label, code in (("no verify.jsonl", missing), ("a row off the schema", off), ("a --gate without =EXIT", badgate)):
            n[0] += 1
            if code != 2:
                fails.append("%s: exit %s, want 2" % (label, code))

    for f in fails:
        sys.stderr.write("SELFTEST FAIL: %s\n" % f)
    if fails:
        sys.stderr.write("SELFTEST RED (%d of %d)\n" % (len(fails), n[0]))
        return 1
    sys.stdout.write("SELFTEST OK (%d cases)\n" % n[0])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
