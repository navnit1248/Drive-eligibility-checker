from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from eligibility import EligibilityService
from evaluator import EvaluationError, Evaluator
from lexer import LexerError, tokenize
from models import Company, Drive, Registration, Student
from parser import ParseError, parse
from registration import RegistrationRejected, RegistrationService
from reports import evaluate_company
from sample_data import reset_demo_data
from scheduler import overlaps
from storage import JsonStorage


class ParserEvaluatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.student = Student("S1", 7.5, 0, "CSE")

    def test_tokenization_of_valid_expression(self) -> None:
        result = tokenize('CGPA >= 7.0 AND arrears == 0')
        self.assertEqual(
            [token.kind for token in result],
            ["IDENTIFIER", "OP", "NUMBER", "AND", "IDENTIFIER", "OP", "NUMBER", "EOF"],
        )

    def test_invalid_token_and_malformed_expressions(self) -> None:
        with self.assertRaises(LexerError):
            tokenize("CGPA @ 7")
        for expression in (
            "CGPA >= AND arrears == 0",
            "(CGPA >= 7.0",
            "CGPA >>> 7.0",
            "CGPA >=",
        ):
            with self.subTest(expression=expression), self.assertRaises(ParseError):
                parse(expression)

    def test_and_or_precedence(self) -> None:
        self.assertTrue(Evaluator(self.student).evaluate(parse('CGPA >= 7 OR arrears == 1 AND department == "CSE"')).passed)
        self.assertFalse(Evaluator(self.student).evaluate(parse('CGPA > 8 AND arrears == 0 OR department == "IT"')).passed)

    def test_not_and_nested_parentheses(self) -> None:
        self.assertTrue(
            Evaluator(self.student).evaluate(parse('NOT (arrears > 0 OR department == "IT")')).passed
        )
        self.assertFalse(Evaluator(self.student).evaluate(parse("NOT (CGPA >= 7)")).passed)

    def test_numeric_and_string_comparisons(self) -> None:
        self.assertTrue(Evaluator(self.student).evaluate(parse('CGPA == 7.5 AND department == "CSE"')).passed)
        self.assertTrue(Evaluator(self.student).evaluate(parse("arrears != 1")).passed)

    def test_unknown_fields_and_incompatible_types(self) -> None:
        with self.assertRaises(EvaluationError):
            Evaluator(self.student).evaluate(parse("unknown == 1"))
        with self.assertRaises(EvaluationError):
            Evaluator(self.student).evaluate(parse('CGPA == "7.5"'))

    def test_multiple_failed_conditions(self) -> None:
        student = Student("S2", 6.4, 2, "ECE")
        company = Company(
            "C1",
            "Example",
            'CGPA >= 7.0 AND arrears == 0 AND department == "CSE"',
        )
        result = EligibilityService().evaluate(student, company)
        self.assertFalse(result.eligible)
        self.assertEqual(len(result.reasons), 3)
        self.assertIn("CGPA is 6.4", result.reasons[0])
        self.assertIn("Arrears are 2", result.reasons[1])
        self.assertIn("Department is ECE", result.reasons[2])

    def test_or_alternative_passes_without_false_failure(self) -> None:
        company = Company("C2", "Alternative", 'CGPA >= 8 OR department == "CSE"')
        result = EligibilityService().evaluate(self.student, company)
        self.assertTrue(result.eligible)
        self.assertEqual(result.reasons, ())

    def test_exact_minimum_cgpa_boundary(self) -> None:
        company = Company("C3", "Boundary", "CGPA >= 7.5")
        self.assertTrue(EligibilityService().evaluate(self.student, company).eligible)


class RegistrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.storage = JsonStorage(Path(self.temp.name))
        self.student = Student("S1", 8.5, 0, "CSE")
        self.companies = [
            Company("A", "Company A", "CGPA >= 7 AND arrears == 0"),
            Company("B", "Company B", "CGPA >= 7"),
            Company("C", "Company C", "CGPA >= 7"),
        ]
        self.drives = [
            Drive("D1", "A", "2030-01-01", "10:00", "12:00"),
            Drive("D2", "B", "2030-01-01", "11:00", "13:00"),
            Drive("D3", "C", "2030-01-01", "12:00", "13:00"),
            Drive("D4", "B", "2030-01-02", "11:00", "13:00"),
        ]
        self.storage.save_students([self.student])
        self.storage.save_companies(self.companies)
        self.storage.save_drives(self.drives)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_successful_registration(self) -> None:
        registration = RegistrationService(self.storage).register("S1", "D1")
        self.assertEqual(registration.drive_id, "D1")
        self.assertEqual(len(self.storage.load_registrations()), 1)

    def test_rejects_ineligible_student_without_saving(self) -> None:
        self.storage.save_students([Student("S1", 6.0, 0, "CSE")])
        with self.assertRaises(RegistrationRejected):
            RegistrationService(self.storage).register("S1", "D1")
        self.assertEqual(self.storage.load_registrations(), [])

    def test_rejects_duplicate_registration(self) -> None:
        service = RegistrationService(self.storage)
        service.register("S1", "D1")
        with self.assertRaisesRegex(RegistrationRejected, "already registered"):
            service.register("S1", "D1")

    def test_detects_overlapping_drives_and_reports_clash(self) -> None:
        service = RegistrationService(self.storage)
        service.register("S1", "D1")
        with self.assertRaisesRegex(RegistrationRejected, "Schedule conflict"):
            service.register("S1", "D2")
        self.assertEqual(len(self.storage.load_registrations()), 1)

    def test_accepts_non_overlapping_and_touching_drives(self) -> None:
        service = RegistrationService(self.storage)
        service.register("S1", "D1")
        service.register("S1", "D3")
        service.register("S1", "D4")
        self.assertEqual(len(self.storage.load_registrations()), 3)

    def test_overlap_half_open_and_date_aware(self) -> None:
        first = self.drives[0]
        self.assertFalse(overlaps(first, self.drives[2]))
        self.assertFalse(overlaps(first, self.drives[3]))

    def test_json_persistence_across_reload(self) -> None:
        RegistrationService(self.storage).register("S1", "D1")
        reloaded = JsonStorage(Path(self.temp.name))
        self.assertEqual(reloaded.load_students(), [self.student])
        self.assertEqual(len(reloaded.load_registrations()), 1)


class BatchTests(unittest.TestCase):
    def test_10000_students_against_100_companies(self) -> None:
        students = [
            Student(f"S{index}", float(index % 11), index % 3, "CSE" if index % 2 else "ECE")
            for index in range(10_000)
        ]
        companies = [
            Company(
                f"C{index}",
                f"Company {index}",
                f'CGPA >= {index % 10} AND arrears <= 1 AND department == "CSE"',
            )
            for index in range(100)
        ]
        service = EligibilityService()
        evaluated = 0
        for company in companies:
            report = evaluate_company(students, company, service)
            evaluated += len(report.eligible) + len(report.ineligible)
        self.assertEqual(evaluated, 1_000_000)


class SampleDataTests(unittest.TestCase):
    def test_sample_students_calculate_expected_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            storage = JsonStorage(directory)
            reset_demo_data(storage)
            tech = storage.load_companies()[0]
            report = evaluate_company(storage.load_students(), tech)
            self.assertEqual([student.student_id for student in report.eligible], ["S1"])
            reasons = {student.student_id: why for student, why in report.ineligible}
            self.assertEqual(len(reasons["S2"]), 1)
            self.assertEqual(len(reasons["S3"]), 2)


if __name__ == "__main__":
    unittest.main()
