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

    def test_stress_and_index(self):
        mk = lambda a, b: [{"date": f"2026-01-{i:03d}", "total": a if i < 97 else b, "tanker": 0} for i in range(104)]
        self.assertEqual(pw.stress(mk(100, 50))[-1][1], 50.0)      # halved traffic -> 50
        self.assertEqual(pw.stress(mk(100, 150))[-1][1], 0.0)      # above usual never goes negative
        idx = pw.build_index({"A": mk(100, 50), "B": mk(100, 50), "C": mk(100, 100)})
        self.assertEqual(idx["latest"], 33)
        self.assertEqual(idx["band"], "Strained")
        self.assertIsNone(pw.build_index({"A": mk(100, 50), "B": mk(100, 50)}))  # needs 3 routes
        self.assertEqual(pw.band(9.9), "Calm")


if __name__ == "__main__":
    unittest.main()
