# Drive Eligibility and Registration System

A local command-line application for evaluating placement-drive eligibility from company-defined expressions and preventing students from registering for overlapping drives.

## Problem statement and objectives

Companies can set eligibility rules over student CGPA, arrears, and department. The system parses those rules with a custom recursive-descent parser, evaluates them against student records, reports failed conditions, persists records as JSON, and rejects registrations that are ineligible, duplicated, or in conflict with another active drive.

## Features

- Lexer, recursive-descent parser, AST, and safe evaluator; no `eval()` or `exec()`.
- Boolean `AND`, `OR`, and `NOT`, comparisons, parentheses, numbers, strings, and booleans.
- All failed AND conditions are explained; OR failures are reported only when every alternative fails.
- Persistent student, company, drive, and registration JSON files.
- Half-open drive interval clash detection, so back-to-back drives are allowed.
- Interactive CLI, expression validation, demonstration data reset, and a one-million-evaluation test.
- Standard library only; no external services or packages are needed.

## Technologies

Python 3.10+ (tested in this workspace with Python 3.14.6), `dataclasses`, `json`, `unittest`, and other Python standard-library modules.

## Project structure

```text
main.py              CLI
models.py            Student, Company, Drive, Registration
lexer.py             Tokenizer
parser.py            Recursive-descent parser and AST
evaluator.py         Type-checked AST evaluation
eligibility.py       Company eligibility and explanations
scheduler.py         Date/time validation and overlap checks
registration.py      Eligibility and schedule enforcement
storage.py            Atomic JSON persistence
reports.py            Batch eligibility/report helpers
sample_data.py        Explicitly loadable demonstration records
data/                 Created on first launch; JSON record files
tests/                unittest coverage
```

## Setup and commands

No packages need installing. If desired, the requirements file can be installed with:

```console
python -m pip install -r requirements.txt
```

Run from the project directory:

```console
python main.py
```

Run the automated tests:

```console
python -m unittest discover -v
```

The app creates `data/students.json`, `data/companies.json`, `data/drives.json`, and `data/registrations.json` as empty arrays when they are missing. It does not seed or replace existing data automatically. To load or reset the demo records, select menu option 13 and type `RESET` at the confirmation prompt. All successful additions and registrations are saved immediately.

## Sample eligibility

The explicitly loaded TechNova sample rule is:

```text
CGPA >= 7.0 AND arrears == 0 AND department == "CSE"
```

The sample students are `S1 8.2 0 CSE`, `S2 7.1 1 CSE`, and `S3 6.4 0 IT`. The records are evaluated, not hardcoded into the output:

```text
S1 ELIGIBLE
S2 NOT ELIGIBLE
- Arrears are 1; required value is 0.
S3 NOT ELIGIBLE
- CGPA is 6.4; minimum required is 7.0.
- Department is IT; required department is CSE.
```

The demo data also has OR and NOT rules and overlapping/consecutive drive slots. To demonstrate registration, register S1 for D1, then try D2 (a clash), then D1 again (a duplicate). D3 begins exactly when D1 ends and is accepted if S1 is eligible for it. D1/D2 are respectively 10:00–12:00 and 11:00–13:00 on the same date.

## Expression language

Names are case-insensitive for keywords and student attributes. Supported attributes are `CGPA`, `arrears`, `department`, and `student_id`.

```ebnf
expression      := or_expression
or_expression   := and_expression ("OR" and_expression)*
and_expression  := not_expression ("AND" not_expression)*
not_expression  := "NOT" not_expression
                 | "(" expression ")"
                 | comparison
comparison      := operand comparison_operator operand
operand         := IDENTIFIER | NUMBER | STRING | BOOLEAN
comparison_operator := ">=" | "<=" | ">" | "<" | "==" | "!="
```

Precedence from highest to lowest is parentheses, `NOT`, comparisons, `AND`, then `OR`. Strings may use single or double quotes; supported escapes include newline, carriage return, tab, quote, and backslash. Numeric comparisons accept integers and decimals. Comparing incompatible types or referring to an unknown field produces an explicit evaluation error.

## Parsing versus evaluation

Parsing happens once for a company's rule: the lexer creates tokens and the recursive-descent parser builds an AST that encodes precedence and grouping. Evaluation is a separate operation: the evaluator walks that AST for a particular student and returns a boolean plus relevant failed-condition explanations. `EligibilityService` caches ASTs by expression so batch checks do not reparse the rule per student.

## Eligibility algorithm

For each AST node, comparison nodes resolve fields and compare type-compatible values; `AND` evaluates both children and collects failures from both; `OR` succeeds if either child succeeds and only reports branch failures if both fail; `NOT` inverts its child's truth value. A student is eligible exactly when the root expression evaluates to true. Every failed comparison in an unsuccessful AND/OR formula is returned.

## Drive clash and registration algorithm

Drive dates/times are validated before comparison. On the same date, two slots overlap exactly when `start_1 < end_2 AND start_2 < end_1`; intervals are half-open, so equal end/start endpoints do not clash. Registration first checks student and drive existence, eligibility, an existing registration for the requested drive, then the student's active registrations for overlaps. It saves a registration only if every check passes.

## Complexity

Let `S` be students, `C` companies, `R` AST nodes per rule, `D` drives, and `N` saved registrations. A batch eligibility run takes `O(S × C × R)` time and caches one parse per distinct company expression. Rule storage takes `O(C × R)`. Registration conflict checking reads the local JSON record lists and scans active registrations, so it takes `O(S + C + D + N)` to load records and `O(N)` for the conflict scan. Clash reporting compares registrations per student and is quadratic in that student's registrations. For the required 10,000-by-100 workload, the test evaluates one million student-company pairs; run the test command to measure execution on your machine.

Measured in the implementation workspace: 1,000,000 eligibility evaluations completed in 29.938 seconds (33,402 evaluations/second) using Python 3.14.6 on Windows 11. This is a local benchmark result, not a performance guarantee; hardware and system load affect timings.

## Limitations and future improvements

The CLI is single-user and local-file based; concurrent writers are not coordinated. Drive times are same-day only (overnight drives are rejected). There is no authentication, web UI, CSV import/export, or cancellation workflow. A database, indexed schedule store, and audit history would be appropriate future extensions for multi-user deployment.
