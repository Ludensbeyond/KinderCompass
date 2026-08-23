import datetime as dt
import unittest

from stage2.engine import age_in_months, evaluate_preschool_eligibility, load_policy


def service(level, service_type="Full Day", citizenship="SC", fee=1000):
    return {
        "class_of_licence": "Class B (Child Care)",
        "levels_offered": level,
        "type_of_service": service_type,
        "type_of_citizenship": citizenship,
        "fees": fee,
        "last_updated": "2026-07-17",
    }


class Stage2PolicyTests(unittest.TestCase):
    def test_age_uses_completed_months(self):
        self.assertEqual(age_in_months(dt.date(2023, 6, 10), dt.date(2026, 6, 9)), 35)
        self.assertEqual(age_in_months(dt.date(2023, 6, 10), dt.date(2026, 6, 10)), 36)

    def test_selects_exact_programme_level_and_citizenship_fee(self):
        level = "Pre-Nursery (3 yrs old)"
        result = evaluate_preschool_eligibility(
            dob=dt.date(2023, 6, 10), admission_date=dt.date(2026, 6, 10), ghi=4500,
            care_levels=[level], services_menu=[
                service(level, fee=900), service(level, citizenship="SPR", fee=1100),
                service(level, service_type="Half Day AM", fee=500),
            ], citizenship="SC", programme_type="full_day", working_hours_per_month=56,
            household_size=4, non_earning_dependants=2,
        )
        self.assertEqual(result["fee_before_subsidy"], 900)
        self.assertEqual(result["basic_subsidy"], 300)
        self.assertEqual(result["additional_subsidy"], 440)
        self.assertEqual(result["net_monthly_fee"], 160)
        self.assertEqual(result["policy_source"]["policy_id"], "ecda-preschool-subsidies-2025-01-01")

    def test_exact_half_day_variant_does_not_use_cheaper_sibling_fee(self):
        level = "Pre-Nursery (3 yrs old)"
        menu = [
            service(level, service_type="Half Day AM", fee=420),
            service(level, service_type="Half Day PM", fee=510),
        ]
        result = evaluate_preschool_eligibility(
            dob=dt.date(2023, 6, 10), admission_date=dt.date(2026, 6, 10),
            ghi=4500, care_levels=[level], services_menu=menu,
            citizenship="SC", programme_type="half_day_pm",
            service_type="Half Day PM",
        )
        self.assertEqual(result["programme_id"], "half_day_pm")
        self.assertEqual(result["fee_before_subsidy"], 510)

    def test_56_hour_boundary_changes_basic_and_additional_subsidy(self):
        level = "Pre-Nursery (3 yrs old)"
        common = dict(dob=dt.date(2023, 6, 10), admission_date=dt.date(2026, 6, 10),
                      ghi=3000, care_levels=[level], services_menu=[service(level)],
                      citizenship="SC", programme_type="full_day")
        non_working = evaluate_preschool_eligibility(**common, working_hours_per_month=55)
        working = evaluate_preschool_eligibility(**common, working_hours_per_month=56)
        self.assertEqual((non_working["basic_subsidy"], non_working["additional_subsidy"]), (150, 0))
        self.assertEqual((working["basic_subsidy"], working["additional_subsidy"]), (300, 467))

    def test_income_boundary_moves_to_next_band(self):
        level = "Pre-Nursery (3 yrs old)"
        common = dict(dob=dt.date(2023, 6, 10), admission_date=dt.date(2026, 6, 10),
                      care_levels=[level], services_menu=[service(level)], citizenship="SC",
                      programme_type="full_day", working_hours_per_month=56)
        self.assertEqual(evaluate_preschool_eligibility(**common, ghi=3000)["additional_subsidy"], 467)
        self.assertEqual(evaluate_preschool_eligibility(**common, ghi=3000.01)["additional_subsidy"], 440)

    def test_qualifying_large_household_uses_per_capita_income(self):
        level = "Pre-Nursery (3 yrs old)"
        result = evaluate_preschool_eligibility(
            dob=dt.date(2023, 6, 10), admission_date=dt.date(2026, 6, 10), ghi=8000,
            care_levels=[level], services_menu=[service(level)], citizenship="SC",
            programme_type="full_day", working_hours_per_month=56,
            household_size=6, non_earning_dependants=3,
        )
        self.assertEqual(result["income_assessment_method"], "per_capita_income")
        self.assertEqual(result["additional_subsidy"], 340)

    def test_non_citizen_gets_fee_without_ecda_subsidy(self):
        level = "Pre-Nursery (3 yrs old)"
        result = evaluate_preschool_eligibility(
            dob=dt.date(2023, 6, 10), admission_date=dt.date(2026, 6, 10), ghi=3000,
            care_levels=[level], services_menu=[service(level, citizenship="SPR", fee=1100)],
            citizenship="SPR", programme_type="full_day",
        )
        self.assertEqual(result["net_monthly_fee"], 1100)
        self.assertEqual(result["scheme"], "none")

    def test_special_approval_is_referred_for_manual_review(self):
        level = "Pre-Nursery (3 yrs old)"
        result = evaluate_preschool_eligibility(
            dob=dt.date(2023, 6, 10), admission_date=dt.date(2026, 6, 10), ghi=3000,
            care_levels=[level], services_menu=[service(level)], special_approval=True,
        )
        self.assertEqual(result["status"], "manual_review")
        self.assertNotIn("additional_subsidy", result)

    def test_class_c_kindergarten_is_referred_to_kifas_review(self):
        level = "Kindergarten 1 (5 yrs old)"
        kindergarten = service(level, service_type="Full Day", fee=180)
        kindergarten["class_of_licence"] = "Class C (Kindergarten)"
        result = evaluate_preschool_eligibility(
            dob=dt.date(2021, 6, 10), admission_date=dt.date(2026, 6, 10), ghi=3000,
            care_levels=[level], services_menu=[kindergarten], programme_type="full_day",
        )
        self.assertEqual(result["status"], "manual_review")
        self.assertEqual(result["scheme"], "kifas")

    def test_flexi_care_2_uses_fee_but_does_not_invent_subsidy(self):
        level = "Pre-Nursery (3 yrs old)"
        result = evaluate_preschool_eligibility(
            dob=dt.date(2023, 6, 10), admission_date=dt.date(2026, 6, 10), ghi=3000,
            care_levels=[level], services_menu=[service(level, service_type="Flexi Care 2", fee=420)],
            citizenship="SC", programme_type="flexi_care_2", working_hours_per_month=56,
        )
        self.assertTrue(result["eligible"])
        self.assertEqual(result["status"], "manual_review")
        self.assertEqual(result["fee_before_subsidy"], 420)
        self.assertEqual(result["net_monthly_fee"], 420)
        self.assertNotIn("basic_subsidy", result)
        self.assertNotIn("additional_subsidy", result)

    def test_policy_resource_has_source_and_effective_date(self):
        policy = load_policy()
        self.assertEqual(policy["authority"], "Early Childhood Development Agency (ECDA)")
        self.assertEqual(policy["effective_from"], "2025-01-01")


if __name__ == "__main__":
    unittest.main()
