#!/usr/bin/env python3
"""The Competitor Intel graph runner (design.md section 3, Runner). Stdlib only.

The graph comes from the YAML frontmatter of every `references/stages/*.md`. A file's top-level
keys define a node when they carry `node:`; a `nodes:` list defines more, so one file can declare a
stage's other nodes (stage 5's lock, screen, repair and rank; a lane's code nodes). Node keys:

  node, role, model, effort, max_turns, timeout_min, inputs, outputs, after, gate, schema, lane,
  critical                      the design's set; inputs and outputs are BRIEF_ROOT-relative
  run                           a code node's shell command (no role); its exit code is step one
  template                      the prompt body's file, clone-relative (default: the declaring file)
  prompt                        an inline prompt body instead of a template
  inline                        BRIEF_ROOT-relative files pasted into the prompt after the body, for a
                                typed node whose turn cap leaves no turns to Read (stage 5's screens)
  fanout                        {from, list, key, copies}: one instance per item (x copies)
  when                          a shell command; non-zero skips the node
  regen                         {exit, node, effort}: a code node exiting `exit` re-runs `node` once
  notify                        a notification title sent when the node is sealed (check-in)
  final                         runs in the runner's `finally`; its outputs are copied to compound/
  mcp_config                    passed as --mcp-config (the mkt1 node)

A `nodes:` entry may instead be a round group, `{group, rounds, nodes}` (span-verify's repair):
`rounds` chained copies of its member nodes, made at load. Round 1 keeps each member's name and
round r adds `-r<r>`; `{round}` in a member's run, when, gate, inputs, outputs and inline becomes ""
in round 1 and `-r<r>` after, so each round has its own files. A member's `after` naming a member
names that member in its own round; round r's first member also runs after round r-1's last; a node
outside the group naming a member runs after that member's last round. Round r's first member's
`when` decides whether the round runs; a member whose in-round `after` nodes were all skipped is
skipped. run.json records `rounds` {group: count}; the report's ROUNDS line counts the rounds used.

Per node (design steps 1-6): wait for `after:`; build the prompt (body + `INPUTS:` JSON + run
variables) and save it to prompts/; spawn `claude -p` in a scrubbed environment with the role,
model, effort, turn cap, settings and schema flags, stdin /dev/null, under a wall timeout, the
stream-json transcript written to logs/; append the result's usage to run-log.jsonl and write
`structured_output` to the declared path; run `tools/stage-check.py <node>`; on exit 0 commit
brief/ and only then write state/done/<node>. A red node gets one repair with the gate's stderr
appended verbatim; a second red stops the run (`critical`, the default) or degrades the node with a
coverage row. A sentinel the agent wrote is deleted unread.

    python3 tools/run.py graph [--stages DIR]
    python3 tools/run.py run <jd-url> [--slug S] [--dry-run] [--checkout DIR] [--branch B]
                                      [--stages DIR] [--test-root DIR]
    python3 tools/run.py resume <run-root>
    python3 tools/run.py invalidate <run-root> <node>

`run` refuses, exit 2 and before any mkdir or spawn, anything but one http(s) job-ad URL with a
dotted hostname, and under INTEL_BUILD=1 any run without --test-root (design.md M51).
`stub_harness()` is the launch harness land.py runs every test under.
"""
import concurrent.futures as cf
import datetime
import hashlib
import json
import os
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.parse

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parent.parent
STAGES = "references/stages"
BRANCH = "web-brief"
CAP = 12                      # concurrent node processes (design.md section 3)
EFFORTS = ("low", "medium", "high", "xhigh")
CACHE_READ_BASELINE = 72_900_000
GOVERNING = ("AGENTS.md", "CLAUDE.md", "references", "quality-bar", ".claude", "tools", "build", "bin")
ENV_KEEP = ("HOME", "PATH", "USER")   # a section Q3: env -i HOME PATH USER authenticates claude -p
TZ = "Europe/London"
GATE_STDERR_MAX = 60_000
PROMPT_MAX = 900_000          # argv bytes; macOS ARG_MAX is 1 MiB with the environment
GIT_ID = ["-c", "user.name=intel-run", "-c", "user.email=intel-run@localhost"]


class GraphError(Exception):
    pass


# ---- frontmatter: the YAML subset the templates use ------------------------------------------

def parse_scalar(text):
    s = text.strip()
    if not s:
        return None
    if s[0] in "[{":
        return parse_flow(s)
    if len(s) >= 2 and s[0] == s[-1] == '"':
        try:
            return json.loads(s)
        except ValueError:
            return s[1:-1]
    if len(s) >= 2 and s[0] == s[-1] == "'":
        return s[1:-1].replace("''", "'")
    low = s.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~"):
        return None
    if re.fullmatch(r"-?[0-9]+", s):
        return int(s)
    if re.fullmatch(r"-?[0-9]+\.[0-9]+", s):
        return float(s)
    return s


def parse_flow(s):
    value, i = _flow(s, 0)
    if s[i:].strip():
        raise GraphError(f"trailing text after flow value: {s!r}")
    return value


def _ws(s, i):
    while i < len(s) and s[i] in " \t":
        i += 1
    return i


def _flow(s, i):
    i = _ws(s, i)
    if i >= len(s):
        raise GraphError(f"unterminated flow value: {s!r}")
    c = s[i]
    if c == "[":
        out, i = [], i + 1
        while True:
            i = _ws(s, i)
            if i < len(s) and s[i] == "]":
                return out, i + 1
            value, i = _flow(s, i)
            out.append(value)
            i = _ws(s, i)
            if i < len(s) and s[i] == ",":
                i += 1
            elif not (i < len(s) and s[i] == "]"):
                raise GraphError(f"bad flow list: {s!r}")
    if c == "{":
        out, i = {}, i + 1
        while True:
            i = _ws(s, i)
            if i < len(s) and s[i] == "}":
                return out, i + 1
            j = s.find(":", i)
            if j < 0:
                raise GraphError(f"bad flow map: {s!r}")
            key = parse_scalar(s[i:j])
            value, i = _flow(s, j + 1)
            out[str(key)] = value
            i = _ws(s, i)
            if i < len(s) and s[i] == ",":
                i += 1
            elif not (i < len(s) and s[i] == "}"):
                raise GraphError(f"bad flow map: {s!r}")
    if c in "\"'":
        j = i + 1
        while j < len(s) and not (s[j] == c and s[j - 1] != "\\"):
            j += 1
        return parse_scalar(s[i:j + 1]), j + 1
    j, depth = i, 0          # a bare scalar may hold a `{item}` placeholder
    while j < len(s) and (depth or s[j] not in ",]}"):
        depth += (s[j] == "{") - (s[j] == "}" and depth > 0)
        j += 1
    return parse_scalar(s[i:j]), j


def _items(lines):
    out = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        out.append((len(line) - len(line.lstrip(" ")), stripped))
    return out


def _parse_map(items, i, indent):
    out = {}
    while i < len(items):
        ind, text = items[i]
        if ind < indent or (ind == indent and (text == "-" or text.startswith("- "))):
            break
        if ind > indent:
            raise GraphError(f"unexpected indent at {text!r}")
        key, sep, rest = text.partition(":")
        if not sep or not key.strip():
            raise GraphError(f"not a key: value line: {text!r}")
        key, rest = key.strip(), rest.strip()
        i += 1
        if rest:
            value = parse_scalar(rest)
        elif i < len(items) and (items[i][0] > ind or (
                items[i][0] == ind and (items[i][1] == "-" or items[i][1].startswith("- ")))):
            child = items[i][0]
            if items[i][1] == "-" or items[i][1].startswith("- "):
                value, i = _parse_list(items, i, child)
            else:
                value, i = _parse_map(items, i, child)
        else:
            value = None
        if key not in out:
            out[key] = value
    return out, i


def _parse_list(items, i, indent):
    out = []
    while i < len(items):
        ind, text = items[i]
        if ind != indent or not (text == "-" or text.startswith("- ")):
            break
        rest = text[1:].strip()
        if re.match(r"^[A-Za-z_][\w-]*:(\s|$)", rest):
            sub, j = [(indent + 2, rest)], i + 1
            while j < len(items) and items[j][0] > indent:
                sub.append(items[j])
                j += 1
            value, _ = _parse_map(sub, 0, indent + 2)
            out.append(value)
            i = j
        else:
            out.append(parse_scalar(rest))
            i += 1
    return out, i


def frontmatter(text):
    """(mapping, body); mapping is None when line 1 opens no closed `---` block."""
    lines = text.split("\n")
    if not lines or lines[0] != "---":
        return None, text
    for end in range(1, len(lines)):
        if lines[end] == "---":
            mapping, _ = _parse_map(_items(lines[1:end]), 0, 0)
            return mapping, "\n".join(lines[end + 1:]).lstrip("\n")
    return None, text


# ---- graph ----------------------------------------------------------------------------------

def _list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    return [str(value)]


def normalise(raw, source):
    name = raw.get("node")
    if not name:
        raise GraphError(f"{source}: a node without `node:`")
    run_cmd = raw.get("run")
    node = {
        "name": str(name),
        "kind": "code" if run_cmd else "agent",
        "role": raw.get("role"),
        "model": raw.get("model"),
        "effort": raw.get("effort"),
        "max_turns": raw.get("max_turns"),
        "timeout_min": raw.get("timeout_min"),
        "inputs": _list(raw.get("inputs")),
        "outputs": _list(raw.get("outputs")),
        "after": _list(raw.get("after")),
        "gate": _list(raw.get("gate")),
        "schema": raw.get("schema"),
        "lane": raw.get("lane"),
        "critical": raw.get("critical", True) is not False,
        "run": run_cmd,
        "template": raw.get("template") or (None if raw.get("prompt") else source),
        "prompt": raw.get("prompt"),
        "inline": _list(raw.get("inline")),
        "fanout": raw.get("fanout"),
        "when": raw.get("when"),
        "regen": raw.get("regen"),
        "notify": raw.get("notify"),
        "final": raw.get("final") is True,
        "mcp_config": raw.get("mcp_config"),
        "source": source,
    }
    return node


def round_group(entry, source):
    """The nodes of a `{group, rounds, nodes}` entry, every round of them, in round order."""
    group, count, members = entry.get("group"), entry.get("rounds"), entry.get("nodes")
    where = f"{source}: round group {group!r}"
    if not isinstance(group, str) or not group:
        raise GraphError(f"{source}: a round group needs `group:`, a name")
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise GraphError(f"{where}: rounds must be a positive integer, not {count!r}")
    if not isinstance(members, list) or not members or not all(isinstance(m, dict) for m in members):
        raise GraphError(f"{where}: `nodes:` must list its member nodes")
    bases = [normalise(m, source) for m in members]
    names = [b["name"] for b in bases]
    out = []
    for r in range(1, count + 1):
        suffix = "" if r == 1 else f"-r{r}"
        for i, b in enumerate(bases):
            inst = dict(b, name=b["name"] + suffix)
            for k in ("run", "when"):
                inst[k] = substitute(b[k], {"round": suffix})
            for k in ("gate", "inputs", "outputs", "inline"):
                inst[k] = [substitute(x, {"round": suffix}) for x in b[k]]
            inst["after"] = [d + suffix if d in names else d for d in b["after"]]
            if r > 1 and i == 0:
                inst["after"].append(names[-1] + ("" if r == 2 else f"-r{r - 1}"))
            inst["round"] = {"group": group, "index": r, "of": count, "base": b["name"], "first": i == 0,
                             "deps": [d + suffix for d in b["after"] if d in names]}
            out.append(inst)
    return out


def load_graph(root=ROOT, stages=STAGES):
    """{name: node} in file order, every node from every template's frontmatter."""
    directory = pathlib.Path(root) / stages
    if not directory.is_dir():
        raise GraphError(f"no stages directory: {directory}")
    graph = {}
    last_round = {}     # a round member's name -> its instance in the last round
    for path in sorted(directory.glob("*.md")):
        rel = str(path.relative_to(root))
        try:
            mapping, _ = frontmatter(path.read_text(encoding="utf-8"))
        except GraphError as exc:
            raise GraphError(f"{rel}: {exc}")
        if not mapping:
            continue
        nodes = []
        if mapping.get("node"):
            nodes.append(normalise(mapping, rel))
        for entry in mapping.get("nodes") or []:
            if not isinstance(entry, dict):
                raise GraphError(f"{rel}: a `nodes:` entry that is not a mapping")
            if "rounds" in entry or "group" in entry:
                for inst in round_group(entry, rel):
                    nodes.append(inst)
                    last_round[inst["round"]["base"]] = inst["name"]
            else:
                nodes.append(normalise(entry, rel))
        for node in nodes:
            if node["name"] in graph or node["name"] == "launch":
                raise GraphError(f"{rel}: node {node['name']!r} is defined twice")
            graph[node["name"]] = node
    for node in graph.values():
        if not node.get("round"):
            node["after"] = [last_round.get(d, d) for d in node["after"]]
    return graph


def round_counts(graph):
    """{group: rounds} for every round group in the graph."""
    return {n["round"]["group"]: n["round"]["of"] for n in graph.values() if n.get("round")}


def validate(graph, roles=None):
    """Every reason the graph cannot run, as strings. `roles`: compiled role names, when known."""
    errs = []
    names = set(graph) | {"launch"}
    for n in graph.values():
        where = f"{n['source']}: {n['name']}"
        for dep in n["after"]:
            if dep not in names:
                errs.append(f"{where}: after names unknown node {dep!r}")
        if n["kind"] == "agent":
            if not n["role"]:
                errs.append(f"{where}: an agent node needs `role:`")
            elif roles is not None and n["role"] not in roles:
                errs.append(f"{where}: role {n['role']!r} is not in .claude/agents/")
            if not n["model"]:
                errs.append(f"{where}: an agent node needs `model:`")
            if n["effort"] not in EFFORTS:
                errs.append(f"{where}: effort {n['effort']!r} is not one of {', '.join(EFFORTS)}")
            if not isinstance(n["max_turns"], int) or n["max_turns"] < 1:
                errs.append(f"{where}: max_turns must be a positive integer")
        if not isinstance(n["timeout_min"], (int, float)) or n["timeout_min"] <= 0:
            errs.append(f"{where}: timeout_min must be a positive number")
        if n["fanout"] is not None:
            f = n["fanout"]
            if not isinstance(f, dict) or not f.get("from") or not f.get("key"):
                errs.append(f"{where}: fanout needs {{from, list, key, copies}}")
        if n["regen"] is not None:
            r = n["regen"]
            if not isinstance(r, dict) or r.get("node") not in graph or not isinstance(r.get("exit"), int):
                errs.append(f"{where}: regen needs {{exit: int, node: <known node>, effort}}")
            elif r.get("effort") is not None and r["effort"] not in EFFORTS:
                errs.append(f"{where}: regen effort {r['effort']!r} is not one of {', '.join(EFFORTS)}")
    # cycles
    state = {}

    def visit(name, stack):
        if state.get(name) == 1:
            errs.append("cycle: " + " -> ".join(stack + [name]))
            return
        if state.get(name) == 2 or name not in graph:
            return
        state[name] = 1
        for dep in graph[name]["after"]:
            visit(dep, stack + [name])
        state[name] = 2

    for name in graph:
        visit(name, [])
    return errs


def descendants(graph, start):
    out, frontier = set(), {start}
    while frontier:
        nxt = {n for n, node in graph.items() if set(node["after"]) & frontier and n not in out}
        out |= nxt
        frontier = nxt
    return out


def format_graph(graph):
    lines = [f"{'node':<16} {'kind':<5} {'role':<11} {'model/effort':<14} {'turns':>5} {'min':>5}  "
             f"{'lane':<7} {'crit':<4} after",
             f"{'launch':<16} {'code':<5} {'-':<11} {'-':<14} {'-':>5} {'1':>5}  {'-':<7} {'yes':<4} -"]
    for n in graph.values():
        me = f"{n['model']}/{n['effort']}" if n["kind"] == "agent" else "-"
        extra = []
        if n["fanout"]:
            f = n["fanout"]
            extra.append(f"fanout {f.get('from')}:{f.get('key')} x{len(_list(f.get('copies'))) or 1}")
        if n["when"]:
            extra.append("conditional")
        if n["regen"]:
            extra.append(f"regen exit {n['regen'].get('exit')} -> {n['regen'].get('node')}")
        if n.get("round"):
            extra.append(f"{n['round']['group']} round {n['round']['index']} of {n['round']['of']}")
        if n["final"]:
            extra.append("final")
        if n["notify"]:
            extra.append("notifies")
        after = ",".join(n["after"]) or ("-" if n["final"] else "launch")
        lines.append(
            f"{n['name']:<16} {n['kind']:<5} {(n['role'] or '-'):<11} {me:<14} "
            f"{str(n['max_turns'] if n['kind'] == 'agent' else '-'):>5} {str(n['timeout_min']):>5}  {str(n['lane'] or '-'):<7} "
            f"{'yes' if n['critical'] else 'no':<4} {after}"
            + (f"  [{'; '.join(extra)}]" if extra else "")
            + f"  gates:{len(n['gate'])}")
    return "\n".join(lines)


# ---- helpers --------------------------------------------------------------------------------

def now():
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo(TZ))
    except Exception:
        return datetime.datetime.now(datetime.timezone.utc)


def iso(t=None):
    return (t or now()).isoformat(timespec="seconds")


class LaunchRefused(Exception):
    """A launch refused before any mkdir or spawn (exit 2, design.md M51)."""


def launch_refusal(jd_url, test_root=False):
    """None, or why a run must not start: anything but one http(s) URL with a dotted hostname.
    A `file://` URL is a fixture, accepted only where an explicit runs dir is set (INTEL_RUNS_DIR
    or --test-root), as run-selftest's launches set it. Under INTEL_BUILD=1 (a build session) only
    a --test-root run starts."""
    if os.environ.get("INTEL_BUILD") == "1" and not test_root:
        return "INTEL_BUILD=1: a build session starts no run (pass --test-root DIR in a test)"
    u = urllib.parse.urlparse(jd_url or "")
    if u.scheme == "file" and (test_root or os.environ.get("INTEL_RUNS_DIR")):
        return None
    host = u.hostname or ""
    if u.scheme not in ("http", "https") or "." not in host.strip("."):
        return f"want one http(s) job-ad URL with a dotted hostname, got {jd_url!r}"
    return None


def stub_harness(tmp):
    """The launch harness every land.py test runs under (design.md M51): a copy of
    tools/fixtures/run/claude-stub.py first on PATH as `claude` (and a no-op `osascript`),
    INTEL_BUILD=1, a temp INTEL_RUNS_DIR. Returns (env, stub log path); the stub appends every
    invocation to calls.jsonl beside its copy."""
    tmp = pathlib.Path(tmp)
    bindir = tmp / "stub-bin"
    bindir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "tools" / "fixtures" / "run" / "claude-stub.py", bindir / "claude")
    (bindir / "claude").chmod(0o755)
    (bindir / "osascript").write_text("#!/bin/sh\nexit 0\n")
    (bindir / "osascript").chmod(0o755)
    env = dict(os.environ, PATH=f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}", INTEL_BUILD="1",
               INTEL_RUNS_DIR=str(tmp / "runs"), PYTHONDONTWRITEBYTECODE="1")
    (tmp / "runs").mkdir(exist_ok=True)
    found = shutil.which("claude", path=env["PATH"])
    if not found or pathlib.Path(found).resolve() != (bindir / "claude").resolve():
        raise RuntimeError(f"stub harness: `command -v claude` is {found}, not the stub")
    return env, bindir / "calls.jsonl"


def default_slug(url):
    u = urllib.parse.urlparse(url)
    host = (u.hostname or "").lower()
    parts = [p for p in u.path.split("/") if p]
    boards = ("workable.com", "ashbyhq.com", "greenhouse.io", "lever.co", "recruitee.com",
              "teamtailor.com", "personio.de", "bamboohr.com", "breezy.hr")
    if host.endswith("notion.site") or host.endswith("notion.so"):
        name = host.split(".")[0]
    elif any(host.endswith(b) for b in boards) and parts:
        name = parts[0]
    else:
        labels = [x for x in host.split(".") if x not in ("www", "jobs", "careers", "apply", "boards")]
        name = labels[0] if labels else "run"
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "run"


def git(args, cwd, check=True, capture=True):
    p = subprocess.run(["git"] + args, cwd=cwd, stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE if capture else None,
                       stderr=subprocess.PIPE if capture else None, text=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}: {(p.stderr or '').strip()}")
    return (p.stdout or "").strip()


def governing_hash(clone):
    out = subprocess.run(["git", "ls-files", "-z", "--"] + list(GOVERNING), cwd=clone,
                         stdout=subprocess.PIPE, check=True).stdout
    h = hashlib.sha256()
    for rel in sorted(x for x in out.decode().split("\0") if x):
        path = pathlib.Path(clone) / rel
        if path.is_file():
            h.update(rel.encode() + b"\0" + path.read_bytes() + b"\0")
    return h.hexdigest()


def notify(root, title, message):
    with open(pathlib.Path(root) / "notifications.log", "a", encoding="utf-8") as f:
        f.write(f"{iso()}\t{title}\t{message}\n")
    if shutil.which("osascript"):
        esc = lambda s: s.replace("\\", "\\\\").replace('"', '\\"')
        subprocess.run(["osascript", "-e",
                        f'display notification "{esc(message)}" with title "{esc(title)}"'],
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def tsv(value):
    return str(value).replace("\t", " ").replace("\n", " ").strip()


def read_json(path, default=None):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


SCHEMA_MAPS = ("properties", "patternProperties", "$defs", "definitions", "dependentSchemas")
SCHEMA_ONE = ("items", "additionalProperties", "not", "if", "then", "else", "contains",
              "propertyNames", "unevaluatedProperties", "unevaluatedItems", "additionalItems")
SCHEMA_LIST = ("allOf", "anyOf", "oneOf", "prefixItems")


def cli_schema(node):
    """The schema as `claude --json-schema` accepts it. The CLI's validator runs in strict mode on
    its own default draft: `$schema` 2020-12 is "no schema with key or ref" and an `x-` keyword is
    "unknown keyword" (both measured 2026-10-13), so both go. `$id` and `$defs` refs pass. The
    dropped `x-` rules still bind: the node's gate runs `tools/schema.py` on the full schema."""
    if isinstance(node, list):
        return [cli_schema(x) for x in node]
    if not isinstance(node, dict):
        return node
    out = {}
    for key, value in node.items():
        if key == "$schema" or key.startswith("x-"):
            continue
        if key in SCHEMA_MAPS and isinstance(value, dict):
            out[key] = {k: cli_schema(v) for k, v in value.items()}
        elif key in SCHEMA_ONE or key in SCHEMA_LIST:
            out[key] = cli_schema(value)
        else:
            out[key] = value
    return out


def substitute(text, var):
    if text is None:
        return None
    for k, v in var.items():
        text = text.replace("{" + k + "}", str(v))
    return text


# ---- the run --------------------------------------------------------------------------------

class Run:
    def __init__(self, root):
        self.root = pathlib.Path(root)
        self.clone = self.root / "clone"
        self.brief = self.root / "brief"
        self.logs = self.root / "logs"
        self.prompts = self.root / "prompts"
        self.state = self.root / "state"
        self.meta = read_json(self.root / "run.json", {})
        self.lock = threading.Lock()
        self.git_lock = threading.Lock()
        self.procs = set()
        self.done, self.degraded, self.skipped, self.failed = set(), set(), set(), set()
        self.started = set()
        self.attempts = {}
        self.effort_override = {}
        self.regen_context = {}
        self.regenerated = set()
        self.stop = None
        self.graph = {}

    # -- launch --
    @classmethod
    def launch(cls, jd_url, slug, checkout, branch, stages, runs_dir, test_root=False):
        refused = launch_refusal(jd_url, test_root)
        if refused:
            raise LaunchRefused(refused)
        date = now().date().isoformat()
        runs_dir.mkdir(parents=True, exist_ok=True)
        root = runs_dir / f"{slug}-{date}"
        n = 2
        while root.exists():
            root = runs_dir / f"{slug}-{date}-{n}"
            n += 1
        for sub in ("logs", "prompts", "state/done", "state/failed", "state/running", "compound"):
            (root / sub).mkdir(parents=True, exist_ok=True)
        print(root, flush=True)
        run = cls(root)
        start = iso()
        origin = git(["remote", "get-url", "origin"], checkout)
        # A linked worktree cannot be a --reference; its common git dir can.
        common = pathlib.Path(git(["rev-parse", "--git-common-dir"], checkout))
        reference = common if common.is_absolute() else (pathlib.Path(checkout) / common).resolve()
        git(["clone", "-q", "--reference", str(reference), "--branch", branch, origin, str(run.clone)],
            root)
        git(["sparse-checkout", "set", "--no-cone", "/*", "!/.claude/agent-memory/"], run.clone)
        if (run.clone / ".claude" / "agent-memory").exists():
            raise RuntimeError("launch: .claude/agent-memory survived the sparse checkout")
        with open(run.clone / ".git" / "info" / "exclude", "a", encoding="utf-8") as f:
            f.write("\n.run-active\n__pycache__/\n/tools/agents.json\n")
        clone_sha = git(["rev-parse", "HEAD"], run.clone)
        local = git(["rev-parse", "HEAD"], checkout, check=False)
        if local and local != clone_sha:
            print(f"note: checkout HEAD {local[:12]} differs from origin/{branch} {clone_sha[:12]};"
                  " the run uses the pushed head", flush=True)
        (run.clone / ".run-active").write_text(f"{root.name}\n")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        comp = subprocess.run([sys.executable, "tools/agents-compile.py", "--out", "tools/agents.json"],
                              cwd=run.clone, env=env, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True)
        if comp.returncode != 0:
            raise RuntimeError("launch: agents compile red:\n" + comp.stdout + comp.stderr)
        run.brief.mkdir()
        (run.brief / ".gitignore").write_text("pages/\n")
        git(["init", "-q"], run.brief)
        git(GIT_ID + ["commit", "-q", "--allow-empty", "-m", "launch"], run.brief)
        git(["add", "-A"], run.brief)
        git(GIT_ID + ["commit", "-q", "-m", "launch: .gitignore"], run.brief)
        run.graph = load_graph(run.clone, stages)
        roles = set(read_json(run.clone / "tools" / "agents.json", {}))
        errs = validate(run.graph, roles)
        run.meta = {
            "run_id": root.name, "slug": slug, "tz": TZ, "jd_url": jd_url, "clone_sha": clone_sha,
            "governing_hash": governing_hash(run.clone), "bar_key": None, "started_at": start,
            "checkout": str(checkout), "branch": branch, "stages": stages, "pid": os.getpid(),
            "nodes": {n["name"]: {k: n[k] for k in ("kind", "role", "model", "effort", "max_turns",
                                                     "timeout_min", "lane", "critical")}
                      for n in run.graph.values()},
            "rounds": round_counts(run.graph),
        }
        run.save_meta()
        if errs:
            raise RuntimeError("launch: the graph cannot run:\n  " + "\n  ".join(errs))
        run.seal_record("launch", 1)
        run.done.add("launch")
        return run

    def save_meta(self):
        (self.root / "run.json").write_text(json.dumps(self.meta, indent=1) + "\n")

    # -- resume --
    @classmethod
    def resume(cls, root):
        run = cls(root)
        if not run.meta:
            raise RuntimeError(f"resume: no run.json in {root}")
        pid = run.meta.get("pid")
        if pid and pid != os.getpid():
            try:
                os.kill(pid, 0)
                raise RuntimeError(f"resume: runner pid {pid} is still alive")
            except ProcessLookupError:
                pass
            except PermissionError:
                raise RuntimeError(f"resume: runner pid {pid} is still alive")
        run.graph = load_graph(run.clone, run.meta.get("stages", STAGES))
        errs = validate(run.graph, set(read_json(run.clone / "tools" / "agents.json", {})))
        if errs:
            raise RuntimeError("resume: the graph cannot run:\n  " + "\n  ".join(errs))
        commits = set(git(["log", "--format=%H"], run.brief).split())
        for f in (run.state / "done").glob("*"):
            rec = read_json(f, {})
            if rec.get("brief_commit") in commits:
                run.done.add(f.name)
            else:
                f.unlink()
        for f in (run.state / "running").glob("*"):
            f.unlink()
        for f in (run.logs).glob("*-*.*"):
            m = re.match(r"(.+)-([0-9]+)\.(jsonl|out)$", f.name)
            if m:
                run.attempts[m.group(1)] = max(run.attempts.get(m.group(1), 0), int(m.group(2)))
        run.meta["pid"] = os.getpid()
        run.save_meta()
        (run.clone / ".run-active").write_text(f"{run.root.name}\n")
        # Fan-out instances done in an earlier process re-enter through their base on expansion.
        return run

    # -- bookkeeping --
    def log_row(self, row):
        with self.lock:
            with open(self.root / "run-log.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def seal_record(self, name, attempt):
        with self.git_lock:
            git(["add", "-A"], self.brief)
            git(GIT_ID + ["commit", "-q", "--allow-empty", "-m", f"freeze {name} attempt {attempt}"],
                self.brief)
            sha = git(["rev-parse", "HEAD"], self.brief)
        rec = {"node": name, "attempt": attempt, "gate_exit": 0, "brief_commit": sha, "at": iso()}
        (self.state / "done" / name).write_text(json.dumps(rec) + "\n")

    def write_decisions(self, name, decisions):
        if not isinstance(decisions, list) or not decisions:
            return
        path = self.root / "decisions.tsv"
        with self.lock:
            fresh = not path.exists()
            count = 0 if fresh else max(0, len(path.read_text(encoding="utf-8").splitlines()) - 1)
            with open(path, "a", encoding="utf-8") as f:
                if fresh:
                    f.write("id\tnode\tquestion\tchosen\treason\n")
                for d in decisions:
                    if not isinstance(d, dict):
                        continue
                    count += 1
                    f.write(f"D-{count:03d}\t{name}\t{tsv(d.get('question', ''))}\t"
                            f"{tsv(d.get('chosen', ''))}\t{tsv(d.get('reason', ''))}\n")

    def coverage_row(self, name, reason):
        path = self.brief / "coverage.tsv"
        with self.lock:
            fresh = not path.exists()
            with open(path, "a", encoding="utf-8") as f:
                if fresh:
                    f.write("node\treason\n")
                f.write(f"{name}\t{tsv(reason)[:500]}\n")

    def env_vars(self, node, attempt):
        v = {"RUN_ID": self.meta.get("run_id", self.root.name), "RUN_NODE": node["name"],
             "BRIEF_ROOT": str(self.brief), "PYTHONDONTWRITEBYTECODE": "1"}
        return v

    def run_vars(self, node, attempt):
        var = {
            "RUN_ID": self.meta.get("run_id"), "BRIEF_ROOT": str(self.brief),
            "RUN_ROOT": str(self.root), "clone": str(self.clone), "node": node["name"],
            "attempt": attempt, "jd_url": self.meta.get("jd_url"), "slug": self.meta.get("slug"),
            "date": now().date().isoformat(), "tz": TZ, "run_store": str(self.brief),
            "effort": self.effort_override.get(node["name"], node["effort"]),
        }
        for k in ("item", "copy"):
            if node.get("var", {}).get(k) is not None:
                var[k] = node["var"][k]
        veto = read_json(self.root / "veto.json")
        if veto:
            var["veto"] = veto
        return var

    # -- prompt --
    def body(self, node):
        if node.get("prompt"):
            return substitute(str(node["prompt"]), node.get("var", {}))
        path = self.clone / node["template"]
        if not path.is_file():
            raise FileNotFoundError(f"template {node['template']} is not in the clone")
        _, body = frontmatter(path.read_text(encoding="utf-8"))
        return substitute(body, node.get("var", {}))

    def prompt(self, node, attempt, repair):
        b = lambda rel: str(self.brief / rel)
        inputs = {"inputs": {p: b(p) for p in node["inputs"]},
                  "outputs": {p: b(p) for p in node["outputs"]},
                  "run": self.run_vars(node, attempt)}
        text = self.body(node).rstrip("\n") + "\n"
        for rel in node.get("inline") or []:
            path = self.brief / rel
            if not path.is_file():
                raise FileNotFoundError(f"inline file {rel} is not under BRIEF_ROOT")
            text += "\n" + path.read_text(encoding="utf-8").rstrip("\n") + "\n"
        text += "\nINPUTS:\n" + json.dumps(inputs, indent=1) + "\n"
        regen = self.regen_context.get(node["name"])
        if regen:
            text += ("\nREGEN: every candidate of the last lock was ineligible. The rank step's "
                     "output, verbatim, between the markers:\n<<<RANK\n" + regen + "\nRANK>>>\n")
        if repair is not None:
            if len(repair) > GATE_STDERR_MAX:
                repair = repair[:GATE_STDERR_MAX] + "\n[... truncated by the runner]"
            text += (f"\nREPAIR (attempt {attempt}). The node's gate went red on attempt "
                     f"{attempt - 1}. Its stderr, verbatim, between the markers:\n<<<GATE-STDERR\n"
                     + repair + "\nGATE-STDERR>>>\nFix exactly what it names. Everything else you "
                     "wrote is on disk as you left it.\n")
            # A typed node's answer is replaced whole and a fresh process never saw it, so its
            # last answer comes back verbatim, to be returned with only the named fixes (S7b).
            for rel in [o for o in node["outputs"] if o.endswith(".json")] if node["schema"] else []:
                if (self.brief / rel).is_file():
                    text += (f"\nYour typed answer on attempt {attempt - 1} ({rel}), verbatim, between the "
                             "markers. Return it whole, changed only where the stderr above points:\n<<<PREVIOUS\n"
                             + (self.brief / rel).read_text(encoding="utf-8").rstrip("\n") + "\nPREVIOUS>>>\n")
        return text

    def schema(self, node):
        """(schema text, injected) or (None, False)."""
        spec = node["schema"]
        if not spec:
            return None, False
        paths = _list(spec)
        loaded = []
        for rel in paths:
            path = self.clone / rel
            if not path.is_file():
                raise FileNotFoundError(f"schema {rel} is not in the clone")
            loaded.append((pathlib.Path(rel).name.split(".")[0], json.loads(path.read_text())))
        if len(loaded) == 1:
            schema = loaded[0][1]
        else:
            # One object, a property per file. Each file's `$defs` moves to the root under a
            # `<stem>__` prefix, because its `#/$defs/...` refs resolve against the root.
            defs, props = {}, {}
            for stem, sub in loaded:
                sub = json.loads(json.dumps(sub).replace('"#/$defs/', f'"#/$defs/{stem}__')
                                 .replace('"#/definitions/', f'"#/$defs/{stem}__'))
                sub.pop("$id", None)   # an inner $id rebases its refs away from the root
                for key in ("$defs", "definitions"):
                    for name, d in (sub.pop(key, None) or {}).items():
                        defs[f"{stem}__{name}"] = d
                props[stem] = sub
            schema = {"type": "object", "additionalProperties": False, "properties": props,
                      "required": list(props)}
            if defs:
                schema["$defs"] = defs
        schema = cli_schema(schema)
        injected = False
        if isinstance(schema.get("properties"), dict) and "decisions" not in schema["properties"]:
            schema = dict(schema, properties=dict(schema["properties"], decisions={
                "type": "array", "items": {"type": "object", "properties": {
                    "question": {"type": "string"}, "chosen": {"type": "string"},
                    "reason": {"type": "string"}}, "required": ["question", "chosen", "reason"]}}))
            injected = True
        return json.dumps(schema), injected

    def write_structured(self, node, data, injected):
        decisions = data.get("decisions") if isinstance(data, dict) else None
        if injected and isinstance(data, dict):
            data = {k: v for k, v in data.items() if k != "decisions"}
        jsons = [o for o in node["outputs"] if o.endswith(".json")]
        stems = {pathlib.Path(o).name.split(".")[0]: o for o in jsons}
        targets = []
        if len(jsons) > 1 and isinstance(data, dict) and set(stems) <= set(data):
            targets = [(stems[s], data[s]) for s in stems]
        elif node["outputs"]:
            targets = [(node["outputs"][0], data)]
        for rel, value in targets:
            path = self.brief / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        self.write_decisions(node["name"], decisions)

    # -- processes --
    def _spawn(self, cmd, cwd, env, out, err, timeout_s):
        with open(out, "wb") as fo, open(err, "wb") as fe:
            p = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=fo,
                                 stderr=fe, start_new_session=True)
            with self.lock:
                self.procs.add(p)
            timed_out = False
            try:
                rc = p.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                timed_out = True
                self._kill(p)
                rc = p.wait()
            finally:
                with self.lock:
                    self.procs.discard(p)
        return rc, timed_out

    def _kill(self, p):
        try:
            os.killpg(p.pid, signal.SIGTERM)
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    def kill_all(self):
        with self.lock:
            procs = list(self.procs)
        for p in procs:
            self._kill(p)

    def gate(self, node):
        env = dict(os.environ)
        env.update(self.env_vars(node, 0))
        env.update({"RUN_ROOT": str(self.root), "RUN_STAGES": self.meta.get("stages", STAGES),
                    "RUN_BASE_NODE": node.get("base", node["name"]),
                    "RUN_ITEM": str(node.get("var", {}).get("item", "")),
                    "RUN_COPY": str(node.get("var", {}).get("copy", ""))})
        p = subprocess.run([sys.executable, str(self.clone / "tools" / "stage-check.py"), node["name"]],
                           cwd=self.clone, env=env, stdin=subprocess.DEVNULL, capture_output=True,
                           text=True)
        return p.returncode, p.stderr

    def agent_attempt(self, node, attempt, repair):
        name = node["name"]
        tag = f"{name}-{attempt}"
        text = self.prompt(node, attempt, repair)
        (self.prompts / f"{tag}.txt").write_text(text, encoding="utf-8")
        if len(text.encode()) > PROMPT_MAX:
            return {"red": f"runner: prompt is {len(text.encode())} bytes, over the {PROMPT_MAX} argv cap"}
        schema, injected = self.schema(node)
        effort = self.effort_override.get(name, node["effort"])
        cmd = ["claude", "-p", text,
               "--agents", str(self.clone / "tools" / "agents.json"), "--agent", node["role"],
               "--model", str(node["model"]), "--effort", effort,
               "--max-turns", str(node["max_turns"]),
               "--setting-sources", "", "--settings", str(self.clone / "tools" / "run-settings.json"),
               "--strict-mcp-config", "--dangerously-skip-permissions", "--no-session-persistence",
               "--output-format", "stream-json", "--verbose"]
        if node.get("mcp_config"):
            cmd += ["--mcp-config", str(self.clone / node["mcp_config"])]
        if schema:
            cmd += ["--json-schema", schema]
        env = {k: os.environ[k] for k in ENV_KEEP if k in os.environ}
        env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
        env.update(self.env_vars(node, attempt))
        start = iso()
        rc, timed_out = self._spawn(cmd, self.clone, env, self.logs / f"{tag}.jsonl",
                                    self.logs / f"{tag}.err", float(node["timeout_min"]) * 60)
        result = None
        with open(self.logs / f"{tag}.jsonl", encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if isinstance(event, dict) and event.get("type") == "result":
                    result = event
        result = result or {}
        row = {"node": name, "kind": "agent", "role": node["role"], "model": node["model"],
               "effort": effort, "attempt": attempt, "start": start, "end": iso(), "exit": rc,
               "timed_out": timed_out}
        for k in ("subtype", "is_error", "terminal_reason", "num_turns", "duration_ms",
                  "duration_api_ms", "usage", "modelUsage", "total_cost_usd", "permission_denials"):
            row[k] = result.get(k)
        red = None
        if timed_out:
            red = f"runner: wall timeout after {node['timeout_min']} min"
        elif rc != 0 or result.get("is_error") or result.get("subtype") not in ("success",):
            tail = (self.logs / f"{tag}.err").read_text(errors="replace")[-2000:].strip()
            red = (f"agent: exit {rc}, subtype {result.get('subtype')}, terminal_reason "
                   f"{result.get('terminal_reason')}" + (f"\n{tail}" if tail else ""))
        elif schema:
            if result.get("structured_output") is None:
                red = "agent: --json-schema was passed and the result carries no structured_output"
            else:
                self.write_structured(node, result["structured_output"], injected)
        return {"row": row, "red": red}

    def code_attempt(self, node, attempt):
        name = node["name"]
        tag = f"{name}-{attempt}"
        env = dict(os.environ)
        env.update(self.env_vars(node, attempt))
        env.update({"RUN_ROOT": str(self.root)})
        for k, v in node.get("var", {}).items():
            env["RUN_" + k.upper()] = str(v)
        start = iso()
        cmd = substitute(node["run"], node.get("var", {}))
        (self.prompts / f"{tag}.txt").write_text(cmd + "\n", encoding="utf-8")
        rc, timed_out = self._spawn(["bash", "-c", cmd], self.clone, env, self.logs / f"{tag}.out",
                                    self.logs / f"{tag}.err", float(node["timeout_min"]) * 60)
        row = {"node": name, "kind": "code", "attempt": attempt, "start": start, "end": iso(),
               "exit": rc, "timed_out": timed_out}
        out = (self.logs / f"{tag}.out").read_text(errors="replace")
        err = (self.logs / f"{tag}.err").read_text(errors="replace")
        red = None
        if timed_out:
            red = f"runner: wall timeout after {node['timeout_min']} min"
        elif rc != 0:
            red = f"code: `{cmd}` exited {rc}\n{(err or out)[-4000:]}"
        return {"row": row, "red": red, "rc": rc, "out": out, "err": err}

    def execute(self, node):
        """Run one node to its outcome: done, red, skipped or regen. Never raises."""
        name = node["name"]
        running = self.state / "running" / name
        try:
            deps = (node.get("round") or {}).get("deps")
            if deps and all(d in self.skipped for d in deps):
                return {"name": name, "status": "skipped"}   # a round that did not start
            if node.get("when"):
                cond = subprocess.run(["bash", "-c", substitute(node["when"], node.get("var", {}))],
                                      cwd=self.clone, env=dict(os.environ, **self.env_vars(node, 0)),
                                      stdin=subprocess.DEVNULL, capture_output=True)
                if cond.returncode != 0:
                    return {"name": name, "status": "skipped"}
            tries = 1 if node["kind"] == "code" else 2
            repair = None
            last = ""
            for _ in range(tries):
                with self.lock:
                    attempt = self.attempts.get(name, 0) + 1
                    self.attempts[name] = attempt
                running.write_text(json.dumps({"start": iso(), "attempt": attempt}))
                if node["kind"] == "code":
                    res = self.code_attempt(node, attempt)
                    regen = node.get("regen")
                    if regen and res["rc"] == regen.get("exit"):
                        res["row"]["regen"] = True
                        self.log_row(res["row"])
                        return {"name": name, "status": "regen",
                                "text": (res["out"] + res["err"])[-GATE_STDERR_MAX:]}
                else:
                    res = self.agent_attempt(node, attempt, repair)
                # An agent-written sentinel is ignored: only seal() below writes one.
                stray = self.state / "done" / name
                if stray.exists():
                    stray.unlink()
                red = res["red"]
                gate_exit, gate_err = None, ""
                if red is None:
                    gate_exit, gate_err = self.gate(node)
                    if gate_exit != 0:
                        red = gate_err or f"stage-check exited {gate_exit} with no stderr"
                row = res.get("row", {"node": name, "attempt": attempt})
                row["gate_exit"] = gate_exit
                row["gate_stderr"] = gate_err
                self.log_row(row)
                if red is None:
                    self.seal_record(name, attempt)
                    return {"name": name, "status": "done"}
                repair = red
                last = red
            return {"name": name, "status": "red", "reason": last}
        except Exception as exc:  # a runner fault is a red node, never a hung run
            return {"name": name, "status": "red", "reason": f"runner: {exc.__class__.__name__}: {exc}"}
        finally:
            if running.exists():
                running.unlink()

    # -- scheduling --
    def satisfied(self, name):
        return name in self.done or name in self.degraded or name in self.skipped

    def expand(self, node):
        f = node["fanout"]
        data = read_json(self.brief / str(f["from"]))
        if data is None:
            raise RuntimeError(f"fanout: {f['from']} is missing or not JSON")
        items = data.get(f.get("list")) if f.get("list") else data
        if not isinstance(items, list) or not items:
            raise RuntimeError(f"fanout: {f['from']} has no items under {f.get('list')!r}")
        copies = _list(f.get("copies")) or [None]
        names = []
        for item in items:
            key = item.get(f["key"]) if isinstance(item, dict) else item
            for copy in copies:
                var = {"item": key} if copy is None else {"item": key, "copy": copy}
                inst = dict(node, var=var, base=node["name"], fanout=None,
                            name=f"{node['name']}-{key}" + (f"-{copy}" if copy else ""))
                for k in ("inputs", "outputs", "gate", "inline"):
                    inst[k] = [substitute(x, var) for x in node.get(k) or []]
                names.append(inst["name"])
                self.graph[inst["name"]] = inst
        node["instances"] = names
        self.started.add(node["name"])
        for inst in names:  # resumed instances
            if (self.state / "done" / inst).exists() and inst in self.done:
                self.started.add(inst)
        # A resume whose instances all finished in an earlier process has no instance left to
        # finish, so nothing else would close the base and every node after it is unreachable.
        self.group_check(node["name"])

    def group_check(self, base):
        node = self.graph[base]
        insts = node.get("instances") or []
        if not all(self.satisfied(i) or i in self.failed for i in insts):
            return
        if any(i in self.failed for i in insts):
            if node["critical"]:
                self.failed.add(base)
                self.stop = self.stop or f"{base}: an instance went red twice"
            else:
                self.degraded.add(base)
        else:
            self.done.add(base)

    def reset(self, names):
        for name in names:
            node = self.graph.get(name)
            if node is None:
                continue
            for inst in node.pop("instances", []) or []:
                self.graph.pop(inst, None)
                for s in (self.done, self.degraded, self.skipped, self.failed, self.started):
                    s.discard(inst)
                f = self.state / "done" / inst
                if f.exists():
                    f.unlink()
            for s in (self.done, self.degraded, self.skipped, self.failed, self.started):
                s.discard(name)
            f = self.state / "done" / name
            if f.exists():
                f.unlink()

    def handle(self, outcome):
        name, status = outcome["name"], outcome["status"]
        node = self.graph[name]
        if status == "done":
            self.done.add(name)
            if node.get("notify"):
                notify(self.root, str(node["notify"]), f"{name} done: {self.brief}")
        elif status == "skipped":
            self.skipped.add(name)
        elif status == "regen":
            regen = node["regen"]
            if name in self.regenerated:
                self.failed.add(name)
                (self.state / "failed" / name).write_text(json.dumps(
                    {"reason": "no eligible candidate after one regeneration", "at": iso()}))
                self.stop = self.stop or f"{name}: no eligible candidate after one regeneration"
                notify(self.root, "Competitor Intel: blocked", self.stop)
            else:
                self.regenerated.add(name)
                target = regen["node"]
                self.effort_override[target] = regen.get("effort") or self.graph[target]["effort"]
                self.regen_context[target] = outcome.get("text", "")
                bases = {n.get("base", n["name"]) for n in self.graph.values()}
                self.reset({target} | (descendants(self.graph, target) & bases))
        else:
            reason = outcome.get("reason", "")
            (self.state / "failed" / name).write_text(json.dumps({"reason": reason[-4000:], "at": iso()}))
            if node["critical"] and not node.get("base"):
                self.failed.add(name)
                # A code node gets one attempt, and one that stops the run on purpose says why on a
                # `STOP <kind>: <reason>` line (prefetch-client's AGENTS.md hard stop).
                typed = next((l for l in reason.splitlines() if l.startswith("STOP ")), None)
                why = typed or ("red" if node["kind"] == "code" else "red twice")
                self.stop = self.stop or f"{name}: {why}"
            elif node.get("base") and self.graph[node["base"]]["critical"]:
                self.failed.add(name)
            else:
                self.degraded.add(name)
                self.coverage_row(name, reason)
        if node.get("base"):
            self.group_check(node["base"])

    def ready(self):
        out = []
        for name, node in list(self.graph.items()):
            if name in self.started or node["final"] or self.satisfied(name) or name in self.failed:
                continue
            deps = node["after"] or ["launch"]
            if all(self.satisfied(d) for d in deps):
                out.append(node)
        return out

    def schedule(self):
        with cf.ThreadPoolExecutor(max_workers=CAP) as ex:
            futures = {}
            while True:
                if not self.stop:
                    for node in self.ready():
                        if node["fanout"]:
                            try:
                                self.expand(node)
                            except Exception as exc:
                                self.handle({"name": node["name"], "status": "red", "reason": str(exc)})
                            continue
                        if node["name"] in self.done:
                            continue
                        self.started.add(node["name"])
                        futures[ex.submit(self.execute, node)] = node["name"]
                if not futures:
                    if self.stop or not self.ready():
                        break
                    continue
                finished, _ = cf.wait(futures, return_when=cf.FIRST_COMPLETED)
                for f in finished:
                    futures.pop(f)
                    self.handle(f.result())
        pending = [n for n, node in self.graph.items() if not node["final"] and not node.get("fanout")
                   and not self.satisfied(n) and n not in self.failed]
        if pending and not self.stop:
            self.stop = "unreachable nodes: " + ", ".join(pending)

    def finals(self):
        for node in [n for n in self.graph.values() if n["final"]]:
            if node["name"] in self.done:
                continue
            outcome = self.execute(node)
            if outcome["status"] == "done":
                self.done.add(node["name"])
                for rel in node["outputs"]:
                    src = self.brief / rel
                    if src.is_file():
                        shutil.copy2(src, self.root / "compound" / src.name)
            else:
                self.degraded.add(node["name"])
                (self.state / "failed" / node["name"]).write_text(
                    json.dumps({"reason": outcome.get("reason", "")[-4000:], "at": iso()}))

    def report(self, problems):
        reader = read_json(self.brief / "reader.json", {}) or {}
        rec = reader.get("recipient") if isinstance(reader, dict) else None
        if isinstance(rec, dict) and rec.get("name"):
            first = (f"RECIPIENT {rec.get('name')}, {rec.get('title') or '[Unknown] title'} "
                     f"(confidence {rec.get('confidence', '[Unknown]')})")
        else:
            first = "RECIPIENT [Unknown]: no reader.json recipient"
        lines = [first]
        # Line 2 is SHARE only when the publish node sealed, which it does on publish.py exit 0 or 31.
        share = []
        if "publish" in self.done and (self.brief / "11-delivery.md").is_file():
            share = [l for l in (self.brief / "11-delivery.md").read_text(errors="replace").splitlines()
                     if l.startswith("SHARE ")]
        if share:
            lines.append(share[0])
        elif self.stop:
            lines.append(f"NOT SHARED: the run stopped: {self.stop}")
        else:
            lines.append("NOT SHARED: " + ("publish printed no SHARE line" if "publish" in self.done
                                           else "no publish node ran"))
        lines.append(f"RUN {self.root}")
        lines.append(f"CLONE {self.meta.get('clone_sha')}")
        for p in problems:
            lines.append(f"PROBLEM {p}")
        for group, count in round_counts(self.graph).items():
            used = sum(1 for n in self.graph.values() if n.get("round") and n["round"]["group"] == group
                       and n["round"]["first"] and n["name"] in self.done)
            lines.append(f"ROUNDS {group}: {used} of {count} used")
        for name in self.graph:
            node = self.graph[name]
            if node.get("base"):
                continue
            state = ("done" if name in self.done else "degraded" if name in self.degraded else
                     "skipped" if name in self.skipped else "failed" if name in self.failed else
                     "not run")
            lines.append(f"NODE {name} {state}")
        c = cost(self.root)
        lines.append(f"COST cache_read {c['cache_read']:,} of {CACHE_READ_BASELINE:,} "
                     f"({c['cache_read'] / CACHE_READ_BASELINE:.0%}); output {c['output']:,}")
        dec = self.root / "decisions.tsv"
        if dec.exists():
            lines.append("DECISIONS")
            lines += ["  " + l for l in dec.read_text(encoding="utf-8").splitlines()[1:]]
        (self.root / "report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return lines

    def go(self):
        def on_signal(signum, _frame):
            self.stop = self.stop or f"signal {signum}"
            self.kill_all()
        old = {s: signal.signal(s, on_signal) for s in (signal.SIGINT, signal.SIGTERM)}
        problems = []
        try:
            self.schedule()
        except Exception as exc:
            self.stop = self.stop or f"runner fault: {exc}"
        finally:
            try:
                (self.root / "compound").mkdir(exist_ok=True)
                c = cost(self.root)
                (self.root / "compound" / "run-cost.txt").write_text(json.dumps(c, indent=1) + "\n")
                self.finals()
            except Exception as exc:
                problems.append(f"finally: {exc}")
            dirty = git(["status", "--porcelain"], self.clone, check=False)
            if dirty:
                problems.append("the clone is not clean:\n" + dirty)
            if governing_hash(self.clone) != self.meta.get("governing_hash"):
                problems.append("the governing tree changed during the run")
            self.report(problems)
            active = self.clone / ".run-active"
            if active.exists():
                active.unlink()
            for s, h in old.items():
                signal.signal(s, h)
            ok = not self.stop and not problems
            notify(self.root, "Competitor Intel: " + ("done" if ok else "failed"),
                   f"{self.root.name}: " + ("report.txt" if ok else (self.stop or problems[0])))
        return 0 if ok else 1


# ---- reading a run --------------------------------------------------------------------------

def run_log(root):
    rows = []
    path = pathlib.Path(root) / "run-log.jsonl"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    return rows


def cost(root):
    out = {"cache_read": 0, "cache_creation": 0, "input": 0, "output": 0, "cost_usd": 0.0, "calls": 0}
    for r in run_log(root):
        u = r.get("usage") or {}
        if not u:
            continue
        out["calls"] += 1
        out["cache_read"] += u.get("cache_read_input_tokens") or 0
        out["cache_creation"] += u.get("cache_creation_input_tokens") or 0
        out["input"] += u.get("input_tokens") or 0
        out["output"] += u.get("output_tokens") or 0
        out["cost_usd"] += r.get("total_cost_usd") or 0
    return out


def _secs(a, b):
    try:
        return (datetime.datetime.fromisoformat(b) - datetime.datetime.fromisoformat(a)).total_seconds()
    except (TypeError, ValueError):
        return None


def node_minutes(root):
    """{node: minutes summed over attempts} from run-log.jsonl."""
    out = {}
    for r in run_log(root):
        s = _secs(r.get("start"), r.get("end"))
        if s is not None:
            out[r["node"]] = out.get(r["node"], 0) + s / 60
    return out


def wall_minutes(root):
    rows = run_log(root)
    starts = [r["start"] for r in rows if r.get("start")]
    ends = [r["end"] for r in rows if r.get("end")]
    if not starts or not ends:
        return None
    return _secs(min(starts), max(ends)) / 60


def median(xs):
    xs = sorted(xs)
    if not xs:
        return None
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2


def percentile(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    k = max(0, min(len(xs) - 1, int(round(q * (len(xs) - 1)))))
    return xs[k]


def prior_runs(root):
    parent = pathlib.Path(root).parent
    return [p for p in sorted(parent.iterdir()) if p.is_dir() and p != pathlib.Path(root)
            and (p / "run-log.jsonl").exists()]


def status(root):
    root = pathlib.Path(root)
    meta = read_json(root / "run.json", {})
    graph = load_graph(root / "clone", meta.get("stages", STAGES))
    prior = [node_minutes(p) for p in prior_runs(root)]
    mine = node_minutes(root)
    lines = [f"{'node':<16} {'state':<9} {'elapsed':>8} {'median':>8}"]
    names = ["launch"] + list(graph)
    for f in (root / "state" / "done").glob("*"):
        if f.name not in names:
            names.append(f.name)
    for name in names:
        st = "pending"
        elapsed = mine.get(name)
        if (root / "state" / "done" / name).exists():
            st = "done"
        elif (root / "state" / "failed" / name).exists():
            st = "failed"
        if (root / "state" / "running" / name).exists():
            st = "running"
            rec = read_json(root / "state" / "running" / name, {})
            s = _secs(rec.get("start"), iso())
            elapsed = (elapsed or 0) + (s / 60 if s else 0)
        med = median([p[name] for p in prior if name in p])
        fmt = lambda m: "-" if m is None else f"{m:.1f}m"
        lines.append(f"{name:<16} {st:<9} {fmt(elapsed):>8} {fmt(med):>8}")
    return lines


def summary(root):
    root = pathlib.Path(root)
    walls = [w for w in (wall_minutes(p) for p in prior_runs(root) + [root]) if w is not None]
    w = wall_minutes(root)
    fmt = lambda m: "[Unknown]" if m is None else f"{m:.1f} min"
    return [f"wall {fmt(w)} (first node start to last node end, run-log.jsonl)",
            f"p50 {fmt(median(walls))}, p90 {fmt(percentile(walls, 0.9) if len(walls) >= 5 else None)}"
            f" over {len(walls)} run(s)"]


def invalidate(root, name):
    """Remove the sentinels of `name` and every node after it, so a resume re-runs them."""
    root = pathlib.Path(root)
    meta = read_json(root / "run.json", {})
    graph = load_graph(root / "clone", meta.get("stages", STAGES))
    if name not in graph:
        raise GraphError(f"unknown node {name!r}")
    names = {name} | descendants(graph, name)
    removed = []
    for f in list((root / "state" / "done").glob("*")) + list((root / "state" / "failed").glob("*")):
        base = f.name
        if base in names or any(base.startswith(n + "-") and graph[n].get("fanout") for n in names):
            f.unlink()
            removed.append(base)
    return sorted(set(removed))


# ---- command line ---------------------------------------------------------------------------

def runs_dir():
    return pathlib.Path(os.environ.get("INTEL_RUNS_DIR") or pathlib.Path.home() / "competitor-intel-runs")


def main(argv):
    args = argv[1:]
    if not args:
        print(__doc__, file=sys.stderr)
        return 2
    cmd, rest = args[0], args[1:]

    def opt(flag, default=None):
        if flag in rest:
            i = rest.index(flag)
            if i + 1 >= len(rest):
                raise SystemExit(f"run.py: {flag} needs a value")
            value = rest[i + 1]
            del rest[i:i + 2]
            return value
        return default

    def flag(name):
        if name in rest:
            rest.remove(name)
            return True
        return False

    try:
        if cmd == "graph":
            stages = opt("--stages", STAGES)
            graph = load_graph(ROOT, stages)
            roles = {p.stem for p in (ROOT / ".claude" / "agents").glob("*.md")}
            print(format_graph(graph))
            errs = validate(graph, roles)
            for e in errs:
                print("RED " + e)
            return 1 if errs else 0
        if cmd == "run":
            test_root = opt("--test-root")
            if test_root:
                os.environ["INTEL_RUNS_DIR"] = str(pathlib.Path(test_root).resolve())
            slug = opt("--slug")
            stages = opt("--stages", STAGES)
            checkout = pathlib.Path(opt("--checkout", str(ROOT))).resolve()
            branch = opt("--branch", BRANCH)
            dry = flag("--dry-run")
            if len(rest) != 1:
                print("run.py run: one jd-url", file=sys.stderr)
                return 2
            jd = rest[0]
            refused = launch_refusal(jd, bool(test_root))
            if refused:
                print(f"run.py run: {refused}; nothing started", file=sys.stderr)
                return 2
            slug = slug or default_slug(jd)
            if dry:
                graph = load_graph(checkout, stages)
                roles = {p.stem for p in (checkout / ".claude" / "agents").glob("*.md")}
                print(f"run root {runs_dir()}/{slug}-{now().date().isoformat()} (dry run: nothing written)")
                print(f"jd {jd}")
                print(format_graph(graph))
                for e in validate(graph, roles):
                    print("RED " + e)
                return 0
            run = Run.launch(jd, slug, checkout, branch, stages, runs_dir(), bool(test_root))
            return run.go()
        if cmd == "resume" and len(rest) == 1:
            return Run.resume(rest[0]).go()
        if cmd == "invalidate" and len(rest) == 2:
            for name in invalidate(rest[0], rest[1]):
                print(f"invalidated {name}")
            return 0
    except LaunchRefused as exc:
        print(f"run.py: {exc}; nothing started", file=sys.stderr)
        return 2
    except (GraphError, RuntimeError) as exc:
        print(f"run.py: {exc}", file=sys.stderr)
        return 1
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
