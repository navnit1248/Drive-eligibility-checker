"""Batch eligibility and registration report helpers."""

from __future__ import annotations

from dataclasses import dataclass

from eligibility import EligibilityService
from models import Company, Registration, Student


@dataclass(frozen=True)
class EligibilityReport:
    eligible: tuple[Student, ...]
    ineligible: tuple[tuple[Student, tuple[str, ...]], ...]


def evaluate_company(
    students: list[Student], company: Company, service: EligibilityService | None = None
) -> EligibilityReport:
    engine = service or EligibilityService()
    eligible: list[Student] = []
    ineligible: list[tuple[Student, tuple[str, ...]]] = []
    for student in students:
        result = engine.evaluate(student, company)
        if result.eligible:
            eligible.append(student)
        else:
            ineligible.append((student, result.reasons))
    return EligibilityReport(tuple(eligible), tuple(ineligible))


def registrations_for_student(
    registrations: list[Registration], student_id: str
) -> list[Registration]:
    return [
        registration
        for registration in registrations
        if registration.student_id == student_id
    ]
