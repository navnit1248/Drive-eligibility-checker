"""JSON persistence for students, companies, drives, and registrations."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, TypeVar

from models import Company, Drive, Registration, Student

T = TypeVar("T")


class StorageError(RuntimeError):
    """Raised when persistent data cannot be read or written safely."""


class JsonStorage:
    def __init__(self, directory: str | Path = "data"):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._paths = {
            "students": self.directory / "students.json",
            "companies": self.directory / "companies.json",
            "drives": self.directory / "drives.json",
            "registrations": self.directory / "registrations.json",
        }
        for path in self._paths.values():
            if not path.exists():
                self._write(path, [])

    def _read(self, key: str, factory: Callable[[dict[str, Any]], T]) -> list[T]:
        path = self._paths[key]
        try:
            with path.open("r", encoding="utf-8") as file:
                raw = json.load(file)
            if not isinstance(raw, list):
                raise StorageError(f"{path} must contain a JSON array.")
            if not all(isinstance(item, dict) for item in raw):
                raise StorageError(f"{path} contains a record that is not a JSON object.")
            return [factory(item) for item in raw]
        except StorageError:
            raise
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise StorageError(f"Could not load {path}: {exc}") from exc

    def _write(self, path: Path, records: list[dict[str, Any]]) -> None:
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.directory, delete=False
            ) as file:
                temporary_path = Path(file.name)
                json.dump(records, file, indent=2, ensure_ascii=False)
                file.write("\n")
            os.replace(temporary_path, path)
        except OSError as exc:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
            raise StorageError(f"Could not save {path}: {exc}") from exc

    def _save(self, key: str, records: list[Any]) -> None:
        self._write(self._paths[key], [record.to_dict() for record in records])

    def load_students(self) -> list[Student]:
        return self._read("students", Student.from_dict)

    def save_students(self, records: list[Student]) -> None:
        self._save("students", records)

    def load_companies(self) -> list[Company]:
        return self._read("companies", Company.from_dict)

    def save_companies(self, records: list[Company]) -> None:
        self._save("companies", records)

    def load_drives(self) -> list[Drive]:
        return self._read("drives", Drive.from_dict)

    def save_drives(self, records: list[Drive]) -> None:
        self._save("drives", records)

    def load_registrations(self) -> list[Registration]:
        return self._read("registrations", Registration.from_dict)

    def save_registrations(self, records: list[Registration]) -> None:
        self._save("registrations", records)
