import csv
import tempfile
import unittest
from unittest import mock
from datetime import datetime, timezone
from pathlib import Path

from stage1.web_rag import (
    PageContent,
    FetchError,
    PilotError,
    automate_allowlist,
    automate_shared_pages,
    chunk_text,
    extract_html,
    fetch_page_with_browser_fallback,
    ingest_allowlist,
    ingest_operator_pages,
    load_json,
    retrieve,
    retrieve_operator_evidence,
    webpage_freshness,
    validate_allowlist,
    verify_school_identity,
)
from scripts.automate_web_rag_pilot import run_incremental
from scripts.audit_web_rag_readiness import audit as audit_readiness
from scripts.review_web_rag_audit import export_packets, import_packets


def approved(school_id="A", url="https://school.example/centre-a"):
    return {
        "school_id": school_id,
        "school_name": f"School {school_id}",
        "url": url,
        "review_status": "approved",
        "reviewed_at": "2026-08-10",
        "reviewer": "pilot-reviewer",
        "identity_matches": [
            {"type": "postal_code", "expected": "123456", "observed": "123456", "matched": True},
            {"type": "centre_code", "expected": school_id, "observed": school_id, "matched": True},
        ],
    }


def page(url: str, text: str) -> PageContent:
    return PageContent(
        requested_url=url,
        final_url=url,
        title="Official centre page",
        text=text,
        retrieved_at="2026-08-10T00:00:00+00:00",
        content_hash=("a" if "centre-a" in url else "b") * 64,
    )


class WebRagPilotTests(unittest.TestCase):
    def test_review_packet_export_import_round_trip(self):
        index = {"pages": [{"school_id": "A", "source_url": "https://a.example", "chunks": [{
            "chunk_id": "A:1", "school_id": "A", "text": "Outdoor learning in our garden.",
            "source_url": "https://a.example", "title": "A", "retrieved_at": "2026-08-10", "content_hash": "a",
        }]}], "operator_pages": []}
        decisions = [{
            "school_id": "A", "school_name": "School A", "url": "https://a.example",
            "review_status": "approved", "identity_confidence": "high",
            "identity_matches": [{"type": "postal_code", "matched": True}],
        }]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identity_path = root / "identity.csv"
            retrieval_path = root / "retrieval.csv"
            labels_path = root / "labels.json"
            counts = export_packets(
                index, decisions, [], identity_path=identity_path,
                retrieval_path=retrieval_path, overwrite=False,
            )
            self.assertEqual(counts["identity_rows"], 1)
            self.assertGreaterEqual(counts["retrieval_rows"], 1)
            with self.assertRaises(FileExistsError):
                export_packets(index, decisions, [], identity_path=identity_path, retrieval_path=retrieval_path)

            def complete(path, updates):
                with path.open("r", encoding="utf-8-sig", newline="") as handle:
                    rows = list(csv.DictReader(handle))
                    fields = list(rows[0])
                rows[0].update(updates)
                with path.open("w", encoding="utf-8-sig", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(rows)

            complete(identity_path, {"include_in_audit": "yes", "human_expected_identity": "school"})
            complete(retrieval_path, {
                "include_in_audit": "yes", "human_expected_scope": "school",
                "human_evidence_expected": "yes", "human_expected_terms": "outdoor | learning",
                "human_expected_source_contains": "a.example",
            })
            imported = import_packets(identity_path, retrieval_path, labels_path)
            labels = load_json(labels_path)
            self.assertEqual(imported, {"identity_imported": 1, "retrieval_imported": 1})
            self.assertEqual(labels["identity_cases"][0]["expected_identity"], "school")
            self.assertEqual(labels["retrieval_cases"][0]["expected_terms"], ["outdoor", "learning"])

    def test_production_audit_enforces_sample_size_and_quality_gates(self):
        index = {"pages": [{"school_id": "A", "freshness": "current", "chunks": [{
            "chunk_id": "A:1", "school_id": "A", "text": "Outdoor learning in our garden.",
            "source_url": "https://a.example", "title": "A", "retrieved_at": "2026-08-10", "content_hash": "a",
        }]}], "operator_pages": []}
        labels = {
            "identity_cases": [{"case_id": "identity-a", "school_id": "A", "expected_identity": "school"}],
            "retrieval_cases": [{
                "case_id": "outdoor-a", "school_id": "A", "query": "outdoor learning",
                "expected_scope": "school", "evidence_expected": True,
                "expected_terms": ["outdoor", "learning"], "expected_source_contains": "a.example",
            }],
        }
        report = audit_readiness(
            index, [{"school_id": "A", "review_status": "approved"}], [], labels,
            thresholds={"minimum_identity_cases": 1, "minimum_identity_assessed_cases": 1,
                        "minimum_retrieval_cases": 1},
        )
        self.assertTrue(report["production_ready"])
        self.assertEqual(report["metrics"]["retrieval_accuracy"], 1.0)
        insufficient = audit_readiness(index, [{"school_id": "A", "review_status": "approved"}], [], labels)
        self.assertFalse(insufficient["production_ready"])
        self.assertFalse(insufficient["gates"]["identity_sample_size"])

    def test_production_audit_separates_fetch_failure_from_identity_accuracy(self):
        labels = {"identity_cases": [
            {"case_id": "identity-a", "school_id": "A", "expected_identity": "school"},
            {"case_id": "identity-b", "school_id": "B", "expected_identity": "school"},
        ], "retrieval_cases": []}
        report = audit_readiness(
            {"pages": [], "operator_pages": []},
            [{"school_id": "A", "review_status": "approved"},
             {"school_id": "B", "review_status": "fetch_failed"}], [], labels,
            thresholds={"minimum_identity_cases": 1, "minimum_identity_assessed_cases": 1,
                        "minimum_retrieval_cases": 0, "fetch_success_rate": 0.0},
        )
        self.assertEqual(report["metrics"]["identity_accuracy"], 1.0)
        self.assertEqual(report["metrics"]["identity_assessment_coverage"], 0.5)
        self.assertEqual(report["metrics"]["fetch_success_rate"], 0.5)

    def test_production_audit_excludes_robots_denials_from_fetch_success_denominator(self):
        labels = {"identity_cases": [
            {"case_id": "identity-a", "school_id": "A", "expected_identity": "school"},
            {"case_id": "identity-b", "school_id": "B", "expected_identity": "school"},
        ], "retrieval_cases": []}
        report = audit_readiness(
            {"pages": [], "operator_pages": []},
            [{"school_id": "A", "review_status": "approved"},
             {"school_id": "B", "review_status": "fetch_failed", "failure_code": "robots_disallowed"}],
            [], labels,
        )
        self.assertEqual(report["metrics"]["fetch_eligible_cases"], 1)
        self.assertEqual(report["metrics"]["policy_excluded_cases"], 1)
        self.assertEqual(report["metrics"]["fetch_success_rate"], 1.0)

    def test_production_audit_accepts_empty_negative_without_source(self):
        labels = {"identity_cases": [], "retrieval_cases": [{
            "case_id": "negative-a", "school_id": "A", "query": "fees",
            "expected_scope": "school", "evidence_expected": False,
            "expected_terms": [], "expected_source_contains": "a.example",
        }]}
        report = audit_readiness({"pages": [], "operator_pages": []}, [], [], labels)
        result = report["retrieval_results"][0]
        self.assertTrue(result["passed"])
        self.assertTrue(result["source_correct"])

    def test_production_audit_treats_expected_terms_as_alternatives(self):
        index = {"pages": [{"school_id": "A", "chunks": [{
            "chunk_id": "A:1", "school_id": "A", "text": "A literature-based curriculum.",
            "source_url": "https://a.example", "title": "A", "retrieved_at": "2026-08-10",
        }]}], "operator_pages": []}
        labels = {"identity_cases": [], "retrieval_cases": [{
            "case_id": "curriculum-a", "school_id": "A", "query": "curriculum",
            "expected_scope": "school", "evidence_expected": True,
            "expected_terms": ["literature-based", "activity-based"],
            "expected_source_contains": "a.example",
        }]}
        report = audit_readiness(index, [], [], labels)
        self.assertTrue(report["retrieval_results"][0]["passed"])

    def test_webpage_freshness_labels(self):
        now = datetime(2026, 8, 10, tzinfo=timezone.utc)
        self.assertEqual(webpage_freshness("2026-08-01T00:00:00+00:00", now=now), "current")
        self.assertEqual(webpage_freshness("2026-06-20T00:00:00+00:00", now=now), "aging")
        self.assertEqual(webpage_freshness("2026-01-01T00:00:00+00:00", now=now), "stale")
        self.assertEqual(webpage_freshness(None, now=now), "unknown")

    def test_due_refresh_detects_unchanged_content(self):
        record = {
            "school_id": "A", "centre_code": "A100", "centre_name_x": "Bright Kids River",
            "centre_address": "10 River Road Singapore 123456", "postal_code": 123456,
            "centre_website": "https://school.example/river",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            options = {
                "allowlist_path": root / "schools.json", "operator_allowlist_path": root / "operators.json",
                "output_path": root / "index.json", "limit": 1, "shared_limit": 0,
                "delay_seconds": 0, "refresh_after_days": 30,
                "fetcher": lambda url: page(url, "Bright Kids River at 10 River Road Singapore 123456."),
            }
            run_incremental([record], now=datetime(2026, 8, 10, tzinfo=timezone.utc), **options)
            refreshed = run_incremental([record], now=datetime(2026, 9, 15, tzinfo=timezone.utc), **options)
            self.assertEqual(refreshed["school_attempts"], 1)
            self.assertEqual(refreshed["school_decisions"][0]["change_status"], "unchanged")

    def test_due_refresh_detects_change_and_redirect(self):
        record = {
            "school_id": "A", "centre_code": "A100", "centre_name_x": "Bright Kids River",
            "centre_address": "10 River Road Singapore 123456", "postal_code": 123456,
            "centre_website": "https://school.example/river",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            options = {
                "allowlist_path": root / "schools.json", "operator_allowlist_path": root / "operators.json",
                "output_path": root / "index.json", "limit": 1, "shared_limit": 0,
                "delay_seconds": 0, "refresh_after_days": 0,
            }
            original = page(record["centre_website"], "Bright Kids River at 10 River Road Singapore 123456.")
            run_incremental([record], fetcher=lambda _url: original, now=datetime(2026, 8, 10, tzinfo=timezone.utc), **options)
            redirected = PageContent(
                requested_url=record["centre_website"], final_url="https://school.example/new-river",
                title="Official centre page", text="Bright Kids River at 10 River Road Singapore 123456. New curriculum.",
                retrieved_at="2026-09-15T00:00:00+00:00", content_hash="c" * 64,
            )
            result = run_incremental(
                [record], fetcher=lambda _url: redirected,
                now=datetime(2026, 9, 15, tzinfo=timezone.utc), **options,
            )
            self.assertEqual(result["school_decisions"][0]["change_status"], "redirected")
            self.assertEqual(result["index"]["pages"][0]["content_hash"], "c" * 64)
            changed = PageContent(
                requested_url=record["centre_website"], final_url="https://school.example/new-river",
                title="Official centre page", text="Bright Kids River at 10 River Road Singapore 123456. Updated facilities.",
                retrieved_at="2026-09-16T00:00:00+00:00", content_hash="d" * 64,
            )
            changed_result = run_incremental(
                [record], fetcher=lambda _url: changed,
                now=datetime(2026, 9, 16, tzinfo=timezone.utc), **options,
            )
            self.assertEqual(changed_result["school_decisions"][0]["change_status"], "changed")

    def test_refresh_failure_preserves_last_known_evidence(self):
        record = {
            "school_id": "A", "centre_code": "A100", "centre_name_x": "Bright Kids River",
            "centre_address": "10 River Road Singapore 123456", "postal_code": 123456,
            "centre_website": "https://school.example/river",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            options = {
                "allowlist_path": root / "schools.json", "operator_allowlist_path": root / "operators.json",
                "output_path": root / "index.json", "limit": 1, "shared_limit": 0,
                "delay_seconds": 0, "refresh_after_days": 0,
            }
            run_incremental(
                [record], fetcher=lambda url: page(url, "Bright Kids River at 10 River Road Singapore 123456."),
                now=datetime(2026, 8, 10, tzinfo=timezone.utc), **options,
            )

            def unavailable(_url):
                raise PilotError("temporary timeout")

            result = run_incremental(
                [record], fetcher=unavailable, now=datetime(2026, 9, 15, tzinfo=timezone.utc), **options
            )
            self.assertEqual(result["school_decisions"][0]["change_status"], "unavailable")
            self.assertEqual(len(result["index"]["pages"]), 1)
            self.assertEqual(result["index"]["pages"][0]["change_status"], "unavailable")
    def test_retrieval_ranks_exact_phrase_above_scattered_terms(self):
        index = {"pages": [{"school_id": "A", "chunks": [
            {
                "chunk_id": "A:1", "school_id": "A", "text": "Outdoor spaces support creative play and learning.",
                "source_url": "https://a.example", "title": "A", "retrieved_at": "2026-08-10", "content_hash": "a",
            },
            {
                "chunk_id": "A:2", "school_id": "A", "text": "Children participate in outdoor learning every morning.",
                "source_url": "https://a.example", "title": "A", "retrieved_at": "2026-08-10", "content_hash": "a",
            },
        ]}]}
        results = retrieve(index, "A", "outdoor learning")
        self.assertEqual(results[0]["chunk_id"], "A:2")
        self.assertTrue(results[0]["phrase_match"])
        self.assertGreater(results[0]["score"], results[1]["score"])

    def test_retrieval_uses_controlled_synonyms(self):
        report = ingest_allowlist(
            [approved()], fetcher=lambda url: page(url, "Children learn in a spacious garden."), delay_seconds=0
        )
        results = retrieve(report, "A", "playground")
        self.assertTrue(results)
        self.assertIn("playground", results[0]["matched_query_terms"])

    def test_retrieval_rejects_weak_partial_match(self):
        report = ingest_allowlist(
            [approved()], fetcher=lambda url: page(url, "The centre has an outdoor area."), delay_seconds=0
        )
        self.assertEqual(retrieve(report, "A", "outdoor bilingual fees transport"), [])

    def test_retrieval_language_query_requires_language_evidence(self):
        report = ingest_allowlist(
            [approved()], fetcher=lambda url: page(url, "Children enjoy learning opportunities and communication."),
            delay_seconds=0,
        )
        self.assertEqual(retrieve(report, "A", "what languages are taught"), [])

    def test_retrieval_language_query_accepts_named_languages(self):
        report = ingest_allowlist(
            [approved()], fetcher=lambda url: page(url, "Children learn English and Mandarin every day."),
            delay_seconds=0,
        )
        self.assertTrue(retrieve(report, "A", "what languages are taught"))

    def test_retrieval_outdoor_query_rejects_indoor_only_playground(self):
        report = ingest_allowlist(
            [approved()], fetcher=lambda url: page(url, "The centre has a spacious indoor playground."),
            delay_seconds=0,
        )
        self.assertEqual(retrieve(report, "A", "does this branch have an outdoor playground"), [])

    def test_retrieval_fee_query_requires_fee_evidence(self):
        report = ingest_allowlist(
            [approved()], fetcher=lambda url: page(url, "Families join our curriculum and activities."),
            delay_seconds=0,
        )
        self.assertEqual(retrieve(report, "A", "how much are the school fees"), [])

    def test_retrieval_curriculum_query_rejects_generic_programme_wording(self):
        report = ingest_allowlist(
            [approved()], fetcher=lambda url: page(url, "Our programme helps every unique child develop."),
            delay_seconds=0,
        )
        self.assertEqual(retrieve(report, "A", "what curriculum does the preschool have"), [])

    def test_retrieval_philosophy_query_matches_belief_statement(self):
        report = ingest_allowlist(
            [approved()], fetcher=lambda url: page(url, "We believe learning should be fun for children."),
            delay_seconds=0,
        )
        self.assertTrue(retrieve(report, "A", "what learning methods does the school emphasise"))

    def test_retrieval_fee_query_ignores_conversational_how_much_wording(self):
        report = ingest_allowlist(
            [approved()], fetcher=lambda url: page(url, "We provide affordable fees for every family."),
            delay_seconds=0,
        )
        self.assertTrue(retrieve(report, "A", "How much are the preschool fees and are there subsidies?"))

    def test_retrieval_curriculum_prefers_specific_method_over_generic_mention(self):
        index = {"pages": [{"school_id": "A", "chunks": [
            {"chunk_id": "A:1", "school_id": "A", "text": "Quality standards in curriculum and pedagogy.",
             "source_url": "https://a.example", "title": "A", "retrieved_at": "2026-08-10"},
            {"chunk_id": "A:2", "school_id": "A", "text": "Our literature-based curriculum uses an activity-based approach.",
             "source_url": "https://a.example", "title": "A", "retrieved_at": "2026-08-10"},
        ]}], "operator_pages": []}
        results = retrieve(index, "A", "What kind of curriculum does the preschool have?")
        self.assertEqual(results[0]["chunk_id"], "A:2")

    def test_retrieval_facilities_query_rejects_figurative_environment(self):
        report = ingest_allowlist(
            [approved()], fetcher=lambda url: page(url, "We create an environment children look forward to."),
            delay_seconds=0,
        )
        self.assertEqual(retrieve(report, "A", "how is the learning environment"), [])

    def test_retrieval_ignores_stopword_only_query(self):
        report = ingest_allowlist(
            [approved()], fetcher=lambda url: page(url, "A detailed curriculum."), delay_seconds=0
        )
        self.assertEqual(retrieve(report, "A", "is this the school"), [])

    def test_retrieval_ignores_possessive_suffix(self):
        index = {"operator_pages": [{"linked_school_ids": ["A"], "chunks": [{
            "chunk_id": "OP:1", "operator_id": "OP", "school_id": None,
            "linked_school_ids": ["A"], "evidence_scope": "operator",
            "text": "Learning should be fun and discovered by children.",
            "source_url": "https://operator.example", "title": "Operator",
            "retrieved_at": "2026-08-10", "content_hash": "o",
        }]}]}
        self.assertTrue(retrieve_operator_evidence(index, "A", "What is the operator's learning philosophy?"))

    def test_incremental_run_checkpoints_and_skips_completed_pages(self):
        records = [
            {
                "school_id": "A", "centre_code": "A100", "centre_name_x": "Bright Kids River",
                "centre_address": "10 River Road Singapore 123456", "postal_code": 123456,
                "centre_website": "https://school.example/river",
            },
            {"school_id": "B", "centre_name_x": "Operator B", "centre_website": "https://operator.example/about"},
            {"school_id": "C", "centre_name_x": "Operator C", "centre_website": "https://operator.example/about"},
        ]
        calls = []

        def fetch(url):
            calls.append(url)
            text = "Bright Kids River at 10 River Road Singapore 123456." if "school.example" in url else "Operator learning philosophy."
            return page(url, text)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            options = {
                "allowlist_path": root / "schools.json",
                "operator_allowlist_path": root / "operators.json",
                "output_path": root / "index.json",
                "limit": 1,
                "shared_limit": 1,
                "delay_seconds": 0,
                "fetcher": fetch,
            }
            first = run_incremental(records, **options)
            second = run_incremental(records, **options)
            self.assertEqual(first["school_attempts"], 1)
            self.assertEqual(first["operator_attempts"], 1)
            self.assertEqual(second["school_attempts"], 0)
            self.assertEqual(second["operator_attempts"], 0)
            self.assertEqual(calls, ["https://school.example/river", "https://operator.example/about"])
            self.assertEqual(len(second["index"]["pages"]), 1)
            self.assertEqual(len(second["index"]["operator_pages"]), 1)
            self.assertFalse((root / "index.json.tmp").exists())

    def test_targeted_reprocessing_preserves_other_checkpoints(self):
        records = [
            {"school_id": "A", "centre_code": "A100", "centre_name_x": "School A",
             "centre_address": "1 Alpha Road Singapore 111111", "postal_code": 111111,
             "centre_website": "https://a.example/centre"},
            {"school_id": "B", "centre_code": "B100", "centre_name_x": "School B",
             "centre_address": "2 Beta Road Singapore 222222", "postal_code": 222222,
             "centre_website": "https://b.example/centre"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            options = {"allowlist_path": root / "schools.json",
                       "operator_allowlist_path": root / "operators.json",
                       "output_path": root / "index.json", "delay_seconds": 0,
                       "shared_limit": 0}
            run_incremental(
                records,
                fetcher=lambda url: page(url, "School A 1 Alpha Road 111111" if "a.example" in url
                                         else "School B 2 Beta Road 222222"),
                **options,
            )
            result = run_incremental(
                records, school_ids={"A"},
                fetcher=lambda url: page(url, "School A 1 Alpha Road 111111 updated"),
                **options,
            )
            self.assertEqual(result["school_attempts"], 1)
            self.assertEqual({item["school_id"] for item in result["school_decisions"]}, {"A", "B"})
            self.assertEqual({item["school_id"] for item in result["index"]["pages"]}, {"A", "B"})

    def test_incremental_run_retries_fetch_failures(self):
        records = [{
            "school_id": "A", "centre_code": "A100", "centre_name_x": "Bright Kids River",
            "centre_address": "10 River Road Singapore 123456", "postal_code": 123456,
            "centre_website": "https://school.example/river",
        }]
        attempts = []

        def flaky(url):
            attempts.append(url)
            if len(attempts) == 1:
                raise FetchError("timeout", "temporary failure", retryable=True, retry_after_seconds=60)
            return page(url, "Bright Kids River at 10 River Road Singapore 123456.")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            options = {
                "allowlist_path": root / "schools.json",
                "operator_allowlist_path": root / "operators.json",
                "output_path": root / "index.json",
                "limit": 1,
                "shared_limit": 0,
                "delay_seconds": 0,
                "fetcher": flaky,
            }
            first = run_incremental(records, now=datetime(2026, 8, 10, 8, 0, tzinfo=timezone.utc), **options)
            deferred = run_incremental(records, now=datetime(2026, 8, 10, 8, 0, 30, tzinfo=timezone.utc), **options)
            second = run_incremental(records, now=datetime(2026, 8, 10, 8, 2, tzinfo=timezone.utc), **options)
            self.assertEqual(first["school_decisions"][0]["review_status"], "fetch_failed")
            self.assertEqual(first["school_decisions"][0]["failure_code"], "timeout")
            self.assertEqual(deferred["school_attempts"], 0)
            self.assertEqual(second["school_decisions"][0]["review_status"], "approved")
            self.assertEqual(len(second["index"]["pages"]), 1)
            self.assertEqual(len(attempts), 2)

    def test_incremental_run_does_not_retry_permanent_failure(self):
        records = [{
            "school_id": "A", "centre_name_x": "Bright Kids", "centre_website": "https://school.example/river",
        }]

        def disallowed(_url):
            raise FetchError("robots_disallowed", "site policy disallows fetching", retryable=False)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            options = {
                "allowlist_path": root / "schools.json", "operator_allowlist_path": root / "operators.json",
                "output_path": root / "index.json", "limit": 1, "shared_limit": 0,
                "delay_seconds": 0, "fetcher": disallowed,
            }
            first = run_incremental(records, now=datetime(2026, 8, 10, tzinfo=timezone.utc), **options)
            second = run_incremental(records, now=datetime(2027, 8, 10, tzinfo=timezone.utc), **options)
            decision = first["school_decisions"][0]
            self.assertEqual(decision["failure_code"], "robots_disallowed")
            self.assertFalse(decision["retryable"])
            self.assertIsNone(decision["next_retry_at"])
            self.assertEqual(second["school_attempts"], 0)

    def test_incremental_run_reprocesses_changed_url_and_removes_stale_page(self):
        record = {
            "school_id": "A", "centre_code": "A100", "centre_name_x": "Bright Kids River",
            "centre_address": "10 River Road Singapore 123456", "postal_code": 123456,
            "centre_website": "https://school.example/river",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            options = {
                "allowlist_path": root / "schools.json",
                "operator_allowlist_path": root / "operators.json",
                "output_path": root / "index.json",
                "limit": 1,
                "shared_limit": 0,
                "delay_seconds": 0,
            }
            first = run_incremental(
                [record],
                fetcher=lambda url: page(url, "Bright Kids River at 10 River Road Singapore 123456."),
                **options,
            )
            changed = {**record, "centre_website": "https://school.example/generic"}
            second = run_incremental(
                [changed], fetcher=lambda url: page(url, "A generic operator homepage."), **options
            )
            self.assertEqual(len(first["index"]["pages"]), 1)
            self.assertEqual(second["school_decisions"][0]["review_status"], "rejected")
            self.assertEqual(second["school_decisions"][0]["change_status"], "identity_changed")
            self.assertEqual(second["index"]["pages"], [])

    def test_automatic_identity_approves_strong_postal_address_and_name_match(self):
        record = {
            "school_id": "A", "centre_code": "PT1234", "centre_name_x": "Bright Kids @ River Road Pte Ltd",
            "centre_address": "10 River Road, #01-02, Singapore 123456", "postal_code": 123456,
            "centre_website": "https://school.example/river-road",
        }
        candidate_page = page(
            "https://school.example/river-road",
            "Bright Kids at River Road is located at 10 River Road #01-02 Singapore 123456.",
        )
        decision = verify_school_identity(record, candidate_page, record["centre_website"])
        self.assertEqual(decision["review_status"], "approved")
        self.assertEqual(decision["identity_confidence"], "high")
        self.assertEqual(decision["verification_method"], "automated_deterministic")

    def test_automatic_identity_does_not_approve_name_and_domain_alone(self):
        record = {
            "school_id": "A", "centre_code": "PT1234", "centre_name_x": "Bright Kids @ River Road",
            "centre_address": "10 River Road, Singapore 123456", "postal_code": 123456,
            "centre_website": "https://school.example/river-road",
        }
        candidate_page = page("https://school.example/river-road", "Bright Kids at River Road programmes.")
        decision = verify_school_identity(record, candidate_page, record["centre_website"])
        self.assertEqual(decision["review_status"], "pending_review")

    def test_automatic_identity_approves_name_address_and_domain_without_postal(self):
        record = {
            "school_id": "A", "centre_name_x": "The Schoolhouse Dover",
            "centre_address": "131 Dover Road, Singapore 139659", "postal_code": 139659,
            "centre_website": "theschoolhouse.com.sg/dover/",
        }
        candidate_page = page(
            "https://theschoolhouse.com.sg/dover/",
            "The Schoolhouse Dover is located at 131 Dover Road.",
        )
        decision = verify_school_identity(record, candidate_page, record["centre_website"])
        self.assertEqual(decision["review_status"], "approved")

    def test_automatic_identity_uses_unindexed_identity_text(self):
        record = {
            "school_id": "A", "centre_name_x": "Bright Kids River",
            "centre_address": "10 River Road Singapore 123456", "postal_code": 123456,
            "centre_website": "https://school.example/",
        }
        candidate_page = PageContent(
            requested_url=record["centre_website"], final_url=record["centre_website"],
            title="Bright Kids", text="Our learning programme.", retrieved_at="2026-08-10",
            content_hash="a" * 64,
            identity_text="Bright Kids River contact address 10 River Road Singapore 123456",
        )
        decision = verify_school_identity(record, candidate_page, record["centre_website"])
        self.assertEqual(decision["review_status"], "approved")

    def test_automatic_identity_reclassifies_generic_official_homepage_as_operator(self):
        record = {
            "school_id": "A", "centre_name_x": "Sunshine Kids Preschool @ Woodlands Pte Ltd",
            "centre_address": "795 Woodlands Drive 72 Singapore 730795", "postal_code": 730795,
            "centre_website": "sunshinekids.com.sg",
        }
        candidate_page = page(
            "https://sunshinekids.com.sg/",
            "Sunshine Kids is a quality preschool for holistic development.",
        )
        decision = verify_school_identity(record, candidate_page, record["centre_website"])
        self.assertEqual(decision["review_status"], "approved_operator")

    def test_automatic_identity_approves_exact_unqualified_school_brand_homepage(self):
        record = {
            "school_id": "A", "centre_name_x": "Orion Preschool",
            "centre_address": "1 River Road Singapore 123456", "postal_code": 123456,
            "centre_website": "https://orion.example/",
        }
        candidate_page = PageContent(
            requested_url=record["centre_website"], final_url=record["centre_website"],
            title="Orion Preschool", text="Orion Preschool learning programme.",
            retrieved_at="2026-08-10", content_hash="a" * 64,
        )
        decision = verify_school_identity(record, candidate_page, record["centre_website"])
        self.assertEqual(decision["review_status"], "approved")

    def test_automatic_identity_queues_official_acronym_brand_page_for_review(self):
        record = {
            "school_id": "A", "centre_name_x": "GUG Preschool @ Tampines Pte Ltd",
            "centre_address": "300 Tampines Avenue 5 Singapore 529653", "postal_code": 529653,
            "centre_website": "www.gugifted.com",
        }
        candidate_page = page(
            "https://www.gugifted.com/",
            "Growing Up Gifted is a preschool inspired by gifted education.",
        )
        candidate_page = PageContent(**{**candidate_page.__dict__,
            "title": "Growing Up Gifted | Preschool Inspired by Gifted Education"})
        decision = verify_school_identity(record, candidate_page, record["centre_website"])
        self.assertEqual(decision["review_status"], "pending_review")

    def test_automated_allowlist_records_fetch_failure(self):
        rows = [{
            "school_id": "A", "school_name": "School A", "scope": "school_specific_candidate",
            "selected_candidate_url": "https://school.example/centre-a",
        }]
        records = [{"school_id": "A", "centre_name_x": "School A"}]

        def fail(_url):
            raise PilotError("robots policy unavailable")

        decisions, fetched = automate_allowlist(rows, records, fetcher=fail, delay_seconds=0)
        self.assertEqual(decisions[0]["review_status"], "fetch_failed")
        self.assertEqual(fetched, {})

    def test_shared_url_is_fetched_once_and_linked_to_all_schools(self):
        rows = [
            {"school_id": "A", "scope": "shared_operator_page_candidate", "selected_candidate_url": "https://operator.example/about"},
            {"school_id": "B", "scope": "shared_operator_page_candidate", "selected_candidate_url": "https://operator.example/about"},
        ]
        calls = []

        def fetch(url):
            calls.append(url)
            return page(url, "Our operator provides play-based programmes.")

        decisions, fetched = automate_shared_pages(rows, fetcher=fetch, delay_seconds=0)
        self.assertEqual(calls, ["https://operator.example/about"])
        self.assertEqual(decisions[0]["review_status"], "approved_operator")
        self.assertEqual(decisions[0]["linked_school_ids"], ["A", "B"])
        self.assertIn("https://operator.example/about", fetched)

    def test_operator_evidence_is_separate_and_explicitly_labelled(self):
        url = "https://operator.example/about"
        decisions = [{
            "operator_id": "OPERATOR_PAGE:1", "operator_name": "operator.example", "url": url,
            "review_status": "approved_operator", "linked_school_ids": ["A", "B"],
        }]
        operator_pages, failures = ingest_operator_pages(
            decisions, fetcher=lambda value: page(value, "Bilingual play-based curriculum across our organisation.")
        )
        index = {"pages": [], "operator_pages": operator_pages}
        self.assertEqual(failures, [])
        self.assertEqual(retrieve(index, "A", "bilingual curriculum"), [])
        results = retrieve_operator_evidence(index, "A", "bilingual curriculum")
        self.assertTrue(results)
        self.assertEqual(results[0]["evidence_scope"], "operator")
        self.assertIsNone(results[0]["school_id"])
        self.assertIn("not verified", results[0]["claim_boundary"])
        self.assertEqual(retrieve_operator_evidence(index, "C", "bilingual"), [])

    def test_pending_entries_are_not_ingested(self):
        entry = approved()
        entry["review_status"] = "pending_review"
        called = []
        report = ingest_allowlist([entry], fetcher=lambda url: called.append(url), delay_seconds=0)
        self.assertEqual(report["pages"], [])
        self.assertEqual(called, [])

    def test_approval_requires_two_distinct_identity_matches(self):
        entry = approved()
        entry["identity_matches"] = entry["identity_matches"][:1]
        with self.assertRaisesRegex(PilotError, "two distinct"):
            validate_allowlist([entry])

    def test_non_https_allowlist_url_is_rejected(self):
        with self.assertRaisesRegex(PilotError, "HTTPS"):
            validate_allowlist([approved(url="http://school.example")])

    def test_extract_html_omits_navigation_scripts_and_footer(self):
        title, text = extract_html(
            "<title>Centre A</title><nav>Menu</nav><main>Play-based learning</main>"
            "<script>secret()</script><footer>Legal links</footer>"
        )
        self.assertEqual(title, "Centre A")
        self.assertEqual(text, "Play-based learning")

    def test_browser_fallback_is_not_used_for_ordinary_fetch_failures(self):
        with mock.patch("stage1.web_rag.fetch_page") as ordinary:
            ordinary.side_effect = FetchError("robots_disallowed", "blocked", retryable=False)
            with self.assertRaises(FetchError) as raised:
                fetch_page_with_browser_fallback("https://school.example")
        self.assertEqual(raised.exception.code, "robots_disallowed")

    def test_extract_html_prefers_main_and_filters_cookie_reviews_and_ui(self):
        main_words = " ".join(f"learning{i}" for i in range(45))
        title, text = extract_html(
            "<html><head><title>Centre A</title></head><body>"
            "<div class='top-menu'>Admissions Navigation</div>"
            f"<main><h1>Centre A programme</h1><p>{main_words}</p>"
            "<div class='cookie-consent'>Accept All Manage consent</div>"
            "<section class='parent-reviews'>A parent testimonial that should not be evidence.</section>"
            "<p>Read more</p><p>Centre A programme</p></main>"
            "<div>Unrelated content outside the main element.</div></body></html>"
        )
        self.assertEqual(title, "Centre A")
        self.assertIn("learning44", text)
        self.assertEqual(text.count("Centre A programme"), 1)
        self.assertNotIn("Admissions Navigation", text)
        self.assertNotIn("Accept All", text)
        self.assertNotIn("testimonial", text)
        self.assertNotIn("Read more", text)
        self.assertNotIn("Unrelated content", text)

    def test_extract_html_falls_back_when_semantic_main_is_too_small(self):
        _, text = extract_html(
            "<main><h1>Short heading</h1></main>"
            "<section><p>This useful legacy page has no meaningful semantic main wrapper.</p></section>"
        )
        self.assertIn("useful legacy page", text)

    def test_chunks_have_bounded_overlap(self):
        chunks = chunk_text("one two three four five six", max_words=4, overlap_words=1)
        self.assertEqual(chunks, ["one two three four", "four five six"])

    def test_ingestion_records_provenance_and_citations(self):
        report = ingest_allowlist(
            [approved()],
            fetcher=lambda url: page(url, "Outdoor play and bilingual learning every day."),
            delay_seconds=0,
        )
        self.assertEqual(report["purpose"], "explanation_only")
        chunk = report["pages"][0]["chunks"][0]
        self.assertEqual(chunk["school_id"], "A")
        self.assertEqual(len(chunk["content_hash"]), 64)
        result = retrieve(report, "A", "outdoor bilingual")
        self.assertEqual(result[0]["citation"]["url"], "https://school.example/centre-a")
        self.assertEqual(result[0]["citation"]["chunk_id"], chunk["chunk_id"])

    def test_retrieval_is_strictly_school_isolated(self):
        entries = [approved("A", "https://school.example/centre-a"), approved("B", "https://school.example/centre-b")]
        report = ingest_allowlist(
            entries,
            fetcher=lambda url: page(url, "Montessori garden" if "centre-a" in url else "Montessori robotics"),
            delay_seconds=0,
        )
        results = retrieve(report, "A", "Montessori robotics garden")
        self.assertTrue(results)
        self.assertTrue(all(item["school_id"] == "A" for item in results))
        self.assertNotIn("robotics", " ".join(item["text"] for item in results).lower())

    def test_unavailable_evidence_returns_empty_result(self):
        self.assertEqual(retrieve({"pages": []}, "A", "outdoor learning"), [])

    def test_school_id_is_mandatory(self):
        with self.assertRaisesRegex(PilotError, "school_id"):
            retrieve({"pages": []}, "", "outdoor learning")


if __name__ == "__main__":
    unittest.main()
