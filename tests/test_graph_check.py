"""Tests for scripts/graph_check.py on a fictional fixture. Offline, no Graphify needed."""
import copy, json, os, subprocess, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "channel-to-brain", "scripts")
sys.path.insert(0, SCRIPTS)
import graph_check  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixture")


def load(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return json.load(f)


class GraphCheck(unittest.TestCase):
    def test_fixture_passes(self):
        r = graph_check.check(load("graph_extraction.json"), load("graph_manifest.json"))
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["counts"]["nodes"], 4)

    def test_dangling_edge(self):
        d = load("graph_extraction.json")
        d["edges"].append({"source": "k_a_1", "target": "nope", "relation": "mentions", "confidence": "EXTRACTED"})
        r = graph_check.check(d)
        self.assertFalse(r["ok"])
        self.assertTrue(any("dangling" in p for p in r["problems"]))

    def test_video_without_claim(self):
        d = load("graph_extraction.json")
        d["nodes"].append({"id": "v_lonely", "kind": "video", "label": "x", "source_file": "videos/lonely.md"})
        r = graph_check.check(d)
        self.assertTrue(any("no linked claim" in p for p in r["problems"]))

    def test_claim_needs_anchor(self):
        d = load("graph_extraction.json")
        del d["nodes"][1]["source_location"]
        self.assertTrue(any("source_location" in p for p in graph_check.check(d)["problems"]))

    def test_bad_confidence_and_duplicate_id(self):
        d = load("graph_extraction.json")
        d["edges"][0]["confidence"] = "SURE"
        d["nodes"].append(copy.deepcopy(d["nodes"][2]))
        p = graph_check.check(d)["problems"]
        self.assertTrue(any("bad confidence" in x for x in p))
        self.assertTrue(any("duplicate node id" in x for x in p))

    def test_missing_coverage_node_and_manifest_label(self):
        d = load("graph_extraction.json")
        d["nodes"] = [n for n in d["nodes"] if n["kind"] != "coverage"]
        self.assertTrue(any("coverage node" in p for p in graph_check.check(d)["problems"]))
        r = graph_check.check(load("graph_extraction.json"), {})
        self.assertTrue(any("manifest" in p for p in r["problems"]))

    def test_malformed_input_is_controlled(self):
        for bad in ([], "x", None, 5, {"nodes": 1, "edges": []}, {"nodes": [], "edges": "x"}, {"nodes": [], "links": None}):
            r = graph_check.check(bad)
            self.assertFalse(r["ok"], bad)
        d = load("graph_extraction.json")
        d["edges"].append({"source": ["a"], "target": {"b": 1}, "relation": "mentions", "confidence": ["EXTRACTED"]})
        d["edges"].append("not an object")
        d["nodes"].append("not an object")
        d["nodes"].append({"id": ["unhashable"]})
        r = graph_check.check(d, ["not", "an", "object"])
        self.assertFalse(r["ok"])
        self.assertTrue(any("manifest must be" in p for p in r["problems"]))
        d2 = load("graph_extraction.json")
        d2["edges"][0]["confidence"] = ["x"]
        self.assertFalse(graph_check.check(d2)["ok"])

    def test_fake_video_link_does_not_count(self):
        d = load("graph_extraction.json")
        d["nodes"].append({"id": "v_other", "kind": "video", "label": "o", "source_file": "videos/o.md"})
        d["edges"].append({"source": "v_other", "target": "v_demoAAAAAAA", "relation": "references", "confidence": "EXTRACTED",
                           "confidence_score": 1.0, "source_file": "videos/o.md", "source_location": "L1"})
        d["edges"].append({"source": "v_other", "target": "c_prompting", "relation": "from_video", "confidence": "EXTRACTED",
                           "confidence_score": 1.0, "source_file": "videos/o.md", "source_location": "L2"})
        r = graph_check.check(d)
        self.assertTrue(any("video with no linked claim: v_other" in p for p in r["problems"]), r)

    def test_edge_provenance_and_score(self):
        for mutate, text in (
            (lambda e: e.pop("source_file"), "source_file and source_location"),
            (lambda e: e.pop("source_location"), "source_file and source_location"),
            (lambda e: e.pop("confidence_score"), "confidence_score"),
            (lambda e: e.__setitem__("confidence_score", 1.5), "confidence_score"),
            (lambda e: e.__setitem__("confidence_score", float("nan")), "confidence_score"),
            (lambda e: e.__setitem__("confidence_score", True), "confidence_score"),
        ):
            d = load("graph_extraction.json")
            mutate(d["edges"][0])
            self.assertTrue(any(text in p for p in graph_check.check(d)["problems"]), text)

    def test_inferred_and_ambiguous_need_basis(self):
        d = load("graph_extraction.json")
        del d["edges"][1]["basis"]
        self.assertTrue(any("INFERRED edge without basis" in p for p in graph_check.check(d)["problems"]))
        d = load("graph_extraction.json")
        d["edges"][1]["confidence"] = "AMBIGUOUS"
        del d["edges"][1]["basis"]
        self.assertTrue(any("AMBIGUOUS edge without basis" in p for p in graph_check.check(d)["problems"]))

    def test_manifest_counts_as_coverage_record(self):
        d = load("graph_extraction.json")
        d["nodes"] = [n for n in d["nodes"] if n["kind"] != "coverage"]
        self.assertFalse(graph_check.check(d)["ok"])
        r = graph_check.check(d, load("graph_manifest.json"))
        self.assertFalse(any("coverage" in p for p in r["problems"]), r)

    def test_links_key_accepted(self):
        d = load("graph_extraction.json")
        d["links"] = d.pop("edges")
        self.assertTrue(graph_check.check(d, load("graph_manifest.json"))["ok"])

    def test_cli_exit_codes(self):
        ok = subprocess.run([sys.executable, os.path.join(SCRIPTS, "graph_check.py"), os.path.join(FIX, "graph_extraction.json"),
                             "--manifest", os.path.join(FIX, "graph_manifest.json")], capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stdout)
        bad = subprocess.run([sys.executable, os.path.join(SCRIPTS, "graph_check.py"), os.path.join(FIX, "missing.json")], capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)

    def test_no_network_imports(self):
        src = open(os.path.join(SCRIPTS, "graph_check.py"), encoding="utf-8").read()
        for bad in ("urllib", "socket", "requests", "http."):
            self.assertNotIn(bad, src)


if __name__ == "__main__":
    unittest.main()
