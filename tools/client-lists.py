#!/usr/bin/env python3
"""Where the client's own pages list companies, found by grep (Globex design § 3, `client-lists` node).

WHY THIS EXISTS. Every rival extractor needs one thing from the client's side: the paths and line
ranges where the client's own site lists customers, case studies, integrations or rivals, so it can
write its `named` or `not named` join row. A client extractor used to find them first, 5.3 minutes
on the critical path. b2 § 4 measured a grep over the prefetched client pages finding 11 of that
extractor's 12 rows in under a second, missing one only because its line cap was 90 characters;
this is that grep, at a 200-character cap.

THREE PASSES over `$BRIEF_ROOT/pages/<host>-<8 hex>.txt`, for each client host:
  heading      a line of at most LINE_MAX characters naming a list (HEADING_RE): "trusted by",
               "our customers", "success stories", "testimonials", "integrations", "comparison",
               "top 10 ...". A line reading only "Case Studies" is a nav link, not a list.
  closed-list  a machine file holding story paths (STORY_RE, as a sitemap does), at the first such
               line, or a `## Case Studies` heading (as an llms.txt does).
  names        on a page with no hit above: the first line naming a customer taken from those story
               slugs, when two or more lines name one.
A superset with some noise, by design: each rival extractor reads the page itself.

OUTPUT. `$BRIEF_ROOT/client-lists.tsv`, the header `path<TAB>line<TAB>kind<TAB>text`, then a row per
hit, `text` cut to LINE_MAX. With no hit on any client page it holds exactly one typed row,
`-<TAB>-<TAB>none<TAB><why>`, so "no list" is written, never an empty file.

  python3 tools/client-lists.py BRIEF_ROOT [--hosts h1,h2]   hosts default to reader.json
                                                             company.hosts
  python3 tools/client-lists.py --selftest                   offline, on the Globex client pages

EXIT CODES. 0 written (rows or `none`). 2 bad usage, no hosts, or no client page to read.
"""

import json
import pathlib
import re
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tools/fixtures/client-lists/globex"
COLUMNS = ("path", "line", "kind", "text")
LINE_MAX = 200  # b2 § 4: at 90 the grep missed a list named inside a longer line
HEADING_RE = re.compile(r"trusted by|our (clients|customers|partners)|success stor|testimonial|case studies$|"
                        r"latest .*case studies|integrations?\b|comparison|top [0-9]+ |campaign content", re.I)
NAV_ONLY = re.compile(r"^case studies$", re.I)
STORY_RE = re.compile(r"/(case-studies|case-study|customers|customer-stories|success-stories)/([a-z0-9][a-z0-9-]*)/?")
CLOSED_HEADING = re.compile(r"^#+ case studies\b|\s#+ case studies\b", re.I)
PAGE_NAME = re.compile(r"^(?P<host>.+)-[0-9a-f]{8}\.txt$")


def client_pages(root, hosts):
    out = []
    for path in sorted((root / "pages").glob("*.txt")):
        m = PAGE_NAME.match(path.name)
        if m and m.group("host") in hosts:
            out.append(path)
    return out


def find(root, hosts):
    """[(path, line, kind, text)] over the client's pages, in page then line order."""
    pages = client_pages(root, hosts)
    texts = {p: p.read_text(encoding="utf-8", errors="replace").splitlines() for p in pages}
    rows, hit = [], set()
    slugs = set()
    for p in pages:
        rel = "pages/" + p.name
        for n, line in enumerate(texts[p], start=1):
            t = line.strip()
            if len(t) <= LINE_MAX and HEADING_RE.search(t) and not NAV_ONLY.match(t):
                rows.append((rel, n, "heading", t))
                hit.add(p)
        story = [(n, m) for n, line in enumerate(texts[p], start=1) for m in STORY_RE.finditer(line)
                 if "/images/" not in line[max(0, m.start() - 40):m.end()]]
        found = {m.group(2) for _, m in story}
        slugs |= found
        if found:
            rows.append((rel, story[0][0], "closed-list", "%d story paths under /%s/" % (len(found), story[0][1].group(1))))
            hit.add(p)
        for n, line in enumerate(texts[p], start=1):
            if CLOSED_HEADING.search(line):
                rows.append((rel, n, "closed-list", CLOSED_HEADING.search(line).group(0).strip()))
                hit.add(p)
                break
    names = sorted({s.split("-")[0] for s in slugs if len(s.split("-")[0]) >= 3})
    if names:
        name_re = re.compile(r"\b(%s)\b" % "|".join(map(re.escape, names)), re.I)
        for p in pages:
            if p in hit:
                continue
            lines = [n for n, line in enumerate(texts[p], start=1) if name_re.search(line)]
            if len(lines) >= 2:
                first = texts[p][lines[0] - 1].strip()
                rows.append(("pages/" + p.name, lines[0], "names", "%d lines name a story's customer: %s"
                             % (len(lines), first[:LINE_MAX - 40])))
    rows.sort(key=lambda r: (r[0], r[1]))
    return rows, len(pages)


def write(root, rows, npages):
    body = ["\t".join(COLUMNS)]
    if rows:
        body += ["%s\t%d\t%s\t%s" % (p, n, k, re.sub(r"\s+", " ", t)[:LINE_MAX]) for p, n, k, t in rows]
    else:
        body.append("-\t-\tnone\tno list heading, story path or story customer on %d client page%s"
                    % (npages, "" if npages == 1 else "s"))
    (root / "client-lists.tsv").write_text("\n".join(body) + "\n", encoding="utf-8")


def run(root, hosts=None):
    root = pathlib.Path(root)
    if hosts is None:
        try:
            hosts = json.loads((root / "reader.json").read_text(encoding="utf-8"))["company"]["hosts"]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            sys.stderr.write("client-lists: no --hosts and no reader.json company.hosts (%s)\n" % exc)
            return 2
    hosts = [h.strip().lower() for h in hosts if h.strip()]
    if not hosts:
        sys.stderr.write("client-lists: no client hosts\n")
        return 2
    if not (root / "pages").is_dir():
        sys.stderr.write("client-lists: %s has no pages/\n" % root)
        return 2
    rows, npages = find(root, set(hosts))
    write(root, rows, npages)
    print("CLIENT-LISTS %s (%d rows from %d client pages) -> %s"
          % ("OK" if rows else "NONE", len(rows), npages, root / "client-lists.tsv"))
    return 0


def selftest():
    fails, n = [], 0

    def verdict(label, ok, got=""):
        nonlocal n
        n += 1
        print("SELFTEST %s %s" % ("OK  " if ok else "FAIL", label))
        if not ok:
            fails.append("%s: got %s" % (label, got))

    want = json.loads((FIXTURE / "expected.json").read_text(encoding="utf-8"))
    rows, npages = find(FIXTURE, set(want["hosts"]))
    have = {(p, ln) for p, ln, _, _ in rows}

    def found(r):
        return any(p == r["path"] and a <= ln <= b for p, ln in have for a, b in r["ranges"])
    hits = [r for r in want["rows"] if found(r)]
    missed = [(r["path"], r["lines"]) for r in want["rows"] if not found(r)]
    verdict("finds %d of the Globex extractor's %d client-list rows, on their pages and lines (11 or more wanted)"
            % (len(hits), len(want["rows"])), len(hits) >= 11, missed)
    long_row = ("pages/www.globex.io-60d0809d.txt", 28)
    verdict("a list named inside a line over 90 characters is found (the 200-character cap)",
            long_row in have, sorted(have)[:5])
    verdict("a nav line reading only 'Case Studies' is no hit",
            not any(t.strip().lower() == "case studies" for _, _, k, t in rows if k == "heading"), rows[:3])
    with tempfile.TemporaryDirectory(prefix="client-lists-") as tmp:
        root = pathlib.Path(tmp)
        (root / "pages").mkdir()
        for name in ("pages/www.globex.io-60d0809d.txt", "pages/globex.io-48e4bbf6.txt"):
            (root / name).write_bytes((FIXTURE / name).read_bytes())
        (root / "reader.json").write_text(json.dumps({"company": {"hosts": want["hosts"]}}), encoding="utf-8")
        code = run(root)
        lines = (root / "client-lists.tsv").read_text(encoding="utf-8").splitlines()
        verdict("rows are written under the header, from reader.json's hosts",
                code == 0 and lines[0] == "\t".join(COLUMNS) and len(lines) >= 3
                and all(len(ln.split("\t")) == 4 for ln in lines), lines[:4])
        (root / "pages" / "www.globex.io-60d0809d.txt").write_text("Nothing listed here.\n", encoding="utf-8")
        (root / "pages" / "globex.io-48e4bbf6.txt").write_text("About us.\nContact.\n", encoding="utf-8")
        code = run(root)
        lines = (root / "client-lists.tsv").read_text(encoding="utf-8").splitlines()
        verdict("no hit writes exactly one typed `none` row", code == 0 and len(lines) == 2
                and lines[1].startswith("-\t-\tnone\t"), lines)
        code = run(root, hosts=["other.example"])
        lines = (root / "client-lists.tsv").read_text(encoding="utf-8").splitlines()
        verdict("a host with no saved page is a typed `none` over 0 pages",
                code == 0 and lines[1].endswith("on 0 client pages"), lines)
        (root / "reader.json").unlink()
        verdict("no hosts and no reader.json is exit 2", run(root) == 2)
    if fails:
        print("SELFTEST RED (%d of %d)" % (len(fails), n))
        for f in fails:
            print("  %s" % f)
        return 1
    print("SELFTEST OK (%d cases)" % n)
    return 0


def main(argv):
    args = argv[1:]
    if args == ["--selftest"]:
        return selftest()
    hosts = None
    if len(args) == 3 and args[1] == "--hosts":
        hosts = args[2].split(",")
        args = args[:1]
    if len(args) != 1 or args[0].startswith("-"):
        sys.stderr.write("usage: client-lists.py BRIEF_ROOT [--hosts h1,h2] | client-lists.py --selftest\n")
        return 2
    return run(args[0], hosts)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
