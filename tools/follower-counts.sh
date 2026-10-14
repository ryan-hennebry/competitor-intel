#!/usr/bin/env bash
# S9, R25. Salvaged from the Round run's recorded curl method (not recovered verbatim; no
# byte-identical snippet exists on disk). ~94% / ~100% hit rate on LinkedIn / X in that run.
# Never touch /in/ profile URLs: they return HTTP 999 to curl.
#
# The script prints an OUTCOME, not just a number, because `references/provenance.md` rule 4 says
# "Verified-blocked is not verified-absent. A 403 is recorded as blocked, with the query shapes
# tried, and so is any other refusal to serve the page: a 401, a 429, or LinkedIn's 999." The
# earlier shape swallowed the HTTP status and printed an empty cell for a 403, a 404, a 5xx and a
# page that genuinely carries no count, so a run had no way to tell a refusal from a real nothing
# and Coverage Notes had to guess. classify() EXTENDS rule 4 rather than transcribing it: rule 4
# has two arms and classify() has four. rank() decides which of the two attempts gets written up.
#
# Only the enumerated codes become `blocked`. Anything unrecognised falls to `unknown` and its raw
# code still survives in the attempts column, so the classifier discards nothing.
#
# Each row names the URL that actually produced the winning outcome, and each label in the attempts
# column names the host that attempt actually contacted. AGENTS.md requires every URL in the brief
# to be a page that was actually fetched, and the earlier shape always printed the www URL even when
# the number had come from uk.linkedin.com: a latent provenance defect, fixed here. The attempts
# column carried the same defect one layer down -- it hardcoded `www:` whatever host had answered,
# so a bare `https://linkedin.com/company/x/` footer href was written up as `www:200` -- and
# host_label fixes that half too, rather than leaving a header claim the file did not keep.
#
# V13. The script takes NAME=URL, never a slug. Until 2026-09-06 it took a bare slug and built
# `https://www.linkedin.com/company/${slug}/` from it, and on that day it printed
# `# 6 of 6 count; blocked 0; absent 0; no-count 0; unknown 0` at exit 0 with two of the six numbers
# belonging to unrelated companies: `linkedin.com/company/singulier` is a French packaging agency at
# 16 followers against the real 18,928, and `linkedin.com/company/code-and-co` is a Malmo web studio
# at 66 against the real 3,458 (docs/PLAN.md landmine 6.5). Nothing was wrong with the fetch. The
# URL was wrong, and it was wrong because the run had invented it, which `references/provenance.md`
# rule 1 forbids: every URL comes from a page actually fetched, never constructed. So the URL now
# arrives from the company's own homepage footer, and a slug-shaped argument is refused at exit 2
# rather than quietly accepted, because accepting it is the defect.
#
# The URL alone is not enough, because a footer href can be mistranscribed and a page can be
# renamed. `references/provenance.md` rule 7 asks that a fetched entity be confirmed from the page
# itself rather than from a 200 or an exit 0, so a page that answers with a count must also name the
# company in its <title> before that count is written up. When it does not, the outcome is
# `unconfirmed` and the number is withheld.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

# parse_followers reads LinkedIn company-page HTML on stdin and prints the follower count as a
# bare integer, or nothing if the page carries none. Isolated so it is proved against a saved
# fixture with no network call: run `tools/follower-counts.sh --selftest`, whose first case reads
# tools/fixtures/linkedin-followers-sample.html with a logging curl stub already on PATH and then
# asserts that stub's call log is empty. It exits non-zero on mismatch.
#
# Known limit, measured: it reads digits only, so `12K followers`, `12.3K followers` and
# `1.2M followers` all parse to empty and, on a 200, are labelled `no-count`, which claims the page
# carried no count when it did. Widening the parser is a different slice; until then `no-count` is
# the weaker claim it looks like, not proof that the page was silent.
parse_followers() {
  grep -oE '[0-9][0-9,.]*[0-9]? followers' | head -1 | grep -oE '[0-9,.]+' | tr -d ',.'
}

# parse_title reads the same HTML on stdin and prints the page's <title> as one line, or nothing.
# It is the only thing on the page this script trusts to say WHOSE page it is: a follower count is
# just an integer and names nobody.
#
# Newlines and tabs are folded to spaces first, because a <title> is routinely wrapped across lines
# in saved HTML and because the row this feeds is tab-separated -- a tab surviving out of the page
# would silently add a column. Entities are deliberately NOT decoded here: confirm_entity resolves
# both sides through build/build.py --slug, which unescapes, and decoding twice in two places is how
# the two halves of an identity check drift apart.
parse_title() {
  tr '\n\t' '  ' | grep -oiE '<title[^>]*>[^<]*</title>' | head -1 |
    sed -e 's#<[^>]*>##g' -e 's#^ *##' -e 's# *$##'
}

# classify turns one HTTP code plus whatever parse_followers returned into exactly one token from
# the closed set: count | blocked | absent | no-count | unknown. Pure, no I/O, so the selftest can
# reason about it and so the rule it encodes is readable in one screen.
#
# The arms EXTEND `references/provenance.md` rule 4 as amended; they do not transcribe it. Rule 4
# has two arms and this has four. Rule 4 supplies `blocked` for a 403 and for any other refusal to
# serve the page (401, 429, LinkedIn's own 999), `absent` for a 404 on a canonical path, and the
# "answers and does not carry the value" case this script names `no-count`, which is a statement
# about the page and not about our access to it. The `unknown` catch-all is this script's own
# extension, covering the empty/000 code curl leaves behind on a transport failure: guessing past
# an unenumerated 5xx or 3xx would be exactly the fabrication rule 4 exists to stop.
#
# The dispatch is code first and a count is read only inside a 2xx. LinkedIn's authwall (999) and
# its 403 bodies routinely still carry "N followers", so a number parsed off a refused page is
# discarded ON PURPOSE: publishing it would write a refusal up as a verified count, and
# `docs/history/pipeline.md` counts every integer this script prints toward its coverage pass. This
# is also what makes the `count=""` normalisation in main live rather than dead code, because
# classify can now return blocked or absent with a parsed number still sitting in the caller.
classify() {
  local code="$1" count="$2"

  case "$code" in
    2??) if [ -n "$count" ]; then printf 'count\n'; else printf 'no-count\n'; fi ;;
    401|403|429|999) printf 'blocked\n' ;;
    404) printf 'absent\n' ;;
    *) printf 'unknown\n' ;;
  esac
}

# rank orders the outcomes so main can pick a winner between two attempts: count > absent >
# blocked > no-count > unknown, lower number wins, ties keep the first (canonical) attempt.
#
# `blocked` outranking `no-count` is the load-bearing pair. With www=403 and uk=200-carrying-no-
# count, ranking `no-count` higher would write a refused canonical source up as "there is nothing
# there", which is the exact direction `references/methodology.md:198-199` bans: never report a
# dimension as absent when it was blocked.
#
# The `absent` arm is unreachable by construction: main stops before the retry when the canonical
# attempt is already `absent`, and the demotion block rewrites a uk 404 to `unknown`, so nothing
# that reaches rank is ever `absent`. The arm is kept, but ranking `absent` above `blocked` is safe
# only in company with that demotion. Delete the demotion and this ordering silently lets a
# non-canonical 404 outrank a canonical refusal, which is the direction rule 4 exists to forbid.
rank() {
  case "$1" in
    count) printf '1\n' ;;
    absent) printf '2\n' ;;
    blocked) printf '3\n' ;;
    no-count) printf '4\n' ;;
    *) printf '5\n' ;;
  esac
}

# ident resolves a string to this repository's one identity key by calling
# `python3 build/build.py --slug`, which lower-cases, decodes HTML entities and strips everything
# that is not a letter or a digit.
#
# It calls that function rather than reimplementing it in sed, and that is the whole point of the
# slice: V13's seam is "every artefact resolves through one function". A bash copy of the
# normalisation would be a second answer to the question "is this the same company", and the defect
# this script exists to close is exactly two answers disagreeing -- GATE 5 refused `Code & Co.` its
# own snapshot because one side had decoded `&amp;` and the other had not.
#
# On any failure -- no python3, a moved build.py, a build.py that no longer knows --slug, or a
# string that carries no letter or digit -- ident FAILS, returning 1 after saying so on stderr, and
# its caller withholds the count. That is the fail-closed direction: a broken identity check costs
# a number, never publishes one.
#
# The verdict on an empty key has exactly one owner, and it is `slug_cli` in build/build.py, which
# exits 2 with its own message. ident reads that exit status and does not re-derive the same verdict
# by testing the printed key for emptiness. Two copies of one rule is what this slice removes: while
# the caller here re-derived it, `slug_cli`'s guard could be replaced by `print(""); return 0` with
# every suite still green, because the second copy reached the same answer on its own.
ident() {
  local out
  if ! out="$(python3 "$ROOT/build/build.py" --slug "$1" 2>/dev/null)"; then
    printf 'follower-counts: could not resolve an identity key for "%s"; build/build.py --slug\n' \
      "$1" >&2
    printf '  exited non-zero, so the entity cannot be confirmed and the count is withheld.\n' >&2
    return 1
  fi
  printf '%s\n' "$out"
}

# confirm_entity <name> <title> returns 0 when a segment of the page's title IS the company, 1
# otherwise.
#
# The test is SEGMENT EQUALITY, not containment. A LinkedIn <title> is the company's name inside
# furniture nobody controls -- `Atlar | LinkedIn`, `Acme, Inc. | LinkedIn`, a tagline, a locale --
# so the title is split on that furniture (`|`, `-`, en dash, em dash, `:`, middle dot, bullet),
# each segment is resolved through the same `--slug` function, any segment whose key is `linkedin`
# is dropped, and the company's key must EQUAL one of the segments that remain.
#
# Containment was the earlier shape and it confirmed almost anything. It slugged the whole title,
# `| LinkedIn` furniture included, so every company whose key is a substring of `linkedin` -- `in`,
# `link`, `ink`, `edi` -- confirmed every page it was ever shown, and `Round` confirmed
# `Roundtable Inc | LinkedIn`. A prefix rule does not rescue it: `round` against `Roundtable` is
# exactly the false positive that costs, and no string rule can tell it from the true case.
#
# The accepted consequence: a company whose own name is longer than its LinkedIn title -- `Atlar
# Payments Ltd` against `Atlar | LinkedIn` -- now lands `unconfirmed` rather than confirming. That
# is correct, and it is what the token means.
#
# A 1 means NOT CONFIRMED FROM THE PAGE. It does not mean the page is the wrong company, and no
# message here says that it does. `references/provenance.md` rule 7 carries the caveat and it is
# real: AI Lighthouse Partners' LinkedIn page renders as its product, DiligenceIQ, so a correct
# footer href lands here as unconfirmed. Rule 7 already says what confirms such a page: the footer
# href it came from, read by a human. This function cannot see that and so it declines to claim
# more than it knows.
confirm_entity() {
  local nkey t seg segkey

  if ! nkey="$(ident "$1")"; then
    return 1
  fi

  # Separator furniture -> newlines. The multi-byte separators are spelled in \x escapes so this
  # file stays ASCII: \xe2\x80\x93 en dash, \xe2\x80\x94 em dash, \xc2\xb7 middle dot,
  # \xe2\x80\xa2 bullet.
  t="$2"
  t="${t//|/$'\n'}"
  t="${t//-/$'\n'}"
  t="${t//:/$'\n'}"
  t="${t//$'\xe2\x80\x93'/$'\n'}"
  t="${t//$'\xe2\x80\x94'/$'\n'}"
  t="${t//$'\xc2\xb7'/$'\n'}"
  t="${t//$'\xe2\x80\xa2'/$'\n'}"

  # Split on newline with pathname expansion off: a title is untrusted text and may carry `*`.
  local IFS=$'\n'
  set -f
  set -- $t
  set +f

  for seg in "$@"; do
    # A segment of pure punctuation resolves to no key, and ident says so by exiting non-zero.
    # Its message is suppressed HERE and only here: a title routinely carries such a segment, so
    # it is expected rather than a failure. The company name above gets the loud path.
    if ! segkey="$(ident "$seg" 2>/dev/null)"; then
      continue
    fi
    if [ "$segkey" != "linkedin" ] && [ "$segkey" = "$nkey" ]; then
      return 0
    fi
  done
  return 1
}

# attempt fetches one URL and prints `<code>\t<outcome>\t<count>\t<title>` on a single line.
#
# The `if out="$(curl ...)"` wrapper is what keeps `set -e` from aborting on a non-zero curl exit,
# and it is scoped to that one command; there is no script-level `|| true` here any more, because a
# blanket tolerance is what hid the status codes in the first place.
#
# curl's exit status is not read and so it is not stored. Measured on this machine (bash 3.2.57):
# curl -w still emits the write-out line on transport failure, giving exit 7 with code=000 on
# connection refused and exit 6 with code=000 on DNS failure. An HTTP code is therefore always
# present, and the code alone drives classify(); the exit status would corroborate and decide
# nothing, so keeping it would only be a variable nobody reads.
#
# Every `|| true` that survives in this script wraps parse_followers, which legitimately exits 1
# when the page carries no count: two of them, one in attempt() below and one in the selftest's
# fixture parse. That call is the only kind of call the tolerance belongs on. No `|| true` sits on
# a curl call anywhere, including the selftest's own logging probe, which uses the
# `if curl ...; then :; fi` idiom introduced here rather than the blanket tolerance.
attempt() {
  local out code body count title

  if out="$(curl -sL -A "$UA" --max-time 10 -w '\n%{http_code}' "$1" 2>/dev/null)"; then :; fi
  code="${out##*$'\n'}"
  body="${out%$'\n'*}"
  if [ -z "$code" ]; then
    code="000"
  fi
  count="$(printf '%s' "$body" | parse_followers || true)"
  title="$(printf '%s' "$body" | parse_title || true)"
  printf '%s\t%s\t%s\t%s\n' "$code" "$(classify "$code" "$count")" "$count" "$title"
}

# bad_argument prints why one argument was refused and exits 2. It always prints the required form
# and the reason the old form is gone, because the run that gets this message is the run that was
# about to build a URL out of a company name, and telling it only "bad argument" leaves it free to
# try a slightly different slug.
bad_argument() {
  printf 'follower-counts: bad argument "%s": %s\n' "$1" "$2" >&2
  printf '%s\n' \
    '  Required form: NAME=URL, e.g.' \
    "    tools/follower-counts.sh 'Atlar=https://www.linkedin.com/company/atlarhq/'" \
    "  NAME is the company's name as its own site writes it. URL is the linkedin.com/company/..." \
    "  href taken from that company's own homepage footer -- an absolute http(s) URL. A slug this" \
    '  run constructed from the name is not a canonical URL and is refused: references/provenance.md' \
    '  rule 1 requires every URL to come from a page actually fetched, never constructed, and on' \
    "  2026-09-06 two constructed slugs returned other companies' follower counts at exit 0." >&2
  exit 2
}

# check_argument validates one NAME=URL and prints nothing when it is well formed.
#
# Fail closed: the bare-slug form must not keep working by accident, because that form IS the
# defect. Three refusals, each with its own first line, so a run can tell which of the three it hit.
check_argument() {
  local arg="$1" name url

  case "$arg" in
    *=*) : ;;
    *) bad_argument "$arg" 'expected NAME=URL, and this argument has no "=".' ;;
  esac

  name="${arg%%=*}"
  url="${arg#*=}"

  if [ -z "$name" ]; then
    bad_argument "$arg" 'the NAME before "=" is empty.'
  fi

  case "$url" in
    https://*/company/*|http://*/company/*) : ;;
    *) bad_argument "$arg" \
         'the URL after "=" is not an absolute http(s) URL containing /company/.' ;;
  esac
}

# mirror_url prints the cross-check host for a canonical LinkedIn URL by SWAPPING the host on the
# URL it was given, and prints nothing when there is no mirror to swap to.
#
# It swaps rather than rebuilding the path, and that distinction is the slice. Rebuilding would put
# this script back in the business of constructing URLs out of a slug it parsed, which is the one
# thing V13 removed. The path travels untouched from the footer href to both fetches, so if the
# canonical URL is right the mirror is right, and if it is wrong both are wrong in the same visible
# way rather than one of them being wrong in a way nobody authored.
mirror_url() {
  case "$1" in
    *www.linkedin.com*) printf '%s\n' "${1/www.linkedin.com/uk.linkedin.com}" ;;
    *uk.linkedin.com*) printf '%s\n' "${1/uk.linkedin.com/www.linkedin.com}" ;;
  esac
}

# host_label prints the attempts-column label for the host a URL actually names: the subdomain for
# `<x>.linkedin.com`, the whole host otherwise. `www.linkedin.com` -> `www`, `uk.linkedin.com` ->
# `uk`, and a bare `linkedin.com` -> `linkedin.com`.
#
# The label used to be the literal string `www:` whatever host had been fetched, which is the same
# defect this file's header claims to have fixed for the URL column: a bare
# `https://linkedin.com/company/x/` footer href -- a common shape -- was fetched once and written up
# as `www:200`, naming a host nobody had contacted. mirror_url has no swap for that host either, so
# the cross-check silently did not happen; main now says `mirror:none` rather than printing nothing.
host_label() {
  local host="${1#*://}"
  host="${host%%/*}"
  case "$host" in
    *.linkedin.com) printf '%s\n' "${host%%.*}" ;;
    *) printf '%s\n' "$host" ;;
  esac
}

# main takes NAME=URL arguments and prints one tab-separated row each, then one summary line.
#
# Row: `<url>\t<count>\t<outcome>\t<attempts>\t<title>`. count is empty for every outcome but
# `count`, per rule 2, blank beats guess. attempts is a newline-free space-separated scalar
# (`www:403 uk:200`) rather than an array, because /bin/bash here is 3.2 where expanding an empty
# array under `set -u` is itself an error. title is the fifth column and `-` when the page carried
# none: it is the evidence for the outcome in the third column, so a reader can see WHY a count was
# withheld without refetching the page.
#
# Every argument is validated before the first fetch. Refusing the fourth argument after fetching
# three would leave a half-run behind and teach the caller to read rows rather than the exit code.
main() {
  local arg name url1 url2 a1 a2 rest c1 c2 o1 o2 n1 n2 t1 t2
  local url count outcome attempts title
  local total=0 n_count=0 n_blocked=0 n_absent=0 n_nocount=0 n_unconfirmed=0 n_unknown=0

  for arg in "$@"; do
    check_argument "$arg"
  done

  for arg in "$@"; do
    name="${arg%%=*}"
    url1="${arg#*=}"
    url2="$(mirror_url "$url1")"

    a1="$(attempt "$url1")"
    c1="${a1%%$'\t'*}"
    rest="${a1#*$'\t'}"
    o1="${rest%%$'\t'*}"
    rest="${rest#*$'\t'}"
    n1="${rest%%$'\t'*}"
    t1="${rest#*$'\t'}"

    url="$url1"
    outcome="$o1"
    count="$n1"
    title="$t1"
    attempts="$(host_label "$url1"):$c1"

    # `count` and `absent` both stop here. For `count` there is nothing left to learn. For `absent`,
    # rule 4 makes a 404 on the canonical path the one decisive negative in the whole rule set: a
    # retry can only confirm it or overwrite it with a weaker, non-canonical finding, so the retry
    # is suppressed rather than merely ignored.
    if [ "$o1" != "count" ] && [ "$o1" != "absent" ] && [ -z "$url2" ]; then
      # The cross-check was wanted and there was no host to swap to: a bare `linkedin.com` footer
      # href, or any host mirror_url does not know. Say so in the attempts column. Printing only
      # the one attempt would read as a company whose mirror agreed, or was never wanted.
      attempts="$attempts mirror:none"
    fi

    if [ "$o1" != "count" ] && [ "$o1" != "absent" ] && [ -n "$url2" ]; then
      a2="$(attempt "$url2")"
      c2="${a2%%$'\t'*}"
      rest="${a2#*$'\t'}"
      o2="${rest%%$'\t'*}"
      rest="${rest#*$'\t'}"
      n2="${rest%%$'\t'*}"
      t2="${rest#*$'\t'}"
      attempts="$attempts $(host_label "$url2"):$c2"

      # A uk. 404 is demoted to unknown and never written up as absent, and provenance is what
      # separates the two URLs. The canonical one arrived from the company's own homepage footer,
      # which is what makes it the company's published page; the mirror is that same URL with the
      # host swapped by mirror_url, a cross-check nobody published. (The attempts column names the
      # canonical attempt and then its mirror, each labelled by host_label from the URL that was
      # actually fetched, so `www:` and `uk:` appear when those hosts were the ones contacted and
      # never otherwise.) Rule 4 makes only a 404 on a canonical path absent, so the mirror's 404
      # decides nothing.
      #
      # This comment used to say both URLs were built the same way, by interpolating the slug, so
      # construction was not what separated them. That was true until V13 and is now false: nothing
      # here is constructed.
      #
      # The rule is applied here in main rather than inside classify because canonicality is a
      # property of the call site, not of the HTTP exchange: classify sees a 404 and has no way to
      # know whose 404 it is.
      if [ "$o2" = "absent" ]; then
        o2="unknown"
        n2=""
      fi

      if [ "$(rank "$o2")" -lt "$(rank "$o1")" ]; then
        url="$url2"
        outcome="$o2"
        count="$n2"
        title="$t2"
      fi
    fi

    # Provenance rule 7, applied to the winning attempt: a page that answered with a count has
    # still told us nothing about whose page it was. Confirm the entity from the page or withhold
    # the number.
    #
    # It runs AFTER the winner is chosen and not inside attempt(), for two reasons. classify() maps
    # an HTTP code and a parsed integer to an outcome and has no business knowing which company the
    # run is briefing. And a retry would be pointless: the mirror serves the same page under the
    # same title, so re-fetching an unconfirmed count could only reproduce it.
    if [ "$outcome" = "count" ] && ! confirm_entity "$name" "$title"; then
      outcome="unconfirmed"
    fi

    if [ "$outcome" != "count" ]; then
      count=""
    fi
    if [ -z "$title" ]; then
      title="-"
    fi

    printf '%s\t%s\t%s\t%s\t%s\n' "$url" "$count" "$outcome" "$attempts" "$title"

    total=$((total + 1))
    case "$outcome" in
      count) n_count=$((n_count + 1)) ;;
      blocked) n_blocked=$((n_blocked + 1)) ;;
      absent) n_absent=$((n_absent + 1)) ;;
      no-count) n_nocount=$((n_nocount + 1)) ;;
      unconfirmed) n_unconfirmed=$((n_unconfirmed + 1)) ;;
      *) n_unknown=$((n_unknown + 1)) ;;
    esac
  done

  printf '# %d of %d count; blocked %d; absent %d; no-count %d; unconfirmed %d; unknown %d\n' \
    "$n_count" "$total" "$n_blocked" "$n_absent" "$n_nocount" "$n_unconfirmed" "$n_unknown"
}

# --- selftest -------------------------------------------------------------------------------------
# Fail-fast: the first mismatch prints both got and want and returns non-zero, because a harness that
# reports six results and exits 0 teaches a run to read output instead of exit codes.
#
# The old selftest drove a `count_for_stdin` shim that duplicated production behaviour and could
# have stayed green while production diverged. Both it and `count_for` are gone: a curl stub on
# PATH now drives the real attempt() and the real main() through every branch end to end, so what
# is proved here is what ships.

# stub_install writes the fake curl. It stays tiny because the scenario is data, held in
# $FC_STUB_DIR as files named `www` and `uk`; the stub only picks one and prints it. A file named
# `<slug>.www` or `<slug>.uk` wins over the bare host file, which is how a multi-slug case gives
# each slug a different outcome from one scenario directory.
#
# It does not format `%{http_code}`. Each scenario file is authored as `body\n<code>`, which is
# byte-for-byte what the real `curl -w '\n%{http_code}'` emits, so attempt() splits stub output and
# live output identically. When the scenario supplies no file for a host the stub reproduces a
# transport failure. That behaviour was measured on this machine rather than assumed: real curl
# gives rc=7 code=000 on connection refused and rc=6 code=000 on DNS failure, i.e. it still emits
# the write-out line, which is why the HTTP code and not rc drives classify().
#
# The stub does, however, check that `-w` was actually asked for, and drops the trailing code line
# when it was not. Without that check the stub hands back a status code nobody requested, and the
# whole harness goes green against the pre-S9b `curl ... || true` shape that had no `-w` at all --
# the exact regression classify() exists to prevent. A test that cannot fail on the bug it was
# written for is not evidence, so those lines are load-bearing. The check accepts every legal
# spelling of the same request, because a spelling-only check would go falsely red the day
# production is rewritten: `*--write-out*` covers both `--write-out '...'` and the attached
# `--write-out='...'`, and `*" -w"*` covers both `-w '...'` and the attached `-w'...'`. Matching
# ` -w` without a trailing space is safe here because no other argument this script passes to curl
# begins `-w`, so dropping `-w` entirely still leaves wrote_out=no and still turns the harness red.
stub_install() {
  local stub="$1"

  printf '%s\n' \
    '#!/bin/sh' \
    'printf "%s\n" "$*" >> "$FC_CALL_LOG"' \
    'label=www' \
    'case "$*" in *uk.linkedin*) label=uk ;; esac' \
    'slug=$(printf "%s" "$*" | sed -e "s#.*/company/##" -e "s#/.*##")' \
    'file="$FC_STUB_DIR/$label"' \
    'if [ -f "$FC_STUB_DIR/$slug.$label" ]; then file="$FC_STUB_DIR/$slug.$label"; fi' \
    'wrote_out=no' \
    'case "$*" in *--write-out*|*" -w"*) wrote_out=yes ;; esac' \
    'if [ ! -f "$file" ]; then' \
    '  if [ "$wrote_out" = yes ]; then printf "\n000"; fi' \
    '  exit 7' \
    'fi' \
    'if [ "$wrote_out" = yes ]; then cat "$file"; else sed "\$d" "$file"; fi' \
    'exit 0' \
    >"$stub"
  chmod +x "$stub"
}

# scenario starts a fresh, empty $FC_STUB_DIR, truncates the call log and resets the argument
# vector to the default one company, so every case's call count and arguments are that case's own.
#
# The default NAME is `Acme, Inc.`, which is the name in the fixture title's first segment, because
# confirm_entity now requires segment EQUALITY: `Acme` against `Acme, Inc. | LinkedIn` is exactly
# the shorter-name case the rule refuses, and the cases below are about classify() and the retry,
# not about confirmation.
scenario() {
  FC_STUB_DIR="$SELFTEST_TMP/scenario/$1"
  export FC_STUB_DIR
  mkdir -p "$FC_STUB_DIR"
  : >"$FC_CALL_LOG"
  fc_args "Acme, Inc.=https://www.linkedin.com/company/acme/"
}

# fc_args sets the argument vector check_case hands to main, one NAME=URL per parameter.
#
# A global array and not the space-separated string the old harness word-split: a NAME is a company
# name as its own site writes it, so it contains spaces (`Code & Co.`), and word splitting would
# tear one argument into two and refuse both.
fc_args() {
  FC_ARGS=("$@")
}

# stub_reply <www|uk|slug.www|slug.uk> <body> <code>
stub_reply() {
  printf '%s\n%s' "$2" "$3" >"$FC_STUB_DIR/$1"
}

# summary renders the exact tally line main ends with, so each case's want carries the counters and
# not only the rows. It repeats main's format string on purpose: a mutation to one and not the
# other is precisely the defect this is here to catch.
summary() {
  printf '# %d of %d count; blocked %d; absent %d; no-count %d; unconfirmed %d; unknown %d\n' \
    "$1" "$2" "$3" "$4" "$5" "$6" "$7"
}

# check_case runs main and asserts its WHOLE output, the number of curl calls, and optionally a
# substring the second call's URL must contain. Whole output, not the first row: comparing only the
# first line left the summary line and the multi-slug loop unconstrained, and three mutations (a
# garbled `#` format, `for slug in "${1:-}"`, swapped counter arguments) shipped green under it.
# Comparing whole rows matters for the same reason: a substring assertion passes on a row whose URL
# column names a host it never fetched.
#
# The arguments come from the $FC_ARGS array set by scenario/fc_args, not from a positional string.
# See fc_args for why.
#
# CASES is incremented here so the closing narrative line reports a count derived from execution.
# It used to hardcode `11`; a hardcoded case count survives the deletion of a case, which is the
# one thing that number exists to notice. Same shape as `CASES`/`CHECKS_RUN` in tools/score-check.sh.
check_case() {
  local label="$1" want_out="$2" want_calls="$3" want_second="${4:-}"
  local got_out got_calls line2

  CASES=$((CASES + 1))
  got_out="$(main "${FC_ARGS[@]}")"
  if [ "$got_out" != "$want_out" ]; then
    printf 'SELFTEST FAIL: %s: wrong output\n  got  |%s|\n  want |%s|\n' \
      "$label" "$got_out" "$want_out" >&2
    return 1
  fi
  got_calls="$(wc -l <"$FC_CALL_LOG" | tr -d ' ')"
  if [ "$got_calls" != "$want_calls" ]; then
    printf 'SELFTEST FAIL: %s: curl called %s times, want %s\n' "$label" "$got_calls" "$want_calls" >&2
    return 1
  fi
  if [ -n "$want_second" ]; then
    line2="$(sed -n '2p' "$FC_CALL_LOG")"
    case "$line2" in
      *"$want_second"*) : ;;
      *) printf 'SELFTEST FAIL: %s: second call was "%s", want one naming %s\n' \
           "$label" "$line2" "$want_second" >&2
         return 1 ;;
    esac
  fi
  printf 'SELFTEST OK   %-26s -> %s | %s call(s)\n' \
    "$label" "$(printf '%s' "$got_out" | tr '\n' '|')" "$got_calls"
}

# check_exit runs the SCRIPT FILE as a child process and asserts its exit status and one substring
# of its output. A child and not an in-process call, for two reasons that both matter here.
#
# An exit-2 path cannot be tested in-process at all: `exit` in a shell function exits the shell, so
# an in-process case would take the harness down with it.
#
# And measured bash 3.2 behaviour: `set -e` does not reach inside `$( ( ... ) )`, so a harness that
# runs its subject that way is structurally blind to a `set -e` abort -- tools/known-traps.sh died
# on the real corpus with twelve such cases green. A child process gets its own armed `-e`, and it
# is the only mode here that exercises the entry guard and the argument dispatch at all.
check_exit() {
  local label="$1" want_rc="$2" want_msg="$3" arg="$4"
  local out rc=0

  CASES=$((CASES + 1))
  out="$(bash "${BASH_SOURCE[0]}" "$arg" 2>&1)" || rc=$?
  if [ "$rc" != "$want_rc" ]; then
    printf 'SELFTEST FAIL: %s: exit %s, want %s\n  got |%s|\n' "$label" "$rc" "$want_rc" "$out" >&2
    return 1
  fi
  case "$out" in
    *"$want_msg"*) : ;;
    *) printf 'SELFTEST FAIL: %s: message did not name the reason\n  got  |%s|\n  want a message containing |%s|\n' \
         "$label" "$out" "$want_msg" >&2
       return 1 ;;
  esac
  printf 'SELFTEST OK   %-26s -> exit %s, %s\n' "$label" "$rc" "$want_msg"
}

selftest() {
  local fixture wrong got body_count body_plain body_product want_two title_acme

  CASES=0

  SELFTEST_TMP="$(mktemp -d "${TMPDIR:-/tmp}/follower-counts-selftest.XXXXXX")"
  trap 'rm -rf "$SELFTEST_TMP"' EXIT

  fixture="$(dirname "${BASH_SOURCE[0]}")/fixtures/linkedin-followers-sample.html"
  if [ ! -f "$fixture" ]; then
    printf 'SELFTEST FAIL: no fixture at %s\n' "$fixture" >&2
    return 1
  fi

  # The wrong-company fixture is the one docs/PLAN.md V13 names in its Done clause: a page that
  # answers 200 and carries a real follower count and belongs to somebody else.
  wrong="$(dirname "${BASH_SOURCE[0]}")/fixtures/linkedin-wrong-company.html"
  if [ ! -f "$wrong" ]; then
    printf 'SELFTEST FAIL: no fixture at %s\n' "$wrong" >&2
    return 1
  fi

  title_acme='Acme, Inc. | LinkedIn'
  body_count="<title>$title_acme</title>"'<div class="org-top-card-summary-info-list__info-item">12,345 followers</div>'
  body_plain='<div>no count on this page</div>'
  # A page that renders as the company's PRODUCT rather than its name. Provenance rule 7's own
  # caveat, and a real one: AI Lighthouse Partners' LinkedIn page is titled DiligenceIQ.
  body_product='<title>DiligenceIQ | LinkedIn</title><div>12,345 followers</div>'

  FC_CALL_LOG="$SELFTEST_TMP/curl-calls.log"
  export FC_CALL_LOG
  mkdir -p "$SELFTEST_TMP/bin"
  stub_install "$SELFTEST_TMP/bin/curl"
  PATH="$SELFTEST_TMP/bin:$PATH"
  export PATH
  hash -r

  # S0, the no-network proof. The stub is already on PATH and logs every invocation, so an empty
  # call log after parsing the fixture is evidence that no fetch happened; the claim "it only reads
  # a fixture" is not. This is what keeps `docs/history/pipeline.md`'s promise that --selftest proves
  # the parser against the saved fixture with no network call.
  #
  # An empty log is only evidence if the log is known to record. So call the stub deliberately
  # first and assert the log is NOT empty, then reset it. Without this, neutering the stub's own
  # logging line leaves S0 green and the defect is caught only later, by S1's call count.
  scenario s0
  CASES=$((CASES + 1))
  if curl -sL -w '\n%{http_code}' 'https://www.linkedin.com/company/logging-probe/' >/dev/null 2>&1; then :; fi
  if [ ! -s "$FC_CALL_LOG" ]; then
    printf 'SELFTEST FAIL: no network on parse: the curl stub logged nothing for a deliberate call, so an empty log proves nothing\n' >&2
    return 1
  fi
  : >"$FC_CALL_LOG"
  got="$(parse_followers <"$fixture" || true)"
  if [ "$got" != "12345" ]; then
    printf 'SELFTEST FAIL: no network on parse: parse_followers gave "%s", want "12345"\n' "$got" >&2
    return 1
  fi
  if [ -s "$FC_CALL_LOG" ]; then
    printf 'SELFTEST FAIL: no network on parse: curl was called\n  got  %s\n  want an empty call log\n' \
      "$(tr '\n' ';' <"$FC_CALL_LOG")" >&2
    return 1
  fi
  printf 'SELFTEST OK   %-26s -> %s | 0 call(s), empty %s\n' \
    'no network on parse' "$got" "$FC_CALL_LOG"

  # S1 count on the first attempt: the retry never runs.
  scenario s1
  stub_reply www "$body_count" 200
  check_case 'count first attempt' \
    "https://www.linkedin.com/company/acme/"$'\t'"12345"$'\t'"count"$'\t'"www:200"$'\t'"$title_acme"$'\n'"$(summary 1 1 0 0 0 0 0)" \
    1

  # S2 count on the retry: the winning row must name the uk URL, because that is the page fetched.
  scenario s2
  stub_reply www '' 999
  stub_reply uk "$body_count" 200
  check_case 'count on retry' \
    "https://uk.linkedin.com/company/acme/"$'\t'"12345"$'\t'"count"$'\t'"www:999 uk:200"$'\t'"$title_acme"$'\n'"$(summary 1 1 0 0 0 0 0)" \
    2 'uk.linkedin.com'

  # S3 blocked on both: 999 and 403 are both refusals, never an absence.
  scenario s3
  stub_reply www '' 999
  stub_reply uk '' 403
  check_case 'blocked both hosts' \
    "https://www.linkedin.com/company/acme/"$'\t'$'\t'"blocked"$'\t'"www:999 uk:403"$'\t'"-"$'\n'"$(summary 0 1 1 0 0 0 0)" \
    2 'uk.linkedin.com'

  # S3b a refusal whose body still carries "12,345 followers", which LinkedIn's authwall and its
  # 403 pages routinely do. The outcome must be blocked and the count column must stay EMPTY:
  # printing that number would publish a refused page as a verified count.
  scenario s3b
  stub_reply www "$body_count" 403
  stub_reply uk "$body_count" 403
  check_case 'blocked page carries count' \
    "https://www.linkedin.com/company/acme/"$'\t'$'\t'"blocked"$'\t'"www:403 uk:403"$'\t'"$title_acme"$'\n'"$(summary 0 1 1 0 0 0 0)" \
    2 'uk.linkedin.com'

  # S4 absent suppresses the retry. The call count is the assertion: one call, not two.
  scenario s4
  stub_reply www '' 404
  check_case 'absent suppresses retry' \
    "https://www.linkedin.com/company/acme/"$'\t'$'\t'"absent"$'\t'"www:404"$'\t'"-"$'\n'"$(summary 0 1 0 1 0 0 0)" \
    1

  # S4b the same axis on the other side: a 404 body carrying a count is still absent with an empty
  # count column. Together with S3b this pins the code-before-count dispatch in both directions.
  scenario s4b
  stub_reply www "$body_count" 404
  check_case 'absent page carries count' \
    "https://www.linkedin.com/company/acme/"$'\t'$'\t'"absent"$'\t'"www:404"$'\t'"$title_acme"$'\n'"$(summary 0 1 0 1 0 0 0)" \
    1

  # S5 no-count on both: the pages answered, they simply carry no number.
  scenario s5
  stub_reply www "$body_plain" 200
  stub_reply uk "$body_plain" 200
  check_case 'no-count both hosts' \
    "https://www.linkedin.com/company/acme/"$'\t'$'\t'"no-count"$'\t'"www:200 uk:200"$'\t'"-"$'\n'"$(summary 0 1 0 0 1 0 0)" \
    2 'uk.linkedin.com'

  # S6 unknown: no scenario file for either host, so the stub fails transport and reports 000.
  scenario s6
  check_case 'unknown transport fail' \
    "https://www.linkedin.com/company/acme/"$'\t'$'\t'"unknown"$'\t'"www:000 uk:000"$'\t'"-"$'\n'"$(summary 0 1 0 0 0 0 1)" \
    2 'uk.linkedin.com'

  # S7 the load-bearing precedence pair: a refused www must beat an answering-but-empty uk.
  scenario s7
  stub_reply www '' 403
  stub_reply uk "$body_plain" 200
  check_case 'blocked beats no-count' \
    "https://www.linkedin.com/company/acme/"$'\t'$'\t'"blocked"$'\t'"www:403 uk:200"$'\t'"-"$'\n'"$(summary 0 1 1 0 0 0 0)" \
    2 'uk.linkedin.com'

  # S8 a uk 404 is demoted to unknown, so the www no-count wins rather than being called absent.
  scenario s8
  stub_reply www "$body_plain" 200
  stub_reply uk '' 404
  check_case 'uk 404 demoted' \
    "https://www.linkedin.com/company/acme/"$'\t'$'\t'"no-count"$'\t'"www:200 uk:404"$'\t'"-"$'\n'"$(summary 0 1 0 0 1 0 0)" \
    2 'uk.linkedin.com'

  # S9 two slugs with different outcomes. One slug can never constrain the loop over "$@" or the
  # tallies: with a single company every counter is 0 or 1 and their order in the summary printf
  # does not show. Two rows in order plus a summary that counts both is what pins them.
  scenario s9
  stub_reply acme.www "$body_count" 200
  stub_reply widget.www '' 403
  stub_reply widget.uk '' 403
  fc_args "Acme, Inc.=https://www.linkedin.com/company/acme/" \
          "Widget=https://www.linkedin.com/company/widget/"
  want_two="https://www.linkedin.com/company/acme/"$'\t'"12345"$'\t'"count"$'\t'"www:200"$'\t'"$title_acme"
  want_two="$want_two"$'\n'"https://www.linkedin.com/company/widget/"$'\t'$'\t'"blocked"$'\t'"www:403 uk:403"$'\t'"-"
  want_two="$want_two"$'\n'"$(summary 1 2 1 0 0 0 0)"
  check_case 'two companies, two outcomes' "$want_two" 3 'www.linkedin.com/company/widget'

  # S10 the case docs/PLAN.md V13 names in its Done clause: the fetch is perfect and the page
  # belongs to somebody else. 200, a real count, and a title naming another company. Before V13
  # this printed `3458`-shaped confidence; it must now print no number at all and say why.
  scenario s10
  stub_reply www "$(cat "$wrong")" 200
  fc_args "Code & Co.=https://www.linkedin.com/company/code-and-co/"
  check_case 'wrong company unconfirmed' \
    "https://www.linkedin.com/company/code-and-co/"$'\t'$'\t'"unconfirmed"$'\t'"www:200"$'\t'"Nordic Web Studio AB | LinkedIn"$'\n'"$(summary 0 1 0 0 0 1 0)" \
    1

  # S10b the same fixture, the same 200, the same count, asked for under the name the page actually
  # carries -- `Nordic Web Studio AB`, the whole first segment and not a prefix of it: confirmed,
  # and the number is published. Paired with S10 on purpose. A confirmation check that refuses
  # everything would pass S10 alone, and this is the case it fails.
  scenario s10b
  stub_reply www "$(cat "$wrong")" 200
  fc_args "Nordic Web Studio AB=https://www.linkedin.com/company/nordic-web-studio/"
  check_case 'title confirms the company' \
    "https://www.linkedin.com/company/nordic-web-studio/"$'\t'"66"$'\t'"count"$'\t'"www:200"$'\t'"Nordic Web Studio AB | LinkedIn"$'\n'"$(summary 1 1 0 0 0 0 0)" \
    1

  # S10c rule 7's own caveat: a page that renders as the company's PRODUCT, not its name. It lands
  # unconfirmed rather than being silently counted, which is the honest reading -- the page did not
  # confirm the company, and only the footer href a human read can. The outcome is not a claim that
  # this is the wrong company.
  scenario s10c
  stub_reply www "$body_product" 200
  fc_args "AI Lighthouse Partners=https://www.linkedin.com/company/ai-lighthouse-partners/"
  check_case 'product title unconfirmed' \
    "https://www.linkedin.com/company/ai-lighthouse-partners/"$'\t'$'\t'"unconfirmed"$'\t'"www:200"$'\t'"DiligenceIQ | LinkedIn"$'\n'"$(summary 0 1 0 0 0 1 0)" \
    1

  # S10d the false positive containment used to publish: the company key is a SUBSTRING of the
  # title's key but equals no segment of it. `Round` inside `Roundtable Inc | LinkedIn` slugs to
  # `round` inside `roundtableinclinkedin`, so the old whole-title containment test confirmed a
  # different company's page and printed its 4,210 followers as Round's. Segment equality refuses
  # it: the segments are `roundtableinc` and `linkedin`, and `round` is neither.
  scenario s10d
  stub_reply www '<title>Roundtable Inc | LinkedIn</title><div>4,210 followers</div>' 200
  fc_args "Round=https://www.linkedin.com/company/roundtable/"
  check_case 'substring is not confirmation' \
    "https://www.linkedin.com/company/roundtable/"$'\t'$'\t'"unconfirmed"$'\t'"www:200"$'\t'"Roundtable Inc | LinkedIn"$'\n'"$(summary 0 1 0 0 0 1 0)" \
    1

  # S10e the worst of that class: a company key that is a substring of `linkedin` itself. `In`
  # slugs to `in`, and `in` sits inside the `linkedin` the furniture puts on EVERY page, so under
  # containment this name confirmed every page it was ever shown -- including this unrelated one,
  # whose count would have been published as In's. The furniture segment is dropped and equality
  # does the rest. `link`, `ink` and `edi` are the same defect and the same fix.
  scenario s10e
  stub_reply www "$(cat "$wrong")" 200
  fc_args "In=https://www.linkedin.com/company/in/"
  check_case 'two-letter name unconfirmed' \
    "https://www.linkedin.com/company/in/"$'\t'$'\t'"unconfirmed"$'\t'"www:200"$'\t'"Nordic Web Studio AB | LinkedIn"$'\n'"$(summary 0 1 0 0 0 1 0)" \
    1

  # S14 a footer href on a host that is neither www. nor uk.: a bare `linkedin.com`, which is a
  # common shape. Two assertions in one row. The attempts label is derived from the host actually
  # fetched, so it reads `linkedin.com:200` and not the hardcoded `www:200` that named a host
  # nobody had contacted. And mirror_url has no swap for this host, so the cross-check that a
  # `no-count` outcome would otherwise have triggered did not happen -- `mirror:none` says so,
  # where the earlier shape printed one attempt and left it looking like a mirror that agreed.
  scenario s14
  stub_reply www "$body_plain" 200
  fc_args "Acme, Inc.=https://linkedin.com/company/acme/"
  check_case 'bare host, no mirror' \
    "https://linkedin.com/company/acme/"$'\t'$'\t'"no-count"$'\t'"linkedin.com:200 mirror:none"$'\t'"-"$'\n'"$(summary 0 1 0 0 1 0 0)" \
    1

  # S11-S13 the three refusals, each run as a child process so the entry guard, the argument
  # dispatch and `exit 2` itself are exercised, and each asserting its own reason. The bare slug is
  # the important one: it is the argument form that produced the 2026-09-06 defect, and it must be
  # refused rather than quietly still working.
  scenario s11
  check_exit 'bare slug refused' 2 'expected NAME=URL, and this argument has no "="' \
    'atlarhq'
  check_exit 'non-company URL refused' 2 \
    'the URL after "=" is not an absolute http(s) URL containing /company/' \
    'Atlar=https://atlar.com/about'
  check_exit 'empty NAME refused' 2 'the NAME before "=" is empty' \
    '=https://www.linkedin.com/company/atlarhq/'

  # The refusals must be decided before any fetch. The call log has been reset by scenario s11 and
  # the three children inherited the stubbed PATH, so a single logged call here means one of them
  # got as far as the network on an argument it had already been handed reasons to refuse.
  if [ -s "$FC_CALL_LOG" ]; then
    printf 'SELFTEST FAIL: refusals fetched first\n  got  %s\n  want an empty call log\n' \
      "$(tr '\n' ';' <"$FC_CALL_LOG")" >&2
    return 1
  fi
  CASES=$((CASES + 1))
  printf 'SELFTEST OK   %-26s -> 0 call(s), empty %s\n' 'refusals fetch nothing' "$FC_CALL_LOG"

  rm -rf "$SELFTEST_TMP"
  trap - EXIT

  printf 'SELFTEST OK: %s cases. parser -> 12345 against the saved fixture with a curl stub first proved to log and then an empty call log; stubbed scenarios proved the exact rows, summary line and call count for count, count-on-retry, blocked, blocked-page-carrying-a-count, absent-suppresses-retry, absent-page-carrying-a-count, no-count, unknown, blocked-over-no-count, uk-404-demotion and a two-company run; provenance rule 7 proved on one fixture read both ways -- unconfirmed with the count withheld when the title names another company, count published when the title names this one -- on a page titled for the product rather than the company, on a title whose key CONTAINS the company key but whose segments do not equal it, and on a two-letter name that sits inside the word `linkedin` the furniture puts on every page; one row on a host that is neither www. nor uk., labelled from the host actually fetched and carrying `mirror:none` where no cross-check existed; and three refusals run as child processes, each exiting 2 on its own reason (a bare slug with no "=", a URL with no /company/, an empty NAME) with a call log proving none of them fetched anything first\n' \
    "$CASES"
}

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  if [ "${1:-}" = "--selftest" ]; then
    selftest
  else
    main "$@"
  fi
fi
