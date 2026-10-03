import json, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import crux

LONG = "The Committee decided to maintain the target range for the federal funds rate at 3-1/2 to 3-3/4 percent today. " * 12
PAGE = f"<html><nav><a>Home page link</a><ul><li>About the Federal Reserve system and its many menu entries here</li></ul></nav><body><p>{LONG}</p><p>short</p><p>Inflation projection is 2.4% for the year.</p><footer>{LONG}</footer></body></html>"
GOOD = {"headline": "Fed keeps rates unchanged", "decision": "Held the range at 3-1/2 to 3-3/4 percent.",
        "summary": "The Fed left rates as they were. It cited steady conditions.", "points": ["Rates held", "No change in tone"],
        "watch": ["Incoming data"], "tone": "steady", "numbers": [{"label": "Range", "value": "3-1/2 to 3-3/4 percent"}, {"label": "Fake", "value": "9.99%"}]}


class T(unittest.TestCase):
    def test_html_to_text_drops_menus_and_short_bits(self):
        t = crux.html_to_text(PAGE)
        self.assertIn("maintain the target range", t)
        self.assertIn("Inflation projection is 2.4%", t)
        self.assertNotIn("menu entries", t)
        self.assertNotIn("short\n", t + "\n")
        self.assertEqual(t.count("maintain the target range"), 12)  # footer excluded

    def test_discover_fed(self):
        h = '<a href="/newsevents/pressreleases/monetary20260916a.htm">x</a><a href="https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916b.htm">p</a><a href="/newsevents/pressreleases/monetary20260729a.htm">y</a>'
        r = {c["date"]: c for c in crux.discover_fed(h, "")}
        self.assertEqual(sorted(r), ["2026-07-29", "2026-09-16"])
        self.assertTrue(r["2026-09-16"]["urls"][0][1].startswith("https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a"))

    def test_discover_rbi(self):
        h = '<a href="/Scripts/BS_PressReleaseDisplay.aspx?prid=63288">Governor&#8217;s Statement: August 5, 2026</a><a href="/Scripts/BS_PressReleaseDisplay.aspx?prid=62864">Governor’s Statement: June 05, 2026</a><a href="x?prid=1">Full Document</a>'
        r = {c["date"]: c for c in crux.discover_rbi(h)}
        self.assertEqual(sorted(r), ["2026-06-05", "2026-08-05"])
        self.assertTrue(r["2026-08-05"]["resolution"].endswith("prid=63287"))

    def test_parse_json_handles_fences(self):
        self.assertEqual(crux.parse_json('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertIsNone(crux.parse_json("no json here"))

    def test_validate_filters_numbers_and_advice(self):
        v = crux.validate(dict(GOOD), LONG)
        self.assertEqual([n["label"] for n in v["numbers"]], ["Range"])      # fabricated 9.99% dropped
        bad = dict(GOOD, summary="You should buy banks now.")
        self.assertIsNone(crux.validate(bad, LONG))
        self.assertIsNone(crux.validate({"headline": "x"}, LONG))
        self.assertEqual(crux.validate(dict(GOOD, tone="hawkish"), LONG)["tone"], "unclear")

    def test_main_end_to_end_with_stubs(self):
        import tempfile
        d = tempfile.mkdtemp(); old = os.getcwd(); os.chdir(d)
        try:
            os.environ["ANTHROPIC_API_KEY"] = "test"
            today = crux.datetime.now(crux.timezone.utc).strftime("%Y%m%d")
            fed_page = f'<a href="/newsevents/pressreleases/monetary{today}a.htm">s</a>'
            crux.fetch = lambda url, tries=3: fed_page if "press-fomc" in url else ("<html></html>" if "Annualpolicy" in url else PAGE)
            crux.ask_claude = lambda text, label, bank: "```json\n" + json.dumps(GOOD) + "\n```"
            crux.main()
            out = json.load(open("data/crux.json"))
            self.assertEqual(len(out["items"]), 1)
            self.assertEqual(out["items"][0]["bank"], "FED")
            crux.main()                                                      # second run: nothing new, no duplicate
            self.assertEqual(len(json.load(open("data/crux.json"))["items"]), 1)
        finally:
            os.chdir(old)


if __name__ == "__main__":
    unittest.main()
