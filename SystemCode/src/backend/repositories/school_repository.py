from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SchoolNotFoundError(LookupError):
    def __init__(self, school_ids: list[str]):
        self.school_ids = school_ids
        super().__init__("Unknown school ID(s): " + ", ".join(school_ids))


class SchoolRepository:
    """Read trusted school facts from the generated catalogue by stable school ID."""

    def __init__(self, catalogue_path: Path):
        self.catalogue_path = catalogue_path
        self._mtime_ns: int | None = None
        self._by_id: dict[str, dict[str, Any]] = {}

    def _refresh(self) -> None:
        try:
            mtime_ns = self.catalogue_path.stat().st_mtime_ns
        except FileNotFoundError as exc:
            raise RuntimeError(f"School catalogue is unavailable: {self.catalogue_path}") from exc
        if self._mtime_ns == mtime_ns:
            return
        records = json.loads(self.catalogue_path.read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise RuntimeError("School catalogue must be a JSON array")
        by_id: dict[str, dict[str, Any]] = {}
        for record in records:
            school_id = record.get("school_id")
            if not school_id or school_id in by_id:
                raise RuntimeError("School catalogue contains missing or duplicate school IDs")
            by_id[school_id] = {
                **record,
                "name": record.get("name") or record.get("centre_name_x") or record.get("centre_name"),
            }
        self._by_id = by_id
        self._mtime_ns = mtime_ns

    def get(self, school_id: str) -> dict[str, Any]:
        self._refresh()
        if school_id not in self._by_id:
            raise SchoolNotFoundError([school_id])
        return dict(self._by_id[school_id])

    def get_many(self, school_ids: list[str]) -> list[dict[str, Any]]:
        self._refresh()
        missing = list(dict.fromkeys(item for item in school_ids if item not in self._by_id))
        if missing:
            raise SchoolNotFoundError(missing)
        return [dict(self._by_id[item]) for item in school_ids]

    def all(self) -> list[dict[str, Any]]:
        self._refresh()
        return [dict(item) for item in self._by_id.values()]
