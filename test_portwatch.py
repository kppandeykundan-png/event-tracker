import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import portwatch as pw


def feat(ms, total, tanker):
    return {"attributes": {"date": ms, "portname": "X", "n_total": total, "n_tanker": tanker, "capacity": 5}}


class T(unittest.TestCase):
    def test_parse_sorts_dedupes_and_dates(self):
        day = 86400000
        rows = pw.parse([feat(day * 2, 30, 10), feat(day, 20, 5), feat(day, 22, 6)])
        self.assertEqual([r["date"] for r in rows], ["1970-01-02", "1970-01-03"])
        self.assertEqual(rows[1]["tanker"], 10)

    def test_summarize_change(self):
        rows = [{"date": f"d{i:03d}", "total": 100, "tanker": 40} for i in range(90)] + \
               [{"date": f"e{i:03d}", "total": 50, "tanker": 20} for i in range(7)]
        s = pw.summarize(rows)
        self.assertEqual((s["avg7_total"], s["change_pct"]), (50.0, -50))

    def test_short_history_has_no_baseline(self):
        rows = [{"date": f"d{i:02d}", "total": 10, "tanker": 4} for i in range(20)]
        self.assertIsNone(pw.summarize(rows)["change_pct"])

    def test_empty_and_missing_fields(self):
        self.assertIsNone(pw.summarize([]))
        self.assertEqual(pw.parse([{"attributes": {"portname": "X"}}]), [])


if __name__ == "__main__":
    unittest.main()


class TestIndex(unittest.TestCase):
    def rows(self, tail):
        return [{"date": f"2026-01-{i + 1:03d}", "total": 100, "tanker": 40} for i in range(90)] + \
               [{"date": f"2026-02-{i + 1:03d}", "total": tail, "tanker": 20} for i in range(7)]

    def test_stress_half_traffic_is_fifty(self):
        self.assertEqual(pw.stress(self.rows(50))[-1][1], 50.0)

    def test_above_usual_counts_zero(self):
        self.assertEqual(pw.stress(self.rows(150))[-1][1], 0.0)

    def test_band(self):
        self.assertEqual([pw.band(v) for v in (0, 15, 30, 80)], ["Calm", "Watchful", "Strained", "Severe"])

    def test_index_needs_three_routes(self):
        self.assertIsNone(pw.build_index({"A": self.rows(50), "B": self.rows(50)}))
        long = [{"date": f"d{i:03d}", "total": 100 if i < 100 else 50, "tanker": 0} for i in range(114)]
        idx = pw.build_index({k: long for k in "ABC"})
        self.assertTrue(40 <= idx["latest"] <= 55)
        self.assertEqual(len(idx["components"]), 3)
