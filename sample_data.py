"""Explicitly loadable demonstration records; never applied automatically."""

from __future__ import annotations

from models import Company, Drive, Student
from storage import JsonStorage


def reset_demo_data(storage: JsonStorage) -> None:
    students = [
        Student("S1", 8.2, 0, "CSE"),
        Student("S2", 7.1, 1, "CSE"),
        Student("S3", 6.4, 0, "IT"),
    ]
    companies = [
        Company(
            "TECH",
            "TechNova",
            'CGPA >= 7.0 AND arrears == 0 AND department == "CSE"',
            min_cgpa=7.0,
            max_arrears=0,
            allowed_departments=("CSE",),
        ),
        Company(
            "ALT",
            "AltSystems",
            'CGPA >= 8.0 OR department == "ECE"',
        ),
        Company(
            "CLEAR",
            "ClearPath",
            "NOT (arrears > 0)",
        ),
    ]
    drives = [
        Drive("D1", "TECH", "2030-06-01", "10:00", "12:00"),
        Drive("D2", "ALT", "2030-06-01", "11:00", "13:00"),
        Drive("D3", "CLEAR", "2030-06-01", "12:00", "13:00"),
    ]
    storage.save_students(students)
    storage.save_companies(companies)
    storage.save_drives(drives)
    storage.save_registrations([])
