/** Format the exact score fields returned on the Stage 2 evaluated result. */
export function getRecommendationScores(centre) {
  const match = Number.isFinite(centre.match_score)
    ? `${centre.match_score.toFixed(1)}%`
    : "Unavailable";
  const evidence = Number.isFinite(centre.profile_confidence)
    ? `${(centre.profile_confidence * 100).toFixed(1)}%`
    : "Unavailable";
  const combined = Number.isFinite(centre.combined_score)
    ? `${centre.combined_score.toFixed(1)}%`
    : "Unavailable";
  return { match, evidence, combined };
}

/** Return unknown evidence labels without treating them as a match or mismatch. */
export function unknownPreferenceLabels(breakdown) {
  return breakdown
    .filter((item) => ["unknown", "inferred", "partially_supported"].includes(item.status))
    .map((item) => {
      const label = item.attribute.startsWith("language:")
        ? `Language (${item.attribute.slice("language:".length)})`
        : item.attribute.replaceAll("_", " ");
      const evidence = item.status === "inferred" ? " (inferred)"
        : item.status === "partially_supported" ? " (partial evidence)" : " (unknown)";
      return `${label}${item.importance === "required" ? " (required)" : ""}${evidence}`;
    });
}

function preferenceLabel(attribute) {
  if (attribute.startsWith("language:")) return `${attribute.slice("language:".length)} language`;
  const labels = {
    pedagogy: "teaching approach",
    spark_certified: "SPARK status",
    operator_scheme: "operator scheme",
    transport: "transport",
    food: "food arrangement",
    full_day: "full-day care",
    care_level: "care level",
  };
  return labels[attribute] ?? attribute.replaceAll("_", " ");
}

function preferenceValue(value) {
  if (value === true) return "yes";
  if (value === false) return "no";
  return value == null || value === "" ? "not specified" : String(value);
}

function parentSource(source) {
  if (source === "ECDA/LifeSG preschool dataset") {
    return {
      label: "Listing of Centres dataset",
      url: "https://data.gov.sg/datasets/d_696c994c50745b079b3684f0e90ffc53/view",
    };
  }
  if (source === "ECDA/LifeSG service records") {
    return {
      label: "Listing of Centre Services dataset",
      url: "https://data.gov.sg/datasets/d_44cfe12f2858ae503a093dfc075a28be/view",
    };
  }
  return { label: source || "KinderCompass school catalogue", url: null };
}

/** Build parent-facing reasons only from scorer-provided values and states. */
export function getParentRecommendationDetails(centre, profile) {
  const matches = [];
  const information = [];
  const confirm = [];
  for (const item of centre.match_breakdown ?? []) {
    const label = preferenceLabel(item.attribute);
    const profilePreference = profile?.preferences?.[item.attribute];
    const desired = profilePreference?.desired !== false;
    const requestedValue = !desired && typeof item.preference === "boolean"
      ? !item.preference
      : item.preference;
    const requested = preferenceValue(requestedValue);
    const requestedPhrase = typeof item.preference === "boolean"
      ? item.attribute === "spark_certified"
        ? `SPARK status recorded as ${requested}`
        : requested === "yes" ? label : `no ${label}`
      : desired ? `${requested} ${label}` : `avoiding ${preferenceValue(item.preference)}`;
    const schoolValue = preferenceValue(item.school_value);
    if (["unknown", "inferred", "partially_supported"].includes(item.status)
        || ["derived", "partially_supported"].includes(item.evidence_state)
        || ["stale", "future_dated"].includes(item.freshness)) {
      const evidenceNote = item.status === "inferred" || item.evidence_state === "derived"
        ? `The available value “${preferenceValue(item.recorded_value ?? item.school_value)}” is inferred and is not a confirmed school fact.`
        : item.status === "partially_supported" || item.evidence_state === "partially_supported"
          ? `The catalogue value “${preferenceValue(item.recorded_value ?? item.school_value)}” only partially supports this comparison.`
          : item.freshness === "stale" || item.freshness === "future_dated"
            ? "The available record is not current enough to confirm this preference."
            : "KinderCompass has no recorded information about this preference.";
      confirm.push({
        text: `${evidenceNote}${item.source_date ? ` Source date: ${item.source_date}.` : ""} Ask the preschool whether it meets your ${item.importance === "required" ? "required " : ""}preference for ${requestedPhrase}.`,
        importance: item.importance,
      });
      continue;
    }
    information.push({
      label,
      value: schoolValue,
      source: parentSource(item.source),
      inferred: item.evidence_state === "derived",
      matches: item.status === "matched",
      sourceDate: item.source_date,
      freshness: item.freshness,
    });
    if (item.status === "matched") matches.push(`Recorded school information matches your preference for ${requestedPhrase}.`);
  }
  for (const item of profile?.unsupported_preferences ?? []) {
    confirm.push({
      text: `KinderCompass does not currently assess ${preferenceValue(item.value)} ${preferenceLabel(item.attribute)}. Ask the preschool directly about it.`,
      importance: item.importance,
    });
  }
  return { matches, information, confirm };
}

/** Compare the returned fee estimate with its returned inputs without recalculating policy. */
export function getParentFeeBreakdown(centre) {
  const fee = centre.fee_before_subsidy;
  const basic = centre.basic_subsidy;
  const additional = centre.additional_subsidy_applied;
  const maximumAdditional = centre.maximum_additional_subsidy ?? centre.additional_subsidy;
  const minimum = centre.minimum_copayment;
  const net = centre.net_monthly_fee;
  const hasCoreValues = [fee, basic, additional, net].every(Number.isFinite);
  const hasMinimum = Number.isFinite(minimum);
  const rawAfterSubsidies = hasCoreValues ? fee - basic - additional : null;
  const expected = hasCoreValues
    ? Math.max(hasMinimum ? minimum : 0, rawAfterSubsidies)
    : null;
  const reconciles = expected == null ? null : Math.abs(expected - net) < 0.01;
  return {
    fee,
    basic,
    additional,
    maximumAdditional,
    minimum,
    net,
    minimumApplied: hasMinimum && rawAfterSubsidies != null && rawAfterSubsidies <= minimum && Math.abs(net - minimum) < 0.01,
    reconciles,
  };
}

/** Distinguish no Stage 1 matches, no Stage 2 eligible schools, and distance filtering. */
export function getStage1EmptyState(trace) {
  if (trace?.database_candidates_after_hard_constraints === 0) return "hard_filters";
  if (trace?.after_distance_filter === 0) {
    if ((trace?.distance_missing_coordinates ?? 0) > 0) return "distance_unknown";
    if ((trace?.distance_outside_radius ?? 0) > 0) return "distance_filtered";
  }
  if (trace?.after_required_preference_enforcement === 0) return "required_preferences";
  return "no_candidates";
}

export function getRecommendationEmptyState({ stage, recordedState, eligibleCount, visibleCount, unknownDistanceCount = 0 }) {
  if (stage !== "choose") {
    if (recordedState === "stage1_hard_filters") return "hard_filters";
    if (recordedState === "stage1_required") return "required_preferences";
    if (recordedState === "stage1_distance") return "distance_filtered";
    if (recordedState === "stage1_distance_unknown") return "distance_unknown";
    if (recordedState === "stage1") return "no_candidates";
    if (recordedState === "stage2") return "no_eligible";
    return "not_ready";
  }
  if (eligibleCount === 0) return "no_eligible";
  if (visibleCount === 0 && unknownDistanceCount > 0) return "distance_unknown";
  if (visibleCount === 0) return "distance_filtered";
  return null;
}
