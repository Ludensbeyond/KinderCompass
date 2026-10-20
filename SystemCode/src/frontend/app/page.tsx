"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import LiveMap, { MapPoint } from "./LiveMap";
import { getParentFeeBreakdown, getParentRecommendationDetails, getRecommendationEmptyState, getRecommendationScores, getStage1EmptyState } from "./recommendation-display.mjs";

type ProgrammeId = "full_day" | "half_day_am" | "half_day_pm" |
  "flexi_care_1" | "flexi_care_1_am" | "flexi_care_1_pm" |
  "flexi_care_2" | "flexi_care_3";

type SchoolReview = {
  overall: number;
  relationship: string;
  review_text: string;
  created_at: string;
};
type ParentRating = {
  school_id: string;
  average: number | null;
  count: number;
  reviews?: SchoolReview[];
  evidence_category?: "parent_sentiment";
  source?: string;
};
type SchoolRatingResponse = { rating_id: string; status: "recorded"; summary: ParentRating };
type ProgrammeOption = {
  programme_id: ProgrammeId;
  service_label: string;
  status: Centre["status"];
  eligible: boolean;
  eligible_level?: string;
  fee_before_subsidy: number;
  net_monthly_fee: number;
  basic_subsidy?: number;
  additional_subsidy?: number;
  maximum_additional_subsidy?: number;
  additional_subsidy_applied?: number;
  minimum_copayment?: number;
  warnings?: string[];
  policy_source?: Centre["policy_source"];
};

type Centre = {
  school_id: string;
  centre_code?: string | null;
  tp_code?: string | null;
  name: string;
  base_fee: number;
  pedagogy?: string;
  eligible?: boolean;
  eligible_level?: string;
  net_monthly_fee?: number | null;
  status?: "estimated" | "manual_review" | "fee_unavailable" | "ineligible" | "needs_information";
  fee_before_subsidy?: number;
  basic_subsidy?: number;
  additional_subsidy?: number;
  maximum_additional_subsidy?: number;
  additional_subsidy_applied?: number;
  minimum_copayment?: number;
  programme_id?: ProgrammeId;
  service_label?: string;
  preferred_programme_available?: boolean;
  programme_options?: ProgrammeOption[];
  warnings?: string[];
  reason?: string;
  reasons?: string[];
  policy_source?: { policy_id: string; authority: string; effective_from: string; source_url: string };
  distance_km?: number;
  postal_code?: number | string | null;
  mention_links?: { query: string; google_maps: string; google_search: string; reddit: string };
  parent_rating?: ParentRating;
  match_score?: number;
  profile_confidence?: number;
  combined_score?: number;
  strengths?: string[];
  tradeoffs?: string[];
  match_breakdown?: { attribute: string; preference: unknown; school_value: unknown; recorded_value?: unknown; matched: boolean | null; status: "matched" | "not_matched" | "unknown" | "inferred" | "partially_supported"; importance: string; contribution: number; possible_contribution: number; evidence_state: "verified" | "derived" | "calculated" | "partially_supported" | "recorded" | "unknown"; value_state: "confirmed_yes" | "confirmed_no" | "confirmed_value" | "inferred_value" | "calculated_value" | "partially_supported_value" | "recorded_value" | "unknown"; source: string; source_method: string; source_reliability: string; availability: number; source_date?: string | null; freshness: "current" | "stale" | "future_dated" | "unknown" }[];
};

type Stop = MapPoint & {
  order: number;
  centre_code?: string | null;
  leg_distance_km: number;
  cumulative_distance_km: number;
};
type Route = { total_distance_km: number; distance_method: string; schedule: Stop[] };
type DistanceResult = { school_id: string; distance_km: number };
type Citation = { url: string; title: string; retrieved_at: string; chunk_id: string; evidence_scope: string; authority?: string; effective_from?: string };
type EvidenceCategory = "authoritative_fact" | "school_published_claim" | "calculated_estimate" | "parent_sentiment" | "unknown";
type Message = { role: "assistant" | "user"; text: string; citations?: Citation[]; evidenceCategory?: EvidenceCategory | null; answerId?: string; usefulness?: "helpful" | "not_helpful" };
type PreferenceImportance = "required" | "high_priority" | "preferred" | "nice_to_have";
type PreferenceItem = { attribute: string; value: unknown; importance: PreferenceImportance };
type PreferenceProfile = { hard_constraints: Record<string, unknown>; preferences: Record<string, unknown>; preference_items?: PreferenceItem[]; unsupported_preferences?: PreferenceItem[]; recognized?: string[] };
type FamilyDetails = { dob: string; admission_date: string; gross_household_income: number; citizenship: "SC" | "SPR" | "Others"; programme_type: "full_day" | "half_day" | "flexi_care_1" | "flexi_care_2" | "flexi_care_3"; working_hours_per_month: number; household_size: number; non_earning_dependants: number; special_approval: boolean };
type SchoolRelationship = "enrolled" | "visited" | "applied" | "researching";
type ResultsEmptyState = "not_ready" | "stage1" | "stage1_hard_filters" | "stage1_required" | "stage1_distance" | "stage1_distance_unknown" | "stage2";
const EXPERIENCE_LABELS: Record<SchoolRelationship, string> = {
  researching: "Researching the school",
  applied: "Applied the school",
  visited: "Visited the school",
  enrolled: "Enrolled the school",
};

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const money = new Intl.NumberFormat("en-SG", { style: "currency", currency: "SGD", maximumFractionDigits: 0 });

function formatPostalCode(value: Centre["postal_code"]): string | null {
  const digits = String(value ?? "").replace(/\D/g, "");
  if (!digits) return null;
  return digits.length < 6 ? digits.padStart(6, "0") : digits;
}

function appliedFilters(profile: PreferenceProfile | null): string[] {
  const hard = profile?.hard_constraints;
  if (!hard) return [];
  const filters: string[] = [];
  if (hard.language) filters.push(`${hard.language} required`);
  if (hard.max_distance_km != null) filters.push(`Within ${hard.max_distance_km} km`);
  if (hard.level) filters.push(String(hard.level));
  return filters;
}

function FeeNotes({ centre }: { centre: Centre }) {
  const fee = getParentFeeBreakdown(centre);
  const hasBreakdown = [fee.fee, fee.basic, fee.additional, fee.maximumAdditional].some(Number.isFinite);
  const notes = [
    ...(centre.status === "manual_review" && centre.reason ? [centre.reason] : []),
    ...(centre.warnings ?? []).filter((note) => !note.toLowerCase().includes("not an ecda subsidy approval")),
  ];
  if (fee.net == null && !hasBreakdown && notes.length === 0 && !centre.policy_source) return null;
  return <div className="feeNotes">
    {fee.net != null && <strong className="feeEstimate">Estimated monthly fee: {money.format(fee.net)}</strong>}
    {hasBreakdown && <p className="feeBreakdown">{fee.fee != null && <>Fee before subsidy: {money.format(fee.fee)}</>}{fee.basic != null && <> · Basic subsidy: −{money.format(fee.basic)}</>}{fee.additional != null && <> · Additional subsidy applied: −{money.format(fee.additional)}</>}{fee.maximumAdditional != null && <> · Maximum additional subsidy: up to {money.format(fee.maximumAdditional)}</>}</p>}
    {fee.additional == null && fee.maximumAdditional != null && <p>This response includes the maximum additional subsidy but not the amount actually applied, so the breakdown cannot be fully reconciled.</p>}
    {fee.minimumApplied && fee.minimum != null && <p>A minimum monthly co-payment of {money.format(fee.minimum)} applies under this estimate.</p>}
    {fee.reconciles === false && <p className="feeWarning">The returned fee estimate does not reconcile with the displayed fee and subsidy figures. Confirm the estimate before relying on this breakdown.</p>}
    {centre.policy_source && <p>Policy source: <a href={centre.policy_source.source_url} target="_blank" rel="noreferrer">{centre.policy_source.authority} · effective {sourceDateLabel(centre.policy_source.effective_from)}</a></p>}
    <p>This is an estimate based on the family details provided, not ECDA approval. Confirm current fees and eligibility with the preschool; GST treatment and additional charges may vary.</p>
    {notes.map((note) => <p key={note}>{note}</p>)}
  </div>;
}

function RecommendationExplanation({ centre, profile, distanceKm }: { centre: Centre; profile: PreferenceProfile | null; distanceKm?: number }) {
  const details = getParentRecommendationDetails(centre, profile);
  return (
    <div className="parentExplanation">
      <section>
        <h4>Why this preschool matches</h4>
        {details.matches.length > 0
          ? <ul>{details.matches.map((reason) => <li key={reason}>{reason}</li>)}</ul>
          : <p>We don&apos;t have enough school information to explain a preference match yet.</p>}
      </section>
      <section>
        <h4>Information available</h4>
        {details.information.length > 0 || distanceKm != null
          ? <ul>{details.information.map((item) => <li key={`${item.label}-${item.source.label}`}><strong>{item.label}:</strong> {item.value} · {item.matches ? "matches this preference" : "does not match this preference"}<small>Source: {item.source.url ? <a href={item.source.url} target="_blank" rel="noreferrer">{item.source.label}</a> : item.source.label}{item.sourceDate ? ` · Catalogue updated ${item.sourceDate}` : " · Update date unavailable"}</small></li>)}{distanceKm != null && <li><strong>Distance from home:</strong> {distanceKm.toFixed(2)} km<small>Calculated from the entered postal code and preschool location.</small></li>}</ul>
          : <p>No preference-related details are available in the school record.</p>}
        {details.information.length > 0 && <small>Recorded school information is not independently checked for current accuracy.</small>}
      </section>
      <section>
        <h4>What to confirm</h4>
        {details.confirm.length > 0
          ? <ul>{details.confirm.map((item, index) => <li key={`${index}-${item.text}`}>{item.text}</li>)}</ul>
          : <p>No specific preference gaps are flagged. School information may still need direct confirmation.</p>}
      </section>
    </div>
  );
}
function ParentMentionLinks({ centre }: { centre: Centre }) {
  const links = mentionLinksFor(centre);
  return (
    <div className="mentionLinks">
      <strong>Parent mentions online</strong>
      <nav>
        <a href={links.google_maps} target="_blank" rel="noreferrer">Google Maps</a>
        <a href={links.google_search} target="_blank" rel="noreferrer">Google reviews</a>
        <a href={links.reddit} target="_blank" rel="noreferrer">Reddit</a>
      </nav>
      <small>Search links for this name and postal code. Confirm it is the same centre; this is not KinderCompass evidence and does not change ranking.</small>
    </div>
  );
}

function SchoolRatingPanel({
  centre, sessionId, onRated,
}: {
  centre: Centre;
  sessionId: string;
  onRated: (schoolId: string, summary: ParentRating) => void;
}) {
  const [overall, setOverall] = useState("5");
  const [relationship, setRelationship] = useState<SchoolRelationship>("researching");
  const [reviewText, setReviewText] = useState("");
  const [consent, setConsent] = useState(false);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const rating = centre.parent_rating;
  const reviews = rating?.reviews ?? [];
  const summary = rating?.count
    ? `${rating.average?.toFixed(1)} / 5 from ${rating.count} parent rating${rating.count === 1 ? "" : "s"}`
    : "No KinderCompass ratings yet";

  async function submitRating(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    event.stopPropagation();
    if (!sessionId || !consent) return;
    setBusy(true); setStatus("");
    try {
      const result = await post<SchoolRatingResponse>(
        `/api/schools/${encodeURIComponent(centre.school_id)}/ratings`,
        {
          anonymous_session_id: sessionId,
          overall: Number(overall),
          relationship,
          review_text: reviewText.trim() || null,
          consent: true,
        },
      );
      onRated(centre.school_id, result.summary);
      setReviewText("");
      setStatus("Thank you. Your anonymous school rating was recorded.");
      setConsent(false);
    } catch (caught) {
      setStatus((caught as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="schoolRating" onSubmit={submitRating}>
      <strong>School Ratings by Other Kinder Compass users</strong>
      <p>{summary}</p>
      <div className="reviewWindow" aria-label="Reviews from other users">
        <strong>Reviews</strong>
        {reviews.length === 0
          ? <p>No written reviews yet.</p>
          : reviews.map((review) => (
            <article key={`${review.created_at}-${review.review_text.slice(0, 24)}`}>
              <small>{review.overall} / 5 · {EXPERIENCE_LABELS[review.relationship as SchoolRelationship] ?? review.relationship} · {sourceDateLabel(review.created_at)}</small>
              <p>{review.review_text}</p>
            </article>
          ))}
      </div>
      <div className="schoolRatingFields">
        <label>Your rating
          <select value={overall} onChange={(event) => setOverall(event.target.value)}>
            {[5, 4, 3, 2, 1].map((value) => <option value={value} key={value}>{value} / 5</option>)}
          </select>
        </label>
        <label>Your experience
          <select value={relationship} onChange={(event) => setRelationship(event.target.value as SchoolRelationship)}>
            {(Object.keys(EXPERIENCE_LABELS) as SchoolRelationship[]).map((value) =>
              <option value={value} key={value}>{EXPERIENCE_LABELS[value]}</option>
            )}
          </select>
        </label>
      </div>
      <label className="schoolReviewText">Your review
        <textarea maxLength={1000} value={reviewText} onChange={(event) => setReviewText(event.target.value)} placeholder="Describe what you noticed at this school" />
      </label>
      <label className="schoolRatingConsent">
        <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} />
        <span>I consent to storing this anonymous school rating and review. Family details are not stored.</span>
      </label>
      <button type="submit" className="primary" disabled={busy || !consent || !sessionId}>Submit school rating</button>
      {status && <small>{status}</small>}
      <small>First-party parent sentiment collected here. It does not change ranking.</small>
    </form>
  );
}

function mentionLinksFor(centre: Centre): { query: string; google_maps: string; google_search: string; reddit: string } {
  if (centre.mention_links?.google_maps) return centre.mention_links;
  const postal = String(centre.postal_code ?? "").replace(/\D/g, "");
  const query = [centre.name, postal.length === 6 ? postal : null, "Singapore"].filter(Boolean).join(" ");
  return {
    query,
    google_maps: `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`,
    google_search: `https://www.google.com/search?q=${encodeURIComponent(`${query} reviews`)}`,
    reddit: `https://www.reddit.com/search/?q=${encodeURIComponent(query)}`,
  };
}

function sourceDateLabel(value?: string | null): string {
  if (!value) return "Unavailable";
  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(date.getTime())
    ? "Unavailable"
    : new Intl.DateTimeFormat("en-SG", { day: "numeric", month: "long", year: "numeric" }).format(date);
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 60_000);
  try {
    const response = await fetch(`${API}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail ?? "Something went wrong. Please try again.");
    return data;
  } catch (caught) {
    if (controller.signal.aborted) {
      throw new Error("The request took too long. Please try again.");
    }
    throw caught;
  } finally {
    clearTimeout(timer);
  }
}

export default function Home() {
  const [stage, setStage] = useState<"family" | "search" | "choose">("family");
  const [resultsEmptyState, setResultsEmptyState] = useState<ResultsEmptyState>("not_ready");
  const [tab, setTab] = useState<"form" | "results" | "map">("form");
  const [preference, setPreference] = useState("");
  const [eligible, setEligible] = useState<Centre[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [excluded, setExcluded] = useState<string[]>([]);
  const [routes, setRoutes] = useState<Record<string, Route>>({});
  const [homePoint, setHomePoint] = useState<MapPoint | null>(null);
  const [mapBusy, setMapBusy] = useState(false);
  const [distances, setDistances] = useState<Record<string, number>>({});
  const [distanceFilter, setDistanceFilter] = useState("none");
  const [busy, setBusy] = useState(false);
  const [programmeBusy, setProgrammeBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [homePostalCode, setHomePostalCode] = useState("731764");
  const [familyDetails, setFamilyDetails] = useState<FamilyDetails | null>(null);
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", text: "Please complete the Family details form first. I will help with preschool preferences after it is saved." },
  ]);
  const [preferenceProfile, setPreferenceProfile] = useState<PreferenceProfile | null>(null);
  const [understood, setUnderstood] = useState<string[]>([]);
  const [readyToSearch, setReadyToSearch] = useState(false);
  const [anonymousSessionId, setAnonymousSessionId] = useState("");
  const [rememberDetails, setRememberDetails] = useState(false);
  const [memoryStatus, setMemoryStatus] = useState("");

  const mapPoints = useMemo<MapPoint[]>(() => {
    const comparisons = Object.entries(routes);
    if (comparisons.length) {
      const schoolById = new Map(eligible.map((centre) => [centre.school_id, centre]));
      return [
        comparisons[0][1].schedule[0],
        ...comparisons.map(([schoolId, comparison]) => ({
          ...comparison.schedule[1],
          postal_code: schoolById.get(schoolId)?.postal_code,
          distance_km: distances[schoolId]
            ?? comparison.total_distance_km
            ?? comparison.schedule[1]?.leg_distance_km,
        })),
      ];
    }
    return homePoint ? [homePoint] : [];
  }, [distances, eligible, homePoint, routes]);

  const visibleEligible = useMemo(() => {
    if (distanceFilter === "none") return eligible;
    const maximum = Number(distanceFilter);
    return eligible.filter((centre) => distances[centre.school_id] != null && distances[centre.school_id] <= maximum);
  }, [distanceFilter, distances, eligible]);
  const recommendationEmptyState = getRecommendationEmptyState({
    stage,
    recordedState: resultsEmptyState,
    eligibleCount: eligible.length,
    visibleCount: visibleEligible.length,
    unknownDistanceCount: distanceFilter === "none" ? 0 : Math.max(0, eligible.length - Object.keys(distances).length),
  });

  useEffect(() => {
    const key = "kindercompass-anonymous-session";
    const existing = window.localStorage.getItem(key);
    const value = existing ?? window.crypto.randomUUID();
    if (!existing) window.localStorage.setItem(key, value);
    setAnonymousSessionId(value);
    const combinedConsent = window.localStorage.getItem("kindercompass-remember-conversation-and-preferences") === "true";
    setRememberDetails(combinedConsent);
    if (combinedConsent || window.localStorage.getItem("kindercompass-remember-preferences") === "true") {
      void post<{ found: boolean; profile?: PreferenceProfile; understood: string[] }>("/api/memory/restore", {
        anonymous_session_id: value,
      }).then((result) => {
        if (!result.found || !result.profile) return;
        setPreferenceProfile(result.profile);
        if (!combinedConsent) setMemoryStatus("Saved preferences restored. Enable this option to remember future conversations and preferences.");
        setUnderstood(result.understood);
        setReadyToSearch(Boolean(Object.keys(result.profile.hard_constraints).length || Object.keys(result.profile.preferences).length));
        setMessages((items) => [...items, { role: "assistant", text: "I restored your saved preschool preferences and unresolved decision state. Family form details are not saved with preferences." }]);
      }).catch(() => setMemoryStatus("Saved preferences could not be restored."));
    }
  }, []);

  useEffect(() => {
    setRoutes({});
    if (!/^\d{6}$/.test(homePostalCode)) {
      setHomePoint(null);
      return;
    }
    let cancelled = false;
    const timer = setTimeout(() => {
      setMapBusy(true);
      void post<MapPoint>("/api/geocode", { postal_code: homePostalCode })
        .then((point) => { if (!cancelled) { setHomePoint(point); setError(""); } })
        .catch((caught) => { if (!cancelled) { setHomePoint(null); setError((caught as Error).message); } })
        .finally(() => { if (!cancelled) setMapBusy(false); });
    }, 400);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [homePostalCode]);

  useEffect(() => {
    if (!eligible.length || !/^\d{6}$/.test(homePostalCode)) {
      setDistances({});
      return;
    }
    let cancelled = false;
    void post<{ distances: DistanceResult[] }>("/api/distances", {
      school_ids: eligible.map((centre) => centre.school_id),
      home_postal_code: homePostalCode,
    })
      .then((result) => {
        if (!cancelled) setDistances(Object.fromEntries(result.distances.map((item) => [item.school_id, item.distance_km])));
      })
      .catch((caught) => { if (!cancelled) setError((caught as Error).message); });
    return () => { cancelled = true; };
  }, [eligible, homePostalCode]);

  useEffect(() => {
    if (!selected.length || !/^\d{6}$/.test(homePostalCode)) {
      setRoutes({});
      return;
    }
    let cancelled = false;
    setMapBusy(true);
    void Promise.all(selected.map(async (schoolId) => [schoolId, await post<Route>("/api/route", {
        school_id: schoolId,
        home_postal_code: homePostalCode,
      })] as const))
      .then((results) => { if (!cancelled) { setRoutes(Object.fromEntries(results)); setError(""); } })
      .catch((caught) => { if (!cancelled) { setRoutes({}); setError((caught as Error).message); } })
      .finally(() => { if (!cancelled) setMapBusy(false); });
    return () => { cancelled = true; };
  }, [eligible, homePostalCode, selected]);

  async function sendPreference(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!familyDetails) return;
    setBusy(true); setError("");
    const question = preference.trim();
    setMessages((items) => [...items, { role: "user", text: question }]);
    try {
      const result = await post<{ profile: PreferenceProfile; understood: string[]; ready_to_search: boolean; question: string; citations?: Citation[]; evidence_category?: EvidenceCategory | null; answer_id?: string }>("/api/preferences", {
        message: question,
        profile: preferenceProfile,
        selected_school_ids: selected,
        eligible_school_ids: eligible.map((centre) => centre.school_id),
        excluded_school_ids: excluded,
        family: familyDetails,
        home_postal_code: homePostalCode,
        anonymous_session_id: rememberDetails ? anonymousSessionId : undefined,
        remember_preferences: rememberDetails,
        remember_conversation: rememberDetails,
      });
      setPreferenceProfile(result.profile); setUnderstood(result.understood);
      const distancePreference = result.profile.preference_items?.find((item) => item.attribute === "max_distance_km");
      setDistanceFilter(distancePreference
        ? String(distancePreference.value)
        : (/^\d{6}$/.test(homePostalCode) ? "5" : "none"));
      setReadyToSearch(result.ready_to_search);
      setMessages((items) => [...items, { role: "assistant", text: result.question, citations: result.citations, evidenceCategory: result.evidence_category, answerId: result.answer_id }]);
      setPreference("");
    } catch (caught) {
      const message = (caught as Error).message;
      setError(message); setMessages((items) => [...items, { role: "assistant", text: message }]);
    } finally { setBusy(false); }
  }

  async function confirmSearch() {
    if (!preferenceProfile || !readyToSearch || !familyDetails) return;
    setBusy(true); setError("");
    setResultsEmptyState("not_ready");
    try {
      const distancePreference = preferenceProfile.preference_items?.find((item) => item.attribute === "max_distance_km");
      const requestedRadius = distancePreference ? Number(distancePreference.value) : undefined;
      const searchResult = await post<{ centres: Centre[]; trace: { trace_id: string; [key: string]: unknown }; message: string; profile: PreferenceProfile }>("/api/search", {
        profile: preferenceProfile,
        ...(/^\d{6}$/.test(homePostalCode) ? { home_postal_code: homePostalCode } : {}),
        ...(requestedRadius ? { radius_km: requestedRadius } : {}),
      });
      if (searchResult.centres.length === 0) {
        if (rememberDetails) await clearConversationContext();
        setPreferenceProfile(searchResult.profile);
        setReadyToSearch(false);
        const empty = getStage1EmptyState(searchResult.trace);
        setResultsEmptyState(empty === "hard_filters" ? "stage1_hard_filters"
          : empty === "required_preferences" ? "stage1_required"
            : empty === "distance_unknown" ? "stage1_distance_unknown"
              : empty === "distance_filtered" ? "stage1_distance" : "stage1");
        setEligible([]); setSelected([]); setRoutes({});
        setMessages((items) => [...items, { role: "assistant", text: searchResult.message }]);
        setStage("search"); setTab("results");
        return;
      }
      const evaluationResult = await post<{ centres: Centre[] }>("/api/evaluate", {
        school_ids: searchResult.centres.map((centre) => centre.school_id),
        profile: preferenceProfile,
        family: familyDetails,
        trace_id: searchResult.trace.trace_id,
        include_ineligible: true,
      });
      const eligibleCentres = evaluationResult.centres.filter((centre) => centre.eligible);
      setEligible(eligibleCentres);
      if (!distancePreference && /^\d{6}$/.test(homePostalCode)) {
        setDistanceFilter("5");
      }
      setResultsEmptyState(eligibleCentres.length === 0 ? "stage2" : "not_ready");
      setExcluded(evaluationResult.centres.filter((centre) => !centre.eligible).map((centre) => centre.school_id));
      setSelected([]); setRoutes({});
      setMessages((items) => [...items, { role: "assistant", text: `I found ${searchResult.centres.length} ranked matches, and ${eligibleCentres.length} match the age and fee criteria. Choose one or more preschools to compare with home.` }]);
      setStage("choose"); setTab("results");
    } catch (caught) {
      const message = (caught as Error).message;
      setError(message); setMessages((items) => [...items, { role: "assistant", text: message }]);
    } finally { setBusy(false); }
  }

  function saveFamilyDetails(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setFamilyDetails({
      dob: String(form.get("dob")),
      admission_date: String(form.get("admission_date")),
      gross_household_income: Number(form.get("income")),
      citizenship: String(form.get("citizenship")) as FamilyDetails["citizenship"],
      programme_type: String(form.get("programme_type")) as FamilyDetails["programme_type"],
      working_hours_per_month: Number(form.get("working_hours")),
      household_size: Number(form.get("household_size")),
      non_earning_dependants: Number(form.get("dependants")),
      special_approval: form.get("special_approval") === "on",
    });
    setError(""); setStage("search"); setTab("form");
    setMessages((items) => [...items, { role: "assistant", text: "Family details saved. Now tell me what matters most in a preschool. You can mention pedagogy, language, SPARK, transport, food, or full-day care." }]);
  }

  function toggleSchool(id: string) {
    setSelected((items) => items.includes(id) ? items.filter((item) => item !== id) : [...items, id]);
  }

  async function changeMemory(enabled: boolean) {
    setMemoryStatus("");
    if (!anonymousSessionId || busy) return;
    setBusy(true);
    try {
      if (enabled) {
        await clearConversationContext();
        if (preferenceProfile) {
          await post("/api/memory/save", { anonymous_session_id: anonymousSessionId, profile: preferenceProfile });
        }
        window.localStorage.setItem("kindercompass-remember-conversation-and-preferences", "true");
        window.localStorage.removeItem("kindercompass-remember-preferences");
        setRememberDetails(true);
        setMemoryStatus("Conversation and preferences will be remembered.");
      } else {
        await post("/api/memory/forget", { anonymous_session_id: anonymousSessionId });
        window.localStorage.removeItem("kindercompass-remember-conversation-and-preferences");
        window.localStorage.removeItem("kindercompass-remember-preferences");
        setRememberDetails(false);
        setMemoryStatus("Saved conversation and preferences cleared.");
      }
    } catch (caught) {
      setMemoryStatus((caught as Error).message);
    } finally { setBusy(false); }
  }

  async function clearConversationContext() {
    if (anonymousSessionId) {
      await post("/api/conversation/forget", { anonymous_session_id: anonymousSessionId });
    }
  }

  async function rateChatAnswer(answerId: string, helpful: boolean) {
    if (!anonymousSessionId) return;
    try {
      await post("/api/chat-feedback", {
        answer_id: answerId,
        anonymous_session_id: anonymousSessionId,
        helpful,
        consent: true,
      });
      setMessages((items) => items.map((item) => item.answerId === answerId
        ? { ...item, usefulness: helpful ? "helpful" : "not_helpful" }
        : item));
    } catch (caught) {
      setError((caught as Error).message);
    }
  }

  async function changeProgramme(schoolId: string, programmeId: ProgrammeId) {
    if (!familyDetails) return;
    setProgrammeBusy(schoolId); setError("");
    try {
      const estimate = await post<ProgrammeOption & { school_id: string }>(
        `/api/schools/${encodeURIComponent(schoolId)}/programme-estimate`,
        { family: familyDetails, programme_id: programmeId },
      );
      setEligible((centres) => centres.map((centre) =>
        centre.school_id === schoolId ? { ...centre, ...estimate } : centre
      ));
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setProgrammeBusy(null);
    }
  }

  function updateParentRating(schoolId: string, summary: ParentRating) {
    setEligible((centres) => centres.map((centre) =>
      centre.school_id === schoolId ? { ...centre, parent_rating: summary } : centre
    ));
    setError("");
  }

  async function updateImportance(attribute: string, value: unknown, importance: PreferenceImportance) {
    if (busy) return;
    setBusy(true); setError("");
    try {
      if (rememberDetails) await clearConversationContext();
      setPreferenceProfile((profile) => profile ? {
        ...profile,
        preference_items: profile.preference_items?.map((item) =>
          item.attribute === attribute && item.value === value ? { ...item, importance } : item
        ),
      } : profile);
    } catch (caught) {
      setError((caught as Error).message);
    } finally { setBusy(false); }
  }

  return (
    <main className="appFrame">
      <header className="topbar">
        <div className="brand"><span className="brandMark">K</span><span>KinderCompass</span></div>
        <span className="status"><i /> Preschool planning workspace</span>
      </header>

      <div className="workspace">
        <aside className="chatPanel">
          <div className="sectionTitle"><span className="bot">✦</span><div><h1>Compass chat</h1><p>Describe the preschool you need</p></div></div>
          {understood.length > 0 && <details className="preferenceSummary"><summary><strong>Understood preferences</strong><span>{understood.length}</span></summary><div className="preferenceContent"><div className="preferenceChips">{understood.map((item) => <span key={item}>{item}</span>)}</div>{preferenceProfile?.preference_items?.some((item) => !["care_level", "max_distance_km"].includes(item.attribute) && !(item.attribute === "language" && preferenceProfile.hard_constraints.language)) && <div className="importanceControls"><strong>Adjust ranking importance</strong>{preferenceProfile.preference_items.filter((item) => !["care_level", "max_distance_km"].includes(item.attribute) && !(item.attribute === "language" && preferenceProfile.hard_constraints.language)).map((item) => <label key={`${item.attribute}-${String(item.value)}`}><span>{item.attribute.replaceAll("_", " ")}</span><select value={item.importance} disabled={busy} onChange={(event) => void updateImportance(item.attribute, item.value, event.target.value as PreferenceImportance)}><option value="required">Required</option><option value="high_priority">High priority</option><option value="preferred">Preferred</option><option value="nice_to_have">Nice to have</option></select></label>)}</div>}<small>Send another message to add or correct these preferences.</small></div></details>}
          <div className="messages" aria-live="polite">
            {messages.map((message, index) => <div className={`message ${message.role}`} key={`${message.role}-${index}`}><span>{message.text}</span>{message.evidenceCategory && <small className={`evidenceLabel ${message.evidenceCategory}`}>Evidence: {message.evidenceCategory.replaceAll("_", " ")}</small>}{message.citations?.length ? <div className="messageSources"><strong>Sources</strong>{message.citations.map((citation, sourceIndex) => <a href={citation.url} target="_blank" rel="noreferrer" key={citation.chunk_id}>[{sourceIndex + 1}] {citation.title}<small>{citation.evidence_scope === "general" ? "General guidance" : "School evidence"}{citation.authority ? ` · ${citation.authority}` : ""}{citation.effective_from ? ` · Effective ${sourceDateLabel(citation.effective_from)}` : ""} · Retrieved {sourceDateLabel(citation.retrieved_at)}</small></a>)}</div> : null}{message.answerId && <div className="answerRating"><small>Was this useful?</small><button className={message.usefulness === "helpful" ? "selected" : ""} onClick={() => void rateChatAnswer(message.answerId!, true)} aria-label="Helpful answer">Yes</button><button className={message.usefulness === "not_helpful" ? "selected" : ""} onClick={() => void rateChatAnswer(message.answerId!, false)} aria-label="Not helpful answer">No</button></div>}</div>)}
            {busy && <div className="message assistant typing">Thinking…</div>}
          </div>
          {understood.length > 0 && <div className="recommendationAction"><button onClick={confirmSearch} disabled={busy || !readyToSearch}>Show recommendations</button></div>}
          <form className="chatComposer" onSubmit={sendPreference}>
            <textarea required minLength={2} maxLength={500} disabled={!familyDetails || busy} value={preference} onChange={(event) => setPreference(event.target.value)} placeholder={familyDetails ? "Ask for Montessori, bilingual, play-based…" : "Complete Family details to unlock chat"} />
            <button className="primary" disabled={!familyDetails || busy}>Send <span>↑</span></button>
          </form>
          <div className="memoryControl">
            <label><input type="checkbox" checked={rememberDetails} disabled={busy || !anonymousSessionId} onChange={(event) => void changeMemory(event.target.checked)} /><span>Remember my conversation and preferences</span></label>
            <small>Recent chat expires after 30 minutes of inactivity; preschool preferences are saved for up to 180 days. Chat may include family details you mention. Turning this off clears both. {memoryStatus}</small>
          </div>
        </aside>

        <section className="rightColumn">
          <div className="displayPanel">
            <div className="tabs">
              <button className={tab === "form" ? "active" : ""} onClick={() => setTab("form")}>Form</button>
              <button className={tab === "results" ? "active" : ""} onClick={() => setTab("results")}>Results <span>{stage === "choose" ? eligible.length : 0}</span></button>
              <button className={tab === "map" ? "active" : ""} onClick={() => setTab("map")}>Map</button>
              <small>{stage === "family" ? "Family details first" : stage === "search" ? "Chat ready" : `${selected.length} selected`}</small>
            </div>
            {error && <div className="alert">{error}</div>}

            <div className="displayBody">
              {tab === "form" && stage === "family" && <form className="contentForm" onSubmit={saveFamilyDetails}>
                <div className="contentHead"><p>Step 1</p><h2>Family details</h2><span>Complete this form to unlock Compass chat. These details are used for age eligibility, fee estimates, and home distance.</span></div>
                <div className="formGrid">
                  <label>Child&apos;s date of birth<input name="dob" type="date" required defaultValue={familyDetails?.dob ?? "2023-06-10"} /></label>
                  <label>Admission date<input name="admission_date" type="date" required defaultValue={familyDetails?.admission_date ?? "2026-09-01"} /></label>
                  <label>Child citizenship<select name="citizenship" defaultValue={familyDetails?.citizenship ?? "SC"}><option value="SC">Singapore Citizen</option><option value="SPR">Permanent Resident</option><option value="Others">Other</option></select></label>
                  <label>Care programme<select name="programme_type" defaultValue={familyDetails?.programme_type ?? "full_day"}><option value="full_day">Full day</option><option value="half_day">Half day</option><option value="flexi_care_1">Flexi-care 1 (12–24 hours/week)</option><option value="flexi_care_2">Flexi-care 2 (confirm hours with centre)</option><option value="flexi_care_3">Flexi-care 3 (&gt;36–48 hours/week)</option></select></label>
                  <label>Gross monthly income<input name="income" type="number" min="0" required defaultValue={familyDetails?.gross_household_income ?? 4500} /></label>
                  <label>Applicant working hours/month<input name="working_hours" type="number" min="0" required defaultValue={familyDetails?.working_hours_per_month ?? 56} /></label>
                  <label>Household size<input name="household_size" type="number" min="1" required defaultValue={familyDetails?.household_size ?? 4} /></label>
                  <label>Non-earning dependants<input name="dependants" type="number" min="0" required defaultValue={familyDetails?.non_earning_dependants ?? 2} /></label>
                  <label>Home postal code<input value={homePostalCode} onChange={(e) => setHomePostalCode(e.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric" pattern="[0-9]{6}" required placeholder="540231" /></label>
                  <label className="checkField"><input name="special_approval" type="checkbox" defaultChecked={familyDetails?.special_approval ?? false} /><span>My circumstances may require ECDA Special Approval</span></label>
                </div>
                <p className="estimateNote">Fee results are estimates based on reported information and the cited ECDA policy, not subsidy approval.</p>
                <button className="primary" disabled={busy}>Save and continue to chat →</button>
              </form>}

              {tab === "form" && stage === "search" && <div className="contentForm"><div className="contentHead"><p>Family details saved</p><h2>Continue in Compass chat</h2><span>Describe your preschool preferences, then click Show recommendations.</span></div><button className="primary" onClick={() => { setStage("family"); setTab("form"); }}>Edit family details</button></div>}

              {tab === "form" && stage === "choose" && <div className="contentForm">
                <div className="contentHead"><p>Location ready</p><h2>Home to preschools</h2><span>Home postal code: {homePostalCode}. Select any number of preschools in Results and their distances will be calculated independently. Change hours, citizenship, programme, or Special Approval here, then show recommendations again.</span></div>
                <button className="primary" onClick={() => { setStage("family"); setTab("form"); }}>Edit family details</button>
              </div>}

              {tab === "results" && stage !== "choose" && <div className="emptyState"><span>⌁</span>{recommendationEmptyState === "hard_filters" ? <><h2>No schools met all applied filters</h2><p>The catalogue returned no candidates for these hard filters. Missing catalogue information may also prevent a school from being checked; review the required care level, language, and location.</p></> : recommendationEmptyState === "required_preferences" ? <><h2>No candidates met the required preferences</h2><p>No candidate remained after the required-preference check. Unknown or inferred evidence is not treated as a confirmed mismatch.</p></> : recommendationEmptyState === "distance_unknown" ? <><h2>Distance could not be confirmed</h2><p>No candidate with a known location was available within the requested distance. Schools without coordinates cannot be confirmed as near or far.</p></> : recommendationEmptyState === "distance_filtered" ? <><h2>No candidates were within the requested distance</h2><p>Candidates with known coordinates were outside the selected radius. You can explicitly increase the distance or remove that requirement.</p></> : recommendationEmptyState === "no_candidates" ? <><h2>No preschools matched these preferences</h2><p>No candidates remained after the current preference checks. Ask Compass which supported requirement could be changed, or update a preference and search again.</p></> : recommendationEmptyState === "no_eligible" ? <><h2>No eligible preschools in these results</h2><p>The Stage 1 candidates did not meet the current age and fee eligibility checks. Review family details and try again.</p><button className="primary" onClick={() => { setStage("family"); setTab("form"); }}>Review family details</button></> : <><h2>Recommendations are not ready</h2><p>{stage === "family" ? "Complete Family details first." : "Continue in Compass chat and show recommendations."}</p></>}</div>}

              {tab === "results" && stage === "choose" && <>

                <div className="rankingSummary"><div><strong>Recommendations for your family</strong><p>Each preschool shows which preferences its recorded information supports and what still needs confirmation.</p></div><span>{visibleEligible.length} of {eligible.length} schools</span></div>{appliedFilters(preferenceProfile).length > 0 && <p className="appliedFilters">Filters applied: {appliedFilters(preferenceProfile).join(" · ")}</p>}
                <div className="resultToolbar"><label>Distance from home<select value={distanceFilter} onChange={(event) => setDistanceFilter(event.target.value)}><option value="none">None</option>{distanceFilter !== "none" && !["1", "2", "3", "4", "5"].includes(distanceFilter) && <option value={distanceFilter}>Within {distanceFilter} km</option>}{[1, 2, 3, 4, 5].map((km) => <option value={km} key={km}>Within {km} km</option>)}</select></label><span>Filtering preserves the original rank</span></div>
                {distanceFilter !== "none" && eligible.length > Object.keys(distances).length && visibleEligible.length > 0 && <p className="appliedFilters">Distance is unknown for {eligible.length - Object.keys(distances).length} school(s) without coordinates; they are omitted from this distance-filtered view.</p>}
                <div className="resultList selectable">{recommendationEmptyState === "no_eligible" ? <div className="emptyState"><h2>No eligible preschools in these results</h2><p>The matched schools did not meet the current age and fee eligibility checks. Review family details or preferences and try again.</p><button className="primary" onClick={() => { setStage("family"); setTab("form"); }}>Review family details</button></div> : recommendationEmptyState === "distance_filtered" ? <div className="emptyState"><h2>No eligible schools with a known distance within {distanceFilter} km</h2><p>The eligible schools with calculable distances are outside this radius. Increase the distance or select None to see all eligible recommendations.</p></div> : recommendationEmptyState === "distance_unknown" ? <div className="emptyState"><h2>Distance is unknown for some schools</h2><p>No school with a calculated distance is within {distanceFilter} km. {Math.max(0, eligible.length - Object.keys(distances).length)} eligible school(s) have no coordinates, so their distance cannot be confirmed.</p></div> : visibleEligible.map((centre) => { const scores = getRecommendationScores(centre); const postalCode = formatPostalCode(centre.postal_code); return <article className={selected.includes(centre.school_id) ? "selected" : ""} key={centre.school_id}>
                  <button className="resultChoice" onClick={() => toggleSchool(centre.school_id)}>
                    <span className="selectMark">✓</span>
                    <div>
                      <span className="rankBadge">#{eligible.findIndex((item) => item.school_id === centre.school_id) + 1}</span>
                      <h3>{centre.name}{postalCode && <span className="schoolPostalCode">(Postal code: {postalCode})</span>}</h3>
                      <p>{centre.eligible_level ?? "Preschool"} · Age/fee eligible</p>
                    </div>
                    {routes[centre.school_id] && <div className="schoolMetrics"><strong className="distanceMetric">{routes[centre.school_id].total_distance_km.toFixed(2)} km<small>route from home</small></strong></div>}
                  </button>
                  <RecommendationExplanation centre={centre} profile={preferenceProfile} distanceKm={distances[centre.school_id]} />
                  {centre.programme_options && centre.programme_options.length > 0 && <div className="programmePicker"><label>Programme<select value={centre.programme_id ?? ""} disabled={programmeBusy === centre.school_id} onChange={(event) => void changeProgramme(centre.school_id, event.target.value as ProgrammeId)}>{centre.programme_options.map((option) => <option value={option.programme_id} key={option.programme_id}>{option.service_label} — {money.format(option.net_monthly_fee)}/month</option>)}</select></label>{centre.preferred_programme_available === false && <small>Your preferred programme is unavailable at this school; the lowest-fee available option is shown.</small>}</div>}
                  <FeeNotes centre={centre} />
                  <ParentMentionLinks centre={centre} />
                  <SchoolRatingPanel centre={centre} sessionId={anonymousSessionId} onRated={updateParentRating} />
                  <details className="scoreBreakdown"><summary>Optional ranking details</summary><div>
                    <p><small>Preference match: {scores.match}. Evidence completeness: {scores.evidence}. Combined ranking score: {scores.combined}. This combined score determines order before age and fee eligibility filtering.</small></p>
                    <p><small>Combined score = √(preference-match percentage × evidence-coverage percentage). The ranking balances preference match with the share of weighted preferences that have usable information. These internal measures do not establish factual accuracy.</small></p>
                  </div></details>
                </article>; })}</div>
                <div className="rankingHelp"><p>Fees are estimates; review the notes on each preschool. Parent mentions online are web searches, not KinderCompass evidence. First-party parent ratings are shown separately and do not affect recommendation order.</p></div>

              </>}

              {tab === "map" && <div className="mapPanel mapTab">
                <div className="mapHead"><div><span>Live map</span><h2>Home to preschools</h2></div><div className="legend"><span><i className="home" />Home</span><span><i className="school" />Preschools</span></div></div>
                <LiveMap points={mapPoints} />
                {mapBusy && <div className="mapHint">Updating map…</div>}
                {!mapBusy && !mapPoints.length && <div className="mapHint">Enter a valid home postal code to display its location.</div>}
              </div>}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
