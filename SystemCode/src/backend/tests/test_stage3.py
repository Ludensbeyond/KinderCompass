import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from stage3.optimizer import calculate_home_to_preschool, haversine_km
from stage3.runner import run_from_file


class Stage3Tests(unittest.TestCase):
    def test_haversine_is_zero_for_same_point(self):
        point = {"latitude": 1.3, "longitude": 103.8}
        self.assertEqual(haversine_km(point, point), 0.0)

    def test_calculates_exactly_home_then_one_preschool(self):
        home = {"type": "home", "name": "Home", "latitude": 1.30, "longitude": 103.80}
        school = {"type": "preschool", "name": "A", "centre_code": "A", "latitude": 1.31, "longitude": 103.81}
        result = calculate_home_to_preschool(home, school)
        self.assertEqual([stop["type"] for stop in result["schedule"]], ["home", "preschool"])
        self.assertNotIn("optimizer", result)
        self.assertGreater(result["total_distance_km"], 0)

    @patch("stage3.runner.geocode_postal_code", return_value={"latitude": 1.30, "longitude": 103.80})
    def test_file_pipeline_joins_selected_school_to_geojson(self, geocode):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage2 = root / "stage2.json"
            locations = root / "locations.geojson"
            output = root / "stage3.json"
            stage2.write_text(json.dumps([{"school_id": "CENTRE:PT1", "centre_code": "PT1", "name": "School", "eligible": True}]), encoding="utf-8")
            locations.write_text(json.dumps({"features": [{"properties": {"Description": "<th>CENTRE_CODE</th><td>PT1</td>"}, "geometry": {"coordinates": [103.81, 1.31]}}]}), encoding="utf-8")
            result = run_from_file(
                stage2,
                selected_code="CENTRE:PT1",
                home_postal_code="540231",
                locations_path=locations,
                output_path=output,
            )
            self.assertTrue(output.exists())
            geocode.assert_called_once_with("540231")
            self.assertEqual(result["schedule"][1]["centre_code"], "PT1")


if __name__ == "__main__":
    unittest.main()
