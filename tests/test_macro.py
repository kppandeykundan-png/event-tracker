import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import macro as m, writer as w


class T(unittest.TestCase):
    def test_parse_fx_and_change(self):
        s = m.parse_fx({"rates": {"2026-09-01": {"INR": 88.0}, "2026-09-30": {"INR": 90.2}, "2026-10-01": {"INR": 90.4}}})
        self.assertEqual([x["date"] for x in s], ["2026-09-01", "2026-09-30", "2026-10-01"])
        p = m.pack(s)
        self.assertEqual(p["latest"], 90.4)
        self.assertAlmostEqual(p["change_30d_pct"], 2.73, places=1)
        self.assertAlmostEqual(p["change_1d_pct"], 0.22, places=1)

    def test_parse_eia_skips_bad_values(self):
        r = {"response": {"data": [{"period": "2026-09-28", "series": "RBRTE", "value": "101.5"},
                                   {"period": "2026-09-27", "series": "RBRTE", "value": None},
                                   {"period": "2026-09-28", "series": "RWTC", "value": "97"}]}}
        s = m.parse_eia(r)
        self.assertEqual(s["RBRTE"], [{"date": "2026-09-28", "value": 101.5}])
        self.assertEqual(s["RWTC"][0]["value"], 97.0)

    def test_pack_empty(self):
        self.assertIsNone(m.pack([]))

    def test_meeting_lines_picks_next(self):
        meets = [{"body": "RBI", "name": "MPC", "start": "2026-10-05", "end": "2026-10-07", "decision": "2026-10-07"},
                 {"body": "RBI", "name": "MPC", "start": "2026-08-03", "end": "2026-08-05", "decision": "2026-08-05"}]
        out = w.meeting_lines(meets, today="2026-10-03")
        self.assertIn("4 days away", out)
        self.assertNotIn("2026-08", out)

    def test_flow_lines(self):
        fl = {"daily": [{"date": "2026-10-01", "fii_net": -100, "dii_net": 250}, {"date": "2026-10-02", "fii_net": -50, "dii_net": 50}]}
        self.assertIn("FII Rs -150 cr, DII Rs 300 cr", w.flow_lines(fl))
        self.assertEqual(w.flow_lines({}), "")

    def test_fx_line(self):
        self.assertIn("weaker rupee", w.fx_line({"fx": {"latest": 90.4, "date": "2026-10-01", "change_1d_pct": 0.2, "change_30d_pct": 2.7}}))
        self.assertEqual(w.fx_line({}), "")


if __name__ == "__main__":
    unittest.main()
