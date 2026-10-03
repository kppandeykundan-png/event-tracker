import os, sys, unittest
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import writer as w, build_research as br


class T(unittest.TestCase):
    def test_pick_filters_impact_and_age(self):
        now = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
        ev = {"threads": [{"impact": 5, "updated": "2026-10-05T10:00:00+00:00"},
                          {"impact": 2, "updated": "2026-10-05T10:00:00+00:00"},
                          {"impact": 5, "updated": "2026-10-01T10:00:00+00:00"},
                          {"updated": "2026-10-05T11:00:00+00:00"}]}
        self.assertEqual(len(w.pick(ev, now=now)), 1)

    def test_parse_article(self):
        good = "Oil steadies\n\n" + "word " * 60
        self.assertEqual(w.parse_article(good)[0], "Oil steadies")
        self.assertIsNone(w.parse_article("Too short\n\nx"))

    def test_front_matter(self):
        meta, body = br.parse("---\ntitle: A\ntickers: NSE:X, NSE:Y\n---\n\nHello")
        self.assertEqual((meta["title"], body.strip()), ("A", "Hello"))
        self.assertEqual(br.parse("no front matter")[0], {})


if __name__ == "__main__":
    unittest.main()
