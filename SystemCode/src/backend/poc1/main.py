"""HTTP API for the KinderCompass PoC 1 pipeline."""

from __future__ import annotations

import datetime as dt
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel, Field


REPO_ROOT = Path(__file__).resolve().parents[4]
POC_SRC = REPO_ROOT / "SystemCode" / "notebooks" / "poc1" / "src"
POC_ENV = REPO_ROOT / "SystemCode" / "notebooks" / "poc1" / ".env"
if str(POC_SRC) not in sys.path:
    sys.path.insert(0, str(POC_SRC))

# PoC 1 keeps its Neo4j connection details beside its notebooks. Loading this
# explicit path makes backend startup independent of the terminal's directory.
load_dotenv(POC_ENV)

from stage1.runner import run_from_profile  # noqa: E402
from stage1.nlp_mapper import merge_preference_profile, summarize_profile  # noqa: E402
from stage1.conversation import update_conversation  # noqa: E402
from stage1.web_rag import load_json  # noqa: E402
from stage1.proximity import geocode_postal_code  # noqa: E402
from stage2.engine import evaluate_shortlist  # noqa: E402
from stage3.optimizer import calculate_home_to_preschool  # noqa: E402
from stage3.optimizer import haversine_km  # noqa: E402
from stage3.locations import attach_locations, load_preschool_locations  # noqa: E402


app = FastAPI(title="KinderCompass API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    message: str | None = Field(default=None, min_length=2, max_length=500)
    profile: dict[str, Any] | None = None
    town: str | None = Field(default=None, max_length=30)
    within_1km: bool = False
    home_postal_code: str | None = Field(default=None, pattern=r"^\d{6}$")
    radius_km: float | None = Field(default=None, gt=0)


class PreferenceRequest(BaseModel):
    message: str = Field(min_length=2, max_length=500)
    profile: dict[str, Any] | None = None
    selected_centres: list[dict[str, Any]] = Field(default_factory=list)
    eligible_centres: list[dict[str, Any]] = Field(default_factory=list)
    home_postal_code: str | None = Field(default=None, pattern=r"^\d{6}$")


class FamilyDetails(BaseModel):
    dob: dt.date
    admission_date: dt.date
    gross_household_income: float = Field(ge=0)
    basic_subsidy: float = Field(ge=0)


class EvaluateRequest(BaseModel):
    shortlist: list[dict[str, Any]]
    family: FamilyDetails
    include_ineligible: bool = False
    trace_id: str | None = Field(default=None, max_length=36)


class RouteRequest(BaseModel):
    eligible_centres: list[dict[str, Any]]
    selected_code: str = Field(min_length=1)
    home_postal_code: str = Field(pattern=r"^\d{6}$")


class GeocodeRequest(BaseModel):
    postal_code: str = Field(pattern=r"^\d{6}$")


class DistanceRequest(BaseModel):
    centres: list[dict[str, Any]]
    home_postal_code: str = Field(pattern=r"^\d{6}$")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/search")
def search(request: SearchRequest) -> dict[str, Any]:
    """Stage 1: query schools only after explicit profile confirmation."""
    try:
        profile = request.profile or {}
        if request.message:
            profile = merge_preference_profile(profile, request.message)
        town = request.home_postal_code or request.town
        centres, stage_trace = run_from_profile(profile, town=town, within_1km=request.within_1km, radius_km=request.radius_km, include_trace=True)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    trace_id = str(uuid.uuid4())
    return {
        "message": f"I found {len(centres)} centres matching those preferences.",
        "centres": centres,
        "profile": profile,
        "understood": summarize_profile(profile),
        "trace": {"trace_id": trace_id, "ranking_method": "verified_match_then_evidence_confidence", **stage_trace},
    }


@app.post("/api/preferences")
def preferences(request: PreferenceRequest) -> dict[str, Any]:
    """Update conversational preferences without querying Neo4j."""
    eligible = request.eligible_centres
    if eligible and request.home_postal_code:
        eligible = _attach_home_distances(eligible, request.home_postal_code)
    configured_index = os.getenv("WEB_RAG_INDEX_PATH", "").strip()
    index_path = (
        Path(configured_index)
        if configured_index
        else REPO_ROOT / "SystemCode" / "notebooks" / "poc1" / "output" / "web_rag_pilot_index.json"
    )
    try:
        web_rag_index = load_json(index_path) if index_path.is_file() else None
    except (OSError, ValueError):
        web_rag_index = None
    return update_conversation(
        request.profile, request.message, request.selected_centres, eligible, web_rag_index
    )


@app.post("/api/evaluate")
def evaluate(request: EvaluateRequest) -> dict[str, Any]:
    """Stage 2: evaluate eligibility and estimated monthly cost."""
    try:
        results = evaluate_shortlist(
            request.shortlist,
            dob=request.family.dob,
            admission_date=request.family.admission_date,
            ghi=request.family.gross_household_income,
            basic_subsidy=request.family.basic_subsidy,
            include_ineligible=request.include_ineligible,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    eligible_count = sum(item.get("eligible") is True for item in results)
    return {
        "eligible_count": eligible_count,
        "centres": results,
        "trace": {
            "trace_id": request.trace_id,
            "stage2_input": len(request.shortlist),
            "stage2_eligible": eligible_count,
            "stage2_excluded": len(request.shortlist) - eligible_count,
        },
    }


@app.post("/api/geocode")
def geocode(request: GeocodeRequest) -> dict[str, Any]:
    """Resolve a six-digit postal code for immediate map feedback."""
    try:
        coordinates = geocode_postal_code(request.postal_code)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"name": "Home", "type": "home", **coordinates}


@app.post("/api/distances")
def distances(request: DistanceRequest) -> dict[str, Any]:
    """Calculate independent home distances for a batch of preschools."""
    results = _attach_home_distances(request.centres, request.home_postal_code)
    return {"distances": [
        {"school_id": centre.get("school_id") or centre.get("centre_code"), "distance_km": centre["distance_km"]}
        for centre in results if centre.get("distance_km") is not None
    ]}


def _attach_home_distances(centres: list[dict[str, Any]], home_postal_code: str) -> list[dict[str, Any]]:
    """Calculate backend-owned home distances and attach them to centre records."""
    try:
        home = geocode_postal_code(home_postal_code)
        location_file = REPO_ROOT / "SystemCode" / "data" / "raw" / "PreSchoolsLocation.geojson"
        locations = load_preschool_locations(location_file)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    results = []
    for centre in centres:
        location = locations.get(centre.get("centre_code"))
        results.append({
            **centre,
            "distance_km": round(haversine_km(home, location), 3) if location else None,
        })
    return results


@app.post("/api/route")
def route(request: RouteRequest) -> dict[str, Any]:
    """Stage 3: calculate the distance from home to one eligible preschool."""
    by_code = {
        (centre.get("school_id") or centre.get("centre_code")): centre
        for centre in request.eligible_centres
        if centre.get("eligible") is True
    }
    if request.selected_code not in by_code:
        raise HTTPException(status_code=422, detail="The selected centre is absent or ineligible")

    try:
        location_file = REPO_ROOT / "SystemCode" / "data" / "raw" / "PreSchoolsLocation.geojson"
        selected = by_code[request.selected_code]
        schools = attach_locations([selected], load_preschool_locations(location_file))
        home_coordinates = geocode_postal_code(request.home_postal_code)
        home = {"type": "home", "name": "Home", **home_coordinates}
        result = calculate_home_to_preschool(home, schools[0])
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return result
