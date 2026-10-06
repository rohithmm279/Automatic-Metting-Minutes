"""Offline integrity checks for the archetype regression corpus."""

import json
from pathlib import Path
import unittest


FIXTURE = Path(__file__).parent / "fixtures" / "archetype_eval.json"


class TestArchetypeFixture(unittest.TestCase):
    def test_fixture_covers_five_representative_cases(self):
        cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(len(cases), 5)
        self.assertEqual(
            {case["archetype"] for case in cases},
            {"corporate_sync", "student_casual", "technical_design", "sales"},
        )

    def test_each_case_has_mutually_exclusive_ground_truth_categories(self):
        cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
        for case in cases:
            ground_truth = case["ground_truth"]
            self.assertTrue(case["transcript"].strip())
            self.assertIsInstance(ground_truth["action_items"], list)
            self.assertIsInstance(ground_truth["decisions"], list)
            self.assertIsInstance(ground_truth["unresolved_issues"], list)
            actions = {item["task"].lower() for item in ground_truth["action_items"]}
            decisions = {item.lower() for item in ground_truth["decisions"]}
            issues = {item.lower() for item in ground_truth["unresolved_issues"]}
            self.assertTrue(actions.isdisjoint(decisions))
            self.assertTrue(actions.isdisjoint(issues))
            self.assertTrue(decisions.isdisjoint(issues))


if __name__ == "__main__":
    unittest.main()
