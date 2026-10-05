from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from SystemCode.src.backend.domain.catalogue import SchoolRecord


StructuredSchoolFactOperation = Literal[
    "food", "programmes", "fees", "vacancy", "operating_hours",
    "transport", "contact", "location",
]

STRUCTURED_SCHOOL_FACT_FIELDS: dict[StructuredSchoolFactOperation, tuple[str, ...]] = {
    "food": ("food_offered",),
    "programmes": (
        "care_levels", "services_menu", "pedagogy", "second_languages_offered",
        "service_model",
    ),
    "fees": ("base_fee", "services_menu", "has_fee_data"),
    "vacancy": ("has_vacancy_data",),
    "operating_hours": ("weekday_full_day", "extended_operating_hours", "saturday"),
    "transport": ("provision_of_transport",),
    "contact": (
        "centre_contact_no", "centre_email_address", "contactno_lifesg",
        "emailaddress_lifesg", "centre_website", "website_lifesg",
    ),
    "location": ("centre_address", "postal_code", "town", "geometry"),
}


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

    def get_structured_facts(
        self, school_ids: list[str], operation: StructuredSchoolFactOperation,
        *, as_of: date | None = None,
    ) -> list[dict[str, Any]]:
        """Return one allowlisted fact projection for authoritative school IDs.

        The operation, rather than caller-supplied field names or query text,
        controls the projection. This keeps Cypher and unrestricted catalogue
        access outside the conversation-tool boundary.
        """

        if operation not in STRUCTURED_SCHOOL_FACT_FIELDS:
            raise ValueError(f"unsupported structured school fact operation: {operation}")
        records = self.get_many(school_ids)
        version = self.catalogue_version
        today = as_of or date.today()
        results: list[dict[str, Any]] = []
        for record in records:
            source = record.model_dump(mode="json")
            fields = list(STRUCTURED_SCHOOL_FACT_FIELDS[operation])
            if operation == "vacancy":
                fields.extend(sorted(key for key in source if "_vacancy_" in key))
            facts = {key: source.get(key) for key in fields if key in source}
            last_updated = source.get("last_updated")
            freshness = "unknown"
            if last_updated:
                try:
                    updated = datetime.fromisoformat(str(last_updated)).date()
                    freshness = "stale" if updated < today - timedelta(days=180) else "current"
                except ValueError:
                    freshness = "unknown"
            meaningful = [
                value for key, value in facts.items()
                if key not in {"has_fee_data", "has_vacancy_data"}
                and value not in (None, "", [], {})
            ]
            available = bool(meaningful)
            if operation == "vacancy":
                available = bool(source.get("has_vacancy_data") and meaningful)
            elif operation == "fees" and source.get("has_fee_data") is False:
                available = False
            results.append({
                "school_id": record.school_id,
                "name": record.name,
                "operation": operation,
                "facts": facts,
                "available": available,
                "source": "generated_school_catalogue",
                "catalogue_version": version,
                "last_updated": last_updated,
                "freshness": freshness,
            })
        return results

    @property
    def catalogue_version(self) -> str:
        self._refresh()
        return str(self._mtime_ns)

    def facet_summary(self) -> dict:
        """Return privacy-free catalogue statistics for next-question selection."""
        self._refresh()
        from stage1.dialogue_manager import catalogue_facets

        return catalogue_facets(self._by_id.values())
