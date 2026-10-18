"""Offline, dependency-free metrics for recommendation evaluation.

Inputs are explicitly labelled evaluation records; the module never infers
ground truth from catalogue data or generates LLM judgements.
"""

from __future__ import annotations

import math
import datetime as dt
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any


RELEVANCE_THRESHOLD = 2
RELEVANCE_SCALE = {0: "not relevant", 1: "marginally relevant", 2: "relevant", 3: "highly relevant"}
RANKING_K = 3


def hard_constraint_metrics(
    candidate_ids: Sequence[str], excluded_ids: Iterable[str], outcomes: Mapping[str, str],
) -> dict[str, Any]:
    """Score predicted exclusions against pass/fail/unknown labels.

    Fail is the positive class. Explicit unknown and absent labels are omitted
    from confusion counts and counted separately so the states are not merged.
    """
    if any(not isinstance(item, str) or not item.strip() for item in candidate_ids):
        raise ValueError("candidate_ids must contain non-empty school IDs")
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("candidate_ids must be unique family–preschool pairs")
    excluded = set(excluded_ids)
    if not excluded.issubset(set(candidate_ids)):
        raise ValueError("excluded_ids must be drawn from candidate_ids")
    tp = fp = fn = tn = unknown_retained = unknown_excluded = missing_retained = missing_excluded = 0
    for school_id in candidate_ids:
        is_excluded = school_id in excluded
        if school_id not in outcomes:
            missing_excluded += int(is_excluded)
            missing_retained += int(not is_excluded)
            continue
        outcome = outcomes[school_id]
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
    f1_denominator = 2 * tp + fp + fn
    f1 = 2 * tp / f1_denominator if f1_denominator else None
    unknown_total = unknown_retained + unknown_excluded
    missing_total = missing_retained + missing_excluded
    confirmed_failures = tp + fn
    confirmed_passes = fp + tn
    return {
        "precision": precision, "recall": recall, "f1": f1,
        "precision_denominator": tp + fp, "recall_denominator": tp + fn,
        "f1_denominator": f1_denominator,
        "true_positive": tp, "false_positive": fp, "false_negative": fn, "true_negative": tn,
        "confirmed_failure_violation_rate": fn / confirmed_failures if confirmed_failures else None,
        "confirmed_failure_denominator": confirmed_failures,
        "confirmed_pass_over_exclusion_rate": fp / confirmed_passes if confirmed_passes else None,
        "confirmed_pass_denominator": confirmed_passes,
        "unknown_retained": unknown_retained, "unknown_excluded": unknown_excluded,
        "unknown_denominator": unknown_total,
        "unknown_retention_rate": unknown_retained / unknown_total if unknown_total else None,
        "unlabelled_retained": missing_retained, "unlabelled_excluded": missing_excluded,
        "unlabelled_denominator": missing_total,
    }


def _unique_ids(ids: Sequence[str]) -> tuple[list[str], int]:
    unique = list(dict.fromkeys(ids))
    return unique, len(ids) - len(unique)


def evaluate_ranking_case(
    ranked_ids: Sequence[str],
    relevance: Mapping[str, float],
    *,
    case_id: str | None = None,
    reference_case_id: str | None = None,
    reference_ids: Sequence[str] | None = None,
    reference_order: Sequence[str] | Mapping[str, float] | None = None,
    hard_constraint_outcomes: Mapping[str, str] | None = None,
    eligibility: Mapping[str, str] | None = None,
    labels_complete: bool | None = None,
    k: int = RANKING_K,
) -> dict[str, Any]:
    """Evaluate one returned order against same-case graded labels.

    Relevance is graded 0..3; >=2 is binary relevant. Duplicate result IDs
    keep their first occurrence. Unlabelled results in the top k make metrics
    requiring binary decisions undefined. NDCG uses available labels for its
    ideal order; recall requires complete labels for the declared reference
    pool. Empty labels and zero-IDCG cases are explicitly excluded.
    """
    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("case_id must be a non-empty scenario ID")
    if not isinstance(reference_case_id, str) or not reference_case_id.strip():
        raise ValueError(f"reference_case_id must be a non-empty ID for case {case_id!r}")
    if k <= 0:
        raise ValueError("k must be positive")
    if case_id != reference_case_id:
        raise ValueError(f"ranking case {case_id!r} does not match reference case {reference_case_id!r}")
    if labels_complete is not None and not isinstance(labels_complete, bool):
        raise ValueError(f"labels_complete must be true, false, or absent for case {case_id!r}")
    if reference_ids is not None:
        if isinstance(reference_ids, (str, bytes)):
            raise ValueError(f"reference_ids must be a list of school IDs for case {case_id!r}")
        if any(not isinstance(item, str) or not item.strip() for item in reference_ids):
            raise ValueError(f"reference_ids contains a missing or empty school ID for case {case_id!r}")
        if len(set(reference_ids)) != len(reference_ids):
            raise ValueError(f"reference_ids contains duplicate school IDs for case {case_id!r}")
    for school_id, value in relevance.items():
        if isinstance(value, bool) or not isinstance(value, int) or value not in RELEVANCE_SCALE:
            raise ValueError(f"invalid relevance label for {school_id!r}: {value!r}; expected an integer from 0 to 3")

    reference_id_set = set(reference_ids) if reference_ids is not None else None
    if reference_id_set is not None and labels_complete is not False:
        missing_reference_labels = sorted(reference_id_set - set(relevance))
        if missing_reference_labels:
            declaration = "labels_complete=true" if labels_complete is True else "a complete reference pool"
            raise ValueError(
                f"case {case_id!r} declares {declaration} but has no relevance labels for "
                f"reference IDs: {missing_reference_labels}"
            )
        omitted_relevant_ids = sorted(
            school_id for school_id, value in relevance.items()
            if value >= RELEVANCE_THRESHOLD and school_id not in reference_id_set
        )
        if omitted_relevant_ids:
            raise ValueError(
                f"case {case_id!r} declares a complete reference pool that omits known relevant IDs: "
                f"{omitted_relevant_ids}"
            )

    judged_relevance = (
        dict(relevance) if reference_id_set is None
        else {school_id: value for school_id, value in relevance.items() if school_id in reference_id_set}
    )
    # A benchmark must never award relevance to a school independently labelled
    # as violating a hard constraint or as ineligible for the family.
    hard_outcomes = hard_constraint_outcomes or {}
    eligibility_outcomes = eligibility or {}
    if set(hard_outcomes.values()) - {"pass", "fail", "unknown"}:
        raise ValueError("hard constraint outcomes must be pass, fail, or unknown")
    if set(eligibility_outcomes.values()) - {"eligible", "ineligible", "unknown"}:
        raise ValueError("eligibility outcomes must be eligible, ineligible, or unknown")
    unsafe_ids = {
        school_id for school_id, outcome in hard_outcomes.items()
        if outcome == "fail"
    } | {
        school_id for school_id, outcome in eligibility_outcomes.items()
        if outcome == "ineligible"
    }
    adjusted_relevance = dict(judged_relevance)
    for school_id in unsafe_ids & (reference_id_set if reference_id_set is not None else set(relevance)):
        adjusted_relevance[school_id] = 0
    ids, duplicate_count = _unique_ids(ranked_ids)
    top_ids = ids[:k]
    missing_top_labels = [school_id for school_id in top_ids if school_id not in judged_relevance]
    top_five_ids = ids[:5]
    missing_top_five_labels = [school_id for school_id in top_five_ids if school_id not in judged_relevance]
    available_relevant = sum(value >= RELEVANCE_THRESHOLD for value in adjusted_relevance.values())
    if reference_id_set is None:
        # Without a reference pool, only an explicit completeness assertion
        # makes the supplied relevance map a valid recall denominator.
        label_pool_complete = labels_complete
    else:
        # The declared pool gives a denominator, but every member still needs
        # a label; an explicit false declaration keeps the case incomplete.
        label_pool_complete = (
            False if labels_complete is False
            else all(school_id in relevance for school_id in reference_id_set)
        )

    if reference_id_set == set() or (reference_id_set is None and labels_complete is True and not relevance):
        reference_data_status = "empty_reference_pool"
    elif reference_id_set is None and labels_complete is None:
        reference_data_status = "missing_reference_data"
    elif label_pool_complete is True:
        reference_data_status = "complete_reference_labels"
    else:
        reference_data_status = "incomplete_reference_labels"

    missing_reference_reason = (
        "empty_reference_pool" if reference_data_status == "empty_reference_pool"
        else "reference_completeness_not_declared" if reference_data_status == "missing_reference_data"
        else "missing_reference_labels"
    )

    ndcg = None
    ndcg_exclusion = None
    if not judged_relevance:
        ndcg_exclusion = missing_reference_reason
    elif missing_top_labels:
        ndcg_exclusion = "unlabelled_result_in_top_k"
    else:
        ndcg = ndcg_at_k(top_ids, adjusted_relevance, k)
        if ndcg is None:
            ndcg_exclusion = "idcg_zero_no_positive_relevance"

    ndcg5 = None
    ndcg5_exclusion = None
    if not adjusted_relevance:
        ndcg5_exclusion = missing_reference_reason
    elif missing_top_five_labels:
        ndcg5_exclusion = "unlabelled_result_in_top_k"
    else:
        ndcg5 = ndcg_at_k(top_five_ids, adjusted_relevance, 5)
        if ndcg5 is None:
            ndcg5_exclusion = "idcg_zero_no_positive_relevance"

    tau_b = None
    tau_exclusion = None
    if reference_order is None:
        tau_exclusion = "reference_ranking_not_provided"
    else:
        reference_values = dict(reference_order) if isinstance(reference_order, Mapping) else None
        ref_ids = list(reference_order) if reference_values is not None else list(reference_order)
        if any(not isinstance(item, str) or not item.strip() for item in ref_ids):
            raise ValueError(f"reference_order contains a missing or empty school ID for case {case_id!r}")
        if reference_values is None and len(set(ref_ids)) != len(ref_ids):
            raise ValueError(f"reference_order contains duplicate school IDs for case {case_id!r}")
        if reference_values is not None and any(
            isinstance(rank, bool) or not isinstance(rank, (int, float)) or not math.isfinite(rank)
            for rank in reference_values.values()
        ):
            raise ValueError(f"reference_order ranks must be finite numbers for case {case_id!r}")
        safe_ids = [school_id for school_id in ids if school_id not in unsafe_ids]
        safe_reference = (
            {school_id: rank for school_id, rank in reference_values.items() if school_id not in unsafe_ids}
            if reference_values is not None
            else [school_id for school_id in ref_ids if school_id not in unsafe_ids]
        )
        tau_b = kendall_tau_b(safe_ids, safe_reference)
        if tau_b is None:
            tau_exclusion = "fewer_than_two_comparable_items_or_no_untied_pairs"

    binary_exclusion = missing_reference_reason if not judged_relevance else (
        "unlabelled_result_in_top_k" if missing_top_labels else None
    )
    precision = recall = hit_rate = None
    recall_exclusion = binary_exclusion
    if binary_exclusion is None:
        relevant_results = [school_id for school_id in top_ids if adjusted_relevance[school_id] >= RELEVANCE_THRESHOLD]
        precision = len(relevant_results) / len(top_ids) if top_ids else 0.0
        hit_rate = float(bool(relevant_results))
        if label_pool_complete is None:
            recall_exclusion = "reference_completeness_not_declared"
        elif not label_pool_complete:
            recall_exclusion = "incomplete_reference_labels"
        elif reference_data_status == "empty_reference_pool":
            recall_exclusion = "empty_reference_pool"
        elif available_relevant == 0:
            recall_exclusion = "no_relevant_reference_schools"
        else:
            recall = len(relevant_results) / available_relevant

    mrr = None
    mrr_exclusion = None
    if not judged_relevance:
        mrr_exclusion = missing_reference_reason
    else:
        for index, school_id in enumerate(ids):
            if school_id not in judged_relevance:
                mrr_exclusion = "unlabelled_result_before_first_relevant"
                break
            if adjusted_relevance[school_id] >= RELEVANCE_THRESHOLD:
                mrr = 1.0 / (index + 1)
                break
        else:
            mrr = 0.0

    return {
        "case_id": case_id,
        "k": k,
        "relevance_scale": RELEVANCE_SCALE,
        "binary_relevance_threshold": RELEVANCE_THRESHOLD,
        "ranking_ids": ids,
        "duplicate_result_ids_removed": duplicate_count,
        "labelled_ids": len(judged_relevance),
        "unlabelled_top_k_ids": missing_top_labels,
        "unlabelled_top_5_ids": missing_top_five_labels,
        "hard_constraint_or_eligibility_violations_zeroed_for_ranking": sorted(unsafe_ids),
        "reference_relevance": judged_relevance,
        "relevance_after_safety_override": adjusted_relevance,
        "reference_labels_complete": label_pool_complete,
        "reference_data_status": reference_data_status,
        "metrics": {
            "ndcg_at_3": {"value": ndcg, "denominator": 1 if ndcg is not None else 0,
                           "excluded": int(ndcg is None), "exclusion_reason": ndcg_exclusion,
                           "ideal_basis": "all available relevance labels"},
            "ndcg_at_5": {"value": ndcg5, "denominator": 1 if ndcg5 is not None else 0,
                           "excluded": int(ndcg5 is None), "exclusion_reason": ndcg5_exclusion,
                           "ideal_basis": "all available relevance labels"},
            "kendall_tau_b": {"value": tau_b, "denominator": 1 if tau_b is not None else 0,
                              "excluded": int(tau_b is None), "exclusion_reason": tau_exclusion,
                              "comparable_items": len((set(ids) & set(ref_ids)) - unsafe_ids) if reference_order is not None else 0},
            "precision_at_3": {"value": precision, "denominator": 1 if precision is not None else 0,
                               "excluded": int(precision is None), "exclusion_reason": binary_exclusion,
                               "items_in_denominator": len(top_ids) if precision is not None else 0},
            "recall_at_3": {"value": recall, "denominator": 1 if recall is not None else 0,
                            "excluded": int(recall is None), "exclusion_reason": recall_exclusion,
                            "relevant_reference_schools": available_relevant},
            "mrr": {"value": mrr, "denominator": 1 if mrr is not None else 0,
                    "excluded": int(mrr is None), "exclusion_reason": mrr_exclusion},
            "hit_rate_at_3": {"value": hit_rate, "denominator": 1 if hit_rate is not None else 0,
                               "excluded": int(hit_rate is None), "exclusion_reason": binary_exclusion},
        },
    }


def aggregate_case_metrics(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Macro-average defined per-case metrics and expose each denominator."""
    names = ("ndcg_at_3", "ndcg_at_5", "kendall_tau_b", "precision_at_3", "recall_at_3", "mrr", "hit_rate_at_3")
    aggregates = {}
    for name in names:
        values = [case["metrics"][name]["value"] for case in cases
                  if case["metrics"][name]["value"] is not None]
        aggregates[name] = {
            "value": sum(values) / len(values) if values else None,
            "denominator": len(values),
            "excluded_cases": len(cases) - len(values),
            "aggregation": "macro mean over defined per-case values",
        }
    return {"case_count": len(cases), "metrics": aggregates}


def eligibility_violation_metrics(
    recommended_ids: Sequence[str], eligibility: Mapping[str, str],
) -> dict[str, Any]:
    """Measure recommendations of confirmed ineligible schools; unknown stays separate."""
    ids, duplicate_count = _unique_ids(recommended_ids)
    invalid = {value for value in eligibility.values()} - {"eligible", "ineligible", "unknown"}
    if invalid:
        raise ValueError(f"invalid eligibility labels: {sorted(invalid)}")
    counts = {"eligible": 0, "ineligible": 0, "unknown": 0, "unlabelled": 0}
    for school_id in ids:
        counts[eligibility.get(school_id, "unlabelled")] += 1
    known = counts["eligible"] + counts["ineligible"]
    return {
        **counts,
        "confirmed_ineligible_recommendation_rate": counts["ineligible"] / known if known else None,
        "known_eligibility_denominator": known,
        "unknown_recommendation_rate": counts["unknown"] / len(ids) if ids else None,
        "unknown_denominator": len(ids),
        "unlabelled_recommendations": counts["unlabelled"],
        "duplicate_result_ids_removed": duplicate_count,
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
    if not isinstance(predicted, Mapping) and len(set(predicted)) != len(predicted):
        raise ValueError("predicted order contains duplicate IDs")
    if not isinstance(reference_order, Mapping) and len(set(reference_order)) != len(reference_order):
        raise ValueError("reference order contains duplicate IDs")
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
        reference = claim.get("reference")
        has_reference = (
            isinstance(reference, Mapping)
            and bool(str(reference.get("source", "")).strip())
            and bool(str(reference.get("reference", "")).strip())
        )
        if claim.get("verified") is not True or not has_reference or "predicted" not in claim or "expected" not in claim:
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
        numeric_claim = claim.get("claim_type") in {"fee", "subsidy", "age_months", "numeric"}
        if numeric_claim:
            if "unit" in claim or "expected_unit" in claim:
                unit = claim.get("unit")
                expected_unit = claim.get("expected_unit", unit)
                if not isinstance(unit, str) or not isinstance(expected_unit, str) or unit.strip().casefold() != expected_unit.strip().casefold():
                    unverified += 1
                    continue
            try:
                predicted_value = Decimal(str(predicted).strip())
                expected_value = Decimal(str(expected).strip())
            except (InvalidOperation, ValueError):
                unverified += 1
                continue
            if not predicted_value.is_finite() or not expected_value.is_finite():
                unverified += 1
                continue
            try:
                tolerance = Decimal(str(claim.get("tolerance", 0)))
            except (InvalidOperation, ValueError):
                unverified += 1
                continue
            if not tolerance.is_finite() or tolerance < 0:
                unverified += 1
                continue
            matches = abs(predicted_value - expected_value) <= tolerance
        elif claim.get("claim_type") in {"date", "admission_date"}:
            try:
                predicted_date = dt.date.fromisoformat(str(predicted).strip()[:10])
                expected_date = dt.date.fromisoformat(str(expected).strip()[:10])
            except (ValueError, TypeError):
                unverified += 1
                continue
            matches = predicted_date == expected_date
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
    supported = contradicted = unsupported = unverifiable = not_applicable = non_factual = 0
    per_claim = []
    for claim in claims:
        if not claim.get("factual", True):
            non_factual += 1
            per_claim.append({"claim_id": claim.get("claim_id"), "status": "non_factual_excluded"})
            continue
        evidence = claim.get("evidence")
        has_claim_identity = (
            isinstance(claim.get("claim_id"), str) and bool(claim["claim_id"].strip())
            and isinstance(claim.get("claim"), str) and bool(claim["claim"].strip())
        )
        has_evidence_ref = (
            isinstance(evidence, Mapping)
            and bool(str(evidence.get("source", "")).strip())
            and bool(str(evidence.get("reference", "")).strip())
        )
        status = claim.get("status")
        if status is None and claim.get("supported") in (True, False):
            status = "supported" if claim["supported"] else "unsupported"
        if status == "not_applicable":
            not_applicable += 1
            assessed_status = "not_applicable"
        elif not has_claim_identity or not claim.get("evidence_available", False) or not has_evidence_ref or status == "unverifiable":
            unverifiable += 1
            assessed_status = "unverifiable"
        elif status == "supported":
            supported += 1
            assessed_status = "supported"
        elif status == "contradicted":
            contradicted += 1
            assessed_status = "contradicted"
        elif status == "unsupported":
            unsupported += 1
            assessed_status = "unsupported"
        else:
            unverifiable += 1
            assessed_status = "unverifiable"
        per_claim.append({
            "claim_id": claim.get("claim_id"), "claim": claim.get("claim"),
            "status": assessed_status, "evidence": evidence if has_evidence_ref else None,
        })
    evaluated = supported + contradicted + unsupported
    return {"rate": supported / evaluated if evaluated else None,
            "supported": supported, "contradicted": contradicted, "unsupported": unsupported,
            "unverifiable": unverifiable, "unverified": unverifiable, "not_applicable": not_applicable,
            "non_factual_excluded": non_factual,
            "evaluated_claims": evaluated, "per_claim": per_claim}


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


def paired_rating_agreement(records: Sequence[Mapping[str, Any]], *, scale_min: int = 1, scale_max: int = 5) -> dict[str, Any]:
    """Summarize preserved human/LLM ordinal ratings by rubric dimension."""
    grouped: dict[str, list[tuple[int, int]]] = {}
    seen: set[tuple[str, str]] = set()
    for record in records:
        case_id, dimension = record.get("case_id"), record.get("dimension")
        if not isinstance(case_id, str) or not case_id.strip() or not isinstance(dimension, str) or not dimension.strip():
            raise ValueError("paired ratings require non-empty case_id and dimension")
        pair_key = (case_id, dimension)
        if pair_key in seen:
            raise ValueError(f"duplicate paired rating for {case_id!r}/{dimension!r}")
        seen.add(pair_key)
        human, judge = record.get("human"), record.get("llm_judge")
        if any(isinstance(value, bool) or not isinstance(value, int) or not scale_min <= value <= scale_max for value in (human, judge)):
            raise ValueError("paired ratings must be integer values within the configured scale")
        grouped.setdefault(dimension, []).append((human, judge))

    def report(pairs: Sequence[tuple[int, int]]) -> dict[str, Any]:
        n = len(pairs)
        agreements = sum(human == judge for human, judge in pairs)
        observed = agreements / n if n else None
        interval = _wilson_interval(agreements, n) if n else None
        return {
            "sample_size": n,
            "raw_agreement": observed,
            "raw_agreement_95_percent_wilson_interval": interval,
            "quadratic_weighted_cohen_kappa": quadratic_weighted_kappa(
                [pair[0] for pair in pairs], [pair[1] for pair in pairs],
                scale_min=scale_min, scale_max=scale_max,
            ),
            "paired_ratings": [{"human": human, "llm_judge": judge} for human, judge in pairs],
        }

    all_pairs = [pair for pairs in grouped.values() for pair in pairs]
    return {
        "status": "measured" if all_pairs else "not_measured_no_paired_human_labels",
        "sample_size": len(all_pairs),
        "overall": report(all_pairs),
        "by_dimension": {dimension: report(pairs) for dimension, pairs in sorted(grouped.items())},
        "scale": {"minimum": scale_min, "maximum": scale_max, "type": "ordinal"},
    }


def _wilson_interval(successes: int, trials: int, *, z: float = 1.959963984540054) -> list[float]:
    """95% Wilson score interval for raw categorical agreement proportion."""
    proportion = successes / trials
    denominator = 1 + z * z / trials
    centre = (proportion + z * z / (2 * trials)) / denominator
    margin = z * math.sqrt(proportion * (1 - proportion) / trials + z * z / (4 * trials * trials)) / denominator
    return [max(0.0, centre - margin), min(1.0, centre + margin)]


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
