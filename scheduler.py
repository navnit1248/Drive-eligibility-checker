"""Placement-drive validation and half-open interval clash detection."""

from __future__ import annotations

from datetime import date, time

from models import Drive


def validate_drive(drive: Drive) -> None:
    try:
        date.fromisoformat(drive.date)
        start = time.fromisoformat(drive.start_time)
        end = time.fromisoformat(drive.end_time)
    except ValueError as exc:
        raise ValueError("Drive date must be YYYY-MM-DD and times must be valid HH:MM values.") from exc
    if start >= end:
        raise ValueError("Drive end time must be later than its start time on the same date.")


def overlaps(first: Drive, second: Drive) -> bool:
    validate_drive(first)
    validate_drive(second)
    if first.date != second.date:
        return False
    return time.fromisoformat(first.start_time) < time.fromisoformat(second.end_time) and (
        time.fromisoformat(second.start_time) < time.fromisoformat(first.end_time)
    )
