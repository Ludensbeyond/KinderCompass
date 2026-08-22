"""HTTP API for the KinderCompass PoC 1 pipeline."""

from __future__ import annotations

import sys
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[3]
POC_SRC = REPO_ROOT / "SystemCode" / "src" / "backend" / "pipeline"
POC_ENV = REPO_ROOT / ".env"
if str(POC_SRC) not in sys.path:
    sys.path.insert(0, str(POC_SRC))

# Load the repository-level configuration independently of the terminal's
# current directory.
load_dotenv(POC_ENV)

from stage1.runner import run_from_profile  # noqa: E402
from stage1.nlp_mapper import merge_preference_profile, summarize_profile  # noqa: E402
from stage1.proximity import geocode_postal_code  # noqa: E402
from stage1.dialogue_manager import propose_constraint_relaxation  # noqa: E402
from SystemCode.src.backend.domain.models import (  # noqa: E402
    DistanceRequest, DistanceResponse, EvaluateRequest, EvaluationResponse,
    FeedbackRequest, FeedbackResponse,
    GeocodeRequest, GeocodeResponse, HealthResponse, PreferenceRequest,
    PreferenceResponse, ProgrammeEstimateRequest, ProgrammeEstimateResponse,
    RouteRequest, RouteResponse, SearchRequest, SearchResponse,
)
from SystemCode.src.backend.repositories.school_repository import (  # noqa: E402
    SchoolNotFoundError, SchoolRepository,
)
from SystemCode.src.backend.repositories.policy_repository import PolicyUnavailableError  # noqa: E402
from SystemCode.src.backend.services.evaluation_service import (  # noqa: E402
    EvaluationService, ProgrammeUnavailableError,
)
from SystemCode.src.backend.services.location_service import LocationService  # noqa: E402
from SystemCode.src.backend.services.preference_service import PreferenceService  # noqa: E402
from SystemCode.src.backend.services.feedback_service import (  # noqa: E402
    FeedbackSchoolMismatchError, FeedbackService, FeedbackSnapshotNotFoundError,
)


app = FastAPI(title="KinderCompass API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


SCHOOL_REPOSITORY = SchoolRepository(REPO_ROOT / "SystemCode/data/processed/kindercompass_master.json")
EVALUATION_SERVICE = EvaluationService(SCHOOL_REPOSITORY)
LOCATION_SERVICE = LocationService(
    SCHOOL_REPOSITORY, REPO_ROOT / "SystemCode/data/raw/PreSchoolsLocation.geojson"
)
PREFERENCE_SERVICE = PreferenceService(
    SCHOOL_REPOSITORY, EVALUATION_SERVICE, LOCATION_SERVICE, REPO_ROOT
)
FEEDBACK_SERVICE = FeedbackService(
    REPO_ROOT / "SystemCode/src/backend/output/recommendation_feedback.sqlite3"
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/search", response_model=SearchResponse)
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
    relaxation = propose_constraint_relaxation(profile) if not centres else None
    if relaxation:
        profile = {**profile, "pending_relaxation": relaxation}
    response_message = (
        relaxation["question"] if relaxation
        else f"I found {len(centres)} centres matching those preferences."
    )
    return {
        "message": response_message,
        "centres": centres,
        "profile": profile,
        "understood": summarize_profile(profile),
        "trace": {"trace_id": trace_id, "ranking_method": "verified_match_then_evidence_confidence", **stage_trace},
    }


@app.post("/api/preferences", response_model=PreferenceResponse)
def preferences(request: PreferenceRequest) -> dict[str, Any]:
    try:
        if "closest" in request.message.lower() and not request.home_postal_code:
            raise HTTPException(status_code=422, detail="Enter a six-digit home postal code before asking for the nearest preschool.")
        return PREFERENCE_SERVICE.handle(
            message=request.message, profile=request.profile,
            selected_school_ids=request.selected_school_ids,
            eligible_school_ids=request.eligible_school_ids,
            family=request.family, home_postal_code=request.home_postal_code,
        )
    except SchoolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/evaluate", response_model=EvaluationResponse)
def evaluate(request: EvaluateRequest) -> EvaluationResponse:
    """Stage 2: evaluate eligibility and estimated monthly cost."""
    try:
        results = EVALUATION_SERVICE.evaluate(
            request.school_ids, request.profile, request.family,
            include_ineligible=request.include_ineligible,
        )
    except SchoolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (PolicyUnavailableError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    eligible_count = sum(item.get("eligible") is True for item in results)
    try:
        FEEDBACK_SERVICE.record_snapshot(
            request.trace_id,
            results,
            catalogue_version=SCHOOL_REPOSITORY.catalogue_version,
        )
    except (OSError, sqlite3.Error, ValueError) as exc:
        raise HTTPException(
            status_code=503, detail=f"Recommendation snapshot could not be recorded: {exc}"
        ) from exc
    return EvaluationResponse(**{
        "eligible_count": eligible_count,
        "centres": results,
        "trace": {
            "trace_id": request.trace_id,
            "stage2_input": len(request.school_ids),
            "stage2_eligible": eligible_count,
            "stage2_excluded": len(request.school_ids) - eligible_count,
            "catalogue_version": SCHOOL_REPOSITORY.catalogue_version,
        },
    })


@app.post("/api/feedback", response_model=FeedbackResponse)
def feedback(request: FeedbackRequest) -> FeedbackResponse:
    """Record explicit, consented feedback for an immutable recommendation snapshot."""
    try:
        event_id = FEEDBACK_SERVICE.record_feedback(request)
    except FeedbackSnapshotNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FeedbackSchoolMismatchError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (OSError, sqlite3.Error) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return FeedbackResponse(event_id=event_id, status="recorded")


@app.post(
    "/api/schools/{school_id}/programme-estimate",
    response_model=ProgrammeEstimateResponse,
)
def programme_estimate(
    school_id: str, request: ProgrammeEstimateRequest
) -> ProgrammeEstimateResponse:
    """Recalculate one school's fees for an exact programme option."""
    try:
        result = EVALUATION_SERVICE.estimate_programme(
            school_id, request.programme_id, request.family
        )
    except SchoolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ProgrammeUnavailableError, PolicyUnavailableError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ProgrammeEstimateResponse(**result)


@app.post("/api/geocode", response_model=GeocodeResponse)
def geocode(request: GeocodeRequest) -> dict[str, Any]:
    """Resolve a six-digit postal code for immediate map feedback."""
    try:
        coordinates = geocode_postal_code(request.postal_code)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"name": "Home", "type": "home", **coordinates}


@app.post("/api/distances", response_model=DistanceResponse)
def distances(request: DistanceRequest) -> DistanceResponse:
    """Calculate independent home distances for a batch of preschools."""
    try:
        return DistanceResponse(distances=LOCATION_SERVICE.distances(
            request.school_ids, request.home_postal_code
        ))
    except SchoolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/route", response_model=RouteResponse)
def route(request: RouteRequest) -> dict[str, Any]:
    """Stage 3: calculate the distance from home to one eligible preschool."""
    try:
        return LOCATION_SERVICE.route(request.school_id, request.home_postal_code)
    except SchoolNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
