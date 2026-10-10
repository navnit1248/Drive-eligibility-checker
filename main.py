"""Command-line interface for the Drive Eligibility and Registration System."""

from __future__ import annotations

import argparse
import json
import sys
from typing import TypeVar

from models import Company, Drive, Student
from registration import (
    RegistrationRejected,
    RegistrationService,
    overlaps,
    validate_drive,
)
from reports import evaluate_company, registrations_for_student
from rule_engine import EligibilityService, EvaluationError, Evaluator, ParseError, parse
from sample_data import reset_demo_data
from storage import JsonStorage, StorageError

T = TypeVar("T")


MENU = """=========================================
 DRIVE ELIGIBILITY AND REGISTRATION SYSTEM
=========================================
1. View students
2. Add student
3. View companies and eligibility rules
4. Add company or update its rule
5. Evaluate one student
6. Evaluate all students for a company
7. View eligible and ineligible students
8. View placement drives
9. Schedule a placement drive
10. Register student for a drive
11. View registration and clash reports
12. Validate an expression
13. Reset demonstration data (confirmed)
14. Exit
"""


def choose(records: list[T], id_attribute: str, label: str) -> T:
    if not records:
        raise ValueError(f"No {label.lower()} are available.")
    for record in records:
        print(f"{getattr(record, id_attribute)}: {record}")
    chosen = input(f"{label} ID: ").strip()
    for record in records:
        if getattr(record, id_attribute) == chosen:
            return record
    raise ValueError(f"Unknown {label.lower()} ID {chosen!r}.")


def add_student(storage: JsonStorage) -> None:
    student = Student(
        input("Student ID: ").strip(),
        float(input("CGPA (0-10): ")),
        int(input("Number of arrears: ")),
        input("Department: ").strip(),
    )
    students = storage.load_students()
    if any(existing.student_id == student.student_id for existing in students):
        raise ValueError(f"Student ID {student.student_id!r} already exists.")
    students.append(student)
    storage.save_students(students)
    print("Student saved.")


def add_company(storage: JsonStorage) -> None:
    company_id = input("Company ID: ").strip()
    name = input("Company name: ").strip()
    rule = input("Eligibility expression: ").strip()
    parse(rule)
    companies = storage.load_companies()
    existing = next((item for item in companies if item.company_id == company_id), None)
    company = Company(company_id, name, rule)
    if existing:
        companies[companies.index(existing)] = company
        print("Company rule updated.")
    else:
        companies.append(company)
        print("Company saved.")
    storage.save_companies(companies)


def add_drive(storage: JsonStorage) -> None:
    drive = Drive(
        input("Drive ID: ").strip(),
        input("Company ID: ").strip(),
        input("Date (YYYY-MM-DD): ").strip(),
        input("Start time (HH:MM): ").strip(),
        input("End time (HH:MM): ").strip(),
    )
    validate_drive(drive)
    companies = storage.load_companies()
    if not any(company.company_id == drive.company_id for company in companies):
        raise ValueError(f"Unknown company ID {drive.company_id!r}.")
    drives = storage.load_drives()
    if any(existing.drive_id == drive.drive_id for existing in drives):
        raise ValueError(f"Drive ID {drive.drive_id!r} already exists.")
    drives.append(drive)
    storage.save_drives(drives)
    print("Drive saved.")


def evaluate_one(storage: JsonStorage) -> None:
    student = choose(storage.load_students(), "student_id", "Student")
    company = choose(storage.load_companies(), "company_id", "Company")
    result = EligibilityService().evaluate(student, company)
    print(f"\n{student.student_id}: {'ELIGIBLE' if result.eligible else 'NOT ELIGIBLE'}")
    for reason in result.failures:
        print(f"- {reason}")


def evaluate_all(storage: JsonStorage) -> None:
    company = choose(storage.load_companies(), "company_id", "Company")
    students = storage.load_students()
    report = evaluate_company(students, company)
    print(f"\nEligibility for {company.name}:")
    results = {
        student.student_id: reasons for student, reasons in report.ineligible
    }
    for student in students:
        if student.student_id not in results:
            print(f"\n{student.student_id} ELIGIBLE")
        else:
            print(f"\n{student.student_id} NOT ELIGIBLE")
            for reason in results[student.student_id]:
                print(f"- {reason}")


def view_eligibility_summary(storage: JsonStorage) -> None:
    company = choose(storage.load_companies(), "company_id", "Company")
    report = evaluate_company(storage.load_students(), company)
    print(f"\n{company.name} - eligible:")
    print(", ".join(student.student_id for student in report.eligible) or "None")
    print("Ineligible:")
    print(", ".join(student.student_id for student, _ in report.ineligible) or "None")


def view_registration_report(storage: JsonStorage) -> None:
    registrations = storage.load_registrations()
    students = {student.student_id: student for student in storage.load_students()}
    drives = {drive.drive_id: drive for drive in storage.load_drives()}
    companies = {company.company_id: company for company in storage.load_companies()}
    if not registrations:
        print("No registrations.")
    for registration in registrations:
        drive = drives.get(registration.drive_id)
        company = companies.get(drive.company_id) if drive else None
        student_name = students.get(registration.student_id)
        drive_description = (
            f"{company.name if company else 'Unknown company'} "
            f"{drive.date} {drive.start_time}-{drive.end_time}"
            if drive
            else "Missing drive"
        )
        print(
            f"{registration.registration_id}: "
            f"{student_name.student_id if student_name else registration.student_id} -> "
            f"{drive_description} ({'active' if registration.active else 'inactive'})"
        )
    print("\nClashes among active registrations:")
    student_ids = {registration.student_id for registration in registrations}
    clashes = 0
    for student_id in student_ids:
        active = [
            registration
            for registration in registrations_for_student(registrations, student_id)
            if registration.active
        ]
        student_drives = [drives[item.drive_id] for item in active if item.drive_id in drives]
        for index, first in enumerate(student_drives):
            for second in student_drives[index + 1 :]:
                if overlaps(first, second):
                    clashes += 1
                    print(
                        f"{student_id}: {first.company_id} "
                        f"{first.start_time}-{first.end_time} conflicts with "
                        f"{second.company_id} {second.start_time}-{second.end_time}"
                    )
    if clashes == 0:
        print("No clashes found.")


def build_company_rule(line: str) -> str:
    values = line.replace(",", " ").split()
    if len(values) < 3:
        raise ValueError("Company rule must be: minCGPA maxArrears department...")
    try:
        minimum_cgpa = float(values[0])
        maximum_arrears = int(values[1])
    except ValueError as exc:
        raise ValueError("Minimum CGPA must be numeric and maximum arrears an integer.") from exc
    if not 0 <= minimum_cgpa <= 10:
        raise ValueError("Minimum CGPA must be between 0 and 10.")
    if maximum_arrears < 0:
        raise ValueError("Maximum arrears cannot be negative.")
    departments = " OR ".join(
        f"department == {json.dumps(department)}" for department in values[2:]
    )
    return (
        f"CGPA >= {minimum_cgpa} AND arrears <= {maximum_arrears} "
        f"AND ({departments})"
    )


def read_batch_line(prompt: str, missing_message: str) -> str:
    if sys.stdin.isatty():
        return input(prompt)
    line = sys.stdin.readline()
    if not line:
        raise ValueError(missing_message)
    return line


def run_batch(rule: str | None) -> None:
    if rule is None:
        first_line = read_batch_line(
            "Company rule (minimum CGPA, maximum arrears, allowed departments): ",
            "No company rule input. Run this program in a terminal and enter the company rule, "
            "then student count and student records. See README.md for the input format.",
        )
        expression = build_company_rule(first_line)
    else:
        expression = rule
    tree = parse(expression)

    count_line = read_batch_line(
        "Number of students: ",
        "Missing student count. Enter the student count after the company rule.",
    )
    try:
        student_count = int(count_line)
    except ValueError as exc:
        raise ValueError("Student count must be a whole number.") from exc
    if student_count < 0:
        raise ValueError("Number of students cannot be negative.")

    for _ in range(student_count):
        line = read_batch_line(
            "Student (ID CGPA arrears department): ",
            "Input ended before all student records were read.",
        )
        fields = line.replace(",", " ").split()
        if len(fields) != 4:
            raise ValueError(f"Student record must be: ID CGPA arrears department; got {line.strip()!r}.")
        try:
            student = Student(fields[0], float(fields[1]), int(fields[2]), fields[3])
        except ValueError as exc:
            raise ValueError(f"Invalid student record {fields[0]!r}: {exc}") from exc
        result = Evaluator(student).evaluate(tree)
        if result.passed:
            print(f"{student.student_id} ELIGIBLE")
            continue

        labels: list[str] = []
        for reason in result.failures:
            first_word = reason.partition(" ")[0].casefold()
            label = first_word if first_word in {"cgpa", "arrears", "department"} else "rule"
            if label not in labels:
                labels.append(label)
        print(f"{student.student_id} NOT ELIGIBLE ({', '.join(labels)})")
        for reason in result.failures:
            print(f"  - {reason}")


def run(storage: JsonStorage) -> None:
    while True:
        print(MENU)
        choice = input("Choose an option: ").strip()
        try:
            if choice == "1":
                for student in storage.load_students():
                    print(student)
            elif choice == "2":
                add_student(storage)
            elif choice == "3":
                for company in storage.load_companies():
                    print(f"{company.company_id}: {company.name}\n  Rule: {company.eligibility_rule}")
            elif choice == "4":
                add_company(storage)
            elif choice == "5":
                evaluate_one(storage)
            elif choice == "6":
                evaluate_all(storage)
            elif choice == "7":
                view_eligibility_summary(storage)
            elif choice == "8":
                companies = {
                    company.company_id: company for company in storage.load_companies()
                }
                for drive in storage.load_drives():
                    company = companies.get(drive.company_id)
                    print(
                        f"{drive.drive_id}: {company.name if company else drive.company_id} "
                        f"{drive.date} {drive.start_time}-{drive.end_time}"
                    )
            elif choice == "9":
                add_drive(storage)
            elif choice == "10":
                student_id = input("Student ID: ").strip()
                drive_id = input("Drive ID: ").strip()
                registration = RegistrationService(storage).register(student_id, drive_id)
                print(f"Registration saved: {registration.registration_id}")
            elif choice == "11":
                view_registration_report(storage)
            elif choice == "12":
                expression = input("Expression: ")
                tree = parse(expression)
                print(f"Valid expression: {tree}")
            elif choice == "13":
                confirmation = input(
                    "This replaces all current records with demo data. Type RESET to continue: "
                )
                if confirmation == "RESET":
                    reset_demo_data(storage)
                    print("Demonstration data loaded.")
                else:
                    print("Reset cancelled; existing data was not changed.")
            elif choice == "14":
                print("Goodbye.")
                return
            else:
                print("Choose a menu number from 1 to 14.")
        except (ValueError, ParseError, EvaluationError, RegistrationRejected, StorageError) as exc:
            print(f"Error: {exc}")


def run_demo() -> None:
    """Show every required feature on small data, using a temporary store."""
    import tempfile

    print("1. Every failing condition is reported (rule: CGPA >= 7 AND arrears <= 0)")
    student = Student("S9", 6.0, 2, "ECE")
    for reason in Evaluator(student).evaluate(parse("cgpa >= 7.0 AND arrears == 0")).failures:
        print(f"   - {reason}")

    print("\n2. Custom AND / OR / NOT rules (recursive-descent parser)")
    rule = 'cgpa >= 7.0 AND NOT (arrears > 1) AND (department == "CSE" OR department == "IT")'
    print(f"   Rule: {rule}")
    print(f"   Parsed tree: {parse(rule)}")
    for sample in (Student("A1", 8.0, 0, "IT"), Student("A2", 8.0, 3, "IT"), Student("A3", 9.0, 0, "ECE")):
        passed = Evaluator(sample).evaluate(parse(rule)).passed
        print(f"   {sample.student_id}: {'ELIGIBLE' if passed else 'NOT ELIGIBLE'}")

    print("\n3. Drive clashes and 4. registration")
    with tempfile.TemporaryDirectory() as folder:
        storage = JsonStorage(folder)
        storage.save_students([Student("S1", 8.5, 0, "CSE")])
        storage.save_companies([Company("C1", "Alpha", "cgpa >= 7.0"), Company("C2", "Beta", "cgpa >= 7.0")])
        storage.save_drives([
            Drive("D1", "C1", "2026-11-01", "09:00", "12:00"),
            Drive("D2", "C2", "2026-11-01", "11:00", "14:00"),
            Drive("D3", "C2", "2026-11-02", "09:00", "12:00"),
        ])
        service = RegistrationService(storage)
        for drive_id in ("D1", "D2", "D3"):
            try:
                service.register("S1", drive_id)
                print(f"   register S1 {drive_id}: OK")
            except RegistrationRejected as exc:
                print(f"   register S1 {drive_id}: REJECTED - {exc}")


def run_benchmark(students: int = 100_000, companies: int = 100) -> None:
    import random
    import time

    random.seed(1)
    departments = ["CSE", "IT", "ECE", "MECH"]
    people = [
        Student(f"S{i}", round(random.uniform(5, 10), 1), random.randint(0, 3), random.choice(departments))
        for i in range(students)
    ]
    trees = [
        parse(f'cgpa >= {5 + c % 5} AND arrears <= {c % 3} AND (department == "CSE" OR department == "IT")')
        for c in range(companies)
    ]
    start = time.perf_counter()
    eligible = sum(Evaluator(s).evaluate(t).passed for t in trees for s in people)
    elapsed = time.perf_counter() - start
    total = students * companies
    print(f"{students} students x {companies} companies = {total} checks in {elapsed:.1f}s")
    print(f"{eligible} eligible results")


def main() -> None:
    command_line = argparse.ArgumentParser(description="Check placement-drive eligibility.")
    command_line.add_argument("--demo", action="store_true", help="demonstrate every feature")
    command_line.add_argument("--benchmark", action="store_true", help="run 100000 students x 100 companies")
    command_line.add_argument(
        "--interactive",
        action="store_true",
        help="open the local menu for managing students, companies, drives, and registrations",
    )
    command_line.add_argument(
        "--rule",
        help="evaluate a custom expression; stdin then starts with the student count",
    )
    args = command_line.parse_args()
    try:
        if args.demo:
            run_demo()
        elif args.benchmark:
            run_benchmark()
        elif args.interactive:
            run(JsonStorage())
        else:
            run_batch(args.rule)
    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye.")
    except (ValueError, StorageError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
