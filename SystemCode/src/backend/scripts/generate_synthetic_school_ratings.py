"""Populate school_ratings.sqlite3 with demo first-party parent ratings."""

from __future__ import annotations

import argparse
import random
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from SystemCode.src.backend.domain.models import SchoolRatingRequest
from SystemCode.src.backend.repositories.school_repository import SchoolRepository
from SystemCode.src.backend.services.school_rating_service import SchoolRatingService

RELATIONSHIPS = ("enrolled", "visited", "applied", "researching")
POSITIVE_OVERALL = (3, 4, 4, 4, 5, 5, 5, 5)


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"na", "n/a", "none", "null", "-"}:
        return None
    return text


def _review_fragments(record: dict) -> list[str]:
    fragments: list[str] = []
    name = _clean(record.get("name")) or "This centre"
    pedagogy = _clean(record.get("pedagogy")) or _clean(record.get("philosophy"))
    if pedagogy and pedagogy.lower() != "general":
        fragments.append(
            f"The {pedagogy.lower()} approach comes through in daily routines and child-led activities."
        )
    languages = _clean(record.get("second_languages_offered"))
    if languages:
        langs = [part.strip() for part in languages.replace("|", ",").split(",") if part.strip()]
        if langs:
            fragments.append(
                f"We appreciate the exposure to {' and '.join(langs[:3])} through songs, stories, and classroom labels."
            )
    if _clean(record.get("spark_certified")) == "Yes":
        fragments.append("SPARK certification gave us confidence that quality standards are taken seriously.")
    food = _clean(record.get("food_offered"))
    if food:
        short = food if len(food) <= 80 else food[:77] + "..."
        fragments.append(f"Meals are thoughtfully planned ({short.lower()}), and our child eats well on full-day days.")
    hours = _clean(record.get("weekday_full_day"))
    if hours:
        fragments.append(f"Weekday hours ({hours}) fit our work schedule without feeling rushed at drop-off.")
    scheme = _clean(record.get("operator_scheme"))
    if scheme and "anchor" in scheme.lower():
        fragments.append("Being on the Anchor Operator scheme helps keep fees more manageable for our family.")
    elif scheme and scheme.lower() != "na":
        fragments.append(f"The {scheme} setup feels transparent when we compare programme options.")
    levels = record.get("care_levels") or []
    if isinstance(levels, list) and len(levels) >= 3:
        fragments.append(
            "Several age bands are offered under one roof, which makes sibling transitions easier to plan."
        )
    transport = _clean(record.get("provision_of_transport"))
    if transport == "Yes":
        fragments.append("School transport was a helpful option when both parents commute.")
    if _clean(record.get("extended_operating_hours")) == "Yes":
        fragments.append("Extended hours on busy weeks have been reliable and well supervised.")
    website = _clean(record.get("centre_website")) or _clean(record.get("website_lifesg"))
    if website:
        fragments.append("The centre website and tour matched what we saw in the classrooms.")
    fragments.extend([
        f"{name} feels welcoming; staff greet children by name and explain the day clearly to parents.",
        "Teachers communicate promptly about milestones and small incidents, which builds trust.",
        "Classrooms are bright, organised, and set up for safe exploration.",
        "Our child settled faster than we expected and looks forward to going each morning.",
        "Open houses and parent updates made the registration process feel straightforward.",
    ])
    return fragments


def compose_review(record: dict, rng: random.Random) -> str:
    pool = _review_fragments(record)
    rng.shuffle(pool)
    count = 2 if len(pool) >= 2 and rng.random() < 0.55 else 1
    text = " ".join(pool[:count])
    return text[:1000]


def random_created_at(rng: random.Random) -> str:
    days_ago = rng.randint(3, 540)
    moment = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=rng.randint(0, 20))
    return moment.isoformat()


def generate(
    *,
    catalogue_path: Path,
    database_path: Path,
    seed: int,
    replace: bool,
) -> dict[str, int]:
    rng = random.Random(seed)
    repository = SchoolRepository(catalogue_path)
    service = SchoolRatingService(database_path)

    if replace:
        connection = sqlite3.connect(database_path)
        try:
            connection.execute("DELETE FROM school_ratings")
            connection.commit()
        finally:
            connection.close()

    schools = repository.all()
    rating_ids: list[str] = []
    rating_count = 0
    for school in schools:
        payload = school.model_dump()
        reviews_for_school = rng.randint(1, 4)
        for _ in range(reviews_for_school):
            overall = rng.choice(POSITIVE_OVERALL)
            relationship = rng.choice(RELATIONSHIPS)
            review_text = compose_review(payload, rng)
            request = SchoolRatingRequest(
                anonymous_session_id=uuid.uuid4(),
                overall=overall,
                relationship=relationship,
                review_text=review_text,
                consent=True,
            )
            rating_id, _summary = service.record(school.school_id, request)
            rating_ids.append(rating_id)
            rating_count += 1

    connection = sqlite3.connect(database_path)
    try:
        for rating_id in rating_ids:
            connection.execute(
                "UPDATE school_ratings SET created_at = ? WHERE rating_id = ?",
                (random_created_at(rng), rating_id),
            )
        connection.commit()
    finally:
        connection.close()

    return {
        "schools": len(schools),
        "ratings": rating_count,
        "database": str(database_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--catalogue",
        type=Path,
        default=REPO_ROOT / "SystemCode/data/processed/kindercompass_master.json",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=REPO_ROOT / "SystemCode/src/backend/output/school_ratings.sqlite3",
    )
    parser.add_argument("--seed", type=int, default=20261020)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Clear existing ratings before generating (default: append).",
    )
    args = parser.parse_args()
    stats = generate(
        catalogue_path=args.catalogue,
        database_path=args.database,
        seed=args.seed,
        replace=args.replace,
    )
    print(
        f"Wrote {stats['ratings']} synthetic ratings across {stats['schools']} schools -> {stats['database']}"
    )


if __name__ == "__main__":
    main()
