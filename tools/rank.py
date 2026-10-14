#!/usr/bin/env python3
"""The thesis spine's code half: triage, the repair diff, the code tests and the rank.

WHY THIS EXISTS. The lock writes 3-4 typed thesis candidates; three fresh screeners grade each one
on the founder-reader card (`quality-bar/founder-card.md`). Everything after that is code, so no
model ranks, kills or forgives (design.md section 2, R1, R1a, R1b, R4; c2 sections 4-6):
  - a card test is RED on a candidate when a majority of the screeners that graded it say no
    (2 of 3; with 2 screeners, both). A null pass is not graded;
  - code adds two tests the model is blind to. NEW(code): red when the candidate has no `use: main`
    row or every main row is known to the founder. LEAD(code): red when the lead row, evidence[0],
    is not a main row or is known: the sentence would open on the founder's own fact;
  - REPAIR BEFORE KILL: a candidate red only on model tests whose quotes sit verbatim in its prose
    gets ONE rewrite of exactly those clauses (`repair` node), then a fresh re-screen. The repair
    diff refuses a rewrite that touches any unquoted clause or any typed field;
  - the RANK sorts eligible candidates by role weight (the summed `reader.json` duty weights a
    majority of screeners confirmed under ROLE), then DECISION strength, then fewer unresolved
    `advice.depends_on`, then HOLDS green. Ties keep the lock's order. HOLDS ranks, never kills.

KNOWN. A claim row is known when the row says so (`known`, set by code at merge), else when its URL
host is one of `reader.json` `known_hosts` (an entry holding `/` matches as a URL prefix), else the
candidate's own `evidence[].known`.

LAYOUT under BRIEF_ROOT (the runner's fan-out writes the screen files; grouping is by each
verdict's `item`, so file names are free):
  reader.json, candidates.json, claims.jsonl (optional), questions.json (optional)
  screens/*.json     round-1 verdicts, three per candidate (references/schemas/verdict.schema.json)
  repairs.json       written by `triage`: {"repairs": [{id, reds: [{test, quotes, why}]}]}
  repairs/<id>.json  a repaired candidate, the same id
  rescreens/*.json   round-2 verdicts on repaired candidates
Writes 05-thesis.json (references/schemas/thesis.schema.json), 05-thesis.md (rendered for the old
readers: `## Locked thesis` and `## Case against`) and checkin.md, beside the brief and, when
$RUN_ROOT is set, a copy at the run root, where decisions.tsv is read from.

USAGE (the runner's spellings, tools/run.py's stage-5 nodes, in brackets)
  rank.py lock-check BRIEF_ROOT        the lock's gate: NEW(code) and LEAD(code) on every candidate
  rank.py triage BRIEF_ROOT            after round 1: writes repairs.json, prints it
  rank.py needs-repair BRIEF_ROOT ID   [--needs-repair] exit 0 when ID gets a repair, and writes
                                       repairs/ID.reds.json, the quoted reds the repair reads; else 1
  rank.py repair-check BRIEF_ROOT ID   [--repair-diff] the repair's gate: only quoted clauses differ
  rank.py rank BRIEF_ROOT [--checkin PATH]          [rank.py BRIEF_ROOT]
  rank.py --selftest                   offline, on the recorded Globex screens

EXIT CODES. 0 green (rank: a candidate locked). 1 red: lock-check found a code red, or
repair-check refused the rewrite. 2 could not run (usage, a missing or unreadable input).
3 rank only: no candidate is eligible (D12). The runner re-runs the lock once at xhigh with this
output, then notifies and stops. A low role weight (< 6) is a check-in flag, never a stop (D1).

PRECONDITION: none. Stdlib only, offline.
"""

import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse

sys.dont_write_bytecode = True

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCREENS = ROOT / "quality-bar/fixtures/globex/screens"
BLOCKING = ("NEW", "TRUE", "DECISION", "ROLE", "STANCE", "SPEAKER", "FEASIBILITY")
CODE_TESTS = ("NEW(code)", "LEAD(code)", "ROLE(code)")
ROLE_FLOOR = 6          # c2 section 6 rule 4: fewer than two duty bullets; a flag, not a stop
# Prose fields a repair may rewrite, as paths into a candidate. Every other field is typed and
# frozen: evidence, ids, depends_on and the rest never change in a repair.
PROSE = (("headline",), ("thesis",), ("implication", "text"), ("advice", "text"),
         ("advice", "fallback"), ("holds", "text"))
# Punctuation and space beside a quoted clause belong to it: deleting ", whose ... ads," must be
# free to drop one comma.
SEAM = re.compile(r"[\s,;:–—]*")
FOLD = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'})


class Unreadable(Exception):
    """An input the script cannot read: exit 2."""


# --- reading --------------------------------------------------------------------------------------
def read_json(path):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Unreadable("%s: %s" % (path, exc))


def read_claims(path):
    """{id: row} from claims.jsonl, or {} when there is no ledger."""
    path = pathlib.Path(path)
    if not path.is_file():
        return {}
    rows = {}
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                row = json.loads(line)
            except ValueError as exc:
                raise Unreadable("%s:%d: %s" % (path, n, exc))
            if isinstance(row, dict) and isinstance(row.get("id"), str):
                rows[row["id"]] = row
    return rows


def read_verdicts(directory):
    """{item: [verdict]} for every *.json under directory, in file-name order."""
    out = {}
    directory = pathlib.Path(directory)
    if not directory.is_dir():
        return out
    for path in sorted(directory.glob("*.json")):
        v = read_json(path)
        if isinstance(v, dict) and isinstance(v.get("item"), str):
            out.setdefault(v["item"], []).append(v)
    return out


def company_name(reader):
    c = reader.get("company")
    return c.get("name", "") if isinstance(c, dict) else (c or "")


def role_title(reader):
    r = reader.get("role")
    return r.get("title", "") if isinstance(r, dict) else (r or "")


# --- known ----------------------------------------------------------------------------------------
def host_known(url, known_hosts):
    if not isinstance(url, str) or not url:
        return None
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    bare = host + parts.path
    for entry in known_hosts or []:
        entry = entry.lower()
        if "/" in entry:
            if bare.startswith(entry):
                return True
        elif host == entry:
            return True
    return False


def known_fn(reader, claims):
    """A function: claim id (and the candidate's own flag) -> known."""
    hosts = reader.get("known_hosts", [])

    def known(cid, fallback=False):
        row = claims.get(cid)
        if row is not None:
            if isinstance(row.get("known"), bool):
                return row["known"]
            by_host = host_known(row.get("url"), hosts)
            if by_host is not None:
                return by_host
        return bool(fallback)
    return known


# --- the code tests -------------------------------------------------------------------------------
def code_reds(cand, known):
    """[(test, detail)] for NEW(code) and LEAD(code) on one thesis candidate."""
    reds = []
    ev = [e for e in cand.get("evidence", []) if isinstance(e, dict)]
    main = [e for e in ev if e.get("use") == "main"]
    if not main:
        reds.append(("NEW(code)", "no evidence row has use: main"))
    elif all(known(e.get("id"), e.get("known")) for e in main):
        reds.append(("NEW(code)", "every main row is the founder's own: %s"
                     % ", ".join(e.get("id", "?") for e in main)))
    if ev:
        lead = ev[0]
        if lead.get("use") != "main":
            reds.append(("LEAD(code)", "the lead row %s is use: %s, not main" % (lead.get("id"), lead.get("use"))))
        elif known(lead.get("id"), lead.get("known")):
            reds.append(("LEAD(code)", "the lead row %s sits on the founder's own hosts" % lead.get("id")))
    return reds


def line_code_reds(spans, known):
    """[(test, detail)] for a page line: NEW(code) when every cited span is known, LEAD(code) when
    the first cited span cites only known rows. `spans` are {t, c} dicts, c a list of ids."""
    cited = [s for s in spans if s.get("c")]
    reds = []
    if cited and all(all(known(c) for c in s["c"]) for s in cited):
        reds.append(("NEW(code)", "every cited span is the founder's own: %s"
                     % ", ".join(sorted({c for s in cited for c in s["c"]}))))
    if cited and all(known(c) for c in cited[0]["c"]):
        reds.append(("LEAD(code)", "the first cited span cites only the founder's own rows: %s"
                     % ", ".join(cited[0]["c"])))
    return reds


# --- majority -------------------------------------------------------------------------------------
def test_red(verdicts, test):
    """(red, n_red, n_graded, red verdicts) for one card test across screeners."""
    graded = [v for v in verdicts if isinstance(v.get(test), dict) and v[test].get("pass") is not None]
    reds = [v for v in graded if v[test]["pass"] is False]
    return 2 * len(reds) > len(graded), len(reds), len(graded), reds


def majority_lines(verdicts):
    """Duty lines a majority of screeners confirmed under ROLE."""
    count = {}
    for v in verdicts:
        for line in set((v.get("ROLE") or {}).get("lines") or []):
            count[line] = count.get(line, 0) + 1
    return sorted((l for l, n in count.items() if 2 * n > len(verdicts)), key=lambda l: int(l[1:]) if l[1:].isdigit() else 0)


def median_low(xs):
    xs = sorted(xs)
    return xs[(len(xs) - 1) // 2] if xs else 0


def unresolved(cand, claims):
    """advice.depends_on items not yet true or granted; a named fallback resolves them all."""
    adv = cand.get("advice") or {}
    if adv.get("fallback"):
        return 0
    n = 0
    for dep in adv.get("depends_on") or []:
        row = claims.get(dep)
        if dep.startswith("K") or row is None or row.get("state") != "verified":
            n += 1
    return n


def score(cand, verdicts, reader, claims, known):
    """Everything rank and triage need about one candidate on one round of verdicts."""
    weights = {d["line"]: d["weight"] for d in reader.get("duties", [])}
    lines = majority_lines(verdicts)
    reds, model_reds = [], []
    for t in BLOCKING:
        red, n, g, rv = test_red(verdicts, t)
        if red:
            reds.append(t)
            model_reds.append({"test": t, "n": n, "of": g,
                               "quotes": [v[t].get("quote", "") for v in rv],
                               "why": [v[t].get("why", "") for v in rv]})
    code = code_reds(cand, known)
    if "ROLE" not in reds and verdicts and not any(weights.get(l) == 3 for l in lines):
        code.append(("ROLE(code)", "no weight-3 duty line confirmed by a majority"))
    reds += [t for t, _ in code]
    holds_red, _, _, _ = test_red(verdicts, "HOLDS")
    strengths = [v["DECISION"]["strength"] for v in verdicts
                 if isinstance(v.get("DECISION"), dict) and isinstance(v["DECISION"].get("strength"), int)]
    if not verdicts:
        reds.append("UNSCREENED")
    return {"id": cand["id"], "eligible": not reds, "reds": reds, "model_reds": model_reds,
            "code_reds": code, "lines": lines, "role_weight": sum(weights.get(l, 0) for l in lines),
            "strength": median_low(strengths), "unresolved": unresolved(cand, claims),
            "holds": not holds_red and any((v.get("HOLDS") or {}).get("pass") for v in verdicts),
            "screeners": len(verdicts)}


def rank_key(s):
    return (-s["role_weight"], -s["strength"], s["unresolved"], not s["holds"])


def order(scores):
    """Eligible scores, best first; sorted() is stable, so ties keep the lock's order."""
    return sorted((s for s in scores if s["eligible"]), key=rank_key)


# --- locating quotes and the repair diff ----------------------------------------------------------
def get_path(obj, path):
    for k in path:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(k)
    return obj


def locate(text, quote):
    """[(start, end)] where the quote (or each part of an elided quote) sits in text, quote marks
    folded. Parts under three words are ignored: too short to name a clause."""
    if not isinstance(text, str) or not quote:
        return []
    hay = text.translate(FOLD)
    out = []
    for part in re.split(r"\s*(?:…|\.\.\.)\s*", quote.translate(FOLD)):
        part = part.strip().strip("\"'").strip()
        part = part.rstrip(".,;:")
        if len(part.split()) < 3:
            continue
        start = hay.find(part)
        while start != -1:
            out.append((start, start + len(part)))
            start = hay.find(part, start + 1)
    return out


def widen(text, spans):
    """Each span grown over the seam punctuation on both sides, then merged."""
    grown = []
    for a, b in sorted(spans):
        while a > 0 and SEAM.fullmatch(text[a - 1]):
            a -= 1
        m = SEAM.match(text, b)
        grown.append((a, m.end()))
    merged = []
    for a, b in grown:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    return merged


def quoted_spans(cand, reds):
    """{prose path: [(start, end)]} for every red quote found verbatim in the candidate's prose."""
    out = {}
    for red in reds:
        for q in red.get("quotes", []):
            for path in PROSE:
                hits = locate(get_path(cand, path), q)
                if hits:
                    out.setdefault(path, []).extend(hits)
    return out


def repairable(cand, s):
    """True when every red is a model test whose red quotes sit in the candidate's prose."""
    if s["eligible"] or s["code_reds"] or not s["model_reds"]:
        return False
    return all(quoted_spans(cand, [r]) for r in s["model_reds"])


def strip_prose(cand):
    c = json.loads(json.dumps(cand))
    for path in PROSE:
        node = c
        for k in path[:-1]:
            node = node.get(k) if isinstance(node, dict) else None
        if isinstance(node, dict) and path[-1] in node:
            node[path[-1]] = "<prose>"
    return c


def repair_diff(old, new, reds):
    """[] when `new` differs from `old` only inside the quoted clauses; else every refusal."""
    refusals = []
    if strip_prose(old) != strip_prose(new):
        keys = sorted(k for k in set(old) | set(new) if strip_prose(old).get(k) != strip_prose(new).get(k))
        refusals.append("a typed field changed: %s (a repair rewrites quoted clauses only)" % ", ".join(keys))
    spans = quoted_spans(old, reds)
    for path in PROSE:
        o, n = get_path(old, path), get_path(new, path)
        if o == n:
            continue
        name = ".".join(path)
        if not isinstance(o, str) or not isinstance(n, str):
            refusals.append("%s: changed from %r to %r, and no red quotes it" % (name, o, n))
            continue
        cuts = widen(o, spans.get(path, []))
        if not cuts:
            refusals.append("%s: no red quotes this field, so it must stay byte for byte" % name)
            continue
        keep, last = [], 0
        for a, b in cuts:
            keep.append(o[last:a])
            last = b
        keep.append(o[last:])
        pattern = "(.*?)".join(re.escape(k) for k in keep)
        if not re.fullmatch(pattern, n, re.S):
            lost = [k.strip() for k in keep if k.strip() and k not in n]
            refusals.append("%s: the rewrite touches an unquoted clause%s" % (
                name, (": " + " | ".join(repr(k) for k in lost)) if lost else ""))
    return refusals


# --- the run root ---------------------------------------------------------------------------------
def read_repair(path, cid):
    """The repaired candidate: the file's object, or its `candidates[]` entry with this id when the
    repair node's schema wraps candidates as candidates.json does."""
    data = read_json(path)
    if isinstance(data, dict) and isinstance(data.get("candidates"), list):
        data = next((c for c in data["candidates"] if isinstance(c, dict) and c.get("id") == cid), None)
    if not isinstance(data, dict):
        raise Unreadable("%s holds no candidate %r" % (path, cid))
    return data


class Root:
    def __init__(self, root):
        self.root = pathlib.Path(root)
        if not (self.root / "candidates.json").is_file():
            raise Unreadable("%s: no candidates.json" % self.root)
        self.reader = read_json(self.root / "reader.json")
        data = read_json(self.root / "candidates.json")
        self.cands = data.get("candidates") if isinstance(data, dict) else None
        if not isinstance(self.cands, list) or not all(isinstance(c, dict) and c.get("id") for c in self.cands):
            raise Unreadable("%s: candidates.json holds no candidates[] with ids" % self.root)
        self.claims = read_claims(self.root / "claims.jsonl")
        self.known = known_fn(self.reader, self.claims)
        self.r1 = read_verdicts(self.root / "screens")
        self.r2 = read_verdicts(self.root / "rescreens")

    def score1(self, cand):
        return score(cand, self.r1.get(cand["id"], []), self.reader, self.claims, self.known)

    def final(self):
        """[(candidate as ranked, score, note)] in the lock's order, repairs applied."""
        out = []
        for cand in self.cands:
            s1 = self.score1(cand)
            path = self.root / "repairs" / (cand["id"] + ".json")
            if s1["eligible"] or not path.is_file():
                note = "" if s1["eligible"] else ("repairable, no repair ran" if repairable(cand, s1) else "killed")
                out.append((cand, s1, note))
                continue
            fixed = read_repair(path, cand["id"])
            refused = repair_diff(cand, fixed, s1["model_reds"]) if repairable(cand, s1) else ["not repairable"]
            if refused:
                s1 = dict(s1, eligible=False, reds=s1["reds"] + ["REPAIR(refused)"])
                out.append((cand, s1, "repair refused: " + "; ".join(refused)))
                continue
            s2 = score(fixed, self.r2.get(cand["id"], []), self.reader, self.claims, self.known)
            out.append((fixed, s2, "repaired; " + ("eligible on re-screen" if s2["eligible"] else "red again on re-screen: killed")))
        return out


# --- rendering ------------------------------------------------------------------------------------
def claim_ids(cand):
    return [e["id"] for e in cand.get("evidence", []) if isinstance(e, dict) and e.get("id")]


def cell(text):
    return str(text).replace("|", "/").replace("\n", " ")


def render_thesis(reader, ranked, results, locked):
    by = {c["id"]: (c, s, n) for c, s, n in results}
    lines = ["# Stage 5: thesis lock", "",
             "Status: %s" % ("DONE" if locked else "BLOCKED: no eligible candidate"), "",
             "Rendered by `tools/rank.py` from `05-thesis.json`. The JSON is the record; this file is "
             "for the readers that still read Markdown.", ""]
    if locked:
        c = by[locked][0]
        adv = c.get("advice") or {}
        lines += ["## Locked thesis", "", c.get("thesis", ""), "",
                  "Headline: " + c.get("headline", ""),
                  "Subject: " + c.get("subject", ""),
                  "Claims: " + ", ".join(claim_ids(c)),
                  "Advice: %s (first instance: %s; depends on: %s; fallback: %s)" % (
                      adv.get("text", ""), adv.get("first_instance") or "none",
                      ", ".join(adv.get("depends_on") or []) or "nothing", adv.get("fallback") or "none"),
                  "Decision: %s %s" % ((c.get("decision") or {}).get("cite", ""), (c.get("decision") or {}).get("text", "")),
                  "", "## Case against", ""]
        lines += ["- [%s] %s%s" % (x.get("tag", ""), x.get("text", ""), " (the advice depends on it)" if x.get("advice_depends") else "")
                  for x in c.get("case_against", [])]
        lines.append("")
    lines += ["## Rank", "", "| rank | id | role weight | decision | unresolved | holds | headline |",
              "|---|---|---|---|---|---|---|"]
    for k, s in enumerate(ranked, 1):
        lines.append("| %d | %s | %d | %d | %d | %s | %s |" % (k, s["id"], s["role_weight"], s["strength"],
                     s["unresolved"], "G" if s["holds"] else "R", cell(by[s["id"]][0].get("headline", ""))))
    lines += ["", "## Not eligible", "", "| id | red | note |", "|---|---|---|"]
    for c, s, note in results:
        if not s["eligible"]:
            lines.append("| %s | %s | %s |" % (c["id"], ", ".join(s["reds"]), cell(note)))
    return "\n".join(lines) + "\n"


def read_decisions(path):
    path = pathlib.Path(path)
    if not path.is_file():
        return []
    rows = path.read_text(encoding="utf-8").splitlines()
    return [r.split("\t") for r in rows[1:] if r.strip()]


def render_checkin(reader, ranked, results, locked, decisions):
    by = {c["id"]: (c, s, n) for c, s, n in results}
    rec = reader.get("recipient") or {}
    name = rec.get("name") or rec.get("title") or "the founder"
    head = ["# Check-in: %s, %s" % (company_name(reader), role_title(reader)), ""]
    head.append("Recipient: %s (%s, confidence %s)." % (rec.get("name") or "unresolved", rec.get("title", ""), rec.get("confidence", "unknown")))
    if rec.get("taste_model", "generic") == "generic" or not rec.get("writing"):
        head.append("taste: generic, read the headline as %s would." % name)
    out = list(head) + [""]
    if not locked:
        out += ["BLOCKED: no candidate is eligible. The run regenerates the lock once at xhigh; a second "
                "block stops the run and waits for you.", ""]
    else:
        c, s, _ = by[locked]
        out += ["The run continues. Veto with `bin/intel veto <run> --rank N` or `--note \"...\"`.", "",
                "## Locked: rank 1", "", "**%s**" % c.get("headline", ""), "", c.get("thesis", ""), "",
                "Advice: " + (c.get("advice") or {}).get("text", ""), ""]
        if s["role_weight"] < ROLE_FLOOR:
            out += ["FLAG: rank 1's role weight is %d, under %d (fewer than two duty bullets). The run "
                    "continues; read it as the low-value-lock risk." % (s["role_weight"], ROLE_FLOOR), ""]
    out += ["## Ranked", "", "| rank | id | role weight | decision | unresolved | holds | headline |",
            "|---|---|---|---|---|---|---|"]
    for k, s in enumerate(ranked, 1):
        out.append("| %d | %s | %d | %d | %d | %s | %s |" % (k, s["id"], s["role_weight"], s["strength"],
                   s["unresolved"], "G" if s["holds"] else "R", cell(by[s["id"]][0].get("headline", ""))))
    out += ["", "## Duty map", "", "| line | weight | duty | confirmed by |", "|---|---|---|---|"]
    for d in reader.get("duties", []):
        who = [s["id"] for _, s, _ in results if d["line"] in s["lines"]]
        out.append("| %s | %s | %s | %s |" % (d["line"], d["weight"], cell(d.get("text", ""))[:90], ", ".join(who) or "-"))
    out += ["", "## Runner-up", ""]
    if len(ranked) > 1:
        c2, s2, _ = by[ranked[1]["id"]]
        s1 = ranked[0]
        out += ["**%s** (%s)" % (c2.get("headline", ""), c2["id"]), "", c2.get("thesis", ""), "",
                "Below rank 1 on: %s." % ", ".join(
                    k for k, a, b in (("role weight", s1["role_weight"], s2["role_weight"]),
                                      ("decision strength", s1["strength"], s2["strength"])) if a > b) or "the lock's order (a tie)"]
    else:
        out.append("None eligible.")
    out += ["", "## Case against rank 1", ""]
    if locked:
        out += ["- [%s] %s" % (x.get("tag", ""), x.get("text", "")) for x in by[locked][0].get("case_against", [])]
    else:
        out.append("No lock.")
    out += ["", "## Not eligible", ""]
    for c, s, note in results:
        if not s["eligible"]:
            quotes = ["%s: \"%s\"" % (r["test"], r["quotes"][0]) for r in s["model_reds"] if r["quotes"]]
            out.append("- %s: %s. %s%s" % (c["id"], ", ".join(s["reds"]), note,
                       (" " + "; ".join(quotes)) if quotes else ""))
    out += ["", "## Decisions", ""]
    out += ["- %s" % " | ".join(r) for r in decisions] or ["None logged."]
    return "\n".join(out) + "\n"


# --- commands -------------------------------------------------------------------------------------
def cmd_lock_check(root):
    r = Root(root)
    reds = [(c["id"], t, d) for c in r.cands for t, d in code_reds(c, r.known)]
    for cid, t, d in reds:
        sys.stderr.write("RED %s %s: %s\n" % (cid, t, d))
    if reds:
        sys.stderr.write("RANK LOCK-CHECK RED (%d)\n" % len(reds))
        return 1
    print("RANK LOCK-CHECK OK (%d candidates)" % len(r.cands))
    return 0


def cmd_triage(root):
    r = Root(root)
    todo = []
    for cand in r.cands:
        s = r.score1(cand)
        if repairable(cand, s):
            todo.append({"id": cand["id"], "reds": [{"test": m["test"], "quotes": m["quotes"], "why": m["why"]}
                                                   for m in s["model_reds"]]})
        print("%s %s%s" % (cand["id"], "eligible" if s["eligible"] else "red: " + ", ".join(s["reds"]),
                           " -> repair" if any(t["id"] == cand["id"] for t in todo) else ""))
    (r.root / "repairs.json").write_text(json.dumps({"repairs": todo}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("RANK TRIAGE: %d to repair" % len(todo))
    return 0


def cmd_needs_repair(root, cid):
    r = Root(root)
    cand = next((c for c in r.cands if c["id"] == cid), None)
    if cand is None:
        raise Unreadable("no candidate %r in candidates.json" % cid)
    s = r.score1(cand)
    if not repairable(cand, s):
        print("RANK NEEDS-REPAIR %s: no (%s)" % (cid, "eligible" if s["eligible"] else "red " + ", ".join(s["reds"])))
        return 1
    reds = [{"test": m["test"], "quotes": m["quotes"], "why": m["why"]} for m in s["model_reds"]]
    (r.root / "repairs").mkdir(exist_ok=True)
    (r.root / "repairs" / (cid + ".reds.json")).write_text(
        json.dumps({"id": cid, "reds": reds}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("RANK NEEDS-REPAIR %s: yes, %s" % (cid, ", ".join(m["test"] for m in reds)))
    return 0


def cmd_repair_check(root, cid):
    r = Root(root)
    cand = next((c for c in r.cands if c["id"] == cid), None)
    if cand is None:
        raise Unreadable("no candidate %r in candidates.json" % cid)
    fixed = read_repair(r.root / "repairs" / (cid + ".json"), cid)
    s = r.score1(cand)
    refused = repair_diff(cand, fixed, s["model_reds"]) if repairable(cand, s) else ["%s is not repairable" % cid]
    for x in refused:
        sys.stderr.write("REFUSED %s: %s\n" % (cid, x))
    if refused:
        return 1
    print("RANK REPAIR-CHECK OK %s" % cid)
    return 0


def cmd_rank(root, checkin=None):
    r = Root(root)
    results = r.final()
    ranked = order([s for _, s, _ in results])
    locked = ranked[0]["id"] if ranked else None
    verdicts = [v for vs in list(r.r1.values()) + list(r.r2.values()) for v in vs]
    thesis = {"candidates": [c for c, _, _ in results], "verdicts": verdicts,
              "rank": [s["id"] for s in ranked], "locked": locked}
    (r.root / "05-thesis.json").write_text(json.dumps(thesis, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (r.root / "05-thesis.md").write_text(render_thesis(r.reader, ranked, results, locked), encoding="utf-8")
    run_root = os.environ.get("RUN_ROOT")
    decisions = read_decisions(pathlib.Path(run_root) / "decisions.tsv") if run_root else []
    text = render_checkin(r.reader, ranked, results, locked, decisions)
    for target in [pathlib.Path(checkin)] if checkin else [r.root / "checkin.md"] + ([pathlib.Path(run_root) / "checkin.md"] if run_root else []):
        target.write_text(text, encoding="utf-8")
    for c, s, note in results:
        line = "%s: %s" % (c["id"], "eligible, role weight %d, decision %d, unresolved %d, holds %s" % (
            s["role_weight"], s["strength"], s["unresolved"], "G" if s["holds"] else "R") if s["eligible"]
            else "red " + ", ".join(s["reds"]))
        print(line + ("; " + note if note else ""))
        for m in s["model_reds"]:
            for q, w in zip(m["quotes"], m["why"]):
                print("    %s red (%d of %d): \"%s\" -- %s" % (m["test"], m["n"], m["of"], q, w))
        for t, d in s["code_reds"]:
            print("    %s: %s" % (t, d))
    if not locked:
        print("RANK: NO ELIGIBLE CANDIDATE (exit 3)")
        return 3
    print("RANK OK: locked %s (%s)" % (locked, ", ".join(s["id"] for s in ranked)))
    return 0


# --- selftest -------------------------------------------------------------------------------------
def candidate_of(item, cid=None):
    """A c2 recorded item as a candidates.json candidate: fixture-only fields dropped."""
    c = {k: v for k, v in item.items() if k not in ("kind", "source", "rows")}
    if cid:
        c["id"] = cid
    return c


def build_root(tmp, ids, rename=None, rescreen=None):
    """A BRIEF_ROOT from the recorded Globex screens: candidates in `ids` order, every recorded run
    as one screener. rename {item: new id}; rescreen {cid: item whose runs are the re-screen}."""
    rename = rename or {}
    root = pathlib.Path(tmp)
    (root / "screens").mkdir(parents=True)
    shutil.copy(SCREENS / "reader.json", root / "reader.json")
    cands, rows = [], {}
    for item in ids:
        it = read_json(SCREENS / "items" / (item + ".json"))
        cid = rename.get(item, item)
        cands.append(candidate_of(it, cid))
        for row in it.get("rows", []):
            rows[row["id"]] = row
        for run in sorted(p for p in (SCREENS / "results").iterdir() if p.is_dir()):
            f = run / (item + ".json")
            if f.is_file():
                v = read_json(f)
                v["item"] = cid
                (root / "screens" / ("%s-%s.json" % (cid, run.name))).write_text(json.dumps(v), encoding="utf-8")
    (root / "candidates.json").write_text(json.dumps({"candidates": cands}), encoding="utf-8")
    (root / "claims.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows.values()), encoding="utf-8")
    for cid, item in (rescreen or {}).items():
        (root / "rescreens").mkdir(exist_ok=True)
        for run in sorted(p for p in (SCREENS / "results").iterdir() if p.is_dir()):
            f = run / (item + ".json")
            if f.is_file():
                v = read_json(f)
                v["item"] = cid
                (root / "rescreens" / ("%s-%s.json" % (cid, run.name))).write_text(json.dumps(v), encoding="utf-8")
    return root


def cli(*args, env=None):
    p = subprocess.run([sys.executable, str(pathlib.Path(__file__).resolve()), *map(str, args)],
                       capture_output=True, text=True, env=dict(os.environ, **(env or {})))
    return p.returncode, p.stdout + p.stderr


def selftest():
    fails, n = [], 0

    def case(name, ok, why=""):
        nonlocal n
        n += 1
        sys.stdout.write("%s %s%s\n" % ("PASS" if ok else "FAIL", name, "" if ok else " -- " + str(why)[:600]))
        if not ok:
            fails.append(name)

    LOCKS = ["L1-tiktok", "L2-A1", "L3-A1alt", "L4-P1", "L5-P2", "L6-P3final", "CTL-spine-b"]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)

        # 1. The locks as recorded: the final angle without its recital outranks the first lock.
        root = build_root(tmp / "locks", LOCKS)
        rc, out = cli("rank", root, env={"RUN_ROOT": ""})
        thesis = read_json(root / "05-thesis.json") if (root / "05-thesis.json").is_file() else {}
        res = {c["id"]: s for c, s, _ in Root(root).final()}
        case("locks: exit 0", rc == 0, out)
        case("locks: CTL-spine-b ranks above L1-tiktok", thesis.get("rank", [])[:2] == ["CTL-spine-b", "L1-tiktok"], thesis.get("rank"))
        case("locks: role weight 13 against 3", (res["CTL-spine-b"]["role_weight"], res["L1-tiktok"]["role_weight"]) == (13, 3),
             (res["CTL-spine-b"]["role_weight"], res["L1-tiktok"]["role_weight"]))
        case("locks: CTL-spine-b locked", thesis.get("locked") == "CTL-spine-b", thesis.get("locked"))
        want_red = {"L2-A1": "TRUE", "L3-A1alt": "STANCE", "L4-P1": "FEASIBILITY", "L5-P2": "FEASIBILITY", "L6-P3final": "SPEAKER"}
        case("locks: each rejected lock red on its c2 test", all(t in res[i]["reds"] for i, t in want_red.items()),
             {i: res[i]["reds"] for i in want_red})
        md = (root / "05-thesis.md").read_text() if (root / "05-thesis.md").is_file() else ""
        case("05-thesis.md carries the old readers' headings", "\n## Locked thesis\n" in md and "\n## Case against\n" in md
             and "C-074" in md.split("## Case against")[0], md[:300])
        ck = (root / "checkin.md").read_text() if (root / "checkin.md").is_file() else ""
        case("checkin.md: ranked table, duty map, runner-up, case against, taste flag, decisions",
             all(h in ck for h in ("## Ranked", "## Duty map", "## Runner-up", "## Case against rank 1",
                                   "taste: generic", "## Decisions")) and "L1-tiktok" in ck.split("## Runner-up")[1], ck[:400])
        case("checkin.md: no role-weight flag at 13", "FLAG" not in ck)

        # 2. T1-T5, the stage-5 candidates of 2026-10-11: nothing eligible, exit 3 (D12).
        root = build_root(tmp / "t", ["T1", "T2", "T3", "T4", "T5"])
        rc, out = cli("rank", root, env={"RUN_ROOT": ""})
        thesis = read_json(root / "05-thesis.json") if (root / "05-thesis.json").is_file() else {}
        case("T1-T5: exit 3", rc == 3, out)
        case("T1-T5: locked null, rank empty", thesis.get("locked") is None and thesis.get("rank") == [], thesis)
        case("T1-T5: output names each red with its quote", "T5: red" in out and "NEW(code)" in out and 'STANCE red' in out, out[:500])
        case("T1-T5: checkin says blocked", "BLOCKED" in (root / "checkin.md").read_text())

        # 3. Repair before kill: the accepted spine is red on one recital clause; one rewrite of
        #    exactly that clause (spine-b's text) re-screens clean and ranks first.
        root = build_root(tmp / "rep", ["L1-tiktok", "CTL-spine"])
        rc, out = cli("triage", root)
        todo = read_json(root / "repairs.json").get("repairs", []) if (root / "repairs.json").is_file() else []
        case("triage: CTL-spine to repair, on SPEAKER", [t["id"] for t in todo] == ["CTL-spine"]
             and [r["test"] for r in todo[0]["reds"]] == ["SPEAKER"], (rc, out, todo))
        rc, out = cli("--needs-repair", root, "CTL-spine")
        reds = read_json(root / "repairs" / "CTL-spine.reds.json") if (root / "repairs/CTL-spine.reds.json").is_file() else {}
        case("--needs-repair: exit 0 for CTL-spine, its quoted red written for the repair",
             rc == 0 and "whose assets were tested as ads" in json.dumps(reds), (rc, out, reds))
        rc, out = cli("--needs-repair", root, "L1-tiktok")
        case("--needs-repair: exit 1 for the eligible TikTok One", rc == 1, out)
        shutil.rmtree(root / "repairs")
        rc, out = cli("rank", root, env={"RUN_ROOT": ""})
        case("without the repair, TikTok One locks", rc == 0 and read_json(root / "05-thesis.json")["locked"] == "L1-tiktok", out)
        (root / "repairs").mkdir()
        spine = read_json(root / "candidates.json")["candidates"][1]
        fixed = candidate_of(read_json(SCREENS / "items" / "CTL-spine-b.json"), "CTL-spine")
        (root / "repairs" / "CTL-spine.json").write_text(json.dumps(fixed), encoding="utf-8")
        rc, out = cli("--repair-diff", root, "CTL-spine")
        case("repair-check: deleting the quoted clause passes", rc == 0, out)
        (root / "repairs" / "CTL-spine.json").write_text(json.dumps({"candidates": [read_json(root / "candidates.json")["candidates"][0], fixed]}), encoding="utf-8")
        rc, out = cli("--repair-diff", root, "CTL-spine")
        case("repair-check: a repair wrapped in candidates[] is read by its id", rc == 0, out)
        root2 = build_root(tmp / "rep2", ["L1-tiktok", "CTL-spine"], rescreen={"CTL-spine": "CTL-spine-b"})
        (root2 / "repairs").mkdir()
        (root2 / "repairs" / "CTL-spine.json").write_text(json.dumps(fixed), encoding="utf-8")
        (tmp / "runroot").mkdir()
        (tmp / "runroot" / "decisions.tsv").write_text("id\tnode\tquestion\tchosen\treason\nD-1\tlock\tseed Q7\tcovered\tc2\n")
        rc, out = cli(root2, env={"RUN_ROOT": str(tmp / "runroot")})
        thesis = read_json(root2 / "05-thesis.json")
        case("rank.py BRIEF_ROOT: checkin.md beside the brief and at RUN_ROOT, with its decisions",
             (root2 / "checkin.md").is_file() and "seed Q7" in (tmp / "runroot" / "checkin.md").read_text(), out)
        case("repaired and re-screened, the spine locks over TikTok One", rc == 0 and thesis["rank"] == ["CTL-spine", "L1-tiktok"]
             and "starting with Miniclip, and make it" in thesis["candidates"][1]["advice"]["text"], (out, thesis["rank"]))

        # 4. The repair diff refuses a rewrite that touches an unquoted clause, or a typed field.
        bad = json.loads(json.dumps(fixed))
        bad["advice"]["text"] = bad["advice"]["text"].replace("design-partner clients", "every client")
        (root / "repairs" / "CTL-spine.json").write_text(json.dumps(bad), encoding="utf-8")
        rc, out = cli("repair-check", root, "CTL-spine")
        case("repair-check: an unquoted clause rewritten is refused", rc == 1 and "unquoted clause" in out
             and "advice.text" in out, out)
        bad = json.loads(json.dumps(fixed))
        bad["thesis"] = bad["thesis"].replace("starting with Miniclip", "starting with Universal")
        reds = Root(root).score1(spine)["model_reds"]
        case("repair-check: a field no red quotes must stay byte for byte", repair_diff(spine, bad, reds)
             and "thesis" in repair_diff(spine, bad, reds)[0], repair_diff(spine, bad, reds))
        bad = json.loads(json.dumps(fixed))
        bad["advice"]["depends_on"] = ["C-037"]
        case("repair-check: a typed field changed is refused", any("typed field" in x for x in repair_diff(spine, bad, reds)),
             repair_diff(spine, bad, reds))
        rc, out = cli("rank", root, env={"RUN_ROOT": ""})
        case("a refused repair leaves the candidate ineligible", read_json(root / "05-thesis.json")["locked"] == "L1-tiktok"
             and "REPAIR(refused)" in out, out)

        # 5. The lock's gate: NEW(code) and LEAD(code).
        root = build_root(tmp / "lc", ["T5", "CTL-spine-b"])
        rc, out = cli("lock-check", root)
        case("lock-check: T5 red on NEW(code) and LEAD(code), spine-b clean", rc == 1 and "T5 NEW(code)" in out
             and "T5 LEAD(code)" in out and "CTL-spine-b" not in out, out)
        root = build_root(tmp / "lc2", ["CTL-spine-b"])
        data = read_json(root / "candidates.json")
        ev = data["candidates"][0]["evidence"]
        data["candidates"][0]["evidence"] = [e for e in ev if e["id"] == "C-256"] + [e for e in ev if e["id"] != "C-256"]
        (root / "candidates.json").write_text(json.dumps(data), encoding="utf-8")
        rc, out = cli("lock-check", root)
        case("lock-check: a lead row on the founder's own hosts reds LEAD(code) alone", rc == 1 and "LEAD(code)" in out
             and "NEW(code)" not in out, out)

        # 6. The role-weight floor flags and never stops (D1, design section 10 Q4).
        root = build_root(tmp / "floor", ["T1", "L1-tiktok"])
        rc, out = cli("rank", root, env={"RUN_ROOT": ""})
        case("role weight 3 locks with a FLAG, exit 0", rc == 0 and "FLAG: rank 1's role weight is 3" in (root / "checkin.md").read_text(), out)

        # 7. Line code tests, the half line-screen shares: JP, SE1-SE5 and LB red, CTL-V6 green.
        reader = read_json(SCREENS / "reader.json")
        got = {}
        for item in ("F-JOB", "F-SE1", "F-SE2", "F-SE3", "F-SE4", "F-SE5", "F-BEHIND", "CTL-V6", "F-V1", "F-NE"):
            it = read_json(SCREENS / "items" / (item + ".json"))
            claims = {r["id"]: r for r in it.get("rows", [])}
            got[item] = [t for t, _ in line_code_reds(it["spans"], known_fn(reader, claims))]
        case("line code: the six recitals and LB red, CTL-V6 and the verdict lines green",
             all(got[i] for i in ("F-JOB", "F-SE1", "F-SE2", "F-SE3", "F-SE4", "F-SE5", "F-BEHIND"))
             and not got["CTL-V6"] and not got["F-V1"] and not got["F-NE"], got)
        case("known by host: a path entry matches as a prefix",
             host_known("https://find-and-update.company-information.service.gov.uk/company/14125409/officers", reader["known_hosts"])
             and not host_known("https://billo.app/", reader["known_hosts"]))

        # 8. Exit 2 on an unreadable root.
        rc, out = cli("rank", tmp / "absent")
        case("a root with no candidates.json exits 2", rc == 2, out)

    if fails:
        sys.stdout.write("RANK SELFTEST RED (%d of %d cases failed)\n" % (len(fails), n))
        return 1
    sys.stdout.write("RANK SELFTEST OK (%d cases)\n" % n)
    return 0


USAGE = ("usage: rank.py lock-check BRIEF_ROOT | triage BRIEF_ROOT | needs-repair BRIEF_ROOT ID"
         " | repair-check BRIEF_ROOT ID | rank BRIEF_ROOT [--checkin PATH] | --selftest\n")


def main(argv):
    args = argv[1:]
    try:
        if args == ["--selftest"]:
            return selftest()
        if len(args) == 2 and args[0] == "lock-check":
            return cmd_lock_check(args[1])
        if len(args) == 2 and args[0] == "triage":
            return cmd_triage(args[1])
        if len(args) == 3 and args[0] in ("needs-repair", "--needs-repair"):
            return cmd_needs_repair(args[1], args[2])
        if len(args) == 3 and args[0] in ("repair-check", "--repair-diff"):
            return cmd_repair_check(args[1], args[2])
        if len(args) == 2 and args[0] == "rank":
            return cmd_rank(args[1])
        if len(args) == 1 and not args[0].startswith("-"):
            return cmd_rank(args[0])
        if len(args) == 4 and args[0] == "rank" and args[2] == "--checkin":
            return cmd_rank(args[1], args[3])
    except Unreadable as exc:
        sys.stderr.write("rank.py: cannot read: %s\n" % exc)
        return 2
    sys.stderr.write(USAGE)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
