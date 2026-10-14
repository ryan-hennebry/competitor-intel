#!/usr/bin/env python3
"""the operator's approvals ledger (design.md M54, ruling 34): the one writer, and the reader every
spending or gated verb uses.

The ledger is `~/.config/competitor-intel/approvals.tsv`, outside every checkout and worktree,
tab-separated, header `n kind value usd at`:

  n  decide  yes|no  <empty>  <at>     the operator's answer to design.md § 9 row #n
  n  spend   <empty> <usd>    <at>     dollars approved under § 9 row #n

`at` is local Europe/London time as `%Y-%m-%dT%H:%M:%S%z`. Rows only append; for a decide the
last row wins, spend rows sum. Agents are denied this file and this tool: builders' sandbox
`denyWrite` on the directory, and tools/hooks/build_guard.py in the chat's and builders' settings.
The TTY check below is a belt, not the enforcer, since `script` can supply a pty.

    python3 tools/approve.py decide <n> yes|no     from the operator's own terminal
    python3 tools/approve.py spend <n> <usd>       from the operator's own terminal
    python3 tools/approve.py show                  print the ledger's standing answers

INTEL_APPROVALS names another ledger path (selftests only; the build guard denies a command
naming it).
"""
import datetime
import os
import pathlib
import sys
from zoneinfo import ZoneInfo

HEADER = ["n", "kind", "value", "usd", "at"]
KINDS = ("decide", "spend")
TZ = "Europe/London"


class LedgerError(Exception):
    """A ledger that is not the M54 layout."""


def ledger_path(path=None):
    if path:
        return pathlib.Path(path)
    return pathlib.Path(os.environ.get("INTEL_APPROVALS")
                        or pathlib.Path.home() / ".config" / "competitor-intel" / "approvals.tsv")


def read(path=None):
    """Every row as {n, kind, value, usd, at}; [] for an absent ledger; LedgerError on a bad one."""
    path = ledger_path(path)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].split("\t") != HEADER:
        raise LedgerError(f"{path}: header is not {' '.join(HEADER)} (tab-separated)")
    rows = []
    for i, line in enumerate(lines[1:], 2):
        if not line.strip():
            continue
        cells = line.split("\t")
        if len(cells) != 5:
            raise LedgerError(f"{path}:{i}: {len(cells)} cells, want 5")
        n, kind, value, usd, at = cells
        if not n.isdigit() or kind not in KINDS:
            raise LedgerError(f"{path}:{i}: bad n or kind: {line!r}")
        if kind == "decide" and (value not in ("yes", "no") or usd):
            raise LedgerError(f"{path}:{i}: a decide row holds yes or no and no usd")
        if kind == "spend":
            try:
                amount = float(usd)
            except ValueError:
                raise LedgerError(f"{path}:{i}: a spend row holds dollars in usd")
            if value:
                raise LedgerError(f"{path}:{i}: a spend row holds an empty value")
        rows.append({"n": int(n), "kind": kind, "value": value,
                     "usd": float(usd) if kind == "spend" else None, "at": at})
    return rows


def decision(n, path=None):
    """'yes', 'no' or None for § 9 row #n; the last decide row wins."""
    last = None
    for row in read(path):
        if row["kind"] == "decide" and row["n"] == int(n):
            last = row["value"]
    return last


def approved(n, path=None):
    return decision(n, path) == "yes"


def spend_total(n, path=None):
    return float(sum(r["usd"] for r in read(path) if r["kind"] == "spend" and r["n"] == int(n)))


def stamp():
    return datetime.datetime.now(ZoneInfo(TZ)).strftime("%Y-%m-%dT%H:%M:%S%z")


def append(row, path=None):
    path = ledger_path(path)
    read(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists() or path.stat().st_size == 0
    with open(path, "a", encoding="utf-8") as f:
        if new:
            f.write("\t".join(HEADER) + "\n")
        f.write("\t".join(row) + "\n")


def main(argv):
    args = argv[1:]
    if args == ["show"]:
        try:
            rows = read()
        except LedgerError as exc:
            print(f"approve: {exc}", file=sys.stderr)
            return 2
        for n in sorted({r["n"] for r in rows}):
            usd = spend_total(n)
            print(f"#{n} {decision(n) or '-'}" + (f" ${usd:g}" if usd else ""))
        return 0
    if len(args) != 3 or args[0] not in KINDS or not args[1].lstrip("#").isdigit():
        print(__doc__, file=sys.stderr)
        return 2
    kind, n, value = args[0], args[1].lstrip("#"), args[2]
    if kind == "decide" and value not in ("yes", "no"):
        print("approve: decide takes yes or no", file=sys.stderr)
        return 2
    if kind == "spend":
        try:
            if float(value) <= 0:
                raise ValueError
        except ValueError:
            print("approve: spend takes a positive dollar amount", file=sys.stderr)
            return 2
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("approve: run this from your own terminal; nothing written", file=sys.stderr)
        return 2
    row = [n, kind, value, "", stamp()] if kind == "decide" else [n, kind, "", value, stamp()]
    try:
        append(row)
    except LedgerError as exc:
        print(f"approve: {exc}; nothing written", file=sys.stderr)
        return 2
    print(f"recorded #{n} {kind} {value} in {ledger_path()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
