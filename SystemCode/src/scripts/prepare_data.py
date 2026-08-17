"""Build the processed KinderCompass preschool catalogue from raw datasets."""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

import geopandas as gpd
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RAW_DIR = REPO_ROOT / "SystemCode" / "data" / "raw"
DEFAULT_OUTPUT = REPO_ROOT / "SystemCode" / "data" / "processed" / "kindercompass_master.json"


def infer_pedagogy(name: object) -> str:
    """Infer a conservative pedagogy label from a centre name."""
    text = str(name or "").lower()
    if "montessori" in text:
        return "Montessori"
    if "bilingual" in text:
        return "Bilingual"
    if "reggio" in text:
        return "Reggio Emilia"
    if "play" in text:
        return "Play-based"
    return "General"


def _require_files(raw_dir: Path) -> dict[str, Path]:
    paths = {
        "centres": raw_dir / "ListingofCentres.csv",
        "licences": raw_dir / "ListingofCentresLicenceHistory.csv",
        "services": raw_dir / "ListingofCentreServices.csv",
        "locations": raw_dir / "PreSchoolsLocation.geojson",
        "planning_areas": raw_dir / "MasterPlan2025PlanningArea.geojson",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing raw input files: " + ", ".join(missing))
    return paths


def prepare_catalogue(raw_dir: str | Path = DEFAULT_RAW_DIR) -> pd.DataFrame:
    """Load, validate, enrich, and combine all raw preschool datasets."""
    paths = _require_files(Path(raw_dir).resolve())
    centres = pd.read_csv(paths["centres"], dtype={"postal_code": "string"})
    licences = pd.read_csv(paths["licences"])
    services = pd.read_csv(paths["services"])
    locations = gpd.read_file(paths["locations"])
    planning_areas = gpd.read_file(paths["planning_areas"]).to_crs(locations.crs)

    valid_centre = centres["centre_code"].notna() & centres["centre_code"].ne("na")
    valid_tp = centres["tp_code"].notna() & centres["tp_code"].ne("na")
    centres["school_id"] = pd.NA
    centres.loc[valid_centre, "school_id"] = "CENTRE:" + centres.loc[valid_centre, "centre_code"]
    centres.loc[~valid_centre & valid_tp, "school_id"] = "TP:" + centres.loc[~valid_centre & valid_tp, "tp_code"]
    centres["identifier_type"] = valid_centre.map({True: "centre_code", False: "tp_code"})
    if centres["school_id"].isna().any():
        raise ValueError("Every centre must have either a centre_code or tp_code")
    if not centres["school_id"].is_unique:
        raise ValueError("school_id must be unique before enrichment")

    locations = gpd.sjoin(
        locations,
        planning_areas[["PLN_AREA_N", "geometry"]],
        how="left",
        predicate="within",
    ).drop(columns=["index_right"])
    locations = locations.rename(columns={"PLN_AREA_N": "town"})
    locations["centre_code"] = locations["Description"].str.extract(
        r"<th>CENTRE_CODE</th>\s*<td>(.*?)</td>"
    )
    locations = locations[
        locations["centre_code"].notna() & locations["centre_code"].ne("na")
    ].drop_duplicates(subset=["centre_code"], keep="last")

    licences = licences[
        licences["centre_code"].notna() & licences["centre_code"].ne("na")
    ]
    licences = licences.sort_values("license_issue_date").drop_duplicates(
        subset=["centre_code"], keep="last"
    )
    combined = pd.merge(centres, locations, on="centre_code", how="left", validate="many_to_one")
    combined = pd.merge(combined, licences, on="centre_code", how="left", validate="many_to_one")

    services["fees"] = pd.to_numeric(services["fees"], errors="coerce")
    services = services[
        services["centre_code"].notna() & services["centre_code"].ne("na")
    ]
    service_summary = (
        services.groupby("centre_code")
        .agg(
            base_fee=("fees", "min"),
            care_levels=("levels_offered", lambda values: sorted(set(values.dropna()))),
        )
        .reset_index()
    )
    services_json = (
        services.groupby("centre_code")[[
            "levels_offered", "type_of_service", "type_of_citizenship", "fees"
        ]]
        .apply(lambda frame: frame.to_dict(orient="records"), include_groups=False)
        .reset_index(name="services_menu")
    )
    combined = pd.merge(combined, services_json, on="centre_code", how="left")
    combined = pd.merge(combined, service_summary, on="centre_code", how="left")
    combined["postal_code"] = pd.to_numeric(combined["postal_code"], errors="coerce").astype("Int64")
    combined["operator_scheme"] = combined["scheme_type"]
    combined["philosophy"] = combined["centre_name_x"].apply(infer_pedagogy)
    combined["pedagogy"] = combined["centre_name_x"].apply(infer_pedagogy)

    vacancy_columns = [column for column in combined.columns if "_vacancy_" in column]
    combined["has_location"] = combined["geometry"].notna()
    combined["has_fee_data"] = combined["base_fee"].notna()
    combined["has_licence_data"] = combined["license_issue_date"].notna()
    combined["has_vacancy_data"] = combined[vacancy_columns].notna().any(axis=1)
    if not combined["school_id"].is_unique:
        raise ValueError("Enrichment produced duplicate school_id values")
    combined["geometry"] = combined["geometry"].astype(str)
    return combined


def write_catalogue(catalogue: pd.DataFrame, output: str | Path = DEFAULT_OUTPUT) -> Path:
    """Atomically write a processed catalogue as record-oriented JSON."""
    destination = Path(output).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=destination.name + ".", suffix=".tmp", dir=destination.parent
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        catalogue.to_json(temporary, orient="records")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    catalogue = prepare_catalogue(args.raw_dir)
    destination = write_catalogue(catalogue, args.output)
    print(f"Prepared {len(catalogue):,} schools -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
