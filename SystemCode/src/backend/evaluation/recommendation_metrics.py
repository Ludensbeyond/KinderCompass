"""Offline, dependency-free metrics for recommendation evaluation.

Inputs are explicitly labelled evaluation records; the module never infers
ground truth from catalogue data or generates LLM judgements.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any


def hard_constraint_metrics(
    candidate_ids: Sequence[str], excluded_ids: Iterable[str], outcomes: Mapping[str, str],
) -> dict[str, Any]:
    """Score predicted exclusions against pass/fail/unknown labels.

    Fail is the positive class. Unknown labels are omitted from confusion
    counts and separately counted for retention.
    """
    excluded = set(excluded_ids)
    tp = fp = fn = tn = unknown_retained = unknown_excluded = 0
    for school_id in candidate_ids:
        outcome = outcomes.get(school_id, "unknown")
        is_excluded = school_id in excluded
        if outcome == "fail":
            tp += int(is_excluded)
            fn += int(not is_excluded)
        elif outcome == "pass":
            fp += int(is_excluded)
            tn += int(not is_excluded)
        elif outcome == "unknown":
            unknown_excluded += int(is_excluded)
            unknown_retained += int(not is_excluded)
        else:
            raise ValueError(f"Unknown hard-constraint outcome: {outcome}")
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else 0.0 if precision is not None and recall is not None else None
    unknown_total = unknown_retained + unknown_excluded
    return {
        "precision": precision, "recall": recall, "f1": f1,
        "true_positive": tp, "false_positive": fp, "false_negative": fn, "true_negative": tn,
        "unknown_retained": unknown_retained, "unknown_excluded": unknown_excluded,
        "unknown_retention_rate": unknown_retained / unknown_total if unknown_total else None,
    }


def ndcg_at_k(ranked_ids: Sequence[str], relevance: Mapping[str, float], k: int) -> float | None:
    """NDCG with exponential gain; return None when no positive judged gain exists."""
    if k <= 0:
        raise ValueError("k must be positive")
    if not relevance or not any(float(value) > 0 for value in relevance.values()):
        return None

    def dcg(values: Sequence[float]) -> float:
        return sum((2.0 ** value - 1.0) / math.log2(index + 2) for index, value in enumerate(values))

    observed = [float(relevance.get(school_id, 0)) for school_id in ranked_ids[:k]]
    ideal = sorted((float(value) for value in relevance.values()), reverse=True)[:k]
    ideal_dcg = dcg(ideal)
    return dcg(observed) / ideal_dcg if ideal_dcg else None


def kendall_tau_b(
    predicted: Sequence[str] | Mapping[str, float],
    reference_order: Sequence[str] | Mapping[str, float],
) -> float | None:
    """Kendall tau-b on shared IDs; mappings provide rank/score values and ties."""
    predicted_values = dict(predicted) if isinstance(predicted, Mapping) else {key: index for index, key in enumerate(predicted)}
    reference = dict(reference_order) if isinstance(reference_order, Mapping) else {key: index for index, key in enumerate(reference_order)}
    common = [school_id for school_id in predicted_values if school_id in reference]
    if len(common) < 2:
        return None
    concordant = discordant = tied_predicted = tied_reference = 0
    for i in range(len(common)):
        for j in range(i + 1, len(common)):
            predicted_delta = predicted_values[common[i]] - predicted_values[common[j]]
            reference_delta = reference[common[i]] - reference[common[j]]
            product = predicted_delta * reference_delta
            if product > 0:
                concordant += 1
            elif product < 0:
                discordant += 1
            elif predicted_delta == 0 and reference_delta != 0:
                tied_predicted += 1
            elif reference_delta == 0 and predicted_delta != 0:
                tied_reference += 1
    denominator = math.sqrt((concordant + discordant + tied_predicted) * (concordant + discordant + tied_reference))
    return (concordant - discordant) / denominator if denominator else None


def claim_accuracy(claims: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Compare verified claims by type without coercing values to booleans.

    Fee claims are compared as finite decimal amounts, so numeric strings and
    numbers use the same comparison. Boolean and status claims compare as
    booleans or normalized strings. Missing, malformed, or unsupported values
    are reported as unverified.
    """
    correct = incorrect = unverified = 0
    for claim in claims:
        if claim.get("verified") is not True or "predicted" not in claim or "expected" not in claim:
            unverified += 1
            continue
        predicted = claim.get("predicted")
        expected = claim.get("expected")
        if predicted is None or expected is None:
            unverified += 1
            continue
        if (isinstance(predicted, str) and not predicted.strip()) or (isinstance(expected, str) and not expected.strip()):
            unverified += 1
            continue
        if claim.get("claim_type") == "fee":
            try:
                predicted_value = Decimal(str(predicted).strip())
                expected_value = Decimal(str(expected).strip())
            except (InvalidOperation, ValueError):
                unverified += 1
                continue
            if not predicted_value.is_finite() or not expected_value.is_finite():
                unverified += 1
                continue
            matches = predicted_value == expected_value
        elif isinstance(predicted, bool) and isinstance(expected, bool):
            matches = predicted is expected
        elif isinstance(predicted, str) and isinstance(expected, str):
            matches = predicted.strip().casefold() == expected.strip().casefold()
        elif (
            isinstance(predicted, (int, float, Decimal)) and not isinstance(predicted, bool)
            and isinstance(expected, (int, float, Decimal)) and not isinstance(expected, bool)
        ):
            matches = predicted == expected
        else:
            unverified += 1
            continue
        if matches:
            correct += 1
        else:
            incorrect += 1
    verified = correct + incorrect
    return {"accuracy": correct / verified if verified else None,
            "correct": correct, "incorrect": incorrect, "unverified": unverified,
            "verified_claims": verified}


def grounded_claim_rate(claims: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Rate annotated atomic factual claims; unavailable evidence is unverified.

    Count claims marked factual and with available evidence in the denominator.
    Claims outside that denominator are reported as unverified.
    """
    supported = unsupported = unverified = 0
    for claim in claims:
        if (
            not claim.get("factual", True)
            or not claim.get("evidence_available", False)
            or claim.get("supported") not in (True, False)
        ):
            unverified += 1
        elif claim.get("supported") is True:
            supported += 1
        else:
            unsupported += 1
    evaluated = supported + unsupported
    return {"rate": supported / evaluated if evaluated else None,
            "supported": supported, "unsupported": unsupported, "unverified": unverified,
            "evaluated_claims": evaluated}


def quadratic_weighted_kappa(human: Sequence[int], judge: Sequence[int], *, scale_min: int = 1, scale_max: int = 5) -> float | None:
    """Quadratic weighted Cohen kappa for paired ordinal ratings."""
    if len(human) != len(judge):
        raise ValueError("human and judge ratings must have equal length")
    if not human:
        return None
    if scale_max <= scale_min:
        raise ValueError("rating scale must contain at least two values")
    size = scale_max - scale_min + 1
    observed = [[0.0] * size for _ in range(size)]
    human_counts = [0] * size
    judge_counts = [0] * size
    for first, second in zip(human, judge):
        if not scale_min <= first <= scale_max or not scale_min <= second <= scale_max:
            raise ValueError("rating outside configured scale")
        i, j = first - scale_min, second - scale_min
        observed[i][j] += 1
        human_counts[i] += 1
        judge_counts[j] += 1
    total = len(human)
    observed_disagreement = expected_disagreement = 0.0
    for i in range(size):
        for j in range(size):
            weight = ((i - j) / (size - 1)) ** 2
            observed_disagreement += weight * observed[i][j] / total
            expected_disagreement += weight * human_counts[i] * judge_counts[j] / (total * total)
    if expected_disagreement == 0:
        return None
    return 1 - observed_disagreement / expected_disagreement


def confidence_completeness_error(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Compare reported 0..1 confidence with weighted known/total evidence."""
    errors = []
    for record in records:
        total = float(record.get("total_weight", 0))
        if total <= 0:
            continue
        known = float(record.get("known_weight", 0))
        if known < 0 or known > total:
            raise ValueError("known_weight must be between zero and total_weight")
        expected = known / total
        reported = float(record["reported_confidence"])
        if not 0 <= reported <= 1:
            raise ValueError("reported_confidence must be between zero and one")
        errors.append(abs(expected - reported))
    return {"mean_absolute_error": sum(errors) / len(errors) if errors else None,
            "evaluated": len(errors), "interpretation": "evidence completeness only; not factual correctness or probability calibration"}


def compare_rankings(
    old_order: Sequence[str] | Mapping[str, float],
    new_order: Sequence[str] | Mapping[str, float], relevance: Mapping[str, float],
    reference_order: Sequence[str] | Mapping[str, float],
) -> dict[str, Any]:
    """Report supplied rankings on one label set; mappings encode tied ranks.

    Mapping values are rank positions where lower is better. NDCG resolves
    same-position ties by school ID; Kendall tau-b retains the ties.
    """
    def ordered_ids(order: Sequence[str] | Mapping[str, float]) -> list[str]:
        return sorted(order, key=lambda school_id: (order[school_id], school_id)) if isinstance(order, Mapping) else list(order)

    def metrics(order: Sequence[str] | Mapping[str, float]) -> dict[str, Any]:
        ids = ordered_ids(order)
        return {"ndcg_at_3": ndcg_at_k(ids, relevance, 3),
                "ndcg_at_5": ndcg_at_k(ids, relevance, 5),
                "kendall_tau_b": kendall_tau_b(order, reference_order)}
    return {"old_match_first": metrics(old_order), "new_combined_score": metrics(new_order),
            "labelled_ids": sorted(relevance)}
