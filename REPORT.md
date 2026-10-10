# Final Review Report – Drive Eligibility and Registration

Python 3.14, standard library only. Run everything from the project folder.

## 1. Completion of required features

| Requirement | Where | How to see it |
|---|---|---|
| Student records (ID, CGPA, arrears, department) | `models.py` (`Student`) | sample input |
| Rule line `minCGPA maxArrears dept...` (spaces or commas) | `main.py` `build_company_rule` | `python main.py` |
| Rules in an AND / OR / NOT expression language | `rule_engine.py` | `python main.py --demo`, `--rule` |
| Recursive-descent parser and evaluator | `rule_engine.py` (`Parser`, `Evaluator`) | `python main.py --demo` |
| Print every failing condition, not just the first | `Evaluator._collect_failures` | `python main.py --demo` |
| Same-day drive clash detection (interval check) | `registration.py` `overlaps` | `python main.py --demo` |
| Registration command | `RegistrationService.register`, menu option 10 | `python main.py --interactive` |
| 10^5 students and 100 companies | `main.py --benchmark` | `python main.py --benchmark` |
| README with the grammar | `README.md` | – |

## 2. Correctness and test coverage

`python -m unittest discover -v` runs 22 tests, all passing. They cover: the sample input and output, each comparison operator, AND/OR/NOT precedence and parentheses, parse errors (unterminated string, missing parenthesis, unknown field, type mismatch), all failures reported, OR failures reported only when both branches fail, overlapping / back-to-back / different-day drives, registration accepted / ineligible / duplicate / clashing, JSON storage, empty and comma-separated input, and a 100,000 × 100 run.

## 3. Required output / report format

Input:
```
7.0 0 CSE IT
3
S1 8.2 0 CSE
S2 7.1 1 CSE
S3 6.4 0 IT
```
Output (indented reason lines follow each rejection):
```
S1 ELIGIBLE
S2 NOT ELIGIBLE (arrears)
S3 NOT ELIGIBLE (cgpa)
```
Clash message: `Schedule conflict. Existing drive: Alpha 09:00-12:00, Requested drive: Beta 11:00-14:00`.

## 4. Code quality and memory management

- Small modules with one job each: `rule_engine.py` (lexer, parser, evaluator), `registration.py` (clashes and registration), `models.py`, `storage.py`, `reports.py`, `main.py`.
- Records are frozen dataclasses; errors are specific exceptions (`ParseError`, `EvaluationError`, `RegistrationRejected`) reported as clear messages.
- Batch mode **streams**: it reads one student, evaluates, prints, and discards it, so memory is O(1) in the number of students (plus the rule tree). The rule is parsed once, outside the student loop.
- Parsed rules are cached per company (`EligibilityService._asts`) so a rule is never re-parsed.
- Evaluation short-circuits on the fast path (`_passes`); the slower full failure collection runs only for rejected students.

## 5. Time and space complexity

Let N = students, C = companies, R = size of a rule (tokens).

| Operation | Time | Space |
|---|---|---|
| Parse one rule (recursive descent) | O(R) | O(R) tree |
| Evaluate one student against one rule | O(R) | O(R) for the failure list |
| Whole run (N students × C companies) | O(N · C · R) | O(C · R) streaming; O(N) if students are held in memory |
| Clash check for one registration (k active registrations) | O(k) | O(k) |
| ID lookups (dicts) | O(1) average | O(N) |

Measured: 10^5 students × 100 companies = 10,000,000 evaluations in about 1 minute (about 160k–270k per second); one company with 10^5 students streamed from stdin takes about 1.6 s.

## 6. Final demonstration script

1. `python main.py` and enter the sample input above.
2. `python main.py --demo` – failing conditions, AND/OR/NOT, clash, registration.
3. `python main.py --benchmark` – 10^5 × 100.
4. `python -m unittest discover -v` – 22 tests.

## 7. Likely viva questions

- **Why recursive descent?** Each grammar rule becomes one function, which makes precedence (NOT > AND > OR) and parentheses easy to write and explain.
- **How are all failures reported?** For AND, both sides are checked and failures from both are collected. For OR, failures are reported only if both sides fail.
- **How does clash detection work?** Same date and `start1 < end2 and start2 < end1`. A drive ending at 12:00 and one starting at 12:00 do not clash.
- **Why dictionaries?** ID → record lookups in O(1), and a rule-text → parsed-tree cache.
- **How does it handle 10^5 students?** The rule is parsed once, students are streamed, and passing students use a short-circuit check.
- **Where are the limits?** Pure Python, so 10^7 evaluations takes about a minute. Rules must quote string values (`department == "CSE"`).
