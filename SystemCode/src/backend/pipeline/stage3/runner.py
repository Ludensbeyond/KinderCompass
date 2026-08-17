"""Command-line Stage 3 home-to-preschool distance calculator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from stage1.proximity import geocode_postal_code
from stage3.locations import attach_locations, load_preschool_locations
from stage3.optimizer import calculate_home_to_preschool


DEFAULT_LOCATIONS = "SystemCode/data/raw/PreSchoolsLocation.geojson"


def run_from_file(
    input_path: str | Path,
    *,
    selected_code: str,
    home_postal_code: str,
    locations_path: str | Path = DEFAULT_LOCATIONS,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    source = Path(input_path)
    try:
        stage2_results = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Stage 2 input file does not exist: {source}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Stage 2 input is not valid JSON: {source}") from exc
    if not isinstance(stage2_results, list):
        raise ValueError("Stage 2 input must be a JSON array")

    by_code = {
        (school.get("school_id") or school.get("centre_code")): school
        for school in stage2_results
        if school.get("eligible") is True
    }
    if selected_code not in by_code:
        raise ValueError("The selected centre is absent or ineligible in Stage 2")

    if len(home_postal_code) != 6 or not home_postal_code.isdigit():
        raise ValueError("Home postal code must contain exactly six digits")
    home = {"type": "home", "name": "Home", **geocode_postal_code(home_postal_code)}
    school = attach_locations(
        [by_code[selected_code]], load_preschool_locations(locations_path)
    )[0]
    result = calculate_home_to_preschool(home, school)

    print(f"Home-to-preschool distance: {result['total_distance_km']:.3f} km")
    if output_path is not None:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Stage 3 result written to {destination}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate the Stage 3 home-to-preschool distance")
    parser.add_argument("--input", required=True, help="Stage 2 results JSON file")
    parser.add_argument("--select", required=True, help="One eligible school_id or centre code")
    parser.add_argument("--home-postal-code", required=True, help="Six-digit home postal code")
    parser.add_argument("--locations", default=DEFAULT_LOCATIONS)
    parser.add_argument("--output", help="Optional Stage 3 result JSON file")
    args = parser.parse_args()
    try:
        run_from_file(
            args.input,
            selected_code=args.select,
            home_postal_code=args.home_postal_code,
            locations_path=args.locations,
            output_path=args.output,
        )
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
