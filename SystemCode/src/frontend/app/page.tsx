"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import LiveMap, { MapPoint } from "./LiveMap";

type ProgrammeId = "full_day" | "half_day_am" | "half_day_pm" |
  "flexi_care_1" | "flexi_care_1_am" | "flexi_care_1_pm" |
  "flexi_care_2" | "flexi_care_3";

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
  minimum_copayment?: number;
  programme_id?: ProgrammeId;
  service_label?: string;
  preferred_programme_available?: boolean;
  programme_options?: ProgrammeOption[];
  warnings?: string[];
  policy_source?: { policy_id: string; authority: string; effective_from: string; source_url: string };
  distance_km?: number;
  match_score?: number;
  profile_confidence?: number;
  strengths?: string[];
  tradeoffs?: string[];
  match_breakdown?: { attribute: string; preference: unknown; matched: boolean | null; status: "matched" | "not_matched" | "unknown"; importance: string; contribution: number; possible_contribution: number; evidence_state: "verified" | "derived" | "calculated" | "unknown"; value_state: "confirmed_yes" | "confirmed_no" | "confirmed_value" | "unknown"; source: string; source_method: string; source_reliability: string; source_date?: string | null; freshness: "current" | "stale" | "future_dated" | "unknown" }[];
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
type PreferenceProfile = { hard_constraints: Record<string, unknown>; preferences: Record<string, unknown>; preference_items?: PreferenceItem[]; recognized?: string[] };
type FamilyDetails = { dob: string; admission_date: string; gross_household_income: number; citizenship: "SC" | "SPR" | "Others"; programme_type: "full_day" | "half_day" | "flexi_care_1" | "flexi_care_2" | "flexi_care_3"; working_hours_per_month: number; household_size: number; non_earning_dependants: number; special_approval: boolean };
type FeedbackEvent = "selected" | "rejected" | "contacted" | "visited" | "applied" | "rated";
type FeedbackReason = "good_match" | "fee" | "distance" | "programme" | "evidence" | "other";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const money = new Intl.NumberFormat("en-SG", { style: "currency", currency: "SGD", maximumFractionDigits: 0 });
function sourceDateLabel(value?: string | null): string {
  if (!value) return "Unavailable";
  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(date.getTime())
    ? "Unavailable"
    : new Intl.DateTimeFormat("en-SG", { day: "numeric", month: "long", year: "numeric" }).format(date);
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.detail ?? "Something went wrong. Please try again.");
  return data;
}

export default function Home() {
  const [stage, setStage] = useState<"family" | "search" | "choose">("family");
  const [tab, setTab] = useState<"form" | "results" | "ratings">("form");
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
  const [recommendationTrace, setRecommendationTrace] = useState("");
  const [anonymousSessionId, setAnonymousSessionId] = useState("");
  const [rememberPreferences, setRememberPreferences] = useState(false);
  const [memoryStatus, setMemoryStatus] = useState("");
  const [feedbackSchoolId, setFeedbackSchoolId] = useState("");
  const [feedbackEvent, setFeedbackEvent] = useState<FeedbackEvent>("selected");
  const [feedbackReason, setFeedbackReason] = useState<FeedbackReason>("good_match");
  const [feedbackRating, setFeedbackRating] = useState("5");
  const [feedbackConsent, setFeedbackConsent] = useState(false);
  const [feedbackStatus, setFeedbackStatus] = useState("");

  const mapPoints = useMemo<MapPoint[]>(() => {
    const comparisons = Object.values(routes);
    if (comparisons.length) {
      return [comparisons[0].schedule[0], ...comparisons.map((comparison) => comparison.schedule[1])];
    }
    return homePoint ? [homePoint] : [];
  }, [homePoint, routes]);

  const visibleEligible = useMemo(() => {
    if (distanceFilter === "none") return eligible;
    const maximum = Number(distanceFilter);
    return eligible.filter((centre) => distances[centre.school_id] != null && distances[centre.school_id] <= maximum);
  }, [distanceFilter, distances, eligible]);

  useEffect(() => {
    const key = "kindercompass-anonymous-session";
    const existing = window.localStorage.getItem(key);
    const value = existing ?? window.crypto.randomUUID();
    if (!existing) window.localStorage.setItem(key, value);
    setAnonymousSessionId(value);
    if (window.localStorage.getItem("kindercompass-remember-preferences") === "true") {
      setRememberPreferences(true);
      void post<{ found: boolean; profile?: PreferenceProfile; understood: string[] }>("/api/memory/restore", {
        anonymous_session_id: value,
      }).then((result) => {
        if (!result.found || !result.profile) return;
        setPreferenceProfile(result.profile);
        setUnderstood(result.understood);
        setReadyToSearch(Boolean(Object.keys(result.profile.hard_constraints).length || Object.keys(result.profile.preferences).length));
        setMessages((items) => [...items, { role: "assistant", text: "I restored your saved preschool preferences and unresolved decision state. Family details and previous chat messages were not stored." }]);
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
        anonymous_session_id: rememberPreferences ? anonymousSessionId : undefined,
        remember_preferences: rememberPreferences,
      });
      setPreferenceProfile(result.profile); setUnderstood(result.understood);
      const distancePreference = result.profile.preference_items?.find((item) => item.attribute === "max_distance_km");
      setDistanceFilter(distancePreference ? String(distancePreference.value) : "none");
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
    try {
      const distancePreference = preferenceProfile.preference_items?.find((item) => item.attribute === "max_distance_km");
      const requestedRadius = distancePreference ? Number(distancePreference.value) : undefined;
      const searchResult = await post<{ centres: Centre[]; trace: { trace_id: string }; message: string; profile: PreferenceProfile }>("/api/search", {
        profile: preferenceProfile,
        ...(requestedRadius ? { home_postal_code: homePostalCode, radius_km: requestedRadius } : {}),
      });
      if (searchResult.centres.length === 0) {
        setPreferenceProfile(searchResult.profile);
        setReadyToSearch(false);
        setEligible([]); setSelected([]); setRoutes({});
        setMessages((items) => [...items, { role: "assistant", text: searchResult.message }]);
        setStage("search"); setTab("form");
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
      setExcluded(evaluationResult.centres.filter((centre) => !centre.eligible).map((centre) => centre.school_id));
      setRecommendationTrace(searchResult.trace.trace_id);
      setFeedbackSchoolId(eligibleCentres[0]?.school_id ?? "");
      setFeedbackStatus("");
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

  async function changePreferenceMemory(enabled: boolean) {
    setMemoryStatus("");
    if (!anonymousSessionId) return;
    try {
      if (enabled) {
        window.localStorage.setItem("kindercompass-remember-preferences", "true");
        setRememberPreferences(true);
        if (preferenceProfile) {
          await post("/api/memory/save", { anonymous_session_id: anonymousSessionId, profile: preferenceProfile });
        }
        setMemoryStatus("Structured preferences will be remembered for up to 180 days.");
      } else {
        await post("/api/memory/forget", { anonymous_session_id: anonymousSessionId });
        window.localStorage.removeItem("kindercompass-remember-preferences");
        setRememberPreferences(false);
        setMemoryStatus("Saved preferences were forgotten.");
      }
    } catch (caught) {
      setMemoryStatus((caught as Error).message);
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

  async function submitFeedback(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!recommendationTrace || !anonymousSessionId || !feedbackSchoolId || !feedbackConsent) return;
    setBusy(true); setError(""); setFeedbackStatus("");
    try {
      await post<{ event_id: string; status: "recorded" }>("/api/feedback", {
        trace_id: recommendationTrace,
        anonymous_session_id: anonymousSessionId,
        school_id: feedbackSchoolId,
        event_type: feedbackEvent,
        reason: feedbackReason,
        rating: feedbackEvent === "rated" ? Number(feedbackRating) : null,
        consent: true,
      });
      setFeedbackStatus("Thank you. Your anonymous feedback was recorded.");
      setFeedbackConsent(false);
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function updateImportance(attribute: string, value: unknown, importance: PreferenceImportance) {
    setPreferenceProfile((profile) => profile ? {
      ...profile,
      preference_items: profile.preference_items?.map((item) =>
        item.attribute === attribute && item.value === value ? { ...item, importance } : item
      ),
    } : profile);
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
          {understood.length > 0 && <><details className="preferenceSummary"><summary><strong>Understood preferences</strong><span>{understood.length}</span></summary><div className="preferenceContent"><div className="preferenceChips">{understood.map((item) => <span key={item}>{item}</span>)}</div>{preferenceProfile?.preference_items?.some((item) => !["care_level", "max_distance_km"].includes(item.attribute) && !(item.attribute === "language" && preferenceProfile.hard_constraints.language)) && <div className="importanceControls"><strong>Adjust ranking importance</strong>{preferenceProfile.preference_items.filter((item) => !["care_level", "max_distance_km"].includes(item.attribute) && !(item.attribute === "language" && preferenceProfile.hard_constraints.language)).map((item) => <label key={`${item.attribute}-${String(item.value)}`}><span>{item.attribute.replaceAll("_", " ")}</span><select value={item.importance} onChange={(event) => updateImportance(item.attribute, item.value, event.target.value as PreferenceImportance)}><option value="required">Required</option><option value="high_priority">High priority</option><option value="preferred">Preferred</option><option value="nice_to_have">Nice to have</option></select></label>)}</div>}<small>Send another message to add or correct these preferences.</small></div></details><div className="recommendationAction"><button onClick={confirmSearch} disabled={busy || !readyToSearch}>Show recommendations</button></div></>}
          <div className="messages" aria-live="polite">
            {messages.map((message, index) => <div className={`message ${message.role}`} key={`${message.role}-${index}`}><span>{message.text}</span>{message.evidenceCategory && <small className={`evidenceLabel ${message.evidenceCategory}`}>Evidence: {message.evidenceCategory.replaceAll("_", " ")}</small>}{message.citations?.length ? <div className="messageSources"><strong>Sources</strong>{message.citations.map((citation, sourceIndex) => <a href={citation.url} target="_blank" rel="noreferrer" key={citation.chunk_id}>[{sourceIndex + 1}] {citation.title}<small>{citation.evidence_scope === "general" ? "General guidance" : "School evidence"}{citation.authority ? ` · ${citation.authority}` : ""}{citation.effective_from ? ` · Effective ${sourceDateLabel(citation.effective_from)}` : ""} · Retrieved {sourceDateLabel(citation.retrieved_at)}</small></a>)}</div> : null}{message.answerId && <div className="answerRating"><small>Was this useful?</small><button className={message.usefulness === "helpful" ? "selected" : ""} onClick={() => void rateChatAnswer(message.answerId!, true)} aria-label="Helpful answer">Yes</button><button className={message.usefulness === "not_helpful" ? "selected" : ""} onClick={() => void rateChatAnswer(message.answerId!, false)} aria-label="Not helpful answer">No</button></div>}</div>)}
            {busy && <div className="message assistant typing">Thinking…</div>}
          </div>
          <form className="chatComposer" onSubmit={sendPreference}>
            <textarea required minLength={2} maxLength={500} disabled={!familyDetails || busy} value={preference} onChange={(event) => setPreference(event.target.value)} placeholder={familyDetails ? "Ask for Montessori, bilingual, play-based…" : "Complete Family details to unlock chat"} />
            <button className="primary" disabled={!familyDetails || busy}>Send <span>↑</span></button>
          </form>
          <div className="memoryControl">
            <label><input type="checkbox" checked={rememberPreferences} onChange={(event) => void changePreferenceMemory(event.target.checked)} /><span>Remember my structured preferences on this device</span></label>
            <small>Saves compact preferences and unresolved decisions—not chat text, postal code, income, or child details. {memoryStatus}</small>
          </div>
        </aside>

        <section className="rightColumn">
          <div className="displayPanel">
            <div className="tabs">
              <button className={tab === "form" ? "active" : ""} onClick={() => setTab("form")}>Form</button>
              <button className={tab === "results" ? "active" : ""} onClick={() => setTab("results")}>Results <span>{stage === "choose" ? eligible.length : 0}</span></button>
              <button className={tab === "ratings" ? "active" : ""} onClick={() => setTab("ratings")}>Feedback</button>
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
                <div className="contentHead"><p>Location ready</p><h2>Home to preschools</h2><span>Home postal code: {homePostalCode}. Select any number of preschools in Results and their distances will be calculated independently.</span></div>
              </div>}

              {tab === "results" && stage !== "choose" && <div className="emptyState"><span>⌁</span><h2>Recommendations are not ready</h2><p>{stage === "family" ? "Complete Family details first." : "Continue in Compass chat and show recommendations."}</p></div>}

              {tab === "results" && stage === "choose" && <>
                <div className="rankingSummary"><div><strong>Ranked recommendations</strong><p>Ordered by preference match, then evidence confidence.</p></div><span>{visibleEligible.length} of {eligible.length} schools</span></div>
                <div className="resultToolbar"><label>Distance from home<select value={distanceFilter} onChange={(event) => setDistanceFilter(event.target.value)}><option value="none">None</option>{distanceFilter !== "none" && !["1", "2", "3", "4", "5"].includes(distanceFilter) && <option value={distanceFilter}>Within {distanceFilter} km</option>}{[1, 2, 3, 4, 5].map((km) => <option value={km} key={km}>Within {km} km</option>)}</select></label><span>Filtering preserves the original rank</span></div>
                <div className="resultList selectable">{visibleEligible.length === 0 ? <div className="emptyState"><h2>No schools within this distance</h2><p>Increase the distance or select None.</p></div> : visibleEligible.map((centre) => <article className={selected.includes(centre.school_id) ? "selected" : ""} key={centre.school_id}><button className="resultChoice" onClick={() => toggleSchool(centre.school_id)}><span className="selectMark">✓</span><div><span className="rankBadge">#{eligible.findIndex((item) => item.school_id === centre.school_id) + 1}</span><small>{centre.match_score?.toFixed(0) ?? "—"}% match · {((centre.profile_confidence ?? 0) * 100).toFixed(0)}% evidence · Eligible · {centre.eligible_level}</small><h3>{centre.name}</h3><p>{centre.strengths?.length ? `Strengths: ${centre.strengths.join(", ")}` : "Limited preference evidence"}{centre.tradeoffs?.length ? ` · Trade-offs: ${centre.tradeoffs.join(", ")}` : ""}</p><p>{distances[centre.school_id] != null ? `${distances[centre.school_id].toFixed(2)} km from home` : "Distance unavailable"}</p></div><div className="schoolMetrics"><strong>{money.format(centre.net_monthly_fee ?? 0)}<small>/month</small></strong>{routes[centre.school_id] && <strong className="distanceMetric">{routes[centre.school_id].total_distance_km.toFixed(2)} km<small>from home</small></strong>}</div></button>{centre.programme_options && centre.programme_options.length > 0 && <div className="programmePicker"><label>Programme<select value={centre.programme_id ?? ""} disabled={programmeBusy === centre.school_id} onChange={(event) => void changeProgramme(centre.school_id, event.target.value as ProgrammeId)}>{centre.programme_options.map((option) => <option value={option.programme_id} key={option.programme_id}>{option.service_label} — {money.format(option.net_monthly_fee)}/month</option>)}</select></label>{centre.preferred_programme_available === false && <small>Your preferred programme is unavailable at this school; the lowest-fee available option is shown.</small>}</div>}<details className="scoreBreakdown"><summary>How this score was calculated</summary><div>{centre.match_breakdown?.length ? centre.match_breakdown.map((item) => <p key={item.attribute}><strong>{item.attribute.split(":")[0].replaceAll("_", " ")}</strong><span className={`evidenceStatus ${item.status}`}>{item.status.replaceAll("_", " ")}</span><small>{item.importance.replaceAll("_", " ")} · {item.contribution} of {item.possible_contribution} verified points</small><small>Source: {item.source} · Evidence: {item.evidence_state} · Last updated: {sourceDateLabel(item.source_date)}</small></p>) : <p>All requested features were applied as required filters. The remaining schools satisfy those verifiable requirements, but no preferred criteria were available to rank them further.</p>}</div></details></article>)}</div>
                <div className="rankingHelp"><p><strong>Preference match</strong> means how well the school matches requested features.</p><p><strong>Evidence confidence</strong> means how much usable school data was available to evaluate those features.</p></div>
              </>}

              {tab === "ratings" && stage !== "choose" && <div className="emptyState"><span>☆</span><h2>Ratings are not ready</h2><p>Generate recommendations before submitting feedback.</p></div>}

              {tab === "ratings" && stage === "choose" && <form className="feedbackPanel" onSubmit={submitFeedback}><div className="contentHead"><p>Optional feedback</p><h2>Feedback</h2><span>Your anonymous feedback is linked only to this recommendation result. Family details and chat text are not stored.</span></div><div className="feedbackFields"><label>School<select value={feedbackSchoolId} onChange={(event) => setFeedbackSchoolId(event.target.value)}>{eligible.map((centre) => <option value={centre.school_id} key={centre.school_id}>{centre.name}</option>)}</select></label><label>Outcome<select value={feedbackEvent} onChange={(event) => setFeedbackEvent(event.target.value as FeedbackEvent)}><option value="selected">Selected for comparison</option><option value="rejected">Rejected</option><option value="contacted">Contacted centre</option><option value="visited">Visited centre</option><option value="applied">Applied</option><option value="rated">Rate recommendation</option></select></label><label>Main reason<select value={feedbackReason} onChange={(event) => setFeedbackReason(event.target.value as FeedbackReason)}><option value="good_match">Good match</option><option value="fee">Fee</option><option value="distance">Distance</option><option value="programme">Programme</option><option value="evidence">Evidence quality</option><option value="other">Other</option></select></label>{feedbackEvent === "rated" && <label>Usefulness<select value={feedbackRating} onChange={(event) => setFeedbackRating(event.target.value)}>{[5, 4, 3, 2, 1].map((rating) => <option value={rating} key={rating}>{rating} / 5</option>)}</select></label>}</div><label className="feedbackConsent"><input type="checkbox" checked={feedbackConsent} onChange={(event) => setFeedbackConsent(event.target.checked)} /><span>I consent to storing this anonymous feedback for recommendation evaluation.</span></label><button className="primary" disabled={busy || !feedbackConsent || !feedbackSchoolId}>Submit feedback</button>{feedbackStatus && <small className="feedbackSuccess">{feedbackStatus}</small>}</form>}
            </div>
          </div>

          <div className="mapPanel">
            <div className="mapHead"><div><span>Live map</span><h2>Home to preschools</h2></div><div className="legend"><span><i className="home" />Home</span><span><i className="school" />Preschools</span></div></div>
            <LiveMap points={mapPoints} />
            {mapBusy && <div className="mapHint">Updating map…</div>}
            {!mapBusy && !mapPoints.length && <div className="mapHint">Enter a valid home postal code to display its location.</div>}
          </div>
        </section>
      </div>
    </main>
  );
}
