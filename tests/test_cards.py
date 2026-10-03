import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    import make_cards as mc
except ImportError:
    mc = None


@unittest.skipUnless(mc, "Pillow not installed")
class T(unittest.TestCase):
    def test_card_is_written_at_instagram_size(self):
        from PIL import Image
        s = [{"date": f"2026-0{1 + i // 28}-{1 + i % 28:02d}", "total": 10 + i % 7} for i in range(60)]
        p = os.path.join(tempfile.mkdtemp(), "c.png")
        mc.card(p, "Brand", "Strait of Hormuz traffic is 64% below usual", "3.1", "ships a day",
                "A short note.", s, "total", 9, [{"date": s[10]["date"], "label": "Event"}], "Source line.")
        self.assertEqual(Image.open(p).size, (1080, 1350))


if __name__ == "__main__":
    unittest.main()
