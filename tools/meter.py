#!/usr/bin/env python3
"""tools/meter.py, the one meter (design.md R8: M55 run roots, M60 the session). Stdlib only.

    python3 tools/meter.py <run root> [--until N]
    python3 tools/meter.py --session <transcript.jsonl> [--cutoff ISO] [--runs-dir D] [--root R ...]

`bin/intel cost` prints the same report. Exit 1 when an agent row has no log, a flat attempt's
stream differs from its `modelUsage` by more than 1%, or a nested attempt's stream exceeds it;
exit 2 on usage.

**Per attempt** (one `logs/<node>-<n>.jsonl` per agent row, the CLI's stream-json):

  stream    every `assistant` event deduplicated by `message.id` across every
            `parent_tool_use_id` (nested agents count), keeping per id the usage with the largest
            `output_tokens`. Streamed `output_tokens` is the first chunk's, so the stream cannot
            meter output.
  counted   the `result` event's `modelUsage`, summed over models (it includes nested agents),
            else, for a killed attempt with no result, the stream. `usage_true` on a run-log row
            is this count, written by the runner at attempt end; where a row carries it, it is
            what the root sums.
  dollars   the CLI's `costUSD` from `modelUsage`; a no-result attempt is re-priced from its
            stream by PRICE, flagged [INFERRED].
  output    a no-result attempt prints `output_est` = thinking `estimated_tokens_delta` + emitted
            text and tool input characters / 3.5, flagged [INFERRED] (median 0.82 of true output
            over 93 result attempts, res-R1R8 § 2.1).
  check     on attempts with a result: a flat one (no nested message) red past 1% on
            cache-read; a nested one red only when its stream exceeds `modelUsage` (ruling 4: the
            stream is a lower bound there, up to 5.7% short on run 2's shape-3).

**The session** (`--session`, A2-11): the transcript and its `<id>/subagents/agent-*.jsonl`
started before the cutoff, each deduplicated by `message.id` as above. Output comes from the
transcript's `cost-state` record only (transcripts hold final usage for few calls), and the
`cost-state` gap (its cache-read less every transcript's, cutoff or not) prints as its own line.
Run roots under the runs directory (a child with `run.json` or `run-log.jsonl`, or one level down
under a parent with neither, as s7b's A/B roots) whose `run.json` `started_at`, else first row,
falls inside the session (start to cutoff), and any `--root`, are metered as above and added.
"""
import datetime
import json
import os
import pathlib
import re
import sys

TOL = 0.01
# USD per million tokens. Fitted to run 2's recorded costUSD (x1.087, median attempt error 6%);
# prices only no-result attempts, always flagged [INFERRED] (res-R1R8 § 2.1 item 3).
PRICE = {"input": 5.0, "cache_read": 0.50, "cache_write_5m": 6.25, "cache_write_1h": 6.25, "output": 25.0}
CHARS_PER_TOKEN = 3.5
CACHE_READ_BAR = 72_900_000   # the secondary line (ruling 1); the bar is costUSD
COST_BAR = 40.0               # notional costUSD per published run (ruling 1)
KEYS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
MU = {"inputTokens": "input_tokens", "cacheCreationInputTokens": "cache_creation_input_tokens",
      "cacheReadInputTokens": "cache_read_input_tokens", "outputTokens": "output_tokens"}


class UsageError(Exception):
    pass


def _events(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if isinstance(e, dict):
                yield e


def _zero():
    return {k: 0 for k in KEYS}


def _add(total, usage):
    for k in KEYS:
        total[k] += (usage or {}).get(k) or 0


def _dedup(records, get):
    """{message id: usage} keeping, per id, the usage with the largest output_tokens."""
    msgs = {}
    for r in records:
        m = get(r)
        if not m:
            continue
        mid, u = m.get("id"), m.get("usage") or {}
        if not mid:
            continue
        prev = msgs.get(mid)
        if prev is None or (u.get("output_tokens") or 0) > (prev[0].get("output_tokens") or 0):
            msgs[mid] = (u, r)
    return msgs


def read_stream(path):
    """(stream summary, result event or None) for one attempt's log."""
    msgs, result, thinking, chars = {}, None, 0, 0
    evs = []
    for e in _events(path):
        t = e.get("type")
        if t == "assistant":
            evs.append(e)
            for c in (e.get("message") or {}).get("content") or []:
                if c.get("type") == "text":
                    chars += len(c.get("text") or "")
                elif c.get("type") == "tool_use":
                    chars += len(json.dumps(c.get("input"), ensure_ascii=False))
        elif t == "result":
            result = e
        elif t == "system" and e.get("subtype") == "thinking_tokens":
            thinking += e.get("estimated_tokens_delta") or 0
    msgs = _dedup(evs, lambda e: e.get("message"))
    usage, cw5, cw1h, nested = _zero(), 0, 0, 0
    for u, e in msgs.values():
        _add(usage, u)
        cc = u.get("cache_creation") or {}
        cw5 += cc.get("ephemeral_5m_input_tokens") or 0
        cw1h += cc.get("ephemeral_1h_input_tokens") or 0
        nested += bool(e.get("parent_tool_use_id"))
    # The CLI streams one assistant event per content block, so each block's characters count
    # once; thinking text is not streamed, its token deltas are.
    return {"usage": usage, "cw5": cw5, "cw1h": cw1h, "messages": len(msgs), "nested_messages": nested,
            "output_est": round(thinking + chars / CHARS_PER_TOKEN)}, result


def from_result(res):
    """(usage, costUSD) from a result event: modelUsage summed over models, else its usage."""
    mu = res.get("modelUsage") or {}
    usage, cost = _zero(), 0.0
    if mu:
        for m in mu.values():
            for src, dst in MU.items():
                usage[dst] += m.get(src) or 0
            cost += m.get("costUSD") or 0.0
    else:
        _add(usage, res.get("usage"))
        cost = res.get("total_cost_usd") or 0.0
    return usage, cost


def price(stream):
    u = stream["usage"]
    other_write = max(0, u["cache_creation_input_tokens"] - stream["cw5"] - stream["cw1h"])
    return (u["input_tokens"] * PRICE["input"] + u["cache_read_input_tokens"] * PRICE["cache_read"]
            + (stream["cw5"] + other_write) * PRICE["cache_write_5m"] + stream["cw1h"] * PRICE["cache_write_1h"]
            + u["output_tokens"] * PRICE["output"]) / 1e6


def attempt(path):
    """One attempt's count: source, usage, dollars, the stream check and its problem, if any."""
    s, res = read_stream(path)
    out = {"result": res is not None, "nested": s["nested_messages"] > 0, "messages": s["messages"],
           "stream_cache_read": s["usage"]["cache_read_input_tokens"], "output_est": None, "problem": None}
    if res is None:
        out.update(source="stream", usage=s["usage"], cost_usd=price(s), cost_inferred=True,
                   output_est=s["output_est"])
        return out
    usage, cost = from_result(res)
    out.update(source="modelUsage", usage=usage, cost_usd=cost, cost_inferred=False)
    got, want = out["stream_cache_read"], usage["cache_read_input_tokens"]
    if out["nested"]:
        if got > want:
            out["problem"] = f"nested stream cache-read {got:,} exceeds modelUsage {want:,}"
    elif want == 0:
        if got:
            out["problem"] = f"flat stream cache-read {got:,} against modelUsage 0"
    elif abs(got - want) / want > TOL:
        out["problem"] = (f"flat stream cache-read {got:,} differs from modelUsage {want:,} by "
                          f"{abs(got - want) / want:.1%}, over 1%")
    return out


def row_fields(path):
    """What the runner writes on an agent row at attempt end (M55)."""
    a = attempt(path)
    usage = dict(a["usage"])
    if a["output_est"] is not None:
        usage["output_est"] = a["output_est"]
    return {"usage_true": usage, "cost_usd_true": a["cost_usd"], "cost_inferred": a["cost_inferred"]}


# ---- a run root --------------------------------------------------------------------------------

def rows(root):
    path = pathlib.Path(root) / "run-log.jsonl"
    out = []
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r, dict):
                out.append(r)
    return out


def meter(root, until=None):
    root = pathlib.Path(root)
    every = rows(root)
    rs = every[:until] if until is not None else every
    tot = {"usage": _zero(), "cost_usd": 0.0, "cost_inferred": 0.0, "output_est": 0}
    reported = {"usage": _zero(), "cost_usd": 0.0}
    m = {"root": root, "rows": len(rs), "rows_all": len(every), "processes": 0, "results": 0, "messages": 0,
         "flat_checked": 0, "nested_checked": 0, "noresult": [], "problems": [], "attempts": {}}
    for r in rs:
        _add(reported["usage"], r.get("usage"))
        reported["cost_usd"] += r.get("total_cost_usd") or 0.0
        if r.get("kind") != "agent":
            continue
        tag = f"{r.get('node')}-{r.get('attempt')}"
        log = root / "logs" / f"{tag}.jsonl"
        if not log.exists():
            m["problems"].append(f"{tag}: agent row with no log ({log})")
            continue
        a = attempt(log)
        m["attempts"][tag] = a
        m["processes"] += 1
        m["results"] += a["result"]
        m["messages"] += a["messages"]
        if a["result"]:
            m["nested_checked" if a["nested"] else "flat_checked"] += 1
        if a["problem"]:
            m["problems"].append(f"{tag}: {a['problem']}")
        usage, dollars, inferred = a["usage"], a["cost_usd"], a["cost_inferred"]
        if isinstance(r.get("usage_true"), dict):
            usage = {k: r["usage_true"].get(k) or 0 for k in KEYS}
            if r.get("cost_usd_true") is not None:
                dollars = r["cost_usd_true"]
        _add(tot["usage"], usage)
        if inferred:
            tot["cost_inferred"] += dollars
            tot["output_est"] += a["output_est"] or 0
            m["noresult"].append((tag, usage["cache_read_input_tokens"], a["output_est"] or 0, dollars, a["nested"]))
        else:
            tot["cost_usd"] += dollars
    m["total"], m["reported"] = tot, reported
    return m


def cost(root, until=None):
    """The run-root totals, the shape `tools/run.py`'s cost() returns, plus the meter's lines."""
    m = meter(root, until)
    u = m["total"]["usage"]
    return {"cache_read": u["cache_read_input_tokens"], "cache_creation": u["cache_creation_input_tokens"],
            "input": u["input_tokens"], "output": u["output_tokens"], "output_est": m["total"]["output_est"],
            "cost_usd": m["total"]["cost_usd"], "cost_usd_inferred": m["total"]["cost_inferred"],
            "processes": m["processes"], "results": m["results"], "messages": m["messages"],
            "problems": m["problems"]}


def _m(n):
    return f"{n / 1e6:.2f}M"


def report(root, until=None):
    """(lines, exit code) for one run root."""
    m = meter(root, until)
    t, rep = m["total"], m["reported"]
    u = t["usage"]
    cr = u["cache_read_input_tokens"]
    lines = [f"run {m['root']}", f"rows {m['rows']} of {m['rows_all']}",
             f"processes {m['processes']}, results {m['results']}, messages {m['messages']}",
             f"cache_read {cr:,} ({_m(cr)}) secondary, {cr / CACHE_READ_BAR:.1%} of {CACHE_READ_BAR:,}; "
             f"run-log usage reported {rep['usage']['cache_read_input_tokens']:,}",
             f"cache_write {u['cache_creation_input_tokens']:,}  input {u['input_tokens']:,}  "
             f"output {u['output_tokens']:,}" + (f" + output_est {t['output_est']:,} [INFERRED]" if m["noresult"] else ""),
             f"costUSD ${t['cost_usd']:.2f} + ${t['cost_inferred']:.2f} [INFERRED] = "
             f"${t['cost_usd'] + t['cost_inferred']:.2f} notional, bar <= ${COST_BAR:.0f} per published run"]
    lines.append(f"no-result attempts {len(m['noresult'])}, counted from the stream and priced by card [INFERRED]:")
    for tag, c, est, dollars, nested in m["noresult"]:
        ge = ">= " if nested else ""
        lines.append(f"  {tag} cache_read {ge}{c:,} output_est {est:,} [INFERRED] ${dollars:.2f} [INFERRED]")
    lines.append(f"check: {m['flat_checked']} flat attempt(s) against modelUsage within 1%; "
                 f"{m['nested_checked']} nested, the stream a lower bound")
    for p in m["problems"]:
        lines.append(f"RED {p}")
    return lines, 1 if m["problems"] else 0


# ---- the session -------------------------------------------------------------------------------

def _ts(s):
    if not s:
        return None
    try:
        d = datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        raise UsageError(f"not an ISO timestamp: {s!r}")
    return d if d.tzinfo else d.replace(tzinfo=datetime.timezone.utc)


def transcript(path):
    """One transcript: first and last timestamp, deduplicated usage, the per-record sum, cost-state."""
    records, first, last, cost_state, per_record = [], None, None, None, 0
    for r in _events(path):
        t = r.get("type")
        if r.get("timestamp"):
            first = first or r["timestamp"]
            last = r["timestamp"]
        if t == "assistant":
            records.append(r)
            per_record += ((r.get("message") or {}).get("usage") or {}).get("cache_read_input_tokens") or 0
        elif t == "cost-state":
            cost_state = r
    usage = _zero()
    msgs = _dedup(records, lambda r: r.get("message"))
    for u, _ in msgs.values():
        _add(usage, u)
    return {"path": pathlib.Path(path), "start": _ts(first), "end": _ts(last), "usage": usage,
            "calls": len(msgs), "records_cache_read": per_record, "cost_state": cost_state}


def _runs_dir(runs_dir):
    if runs_dir:
        return pathlib.Path(runs_dir).expanduser()
    return pathlib.Path(os.environ.get("INTEL_RUNS_DIR") or "~/competitor-intel-runs").expanduser()


def _candidate_roots(base):
    """Run roots under the runs directory: each child with a run.json or a run-log.jsonl, and,
    for a child that has neither (an A/B parent such as s7b), each of its children that has one."""
    out = []
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        if (d / "run.json").exists() or (d / "run-log.jsonl").exists():
            out.append(d)
        else:
            out += sorted(c for c in d.iterdir() if c.is_dir() and (c / "run-log.jsonl").exists())
    return out


def _name(root, base):
    try:
        return str(root.relative_to(base))
    except ValueError:
        return str(root)


def _started(root):
    """run.json `started_at`, else the first run-log row's start, else None."""
    try:
        return _ts(json.loads((root / "run.json").read_text()).get("started_at"))
    except (OSError, ValueError, UsageError):
        pass
    for r in rows(root):
        try:
            return _ts(r.get("start"))
        except UsageError:
            return None
    return None


def session(path, cutoff=None, runs_dir=None, roots=()):
    path = pathlib.Path(path).expanduser()
    if not path.is_file():
        raise UsageError(f"no transcript at {path}")
    main = transcript(path)
    cut = _ts(cutoff) if cutoff else None
    subs, late = [], []
    sub_dir = path.with_suffix("") / "subagents"
    for p in sorted(sub_dir.glob("agent-*.jsonl")) if sub_dir.is_dir() else []:
        s = transcript(p)
        meta = p.with_name(p.name[:-len(".jsonl")] + ".meta.json")
        try:
            s["meta"] = json.loads(meta.read_text()) if meta.exists() else {}
        except ValueError:
            s["meta"] = {}
        (late if cut and s["start"] and s["start"] >= cut else subs).append(s)
    subs.sort(key=lambda s: s["start"] or main["start"])
    cs = main["cost_state"] or {}
    cs_usage, cs_cost = _zero(), cs.get("totalCostUSD")
    for m in (cs.get("modelUsage") or {}).values():
        for src, dst in MU.items():
            cs_usage[dst] += m.get(src) or 0
    every_cr = sum(s["usage"]["cache_read_input_tokens"] for s in [main] + subs + late)
    in_cr = main["usage"]["cache_read_input_tokens"] + sum(s["usage"]["cache_read_input_tokens"] for s in subs)
    gap = max(0, cs_usage["cache_read_input_tokens"] - every_cr) if cs else 0
    window_end = cut or main["end"]
    found = []
    base = _runs_dir(runs_dir)
    if base.is_dir() and main["start"]:
        for d in _candidate_roots(base):
            started = _started(d)
            if started and main["start"] <= started and (window_end is None or started <= window_end):
                found.append(d)
    for r in roots:
        r = pathlib.Path(r).expanduser()
        if r not in found:
            found.append(r)
    runs = []
    for d in found:
        if not (d / "run-log.jsonl").exists():
            runs.append({"name": _name(d, base), "root": d, "cache_read": 0, "cost_usd": 0.0, "metered": False,
                         "problems": []})
            continue
        c = cost(d)
        runs.append({"name": _name(d, base), "root": d, "cache_read": c["cache_read"],
                     "cost_usd": c["cost_usd"] + c["cost_usd_inferred"], "metered": True, "problems": c["problems"]})
    runs_cr = sum(r["cache_read"] for r in runs)
    return {"main": main, "subagents": subs, "late": late, "cost_state": cs, "cost_state_usage": cs_usage,
            "cost_state_usd": cs_cost,
            "subagents_cache_read": sum(s["usage"]["cache_read_input_tokens"] for s in subs),
            "subagents_records_cache_read": sum(s["records_cache_read"] for s in subs),
            "transcripts_cache_read": in_cr, "gap_cache_read": gap, "runs": runs,
            "total_cache_read": in_cr + gap + runs_cr,
            "problems": [f"{r['name']}: {p}" for r in runs for p in r["problems"]]}


def session_report(path, cutoff=None, runs_dir=None, roots=()):
    """(lines, exit code) for one session transcript."""
    s = session(path, cutoff, runs_dir, roots)
    main = s["main"]
    lines = [f"session {pathlib.Path(path).name}" + (f", subagents started before {cutoff}" if cutoff else "")]

    def row(label, u):
        cr = u["cache_read_input_tokens"]
        return f"{label} {cr:,} ({_m(cr)}) cache_read, {u['cache_creation_input_tokens']:,} cache_write"

    lines.append(row("MAIN", main["usage"]) + f", {main['calls']} calls")
    sub = _zero()
    for x in s["subagents"]:
        _add(sub, x["usage"])
    lines.append(f"subagents {len(s['subagents'])} in scope {s['subagents_cache_read']:,} "
                 f"({_m(s['subagents_cache_read'])}); {len(s['late'])} started after the cutoff")
    for x in s["subagents"]:
        meta = x["meta"]
        lines.append(f"  {x['start']:%Y-%m-%dT%H:%M:%SZ} {x['path'].name[len('agent-'):-len('.jsonl')]} "
                     f"{meta.get('agentType', '?')} calls {x['calls']} cache_read {x['usage']['cache_read_input_tokens']:,}"
                     f"  {meta.get('description', '')}")
    for x in s["late"]:
        lines.append(f"  excluded, started {x['start']:%Y-%m-%dT%H:%M:%SZ}: "
                     f"{x['path'].name[len('agent-'):-len('.jsonl')]} {x['meta'].get('description', '')}")
    tc = s["transcripts_cache_read"]
    lines.append(f"transcripts {tc:,} ({_m(tc)}) cache_read deduplicated by message.id; "
                 f"per-record sum {s['subagents_records_cache_read'] / max(1, s['subagents_cache_read']):.2f}x "
                 f"over the subagents")
    if s["cost_state"]:
        cs = s["cost_state_usage"]
        lines.append(f"cost-state gap {s['gap_cache_read']:,} ({_m(s['gap_cache_read'])}) cache_read in "
                     f"cost-state and in no transcript")
        lines.append(f"output {cs['output_tokens']:,} (cost-state); cost-state ${s['cost_state_usd'] or 0:.2f}, "
                     f"cache_read {cs['cache_read_input_tokens']:,}, every transcript included")
    else:
        lines.append("cost-state none: the transcript has no cost-state record; output unmetered, no gap line")
    for r in s["runs"]:
        if r["metered"]:
            lines.append(f"run {r['name']} {r['cache_read']:,} ({_m(r['cache_read'])}) cache_read, "
                         f"${r['cost_usd']:.2f} costUSD")
        else:
            lines.append(f"run {r['name']} unmetered: no run-log.jsonl")
    if not s["runs"]:
        lines.append(f"runs none started inside the session under {_runs_dir(runs_dir)}")
    lines.append(f"in scope {s['total_cache_read']:,} ({_m(s['total_cache_read'])}) cache_read = "
                 f"transcripts + cost-state gap + run roots")
    for p in s["problems"]:
        lines.append(f"RED {p}")
    return lines, 1 if s["problems"] else 0


def _take(args, flag, many=False):
    vals = []
    while flag in args:
        i = args.index(flag)
        if i + 1 >= len(args):
            raise UsageError(f"{flag} needs a value")
        vals.append(args[i + 1])
        del args[i:i + 2]
        if not many:
            break
    return vals if many else (vals[0] if vals else None)


def run_cli(args, default_root=None):
    """(lines, exit) for `meter.py` and `bin/intel cost` argv after the verb."""
    args = list(args)
    sess = _take(args, "--session")
    if sess:
        cutoff, runs_dir, roots = _take(args, "--cutoff"), _take(args, "--runs-dir"), _take(args, "--root", True)
        if args:
            raise UsageError(f"unexpected {' '.join(args)}")
        return session_report(sess, cutoff, runs_dir, roots)
    until = _take(args, "--until")
    if until is not None and not until.isdigit():
        raise UsageError("--until takes a row count")
    if len(args) > 1 or any(a.startswith("-") for a in args):
        raise UsageError(f"unexpected {' '.join(args)}")
    root = args[0] if args else default_root
    if root is None:
        raise UsageError("a run root is required")
    return report(root, int(until) if until is not None else None)


def main(argv):
    try:
        lines, code = run_cli(argv[1:])
    except UsageError as exc:
        print(f"meter: {exc}\n{__doc__.splitlines()[2]}\n{__doc__.splitlines()[3]}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
