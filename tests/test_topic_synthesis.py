import csv
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "skills", "channel-to-brain", "scripts"))
import topic_synthesis as ts  # noqa: E402


class TopicSynthesisTest(unittest.TestCase):
    def test_groups_claims_unchanged_with_ids_and_tags(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "videos"))
            lines = ["# Title", "", "- ~00:10 Step 1: build a content calendar for the month before posting anything. [SEARCH-CHECK PARTLY, unit V1]",
                     "- ~00:20 Filler line about the weather and many other unrelated things going on here.",
                     "- ~00:30 Decision rule: use a content calendar only when you post weekly or more often than that."]
            open(os.path.join(d, "videos", "abc.md"), "w", encoding="utf-8").write("\n".join(lines))
            with open(os.path.join(d, "supporting_claims.csv"), "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                w.writerow(["video_id", "window", "type", "group", "claim", "source_file", "line", "verification", "verification_unit"])
                w.writerow(["abc", "w", "method_step", "g", "x", "videos/abc.md", 3, "", ""])
                w.writerow(["abc", "w", "filler", "filler", "x", "videos/abc.md", 4, "", ""])
                w.writerow(["abc", "w", "decision_rule", "g", "x", "videos/abc.md", 5, "", ""])
            stats = ts.build(d, {"Marketing": {"Content planning": ["content calendar"]}})
            self.assertEqual(stats[("Marketing", "Content planning")], 2)
            text = open(os.path.join(d, "synthesis", "MARKETING.md"), encoding="utf-8").read()
            self.assertIn("(abc)", text)
            self.assertIn("[SEARCH-CHECK PARTLY, unit V1]", text)
            self.assertNotIn("weather", text)
            self.assertLess(text.index("Method steps"), text.index("Decision rules"))
            self.assertTrue(os.path.exists(os.path.join(d, "synthesis", "INDEX.md")))


if __name__ == "__main__":
    unittest.main()
