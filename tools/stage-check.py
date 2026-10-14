#!/usr/bin/env python3
"""A node's gate: its declared gate commands, its declared outputs, then a clean clone.

    BRIEF_ROOT=<dir> python3 tools/stage-check.py <node>

The node comes from the graph `tools/run.py` builds from `references/stages/*.md` (or
`$RUN_STAGES`). A fan-out instance (`screen-T1-a`) names its base in `$RUN_BASE_NODE` and its
item and copy in `$RUN_ITEM` and `$RUN_COPY`, which fill `{item}` and `{copy}` in the gate.

Checks, every one run and every red printed to stderr:
  1. each `gate:` command, run with `bash -c` from the repo root, exits 0;
  2. each declared output (BRIEF_ROOT-relative, no glob) exists and is not empty;
  3. `git status --porcelain` in the repo root prints nothing: a node that edits, adds or deletes
     a tracked or untracked file in the clone is red (design.md section 3, step 5).

Exit 0 green, 1 red, 2 usage (unknown node, BRIEF_ROOT unset). The runner alone acts on the exit:
it writes the sentinel only on 0.
"""
import importlib.util
import os
import pathlib
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parent.parent


def load_runner():
    spec = importlib.util.spec_from_file_location("intel_run", ROOT / "tools" / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv):
    if len(argv) != 2 or argv[1].startswith("-"):
        print(__doc__, file=sys.stderr)
        return 2
    name = argv[1]
    brief = os.environ.get("BRIEF_ROOT")
    if not brief:
        print("stage-check: BRIEF_ROOT is unset", file=sys.stderr)
        return 2
    runner = load_runner()
    try:
        graph = runner.load_graph(ROOT, os.environ.get("RUN_STAGES") or runner.STAGES)
    except runner.GraphError as exc:
        print(f"stage-check: {exc}", file=sys.stderr)
        return 2
    base = os.environ.get("RUN_BASE_NODE") or name
    node = graph.get(base)
    if node is None:
        print(f"stage-check: unknown node {base!r}", file=sys.stderr)
        return 2
    var = {k: os.environ.get("RUN_" + k.upper(), "") for k in ("item", "copy")}
    var = {k: v for k, v in var.items() if v}
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", BRIEF_ROOT=brief)
    reds = []
    for cmd in node["gate"]:
        cmd = runner.substitute(cmd, var)
        p = subprocess.run(["bash", "-c", cmd], cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                           capture_output=True, text=True)
        if p.returncode != 0:
            said = (p.stderr.strip() or p.stdout.strip())[-8000:]
            reds.append(f"GATE RED (exit {p.returncode}): {cmd}" + (f"\n{said}" if said else ""))
    for rel in node["outputs"]:
        rel = runner.substitute(rel, var)
        if any(c in rel for c in "*?[<"):
            continue
        path = pathlib.Path(brief) / rel
        if not path.exists() or (path.is_file() and path.stat().st_size == 0):
            reds.append(f"OUTPUT MISSING: {rel} is absent or empty under BRIEF_ROOT")
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
                           text=True, stdin=subprocess.DEVNULL)
    if dirty.returncode != 0:
        reds.append(f"CLONE UNREADABLE: git status exited {dirty.returncode}: {dirty.stderr.strip()}")
    elif dirty.stdout.strip():
        reds.append("CLONE DIRTY: the node changed the clone; every write belongs under BRIEF_ROOT\n"
                    + dirty.stdout.rstrip())
    if reds:
        print(f"STAGE-CHECK RED {name} ({len(reds)})", file=sys.stderr)
        for r in reds:
            print(r, file=sys.stderr)
        return 1
    print(f"STAGE-CHECK OK {name} ({len(node['gate'])} gate(s), {len(node['outputs'])} output(s), clean clone)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
