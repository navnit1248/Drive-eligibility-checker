"""Domain models for the drive eligibility system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Student:
    student_id: str
    cgpa: float
    arrears: int
    department: str

    def __post_init__(self) -> None:
        if not self.student_id.strip():
            raise ValueError("Student ID cannot be empty.")
        if isinstance(self.cgpa, bool) or not isinstance(self.cgpa, (int, float)):
            raise ValueError("CGPA must be a number.")
        if not 0 <= self.cgpa <= 10:
            raise ValueError("CGPA must be between 0 and 10.")
        if isinstance(self.arrears, bool) or not isinstance(self.arrears, int) or self.arrears < 0:
            raise ValueError("Arrears must be a non-negative integer.")
        if not self.department.strip():
            raise ValueError("Department cannot be empty.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "student_id": self.student_id,
            "cgpa": self.cgpa,
            "arrears": self.arrears,
            "department": self.department,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Student:
        return cls(
            student_id=str(data["student_id"]),
            cgpa=float(data["cgpa"]),
            arrears=int(data["arrears"]),
            department=str(data["department"]),
        )


@dataclass(frozen=True)
class Company:
    company_id: str
    name: str
    eligibility_rule: str
    min_cgpa: float | None = None
    max_arrears: int | None = None
    allowed_departments: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.company_id.strip() or not self.name.strip():
            raise ValueError("Company ID and name cannot be empty.")
        if not self.eligibility_rule.strip():
            raise ValueError("Eligibility rule cannot be empty.")
        if self.min_cgpa is not None and not 0 <= self.min_cgpa <= 10:
            raise ValueError("Minimum CGPA must be between 0 and 10.")
        if self.max_arrears is not None and self.max_arrears < 0:
            raise ValueError("Maximum arrears cannot be negative.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "company_id": self.company_id,
            "name": self.name,
            "eligibility_rule": self.eligibility_rule,
            "min_cgpa": self.min_cgpa,
            "max_arrears": self.max_arrears,
            "allowed_departments": list(self.allowed_departments),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Company:
        return cls(
            company_id=str(data["company_id"]),
            name=str(data["name"]),
            eligibility_rule=str(data["eligibility_rule"]),
            min_cgpa=float(data["min_cgpa"]) if data.get("min_cgpa") is not None else None,
            max_arrears=int(data["max_arrears"]) if data.get("max_arrears") is not None else None,
            allowed_departments=tuple(str(value) for value in data.get("allowed_departments", [])),
        )


@dataclass(frozen=True)
class Drive:
    drive_id: str
    company_id: str
    date: str
    start_time: str
    end_time: str

    def __post_init__(self) -> None:
        if not self.drive_id.strip() or not self.company_id.strip():
            raise ValueError("Drive ID and company ID cannot be empty.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "drive_id": self.drive_id,
            "company_id": self.company_id,
            "date": self.date,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Drive:
        return cls(
            drive_id=str(data["drive_id"]),
            company_id=str(data["company_id"]),
            date=str(data["date"]),
            start_time=str(data["start_time"]),
            end_time=str(data["end_time"]),
        )


@dataclass(frozen=True)
class Registration:
    registration_id: str
    student_id: str
    drive_id: str
    active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "registration_id": self.registration_id,
            "student_id": self.student_id,
            "drive_id": self.drive_id,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Registration:
        return cls(
            registration_id=str(data["registration_id"]),
            student_id=str(data["student_id"]),
            drive_id=str(data["drive_id"]),
            active=bool(data.get("active", True)),
        )
