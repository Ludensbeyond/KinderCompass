import datetime as dt
import unittest
from unittest.mock import patch

from SystemCode.src.backend.domain.catalogue import EvaluatedSchool, SchoolRecord
from SystemCode.src.backend.domain.models import EvaluationResponse, FamilyDetails
from SystemCode.src.backend.services.evaluation_service import EvaluationService
from stage1.scorer import rank_schools


class InMemorySchoolRepository:
    def __init__(self, records):
        self.records = {record.school_id: record for record in records}

    def get_many(self, school_ids):
        return [self.records[school_id] for school_id in school_ids]


def _school(school_id, *, spark, transport):
    return SchoolRecord.model_validate({
        "school_id": school_id,
        "name": school_id,
        "spark_certified": spark,
        "provision_of_transport": transport,
    })


class Stage2RankingContractTests(unittest.TestCase):
    def test_stage2_rechecks_all_hard_constraints_before_preference_scoring(self):
        records = [
            SchoolRecord.model_validate({
                "school_id": "PASS", "name": "Pass",
                "care_levels": ["Nursery"], "second_languages_offered": "Chinese|Malay",
            }),
            SchoolRecord.model_validate({
                "school_id": "WRONG_LEVEL", "name": "Wrong level",
                "care_levels": ["Kindergarten 1"], "second_languages_offered": "Chinese",
            }),
            SchoolRecord.model_validate({
                "school_id": "WRONG_LANGUAGE", "name": "Wrong language",
                "care_levels": ["Nursery"], "second_languages_offered": "Malay",
            }),
            SchoolRecord.model_validate({"school_id": "UNKNOWN", "name": "Unknown"}),
        ]
        service = EvaluationService(InMemorySchoolRepository(records))
        profile = {"hard_constraints": {"level": "Nursery", "language": "Chinese"}, "preferences": {}}
        family = FamilyDetails(
            dob=dt.date(2022, 1, 1), admission_date=dt.date(2026, 1, 1),
            gross_household_income=4500,
        )
        with patch.object(service, "_evaluate_school", side_effect=lambda school, _family:
                          EvaluatedSchool.model_validate({
                              **school.model_dump(), "status": "estimated", "eligible": True,
                              "preferred_programme": "full_day", "preferred_programme_available": True,
                          })):
            result = service.evaluate([record.school_id for record in records], profile, family)
        self.assertEqual([item.school_id for item in result], ["PASS"])

    def test_stage2_returns_final_score_fields_in_rank_order_and_filters_ineligible(self):
        records = [
            _school("HIGH_MATCH_LOW_EVIDENCE", spark="Yes", transport=None),
            _school("LOWER_MATCH_COMPLETE", spark="No", transport="Yes"),
            _school("ZZZ_INELIGIBLE", spark="No", transport="Yes"),
        ]
        profile = {
            "preferences": {
                "spark_certified": {"value": True, "weight": 4, "desired": True},
                "transport": {"value": True, "weight": 3, "desired": True},
            },
            "preference_items": [
                {"attribute": "spark_certified", "value": True, "importance": "nice_to_have"},
                {"attribute": "transport", "value": True, "importance": "high_priority"},
            ],
        }
        family = FamilyDetails(
            dob=dt.date(2022, 1, 1), admission_date=dt.date(2026, 1, 1),
            gross_household_income=4500, citizenship="SC", programme_type="full_day",
        )
        service = EvaluationService(InMemorySchoolRepository(records))

        def evaluate_for_test(school, _family):
            return EvaluatedSchool.model_validate({
                **school.model_dump(),
                "status": "estimated",
                "eligible": school.school_id != "ZZZ_INELIGIBLE",
                "eligible_level": "Nursery (4 yrs old)",
                "preferred_programme": "full_day",
                "preferred_programme_available": True,
            })

        with patch.object(service, "_evaluate_school", side_effect=evaluate_for_test):
            all_results = service.evaluate(
                [record.school_id for record in records], profile, family,
                include_ineligible=True,
            )
            eligible_results = service.evaluate(
                [record.school_id for record in records], profile, family,
            )

        expected_order = [
            item["school_id"]
            for item in rank_schools(profile, records, limit=len(records))
        ]
        self.assertEqual([item.school_id for item in all_results], expected_order)
        self.assertEqual(all_results[0].school_id, "LOWER_MATCH_COMPLETE")
        by_id = {item.school_id: item for item in all_results}
        self.assertGreater(
            by_id["HIGH_MATCH_LOW_EVIDENCE"].match_score,
            by_id["LOWER_MATCH_COMPLETE"].match_score,
        )
        self.assertGreater(
            by_id["LOWER_MATCH_COMPLETE"].combined_score,
            by_id["HIGH_MATCH_LOW_EVIDENCE"].combined_score,
        )
        expected_combined = {
            "LOWER_MATCH_COMPLETE": (69.23076923076923 * 100) ** 0.5,
            "HIGH_MATCH_LOW_EVIDENCE": (100 * (2 / 6.5 * 100)) ** 0.5,
            "ZZZ_INELIGIBLE": (69.23076923076923 * 100) ** 0.5,
        }
        for item in all_results:
            self.assertAlmostEqual(
                item.combined_score,
                round(expected_combined[item.school_id], 1),
            )

        self.assertEqual(
            [item.school_id for item in eligible_results],
            [school_id for school_id in expected_order if school_id != "ZZZ_INELIGIBLE"],
        )
        response = EvaluationResponse(
            eligible_count=len(eligible_results), centres=eligible_results, trace={},
        ).model_dump()
        self.assertEqual(
            [item["school_id"] for item in response["centres"]],
            [item.school_id for item in eligible_results],
        )
        self.assertTrue(all("combined_score" in item for item in response["centres"]))


if __name__ == "__main__":
    unittest.main()
