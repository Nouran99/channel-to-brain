"""Tests for scripts/principle_layer.py with a fictional package and a mock model. Offline, no key, no network."""
import json, os, shutil, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "channel-to-brain", "scripts")
sys.path.insert(0, SCRIPTS)
import principle_layer as pl  # noqa: E402
import graph_check  # noqa: E402

NOTE = """# Demo video {n}

## Spoken
### Window 00:00-10:00
- ~01:05 Validate demand before you build anything, because building first wastes months. [details unreliable: Tool 99.9]
- Set the cache size to 512 in the settings page of the hosting panel.
- Hello and welcome to the channel everyone.
**On screen**
- A slide with a price table
## Notes
"""


class FakeModel:
    def __init__(self):
        self.calls = []
        self.spent = 0.0

    def __call__(self, prompt):
        self.calls.append(prompt)
        if prompt.startswith("You get numbered claims"):
            return "1|principle|validate demand first\n2|detail|cache setting\n3|filler|greeting"
        if prompt.startswith("Below are claims from"):
            return "G1|Validate Demand Before Building|Check demand first.|Not tool steps.\nG2|None of these|Tool specific."
        if prompt.startswith("Assign each numbered claim"):
            return "\n".join("%s|G1" % l.split("|")[0] for l in prompt.split("Claims (id|type|claim):\n")[1].split("\n") if l)
        return "Check demand first. The reasoning is that building first wastes time. Apply it before any build. The creator says so."


class PrincipleLayer(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.pkg = os.path.join(self.d, "pkg")
        os.makedirs(os.path.join(self.pkg, "videos"))
        for n in ("aaa", "bbb"):
            open(os.path.join(self.pkg, "videos", n + ".md"), "w", encoding="utf-8").write(NOTE.format(n=n))
        self.work = os.path.join(self.d, "work")

    def tearDown(self):
        shutil.rmtree(self.d)

    def typed(self):
        v = pl.parse_claims(self.pkg)
        m = FakeModel()
        pl.run_type(m, v, os.path.join(self.work, "out"))
        rows, miss = pl.parse_typed(v, os.path.join(self.work, "out"))
        return v, m, rows, miss

    def test_parse_claims_skips_on_screen_and_tags(self):
        v = pl.parse_claims(self.pkg)
        self.assertEqual([len(x["claims"]) for x in v], [3, 3])
        self.assertTrue(v[0]["claims"][0]["text"].startswith("Validate demand"))
        self.assertNotIn("details unreliable", v[0]["claims"][0]["text"])

    def test_type_is_resumable_and_parse_counts(self):
        v, m, rows, miss = self.typed()
        self.assertEqual(miss, 0)
        self.assertEqual(len(m.calls), 2)
        m2 = FakeModel()
        pl.run_type(m2, v, os.path.join(self.work, "out"))
        self.assertEqual(m2.calls, [])  # saved successes are not run again

    def test_unlabeled_is_reported(self):
        v, m, rows, miss = self.typed()
        for f in os.listdir(os.path.join(self.work, "out")):
            p = os.path.join(self.work, "out", f)
            d = json.load(open(p))
            d["text"] = d["text"].split("\n")[0]
            json.dump(d, open(p, "w"))
        rows, miss = pl.parse_typed(v, os.path.join(self.work, "out"))
        self.assertEqual(miss, 4)

    def test_groups_merge_pages_graph_check(self):
        v, m, rows, miss = self.typed()
        d = pl.run_groups(FakeModel(), rows, 1, "demo", 3, 700)
        self.assertEqual(d["none"], "G2")
        self.assertEqual({r["group"] for r in d["claims"] if r["type"] == "principle"}, {"G1"})
        self.assertEqual({r["group"] for r in d["claims"] if r["type"] == "detail"}, {"detail"})  # never grouped
        d = pl.apply_merge(d, {"rename": {"G1": "Validate Demand First"}})
        self.assertEqual(d["groups"]["G1"][0], "Validate Demand First")
        pl.run_overview(FakeModel(), d, "demo")
        self.assertIn("the material", d["groups"]["G1"][2].lower())
        self.assertNotIn("creator", d["groups"]["G1"][2].lower())
        res = pl.build_pages(self.pkg, d, "6 of 6 fit")
        self.assertEqual(res["groups"], 1)
        idx = open(os.path.join(self.pkg, "principles", "INDEX.md"), encoding="utf-8").read()
        self.assertIn("UNVERIFIED", idx)
        page = open(os.path.join(self.pkg, "principles", "G1-validate-demand-first.md"), encoding="utf-8").read()
        self.assertIn("[details unreliable: Tool 99.9]", page)
        self.assertIn("(video aaa, window 00:00-10:00, line L5 of videos/aaa.md)", page)
        csvt = open(os.path.join(self.pkg, "supporting_claims.csv"), encoding="utf-8").read()
        self.assertIn("video_id,window,type,group,claim", csvt)
        self.assertIn(",detail,", csvt)
        g, man = pl.build_graph(d, "limits", self.pkg)
        r = graph_check.check(g, man)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["counts"]["principles_per_video"], {"v:aaa": 1, "v:bbb": 1})
        c = pl.check(pl.parse_claims(self.pkg), d)
        self.assertTrue(c["ok"], c)

    def test_merge_drop_and_renumber(self):
        d = {"groups": {"G1": ["a", "x"], "G2": ["b", "y"], "G3": ["c", "z"], "G4": ["None of these", "n"]},
             "claims": [{"group": "G1"}, {"group": "G2"}, {"group": "G3"}, {"group": "G4"}], "none": "G4"}
        o = pl.apply_merge(d, {"drop": ["G1"], "merge": {"G2": {"from": ["G2", "G3"], "title": "bc", "statement": "s"}}})
        self.assertEqual(sorted(o["groups"]), ["G1", "G2"])
        self.assertEqual(o["none"], "G2")
        self.assertEqual([r["group"] for r in o["claims"]], ["G2", "G1", "G1", "G2"])

    def test_model_needs_config_and_stops_at_cap(self):
        cfg = os.path.join(self.d, "m.json")
        json.dump({"endpoint": "https://example.invalid/{model}", "model": "m"}, open(cfg, "w"))
        with self.assertRaises(SystemExit):
            pl.Model(cfg)
        json.dump({"endpoint": "https://example.invalid/{model}", "model": "m", "key_env_name": "CTB_TEST_KEY_NOT_SET",
                   "price_in_per_m": 0, "price_out_per_m": 0, "hard_cap_usd": 0}, open(cfg, "w"))
        os.environ.pop("CTB_TEST_KEY_NOT_SET", None)
        with self.assertRaises(SystemExit):
            pl.Model(cfg)
        os.environ["CTB_TEST_KEY_NOT_SET"] = "x"
        try:
            m = pl.Model(cfg)
            with self.assertRaises(SystemExit) as c:
                m("hi")  # cap 0: stops before any network call
            self.assertEqual(c.exception.code, 3)
        finally:
            del os.environ["CTB_TEST_KEY_NOT_SET"]

    def test_example_config_is_refused_until_filled(self):
        os.environ["CTB_TEST_KEY2"] = "x"
        try:
            ex = os.path.join(ROOT, "skills", "channel-to-brain", "references", "model-config.example.json")
            with self.assertRaises(SystemExit):
                pl.Model(ex)  # placeholders are refused
            c = json.load(open(ex))
            c.update({"endpoint": "https://example.invalid/{model}", "model": "m", "key_env_name": "CTB_TEST_KEY2"})
            cfg = os.path.join(self.d, "ok.json")
            json.dump(c, open(cfg, "w"))
            m = pl.Model(cfg)
            with self.assertRaises(SystemExit) as e:
                m("hi")  # cap is 0 in the example, so it stops before any call
            self.assertEqual(e.exception.code, 3)
            c["endpoint"] = "http://example.invalid/{model}"
            json.dump(c, open(cfg, "w"))
            with self.assertRaises(SystemExit):
                pl.Model(cfg)
        finally:
            del os.environ["CTB_TEST_KEY2"]

    def test_script_has_no_default_model_or_key(self):
        src = open(os.path.join(SCRIPTS, "principle_layer.py"), encoding="utf-8").read().lower()
        for bad in ("gemini", "api_key=", "googleapis"):
            self.assertNotIn(bad, src)


if __name__ == "__main__":
    unittest.main()
