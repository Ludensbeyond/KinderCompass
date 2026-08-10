"""KinderCompass Stage 1 -> Stage 2 application flow."""

from __future__ import annotations

import datetime as dt
from numbers import Real
from typing import Any

from stage1.runner import run_from_text
from stage2.engine import evaluate_shortlist


def search_and_evaluate(
    text: str,
    *,
    dob: dt.date,
    admission_date: dt.date,
    ghi: Real,
    basic_subsidy: Real,
    town: str | None = None,
    include_ineligible: bool = False,
) -> list[dict[str, Any]]:
    """Search Neo4j in Stage 1 and pass that shortlist into Stage 2."""
    shortlist = run_from_text(text=text, town=town)
    return evaluate_shortlist(
        shortlist,
        dob=dob,
        admission_date=admission_date,
        ghi=ghi,
        basic_subsidy=basic_subsidy,
        include_ineligible=include_ineligible,
    )
