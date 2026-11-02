"""Historical bot audience is shown without inflating live user counts."""
import unittest

from handlers.admin import LEGACY_USERS_SNAPSHOT, format_audience_counts


class AudienceStatsTests(unittest.TestCase):
    def test_historical_snapshot_is_95(self):
        self.assertEqual(LEGACY_USERS_SNAPSHOT, 95)

    def test_two_independent_counts(self):
        output = format_audience_counts(3)
        self.assertIn("В базе Timeweb: <b>3</b>", output)
        self.assertIn("До переезда (срез 02.11): <b>95</b>", output)
        self.assertIn("точное общее число неизвестно", output)
        self.assertNotIn("<b>98</b>", output)

    def test_dynamic_timeweb_count(self):
        output = format_audience_counts(127)
        self.assertIn("В базе Timeweb: <b>127</b>", output)
        self.assertIn("До переезда (срез 02.11): <b>95</b>", output)


if __name__ == "__main__":
    unittest.main()
