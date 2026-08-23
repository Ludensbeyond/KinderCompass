"""Command-line Stage 2 runner that consumes a Stage 1 JSON shortlist."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

from stage2.engine import evaluate_shortlist


def _date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use a date in YYYY-MM-DD format") from exc


def run_from_file(
    input_path: str | Path,
    *,
    dob: dt.date,
    admission_date: dt.date,
    ghi: float,
    basic_subsidy: float | None = None,
    citizenship: str = "SC",
    programme_type: str = "full_day",
    working_hours_per_month: float = 56,
    household_size: int = 1,
    non_earning_dependants: int = 0,
    output_path: str | Path | None = None,
    include_ineligible: bool = False,
) -> list[dict[str, Any]]:
    """Load a Stage 1 JSON file, evaluate it, and optionally write Stage 2 JSON."""
    source = Path(input_path)
    try:
        shortlist = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Stage 1 input file does not exist: {source}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Stage 1 input is not valid JSON: {source}") from exc

    if not isinstance(shortlist, list) or not all(
        isinstance(school, dict) for school in shortlist
    ):
        raise ValueError("Stage 1 input must be a JSON array of preschool objects")

    results = evaluate_shortlist(
        shortlist,
        dob=dob,
        admission_date=admission_date,
        ghi=ghi,
        basic_subsidy=basic_subsidy,
        citizenship=citizenship,
        programme_type=programme_type,
        working_hours_per_month=working_hours_per_month,
        household_size=household_size,
        non_earning_dependants=non_earning_dependants,
        include_ineligible=include_ineligible,
    )

    print(f"Stage 2 found {len(results)} eligible preschools")
    for school in results:
        print(
            f"{school.get('name', '<unnamed>')}: "
            f"{school['eligible_level']}, net monthly fee=${school['net_monthly_fee']:.2f}"
        )

    if output_path is not None:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Stage 2 results written to {destination}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate a Stage 1 preschool shortlist"
    )
    parser.add_argument("--input", required=True, help="Stage 1 shortlist JSON file")
    parser.add_argument("--dob", required=True, type=_date, help="Child DOB: YYYY-MM-DD")
    parser.add_argument(
        "--admission-date", required=True, type=_date, help="Admission date: YYYY-MM-DD"
    )
    parser.add_argument("--ghi", required=True, type=float, help="Gross household income")
    parser.add_argument("--basic-subsidy", type=float, help="Deprecated compatibility override")
    parser.add_argument("--citizenship", choices=("SC", "SPR", "Others"), default="SC")
    parser.add_argument(
        "--programme-type",
        choices=("full_day", "half_day", "flexi_care_1", "flexi_care_2", "flexi_care_3"),
        default="full_day",
    )
    parser.add_argument("--working-hours", type=float, default=56)
    parser.add_argument("--household-size", type=int, default=1)
    parser.add_argument("--non-earning-dependants", type=int, default=0)
    parser.add_argument("--output", help="Optional Stage 2 output JSON file")
    parser.add_argument(
        "--include-ineligible",
        action="store_true",
        help="Keep ineligible schools in the Stage 2 output",
    )
    args = parser.parse_args()
    run_from_file(
        args.input,
        dob=args.dob,
        admission_date=args.admission_date,
        ghi=args.ghi,
        basic_subsidy=args.basic_subsidy,
        citizenship=args.citizenship,
        programme_type=args.programme_type,
        working_hours_per_month=args.working_hours,
        household_size=args.household_size,
        non_earning_dependants=args.non_earning_dependants,
        output_path=args.output,
        include_ineligible=args.include_ineligible,
    )


if __name__ == "__main__":
    main()
