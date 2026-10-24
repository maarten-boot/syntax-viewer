# Conversation Log — syntax-viewer

Running log of the design conversation. Newest entries at the bottom.

---

## 2026-10-24 — Session 1

### Entry 1 — Working agreement
**User:** Will describe a scenario. Asked to:
- keep a running conversation log in `Conversation.md`
- prepare a `Plan.md` and a `Spec.md`
- prepare test cases as we go
- keep `Spec.md` and `Plan.md` up to date
- after significant changes, suggest a crosscheck between Spec.md, Plan.md and the actual code

**Assistant:** Created `Conversation.md`, `Spec.md`, `Plan.md`, and `tests/TestCases.md` as skeletons. Waiting for the scenario.

### Entry 2 — Initial scenario
**User:** Wants a small application that:
- loads various grammar/syntax files: Lark, EBNF, and extracts the syntax rules from Lemon, Yacc, Bison; possibly other formats later
- builds a list of non-terminals and terminals and shows it in a scrollable list on the left
- selecting a non-terminal on the left shows that rule's definition in the right window
- in the right window all non-terminals and terminals act as links; selecting a link focuses that item in the left column and shows its definition on the right
- has a search filter to temporarily reduce what is shown in the left list

**Assistant:** Turned this into Spec v0.1 (FR-1…FR-10, NFR-1…NFR-3), a first Plan (core model + parser plug-ins separated from the UI), and initial test cases TC-01…TC-24. Recorded open questions in Spec §6, notably:
- Q1 implementation language / GUI toolkit
- Q2 where the search filter lives (user wrote "right column" but it filters the left list — assumed it sits above the left list)
- Q3 how a rule is displayed (original source text vs. normalised notation)
- Q4 what selecting a terminal shows
- Q5 which EBNF dialect(s)

### Entry 3 — Decisions on open questions
**User answered:**
- Q1 Stack: **Python + PySide6** (pytest for tests)
- Q2 Filter: **filter box above the left list**. Following a link to a symbol hidden by the filter **clears the filter**.
- Q3 Rendering: **both, toggleable**. Normalised notation and the original source text.
- Q5 EBNF: **W3C (`::=`) and ISO 14977 (`= … ;`)**

**Assistant:** Updated Spec to v0.2. FR-2 now covers both EBNF dialects. FR-9 now states the clear-on-link rule. Added FR-11 (rendering toggle), which means the model must keep each rule's original source span. Added TC-26…TC-29. Updated Plan M0 to done, set the stack, and split M5 into W3C and ISO readers. Q4 (terminal view / "used by") and Q6 (nice-to-haves) are still open.

### Entry 4 — Q4 / Q6 answered
**User:**
- Q6: wants **back/forward navigation** and a **clear-history** action. "Used by" is a very nice idea.
- Q4: yes, show **"used by"** for terminals too.

**Assistant:** Spec v0.3:
- FR-10 updated: a terminal shows its definition (if any) plus "used by".
- FR-12 added: a "used by" (reverse references) section for every symbol, with links.
- FR-13 added: back/forward history with browser semantics, plus clear history.

Filter-by-kind and regex filter were not chosen, so they are recorded as deferred. Added TC-30…TC-37. Plan: reverse-reference index goes in the model (M1); history goes in the controller (M7). Starting M1.

### Entry 5 — M1 implemented
**Assistant:** Implemented M1 in `src/syntax_viewer/`:
- `model.py`: Grammar, Symbol, Rule, expression nodes, used-by index, GrammarError
- `readers/__init__.py`: Reader ABC, registry, entry-point plug-ins, `choose()`, `load()`
- `render.py`: normalised text
- `history.py`: pulled forward from M7 because it does not depend on Qt
- `cli.py`: `--dump`, `--format`, `--list-formats`

Also added `pyproject.toml` and `.venv` (Python 3.14, pytest). Tests: `tests/test_{model,registry,history,cli}.py` with a test-only `DummyReader`; 20 pass. Bugs found and fixed while testing:
- Normalised output wrapped leaf symbols in parentheses before `?`, `*`, `+` (precedence table).
- `dump()` bound `sys.stdout` when the function was defined, so redirected output got nothing.

Model deviation: there is no `Group` node. Parentheses are derived from precedence when rendering (Spec/Plan updated).

### Entry 6 — Sample grammars supplied
**User:** Pointed to real grammars to try:
- https://github.com/maarten-boot/kukel: `syntax.ebnf` and `syntax.lark`
- https://github.com/maarten-boot/BBCZ80 (branch `mboot/conversation-log`): `mboot/BBCBASIC.ebnf`

**Assistant:** Copied them to `tests/fixtures/` as `kukel.ebnf`, `kukel.lark`, and `BBCBASIC.ebnf`. Both EBNF files are ISO 14977 style and use features the ISO reader must handle:
- **nested** `(* … *)` comments: kukel's header comment contains `(* ... *)`
- comma concatenation (kukel) **and** plain juxtaposition without commas (BBCBASIC)
- hyphenated names (`name-start`)
- exception `a - b` (kukel)
- special sequences `? any character except EOL ?` (both)
- informal ranges `"a" .. "z"` (BBCBASIC)
- trailing comments after `;`

kukel.lark uses `?rule` / `!rule` prefixes, `-> alias`, `[x]`, `%ignore`, and imports.

New open questions:
- Q7: kukel's convention says "rules whose names start with an upper-case letter are lexical (tokens)". Should these be listed as terminals?
- Q8: should comments next to a rule be shown in the definition view?

### Entry 7 — Q7 / Q8 answered
**User:**
- Q7: **per file**; best to **ask on loading** when the app sees such a pattern.
- Q8: **yes**, showing rule comments would be very helpful.

**Assistant:** Spec v0.5:
- FR-14: uppercase-lexical convention. Detected at load time; the GUI asks; the answer is remembered per file; headless uses `--uppercase-terminals yes|no|auto`.
- FR-15: rule comments. Attachment is positional: leading, inner, and trailing (kukel puts its notes *after* the rule). Comments separated from a rule by a blank line on both sides are section comments and are not attached.

Added TC-42…TC-49. Implementing the model support next, then the crosscheck offered in E5, then the ISO 14977 reader (M5b).

### Entry 8 — FR-14/15 model support and ISO 14977 reader (M5b)
**Assistant:** Implemented:
- `Comment`/`CommentPos` and `Rule.comments`, plus `attach_comments()` (positional heuristic: inner, trailing chain, leading; an indented or same-line comment counts as trailing when ambiguous)
- `Grammar.lexical_candidates()` and `set_lexical()`, which can be toggled at any time
- CLI `--uppercase-terminals auto|yes|no`; the dump now prints comments
- model nodes `Except`, `Repeat` (BBCBASIC `13 * (...)`), `Range`, and `Special`, with rendering
- `readers/iso_ebnf.py`: nested comments, `,` or juxtaposition, hyphenated names, `- .. ? ?`, `n *`, `(/ /)`/`(: :)`, `| / !`, and a "missing ';'" error at the next rule

Results:
- kukel.ebnf: 89 rules; the convention is detected with 25 candidates.
- BBCBASIC.ebnf: parses fully. `EOL` is correctly UNDEFINED (defined only in prose).

40 tests pass. One test expectation was wrong (kukel's first rule is literally named `start`). `.bnf` was dropped from the ISO extensions because classic BNF uses `::=`.

### Entry 9 — Crosscheck X1
**User:** "yes do a crosscheck now."

**Assistant:** Compared Spec v0.5, Plan v0.5, the tests, and the code requirement by requirement, and probed spans, comments, performance, and deep nesting. Full findings are in Plan.md › Crosscheck log, X1. In short:
- Code fixes: the deep-nesting crash (NFR-2), comments missing from the dump for lexical terminals, and FR-14 not excluding native-terminal formats.
- Spec v0.6: FR-3 was garbled by an earlier edit and is now rewritten; other wording and field details brought in line with the code.
- Plan v0.6: signatures updated, and the Lark reader will be hand-written (the library loader loses comments and positions).
- Tests: fixed TC-26; TC-24 now uses a real fixture; added TC-25, TC-29, TC-50, and FR-14 CLI tests. 47 pass.

### Entry 10 — Lark reader (M4)
**User:** "you can continue"

**Assistant:** Implemented `readers/lark.py`, a hand-written reader per decision X1. It handles:
- `?`/`!` prefixes, `-> alias`, `|` continuation lines, `[ ]`, `( )` across lines
- `? * +`, `~ n` / `~ n..m`, `"a".."z"`, `"x"i`, `/re/flags`
- priorities `NAME.2`
- `%import` (dotted, `(A, B)`, `-> alias`), `%ignore`, `%declare`, `%override`, `%extend`
- `//` comments; consecutive lines are merged into one block

Templates (`name{x}`) give a clear "not supported yet" error.

Design: Lark terminal definitions are stored as **rules marked lexical**, reusing the FR-14 mechanism, so terminals get spans, comments, and used-by. `native_terminals=True` blocks the uppercase prompt. Priority and `%ignore` show in the terminal's declaration.

Results on kukel.lark: 89 rules and 16 terminal definitions, no undefined symbols. Rule names match the `lark` library exactly (new cross-check test; `lark` added as a dev dependency).

Bug found: CLI `--uppercase-terminals auto` wiped the Lark reader's lexical set, so terminals showed as rules. Fixed: the CLI leaves native-terminal formats alone. 64 tests pass.

### Entry 11 — W3C EBNF reader (M5a)
**Assistant:** Implemented `readers/w3c_ebnf.py` (XML-spec notation):
- rules end at the next `name ::=`
- `[...]` character classes (stored as Regex terminals), `#xN` char codes, `? * +`, `A - B`, `/* */` comments
- `[n]` rule numbers skipped
- `[ VC: … ]` / `[ WFC: … ]` notes kept as comments, so they attach to the rule

Added the `tests/fixtures/json-w3c.ebnf` fixture (JSON, written for the tests). The `.ebnf` dialect sniff now picks correctly between ISO and W3C for all three `.ebnf` fixtures. `.bnf` is not claimed by either reader, because classic BNF `<angle>` names are not supported. 76 tests pass. All readers that have fixtures are now done; Yacc/Bison and Lemon need sample grammars.

### Entry 12 — GUI (M6 + M7)
**Assistant:** Installed PySide6 6.12 in `.venv`. Implemented three layers:
- `browser.py`: a Qt-free controller for filter, selection, history, view mode, and reveal-on-link.
- `page.py`: Qt-free HTML for the right pane. Kind-coloured `sym:` links in both views, comments (leading/inner/trailing), declaration, used-by, and undefined/no-definition notes. The original view links symbols but not text inside inner comments.
- `gui.py`: QMainWindow with a filter box and symbol list on the left, a QTextBrowser on the right, and a toolbar plus menus:
  - Open, Reload as format (GUI override for FR-2), Quit
  - Original source (Ctrl+U), Upper-case rules are terminals, Find (Ctrl+F)
  - Back (Alt+Left), Forward (Alt+Right), Clear history
  - status bar with counts
  - the FR-14 prompt, remembered per file in QSettings

`render.py` gained a `leaf` hook so the normalised view can emit links.

Tests: `test_browser.py` (Qt-free) and `test_gui.py` (offscreen Qt), 106 in total. Screenshots were reviewed. Bugs found and fixed:
- Re-entrant refresh: clearing the filter from code fired `textChanged`, and the nested refresh deleted list items.
- The selected item was not centred in the list.

UX change: named terminals now sort before literals/regexes, because kukel's ~150 quoted literals buried `Identifier`. Back/forward to a filtered-out symbol also clears the filter, consistent with FR-9.

### Entry 13 — Yacc/Bison and Lemon readers (M2, M3)
**User:** "yes sqlite is excellent; a yac is here https://gist.github.com/codebrainz/2933703"

**Assistant:** Added fixtures:
- `c99.y`: the gist's C99 Yacc grammar (2012). It has no actions.
- `sqlite-parse.y`: SQLite `src/parse.y` (Lemon, public domain).
- `calc-bison.y`: hand-written to cover the hard cases: `%{ %}` with `}` inside strings, `%define {…}`, `%code`, mid-rule actions with `<type>` tags, named references `[x]`, `%prec`, `%empty`, `error`, string aliases, a missing `;`, and an epilogue.

Implemented:
- `readers/clex.py`: shared C-aware tokenizer. Brace blocks skip nested braces, strings, chars, and comments; optional Yacc sections; line-skipped directives.
- `readers/yacc.py`: symbol declarations with tags and aliases, `%start`, rules; actions recorded in the new `Rule.elided` and stripped from the original view.
- `readers/lemon.py`: aliases, `X|Y` multi-terminals, `[PREC]`, `%token`/`%fallback`/`%wildcard`/`%token_class`/`%type`/`%start_symbol`. `%if*`/`%else`/`%endif` lines are ignored so every rule is shown. Upper-case names are terminals.

Results:
- c99.y: 68 rules, nothing undefined.
- sqlite: 134 non-terminals / 416 productions (= every `::=` outside comments), 191 terminals, nothing undefined.
- `.y` is correctly split: Yacc if it has `%%`, Lemon if it has `x ::=` rules.

Fixed along the way:
- SQLite `%if !A && B` lines broke the tokenizer; they are now skipped at the lexer level.
- Trailing whitespace left by stripped actions is trimmed.
- Lemon reports a missing `.` after `%token` at the next `::=`.
- A rule-less non-terminal (SQLite's leftover `%type part_opt`) now reads "declared, but has no rules"; it used to say "defined elsewhere", which is reserved for Lark imports.

TC-13 (same grammar in all formats) is now automated. 135 tests pass.

### Entry 14 — Crosscheck X2
**Assistant:** Ran X2 over Spec v0.10, Plan v0.10, TestCases, and all code:
1. A mechanical traceability check: Spec test columns ↔ TestCases ↔ test function names.
2. A requirement-by-requirement code review.
3. Mutation fuzzing of every reader against the seven fixtures.
4. A ruff lint pass.

Findings: the fuzzing found a real crash class (`IndexError` in the Yacc reader on truncated `[name]`; the same unbounded look-ahead pattern existed in all readers); traceability gaps; FR-14/FR-15 wording; outdated Plan risks; an untested entry-point path. All fixed; details in Plan.md › Crosscheck log X2. 142 tests pass, 0 fuzz crashes.

Proposed next (M8): README, a shared token-stream base for the readers, and a desktop check of TC-02/TC-15 by the user.

### Entry 15 — Reader base refactor and Makefile
**User:** "start with 3 and add a makefile so we can test run on a screen for inspections." For item 1, on their machine: `.venv/bin/syntax-viewer: cannot execute: required file not found`.

**Assistant:**
- **Cause of the error:** the virtualenv was created on the VM through the NFS path `/net/192.168.122.1/…`, and its scripts hard-code that interpreter path, which does not exist on the user's host. Virtualenvs are not relocatable.
- **Fix:** a per-host virtualenv `.venv-$(hostname -s)` created by `make venv`; the app is started with `python -m syntax_viewer`. The old `.venv` was removed.
- **Item 3:** new `readers/tokens.py` with:
  - `Tok`
  - `Source` (line lookup, `span()`, positioned `error()`)
  - `TokenParser` (bounded `tok`/`peek`/`take`, `at(*punct)`, `at_kind(kind, *texts)`, `expect()` with uniform "found end of file/line" messages)

  All five readers and `CLexer` now use it; duplicated `Tok` classes and line tables are gone. Behaviour unchanged: 142 tests pass, lint clean, 0 fuzz crashes.
- **Makefile:** targets `help`, `venv`, `run FILE=…`, `dump`, `demo-*` (one per fixture), `test`, `fuzz N=…`, `lint`, `check`, `screenshots` (offscreen PNGs in `build/screenshots` via `tools/screenshots.py`), `clean`, and `distclean`. Verified on the VM from a fresh venv.

### Entry 16 — Git repository
**User:** The project is not yet in a GitHub repo; there is an empty project tree in `../tmp/syntax-viewer`. Make this project a git repo based on it.

**Assistant:** `../tmp/syntax-viewer` is a clone of `git@github.com:maarten-boot/syntax-viewer.git` with one commit ("Initial commit": LICENSE MIT, README.md, GitHub's Python .gitignore). Steps taken:
- Copied its `.git`, `LICENSE`, and `README.md` into this project. `../tmp` was left untouched.
- Used its `.gitignore` plus `.venv-*/` for the per-host virtualenvs.
- Added `tests/fixtures/SOURCES.md` with the provenance and license of each fixture. `c99.y` (gist) states no license, which matters if the repo is public.

**User:** commit on main, no push. Committed as one import commit on `main`.
