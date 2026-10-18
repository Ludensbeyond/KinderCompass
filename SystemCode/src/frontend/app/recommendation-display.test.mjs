import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import {
  getRecommendationEmptyState,
  getParentRecommendationDetails,
  getParentFeeBreakdown,
  getRecommendationScores,
  getStage1EmptyState,
  unknownPreferenceLabels,
} from "./recommendation-display.mjs";

test("formats Stage 2 score fields distinctly using the returned values", () => {
  assert.deepEqual(getRecommendationScores({
    match_score: 80,
    profile_confidence: 0.64,
    combined_score: 71.6,
  }), {
    match: "80.0%",
    evidence: "64.0%",
    combined: "71.6%",
  });
});

test("does not invent a combined score when Stage 2 did not return one", () => {
  assert.equal(getRecommendationScores({ match_score: 80, profile_confidence: 0.64 }).combined, "Unavailable");
});

test("labels unknown required evidence without claiming match or mismatch", () => {
  assert.deepEqual(unknownPreferenceLabels([
    { attribute: "spark_certified", status: "unknown", importance: "required" },
    { attribute: "language:Chinese", status: "unknown", importance: "preferred" },
    { attribute: "transport", status: "matched", importance: "preferred" },
  ]), ["spark certified (required) (unknown)", "Language (Chinese) (unknown)"]);
});

test("distinguishes Stage 1 empty, Stage 2 empty, and distance-filtered results", () => {
  assert.equal(getRecommendationEmptyState({ stage: "search", recordedState: "stage1", eligibleCount: 0, visibleCount: 0 }), "no_candidates");
  assert.equal(getRecommendationEmptyState({ stage: "choose", recordedState: "stage2", eligibleCount: 0, visibleCount: 0 }), "no_eligible");
  assert.equal(getRecommendationEmptyState({ stage: "choose", recordedState: "not_ready", eligibleCount: 2, visibleCount: 0 }), "distance_filtered");
  assert.equal(getRecommendationEmptyState({ stage: "choose", recordedState: "not_ready", eligibleCount: 2, visibleCount: 0, unknownDistanceCount: 1 }), "distance_unknown");
  assert.equal(getRecommendationEmptyState({ stage: "choose", recordedState: "not_ready", eligibleCount: 2, visibleCount: 1 }), null);
  assert.equal(getStage1EmptyState({ database_candidates_after_hard_constraints: 0 }), "hard_filters");
  assert.equal(getStage1EmptyState({ database_candidates_after_hard_constraints: 2, after_distance_filter: 0, distance_missing_coordinates: 2 }), "distance_unknown");
  assert.equal(getStage1EmptyState({ database_candidates_after_hard_constraints: 2, after_distance_filter: 0, distance_outside_radius: 2 }), "distance_filtered");
  assert.equal(getStage1EmptyState({ database_candidates_after_hard_constraints: 2, after_distance_filter: 2, after_required_preference_enforcement: 0 }), "required_preferences");
});

test("explains recorded matches, exposes source, and directs unknown requirements to confirmation", () => {
  const details = getParentRecommendationDetails({ match_breakdown: [
    {
      attribute: "spark_certified", preference: true, school_value: true,
      status: "matched", importance: "required", evidence_state: "verified",
      source: "ECDA/LifeSG preschool dataset",
    },
    {
      attribute: "transport", preference: true, school_value: null,
      status: "unknown", importance: "required", evidence_state: "unknown",
      source: "ECDA/LifeSG preschool dataset",
    },
    {
      attribute: "pedagogy", preference: "Montessori", school_value: "Montessori",
      status: "matched", importance: "preferred", evidence_state: "derived",
      source: "KinderCompass derivation",
    },
    {
      attribute: "transport", preference: true, school_value: false,
      status: "not_matched", importance: "preferred", evidence_state: "verified",
      source: "ECDA/LifeSG preschool dataset",
    },
  ] }, { unsupported_preferences: [
    { attribute: "hands_on_learning", value: true, importance: "preferred" },
  ] });
  assert.match(details.matches[0], /Recorded school information matches your preference for SPARK status recorded as yes/);
  assert.equal(details.matches.length, 1);
  assert.doesNotMatch(JSON.stringify(details.matches), /Montessori|inferred/);
  assert.deepEqual(details.information[0].source, {
    label: "Listing of Centres dataset",
    url: "https://data.gov.sg/datasets/d_696c994c50745b079b3684f0e90ffc53/view",
  });
  assert.match(details.confirm[0].text, /no recorded information.*required preference for transport/i);
  assert.match(details.confirm[1].text, /inferred.*not a confirmed school fact.*teaching approach/i);
  assert.match(details.confirm[2].text, /does not currently assess/);
  assert.equal(details.information.find((item) => item.label === "transport").matches, false);
  assert.doesNotMatch(JSON.stringify(details), /verified points|last updated/i);
});

test("describes a negative preference without reversing the parent's intent", () => {
  const details = getParentRecommendationDetails({ match_breakdown: [{
    attribute: "transport", preference: true, school_value: false,
    status: "matched", importance: "preferred", evidence_state: "verified",
    source: "ECDA/LifeSG preschool dataset",
  }] }, { preferences: { transport: { value: true, desired: false } } });
  assert.match(details.matches[0], /matches your preference for no transport/);
});

test("explains a fee estimate that is limited by the policy minimum payable amount", () => {
  assert.deepEqual(getParentFeeBreakdown({
    fee_before_subsidy: 610,
    basic_subsidy: 300,
    additional_subsidy: 440,
    maximum_additional_subsidy: 440,
    additional_subsidy_applied: 285,
    minimum_copayment: 25,
    net_monthly_fee: 25,
  }), {
    fee: 610,
    basic: 300,
    additional: 285,
    maximumAdditional: 440,
    minimum: 25,
    net: 25,
    minimumApplied: true,
    reconciles: true,
  });
});

test("flags fee figures that do not reconcile and handles incomplete fee data", () => {
  assert.equal(getParentFeeBreakdown({
    fee_before_subsidy: 610,
    basic_subsidy: 300,
    additional_subsidy: 440,
    maximum_additional_subsidy: 440,
    additional_subsidy_applied: 285,
    minimum_copayment: 25,
    net_monthly_fee: 30,
  }).reconciles, false);
  assert.equal(getParentFeeBreakdown({ net_monthly_fee: 25 }).reconciles, null);
});

test("keeps technical score wording optional and presents parent-facing sections", async () => {
  const page = await readFile(new URL("./page.tsx", import.meta.url), "utf8");
  const diagnosticStart = page.indexOf('<details className="scoreBreakdown"><summary>Optional ranking details</summary>');
  assert.notEqual(diagnosticStart, -1);
  assert.ok(page.indexOf("Combined ranking score", diagnosticStart) >= diagnosticStart);
  assert.match(page, /<h4>Why this preschool matches<\/h4>/);
  assert.match(page, /<h4>Information available<\/h4>/);
  assert.match(page, /<h4>What to confirm<\/h4>/);
  assert.match(page, /We don&apos;t have enough school information to explain a preference match yet\./);
  assert.match(page, /No specific preference gaps are flagged\. School information may still need direct confirmation\./);
  assert.match(page, /The returned fee estimate does not reconcile with the displayed fee and subsidy figures/);
  assert.doesNotMatch(page, /working full day policy table was applied/i);
  assert.doesNotMatch(page, /verified points|Evidence type:.*evidence_state|Last updated:.*source_date/i);
});
