# Test Cases — syntax-viewer

_Last updated: 2026-10-24_

Each test case traces to a Spec requirement. Fixtures go in `tests/fixtures/`. Automated tests use pytest. ✅ = passing (automated, or "manual ✅" when checked by the user). GUI cases are manual until a GUI test harness exists.

| TC | Spec | Description | Input | Expected | Auto? |
|----|------|-------------|-------|----------|-------|
| TC-01 | FR-1 | Open a file from the command line | `syntax-viewer tests/fixtures/json-w3c.ebnf` | Window opens with calc symbols listed | yes ✅ (offscreen; via `open()`) |
| TC-02 | FR-1 | Open via file dialog | `make demo-json`, then File > Open > `tests/fixtures/kukel.lark` | Symbols listed | manual ✅ (user, 2026-10-24) |
| TC-03 | FR-2 | Detect by extension | `.lark`, `.ebnf` | Lark / EBNF reader chosen | yes ✅ (both) |
| TC-04 | FR-2 | Disambiguate `.y` | `calc-bison.y`, `c99.y` vs `sqlite-parse.y` | Bison reader vs Lemon reader | yes ✅ |
| TC-05 | FR-2 | Manual format override | Force Lemon on `.txt` file | Lemon reader used | yes ✅ |
| TC-06 | FR-3 | Yacc/Bison: basic rules | `expr : expr '+' term \| term ;` | NT `expr` with 2 alternatives; `'+'` terminal; `term` NT ref | yes ✅ |
| TC-07 | FR-3 | Yacc/Bison: actions and code skipped | Rules with `{ … { nested } "}" /* } */ }`, `%{ %}`, epilogue after `%%` | Only rule structure extracted; no stray symbols | yes ✅ |
| TC-08 | FR-3 | Yacc/Bison: `%token` and empty alternative | `%token NUM` / `opt : /* empty */ \| X ;` | `NUM` is a T; `opt` has an empty alternative | yes ✅ |
| TC-09 | FR-3 | Lemon rules | `expr(A) ::= expr(B) PLUS term(C). { A = B + C; }` | NT `expr` → `expr PLUS term`; aliases and action dropped | yes ✅ |
| TC-10 | FR-3 | Lark rules and terminals | `start: expr+` / `NUMBER: /\d+/` / `%import common.WS` | `start` NT; `NUMBER` T with regex definition; import handled | yes ✅ |
| TC-11 | FR-3, NFR-2 | Malformed input (dummy + ISO: missing `;`, unbalanced `(`, unterminated string/comment) | Unterminated rule / unbalanced brace | Error message with file:line; no crash | yes ✅ |
| TC-12 | FR-4 | Plug-in registration (direct and via entry points) | Register a dummy reader | Registry selects it for its extension; no core changes | yes ✅ |
| TC-13 | FR-5 | Same grammar, different formats | Inline calc grammar in all five formats | Same rule shape (alternatives and item kinds) | yes ✅ |
| TC-14 | FR-5 | EBNF operators in model and render | `a ::= b? c* (d \| e)+` | Opt, Star, Plus(Alt) nodes; renders `b? c* ( d \| e )+` | yes ✅ |
| TC-15 | FR-6 | Symbol list contents | calc grammar | All NTs and Ts listed, distinct styling, scrollable | manual ✅ (user, 2026-10-24) |
| TC-16 | FR-6 | Undefined symbol marked | Rule referencing `foo` that is never defined | `foo` shown with an "undefined" marker | yes ✅ (model) + manual |
| TC-17 | FR-7 | Show definition | Click `expr` | Right pane shows all alternatives of `expr` | yes ✅ (page) |
| TC-18 | FR-8 | Follow an NT link | Click `term` in the `expr` definition | Left list selects and scrolls to `term`; right shows `term` | yes ✅ (offscreen) |
| TC-19 | FR-8 | Follow a T link | Click `NUMBER` | Left selects `NUMBER`; right shows its definition (FR-10) | yes ✅ (offscreen) |
| TC-20 | FR-9 | Filter narrows list | Type `exp` | Only symbols containing `exp` remain | yes ✅ |
| TC-21 | FR-9 | Clear filter | Clear the box | Full list restored; selection kept | yes ✅ |
| TC-22 | FR-9 | Link to filtered-out symbol | Filter `exp`, click `term` | Filter cleared; `term` selected and scrolled into view; right pane shows `term` | yes ✅ (controller + offscreen) |
| TC-23 | FR-10 | Terminal without definition | Select `'+'` (Yacc) | Shows "terminal (no definition)" plus a "used by" list | yes ✅ (page) |
| TC-24 | NFR-1 | Headless dump | `syntax-viewer --dump tests/fixtures/kukel.ebnf` | Prints rules (starting `start ::= program`) and comments; no GUI imported | yes ✅ |
| TC-25 | NFR-3 | Large grammar performance | Generated 2000-rule ISO grammar (real-world grammar still to add) | Load < 1 s (measured 0.08 s); GUI open + filter + clear on 1,000 rules < 1 s | yes ✅ |
| TC-26 | FR-3 | EBNF W3C | `expr ::= term ('+' term)*` | NT `expr`; Star over Seq (no Group node) | yes ✅ |
| TC-27 | FR-3 | EBNF ISO 14977 | `expr = term , { "+" , term } ;` / `opt = [ x ] ;` | `{}` → Star, `[]` → Opt; `,` → Seq | yes ✅ |
| TC-28 | FR-11 | Toggle rendering | Select `expr`, toggle to original, click link `term` | Original text shown with links; toggle stays on "original" for `term` | yes ✅ (offscreen) |
| TC-29 | FR-11 | Source span accuracy | Each fixture format | The rule's source slice equals the expected text (actions stripped in the original view) | yes ✅ (all five formats) |
| TC-30 | FR-12 | Used-by for NT | calc: `term` used in `expr` | `used_by["term"] == {"expr"}` | yes ✅ |
| TC-31 | FR-12 | Used-by for T and self-reference | `'+'` used in `expr`; `expr` references itself | `'+'` → {expr}; `expr` used_by includes `expr` | yes ✅ |
| TC-32 | FR-12 | Unused symbol | `%token UNUSED` never referenced | used_by empty → shows "(unused)" | yes ✅ |
| TC-33 | FR-13 | Back/forward | Visit a → b → c, back, back, forward | Current: b, a, b | yes (History) ✅ |
| TC-34 | FR-13 | New navigation truncates forward | a → b → c, back, visit d | Forward empty; back goes to b | yes (History) ✅ |
| TC-35 | FR-13 | Re-selecting current is a no-op | a → a | History length 1 | yes (History) ✅ |
| TC-36 | FR-13 | Clear history | a → b → c, back, clear | Current b; can't go back or forward | yes (History) ✅ |
| TC-37 | FR-13 | Button state and shortcuts; reset on open | Start; Alt+Left; open new file | Buttons disabled at the ends; shortcuts work; history reset | yes ✅ (offscreen; shortcuts checked as bindings) |
| TC-38 | FR-3 | ISO reader on kukel.ebnf | `tests/fixtures/kukel.ebnf` | Loads without error; 89 rules; nested header comment skipped; `-` exceptions parsed | yes ✅ |
| TC-39 | FR-3 | ISO reader on BBCBASIC.ebnf | `tests/fixtures/BBCBASIC.ebnf` | Loads; hyphenated names; juxtaposition concatenation; `"A" .. "Z"` parsed as Range; `? … ?` as Special | yes ✅ |
| TC-40 | FR-3 | Lark reader on kukel.lark | `tests/fixtures/kukel.lark` | Loads; `?statement` named `statement`; `-> alias` doesn't create symbols; `%ignore` terminals present | yes ✅ |
| TC-41 | FR-2 | `.ebnf` dialect sniff | kukel.ebnf / a W3C `::=` file | ISO / W3C reader chosen | yes ✅ |
| TC-42 | FR-14 | Detect convention | kukel.ebnf | Detection says yes; candidates = the 25 upper-case rules | yes ✅ |
| TC-43 | FR-14 | No false positive | BBCBASIC.ebnf (all lower-case) | Detection says no | yes ✅ |
| TC-44 | FR-14 | Apply convention, plus CLI `auto`/`no` and no-op for native-terminal formats | kukel.ebnf with `yes` | `Identifier` kind = terminal, definition kept, used_by unchanged | yes ✅ |
| TC-45 | FR-14 | GUI prompt and memory | Open kukel.ebnf twice | Asked once; second open uses the remembered answer; menu can change it | yes ✅ (offscreen, injected prompt) |
| TC-46 | FR-15 | Trailing comment | kukel `global_variable` | Comment "A global without an initializer is nil…" attached as trailing | yes ✅ |
| TC-47 | FR-15 | Inner comment | BBCBASIC `type-suffix = "%" (* 32-bit integer *) …` | Attached as inner | yes ✅ |
| TC-48 | FR-15 | Section comment not attached | Header comment separated by blank lines | Not attached to any rule | yes ✅ |
| TC-49 | FR-15 | Leading comment | `(* doc *)` directly above `a = b ;` | Attached as leading to `a` | yes ✅ |
| TC-50 | NFR-2 | Pathological nesting | `a = ((((…5000…b…)))) ;` | Exit 1 with "nested too deeply"; no traceback | yes ✅ |
| TC-51 | FR-3 | Lark reader agrees with the `lark` library | kukel.lark | Same rule names (ignoring `__` helpers); our terminals ⊆ lark's | yes ✅ |
| TC-52 | FR-3 | Lark features and errors | prefixes, alias, `~ 2..3`, imports, `%override`/`%extend`, multi-line parens; malformed lines and templates | Correct model; errors with line numbers | yes ✅ |
| TC-53 | FR-3 | W3C on json-w3c.ebnf | `tests/fixtures/json-w3c.ebnf` | 15 rules; start `json`; `[ VC: … ]` attached to `member`; char classes as terminals | yes ✅ |
| TC-54 | FR-6 | List order and scroll | kukel.ebnf; link to `Identifier` | Named terminals before literals; selected item visible in the list viewport | yes ✅ (offscreen) |
| TC-55 | FR-2 | GUI reload as another format | json-w3c.ebnf → Reload as `ebnf-iso` | Error shown; previous grammar kept | yes ✅ (offscreen) |
| TC-56 | FR-3 | Yacc on c99.y | `tests/fixtures/c99.y` | 68 rules; start `translation_unit`; nothing undefined | yes ✅ |
| TC-57 | FR-3 | Lemon on sqlite-parse.y | `tests/fixtures/sqlite-parse.y` | 134 NTs / 416 productions; `%if` lines skipped; `%token_class`, `%fallback`, `%wildcard`, `%type` in declarations; nothing undefined | yes ✅ |
| TC-58 | FR-11 | Actions stripped in original view | calc-bison `exp`, sqlite `explain` | No action code; no blank or trailing-space lines | yes ✅ |
| TC-59 | FR-10 | Rule-less non-terminal wording | sqlite `part_opt`; Lark `%import … -> x` | "declared, but has no rules" / "rule defined in another grammar" | yes ✅ |
| TC-60 | NFR-2 | Truncated real grammars never crash | Every prefix of six fixtures; `%%\na [` | Parses or raises GrammarError, nothing else (plus `tests/fuzz_readers.py` for mutation fuzzing) | yes ✅ |
| TC-61 | NFR-1 | Runs on the user's host from the shared tree | `make venv && make demo-sqlite` on a desktop host | Window opens; no "required file not found"; the VM's venv is untouched | manual ✅ (user, 2026-10-24) |
