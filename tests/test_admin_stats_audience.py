"""The owner-specified historical baseline changes /stats only, not SQLite."""
import unittest

from handlers.admin import (
    LEGACY_USERS_SNAPSHOT,
    LEGACY_SALES_SNAPSHOT,
    with_historical_totals,
)


class AudienceStatsTests(unittest.TestCase):
    def test_baseline(self):
        self.assertEqual(LEGACY_USERS_SNAPSHOT, 95)
        self.assertEqual(LEGACY_SALES_SNAPSHOT, 1)

    def test_original_stats_numbers(self):
        original = {"total": 3, "purchased": 1, "rev_total": 1990, "opened_guide": 2}
        result = with_historical_totals(original)
        self.assertEqual(result["total"], 98)
        self.assertEqual(result["purchased"], 2)
        self.assertEqual(result["rev_total"], 1990)
        self.assertEqual(result["opened_guide"], 2)
        self.assertEqual(original["total"], 3)
        self.assertEqual(original["purchased"], 1)

    def test_counts_continue_increasing(self):
        result = with_historical_totals({"total": 4, "purchased": 2})
        self.assertEqual(result["total"], 99)
        self.assertEqual(result["purchased"], 3)


if __name__ == "__main__":
    unittest.main()
