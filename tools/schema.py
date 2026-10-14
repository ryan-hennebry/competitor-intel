#!/usr/bin/env python3
"""The one JSON Schema validator: every typed artefact of a run against its schema.

WHY THIS EXISTS. The runner decides a node by exit codes, so each artefact a node writes (`run.json`,
`reader.json`, `questions.json`, `claims.jsonl`, `names.json`, `candidates.json`, `05-thesis.json`,
verdicts, findings, `patches.json`, `verify.jsonl`, `run-log.jsonl`, `decisions.tsv`,
`rulings.tsv`, `brief.json`) has a schema under `references/schemas/` (`brief.json`'s is
`build/web/brief.schema.json`), and this file grades it. `tools/brief-check.py` imports `validate`
from here, so the brief and every other artefact are read one way. `jsonschema` is not a CI
dependency.

THE DIALECT is exactly KEYWORDS, with JSON Schema 2020-12 semantics: a keyword applies only to its
own instance type. Two narrowings and one extension:
  - `$ref` is `#/$defs/<name>`, a sibling file `<name>.schema.json`, or `<file>#/$defs/<name>`,
    resolved beside the referring schema;
  - `additionalProperties` is a boolean;
  - `x-maxWords` caps whitespace-separated words, counted on a string, or on a span array's `t`
    values joined.
A keyword outside the dialect is exit 2, so no schema carries a bound nobody enforces.

INPUT FORMS, by suffix: `.json` is one instance; `.jsonl` is one instance per non-blank line; `.tsv`
is a header row, then one instance per row, each cell a string keyed by its header.

EXIT CODES. 0 valid. 1 violations, one line each. 2 the script could not do its job: bad usage, a
missing file, an unreadable schema, or a keyword outside the dialect.

  python3 tools/schema.py <schema> <file>
  python3 tools/schema.py --fixtures [cases.tsv]   every bad-shape fixture reds with its own line
  python3 tools/schema.py --selftest               the dialect, keyword by keyword, then --fixtures

PRECONDITION: none. No network, no environment variable.
"""

import contextlib
import copy
import csv
import io
import json
import pathlib
import re
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
CASES = ROOT / "tools/fixtures/schema/cases.tsv"

ANNOTATIONS = {"$schema", "$id", "title", "description", "$defs"}
KEYWORDS = {"$ref", "type", "const", "enum", "pattern", "minLength", "minItems", "maxItems",
            "uniqueItems", "items", "required", "properties", "additionalProperties", "minimum",
            "maximum", "x-maxWords"}
TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "integer": int,
         "number": (int, float)}


class SchemaError(Exception):
    """The schema itself is unusable: exit 2, never a finding against the instance."""


def words(node):
    """x-maxWords' count: a string's words, or a span array's t values joined."""
    if isinstance(node, str):
        return len(node.split())
    return len("".join(s["t"] for s in node
                       if isinstance(s, dict) and isinstance(s.get("t"), str)).split())


def is_type(node, name):
    if name == "null":
        return node is None
    if name not in TYPES:
        raise SchemaError("type %r is not one this validator knows" % name)
    return isinstance(node, TYPES[name]) and (name == "boolean" or not isinstance(node, bool))


_FILES = {}


def load_schema(path):
    path = pathlib.Path(path)
    key = str(path.resolve())
    if key not in _FILES:
        try:
            _FILES[key] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise SchemaError("cannot read %s (%s)" % (path, exc))
        if not isinstance(_FILES[key], dict):
            raise SchemaError("%s is not a JSON object" % path)
    return _FILES[key]


def resolve(ref, defs, base):
    """A `$ref` as (schema, defs, base) for the node it names."""
    target, _, frag = ref.partition("#")
    if target:
        if base is None or "/" in target or not target.endswith(".schema.json"):
            raise SchemaError("unresolvable $ref %r: a file ref names a sibling *.schema.json" % ref)
        whole = load_schema(pathlib.Path(base) / target)
        defs = whole.get("$defs", {})
        if not frag:
            return whole, defs, base
    elif not frag:
        raise SchemaError("unresolvable $ref %r" % ref)
    name = frag.rsplit("/", 1)[-1]
    if not frag.startswith("/$defs/") or name not in defs:
        raise SchemaError("unresolvable $ref %r" % ref)
    return defs[name], defs, base


def validate(node, sch, defs, path, out, base=None):
    """Appends `path: problem` strings to `out`. `base` is the directory sibling-file refs resolve in."""
    if not isinstance(sch, dict):
        raise SchemaError("the schema at %s is not an object" % path)
    unknown = set(sch) - KEYWORDS - ANNOTATIONS
    if unknown:
        raise SchemaError("keyword(s) %s at %s are not ones this validator enforces" %
                          (sorted(unknown), path))
    if sch.get("additionalProperties", False) not in (True, False):
        raise SchemaError("additionalProperties at %s is a schema; this dialect takes a boolean" % path)
    if "items" in sch and not isinstance(sch["items"], dict):
        raise SchemaError("items at %s is not one schema" % path)
    if "$ref" in sch:
        target, tdefs, tbase = resolve(sch["$ref"], defs, base)
        validate(node, target, tdefs, path, out, tbase)
    if "type" in sch:
        kinds = sch["type"] if isinstance(sch["type"], list) else [sch["type"]]
        if not any(is_type(node, k) for k in kinds):
            out.append("%s: is %s, want %s" % (path, type(node).__name__, " or ".join(kinds)))
            return
    if "const" in sch and not (type(node) is type(sch["const"]) and node == sch["const"]):
        out.append("%s: is %r, want %r" % (path, node, sch["const"]))
    if "enum" in sch and not any(type(node) is type(e) and node == e for e in sch["enum"]):
        out.append("%s: is %r, want one of %s" % (path, node, sch["enum"]))
    if isinstance(node, str):
        if len(node) < sch.get("minLength", 0):
            out.append("%s: is shorter than %d characters" % (path, sch["minLength"]))
        if "pattern" in sch and not re.search(sch["pattern"], node):
            out.append("%s: %r does not match %s" % (path, node, sch["pattern"]))
    if isinstance(node, (int, float)) and not isinstance(node, bool):
        if "minimum" in sch and node < sch["minimum"]:
            out.append("%s: %r is below the minimum %r" % (path, node, sch["minimum"]))
        if "maximum" in sch and node > sch["maximum"]:
            out.append("%s: %r is over the maximum %r" % (path, node, sch["maximum"]))
    if isinstance(node, list):
        if len(node) < sch.get("minItems", 0):
            out.append("%s: %d item(s), want at least %d" % (path, len(node), sch["minItems"]))
        if "maxItems" in sch and len(node) > sch["maxItems"]:
            out.append("%s: %d items, over the cap of %d" % (path, len(node), sch["maxItems"]))
        if sch.get("uniqueItems"):
            keys = [json.dumps(x, sort_keys=True) for x in node]
            if len(keys) != len(set(keys)):
                out.append("%s: items repeat" % path)
        if "items" in sch:
            for i, item in enumerate(node):
                validate(item, sch["items"], defs, "%s[%d]" % (path, i), out, base)
    if "x-maxWords" in sch and isinstance(node, (str, list)) and words(node) > sch["x-maxWords"]:
        out.append("%s: %d words, over the cap of %d" % (path, words(node), sch["x-maxWords"]))
    if isinstance(node, dict):
        for key in sch.get("required", []):
            if key not in node:
                out.append("%s: missing %r" % (path, key))
        props = sch.get("properties", {})
        for key, value in node.items():
            if key in props:
                validate(value, props[key], defs, "%s.%s" % (path, key), out, base)
            elif sch.get("additionalProperties") is False:
                out.append("%s: %r is not a field of this object" % (path, key))


def instances(path):
    """[(label, instance)] read from a .json, .jsonl or .tsv file, plus the lines that did not parse.
    A missing or unreadable file is OSError, the caller's exit 2."""
    path = pathlib.Path(path)
    text = path.read_text(encoding="utf-8")
    found, bad = [], []
    if path.suffix == ".jsonl":
        for n, line in enumerate(text.split("\n"), start=1):
            if line.strip():
                try:
                    found.append(("%s:%d: $" % (path, n), json.loads(line)))
                except ValueError as exc:
                    bad.append("%s:%d: the line is not JSON (%s)" % (path, n, exc))
    elif path.suffix == ".tsv":
        rows = list(csv.reader(io.StringIO(text), delimiter="\t"))
        head = rows[0] if rows else []
        for n, row in enumerate(rows[1:], start=2):
            if not any(cell.strip() for cell in row):
                continue
            if len(row) != len(head):
                bad.append("%s:%d: %d cells under a %d-column header" % (path, n, len(row), len(head)))
                continue
            found.append(("%s:%d: $" % (path, n), dict(zip(head, row))))
    else:
        try:
            found.append(("%s: $" % path, json.loads(text)))
        except ValueError as exc:
            bad.append("%s: the file is not JSON (%s)" % (path, exc))
    return found, bad


def check(schema_path, data_path):
    """Every violation of `data_path` against `schema_path`, one string each. Raises SchemaError
    and OSError."""
    sch = load_schema(schema_path)
    found, out = instances(data_path)
    if not found and not out:
        out.append("%s: holds no instance" % data_path)
    for label, inst in found:
        got = []
        validate(inst, sch, sch.get("$defs", {}), "$", got, pathlib.Path(schema_path).parent)
        out += [label[:-1] + g for g in got]
    return out


def run_cases(cases=CASES, quiet=False):
    """--fixtures: each row of cases.tsv is `file schema want`. `want` is `green`, or the text the
    one violation must hold; two violations, or one without that text, is a failure too, so a
    fixture reds for its own reason or not at all. Paths are relative to the repository root."""
    fails, n = [], 0
    rows = list(csv.DictReader(pathlib.Path(cases).open(encoding="utf-8"), delimiter="\t"))
    if not rows or set(rows[0]) != {"file", "schema", "want"}:
        raise SchemaError("%s: want the header file<TAB>schema<TAB>want and one row or more" % cases)
    for row in rows:
        n += 1
        got = check(ROOT / row["schema"], ROOT / row["file"])
        if row["want"] == "green":
            ok = not got
        else:
            ok = len(got) == 1 and row["want"] in got[0]
        if not quiet:
            sys.stdout.write("FIXTURE %-5s %s  %s\n" % ("green" if row["want"] == "green" else "red",
                                                        "OK  " if ok else "FAIL", row["file"]))
        if not ok:
            fails.append("%s against %s: want %s, got %s" % (row["file"], row["schema"], row["want"], got))
    return n, fails


# --- selftest -------------------------------------------------------------------------------------
# Each case: (label, schema, instance, the text the one violation holds, or None for green).
UNIT = [
    ("type string", {"type": "string"}, 3, "want string"),
    ("type integer refuses a boolean", {"type": "integer"}, True, "want integer"),
    ("type integer refuses a float", {"type": "integer"}, 1.5, "want integer"),
    ("type number takes an integer", {"type": "number"}, 2, None),
    ("type null in a list", {"type": ["string", "null"]}, None, None),
    ("const", {"const": "a"}, "b", "want 'a'"),
    ("enum", {"enum": ["a", "b"]}, "c", "want one of"),
    ("enum keeps 1 and true apart", {"enum": [1]}, True, "want one of"),
    ("pattern", {"pattern": "^Q[0-9]+$"}, "Z1", "does not match"),
    ("minLength", {"minLength": 2}, "a", "shorter than 2"),
    ("minimum", {"minimum": 1}, 0, "below the minimum"),
    ("maximum", {"maximum": 3}, 4, "over the maximum"),
    ("minItems", {"minItems": 2}, [1], "want at least 2"),
    ("maxItems", {"maxItems": 1}, [1, 2], "over the cap of 1"),
    ("uniqueItems", {"uniqueItems": True}, ["a", "a"], "items repeat"),
    ("items", {"items": {"type": "string"}}, ["a", 1], "$[1]: is int"),
    ("required", {"required": ["a"]}, {}, "missing 'a'"),
    ("properties", {"properties": {"a": {"type": "string"}}}, {"a": 1}, "$.a: is int"),
    ("additionalProperties false", {"additionalProperties": False}, {"b": 1}, "not a field"),
    ("x-maxWords on a string", {"x-maxWords": 2}, "one two three", "3 words, over the cap of 2"),
    ("x-maxWords on a span array", {"x-maxWords": 2}, [{"t": "one two"}, {"t": " three"}], "3 words"),
    ("$ref to a def", {"$ref": "#/$defs/d"}, 1, "want string"),
    ("a keyword applies to its own type only", {"minLength": 3, "minItems": 3}, 5, None),
]
UNIT_DEFS = {"d": {"type": "string"}}


def selftest():
    fails, count = [], 0

    def verdict(label, ok, got):
        nonlocal count
        count += 1
        if ok:
            sys.stdout.write("SELFTEST OK  %s\n" % label)
        else:
            fails.append("%s: got %s" % (label, got))

    for label, sch, inst, want in UNIT:
        got = []
        validate(inst, sch, UNIT_DEFS, "$", got)
        verdict(label, (not got) if want is None else (len(got) == 1 and want in got[0]), got)
    # Fail closed: a keyword outside the dialect, a schema-valued additionalProperties, a tuple
    # items, an unknown type and a dangling ref are each exit 2, never a silent pass.
    for label, sch in (("an unknown keyword", {"maxLength": 3}),
                       ("additionalProperties as a schema", {"additionalProperties": {"type": "string"}}),
                       ("items as a list", {"items": [{"type": "string"}]}),
                       ("an unknown type", {"type": "date"}),
                       ("a dangling $ref", {"$ref": "#/$defs/nobody"}),
                       ("a $ref outside the directory", {"$ref": "../x.schema.json"})):
        try:
            validate("x", sch, {}, "$", [], ROOT)
            verdict("fails closed on " + label, False, "no SchemaError")
        except SchemaError:
            verdict("fails closed on " + label, True, None)
    # Sibling-file refs, whole file and a def in it, and the three input forms through check().
    with tempfile.TemporaryDirectory() as tmp:
        d = pathlib.Path(tmp)
        (d / "leaf.schema.json").write_text(json.dumps(
            {"type": "object", "required": ["k"], "$defs": {"n": {"type": "integer"}}}))
        (d / "top.schema.json").write_text(json.dumps(
            {"type": "object", "additionalProperties": False,
             "properties": {"a": {"$ref": "leaf.schema.json"}, "b": {"$ref": "leaf.schema.json#/$defs/n"}}}))
        (d / "row.schema.json").write_text(json.dumps(
            {"type": "object", "required": ["id"], "properties": {"id": {"pattern": "^C-"}}}))
        (d / "x.json").write_text(json.dumps({"a": {}, "b": "2"}))
        got = check(d / "top.schema.json", d / "x.json")
        verdict("a sibling-file $ref, whole and to a def",
                len(got) == 2 and "$.a: missing 'k'" in got[0] and "$.b: is str" in got[1], got)
        (d / "x.jsonl").write_text('{"id": "C-1"}\n\n{"id": "Z"}\nnot json\n')
        got = check(d / "row.schema.json", d / "x.jsonl")
        verdict("jsonl: one label per line, an unparsed line counted",
                len(got) == 2 and any(":3: $.id" in g for g in got) and any(":4: the line" in g for g in got), got)
        (d / "x.tsv").write_text("id\tnote\nC-1\ta\nZ\tb\nC-2\n")
        got = check(d / "row.schema.json", d / "x.tsv")
        verdict("tsv: cells keyed by the header, a short row counted",
                len(got) == 2 and any(":3: $.id" in g for g in got) and any(":4: 1 cells" in g for g in got), got)
        (d / "empty.jsonl").write_text("\n")
        got = check(d / "row.schema.json", d / "empty.jsonl")
        verdict("an empty file is a violation, never green", len(got) == 1 and "no instance" in got[0], got)
        with contextlib.redirect_stderr(io.StringIO()):
            codes = (main(["schema.py"]), main(["schema.py", str(d / "row.schema.json"), str(d / "none.json")]),
                     main(["schema.py", str(d / "nobody.schema.json"), str(d / "x.json")]))
        verdict("bad usage, a missing file and a missing schema exit 2", codes == (2, 2, 2), codes)
        with contextlib.redirect_stdout(io.StringIO()):
            code = main(["schema.py", str(d / "row.schema.json"), str(d / "x.jsonl")])
        verdict("violations exit 1", code == 1, code)
        # The fixture runner's own guard: a fixture that reds for a second reason is a failure.
        (d / "two.json").write_text(json.dumps({"a": {}, "b": "2"}))
        (d / "cases.tsv").write_text("file\tschema\twant\n%s\t%s\tmissing 'k'\n" %
                                     (d / "two.json", d / "top.schema.json"))
        n, f = run_cases(d / "cases.tsv", quiet=True)
        verdict("a fixture red twice is a fixture failure", n == 1 and len(f) == 1, f)
    n, f = run_cases()
    count += n
    fails += f
    for f in fails:
        sys.stderr.write("SELFTEST FAIL: %s\n" % f)
    if fails:
        sys.stderr.write("SELFTEST RED (%d failure%s)\n" % (len(fails), "" if len(fails) == 1 else "s"))
        return 1
    sys.stdout.write("SELFTEST OK (%d cases)\n" % count)
    return 0


USAGE = ("usage: schema.py <schema> <file.json|file.jsonl|file.tsv>\n"
         "       schema.py --fixtures [cases.tsv]\n       schema.py --selftest\n")


def main(argv):
    try:
        if argv[1:] == ["--selftest"]:
            return selftest()
        if argv[1:2] == ["--fixtures"] and len(argv) <= 3:
            n, fails = run_cases(pathlib.Path(argv[2]) if len(argv) == 3 else CASES)
            for f in fails:
                sys.stderr.write("FAIL: %s\n" % f)
            sys.stdout.write("%d fixture(s), %d failing\n" % (n, len(fails)))
            return 1 if fails else 0
        if len(argv) != 3 or any(a.startswith("-") for a in argv[1:]):
            sys.stderr.write(USAGE)
            return 2
        found = check(argv[1], argv[2])
    except SchemaError as exc:
        sys.stderr.write("FAIL: the schema is unusable: %s\n" % exc)
        return 2
    except OSError as exc:
        sys.stderr.write("FAIL: cannot read %s\n" % exc)
        return 2
    for line in found:
        sys.stdout.write(line + "\n")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
