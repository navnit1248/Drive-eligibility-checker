# Drive Eligibility and Registration

A small Python command-line program that checks placement eligibility, explains failed conditions, and prevents a student from registering for overlapping drives.

## Requirements

- Python 3.10 or newer.
- No third-party packages.

## Run the sample input

Run `python main.py`, then enter or pipe:

```text
7.0 0 CSE IT
3
S1 8.2 0 CSE
S2 7.1 1 CSE
S3 6.4 0 IT
```

The first line is `minimum-CGPA maximum-arrears allowed-department...`. The next line is the student count. Each remaining line is `student-ID CGPA arrears department`.

Output:

```text
S1 ELIGIBLE
S2 NOT ELIGIBLE (arrears)
  - Arrears are 1; required value is 0.
S3 NOT ELIGIBLE (cgpa)
  - CGPA is 6.4; minimum required is 7.0.
```

Allowed departments are alternatives; CGPA, arrears, and department requirements must all pass. The program builds and parses an expression from the company rule line. It parses the rule once before reading the student records.

To use a custom expression instead, pass `--rule` and start standard input with the student count:

```powershell
python main.py --rule 'CGPA >= 7 AND arrears == 0 AND department == "CSE"'
```

Expressions support `AND`, `OR`, `NOT`, comparisons (`>=`, `<=`, `>`, `<`, `==`, `!=`), parentheses, numeric/string/boolean literals, and the student fields `CGPA`, `arrears`, `department`, and `student_id`. Invalid syntax and invalid field/type comparisons are reported as errors. An unsuccessful rule prints each relevant failing condition; an OR branch that passes does not create a false failure.

## Registration and drive clashes

Run `python main.py --demo` to see every failing condition, AND/OR/NOT rules, clash detection and registration in action, and `python main.py --benchmark` for the 100,000 students × 100 companies run (about 1 minute).

Start the interactive local-record menu with `python main.py --interactive`. Add students and company rules, schedule drives with a date and start/end times, then use **Register student for a drive**. A registration is saved only if the student is eligible, is not already registered for that drive, and has no active overlapping registration. Drive intervals are half-open: one drive ending at 12:00 and another starting at 12:00 do not conflict.

The interactive mode stores records in `data/students.json`, `companies.json`, `drives.json`, and `registrations.json`; missing files are created as empty lists. The menu's confirmed demo-data reset is optional.

## Parser and grammar

The lexer turns the expression into tokens. A recursive-descent parser constructs an AST using this grammar:

```ebnf
expression      := or_expression
or_expression   := and_expression ("OR" and_expression)*
and_expression  := not_expression ("AND" not_expression)*
not_expression  := "NOT" not_expression | "(" expression ")" | comparison
comparison      := operand comparison_operator operand
operand         := IDENTIFIER | NUMBER | STRING | BOOLEAN
comparison_operator := ">=" | "<=" | ">" | "<" | "==" | "!="
```

Precedence, highest first: parentheses, `NOT`, comparisons, `AND`, `OR`. Parsing creates the reusable AST; evaluation walks it with an individual student's values. For `AND`, both sides are checked to collect every failure. `OR` passes if either side passes; failure details are returned only when both alternatives fail.

For two drives on the same date, there is a clash exactly when `start1 < end2 AND start2 < end1`. Eligibility evaluation takes `O(S × C × R)` time for `S` students, `C` companies, and `R` expression nodes; each rule is parsed once and reused. Registration checks the student's active registrations for conflicts.

## Scale and tests

The evaluator was run against 100,000 students and 100 company rules (10,000,000 evaluations): **37.07 seconds**, approximately **269,729 evaluations/second**, on Python 3.14.6 / Windows 11. Timing varies by machine.

Run all tests, including the 100,000-by-100 workload:

```console
python -m unittest discover -v
```

The tests cover lexing, syntax errors, expression behavior and explanations, registration/clashes, persistence, sample input, and scale. The compact code layout is `rule_engine.py` (lexer, parser, AST, evaluator, and eligibility), `registration.py` (schedule overlap and registration checks), `models.py`, `storage.py`, `reports.py`, `sample_data.py`, and the CLI in `main.py`.
