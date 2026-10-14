#!/usr/bin/env python3
"""Stage 5's screen inputs: one self-contained screening page per thesis candidate.

WHY THIS EXISTS. A screener runs at `--max-turns 3` with Read as its only tool. Handed file paths it
spends its turns reading `reader.json`, `questions.json`, the card and a 250-row `claims.jsonl`
(S4's finding on S5a's wiring). Design section 3 prefers typed nodes' inputs inlined, so this code
writes each candidate's whole input once and `tools/run.py` pastes the file into the screener's
prompt (the node's `inline:` key). The page holds, as `tools/line-screen.py` does for lines and c2's
`run_one.sh` did for theses:
  # CARD     quality-bar/founder-card.md, verbatim
  # READER   reader.json
  # CHANGES  each question's id, text and `changes` rule (the only decisions DECISION may cite)
  # ROWS     every claim row the candidate cites, with `known` set by code (tools/rank.py's rule)
  # ITEM     the candidate, `kind: thesis`

USAGE
  screen-input.py screen BRIEF_ROOT     before round 1: clears the last round's screens/,
                                        repairs/, rescreens/, screen-in/, rescreen-in/ and
                                        repairs.json (a regenerated lock starts clean), then writes
                                        screen-in/<id>.md for every candidate in candidates.json
  screen-input.py rescreen BRIEF_ROOT   after the repairs: rescreen-in/<id>.md for each repaired
                                        candidate whose rewrite passes rank.py's repair diff
  screen-input.py verdict-check FILE ID the screen gate: the verdict's `item` is ID, the key rank.py
                                        groups verdicts by

EXIT CODES. 0 written, or the verdict names its item. 1 verdict-check: another item. 2 could not
run: usage, or an input missing or unreadable.

PRECONDITION: none. Stdlib only, offline.
"""
import importlib.util
import json
import pathlib
import shutil
import sys

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parent.parent
CARD = ROOT / "quality-bar" / "founder-card.md"
ROW_KEYS = ("id", "subject", "claim", "quote", "url", "state", "qualifier", "known")
ROUND = ("screens", "repairs", "rescreens", "screen-in", "rescreen-in")


def load_rank():
    spec = importlib.util.spec_from_file_location("rank", ROOT / "tools" / "rank.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fence(value):
    return "```json\n" + json.dumps(value, indent=1, ensure_ascii=False) + "\n```\n"


def cited(cand):
    """Claim ids in the order the candidate uses them: evidence, inference, advice, holds."""
    ids = [e.get("id") for e in cand.get("evidence", []) if isinstance(e, dict)]
    for inf in cand.get("inference", []) or []:
        ids += (inf.get("from") or []) if isinstance(inf, dict) else []
    ids += (cand.get("advice") or {}).get("depends_on") or []
    ids += ((cand.get("holds") or {}).get("from") or []) if isinstance(cand.get("holds"), dict) else []
    out = []
    for i in ids:
        if isinstance(i, str) and i.startswith("C-") and i not in out:
            out.append(i)
    return out


def page(r, cand, questions):
    rows = [dict({k: r.claims[c][k] for k in ROW_KEYS if k in r.claims[c]}, known=r.known(c))
            for c in cited(cand) if c in r.claims]
    changes = [{k: q.get(k) for k in ("id", "text", "changes")} for q in questions.get("questions", [])
               if isinstance(q, dict)]
    item = dict(cand, kind="thesis")
    return "\n".join(["# CARD\n\n" + CARD.read_text(encoding="utf-8"), "# READER\n\n" + fence(r.reader),
                      "# CHANGES\n\n" + fence(changes), "# ROWS\n\n" + fence(rows), "# ITEM\n\n" + fence(item)])


def questions_of(root):
    path = root / "questions.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def cmd_screen(root, rank):
    for name in ROUND:
        shutil.rmtree(root / name, ignore_errors=True)
    (root / "repairs.json").unlink(missing_ok=True)
    r = rank.Root(root)
    out = root / "screen-in"
    out.mkdir()
    qs = questions_of(root)
    for cand in r.cands:
        (out / (cand["id"] + ".md")).write_text(page(r, cand, qs), encoding="utf-8")
    print("SCREEN-INPUT %d candidate(s): %s" % (len(r.cands), ", ".join(c["id"] for c in r.cands)))
    return 0


def cmd_rescreen(root, rank):
    for name in ("rescreens", "rescreen-in"):
        shutil.rmtree(root / name, ignore_errors=True)
    r = rank.Root(root)
    qs, done = questions_of(root), []
    for cand in r.cands:
        path = root / "repairs" / (cand["id"] + ".json")
        if not path.is_file():
            continue
        s = r.score1(cand)
        fixed = rank.read_repair(path, cand["id"])
        if not rank.repairable(cand, s) or rank.repair_diff(cand, fixed, s["model_reds"]):
            print("SCREEN-INPUT %s: its repair is refused, so it is not re-screened" % cand["id"])
            continue
        (root / "rescreen-in").mkdir(exist_ok=True)
        (root / "rescreen-in" / (cand["id"] + ".md")).write_text(page(r, fixed, qs), encoding="utf-8")
        done.append(cand["id"])
    print("SCREEN-INPUT re-screen %d candidate(s): %s" % (len(done), ", ".join(done) or "none"))
    return 0


def cmd_verdict_check(path, cid):
    verdict = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    item = verdict.get("item") if isinstance(verdict, dict) else None
    if item != cid:
        sys.stderr.write("VERDICT RED %s: `item` is %r; set it to the candidate's id, %r\n" % (path, item, cid))
        return 1
    print("VERDICT OK %s names %s" % (path, cid))
    return 0


def main(argv):
    args = argv[1:]
    try:
        if len(args) == 2 and args[0] in ("screen", "rescreen"):
            rank = load_rank()
            root = pathlib.Path(args[1])
            try:
                return (cmd_screen if args[0] == "screen" else cmd_rescreen)(root, rank)
            except rank.Unreadable as exc:
                sys.stderr.write("screen-input: cannot read: %s\n" % exc)
                return 2
        if len(args) == 3 and args[0] == "verdict-check":
            return cmd_verdict_check(args[1], args[2])
    except (OSError, ValueError) as exc:
        sys.stderr.write("screen-input: %s: %s\n" % (type(exc).__name__, exc))
        return 2
    sys.stderr.write(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
