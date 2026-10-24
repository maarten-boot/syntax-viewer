/* Calculator in Bison syntax, written for syntax-viewer tests.
   Exercises the parts a rule extractor must skip. */
%{
#include <stdio.h>
int yylex(void);
void yyerror(const char *s) { fprintf(stderr, "%s}\n", s); }  /* a '}' in a string */
%}

%define api.value.type {double}
%define parse.error verbose
%code requires { typedef struct { int a; } loc_t; }

%token <double> NUM "number"
%token PLUS "+" MINUS "-"
%token UNUSED
%nterm <double> exp
%left PLUS MINUS
%left '*' '/'
%precedence NEG
%start input

%%

input:
  %empty
| input line
;

/* One line of input. */
line:
  '\n'
| exp '\n'     { printf ("%.10g\n", $1); }
| error '\n'   { yyerrok; }
;

exp[result]:
  NUM
| exp[l] "+" exp[r]   { $result = $l + $r; }
| exp MINUS exp       { $$ = $1 - $3; /* } in a comment */ }
| exp '*' exp         { $$ = $1 * $3; }
| exp '/' exp         {
                        if ($3 == 0) { yyerror ("division by zero"); $$ = 0; }
                        else $$ = $1 / $3;
                      }
| '-' exp  %prec NEG  { $$ = -$2; }
| '(' exp ')'         { $$ = $2; }
| exp '\'' { char c = '}'; (void)c; } <double>{ $$ = $1; } exp
;                                       // trailing comment
assign: NAME '=' exp   /* missing ';' before the next rule is allowed */
stmt  : assign | exp

%%

int main(void) { return yyparse(); }  /* epilogue: never parsed */
