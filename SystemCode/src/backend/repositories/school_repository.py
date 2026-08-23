from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from SystemCode.src.backend.domain.catalogue import SchoolRecord


class SchoolNotFoundError(LookupError):
    def __init__(self, school_ids: list[str]):
        self.school_ids = school_ids
        super().__init__("Unknown school ID(s): " + ", ".join(school_ids))


class SchoolCatalogueValidationError(RuntimeError):
    pass


class SchoolRepository:
    """Read trusted school facts from the generated catalogue by stable school ID."""

    def __init__(self, catalogue_path: Path):
        self.catalogue_path = catalogue_path
        self._mtime_ns: int | None = None
        self._by_id: dict[str, SchoolRecord] = {}
        self._refresh()

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
        by_id: dict[str, SchoolRecord] = {}
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                raise SchoolCatalogueValidationError(
                    f"School catalogue record {index} must be a JSON object"
                )
            school_id = record.get("school_id")
            if not school_id or school_id in by_id:
                raise SchoolCatalogueValidationError(
                    f"School catalogue record {index} has a missing or duplicate school_id"
                )
            normalized = {
                **record,
                "name": record.get("name") or record.get("centre_name_x")
                or record.get("centre_name") or record.get("Name"),
                "care_levels": record.get("care_levels") or [],
                "services_menu": record.get("services_menu") or [],
            }
            try:
                by_id[school_id] = SchoolRecord.model_validate(normalized)
            except ValidationError as exc:
                details = "; ".join(
                    f"{'.'.join(map(str, error['loc']))}: {error['msg']}"
                    for error in exc.errors()
                )
                raise SchoolCatalogueValidationError(
                    f"Invalid school catalogue record {index} ({school_id}): {details}"
                ) from exc
        self._by_id = by_id
        self._mtime_ns = mtime_ns

    def get(self, school_id: str) -> SchoolRecord:
        self._refresh()
        if school_id not in self._by_id:
            raise SchoolNotFoundError([school_id])
        return self._by_id[school_id].model_copy(deep=True)

    def get_many(self, school_ids: list[str]) -> list[SchoolRecord]:
        self._refresh()
        missing = list(dict.fromkeys(item for item in school_ids if item not in self._by_id))
        if missing:
            raise SchoolNotFoundError(missing)
        return [self._by_id[item].model_copy(deep=True) for item in school_ids]

    def all(self) -> list[SchoolRecord]:
        self._refresh()
        return [item.model_copy(deep=True) for item in self._by_id.values()]

    @property
    def catalogue_version(self) -> str:
        self._refresh()
        return str(self._mtime_ns)

    def facet_summary(self) -> dict:
        """Return privacy-free catalogue statistics for next-question selection."""
        self._refresh()
        from stage1.dialogue_manager import catalogue_facets

        return catalogue_facets(self._by_id.values())
