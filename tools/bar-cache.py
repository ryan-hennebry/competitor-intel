#!/usr/bin/env python3
"""The bar, cached (Globex design § 3 `bar` node, § 10 Q2).

WHY THIS EXISTS. `00-bar.md` is the stage-0 agent's fifteen-line index of `quality-bar/`. It never
reads the job ad, so for one quality bar it is the same file on every run: an agent spent on it per
run buys nothing. The run reads it from a cache keyed on what it is made of, and the stage-0
template (`references/stages/00-bar-loader.md`) runs only on a miss.

THE KEY. sha256 over every file under `quality-bar/` (path and bytes; `near-misses.tsv` and
`rulings.tsv` live there) and the generator template's own bytes. A new ruling, a moved near-miss
or a template edit is a new key, so a stale bar is never served. `tools/rule.py add` re-warms the
cache (`warm`) off the run, so the next launch hits.

  bar-cache.py key                 print the key of this tree
  bar-cache.py get BRIEF_ROOT      hit: copy the cached bar to BRIEF_ROOT/00-bar.md (BAR HIT); miss:
                                   write nothing (BAR MISS) and the run's bar-gen node generates it
  bar-cache.py put BRIEF_ROOT      store BRIEF_ROOT/00-bar.md under the key, once bar-check passes
  bar-cache.py warm [--claude EXE] generate the bar now, as the run's bar-gen node would (its role,
                                   model, effort, turns and template), into a scratch BRIEF_ROOT,
                                   then put. No `claude` on PATH, or INTEL_BAR_WARM=0: a note, exit 0
  bar-cache.py --selftest          offline: hit, miss, key change on `rule.py add`, warm on a stub

The cache lives in `$INTEL_CACHE_DIR/bar/` (default `~/.cache/competitor-intel/bar/`), outside every
clone, so the run's clean-clone check never sees it.

EXIT CODES. 0 done (a miss included). 1 put refused (no bar, or bar-check red) or warm failed.
2 bad usage. Stdlib only.
"""
import hashlib
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = "references/stages/00-bar-loader.md"
GEN_NODE = "bar-gen"
SKIP = {"__pycache__", ".DS_Store"}


def cache_dir():
    base = os.environ.get("INTEL_CACHE_DIR") or str(pathlib.Path.home() / ".cache" / "competitor-intel")
    return pathlib.Path(base) / "bar"


def key(root=ROOT):
    h = hashlib.sha256()
    files = [p for p in (root / "quality-bar").rglob("*")
             if p.is_file() and not SKIP & set(p.relative_to(root).parts)]
    for p in sorted(files + [root / TEMPLATE], key=lambda x: x.relative_to(root).as_posix()):
        h.update(p.relative_to(root).as_posix().encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


def get(brief, root=ROOT):
    k = key(root)
    cached = cache_dir() / f"{k}.md"
    if cached.is_file() and cached.stat().st_size:
        brief.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(cached, brief / "00-bar.md")
        print(f"BAR HIT {k[:12]}")
    else:
        print(f"BAR MISS {k[:12]}: the bar-gen node writes it")
    return 0


def bar_check(path, root=ROOT):
    return subprocess.run(["bash", str(root / "tools" / "bar-check.sh"), str(path)], cwd=root,
                          capture_output=True, text=True, stdin=subprocess.DEVNULL,
                          env=dict(os.environ, BRIEF_ROOT=str(path.parent)))


def put(brief, root=ROOT):
    bar = brief / "00-bar.md"
    if not bar.is_file() or not bar.stat().st_size:
        print(f"bar-cache: no bar at {bar}", file=sys.stderr)
        return 1
    p = bar_check(bar, root)
    if p.returncode != 0:
        print(f"bar-cache: bar-check is red, nothing stored\n{p.stdout}{p.stderr}", file=sys.stderr)
        return 1
    k = key(root)
    d = cache_dir()
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f".{k}.{os.getpid()}"
    shutil.copyfile(bar, tmp)
    os.replace(tmp, d / f"{k}.md")
    print(f"BAR STORED {k[:12]}")
    return 0


def load_runner(root):
    spec = importlib.util.spec_from_file_location("intel_run", root / "tools" / "run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def warm(root=ROOT, claude="claude"):
    if os.environ.get("INTEL_BAR_WARM") == "0":
        print("BAR WARM skipped (INTEL_BAR_WARM=0): the next run generates the bar on its miss")
        return 0
    exe = shutil.which(claude)
    if not exe:
        print(f"BAR WARM skipped: no {claude!r} on PATH; the next run generates the bar on its miss")
        return 0
    R = load_runner(root)
    node = R.load_graph(root).get(GEN_NODE)
    if not node:
        print(f"bar-cache: the graph has no {GEN_NODE} node", file=sys.stderr)
        return 1
    _, body = R.frontmatter((root / node["template"]).read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="bar-warm-") as t:
        tmp = pathlib.Path(t)
        brief = tmp / "brief"
        brief.mkdir()
        agents = tmp / "agents.json"
        comp = subprocess.run([sys.executable, str(root / "tools" / "agents-compile.py"), "--out", str(agents)],
                              cwd=root, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                              env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        if comp.returncode != 0:
            print("bar-cache: agents compile red\n" + comp.stdout + comp.stderr, file=sys.stderr)
            return 1
        inputs = {"inputs": {}, "outputs": {o: str(brief / o) for o in node["outputs"]},
                  "run": {"BRIEF_ROOT": str(brief), "node": GEN_NODE, "date": R.now().date().isoformat(),
                          "tz": R.TZ, "effort": node["effort"]}}
        prompt = body.rstrip("\n") + "\n\nINPUTS:\n" + json.dumps(inputs, indent=1) + "\n"
        cmd = [exe, "-p", prompt, "--agents", str(agents), "--agent", node["role"],
               "--model", str(node["model"]), "--effort", str(node["effort"]),
               "--max-turns", str(node["max_turns"]), "--setting-sources", "",
               "--settings", str(root / "tools" / "run-settings.json"), "--strict-mcp-config",
               "--dangerously-skip-permissions", "--no-session-persistence", "--output-format", "json"]
        env = {k: os.environ[k] for k in R.ENV_KEEP if k in os.environ}
        env.update(CLAUDE_CODE_DISABLE_AUTO_MEMORY="1", BRIEF_ROOT=str(brief), RUN_ID="bar-warm",
                   RUN_NODE=GEN_NODE, PYTHONDONTWRITEBYTECODE="1")
        try:
            p = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True,
                               stdin=subprocess.DEVNULL, timeout=float(node["timeout_min"]) * 60)
        except subprocess.TimeoutExpired:
            print("bar-cache: warm timed out", file=sys.stderr)
            return 1
        if p.returncode != 0:
            print(f"bar-cache: warm's claude exited {p.returncode}\n{p.stderr[-2000:]}", file=sys.stderr)
            return 1
        return put(brief, root)


def main(argv):
    args = argv[1:]
    if args == ["--selftest"]:
        return selftest()
    if args == ["key"]:
        print(key())
        return 0
    if len(args) == 2 and args[0] in ("get", "put"):
        return (get if args[0] == "get" else put)(pathlib.Path(args[1]))
    if args[:1] == ["warm"] and len(args) in (1, 3) and (len(args) == 1 or args[1] == "--claude"):
        return warm(claude=args[2] if len(args) == 3 else "claude")
    print(__doc__, file=sys.stderr)
    return 2


# ---- selftest ---------------------------------------------------------------------------------

FAILS = []

STUB = """#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
prompt = args[args.index("-p") + 1]
out = json.loads(prompt.split("INPUTS:", 1)[1])["outputs"]["00-bar.md"]
pathlib.Path(out).write_text(pathlib.Path({green!r}).read_text())
with open({log!r}, "a") as f:
    f.write(json.dumps({{"argv": [a for a in args if a != prompt], "env_run_id": os.environ.get("RUN_ID")}}) + "\\n")
print(json.dumps({{"type": "result", "subtype": "success", "is_error": False}}))
"""


def case(label, ok, detail=""):
    print(f"SELFTEST {'OK  ' if ok else 'FAIL'} {label}" + ("" if ok else f": {detail}"))
    if not ok:
        FAILS.append(label)


def child(tree, args, env):
    return subprocess.run([sys.executable, str(tree / "tools" / "bar-cache.py")] + args, cwd=tree, env=env,
                          capture_output=True, text=True, stdin=subprocess.DEVNULL)


def selftest():
    with tempfile.TemporaryDirectory(prefix="bar-cache-selftest-") as t:
        tmp = pathlib.Path(t)
        tree = tmp / "tree"
        for rel in ("quality-bar", "references/stages", ".claude/agents"):
            shutil.copytree(ROOT / rel, tree / rel, ignore=shutil.ignore_patterns("__pycache__"))
        for rel in ("tools/bar-cache.py", "tools/bar-check.sh", "tools/rule.py", "tools/run.py",
                    "tools/agents-compile.py", "tools/run-settings.json", "tools/fixture-test.py", "AGENTS.md",
                    "references/provenance.md"):
            (tree / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, tree / rel)
        env = dict(os.environ, INTEL_CACHE_DIR=str(tmp / "cache"), PYTHONDONTWRITEBYTECODE="1",
                   INTEL_BAR_WARM="0")
        green = tree / "quality-bar" / "fixtures" / "bar-green.md"
        b1, b2, b3 = tmp / "run1", tmp / "run2", tmp / "run3"

        p = child(tree, ["get", str(b1)], env)
        case("first launch: a miss writes no bar", p.returncode == 0 and "BAR MISS" in p.stdout
             and not (b1 / "00-bar.md").exists(), p.stdout + p.stderr)
        b1.mkdir(exist_ok=True)
        shutil.copyfile(green, b1 / "00-bar.md")
        p = child(tree, ["put", str(b1)], env)
        case("the generated bar is stored under the key", p.returncode == 0 and "BAR STORED" in p.stdout,
             p.stdout + p.stderr)
        p = child(tree, ["get", str(b2)], env)
        case("second launch, inputs unchanged: a hit copies the stored bar",
             "BAR HIT" in p.stdout and (b2 / "00-bar.md").read_bytes() == green.read_bytes(), p.stdout + p.stderr)

        before = child(tree, ["key"], env).stdout.strip()
        fx = json.dumps({"id": "SELFTEST-BAR-1", "owner": "gate", "rules": ["NC"], "brief": "x", "where": "x"})
        add = subprocess.run([sys.executable, str(tree / "tools" / "rule.py"), "add", "--set", "selftest",
                              "--id", "RBAR", "--class", "verdict", "--test", "t", "--example", "e",
                              "--scope", "s", "--source", "selftest", "--fixture", fx],
                             cwd=tree, env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        after = child(tree, ["key"], env).stdout.strip()
        p = child(tree, ["get", str(b3)], env)
        case("rule.py add changes the key, so the next launch misses",
             add.returncode == 0 and before != after and "BAR MISS" in p.stdout and not (b3 / "00-bar.md").exists(),
             (add.returncode, add.stdout + add.stderr, before[:12], after[:12], p.stdout))

        (tmp / "bad").mkdir()
        (tmp / "bad" / "00-bar.md").write_text("Here is the bar:\nnothing else\n")
        p = child(tree, ["put", str(tmp / "bad")], env)
        case("put refuses a bar bar-check reds, and stores nothing", p.returncode == 1
             and not (tmp / "cache" / "bar" / f"{after}.md").exists(), p.stdout + p.stderr)

        stub = tmp / "stub-claude"
        stub.write_text(STUB.format(green=str(green), log=str(tmp / "stub.log")))
        stub.chmod(0o755)
        wenv = dict(env, INTEL_BAR_WARM="1")
        p = child(tree, ["warm", "--claude", str(stub)], wenv)
        log = [json.loads(l) for l in (tmp / "stub.log").read_text().splitlines()] if (tmp / "stub.log").exists() else []
        argv = log[0]["argv"] if log else []
        flag = lambda f: argv[argv.index(f) + 1] if f in argv else None
        case("warm runs the bar-gen node's role, model, effort and turns, hook armed, then stores the bar",
             p.returncode == 0 and "BAR STORED" in p.stdout and (tmp / "cache" / "bar" / f"{after}.md").is_file()
             and flag("--agent") == "bar" and flag("--model") == "opus" and flag("--effort") == "high"
             and flag("--max-turns") == "15" and log[0]["env_run_id"] == "bar-warm",
             (p.returncode, p.stdout + p.stderr, argv))
        p = child(tree, ["get", str(tmp / "run4")], env)
        case("after warm, the next launch hits", "BAR HIT" in p.stdout, p.stdout)

        add_env = dict(env, INTEL_BAR_WARM="1", PATH=f"{tmp / 'bin'}{os.pathsep}{env['PATH']}")
        (tmp / "bin").mkdir()
        (tmp / "bin" / "claude").write_text(STUB.format(green=str(green), log=str(tmp / "stub2.log")))
        (tmp / "bin" / "claude").chmod(0o755)
        fx2 = json.dumps({"id": "SELFTEST-BAR-2", "owner": "gate", "rules": ["NC"], "brief": "x", "where": "x"})
        add = subprocess.run([sys.executable, str(tree / "tools" / "rule.py"), "add", "--set", "selftest",
                              "--id", "RBAR2", "--class", "verdict", "--test", "t", "--example", "e",
                              "--scope", "s", "--source", "selftest", "--fixture", fx2],
                             cwd=tree, env=add_env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        p = child(tree, ["get", str(tmp / "run5")], env)
        case("rule.py add re-warms the cache: the launch after it hits",
             add.returncode == 0 and "BAR STORED" in add.stdout and "BAR HIT" in p.stdout,
             (add.stdout + add.stderr, p.stdout))
    if FAILS:
        print(f"BAR-CACHE SELFTEST FAIL ({len(FAILS)}): " + "; ".join(FAILS))
        return 1
    print("BAR-CACHE SELFTEST OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
