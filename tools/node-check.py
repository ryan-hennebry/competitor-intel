#!/usr/bin/env python3
"""The research lane's node gates, in code (Globex design § 3, node table rows reader to merge).

WHY THIS EXISTS. Each node of stages 1-4 is decided by exit codes (design § 2, R2): the runner
writes the sentinel only when the node's gate exits 0. The schemas grade a typed file's shape; this
grades what a schema cannot see, the joins between files: a positioning line to the page it was read
off, a pool row to the fetch that saw it, a picked name to its own site's <title>, a shard row to
its question and its ID block. One check per subcommand, every finding printed, then the exit.

  node-check.py reader    BRIEF_ROOT        every page captures/jd.json lists as a positioning source
                                            (the client's home page, the board's company page,
                                            llms.txt) that fetched has a reader.json positioning line
                                            sourced to a claims row on that URL; every claim ID that
                                            reader.json cites is a row
  node-check.py questions BRIEF_ROOT        02-questions.md's `### Q<n>.` headings are questions.json's
                                            ids, in order; every `serves` id is a reader.json duty
                                            line or positioning id
  node-check.py segments  BRIEF_ROOT        segments.json ids are 1 to 5, each once; no name,
                                            shape, market, why or query is a placeholder
                                            (PLACEHOLDERS, blank); no query repeats in or
                                            across segments
  node-check.py pool      BRIEF_ROOT TSV    the pool TSV carries POOL_COLUMNS and at least one row,
                                            and every row's url is a URL pages/index.tsv fetched
  node-check.py names     BRIEF_ROOT        each names.json row's page_id is a saved page on its own
                                            domain whose <title> carries `name` as one whole segment;
                                            slugs and domains are unique
  node-check.py shard     BRIEF_ROOT PART   PART is `client` or a names.json slug: the shard parses,
                                            every rival row answers a questions.json id, a rival
                                            shard holds exactly one `named`/`not named` row, and the
                                            company's snapshot and comp file exist (snapshot schema)
  node-check.py blocks    BRIEF_ROOT PART   PART is `reader`, `client` or a slug: every row ID sits
                                            in the PART's block (BLOCKS, id-blocks.json)
  node-check.py mkt1-when BRIEF_ROOT        exit 0 when an MKT1 call applies (a question's topic is
                                            `buyer`, or the seat is a growth role and a question is
                                            about answer engines), else 1; prints the calls
  node-check.py mkt1      BRIEF_ROOT        mkt1/ holds at least one non-empty .md
  node-check.py --selftest

ID BLOCKS. Parallel writers cannot collide on a claim ID when each owns a block: the reader
C-001..C-099, the client extractor C-100..C-199, and rival i of names.json (0-based)
C-(200+100i)..C-(299+100i). `tools/prefetch.py rivals` writes them to id-blocks.json, which the
extractors read; this file is the one place the scheme is computed (`blocks()`).

EXIT CODES. 0 green. 1 findings (mkt1-when: no call applies). 2 bad usage or an unreadable input.
Stdlib only, offline.
"""
import html
import importlib.util
import json
import pathlib
import re
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "references" / "schemas"
FIXTURES = ROOT / "tools" / "fixtures" / "node-check"
POOL_COLUMNS = ("name", "url", "http_code", "one_line", "buyer_named_on_own_site", "markets",
                "linkedin_slug")
READER_BLOCK = (1, 99)
CLIENT_BLOCK = (100, 199)
RIVAL_BASE, RIVAL_SIZE = 200, 100
JOIN_STATES = ("named", "not named")
TITLE_SPLIT = re.compile(r"\s+[|\-–—·•:]\s+|:\s+")
GROWTH = re.compile(r"growth|seo|marketing|gtm|demand|content", re.I)
# Stand-in words a segment field may not be (`placeholder()`), case-folded, letters and / only.
PLACEHOLDERS = {"blocked", "tbd", "tba", "todo", "n/a", "na", "none", "null", "nil", "unknown",
                "placeholder", "pending", "unavailable", "missing", "empty", "xxx"}
ANSWER_ENGINE = re.compile(r"answer engine|\baeo\b|ai search|llm search|generative engine", re.I)


class Unreadable(Exception):
    pass


def load_json(path):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Unreadable(f"{path}: {exc}")


def load_rows(path):
    rows = []
    try:
        lines = pathlib.Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise Unreadable(f"{path}: {exc}")
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            raise Unreadable(f"{path}:{n} is not one JSON object")
        if not isinstance(row, dict):
            raise Unreadable(f"{path}:{n} is not one JSON object")
        rows.append(row)
    return rows


def id_num(cid):
    m = re.fullmatch(r"C-([0-9]{3,})", str(cid or ""))
    return int(m.group(1)) if m else None


def fmt(n):
    return "C-%03d" % n


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")


def blocks(names):
    """{part: (first, last)} for the reader, the client and each names.json slug, in order."""
    out = {"reader": READER_BLOCK, "client": CLIENT_BLOCK}
    for i, row in enumerate(names):
        first = RIVAL_BASE + RIVAL_SIZE * i
        out[row["slug"]] = (first, first + RIVAL_SIZE - 1)
    return out


def index_urls(brief):
    path = brief / "pages" / "index.tsv"
    if not path.is_file():
        return set()
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        return set()
    head = lines[0].split("\t")
    out = set()
    for line in lines[1:]:
        row = dict(zip(head, line.split("\t")))
        for k in ("url", "final_url"):
            if row.get(k):
                out.add(row[k])
    return out


def norm_url(u):
    return str(u or "").strip().rstrip("/")


def schema_check(schema, path):
    spec = importlib.util.spec_from_file_location("intel_schema", ROOT / "tools" / "schema.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.check(str(schema), str(path))


# ---- the checks: each returns a list of findings ----------------------------------------------

def check_reader(brief):
    jd = load_json(brief / "captures" / "jd.json")
    reader = load_json(brief / "reader.json")
    rows = {r.get("id"): r for r in load_rows(brief / "claims.jsonl")}
    out = []
    cited = []
    for p in reader.get("positioning") or []:
        cited += [(f"positioning {p.get('id')}", c) for c in p.get("source") or []]
    rec = reader.get("recipient") or {}
    for key in ("source", "conflict", "writing"):
        cited += [(f"recipient.{key}", c) for c in rec.get(key) or []]
    for where, cid in cited:
        if cid not in rows:
            out.append(f"READER {where} cites {cid}, which is not a claims.jsonl row")
    sourced = {}
    for p in reader.get("positioning") or []:
        for cid in p.get("source") or []:
            if cid in rows:
                sourced.setdefault(norm_url(rows[cid].get("url")), []).append(p.get("id"))
    for page in jd.get("positioning_pages") or []:
        if page.get("state") != "FETCHED":
            continue
        if not sourced.get(norm_url(page.get("url"))):
            out.append(f"READER no positioning line is sourced to the {page.get('kind')} page "
                       f"{page.get('url')}: copy its positioning lines verbatim into claims rows "
                       f"and cite them from reader.json positioning")
    return out


def check_questions(brief):
    q = load_json(brief / "questions.json")
    reader = load_json(brief / "reader.json")
    md = (brief / "02-questions.md").read_text(encoding="utf-8")
    heads = re.findall(r"^### (Q[1-9][0-9]*)\. ", md, re.M)
    ids = [x.get("id") for x in q.get("questions") or []]
    out = []
    if heads != ids:
        out.append(f"QUESTIONS 02-questions.md's headings {heads} are not questions.json's ids {ids}, in order")
    known = {d.get("line") for d in reader.get("duties") or []} | {p.get("id") for p in reader.get("positioning") or []}
    for x in q.get("questions") or []:
        for s in x.get("serves") or []:
            if s not in known:
                out.append(f"QUESTIONS {x.get('id')} serves {s}, which is no reader.json duty line or positioning id")
    return out


def placeholder(value):
    """A field that names no search space: blank, punctuation only, or a stand-in word, alone or
    leading a colon (`BLOCKED: job ad unreachable`). Non-Latin text is never a placeholder."""
    text = str(value or "").strip()
    head = re.sub(r"[^a-z/]", "", re.split(r"\s*[:(]", text, maxsplit=1)[0].lower())
    return not re.search(r"\w", text) or head in PLACEHOLDERS


def check_segments(brief):
    seg = load_json(brief / "segments.json")
    segs = seg.get("segments") or []
    ids = sorted(str(s.get("id")) for s in segs)
    out = [] if ids == ["1", "2", "3", "4", "5"] else [f"SEGMENTS ids are {ids}, want 1 to 5, each once"]
    owner = {}
    for s in segs:
        sid = s.get("id")
        for key in ("name", "shape", "market", "why"):
            if placeholder(s.get(key)):
                out.append(f"SEGMENTS segment {sid} {key} is a placeholder ({s.get(key)!r}): write the "
                           f"search space itself, read off the job ad and the client's pages")
        seen = set()
        for q in s.get("queries") or [""]:
            key = " ".join(str(q).lower().split())
            if placeholder(q):
                out.append(f"SEGMENTS segment {sid} query {q!r} is a placeholder: write a search a "
                           f"buyer would type")
            elif key in seen:
                out.append(f"SEGMENTS segment {sid} repeats the query {q!r}: each query searches anew")
            elif key in owner and owner[key] != sid:
                out.append(f"SEGMENTS segment {sid} query {q!r} is segment {owner[key]}'s too: "
                           f"segments search disjoint results")
            seen.add(key)
            owner.setdefault(key, sid)
    return out


def check_pool(brief, tsv):
    path = pathlib.Path(tsv)
    if not path.is_absolute():
        path = brief / path
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines:
        return [f"POOL {path.name} is empty"]
    head = lines[0].split("\t")
    out = [f"POOL {path.name} lacks the column {c!r}" for c in POOL_COLUMNS if c not in head]
    if len(lines) < 2:
        out.append(f"POOL {path.name} holds no candidate row")
    seen = {norm_url(u) for u in index_urls(brief)}
    for n, line in enumerate(lines[1:], 2):
        row = dict(zip(head, line.split("\t")))
        if not (row.get("name") or "").strip():
            out.append(f"POOL {path.name}:{n} has no name")
        if norm_url(row.get("url")) not in seen:
            out.append(f"POOL {path.name}:{n} {row.get('name')!r}: url {row.get('url')!r} is not a URL "
                       f"pages/index.tsv fetched; fetch it with tools/fetch.py or drop the row")
    return out


def title_of(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(m.group(1))).strip() if m else None


def check_names(brief):
    names = load_json(brief / "names.json")
    out = []
    if not isinstance(names, list):
        return ["NAMES names.json is not a list"]
    for key in ("slug", "domain"):
        vals = [r.get(key) for r in names]
        if len(set(vals)) != len(vals):
            out.append(f"NAMES two rows share a {key}: {vals}")
    for r in names:
        pid, dom, name = str(r.get("page_id")), str(r.get("domain")), r.get("name")
        host = pid.rsplit("-", 1)[0]
        if host != dom and not host.endswith("." + dom):
            out.append(f"NAMES {r.get('slug')}: page {pid} is on {host}, not on its own domain {dom}")
        page = brief / "pages" / f"{pid}.html"
        if not page.is_file():
            out.append(f"NAMES {r.get('slug')}: no saved page pages/{pid}.html")
            continue
        title = title_of(page)
        segs = [s.strip() for s in TITLE_SPLIT.split(title or "") if s.strip()]
        if name != title and name not in segs:
            out.append(f"NAMES {r.get('slug')}: name {name!r} is not the brand on its own <title> "
                       f"{title!r} (segments {segs}); write the brand as the title spells it")
    return out


def company_slug(brief, part):
    if part == "client":
        reader = load_json(brief / "reader.json")
        return slugify(reader["company"]["name"]), reader["company"]["domain"], reader["company"]["name"]
    for r in load_json(brief / "names.json"):
        if r.get("slug") == part:
            return part, r["domain"], r["name"]
    raise Unreadable(f"{part!r} is not `client` or a names.json slug")


def check_shard(brief, part):
    slug, domain, name = company_slug(brief, part)
    shard = brief / "parts" / f"{part}.jsonl"
    rows = load_rows(shard)
    out = []
    if not rows:
        out.append(f"SHARD parts/{part}.jsonl holds no row")
    if part != "client":
        qids = {x.get("id") for x in load_json(brief / "questions.json").get("questions") or []}
        for r in rows:
            if r.get("question_id") not in qids:
                out.append(f"SHARD {r.get('id')}: question_id {r.get('question_id')!r} is not a "
                           f"questions.json id {sorted(qids)}")
        joins = [r.get("id") for r in rows if r.get("state") in JOIN_STATES]
        if len(joins) != 1:
            out.append(f"SHARD parts/{part}.jsonl holds {len(joins)} named/not named rows {joins}, "
                       f"want exactly 1: the client's lists read for {name}")
    snap = brief / "snapshots" / f"{domain}.json"
    if not snap.is_file():
        out.append(f"SHARD no snapshot snapshots/{domain}.json")
    else:
        out += [f"SNAPSHOT {f}" for f in schema_check(SCHEMAS / "snapshot.schema.json", snap)]
    if not (brief / f"comp-{slug}.md").is_file():
        out.append(f"SHARD no comp-{slug}.md")
    return out


def check_blocks(brief, part):
    if part == "reader":
        rows, block = load_rows(brief / "claims.jsonl"), READER_BLOCK
    else:
        rows = load_rows(brief / "parts" / f"{part}.jsonl")
        names = load_json(brief / "names.json") if (brief / "names.json").is_file() else []
        if part != "client" and (brief / "id-blocks.json").is_file():
            got = load_json(brief / "id-blocks.json").get(part)
            block = (id_num(got[0]), id_num(got[1])) if got else None
        else:
            block = blocks(names).get(part)
        if block is None:
            raise Unreadable(f"no ID block for {part!r}")
    out = []
    for r in rows:
        n = id_num(r.get("id"))
        if n is None or not block[0] <= n <= block[1]:
            out.append(f"BLOCKS {r.get('id')} is outside {part}'s block {fmt(block[0])}..{fmt(block[1])}")
    return out


def mkt1_calls(brief):
    q = load_json(brief / "questions.json")
    reader = load_json(brief / "reader.json") if (brief / "reader.json").is_file() else {}
    role = reader.get("role") or {}
    calls = []
    if any(x.get("topic") == "buyer" for x in q.get("questions") or []):
        calls.append("icp_prioritization")
    growth = GROWTH.search(f"{role.get('title', '')} {role.get('kind', '')}")
    aeo = any(x.get("topic") in ("aeo", "answer-engines") or ANSWER_ENGINE.search(x.get("text", ""))
              for x in q.get("questions") or [])
    if growth and aeo:
        calls.append("aeo_audit")
    return calls


def check_mkt1(brief):
    notes = [p for p in (brief / "mkt1").glob("*.md") if p.stat().st_size > 0] if (brief / "mkt1").is_dir() else []
    return [] if notes else ["MKT1 mkt1/ holds no non-empty .md note"]


CHECKS = {"reader": check_reader, "questions": check_questions, "segments": check_segments,
          "names": check_names, "mkt1": check_mkt1}
WITH_ARG = {"pool": check_pool, "shard": check_shard, "blocks": check_blocks}


def main(argv):
    args = argv[1:]
    if args == ["--selftest"]:
        return selftest()
    if not args or (args[0] not in CHECKS and args[0] not in WITH_ARG and args[0] != "mkt1-when") \
            or len(args) != (3 if args[0] in WITH_ARG else 2):
        print(__doc__, file=sys.stderr)
        return 2
    brief = pathlib.Path(args[1])
    try:
        if args[0] == "mkt1-when":
            calls = mkt1_calls(brief)
            print("MKT1 " + (", ".join(calls) if calls else "no call applies"))
            return 0 if calls else 1
        found = WITH_ARG[args[0]](brief, args[2]) if args[0] in WITH_ARG else CHECKS[args[0]](brief)
    except (Unreadable, OSError, KeyError, TypeError, AttributeError) as exc:
        print(f"node-check {args[0]}: unreadable input: {exc}", file=sys.stderr)
        return 2
    for f in found:
        print(f, file=sys.stderr)
    if found:
        print(f"NODE-CHECK {args[0]} RED ({len(found)})", file=sys.stderr)
        return 1
    print(f"NODE-CHECK {args[0]} OK")
    return 0


# ---- selftest ---------------------------------------------------------------------------------

FAILS = []


def case(label, ok, detail=""):
    print(f"SELFTEST {'OK  ' if ok else 'FAIL'} {label}" + ("" if ok else f": {detail}"))
    if not ok:
        FAILS.append(label)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, (dict, list)):
        value = json.dumps(value)
    path.write_text(value, encoding="utf-8")


def row(cid, url, **kw):
    r = {"id": cid, "subject": "Acme", "claim": "c", "qualifier": "q", "scope": "s", "metric": "",
         "quote": "q", "url": url, "source": "pages/x.txt:1", "state": "verified", "exclusive": False,
         "lang": "en"}
    r.update(kw)
    return r


def fixture(tmp):
    b = tmp / "brief"
    write(b / "captures" / "jd.json", {"state": "OK", "positioning_pages": [
        {"kind": "home", "url": "https://acme.example/", "state": "FETCHED"},
        {"kind": "llms", "url": "https://acme.example/llms.txt", "state": "FETCHED"},
        {"kind": "company", "url": "https://jobs.example/acme", "state": "BLOCKED"}]})
    write(b / "reader.json", {"company": {"name": "Acme", "domain": "acme.example", "hosts": ["acme.example"]},
                              "role": {"title": "Head of Growth", "jd_url": "https://jobs.example/acme/1", "kind": "head-of-growth"},
                              "recipient": {"source": ["C-003"], "conflict": [], "writing": []},
                              "duties": [{"line": "L4", "weight": 3, "kind": "duty", "text": "Own growth"}],
                              "positioning": [{"id": "P1", "source": ["C-001"]}, {"id": "P2", "source": ["C-002"]}]})
    write(b / "claims.jsonl", "\n".join(json.dumps(r) for r in (
        row("C-001", "https://acme.example/"), row("C-002", "https://acme.example/llms.txt"),
        row("C-003", "https://acme.example/team"))) + "\n")
    write(b / "questions.json", {"questions": [{"id": "Q1", "topic": "buyer", "text": "Who buys?", "serves": ["L4"]},
                                               {"id": "Q2", "topic": "price", "text": "What does it cost?", "serves": ["P1"]}],
                                 "axes": ["a"], "seeds": []})
    write(b / "02-questions.md", "# Q\n\n### Q1. Who buys?\n\n### Q2. What does it cost?\n")
    write(b / "segments.json", {"segments": [
        {"id": str(i), "name": f"Space {i}", "shape": f"Finance teams buying ledger tool {i}",
         "market": "UK", "language": "en", "queries": [f"ledger tool {i} uk", f"reconciliation vendor {i}"],
         "why": '"Acme builds the ledger" (home)'} for i in range(1, 6)]})
    write(b / "pages" / "index.tsv", "url\tfinal_url\tstatus\tfetched_at\tsha256\tbytes\tpath\n"
          "https://rival.example/\thttps://rival.example/\t200\tt\ts\t1\tpages/rival.example-0123abcd.html\n"
          "https://www.other.example/\thttps://www.other.example/\t200\tt\ts\t1\tpages/www.other.example-89abcdef.html\n")
    write(b / "pages" / "rival.example-0123abcd.html", "<html><head><title>Rival | Ads that sell</title></head></html>")
    write(b / "pages" / "www.other.example-89abcdef.html", "<title>Other Co: the platform</title>")
    write(b / "pool" / "1.tsv", "\t".join(POOL_COLUMNS) + "\nRival\thttps://rival.example/\t200\tads\tyes\tUK\trival\n")
    names = [{"slug": "rival", "name": "Rival", "domain": "rival.example", "page_id": "rival.example-0123abcd"},
             {"slug": "other-co", "name": "Other Co", "domain": "other.example", "page_id": "www.other.example-89abcdef"}]
    write(b / "names.json", names)
    write(b / "id-blocks.json", {k: [fmt(a), fmt(z)] for k, (a, z) in blocks(names).items()})
    write(b / "parts" / "rival.jsonl", "\n".join(json.dumps(r) for r in (
        row("C-200", "https://rival.example/", subject="Rival", question_id="Q1"),
        row("C-201", "https://acme.example/customers", subject="Rival", question_id="Q2", state="not named"))) + "\n")
    write(b / "parts" / "client.jsonl", json.dumps(row("C-100", "https://acme.example/")) + "\n")
    snap = {"domain": "rival.example", "name": "Rival", "captured": "2026-10-13",
            "sources": [{"url": "https://rival.example/", "type": "primary", "date": "2026-10-13"}]}
    write(b / "snapshots" / "rival.example.json", snap)
    write(b / "snapshots" / "acme.example.json", dict(snap, domain="acme.example", name="Acme"))
    write(b / "comp-rival.md", "# Rival\n")
    write(b / "comp-acme.md", "# Acme\n")
    write(b / "mkt1" / "icp.md", "notes\n")
    return b


def edit_json(path, fn):
    data = json.loads(path.read_text())
    fn(data)
    path.write_text(json.dumps(data))


def selftest():
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        b = fixture(tmp)
        for name in CHECKS:
            got = CHECKS[name](b)
            case(f"{name}: green on the fixture", not got, got)
        for name, arg in (("pool", "pool/1.tsv"), ("shard", "rival"), ("shard", "client"),
                          ("blocks", "reader"), ("blocks", "client"), ("blocks", "rival")):
            got = WITH_ARG[name](b, arg)
            case(f"{name} {arg}: green on the fixture", not got, got)
        case("mkt1-when: a buyer question calls icp_prioritization only", mkt1_calls(b) == ["icp_prioritization"],
             mkt1_calls(b))

        def red(label, mutate, fn, want, restore=None):
            snapshot = {p: p.read_bytes() for p in b.rglob("*") if p.is_file()}
            mutate()
            got = fn()
            case(label, any(want in g for g in got), got)
            for p in [p for p in b.rglob("*") if p.is_file() and p not in snapshot]:
                p.unlink()
            for p, data in snapshot.items():
                p.write_bytes(data)

        red("reader: a fetched llms.txt with no positioning line is red",
            lambda: edit_json(b / "reader.json", lambda d: d["positioning"].pop()),
            lambda: check_reader(b), "llms page")
        red("reader: a cited ID with no row is red",
            lambda: edit_json(b / "reader.json", lambda d: d["recipient"]["source"].append("C-099")),
            lambda: check_reader(b), "cites C-099")
        red("questions: a heading out of step with questions.json is red",
            lambda: write(b / "02-questions.md", "### Q2. What does it cost?\n### Q1. Who buys?\n"),
            lambda: check_questions(b), "headings")
        red("questions: serves naming no duty or positioning id is red",
            lambda: edit_json(b / "questions.json", lambda d: d["questions"][0]["serves"].append("L99")),
            lambda: check_questions(b), "serves L99")
        red("segments: a repeated id is red",
            lambda: write(b / "segments.json", {"segments": [{"id": "1"}] * 5}),
            lambda: check_segments(b), "want 1 to 5")
        red("segments: a real run's BLOCKED placeholder pool is red",
            lambda: write(b / "segments.json", (FIXTURES / "segments-blocked.json").read_text()),
            lambda: check_segments(b), "segment 1 name is a placeholder ('BLOCKED')")
        red("segments: an empty market is red",
            lambda: edit_json(b / "segments.json", lambda d: d["segments"][2].update(market=" ")),
            lambda: check_segments(b), "segment 3 market is a placeholder")
        red("segments: a query repeated inside a segment is red",
            lambda: edit_json(b / "segments.json", lambda d: d["segments"][0].update(queries=["ledger tool", "Ledger  tool"])),
            lambda: check_segments(b), "segment 1 repeats the query")
        red("segments: a query another segment already searches is red",
            lambda: edit_json(b / "segments.json", lambda d: d["segments"][4]["queries"].append("ledger tool 1 uk")),
            lambda: check_segments(b), "segment 5 query 'ledger tool 1 uk' is segment 1's too")
        write(b / "segments.json", (FIXTURES / "segments-real.json").read_text())
        case("segments: a real run's segments.json is green", not check_segments(b), check_segments(b))
        red("pool: a row on a URL nobody fetched is red",
            lambda: write(b / "pool" / "1.tsv", "\t".join(POOL_COLUMNS) + "\nGhost\thttps://ghost.example/\t200\tx\tyes\tUK\tg\n"),
            lambda: check_pool(b, "pool/1.tsv"), "not a URL")
        red("pool: a missing column is red",
            lambda: write(b / "pool" / "1.tsv", "name\turl\nRival\thttps://rival.example/\n"),
            lambda: check_pool(b, "pool/1.tsv"), "lacks the column")
        red("names: a name its <title> does not carry is red",
            lambda: edit_json(b / "names.json", lambda d: d[0].update(name="Rival Inc")),
            lambda: check_names(b), "not the brand")
        red("names: a page off the company's own domain is red",
            lambda: edit_json(b / "names.json", lambda d: d[1].update(domain="else.example")),
            lambda: check_names(b), "not on its own domain")
        red("shard: a row with no question_id is red",
            lambda: write(b / "parts" / "rival.jsonl", json.dumps(row("C-200", "u", state="not named")) + "\n"),
            lambda: check_shard(b, "rival"), "question_id None")
        red("shard: a rival shard with no named/not named row is red",
            lambda: write(b / "parts" / "rival.jsonl", json.dumps(row("C-200", "u", question_id="Q1")) + "\n"),
            lambda: check_shard(b, "rival"), "want exactly 1")
        red("shard: a snapshot missing `sources` is red on the snapshot schema",
            lambda: edit_json(b / "snapshots" / "rival.example.json", lambda d: d.pop("sources")),
            lambda: check_shard(b, "rival"), "SNAPSHOT")
        red("shard: no comp file is red",
            lambda: (b / "comp-acme.md").unlink(), lambda: check_shard(b, "client"), "comp-acme.md")
        red("blocks: a rival row outside its block is red",
            lambda: write(b / "parts" / "rival.jsonl", json.dumps(row("C-300", "u", question_id="Q1")) + "\n"),
            lambda: check_blocks(b, "rival"), "outside rival's block C-200..C-299")
        red("blocks: a reader row past C-099 is red",
            lambda: write(b / "claims.jsonl", json.dumps(row("C-100", "u")) + "\n"),
            lambda: check_blocks(b, "reader"), "C-001..C-099")
        red("mkt1: an empty mkt1/ is red", lambda: (b / "mkt1" / "icp.md").write_text(""),
            lambda: check_mkt1(b), "no non-empty")
        edit_json(b / "questions.json", lambda d: d["questions"][0].update(topic="channels"))
        case("mkt1-when: no buyer topic and no growth seat calls nothing", mkt1_calls(b) == [], mkt1_calls(b))
        edit_json(b / "questions.json", lambda d: d["questions"][1].update(text="Which rivals do answer engines cite?"))
        case("mkt1-when: a growth seat and an answer-engine question call aeo_audit",
             mkt1_calls(b) == ["aeo_audit"], mkt1_calls(b))
        case("blocks: rival i owns C-(200+100i)..C-(299+100i)",
             blocks([{"slug": "a"}, {"slug": "b"}]) == {"reader": (1, 99), "client": (100, 199), "a": (200, 299), "b": (300, 399)})
    if FAILS:
        print(f"NODE-CHECK SELFTEST FAIL ({len(FAILS)}): " + "; ".join(FAILS))
        return 1
    print("NODE-CHECK SELFTEST OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
