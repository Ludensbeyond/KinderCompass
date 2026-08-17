import unittest
from pathlib import Path

from SystemCode.src.backend import main


class ApiStartupTests(unittest.TestCase):
    def test_backend_resolves_repository_paths_after_import(self) -> None:
        expected_root = Path(__file__).resolve().parents[4]
        self.assertEqual(main.REPO_ROOT, expected_root)
        self.assertTrue(main.POC_SRC.is_dir())
        self.assertEqual(main.health(), {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
