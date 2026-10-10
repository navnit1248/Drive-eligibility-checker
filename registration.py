"""Registration rules combining eligibility, duplicate, and schedule checks."""

from __future__ import annotations

from uuid import uuid4

from eligibility import EligibilityService
from models import Company, Drive, Registration, Student
from scheduler import overlaps, validate_drive
from storage import JsonStorage


class RegistrationRejected(ValueError):
    """A registration did not pass an eligibility or scheduling check."""


class RegistrationService:
    def __init__(self, storage: JsonStorage, eligibility: EligibilityService | None = None):
        self.storage = storage
        self.eligibility = eligibility or EligibilityService()

    def register(self, student_id: str, drive_id: str) -> Registration:
        students = {student.student_id: student for student in self.storage.load_students()}
        companies = {company.company_id: company for company in self.storage.load_companies()}
        drives = {drive.drive_id: drive for drive in self.storage.load_drives()}
        student = students.get(student_id)
        if student is None:
            raise RegistrationRejected(f"Unknown student ID {student_id!r}.")
        requested = drives.get(drive_id)
        if requested is None:
            raise RegistrationRejected(f"Unknown drive ID {drive_id!r}.")
        validate_drive(requested)
        company = companies.get(requested.company_id)
        if company is None:
            raise RegistrationRejected(
                f"Drive {requested.drive_id!r} refers to unknown company {requested.company_id!r}."
            )
        result = self.eligibility.evaluate(student, company)
        if not result.eligible:
            reasons = "\n".join(f"- {reason}" for reason in result.reasons)
            raise RegistrationRejected(f"Student is not eligible:\n{reasons}")

        registrations = self.storage.load_registrations()
        active_for_student = [
            item for item in registrations if item.student_id == student_id and item.active
        ]
        if any(item.drive_id == drive_id for item in active_for_student):
            raise RegistrationRejected(f"Student is already registered for drive {drive_id!r}.")

        for registration in active_for_student:
            existing = drives.get(registration.drive_id)
            if existing is None:
                raise RegistrationRejected(
                    f"Active registration {registration.registration_id!r} refers to missing "
                    f"drive {registration.drive_id!r}."
                )
            if overlaps(existing, requested):
                existing_company = companies.get(existing.company_id)
                company_name = existing_company.name if existing_company else existing.company_id
                requested_name = company.name
                raise RegistrationRejected(
                    "Schedule conflict.\n"
                    f"Existing drive: {company_name}\n"
                    f"Existing time: {existing.start_time}-{existing.end_time}\n"
                    f"Requested drive: {requested_name}\n"
                    f"Requested time: {requested.start_time}-{requested.end_time}"
                )

        registration = Registration(
            registration_id=str(uuid4()),
            student_id=student_id,
            drive_id=drive_id,
        )
        registrations.append(registration)
        self.storage.save_registrations(registrations)
        return registration
