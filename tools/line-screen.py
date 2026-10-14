#!/usr/bin/env python3
"""The founder-reader line-screen: every authored line of a page, three screeners, majority plus code.

WHY THIS EXISTS. The thesis lock screens one sentence; the page around it is where a verdict on the
reader, a recital of his own facts, a directive or an orphaned rival threat slip back in (c2
section 8.4; design.md section 4, G-R2, G-R3w, G-R3n, G-TT). This script cuts a `brief.json` into
its authored lines (one sentence each, from brief-check's own span walk), sends ALL of them in one
batch to each of three fresh `claude -p` screeners running `.claude/agents/screener.md` with the
card `quality-bar/founder-card.md`, and decides each line in code:
  - a card test is red on a line when 2 of the 3 screeners say no (a null is not graded);
  - NEW(code) and LEAD(code) from `tools/rank.py` red a line whose cited spans, or whose first cited
    span, cite only rows on the founder's own hosts, whatever the model says;
  - a line is red when any test or code check is.
The L-tests are NEW, TRUE, ROLE (the seat), STANCE, SPEAKER and CONSEQUENCE.

FIXTURES MODE. `--fixtures` screens recorded line items (`quality-bar/fixtures/*/screens/items/`,
each `{id, kind: line, text, spans, rows, context}`) in one batch the same way. With `--out DIR
--tag T`, each screener's verdicts land in `DIR/T-a/<item>.json` (and -b, -c), the recorded-verdict
layout `tools/fixture-test.py` counts, plus `DIR/T.json` and `DIR/T.md` for the majority.

SPAWN. The flag set of SP/research/a-platform.md section Recommendation: `env -i` (HOME, PATH,
USER) with CLAUDE_CODE_DISABLE_AUTO_MEMORY=1, `--agents` (the screener compiled by
tools/agents-compile.py, AGENTS.md first) `--agent screener --model opus --effort high
--max-turns 3 --setting-sources "" --settings tools/run-settings.json --strict-mcp-config
--dangerously-skip-permissions --no-session-persistence --output-format json --json-schema`,
stdin /dev/null, a wall timeout. tools/run.py's spawn is a method of its run object, so this is
the small local helper. A screener that fails is retried once; a second failure is exit 2.

USAGE
  line-screen.py BRIEF_JSON --reader READER [--claims CLAIMS] [--only WHERE,...] [--out DIR --tag T]
  line-screen.py --fixtures ITEM.json... --reader READER [--out DIR --tag T] [--expect red]
  line-screen.py --selftest      offline: a stub `claude` on PATH, no model call
`--only` screens the lines of the named fields (brief-check's `where`, e.g. `matrix.legend`) and
still pastes every line as PAGE. `--effort` overrides high; never `max` (b1 section 1).

EXIT CODES. 0: no line red (or, with `--expect red`, every item red). 1: the opposite; each line is
listed. 2: could not run: bad usage, an unreadable input, or a screener that failed twice.

PRECONDITION: `claude` on PATH and logged in, for every mode but --selftest. Costs money: about
$0.10-0.50 a screener on Globex's page.
"""

import concurrent.futures as cf
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parent.parent
CARD = ROOT / "quality-bar/founder-card.md"
VERDICT = ROOT / "references/schemas/verdict.schema.json"
VERDICT_FALLBACK = ROOT / "quality-bar/fixtures/globex/screens/verdict.schema.json"
SETTINGS = ROOT / "tools/run-settings.json"
L_TESTS = ("NEW", "TRUE", "ROLE", "STANCE", "SPEAKER", "CONSEQUENCE")
COPIES = ("a", "b", "c")
ROW_KEYS = ("id", "subject", "claim", "quote", "url", "state", "qualifier", "known")
END = re.compile(r"[.?!][\"'’”)\]]*\s*$")
ENV_KEEP = ("HOME", "PATH", "USER")


class Unreadable(Exception):
    pass


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:
        raise Unreadable("%s does not import (%s: %s)" % (path, type(exc).__name__, exc))
    return mod


RANK = load("rank", ROOT / "tools/rank.py")


def read_json(path):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Unreadable("%s: %s" % (path, exc))


# --- lines ----------------------------------------------------------------------------------------
def ids_of(c):
    if isinstance(c, str):
        return [c]
    return [x for x in c if isinstance(x, str)] if isinstance(c, list) else []


def lines_of(brief):
    """[(where, [span indexes], [spans])] one per sentence, in page order, over brief-check's span
    walk. A sentence ends at a span whose text ends on . ? or ! (closing quotes allowed)."""
    bc = load("brief_check", ROOT / "tools/brief-check.py")
    out = []
    for where, arr in bc.span_arrays(brief):
        cur, idx = [], []
        for j, s in enumerate(arr):
            if not (isinstance(s, dict) and isinstance(s.get("t"), str)):
                continue
            cur.append(s)
            idx.append(j)
            if END.search(s["t"]):
                out.append((where, idx, cur))
                cur, idx = [], []
        if cur:
            out.append((where, idx, cur))
    return out


def line_id(where, idx):
    return "%s[%s]" % (where, str(idx[0]) if len(idx) == 1 else "%d-%d" % (idx[0], idx[-1]))


def trim(row, known):
    out = {k: row.get(k) for k in ROW_KEYS if k in row}
    out["known"] = known(row["id"], row.get("known"))
    return out


def page_items(brief, claims, known, only=None):
    """(items to screen, page lines, rows) for a brief.json."""
    items, page, cited = [], [], set()
    for where, idx, spans in lines_of(brief):
        sp = [{"t": s["t"], "c": ids_of(s.get("c")), "known": all(known(c) for c in ids_of(s.get("c")))
               if ids_of(s.get("c")) else False} for s in spans]
        text = "".join(s["t"] for s in spans).strip()
        lid = line_id(where, idx)
        page.append({"id": lid, "text": text})
        if only and where not in only:
            continue
        items.append({"id": lid, "kind": "line", "field": where, "text": text, "spans": sp})
        cited |= {c for s in sp for c in s["c"]}
    rows = [trim(claims[c], known) for c in sorted(cited) if c in claims]
    return items, page, rows


def fixture_items(paths, known_hosts_reader):
    """(items, rows) for recorded line items; their pasted rows become ROWS, fixture-only fields go."""
    items, rows = [], {}
    for p in paths:
        it = read_json(p)
        if it.get("kind") != "line":
            raise Unreadable("%s is not a line item" % p)
        for r in it.get("rows", []):
            rows[r["id"]] = r
        items.append({k: it[k] for k in ("id", "kind", "field", "text", "context", "spans") if k in it})
    known = RANK.known_fn(known_hosts_reader, rows)
    return items, [trim(r, known) for r in rows.values()], known


# --- the screener call ----------------------------------------------------------------------------
def line_schema():
    base = read_json(VERDICT if VERDICT.is_file() else VERDICT_FALLBACK)
    props = base["properties"]
    one = {"type": "object", "additionalProperties": False, "required": ["item"] + list(L_TESTS),
           "properties": {"item": props["item"]}}
    for t in L_TESTS[:-1]:
        one["properties"][t] = props[t]
    one["properties"]["CONSEQUENCE"] = {
        "type": "object", "additionalProperties": False, "required": ["pass", "quote", "why"],
        "properties": {"pass": {"type": ["boolean", "null"]}, "quote": {"type": "string"},
                       "why": {"type": "string"}}}
    return {"type": "object", "additionalProperties": False, "required": ["verdicts"],
            "properties": {"verdicts": {"type": "array", "items": one}}}


def prompt_of(reader, rows, page, items):
    fence = lambda x: "```json\n" + json.dumps(x, indent=1, ensure_ascii=False) + "\n```\n"
    parts = ["Screen every item in ITEMS against CARD. Every item is `kind: line`: run the tests the "
             "card marks L and give one verdict per item, in order.\n",
             "# CARD\n\n" + CARD.read_text(encoding="utf-8"),
             "# READER\n\n" + fence(reader),
             "# ROWS\n\n" + fence(rows)]
    if page:
        parts.append("# PAGE\n\nEvery authored line of the page, in order.\n\n" + fence(page))
    else:
        parts.append("# PAGE\n\nNone given: CONSEQUENCE is null on every item.\n")
    parts.append("# ITEMS\n\n" + fence(items))
    return "\n".join(parts)


def agents_file(tmp):
    """tools/agents.json holding the screener alone, compiled by agents-compile's own function."""
    ac = load("agents_compile", ROOT / "tools/agents-compile.py")
    agents, reds = ac.compile_dir(ROOT)
    mine = [r for r in reds if r[0] == "screener.md"]
    if mine or "screener" not in agents:
        raise Unreadable("the screener agent does not compile: %s" % (mine or "no .claude/agents/screener.md"))
    path = pathlib.Path(tmp) / "agents.json"
    path.write_text(json.dumps({"screener": agents["screener"]}, ensure_ascii=False), encoding="utf-8")
    return path


def spawn(prompt, schema, agents, effort, timeout_s):
    """One screener: (structured_output or None, the result dict or an error string)."""
    env = {k: os.environ[k] for k in ENV_KEEP if k in os.environ}
    env.update({"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    cmd = ["claude", "-p", prompt, "--agents", str(agents), "--agent", "screener",
           "--model", "opus", "--effort", effort, "--max-turns", "3",
           "--setting-sources", "", "--settings", str(SETTINGS), "--strict-mcp-config",
           "--dangerously-skip-permissions", "--no-session-persistence",
           "--output-format", "json", "--json-schema", json.dumps(schema)]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=ROOT, env=env, stdin=subprocess.DEVNULL, capture_output=True,
                           text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return None, "timeout after %ds" % timeout_s
    try:
        res = json.loads(p.stdout)
    except ValueError:
        return None, "exit %d, no JSON result: %s" % (p.returncode, (p.stderr or p.stdout)[-800:])
    res["_wall_s"] = round(time.time() - t0, 1)
    out = res.get("structured_output")
    if p.returncode != 0 or res.get("is_error") or not isinstance(out, dict):
        return None, "exit %d, subtype %s: %s" % (p.returncode, res.get("subtype"), str(res.get("result"))[-400:])
    return out, res


def screen(prompt, schema, effort, timeout_s):
    """{copy: verdict list} from three screeners in parallel, each retried once. Raises on a
    screener that fails twice."""
    with tempfile.TemporaryDirectory() as tmp:
        agents = agents_file(tmp)

        def one(copy):
            out, res = spawn(prompt, schema, agents, effort, timeout_s)
            if out is None:
                sys.stderr.write("line-screen: screener %s failed (%s); retrying once\n" % (copy, res))
                out, res = spawn(prompt, schema, agents, effort, timeout_s)
            return copy, out, res
        with cf.ThreadPoolExecutor(max_workers=len(COPIES)) as pool:
            got = list(pool.map(one, COPIES))
    failed = [(c, r) for c, o, r in got if o is None]
    if failed:
        raise Unreadable("screener(s) failed twice: %s" % "; ".join("%s: %s" % f for f in failed))
    return {c: (o.get("verdicts") or [], r) for c, o, r in got}


# --- deciding -------------------------------------------------------------------------------------
def decide(items, by_copy, known):
    """[{item, red, tests, code}] per item: majority per L-test, plus the code half."""
    out = []
    for it in items:
        vs = [v for c in COPIES for v in by_copy.get(c, ([], None))[0] if v.get("item") == it["id"]]
        tests = {}
        for t in L_TESTS:
            red, n, of, rv = RANK.test_red(vs, t)
            tests[t] = {"red": red, "n": n, "of": of, "quotes": [v[t].get("quote", "") for v in rv]}
        code = RANK.line_code_reds(it["spans"], known)
        missing = len(vs) < len(COPIES)
        red = any(x["red"] for x in tests.values()) or bool(code)
        out.append({"item": it["id"], "text": it["text"], "red": red, "screeners": len(vs),
                    "missing": missing, "tests": tests, "code": [list(x) for x in code]})
    return out


def report(decided):
    lines = ["| item | red | by | text |", "|---|---|---|---|"]
    for d in decided:
        by = ["%s %d/%d" % (t, x["n"], x["of"]) for t, x in d["tests"].items() if x["red"]]
        by += [c[0] for c in d["code"]]
        lines.append("| %s | %s | %s | %s |" % (d["item"], "RED" if d["red"] else "green", ", ".join(by) or "-",
                                                d["text"].replace("|", "/")[:140]))
    return "\n".join(lines) + "\n"


def write_out(out, tag, items, by_copy, decided, prompt):
    out = pathlib.Path(out)
    for c in COPIES:
        d = out / ("%s-%s" % (tag, c))
        d.mkdir(parents=True, exist_ok=True)
        verdicts, res = by_copy[c]
        for v in verdicts:
            (d / (v["item"] + ".json")).write_text(json.dumps(v, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        if isinstance(res, dict):
            keep = {k: res.get(k) for k in ("subtype", "num_turns", "duration_ms", "duration_api_ms", "_wall_s",
                                            "total_cost_usd", "usage", "modelUsage")}
            (d / "_result.json").write_text(json.dumps(keep, indent=1) + "\n", encoding="utf-8")
    (out / ("%s.prompt.md" % tag)).write_text(prompt, encoding="utf-8")
    (out / ("%s.json" % tag)).write_text(json.dumps({"lines": decided}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / ("%s.md" % tag)).write_text(report(decided), encoding="utf-8")


def cost(by_copy):
    return sum((r or {}).get("total_cost_usd") or 0 for _, r in by_copy.values() if isinstance(r, dict))


# --- main -----------------------------------------------------------------------------------------
def opt(args, flag, default=None):
    if flag in args:
        i = args.index(flag)
        if i + 1 >= len(args):
            raise Unreadable("%s needs a value" % flag)
        val = args[i + 1]
        del args[i:i + 2]
        return val
    return default


def run(args):
    args = list(args)
    reader_path = opt(args, "--reader")
    out, tag = opt(args, "--out"), opt(args, "--tag")
    effort = opt(args, "--effort", "high")
    expect = opt(args, "--expect")
    only = opt(args, "--only")
    claims_path = opt(args, "--claims")
    timeout_s = int(opt(args, "--timeout", "1200"))
    fixtures = "--fixtures" in args
    if fixtures:
        args.remove("--fixtures")
    if not reader_path or not args or (out is None) != (tag is None) or expect not in (None, "red") \
            or effort not in ("low", "medium", "high", "xhigh"):
        raise Unreadable("usage (see --help in the docstring): line-screen.py BRIEF_JSON --reader R | --fixtures ITEMS --reader R")
    reader = read_json(reader_path)
    if fixtures:
        items, rows, known = fixture_items(args, reader)
        page = None
    else:
        if len(args) != 1:
            raise Unreadable("one brief.json at a time")
        brief_path = pathlib.Path(args[0])
        brief = read_json(brief_path)
        claims = RANK.read_claims(claims_path or brief_path.parent / "claims.jsonl")
        known = RANK.known_fn(reader, claims)
        items, page, rows = page_items(brief, claims, known, set(only.split(",")) if only else None)
    if not items:
        raise Unreadable("no lines to screen")
    prompt = prompt_of(reader, rows, page, items)
    by_copy = screen(prompt, line_schema(), effort, timeout_s)
    decided = decide(items, by_copy, known)
    if out:
        write_out(out, tag, items, by_copy, decided, prompt)
    sys.stdout.write(report(decided))
    reds = [d for d in decided if d["red"]]
    short = [d["item"] for d in decided if d["missing"]]
    if short:
        sys.stdout.write("WARNING: fewer than three verdicts for %s\n" % ", ".join(short))
    sys.stdout.write("LINE-SCREEN: %d of %d lines red, three screeners, cost $%.2f\n" % (len(reds), len(decided), cost(by_copy)))
    if expect == "red":
        return 0 if len(reds) == len(decided) else 1
    return 1 if reds else 0


# --- selftest -------------------------------------------------------------------------------------
STUB = r'''#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
PLAN = str(pathlib.Path(__file__).resolve().parent.parent / "plan.json")  # env -i drops any variable
plan = json.loads(pathlib.Path(PLAN).read_text())
import fcntl
with open(PLAN + ".lock", "a") as lk:
    fcntl.flock(lk, fcntl.LOCK_EX)
    counter = pathlib.Path(PLAN + ".n")
    n = int(counter.read_text()) if counter.exists() else 0
    counter.write_text(str(n + 1))
    with open(PLAN + ".argv", "a") as f:
        f.write(json.dumps(args) + "\n")
prompt = args[args.index("-p") + 1]
items = json.loads(prompt.split("# ITEMS")[1].split("```json")[1].split("```")[0])
red = plan["calls"][n % len(plan["calls"])] if plan["calls"] else {}
if red == "fail":
    print(json.dumps({"type": "result", "subtype": "error_max_turns", "is_error": True}))
    sys.exit(1)
verdicts = []
for it in items:
    v = {"item": it["id"]}
    for t in ("NEW", "TRUE", "ROLE", "STANCE", "SPEAKER", "CONSEQUENCE"):
        p = not (t in red.get(it["id"], []))
        v[t] = {"pass": p, "quote": it["text"][:20], "why": "stub"}
    v["ROLE"].update(lines=[], seat=v["ROLE"]["pass"])
    v["STANCE"].update(value="negates" if not v["STANCE"]["pass"] else "neutral", positioning="P1")
    v["SPEAKER"].update(kind="verdict" if not v["SPEAKER"]["pass"] else "none")
    verdicts.append(v)
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "total_cost_usd": 0.01,
                  "structured_output": {"verdicts": verdicts}}))
'''


def selftest():
    fails, n = [], 0

    def case(name, ok, why=""):
        nonlocal n
        n += 1
        sys.stdout.write("%s %s%s\n" % ("PASS" if ok else "FAIL", name, "" if ok else " -- " + str(why)[:600]))
        if not ok:
            fails.append(name)

    globex = ROOT / "quality-bar/fixtures/globex"
    reader = globex / "screens/reader.json"
    brief = read_json(globex / "run/brief.json")
    claims = RANK.read_claims(globex / "run/claims.jsonl")
    known = RANK.known_fn(read_json(reader), claims)

    # 1. Lines: one per sentence, ids in brief-check's spelling, the S7 lines where § 4 puts them.
    items, page, rows = page_items(brief, claims, known)
    ids = [i["id"] for i in items]
    case("page: G-R3w is its own line, recommendations[2].why[1]", "recommendations[2].why[1]" in ids, ids)
    case("page: G-R2 is one line over two spans, recommendations[1].test[0-1]", "recommendations[1].test[0-1]" in ids, ids)
    case("page: G-R3n and G-TT", "recommendations[2].next_step[0]" in ids and "matrix.legend[2]" in ids, ids)
    case("page: one line per sentence, none split mid-sentence", len(items) > 20
         and all(END.search(i["text"]) or i is items[-1] or items[ids.index(i["id"]) + 1]["field"] != i["field"] for i in items), len(items))
    case("page: rows carry code-set known", rows and all(isinstance(r["known"], bool) for r in rows)
         and any(r["known"] for r in rows) and any(not r["known"] for r in rows), rows[:2])
    only, page2, _ = page_items(brief, claims, known, {"matrix.legend"})
    case("--only keeps the whole page as PAGE", all(i["field"] == "matrix.legend" for i in only) and len(page2) == len(page))

    # 2. The batch schema: the L-tests, CONSEQUENCE added, S2's verdict shapes reused.
    sch = line_schema()
    one = sch["properties"]["verdicts"]["items"]
    case("schema: item plus the six L-tests, all required", one["required"] == ["item"] + list(L_TESTS)
         and "DECISION" not in one["properties"], one["required"])

    # 3. The prompt: the card verbatim, fixture provenance dropped.
    fx = [globex / "screens/items" / (i + ".json") for i in ("F-JOB", "F-V1", "CTL-V6")]
    fitems, frows, fknown = fixture_items(fx, read_json(reader))
    pr = prompt_of(read_json(reader), frows, None, fitems)
    case("prompt: the card verbatim, no item `source`, PAGE absent", CARD.read_text() in pr and "job-post line" not in pr
         and "CONSEQUENCE is null" in pr)

    # 4. Majority plus code, through a stub `claude` on PATH.
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        (tmp / "bin").mkdir()
        stub = tmp / "bin" / "claude"
        stub.write_text(STUB)
        stub.chmod(0o755)
        plan = tmp / "plan.json"

        def go(calls, extra=()):
            plan.write_text(json.dumps({"calls": calls}))
            for f in (tmp / "plan.json.n", tmp / "plan.json.argv"):
                if f.exists():
                    f.unlink()
            env = dict(os.environ, PATH="%s:%s" % (tmp / "bin", os.environ["PATH"]))
            p = subprocess.run([sys.executable, str(pathlib.Path(__file__).resolve()), "--fixtures", *map(str, fx),
                                "--reader", str(reader), *extra], capture_output=True, text=True, env=env)
            return p.returncode, p.stdout + p.stderr

        rc, out = go([{"F-V1": ["STANCE"]}, {"F-V1": ["STANCE"]}, {}], ("--out", tmp / "res", "--tag", "t"))
        dec = {d["item"]: d for d in read_json(tmp / "res/t.json")["lines"]} if (tmp / "res/t.json").is_file() else {}
        case("2 of 3 red is red", dec.get("F-V1", {}).get("red") is True and dec["F-V1"]["tests"]["STANCE"]["n"] == 2, out)
        case("code reds the recital the model passed (F-JOB, LEAD(code))", dec.get("F-JOB", {}).get("red") is True
             and dec["F-JOB"]["code"] and not any(x["red"] for x in dec["F-JOB"]["tests"].values()), dec.get("F-JOB"))
        case("CTL-V6 green", dec.get("CTL-V6", {}).get("red") is False, dec.get("CTL-V6"))
        case("a page with a red line exits 1", rc == 1, out)
        case("verdicts land where fixture-test counts them", all((tmp / "res" / ("t-" + c) / "F-V1.json").is_file() for c in COPIES))
        argv = [json.loads(l) for l in (tmp / "plan.json.argv").read_text().splitlines()]
        flags = argv[0]
        case("spawn: the recommended flags", all(f in flags for f in ("--agents", "--agent", "screener", "--strict-mcp-config",
             "--no-session-persistence", "--json-schema", "--setting-sources", "--dangerously-skip-permissions"))
             and flags[flags.index("--effort") + 1] == "high" and flags[flags.index("--setting-sources") + 1] == "", flags[:6])
        case("one prompt, three screeners", len(argv) == 3 and len({json.dumps(a) for a in argv}) == 1, len(argv))

        rc, out = go([{"F-V1": ["STANCE"]}, {}, {}], ("--expect", "red"))
        case("1 of 3 red is green, and --expect red then exits 1", rc == 1 and "| F-V1 | green" in out, out)
        rc, out = go([{"F-V1": ["SPEAKER"], "CTL-V6": ["TRUE"]}] * 3, ("--expect", "red"))
        case("--expect red exits 0 when every item is red", rc == 0, out)
        rc, out = go(["fail", {}, {}, "fail"])
        case("a screener failing twice exits 2", rc == 2 and "failed twice" in out, out)
        rc, out = go(["fail", {}, {}, {}])
        case("a screener failing once is retried", rc == 1 and "retrying once" in out, out)

    if fails:
        sys.stdout.write("LINE-SCREEN SELFTEST RED (%d of %d cases failed)\n" % (len(fails), n))
        return 1
    sys.stdout.write("LINE-SCREEN SELFTEST OK (%d cases)\n" % n)
    return 0


def main(argv):
    if argv[1:] == ["--selftest"]:
        return selftest()
    if argv[1:] in (["--help"], ["-h"], []):
        sys.stdout.write(__doc__)
        return 0 if argv[1:] else 2
    try:
        return run(argv[1:])
    except Unreadable as exc:
        sys.stderr.write("line-screen: %s\n" % exc)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
