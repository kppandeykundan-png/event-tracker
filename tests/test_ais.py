import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ais_collector as c
import ais_alerts as al

CLASSES = [{"name": "VLCC", "min_len": 300, "barrels_m": 2.0}, {"name": "Suezmax", "min_len": 260, "barrels_m": 1.0},
           {"name": "Aframax", "min_len": 225, "barrels_m": 0.7}, {"name": "MR/Handy", "min_len": 150, "barrels_m": 0.3}]
AREAS = {"Hormuz": {"box": [24.5, 55.5, 27.5, 57.5], "kind": "chokepoint"}}


def pos(mmsi, lat, lon):
    return {"MessageType": "PositionReport", "MetaData": {"MMSI": mmsi, "latitude": lat, "longitude": lon}, "Message": {}}


def static(mmsi, typ, a, b):
    return {"MessageType": "ShipStaticData", "MetaData": {"MMSI": mmsi},
            "Message": {"ShipStaticData": {"Type": typ, "Name": "X", "Dimension": {"A": a, "B": b}}}}


class T(unittest.TestCase):
    def test_valid_pos(self):
        for lat, lon in [(91, 0), (10, 181), (0, 0), (None, 5)]:
            self.assertFalse(c.valid_pos(lat, lon))
        self.assertTrue(c.valid_pos(26, 56))

    def test_area_edges(self):
        self.assertEqual(c.area_for(26, 56, AREAS), "Hormuz")
        self.assertEqual(c.area_for(24.5, 55.5, AREAS), "Hormuz")
        self.assertIsNone(c.area_for(10, 56, AREAS))

    def test_class(self):
        for ln, want in [(330, "VLCC"), (280, "Suezmax"), (245, "Aframax"), (180, "MR/Handy"), (100, "Unclassified"), (0, "Unclassified")]:
            self.assertEqual(c.tanker_class(ln, CLASSES), want)

    def test_ingest_dedupe_and_summary(self):
        cache, seen = {}, {"Hormuz": set()}
        for m in [pos(1, 26, 56), pos(1, 26, 56), static(1, 80, 200, 130), pos(2, 26.1, 56.1), static(2, 70, 60, 40),
                  pos(3, 10, 10), pos(4, 91, 56), pos(5, 26, 56)]:
            c.ingest(m, AREAS, cache, seen)
        self.assertEqual(seen["Hormuz"], {"1", "2", "5"})  # dup merged, outside + invalid dropped
        s = c.summarize(seen["Hormuz"], cache, CLASSES)
        self.assertEqual((s["vessels"], s["tankers"], s["classes"], s["capacity_mbbl"]), (3, 1, {"VLCC": 1}, 2.0))
        self.assertEqual(s["typed_pct"], 67)  # vessel 5 never sent static data

    def test_feed_error(self):
        self.assertEqual(c.ingest({"error": "bad key"}, AREAS, {}, {"Hormuz": set()}), 0)

    def _hist(self, today, typed=90, days=6, base=20):
        h = {f"2026-01-{i:02d}": {"tankers": base, "partial": False, "typed_pct": 90} for i in range(1, days + 1)}
        h["2026-01-10"] = {"tankers": today, "partial": False, "typed_pct": typed}
        return {"Hormuz": {"history": h}}

    def test_alerts(self):
        self.assertEqual(len(al.check(self._hist(5), "2026-01-10")), 1)
        self.assertEqual(len(al.check(self._hist(40), "2026-01-10")), 1)
        self.assertEqual(al.check(self._hist(19), "2026-01-10"), [])
        self.assertEqual(al.check(self._hist(5, typed=10), "2026-01-10"), [])  # low confidence
        self.assertEqual(al.check(self._hist(5, days=3), "2026-01-10"), [])    # not enough history


if __name__ == "__main__":
    unittest.main()
