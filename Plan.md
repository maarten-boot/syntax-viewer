# Plan — syntax-viewer

_Status: draft v0.12 · Last updated: 2026-10-24_

## Approach
Three layers, so parsers can be tested without the GUI (NFR-1):

1. **Model** (`model.py`): `Grammar(format, source, path, start, rules, symbols, used_by, lexical, native_terminals)`, `Symbol(name, kind, definition, declaration, span)`, `Rule(lhs, body, span, comments)`, `Comment(text, span, pos)`, `attach_comments()`, `GrammarError`. Rule bodies are expression trees: `Seq`, `Alt`, `Opt`, `Star`, `Plus`, `SymRef`, `Literal`, `Regex`, `Empty` (implemented). `Except`, `Repeat`, `Range`, and `Special` were added with the ISO reader (implemented). There is no `Group` node; the renderer derives parentheses.
2. **Readers** (`readers/`): one plug-in per format, implementing `Reader.detect(path, text) -> score` and `Reader.read(text) -> Grammar`. A registry picks the reader (FR-2, FR-4). `readers.load()` is the single entry point for the CLI and GUI; it turns `RecursionError` into `GrammarError` (NFR-2).
   - Yacc/Bison and Lemon: a hand-written tokenizer that skips `%{…%}`, `{…}` actions (with nested braces, strings, and comments), and the prologue/epilogue. Then it parses `lhs : alt | alt ;` (Yacc/Bison) or `lhs(A) ::= rhs. {action}` (Lemon).
   - Lark: a **hand-written** reader. Decision X1: the `lark` library's loader discards comments and source positions, which FR-11 and FR-15 need. The reader sets `native_terminals=True` and stores terminal definitions as lexical rules (E10), so terminals get spans, comments, and used-by through the same path as FR-14.
   - Shared `tokens.py` (E15): `Tok`, `Source` (lines, spans, errors), and `TokenParser` (bounded cursor). Every reader's parser subclasses it.
   - Shared `clex.py` tokenizer for the C-embedding formats (E13).
   - EBNF: two readers, W3C (`::=`) and ISO 14977 (`=` … `;`), with a content sniff to choose between them.
   - The model computes a reverse-reference index `used_by: dict[str, set[str]]` once after reading (FR-12).
3. **UI** (implemented, E12):
   - `browser.py`: Qt-free `Browser` controller (grammar, filter, `History`, view mode, reveal-on-navigate).
   - `page.py`: Qt-free HTML builder with `sym:<quoted name>` links.
   - `gui.py`: thin PySide6 `MainWindow` that mirrors `Browser` state into widgets on every `refresh()`. Signals are blocked while syncing. Settings and the FR-14 prompt are injectable for tests.
   - GUI tests run on `QT_QPA_PLATFORM=offscreen`.

Stack (decided in E3): Python 3.11+, PySide6, pytest. Packaging uses `pyproject.toml` with a `syntax-viewer` entry point.

Rendering (FR-11): readers record each rule's source span (offsets plus line). The normalised view is generated from the expression tree. The original view takes the source slice, strips the actions, and wraps symbol tokens in anchors. Both views produce HTML for a `QTextBrowser` with `symbol:<name>` anchors.

## Milestones
| # | Milestone | Covers | Status |
|---|-----------|--------|--------|
| M0 | Decide open questions Q1–Q5 | — | done (E3) |
| M1 | Model (including used-by index), reader interface/registry, headless CLI dump (`syntax-viewer --dump file`) | FR-4, FR-5, FR-12 (model), FR-13 (History class), NFR-1 | **done** (E5) |
| M2 | Yacc/Bison reader (shared `clex.py`) | FR-3 | **done** (E13) |
| M3 | Lemon reader | FR-3 | **done** (E13) |
| M4 | Lark reader | FR-3 | **done** (E10) |
| M5a | EBNF W3C reader | FR-3 | **done** (E11) |
| M5b | EBNF ISO 14977 reader, comment attachment, uppercase convention (model + CLI) | FR-3, FR-14 (model), FR-15 (model) | **done** (E8) |
| M6 | GUI: two-pane layout, symbol list, rule view (with comments), uppercase-lexical prompt and per-file setting | FR-1, FR-6, FR-7, FR-10, FR-14, FR-15 | **done** (E12) |
| M7 | Link navigation, filter, normalised/original toggle, used-by section, history | FR-8, FR-9, FR-11, FR-12, FR-13 | **done** (E12) |
| M8 | Error handling, performance check, polish: README, manual desktop check (TC-02, TC-15), readers refactor, Makefile | NFR-2, NFR-3 | in progress: fuzzing/timing (X2), `readers/tokens.py` refactor and Makefile done (E15); README and desktop check open |

## Tasks
- [x] Resolve Q1–Q3, Q5 (E3)
- [x] Resolve Q4, Q6 (E4)
- [x] Real fixtures: `kukel.ebnf`, `kukel.lark`, `BBCBASIC.ebnf` (E6)
- [x] Fixtures: `calc-bison.y` (hand-made), `c99.y` (gist codebrainz/2933703), `sqlite-parse.y` (public domain), `json-w3c.ebnf`; TC-13 uses inline calc grammars in all five formats
- [x] Resolve Q7, Q8 (E7)
- [x] Model: `Rule.comments` (leading/inner/trailing), `Grammar.lexical_candidates()` and `set_lexical()`, CLI `--uppercase-terminals` (FR-14, FR-15)
- [x] Shared comment-attachment helper (`model.attach_comments`) for readers: readers report comment spans; the helper assigns them to rules by position
- [ ] M1…M8 as above

## Risks / decisions
- `.y` is used by both Yacc/Bison and Lemon. Resolved (E13): a `%%` line means Yacc/Bison, otherwise `name ::=` rules mean Lemon.
- Skipping C actions robustly (nested braces, string/char literals, comments) was the main parsing risk. Mitigated by `clex.py`, the `calc-bison.y` trap fixture, and fuzzing (X2).
- The real ISO files mix comma and juxtaposition concatenation, nest comments, and use `-`, `..`, and `? ?` (E6). M5b is bigger than first thought, so it moves ahead of M2 because real fixtures already exist.
- EBNF scope is pinned to W3C and ISO 14977. `.ebnf` files need a content sniff.
- The original-text view depends on accurate source spans. Every reader must record them (covered by TC-29).

- `lark` is a **dev-only** dependency, used to cross-check rule names (test_lark). The app does not need it.
- Next: README, then the user's desktop check (`make demo-*`) of TC-02, TC-15, and TC-61.
- Decision E15: **one virtualenv per host** (`.venv-<hostname>`), because the tree is shared over NFS between the VM and the user's machine and virtualenvs are not relocatable. All tooling goes through `make`; the app runs as `python -m syntax_viewer`.
- Repository (E16): `git@github.com:maarten-boot/syntax-viewer.git`, branch `main`; the project was imported on top of GitHub's initial commit (MIT LICENSE). Pushing is left to the user. Open item: `c99.y` has no stated license (see `tests/fixtures/SOURCES.md`).
- Layout: `src/syntax_viewer/` (model, render, history, browser, page, gui, cli, `readers/{tokens,clex,iso_ebnf,w3c_ebnf,lark,yacc,lemon}`), `tests/` (pytest, fixtures, `fuzz_readers.py`), `tools/screenshots.py`, `Makefile`.
- Manual check still needed on a real desktop: file dialog (TC-02), visual styling (TC-15), real mouse/keyboard use.

## Crosscheck log
| Date | Trigger | Findings | Actions |
|------|---------|----------|---------|
| 2026-10-24 | **X1**, after M1 + M5b (user request E9) | **Code:** (1) `RecursionError` on deeply nested input escaped as a crash (NFR-2); (2) `--dump` omitted comments for lexical terminals (FR-15); (3) FR-14 detection did not exclude Lark-like formats. **Spec:** FR-3 garbled by an earlier edit; reader names, entry points, model fields, list order, used-by wording, comment tie-break, and glossary were missing or outdated. **Plan:** model signatures outdated; task named `apply_uppercase_terminals` (actually `set_lexical`); Lark-library option unresolved. **Tests:** TC-26 referenced the removed `Group` node; TC-24 ran on the dummy format only; FR-14 CLI flag, FR-15 dump, TC-25, and TC-29 untested. | All fixed. Code: `Grammar.native_terminals`, `readers.load` catches recursion, dump prints comments for any symbol with rules. Spec v0.6, Plan v0.6. Tests added (TC-24 real fixture, TC-25, TC-29 ISO, TC-50, FR-14 CLI); 47 pass. Accepted as-is: a section header directly above a rule attaches as leading (per FR-15, user informed). |
| 2026-10-24 | **X2**, after the GUI (M6/M7) and all readers (M2–M5) (user agreed E13) | **Traceability:** Spec rows did not list TC-51…TC-59; TC-41 filed under FR-3 in Spec but FR-2 in TestCases; TC-50…TC-59 tests not named by TC id. **Code (NFR-2):** mutation fuzzing found `IndexError` in the Yacc reader on input ending inside `[name]` (and `_starts_rule` look-ahead); Lark/Lemon/W3C/ISO had the same unbounded look-ahead pattern; 7 unused imports (ruff). **Spec:** FR-14 named only Lark as native-terminal (Yacc/Bison and Lemon are too); FR-15 listed `#` comments, which no format uses. **Plan:** `.y` sniff rule and C-action risk outdated; M8 scope undefined. **Tests:** FR-4 entry-point loading untested. Per-FR code review found no behavioural mismatch. | All fixed. A bounded `peek()` in every reader; `tests/fuzz_readers.py` (0 crash kinds at 1,500 mutations × 7 fixtures); TC-60 truncation regression test; TC-12 entry-point test; tests renamed `test_tcNN_*`; ruff-clean (F, E9, B). Spec v0.11, Plan v0.11. 142 tests pass. Proposed for M8: shared token-stream base for the readers. |
