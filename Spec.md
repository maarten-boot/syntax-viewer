# Spec — syntax-viewer

_Status: draft v0.13 · Last updated: 2026-10-24_

## 1. Purpose
A small desktop application for browsing grammars. It loads grammar files in several notations, extracts their rules into one common model, and lets the user navigate between symbols through a symbol list and hyperlinked rule definitions.

## 2. Scope
### In scope
- Reading grammar files: Lark, EBNF, Lemon, Yacc, Bison.
- Extracting rules only. Semantic actions, C code blocks, and precedence/associativity details are not interpreted.
- Read-only browsing: symbol list, rule view, link navigation, filtering.
- A format plug-in mechanism so more formats can be added later.

### Out of scope (for now)
- Editing or saving grammars.
- Validating grammars or analysing them (LL/LR conflicts, FIRST/FOLLOW sets).
- Converting between formats.

## 3. Glossary
- **Non-terminal (NT):** a symbol defined by at least one rule in the grammar.
- **Terminal (T):** a token. Depending on the format, this is a declared token (`%token`), an uppercase Lark terminal, a quoted literal, a regex, a character range (`"a" .. "z"`), a special sequence (`? … ?`), or a rule shown as lexical by the uppercase convention (FR-14). Literals are keyed by their text as written, so `"a"` and `'a'` are distinct symbols.
- **Undefined symbol:** referenced in a rule but neither defined nor declared.
- **Template:** a Lark rule with parameters (`name{a, b}: …`), used as `name{X, Y}`. Its parameters are placeholders, not symbols.

## 4. Functional requirements
| ID | Requirement | Source | Tests |
|----|-------------|--------|-------|
| FR-1 | The user can open a grammar file (file dialog and command-line argument). | E2 | TC-01, TC-02 |
| FR-2 | The format is chosen by file extension. If that is ambiguous (e.g. `.y` could be Yacc/Bison or Lemon), the app sniffs the content. The user can override the detected format: `--format` on the command line, **File › Reload as format** in the GUI. A failed reload keeps the previous grammar. | E2 | TC-03, TC-04, TC-05, TC-41, TC-55 |
| FR-3 | Supported input formats and reader names (used by `--format`): **Lark** (`lark`), **EBNF W3C** (`ebnf-w3c`, `name ::= expr`), **EBNF ISO 14977** (`ebnf-iso`, `name = a , b \| c ;`), **Lemon** (`lemon`), **Yacc/Bison** (`yacc`). Only the rule structure is extracted. Actions `{…}`, prologue/epilogue code, and `%{ %}` blocks are skipped. **ISO** must accept: nested `(* *)` comments; `,` **or** juxtaposition as concatenation; hyphenated names; `[ ]`/`(/ /)`, `{ }`/`(: :)`, `( )`; `\|`, `/`, `!` as alternative separators; `;` or `.` as terminator; exception `a - b`; repetition `n * x`; special sequences `? … ?`; informal ranges `"a" .. "z"`. **Lark** must accept: `?`/`!` rule prefixes, `-> alias` (alias ignored for structure, not a symbol), multi-line `\|` continuation, `~ n[..m]`, `"a".."z"`, `"x"i`, `/re/flags`, terminal priorities `NAME.n` (shown in the declaration), `%import` (all forms), `%ignore` (shown in the declaration), `%declare`, `%override`, `%extend`. Lark rule **templates** are supported (E21): a definition `name{p1, p2}: …` gets parameters, which are local placeholders (not symbols, not links) shown as `name{p1, p2} ::= …`. A use `name{arg, …}` references the template and each argument (used-by and links). **Yacc/Bison** must accept: `%{ %}`, any directive with `{…}`/string/name arguments (skipped), `%token`/`%nterm`/`%type`/`%left`/`%right`/`%nonassoc`/`%precedence` with `<type>` tags, token numbers and string aliases (an alias is its own terminal, "alias of X"), `%start`, rules `lhs[name]: … | … ;` with the `;` optional before the next rule, mid-rule and final actions, `<type>` tags, `[name]` references, `%prec`, `%empty`, `%dprec`, `%merge`, and the predefined `error` token; the epilogue after the second `%%` is ignored. Undeclared names used in rules are undefined. **Lemon** must accept: `lhs(A) ::= X(B) y|Z . [PREC] {action}`, `%token`/`%left`/`%right`/`%nonassoc`/`%fallback`/`%wildcard`/`%token_class` lists ending in `.`, `%type`/`%destructor NAME {…}`, `%start_symbol`, single-argument directives (`%include {…}`, `%name x`, …), and `%if*`/`%else`/`%endif` lines (ignored: all rules shown). Upper-case names are terminals without declaration. `.y` is Yacc/Bison if it contains a `%%` line, otherwise Lemon if it has `name ::=` rules. **W3C** must accept: rules without terminator (ended by the next `name ::=`), `[...]`/`[^...]` character classes (terminals, not optional), `#xN` character codes, `? * +`, `A - B`, `( )`, `/* */` comments, XML-spec rule numbers `[n]` (skipped), and `[ WFC: … ]`/`[ VC: … ]` notes (treated as comments). Extensions: `.lark`, `.ebnf` (ISO or W3C by content), `.iso`, `.w3c`, `.y` (Yacc or Lemon by content), `.yy`/`.ypp`/`.bison`, `.lemon`; others need `--format`. | E2, E3, E6, E8, E10, E11, E13, E21 | TC-06…TC-11, TC-26, TC-27, TC-38…TC-40, TC-51…TC-53, TC-56, TC-57, TC-62, TC-63 |
| FR-4 | Format readers are plug-ins implementing one common interface (`Reader.detect`, `Reader.read`). Built-in readers register on import. Third-party readers register through the `syntax_viewer.readers` entry-point group. Adding a format needs no changes to the UI or core. `--list-formats` lists them. | E2, E5 | TC-12 |
| FR-5 | All formats map to one common grammar model: **symbols** (name, kind NT/T/undefined, source location, terminal definition and declaration text if any) and **rules** (LHS, body expression, source span, attached comments, elided action spans, template parameters). Several rules may share an LHS; they are merged for display. Body expressions are built from Seq, Alt, Opt, Star, Plus, Except, Repeat, Range, Special, SymRef, Literal, Regex, Empty, Param (template parameter, not a symbol), and Call (template use). Grouping is implicit in the tree; the renderer adds parentheses from precedence. | E2, E8, E21 | TC-13, TC-14, TC-62 |
| FR-6 | Left pane: a scrollable list of all symbols. NTs and Ts are visually distinct, e.g. by icon, colour, or grouping. Undefined symbols are marked. Order: non-terminals (start symbol first), then terminals (named terminals before literals, regexes, ranges, and special sequences), then undefined; alphabetical (case-insensitive) within each group. Colours: non-terminal blue and bold, terminal teal, undefined red with ⚠. The same colours are used for links in the right pane. The start symbol is the LHS of the first rule. | E2 | TC-15, TC-16, TC-54 |
| FR-7 | Selecting an NT in the left list shows its full definition (all alternatives) in the right pane. | E2 | TC-17 |
| FR-8 | In the right pane every NT and T occurrence is a link. Activating a link selects that symbol in the left list, scrolls it into view, and shows its definition on the right. | E2 | TC-18, TC-19 |
| FR-9 | A search filter temporarily reduces the left list to matching symbols. Clearing the filter restores the full list. The filter box sits above the left list. If the user follows a link, or goes back/forward, to a symbol hidden by the active filter, the text filter is cleared; if the symbol's kind is unchecked (FR-16), that kind is checked again. The symbol is then selected. Matching is case-insensitive substring. Ctrl+F focuses the filter. | E2, E3 | TC-20, TC-21, TC-22, TC-66 |
| FR-10 | Selecting a terminal shows its definition where the format has one (Lark terminal pattern, `%token` declaration, including type/precedence if declared). Otherwise it shows "terminal (no definition)". A non-terminal without rules shows "rule defined in another grammar" (Lark `%import`) or "declared, but has no rules" (e.g. a Lemon `%type` with no rules). It always also shows "used by" (FR-12). | E2, E4 | TC-23, TC-59 |
| FR-11 | The right pane can toggle between (a) **normalised** EBNF-like notation, uniform across formats with one alternative per line, and (b) the **original source text** of the rule with actions stripped. Symbols are links in both views. The toggle state persists while navigating. The model therefore stores each rule's source span, plus the spans of actions inside it (Yacc) so the original view can strip them. Lines emptied by stripping and trailing spaces are removed. | E3 | TC-28, TC-29, TC-58 |
| FR-12 | **Used by:** for every symbol (NT or T), the right pane lists the rules (non-terminals, and lexical rules under FR-14) that reference it (a template use references the template and each argument), sorted by name, each a link. A symbol used by nothing shows "(unused)". For the start symbol this is normally empty. | E4 | TC-30, TC-31, TC-32 |
| FR-13 | **Navigation history:** every navigation (list selection or link) is recorded. **Back** and **Forward** (toolbar buttons plus Alt+Left / Alt+Right) move through the history with browser semantics: navigating after going back discards the forward entries. Re-selecting the current symbol adds no entry. **Clear history** empties back and forward but keeps the current symbol. Buttons are disabled when they do nothing. Opening a new file resets the history. | E4 | TC-33…TC-37 |
| FR-14 | **Uppercase-lexical convention (per file):** some grammars (e.g. kukel.ebnf) treat rules whose name starts with an upper-case letter as lexical (tokens). On load the app detects this pattern: the format has no native terminal syntax (EBNF), there are both upper- and lower-case rule names, and upper-case rules reference no lower-case rules. If detected, the GUI **asks** whether to treat those rules as terminals. The answer is remembered per file path (QSettings) and can be changed later with **View › Upper-case rules are terminals**, which applies to all upper-case rules. When enabled, such rules are listed and styled as terminals but keep their definition and "used by". Headless: `--uppercase-terminals yes\|no\|auto` (auto = use the detection result). Not offered for formats with native terminal syntax (Lark, Yacc/Bison, Lemon), where terminals are already known; the CLI ignores `yes` with a warning there. | E7 | TC-42…TC-45 |
| FR-15 | **Rule comments:** comments in the source are attached to rules and shown in the definition view (both normalised and original). Attachment: (a) *leading*: a comment block directly before the rule with no blank line in between; (b) *inner*: comments inside the rule body; (c) *trailing*: comments after the rule's end, before the next blank line or rule; consecutive trailing comments chain. Consecutive line comments (`//`, `#`) on adjacent lines form one comment block. If a comment could be both trailing (of the previous rule) and leading (of the next), it is trailing when it is indented or on the same line as the previous rule's end, otherwise leading. Other comments (section headers, separated by blank lines) are not attached. Applies to every format: `(* *)` (ISO), `/* */` (W3C, Yacc/Bison, Lemon), `//` (Lark, Yacc/Bison, Lemon). Comments inside actions are code and are not attached. | E7 | TC-46…TC-49 |
| FR-16 | **Kind filter:** three checkboxes below the filter box (Non-terminals, Terminals, Undefined; all on by default) restrict the left list to the checked kinds, combined with the text filter (FR-9). The status bar count reflects both. The selection persists while opening other files in the same session. | E21 | TC-64, TC-66, TC-67 |
| FR-17 | **Regex filter:** a `.*` toggle next to the filter box switches the text filter from substring to regular-expression matching (Python `re`, case-insensitive search). While a pattern is invalid, the filter box is marked (red border, tooltip with the error) and the list keeps using the last valid pattern. The mode persists while opening other files in the same session. | E21 | TC-65, TC-67 |

## 5. Non-functional requirements
| ID | Requirement | Source | Tests |
|----|-------------|--------|-------|
| NFR-1 | The parser core runs and is testable without the GUI (headless). The app runs from a checkout shared between hosts (per-host virtualenv, E15). | design, E15 | TC-24, TC-61 |
| NFR-2 | A malformed file produces a clear error with file and line. It never crashes the app; pathological input (e.g. extremely deep nesting) is reported as an error too. Every reader is mutation-fuzzed (`tests/fuzz_readers.py`) to raise only `GrammarError`. | design, X1 | TC-11, TC-50, TC-60 |
| NFR-3 | Grammars of about 1,000 rules (e.g. a full C or SQL grammar) load and filter without noticeable delay (<1 s). | design | TC-25 |

## 6. Open questions
- ~~Q1~~ **Resolved (E3):** Python 3.11+ with PySide6; pytest.
- ~~Q2~~ **Resolved (E3):** Filter above the left list. A link to a filtered-out symbol clears the filter.
- ~~Q3~~ **Resolved (E3):** Both views, toggleable (FR-11).
- ~~Q4~~ **Resolved (E4):** Terminal shows its definition plus "used by" (FR-10, FR-12).
- ~~Q5~~ **Resolved (E3):** W3C and ISO 14977.
- ~~Q7~~ **Resolved (E7):** per file, ask on load when detected (FR-14).
- ~~Q8~~ **Resolved (E7):** show attached comments (FR-15).
- ~~Q6~~ **Resolved (E4):** Back/forward plus clear history (FR-13) and "used by" (FR-12). ~~Deferred~~ filter by kind and regex filter: implemented in E21 (FR-16, FR-17).

## 7. Change history
- 2026-10-24 — Skeleton created.
- 2026-10-24 — v0.1: initial requirements from the scenario (E2).
- 2026-10-24 — v0.2: Q1, Q2, Q3, Q5 resolved. FR-2, FR-3, FR-9 updated; FR-11 added (E3).
- 2026-10-24 — v0.3: Q4, Q6 resolved. FR-10 updated; FR-12 (used by) and FR-13 (history) added (E4).
- 2026-10-24 — v0.4: real fixtures (E6). FR-3 lists the required ISO/Lark features; FR-5 model nodes updated (Except, Range, Special; no Group). Q7, Q8 added.
- 2026-10-24 — v0.5: Q7, Q8 resolved. FR-14 (uppercase-lexical convention) and FR-15 (rule comments) added (E7).
- 2026-10-24 — v0.6: crosscheck X1. FR-3 rewritten (it had been garbled by the v0.4 edit) and reader names added. FR-4 now mentions entry points; FR-5 lists the actual model fields; FR-6 gains ordering; FR-12 wording; FR-14 native-terminal formats; FR-15 tie-break rule; NFR-2 covers deep nesting; glossary extended.
- 2026-10-24 — v0.7: Lark details in FR-3 (E10); line-comment merging in FR-15; templates deferred.
- 2026-10-24 — v0.8: W3C details and the extension list in FR-3 (E11).
- 2026-10-24 — v0.9: GUI details (E12). FR-2 GUI override; FR-6 order and colours; FR-9 back/forward reveal plus Ctrl+F; FR-14 menu.
- 2026-10-24 — v0.10: Yacc/Bison and Lemon details in FR-3; FR-10 rule-less non-terminals; FR-11 action elision (E13).
- 2026-10-24 — v0.11: crosscheck X2. Test columns completed (TC-41→FR-2, TC-51…TC-60); FR-14 lists all native-terminal formats; FR-15 comment syntaxes per format; NFR-2 fuzzing.
- 2026-10-24 — v0.12: FR-16 (kind filter), FR-17 (regex filter), FR-9 kind reveal, FR-3 Lark templates (E21).
- 2026-10-25 — v0.13: crosscheck X3. FR-5 lists Param/Call and the elided/params rule fields; FR-12 template uses; NFR-1 covers TC-61; glossary adds Template.
