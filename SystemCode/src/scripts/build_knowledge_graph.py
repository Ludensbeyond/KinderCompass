"""Create or update the KinderCompass Neo4j graph from the processed catalogue."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[3]
PIPELINE_DIR = REPO_ROOT / "SystemCode" / "src" / "backend" / "pipeline"
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from stage1.kg_client import get_driver  # noqa: E402


DEFAULT_INPUT = REPO_ROOT / "SystemCode" / "data" / "processed" / "kindercompass_master.json"

UPSERT_PRESCHOOL = """
MERGE (p:Preschool {school_id: $school_id})
SET p.centre_code = $centre_code,
    p.tp_code = $tp_code,
    p.identifier_type = $identifier_type,
    p.name = $name,
    p.postal_code = $postal_code,
    p.base_fee = $base_fee,
    p.operator_scheme = $operator_scheme,
    p.care_levels = $care_levels,
    p.philosophy = $philosophy,
    p.pedagogy = $pedagogy,
    p.second_languages_offered = $second_languages_offered,
    p.spark_certified = $spark_certified,
    p.service_model = $service_model,
    p.food_offered = $food_offered,
    p.weekday_full_day = $weekday_full_day,
    p.provision_of_transport = $provision_of_transport,
    p.last_updated = $last_updated
WITH p
OPTIONAL MATCH (p)-[old_location:LOCATED_IN]->(:Town)
DELETE old_location
WITH p
OPTIONAL MATCH (p)-[old_level:SERVES_LEVEL]->(:CareLevel)
DELETE old_level
WITH p
FOREACH (_ IN CASE WHEN $town IS NULL THEN [] ELSE [1] END |
    MERGE (t:Town {name: $town})
    MERGE (p)-[:LOCATED_IN]->(t)
)
"""

ADD_CARE_LEVELS = """
MATCH (p:Preschool {school_id: $school_id})
UNWIND $levels AS level_name
WITH p, level_name WHERE level_name IS NOT NULL
MERGE (c:CareLevel {name: level_name})
MERGE (p)-[:SERVES_LEVEL]->(c)
"""


def load_catalogue(path: str | Path = DEFAULT_INPUT) -> list[dict[str, Any]]:
    source = Path(path).resolve()
    records = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
        raise ValueError("Processed catalogue must be a JSON array of objects")
    identifiers = [record.get("school_id") for record in records]
    if any(not identifier for identifier in identifiers):
        raise ValueError("Every processed record must have a school_id")
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Processed catalogue contains duplicate school_id values")
    return records


def _parameters(school: dict[str, Any]) -> dict[str, Any]:
    fee = school.get("base_fee")
    return {
        "school_id": school["school_id"],
        "centre_code": school.get("centre_code"),
        "tp_code": school.get("tp_code"),
        "identifier_type": school.get("identifier_type"),
        "name": school.get("centre_name_x") or school.get("centre_name") or school.get("name"),
        "postal_code": school.get("postal_code"),
        "town": school.get("town"),
        "base_fee": float(fee) if fee is not None else None,
        "operator_scheme": school.get("operator_scheme"),
        "care_levels": school.get("care_levels") or [],
        "philosophy": school.get("philosophy"),
        "pedagogy": school.get("pedagogy"),
        "second_languages_offered": school.get("second_languages_offered"),
        "spark_certified": school.get("spark_certified"),
        "service_model": school.get("service_model"),
        "food_offered": school.get("food_offered"),
        "weekday_full_day": school.get("weekday_full_day"),
        "provision_of_transport": school.get("provision_of_transport"),
        "last_updated": school.get("last_updated"),
    }


def _care_levels(school: dict[str, Any]) -> list[str]:
    menu = school.get("services_menu") or []
    levels = {
        item.get("levels_offered")
        for item in menu
        if isinstance(item, dict) and item.get("levels_offered")
    }
    return sorted(levels or set(school.get("care_levels") or []))


def build_graph(
    records: list[dict[str, Any]],
    driver: Any,
    *,
    clear_existing: bool = False,
    progress_every: int = 50,
) -> dict[str, int]:
    """Upsert graph records; clear all nodes only when explicitly requested."""
    driver.verify_connectivity()
    if clear_existing:
        driver.run("MATCH (n) DETACH DELETE n")

    started = time.perf_counter()
    for index, school in enumerate(records, start=1):
        driver.run(UPSERT_PRESCHOOL, _parameters(school))
        levels = _care_levels(school)
        if levels:
            driver.run(ADD_CARE_LEVELS, {"school_id": school["school_id"], "levels": levels})
        if progress_every > 0 and index % progress_every == 0:
            elapsed = time.perf_counter() - started
            print(f"Processed {index:,}/{len(records):,} schools ({elapsed:.1f}s)")
    return {"schools": len(records), "cleared_existing": int(clear_existing)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--clear-existing",
        action="store_true",
        help="Delete every existing Neo4j node before rebuilding; omitted by default.",
    )
    parser.add_argument("--progress-every", type=int, default=50)
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    records = load_catalogue(args.input)
    with get_driver() as driver:
        result = build_graph(
            records,
            driver,
            clear_existing=args.clear_existing,
            progress_every=max(0, args.progress_every),
        )
    action = "rebuilt" if args.clear_existing else "updated"
    print(f"Neo4j graph {action}: {result['schools']:,} schools")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
