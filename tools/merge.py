#!/usr/bin/env python3
"""Merge the extractors' claim shards into the run's ledger, in code (Globex design § 3, `merge` node).

WHY THIS EXISTS. Stage 4's lead merged seven extractors' rows by hand: it concatenated
`parts/<slug>.jsonl`, respelt a rival's name the ledger carried two ways, and kept `sources.tsv` in
step, at about 146k tokens resident a call. Each of those is byte work a script does the same way
every time, so the lead's merge becomes this node and the agents only write shards.

WHAT ONE RUN DOES, in $BRIEF_ROOT (read-only except the two outputs):
  1. Reads `claims.jsonl` (the reader's rows, and any earlier merge) and every `parts/*.jsonl` in
     name order. A shard row replaces the ledger row of its ID, so a second merge after a shard
     changes rewrites that shard's rows and nothing else. An ID in two shards, or a shard line that
     is not one JSON object with an `id`, is a finding and nothing is written.
  2. Respells names (claims-check L17): each owner spelling, from `names.json`, `reader.json`
     `company.name` and `snapshots/*.json` `name`, replaces any spelling of the same name key in a
     row's name fields (L17's NAME_FIELDS; never `quote`, the page's own words) that differs from
     it by more than first letters. "INFLUENCER" becomes "Influencer"; "influencer", a common noun
     differing only by its first letter, stays.
  3. Sets `known` on every row by claims-check's `row_known` (c1 § 3 host rule): the URL's host is
     `reader.json` `company.domain` or a subdomain of it, or one of its `known_hosts` exactly.
  4. Writes `claims.jsonl`, rows ordered by ID number, and `sources.tsv`: every row it already
     holds keeps its label, and each distinct row URL without one gets `<subject> <last path
     segment>` (`home` for a bare host), cut to LABEL_MAX characters at a word.
The ledger's own rules stay `claims-check.py --ledger`'s; the runner's gate runs it after this.

  python3 tools/merge.py BRIEF_ROOT        merge; prints MERGE OK and the counts
  python3 tools/merge.py --selftest         offline, on the Globex shards in quality-bar/fixtures/
  python3 tools/merge.py --check [STORE]    the Globex run store, with claims-check --pages (local)

EXIT CODES. 0 merged. 1 findings, nothing written. 2 bad usage or an unreadable input (no
`reader.json`, no `parts/`).
"""

import contextlib
import importlib.util
import io
import json
import pathlib
import re
import shutil
import sys
import tempfile
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
LABEL_MAX = 31  # brief-check L1's label cap
ID_NUM = re.compile(r"^C-(\d{3,})$")
FIXTURE = ROOT / "quality-bar/fixtures/globex/run"
GOOD = ROOT / "tools/fixtures/schema/good/globex"
STORE = pathlib.Path.home() / "competitor-intel-runs/globex-2026-10-11"


def _claims_check():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("claims_check", ROOT / "tools/claims-check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CC = _claims_check()


class Unreadable(Exception):
    pass


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Unreadable("%s cannot be read (%s)" % (path, exc)) from exc


def read_rows(path, findings):
    """The objects of one JSONL file, each with an `id`; a bad line is a finding."""
    out = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError as exc:
            findings.append("%s:%d: not JSON (%s)" % (path.name, n, exc))
            continue
        if not isinstance(obj, dict) or not isinstance(obj.get("id"), str) or not ID_NUM.match(obj["id"]):
            findings.append("%s:%d: a row needs an `id` of the form C-NNN" % (path.name, n))
            continue
        out.append(obj)
    return out


def owners(root, reader):
    """Every owner spelling the run holds: names.json, reader.json and the snapshots."""
    names = [reader.get("company", {}).get("name")]
    if (root / "names.json").is_file():
        names += [e.get("name") for e in read_json(root / "names.json") if isinstance(e, dict)]
    for snap in sorted((root / "snapshots").glob("*.json")) if (root / "snapshots").is_dir() else []:
        data = read_json(snap)
        names.append(data.get("name") if isinstance(data, dict) else None)
    return sorted({n for n in names if isinstance(n, str) and n.strip()})


def respell(rows, names):
    """Rows with each name field's off-spellings of an owner name replaced by the owner's; and
    {(variant, owner): count of rows}."""
    pats = []
    for name in names:
        key = CC.name_key(name)
        body = r"[\s-]?".join(re.escape(ch) for ch in key)
        pats.append((name, re.compile(r"(?<!\w)%s(?!\w)" % body, re.I)))
    seen, out = {}, []
    for row in rows:
        new = dict(row)
        for field in CC.NAME_FIELDS:
            text = new.get(field)
            if not isinstance(text, str):
                continue
            for name, pat in pats:
                def fix(m, name=name):
                    got = m.group(0)
                    if got == name or CC.initial_case_only(got, name):
                        return got
                    seen.setdefault((got, name), set()).add(row["id"])
                    return name
                text = pat.sub(fix, text)
            new[field] = text
        out.append(new)
    return out, {k: len(v) for k, v in seen.items()}


def unify(rows):
    """Rows with every L17 clash no owner name settled respelt to one spelling: the capitalised
    spelling most rows carry, ties to the earliest row. Parallel extractors spell a non-owner name
    independently ("NGINX", "Nginx"), so merge, not a person, makes them one; L17 cannot red the
    ledger merge writes."""
    pats, seen = [], {}
    for _, spellings in sorted(CC.name_spellings([(None, r) for r in rows]).items()):
        names = sorted(spellings)
        if not CC.spelling_clash(names):
            continue
        caps = [n for n in names if any(c.isupper() for c in n)]
        first = {n: min(num(i) for i in spellings[n]) for n in caps}
        canon = min(caps, key=lambda n: (-len(spellings[n]), first[n]))
        for n in names:
            if n != canon and not CC.initial_case_only(n, canon):
                pats.append((n, canon, re.compile(r"(?<!\w)%s(?!\w)" % re.escape(n))))
    out = []
    for row in rows:
        new = dict(row)
        for field in CC.NAME_FIELDS:
            text = new.get(field)
            if not isinstance(text, str):
                continue
            for n, canon, pat in pats:
                if pat.search(text):
                    seen.setdefault((n, canon), set()).add(row["id"])
                    text = pat.sub(canon, text)
            new[field] = text
        out.append(new)
    return out, {k: len(v) for k, v in seen.items()}


def reconcile(root, rows, index):
    """Rows whose url redirected, rewritten to the page's final_url; then every row url still in no
    snapshot, but a page the run fetched, appended to the snapshot named by the row's subject.
    Returns (rows, {snapshot: [urls added]}). web.py reds a brief citing a url no snapshot holds,
    and build is code with no repair, so the join is settled here, before anything is authored
    (vandelay run 2: C-602 cited https://trygravity.ai/, its snapshot https://www.trygravity.com/)."""
    final = {e["url"]: e["final_url"] for e in index
             if e.get("final_url", "").startswith("http") and e["final_url"] != e.get("url")}
    fetched = {e.get("url") for e in index} | {e.get("final_url") for e in index}
    snaps = {}
    for p in sorted((root / "snapshots").glob("*.json")) if (root / "snapshots").is_dir() else []:
        try:
            snaps[p] = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    text = lambda: "".join(json.dumps(d, ensure_ascii=False) for d in snaps.values())
    held = text()
    out = []
    for row in rows:
        url = row.get("url")
        if isinstance(url, str) and url not in held and final.get(url, "\0") in held:
            row = dict(row, url=final[url])
        out.append(row)
    by_name = {str(d.get("name", "")).casefold(): p for p, d in snaps.items() if isinstance(d, dict)}
    added = {}
    for row in out:
        url, subject = row.get("url"), str(row.get("subject", "")).casefold()
        p = by_name.get(subject)
        if not isinstance(url, str) or url in held or url not in fetched or p is None:
            continue
        d = snaps[p]
        host = (urllib.parse.urlsplit(url).hostname or "").removeprefix("www.")
        own = host == str(d.get("domain", "")).removeprefix("www.")
        d.setdefault("sources", []).append({"url": url, "type": "primary" if own else "data",
                                            "date": str(d.get("captured") or "")[:10] or None})
        added.setdefault(p.name, []).append(url)
        held = text()
    for p, d in snaps.items():
        if p.name in added:
            p.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return out, added


def default_label(row):
    url = urllib.parse.urlparse(row["url"])
    segs = [s for s in url.path.split("/") if s]
    seg = re.sub(r"[-_]+", " ", urllib.parse.unquote(segs[-1])) if segs else "home"
    seg = re.sub(r"\.(html?|php|aspx?)$", "", seg, flags=re.I)
    label = ("%s %s" % (row.get("subject") or url.hostname or "", seg)).strip()
    if len(label) > LABEL_MAX:
        label = label[:LABEL_MAX + 1].rsplit(" ", 1)[0] if " " in label[:LABEL_MAX + 1] else label[:LABEL_MAX]
    return label.strip() or (url.hostname or "source")[:LABEL_MAX]


def read_sources(path):
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "url\tlabel":
        raise Unreadable("%s does not open with the header url<TAB>label" % path)
    return [tuple(ln.split("\t", 1)) for ln in lines[1:] if ln.strip() and "\t" in ln]


def merge(root, out=sys.stdout):
    """Returns the exit code."""
    root = pathlib.Path(root)
    findings = []
    try:
        reader = read_json(root / "reader.json")
        if not (root / "parts").is_dir():
            raise Unreadable("%s has no parts/ directory of shards" % root)
        ledger = read_rows(root / "claims.jsonl", findings) if (root / "claims.jsonl").is_file() else []
        sources = read_sources(root / "sources.tsv")
        names = owners(root, reader)
    except (Unreadable, OSError) as exc:
        sys.stderr.write("MERGE: %s\n" % exc)
        return 2
    shard_rows, owner = [], {}
    for part in sorted((root / "parts").glob("*.jsonl")):
        for row in read_rows(part, findings):
            if row["id"] in owner:
                findings.append("%s is in both %s and %s" % (row["id"], owner[row["id"]], part.name))
                continue
            owner[row["id"]] = part.name
            shard_rows.append(row)
    if findings:
        for f in findings:
            sys.stderr.write("FAIL: %s\n" % f)
        sys.stderr.write("MERGE RED (%d finding%s; nothing written)\n" % (len(findings), "" if len(findings) == 1 else "s"))
        return 1
    rows = [r for r in ledger if r["id"] not in owner] + shard_rows
    rows.sort(key=lambda r: int(ID_NUM.match(r["id"]).group(1)))
    rows, respelt = respell(rows, names)
    rows, unified = unify(rows)
    respelt.update(unified)
    rows, added = reconcile(root, rows, CC.read_index(root / "pages") if (root / "pages").is_dir() else [])
    for snap, urls in sorted(added.items()):
        out.write("SNAPSHOT %s gains %d fetched source%s its rows cite\n" % (snap, len(urls), "" if len(urls) == 1 else "s"))
    company = reader.get("company", {})
    for row in rows:
        row["known"] = CC.row_known(row.get("url"), company.get("domain"), reader.get("known_hosts", []))
    (root / "claims.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                                       encoding="utf-8")
    labelled = dict(sources)
    added = []
    for row in rows:
        url = row.get("url")
        if isinstance(url, str) and url.strip() and url not in labelled:
            labelled[url] = default_label(row)
            added.append(url)
    (root / "sources.tsv").write_text("url\tlabel\n" + "".join("%s\t%s\n" % kv for kv in labelled.items()),
                                      encoding="utf-8")
    for (got, name), n in sorted(respelt.items()):
        out.write("RESPELT %r -> %r in %d row%s\n" % (got, name, n, "" if n == 1 else "s"))
    out.write("MERGE OK (%d rows: %d from %d shards; %d known; sources.tsv %d rows, %d new)\n"
              % (len(rows), len(shard_rows), len(list((root / "parts").glob("*.jsonl"))),
                 sum(r["known"] for r in rows), len(labelled), len(added)))
    return 0


# --- selftest and the store check ------------------------------------------------------------------
# The Globex shards (`parts/`, the extractors' first pass, copied from the run store) and its ledger:
# the reader rows C-001..C-036 seed the root, and the merge must give back the ledger's rows
# C-037..C-255 byte for byte, the 31 rows the run respelt by hand included (f-dataflow § 6).
LO, HI = 37, 255


def num(cid):
    return int(ID_NUM.match(cid).group(1))


def seed(root, store, reader):
    (root / "parts").mkdir(parents=True)
    for part in sorted((store / "parts").glob("*.jsonl")):
        shutil.copy(part, root / "parts" / part.name)
    base = [ln for ln in (store / "claims.jsonl").read_text(encoding="utf-8").splitlines()
            if ln.strip() and num(json.loads(ln)["id"]) < LO]
    (root / "claims.jsonl").write_text("\n".join(base) + "\n", encoding="utf-8")
    shutil.copy(reader, root / "reader.json")
    if (GOOD / "names.json").is_file():
        shutil.copy(GOOD / "names.json", root / "names.json")


def reproduces(root, store):
    """(ok, detail): the merged rows C-037..C-255 equal the store ledger's, `known` set aside."""
    want = {r["id"]: r for r in map(json.loads, (store / "claims.jsonl").read_text(encoding="utf-8").splitlines())
            if LO <= num(r["id"]) <= HI}
    got = {r["id"]: {k: v for k, v in r.items() if k != "known"}
           for r in map(json.loads, (root / "claims.jsonl").read_text(encoding="utf-8").splitlines())
           if LO <= num(r["id"]) <= HI}
    bad = sorted(i for i in set(want) | set(got) if want.get(i) != got.get(i))
    return not bad and len(want) == 204, "%d of %d rows differ: %s" % (len(bad), len(want), bad[:6])


def selftest():
    fails, n = [], 0

    def verdict(label, ok, got=""):
        nonlocal n
        n += 1
        if ok:
            print("SELFTEST OK   %s" % label)
        else:
            fails.append("%s: got %s" % (label, got))

    def run(root):
        err, out = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err):
            code = merge(root, out=out)
        return code, out.getvalue() + err.getvalue()

    two = [{"id": "C-201", "claim": "It runs on NGINX and NGINX Plus"},
           {"id": "C-301", "claim": "or on Nginx"}, {"id": "C-302", "claim": "Its signup form"},
           {"id": "C-303", "claim": "Its sign-up page"}]
    got, said = unify(two)
    verdict("unify respells a non-owner clash to the majority capitalised spelling, leaving common words",
            got[1]["claim"] == "or on NGINX" and said == {("Nginx", "NGINX"): 1}
            and got[2]["claim"] == "Its signup form" and got[3]["claim"] == "Its sign-up page", (got, said))
    with tempfile.TemporaryDirectory(prefix="merge-reconcile-") as tmp:
        root = pathlib.Path(tmp)
        (root / "snapshots").mkdir()
        (root / "snapshots" / "g.ai.json").write_text(json.dumps(
            {"domain": "g.ai", "name": "Gee", "captured": "2026-10-13",
             "sources": [{"url": "https://www.g.com/", "type": "primary", "date": "2026-10-13"}]}))
        index = [{"url": "https://g.ai/", "final_url": "https://www.g.com/"},
                 {"url": "https://register.example/g", "final_url": "https://register.example/g"}]
        rows = [{"id": "C-200", "subject": "Gee", "url": "https://g.ai/"},
                {"id": "C-201", "subject": "Gee", "url": "https://register.example/g"},
                {"id": "C-202", "subject": "Gee", "url": "https://never.fetched/x"}]
        got, added = reconcile(root, rows, index)
        snap = (root / "snapshots" / "g.ai.json").read_text()
        verdict("reconcile: a redirected row takes its final_url; a fetched third-party url joins its "
                "subject's snapshot; an unfetched one is left for claims-check to red",
                [r["url"] for r in got] == ["https://www.g.com/", "https://register.example/g",
                                            "https://never.fetched/x"]
                and added == {"g.ai.json": ["https://register.example/g"]}
                and "never.fetched" not in snap and '"type": "data"' in snap, (got, added, snap))
    with tempfile.TemporaryDirectory(prefix="merge-selftest-") as tmp:
        root = pathlib.Path(tmp) / "run"
        seed(root, FIXTURE, FIXTURE / "reader.json")
        code, said = run(root)
        ok, detail = reproduces(root, FIXTURE)
        verdict("the Globex shards reproduce C-037..C-255 byte for byte", code == 0 and ok, (code, said, detail))
        verdict("the respell is INFLUENCER -> Influencer, 31 rows",
                "RESPELT 'INFLUENCER' -> 'Influencer' in 31 rows" in said and said.count("RESPELT") == 1, said)
        good = {r["id"]: r["known"] for r in map(json.loads, (GOOD / "claims.jsonl").read_text().splitlines())}
        rows = [json.loads(ln) for ln in (root / "claims.jsonl").read_text().splitlines()]
        verdict("`known` on every row equals the backfill's (claims-check row_known)",
                len(rows) == 240 and all(r["known"] == good[r["id"]] for r in rows),
                [r["id"] for r in rows if r.get("known") != good.get(r["id"])][:6])
        with contextlib.redirect_stderr(io.StringIO()):
            found = CC.check_ledger(root / "claims.jsonl", require_client_rows=True)
        verdict("the merged ledger passes claims-check --ledger --require-client-rows", not found, found[:3])
        src = (root / "sources.tsv").read_text(encoding="utf-8").splitlines()
        urls = [ln.split("\t")[0] for ln in src[1:]]
        cited = {r["url"] for r in rows if r.get("url")}
        verdict("sources.tsv: the header, each cited URL once, labels 1-31 characters",
                src[0] == "url\tlabel" and sorted(urls) == sorted(cited)
                and all(0 < len(ln.split("\t")[1].strip()) <= LABEL_MAX for ln in src[1:]),
                (src[:3], len(urls), len(cited)))
        before = (root / "claims.jsonl").read_bytes(), (root / "sources.tsv").read_bytes()
        code, said = run(root)
        verdict("a second merge changes nothing", code == 0 and before == ((root / "claims.jsonl").read_bytes(),
                                                                           (root / "sources.tsv").read_bytes()), said)
        kept = pathlib.Path(tmp) / "kept"
        seed(kept, FIXTURE, FIXTURE / "reader.json")
        first = sorted(cited)[0]
        (kept / "sources.tsv").write_text("url\tlabel\n%s\tA label kept\n" % first, encoding="utf-8")
        code, said = run(kept)
        verdict("a label sources.tsv already holds is kept",
                code == 0 and "%s\tA label kept" % first in (kept / "sources.tsv").read_text(), said)
        dup = pathlib.Path(tmp) / "dup"
        seed(dup, FIXTURE, FIXTURE / "reader.json")
        line = (dup / "parts/billo.jsonl").read_text().splitlines()[0]
        (dup / "parts/zz-extra.jsonl").write_text(line + "\n", encoding="utf-8")
        held = (dup / "claims.jsonl").read_bytes()
        code, said = run(dup)
        verdict("an ID in two shards reds, nothing written",
                code == 1 and "in both billo.jsonl and zz-extra.jsonl" in said and (dup / "claims.jsonl").read_bytes() == held, said)
        (dup / "parts/zz-extra.jsonl").write_text("{not json\n", encoding="utf-8")
        code, said = run(dup)
        verdict("a shard line that is not JSON reds", code == 1 and "zz-extra.jsonl:1: not JSON" in said, said)
        (dup / "parts/zz-extra.jsonl").unlink()
        (dup / "reader.json").unlink()
        code, said = run(dup)
        verdict("no reader.json is exit 2", code == 2 and "reader.json" in said, said)
    if fails:
        for f in fails:
            print("SELFTEST FAIL: %s" % f)
        print("SELFTEST RED (%d of %d)" % (len(fails), n))
        return 1
    print("SELFTEST OK (%d cases)" % n)
    return 0


def check(store):
    """The store's own shards, merged, against its ledger, then claims-check with the page store."""
    store = pathlib.Path(store)
    with tempfile.TemporaryDirectory(prefix="merge-check-") as tmp:
        root = pathlib.Path(tmp) / "run"
        seed(root, store, GOOD / "reader.json")
        code = merge(root)
        ok, detail = reproduces(root, store)
        print("%s reproduces C-037..C-255 of %s: %s" % ("OK  " if ok else "FAIL", store, detail))
        rc = CC.main(["claims-check.py", "--ledger", str(root / "claims.jsonl"), "--require-client-rows",
                      "--pages", str(store / "pages"), "--captures", str(store / "captures")])
    return 0 if code == 0 and ok and rc == 0 else 1


def main(argv):
    args = argv[1:]
    if args == ["--selftest"]:
        return selftest()
    if args[:1] == ["--check"] and len(args) <= 2:
        return check(args[1] if len(args) == 2 else STORE)
    if len(args) != 1 or args[0].startswith("-"):
        sys.stderr.write("usage: merge.py BRIEF_ROOT | merge.py --selftest | merge.py --check [STORE]\n")
        return 2
    return merge(args[0])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
