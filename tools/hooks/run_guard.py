#!/usr/bin/env python3
"""PreToolUse run guard (design.md section 3, Hook).

Active only while `$CLAUDE_PROJECT_DIR/.run-active` exists or `RUN_ID` is set. The runner writes
`.run-active` into the run's clone and sets `RUN_ID` only in node environments, so a build session
in a checkout is never blocked: with neither present this script exits 0 before reading anything.

While active it denies, with exit 2 and the reason on stderr (exit 2 blocks under
`--dangerously-skip-permissions`, a section Q4):
  - git commit, push, reset, checkout or stash;
  - any Bash that runs `claude`;
  - Write, Edit, MultiEdit or NotebookEdit outside BRIEF_ROOT;
  - Bash naming ryanhennebry.xyz, in-the-loop/, deploy.sh, verify.sh or wrangler;
  - WebFetch to ryanhennebry.xyz;
  - Bash naming ~/.claude (writes there are what this guards; a Bash write cannot be parsed);
  - TaskOutput.

Any error inside this script exits 0 when inactive and 2 when active: a broken guard in a run
fails closed, and a broken guard in a build session never blocks.

    python3 tools/hooks/run_guard.py < payload.json
"""
import json
import os
import re
import sys

SITE_TERMS = ("ryanhennebry.xyz", "in-the-loop/", "deploy.sh", "verify.sh", "wrangler")
GIT_WRITE = re.compile(r"\bgit\b[^|;&\n]*\b(commit|push|reset|checkout|stash)\b")
CLAUDE_CMD = re.compile(r"(^|[;&|(`\s/'\"])claude(\s|$|[;&|)`'\"])")
WRITE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")


def active():
    if os.environ.get("RUN_ID"):
        return True
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    return bool(project) and os.path.exists(os.path.join(project, ".run-active"))


def home_claude_patterns():
    home = os.path.realpath(os.path.expanduser("~"))
    return ("~/.claude", "$HOME/.claude", "${HOME}/.claude", home + "/.claude")


def verdict(payload):
    """The deny reason for one payload, or None to allow."""
    tool = payload.get("tool_name") or ""
    ti = payload.get("tool_input") or {}
    if tool == "TaskOutput":
        return "run guard: TaskOutput is denied; the runner owns every barrier"
    if tool == "Bash":
        cmd = str(ti.get("command", ""))
        if GIT_WRITE.search(cmd):
            return "run guard: git commit, push, reset, checkout and stash are denied during a run"
        if CLAUDE_CMD.search(cmd):
            return "run guard: nested claude sessions are denied during a run"
        for term in SITE_TERMS:
            if term in cmd:
                return f"run guard: the site repo and deploy are the runner's alone ({term})"
        for pat in home_claude_patterns():
            if pat in cmd:
                return "run guard: ~/.claude is outside the run"
        return None
    if tool == "WebFetch":
        url = str(ti.get("url", ""))
        if re.search(r"^[a-z]+://([^/]*\.)?ryanhennebry\.xyz(?=[:/?#]|$)", url, re.I):
            return "run guard: fetching ryanhennebry.xyz is the runner's publish probe alone"
        return None
    if tool in WRITE_TOOLS:
        raw = str(ti.get("file_path") or ti.get("notebook_path") or "")
        base = payload.get("cwd") or os.getcwd()
        path = os.path.realpath(os.path.join(base, os.path.expanduser(raw)))
        brief = os.environ.get("BRIEF_ROOT")
        if not brief:
            return "run guard: BRIEF_ROOT is unset, so no write has a place to land"
        brief = os.path.realpath(brief)
        if path != brief and not path.startswith(brief + os.sep):
            return f"run guard: writes are confined to BRIEF_ROOT ({brief}); refused {path}"
        return None
    return None


def main():
    try:
        if not active():
            return 0
    except Exception:
        return 0
    try:
        payload = json.load(sys.stdin)
        reason = verdict(payload)
    except Exception as exc:  # fail closed inside a run
        reason = f"run guard: unreadable payload ({exc.__class__.__name__})"
    if reason:
        print(reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
