"""Simple runner to map free-text -> KG filters -> run Stage-1 query and print results."""
import argparse
import json
from pathlib import Path
from dotenv import load_dotenv

from stage1.kg_client import get_driver, run_query, verify_connectivity
from stage1.nlp_mapper import map_text_to_filters
from stage1.query_builder import build_stage1_query
from stage1.scorer import rank_schools
from stage1.proximity import (
    geocode_postal_code,
    load_locations,
    filter_within_radius,
    planning_area_for_point,
)


def run_from_text(text: str, town: str | None = None, output_path: str | Path | None = None, within_1km: bool = False):
    """Run Stage 1 and return its shortlist as a list of dictionaries.

    Printing is retained for the command-line demo, while the return value is the
    programmatic contract consumed by Stage 2.
    """
    return run_from_profile(map_text_to_filters(text), town=town, output_path=output_path, within_1km=within_1km)


def run_from_profile(filters: dict, town: str | None = None, output_path: str | Path | None = None, within_1km: bool = False, radius_km: float | None = None, include_trace: bool = False):
    """Run Stage 1 using an accumulated structured preference profile."""
    load_dotenv()
    driver = get_driver()
    try:
        try:
            verify_connectivity(driver)
        except Exception as e:
            raise RuntimeError(f"Neo4j connectivity failed: {e}") from e

        if not filters["hard_constraints"] and not filters["preferences"]:
            raise ValueError(
                "I could not identify a supported preference. Try Montessori, play-based, "
                "bilingual, Reggio Emilia, a care level, language, SPARK, operator scheme, "
                "transport, halal food, full-day care, or a maximum home distance."
            )
        requested_radius = radius_km if radius_km is not None else 1.0 if within_1km else None
        if requested_radius is not None and requested_radius <= 0:
            raise ValueError("Distance must be greater than 0 km")
        if requested_radius is not None and (not town or not town.isdigit() or len(town) != 6):
            raise ValueError("A distance preference requires a six-digit home postal code")
        repo_root = Path(__file__).resolve().parents[5]
        origin = None
        if town and town.isdigit() and len(town) == 6:
            origin = geocode_postal_code(town)
            if requested_radius is None:
                boundary_file = repo_root / "SystemCode/data/raw/MasterPlan2025PlanningArea.geojson"
                filters["town"] = planning_area_for_point(origin, boundary_file)
        elif town:
            filters["town"] = town

        query, params = build_stage1_query(filters)
        print("Running Cypher:")
        print(query)
        print("Params:", params)

        candidates = run_query(driver, query, params)
        trace = {"database_candidates_after_hard_constraints": len(candidates)}
        if requested_radius is not None:
            locations = load_locations(repo_root / "SystemCode/data/raw/PreSchoolsLocation.geojson")
            candidates = filter_within_radius(candidates, origin, locations, radius_km=requested_radius)
        trace["after_distance_filter"] = len(candidates)
        fully_ranked = rank_schools(filters, candidates, limit=len(candidates))
        trace["after_required_preference_enforcement"] = len(fully_ranked)
        results = fully_ranked[:20]
        trace["stage1_shortlist"] = len(results)
        trace["required_preference_exclusions"] = len(candidates) - len(fully_ranked)
        trace["mean_evidence_confidence"] = (
            round(sum(item["profile_confidence"] for item in results) / len(results), 3)
            if results else 0.0
        )
        print(f"Found {len(results)} matching preschools")
        for r in results[:50]:
            print(r)
        if output_path is not None:
            destination = Path(output_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"Stage 1 shortlist written to {destination}")
        return (results, trace) if include_trace else results
    finally:
        driver.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Run Stage-1 search from free-text input")
    ap.add_argument("--text", required=True, help="Parent free-text preferences")
    ap.add_argument("--town", required=False, help="Optional town code filter")
    ap.add_argument(
        "--output", required=False, help="Write the Stage 1 shortlist to a JSON file"
    )
    args = ap.parse_args()
    run_from_text(args.text, args.town, args.output)
