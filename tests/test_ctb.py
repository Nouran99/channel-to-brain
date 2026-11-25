"""Offline tests for scripts/ctb.py. Fictional fixture, no network, no API.
Run: python3 -m unittest discover -s tests   (from the plugin root)"""
import csv, json, os, subprocess, sys, tempfile, unittest


def rj(p):
    with open(p) as f:
        return json.load(f)


def wj(p, o):
    with open(p, "w") as f:
        json.dump(o, f)


CTB = os.path.join(os.path.dirname(__file__), "..", "skills", "channel-to-brain", "scripts", "ctb.py")

ROWS = [
    {"video_id": "vidB", "title": "B", "length_s": "1300", "upload_date": "2026-01-01", "views": "10", "relevance": "5", "knowledge_value": "3"},
    {"video_id": "vidA", "title": "A", "length_s": "90", "upload_date": "2026-05-01", "views": "5", "relevance": "5", "knowledge_value": "3"},
    {"video_id": "vidC", "title": "C", "length_s": "200", "upload_date": "", "views": "99", "relevance": "1", "knowledge_value": "1"},
    {"video_id": "vidA", "title": "A dup", "length_s": "90", "upload_date": "2026-05-01", "views": "5", "relevance": "5", "knowledge_value": "3"},
]


class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        with open(os.path.join(self.d, "v.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(ROWS[0]))
            w.writeheader(); w.writerows(ROWS)
        self.run_ok("init")
        self.out = self.run_ok("import", "--file", os.path.join(self.d, "v.csv"))
        self.run_ok("rank")

    def run_ctb(self, *args, env=None):
        e = dict(os.environ); e.update(env or {})
        return subprocess.run([sys.executable, CTB, "--workdir", self.d] + list(args),
                              capture_output=True, text=True, env=e)

    def run_ok(self, *args):
        r = self.run_ctb(*args)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        return r.stdout

    def text(self, s="some text"):
        p = os.path.join(self.d, "t.txt")
        with open(p, "w") as f:
            f.write(s)
        return p

    def test_unique_ids_and_rank_order(self):
        self.assertIn('"duplicates_skipped": 1', self.out)
        inv = rj(os.path.join(self.d, "inventory.json"))
        # same relevance and knowledge: newer date (vidA) first, then vidB, vidC last
        self.assertEqual([v["video_id"] for v in inv["videos"]], ["vidA", "vidB", "vidC"])

    def test_window_plan_and_resume(self):
        w = json.loads(self.run_ok("windows", "--video", "vidB"))
        self.assertEqual([(x["start"], x["end"]) for x in w], [(0, 600), (600, 1200), (1200, 1300)])
        self.run_ok("claim", "--video", "vidA", "--start", "0", "--end", "90")
        self.run_ok("record", "--video", "vidA", "--start", "0", "--end", "90", "--status", "ok",
                    "--model", "m", "--tokens", "5", "--text-file", self.text())
        n = json.loads(self.run_ok("next", "--limit", "2"))["next"]
        self.assertEqual(n[0]["video_id"], "vidB")  # saved success skipped

    def test_no_duplicate_claim_or_overwrite(self):
        self.run_ok("claim", "--video", "vidA", "--start", "0", "--end", "90")
        self.assertEqual(self.run_ctb("claim", "--video", "vidA", "--start", "0", "--end", "90").returncode, 3)
        self.run_ok("record", "--video", "vidA", "--start", "0", "--end", "90", "--status", "ok", "--text-file", self.text())
        self.assertEqual(self.run_ctb("claim", "--video", "vidA", "--start", "0", "--end", "90").returncode, 3)
        self.assertEqual(self.run_ctb("record", "--video", "vidA", "--start", "0", "--end", "90", "--status", "ok", "--text-file", self.text()).returncode, 3)

    def test_failure_blocks_and_needs_user_approval(self):
        r = self.run_ctb("record", "--video", "vidA", "--start", "0", "--end", "90", "--status", "error", "--http-status", "503")
        self.assertEqual(r.returncode, 0)
        self.assertIn("BLOCKED", r.stdout)
        j = json.loads(self.run_ok("next", "--limit", "5"))
        self.assertEqual([x["video_id"] for x in j["blocked_need_user_decision"]], ["vidA"])
        self.assertNotIn("vidA", [x["video_id"] for x in j["next"]])
        self.assertNotEqual(self.run_ctb("unblock", "--video", "vidA", "--start", "0", "--end", "90").returncode, 0)
        self.run_ok("unblock", "--video", "vidA", "--start", "0", "--end", "90", "--approval-note", "user approved one retry for this window")
        j = json.loads(self.run_ok("next", "--limit", "5"))
        self.assertIn("vidA", [x["video_id"] for x in j["next"]])

    def test_empty_ok_rejected_and_filter_recorded_as_block(self):
        r = self.run_ctb("record", "--video", "vidA", "--start", "0", "--end", "90", "--status", "ok", "--text-file", self.text("  "))
        self.assertNotEqual(r.returncode, 0)
        self.run_ok("record", "--video", "vidA", "--start", "0", "--end", "90", "--status", "filter", "--note", "empty output")
        self.assertEqual(json.loads(self.run_ok("coverage"))["visual_pass"]["blocked"], 1)

    def test_coverage_counts_by_unique_id(self):
        for s, e in ((0, 600), (600, 1200), (1200, 1300)):
            self.run_ok("record", "--video", "vidB", "--start", str(s), "--end", str(e), "--status", "ok", "--text-file", self.text())
        self.run_ok("record", "--video", "vidC", "--start", "0", "--end", "200", "--status", "ok", "--text-file", self.text())
        c = json.loads(self.run_ok("coverage", "--write", os.path.join(self.d, "COV.md")))
        self.assertEqual(c["unique_videos"], 3)
        self.assertEqual(c["visual_pass"]["done"], 2)   # vidB all windows; vidC single window (200 s)? see below
        self.assertTrue(os.path.exists(os.path.join(self.d, "COV.md")))

    def test_check_flags_mismatch(self):
        os.makedirs(os.path.join(self.d, "results"), exist_ok=True)
        wj(os.path.join(self.d, "results", "wrong-name.json"), {"video_id": "vidA", "start": 0, "end": 90, "status": "ok", "text": "x"})
        r = self.run_ctb("check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("name does not match", r.stdout)

    def test_credential_check_never_prints_value(self):
        cfg = os.path.join(self.d, "ctb.config.json")
        c = rj(cfg); c["key_env_name"] = "CTB_TEST_KEY"; wj(cfg, c)
        r = self.run_ctb("credential-check", env={"CTB_TEST_KEY": "SECRET-VALUE-123"})
        self.assertEqual(r.returncode, 0)
        self.assertIn("present", r.stdout)
        self.assertNotIn("SECRET-VALUE-123", r.stdout + r.stderr)
        self.assertEqual(self.run_ctb("credential-check", env={"CTB_TEST_KEY": ""}).returncode, 1)

    def test_ctb_has_no_network_imports(self):
        with open(CTB) as f:
            src = f.read()
        for m in ("socket", "urllib", "http.client", "requests", "subprocess"):
            self.assertNotIn("import " + m, src)

    def test_record_rejects_window_outside_plan(self):
        r = self.run_ctb("record", "--video", "vidA", "--start", "0", "--end", "600", "--status", "ok", "--text-file", self.text())
        self.assertNotEqual(r.returncode, 0)

    # ---- hardening tests ----
    def test_unsafe_ids_rejected_on_import(self):
        for bad in ("../x", "a/b", "/abs", "a\\b", "..", "a b", "x" * 65, "id\x00z", "résumé", ""):
            p = os.path.join(self.d, "bad.json")
            wj(p, [{"video_id": bad, "length_s": 10}])
            r = self.run_ctb("import", "--file", p)
            self.assertEqual(r.returncode, 2, repr(bad))
            self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(os.listdir(os.path.join(self.d, "results")), [])

    def test_bad_numbers_dates_rejected_on_import(self):
        cases = [{"length_s": "-5"}, {"length_s": "nan"}, {"length_s": "inf"}, {"length_s": "abc"},
                 {"views": "-1"}, {"relevance": "1e999"}, {"upload_date": "01/02/2026"}, {"upload_date": "2026-1-2"}]
        for i, c in enumerate(cases):
            row = {"video_id": "ok%d" % i, "length_s": 10}
            row.update(c)
            p = os.path.join(self.d, "bad.json")
            wj(p, [row])
            r = self.run_ctb("import", "--file", p)
            self.assertEqual(r.returncode, 2, c)
            self.assertNotIn("Traceback", r.stderr)

    def test_unsafe_ids_and_windows_rejected_on_commands(self):
        for args in (["claim", "--video", "../evil", "--start", "0", "--end", "90"],
                     ["record", "--video", "../evil", "--start", "0", "--end", "90", "--status", "error"],
                     ["unblock", "--video", "../evil", "--start", "0", "--end", "90", "--approval-note", "x"],
                     ["claim", "--video", "vidA", "--start", "-1", "--end", "90"],
                     ["claim", "--video", "vidA", "--start", "50", "--end", "50"]):
            r = self.run_ctb(*args)
            self.assertNotEqual(r.returncode, 0, args)
            self.assertNotIn("Traceback", r.stderr)
        self.assertEqual(os.listdir(os.path.join(self.d, "results")), [])
        self.assertFalse(os.path.exists(os.path.join(self.d, "evil.json")))

    def test_corrupt_inventory_config_and_results_stop_cleanly(self):
        inv = os.path.join(self.d, "inventory.json")
        res = os.path.join(self.d, "results", "vidA__0-90.json")
        # corrupt result file: coverage and next stop, check reports it
        with open(res, "w") as f:
            f.write("{not json")
        for cmd in ("coverage", "next"):
            r = self.run_ctb(cmd)
            self.assertEqual(r.returncode, 2, cmd)
            self.assertIn("corrupt", r.stderr)
            self.assertNotIn("Traceback", r.stderr)
        r = self.run_ctb("check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("corrupt", r.stdout)
        # result with a missing or invalid status is never counted
        wj(res, {"video_id": "vidA", "start": 0, "end": 90, "text": "x"})
        r = self.run_ctb("coverage")
        self.assertEqual(r.returncode, 2)
        self.assertIn("invalid status", r.stderr)
        os.remove(res)
        # corrupt inventory
        for body in ("{oops", "[]", '{"videos": "x"}', '{"videos": [{"video_id": "../x"}]}',
                     '{"videos": [{"video_id": "a"}, {"video_id": "a"}]}',
                     '{"videos": [{"video_id": "a", "length_s": -1}]}'):
            with open(inv, "w") as f:
                f.write(body)
            r = self.run_ctb("coverage")
            self.assertEqual(r.returncode, 2, body)
            self.assertNotIn("Traceback", r.stderr)
        # corrupt config
        with open(os.path.join(self.d, "ctb.config.json"), "w") as f:
            f.write("nope")
        r = self.run_ctb("coverage")
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("Traceback", r.stderr)

    def test_config_paths_and_window_seconds_validated(self):
        cfg = os.path.join(self.d, "ctb.config.json")
        for bad in ({"results_dir": "../outside"}, {"results_dir": "/tmp/abs"}, {"inventory_file": "../inv.json"},
                    {"window_seconds": 0}, {"window_seconds": "600"}):
            c = rj(cfg); c.update(bad); wj(cfg, c)
            r = self.run_ctb("coverage")
            self.assertEqual(r.returncode, 2, bad)
            wj(cfg, {})

    def test_leftover_claims_and_temp_files_are_visible(self):
        self.run_ok("claim", "--video", "vidA", "--start", "0", "--end", "90", "--owner", "w1")
        n = json.loads(self.run_ok("next", "--limit", "5"))
        self.assertEqual([x["video_id"] for x in n["claimed_in_progress_or_stale"]], ["vidA"])
        with open(os.path.join(self.d, "results", "vidB__0-600.json.123.tmp"), "w") as f:
            f.write("partial")
        r = self.run_ctb("check")
        self.assertEqual(r.returncode, 1)
        self.assertIn("claim present", r.stdout)
        self.assertIn("leftover temp", r.stdout)
        self.run_ok("release", "--video", "vidA", "--start", "0", "--end", "90")

    def test_parallel_claims_only_one_wins(self):
        import concurrent.futures as cf
        sys.path.insert(0, os.path.dirname(CTB))
        import ctb
        w = ctb.Work(self.d)
        with cf.ThreadPoolExecutor(16) as ex:
            res = list(ex.map(lambda i: ctb.claim_window(w, "vidB", 0, 600, "w%d" % i), range(16)))
        self.assertEqual(res.count(None), 1)

    def test_parallel_records_only_one_wins_and_file_is_valid(self):
        import concurrent.futures as cf
        sys.path.insert(0, os.path.dirname(CTB))
        import ctb
        w = ctb.Work(self.d)
        big = "x" * 200000
        with cf.ThreadPoolExecutor(16) as ex:
            res = list(ex.map(lambda i: ctb.record_result(w, "vidB", 0, 600, "ok", 200, i, "m", "", big + str(i)), range(16)))
        self.assertEqual(res.count(None), 1)
        r = rj(w.rpath("vidB", 0, 600))
        self.assertEqual(r["status"], "ok")
        self.assertEqual(len(r["text"]) - len(str(r["tokens"])), 200000)
        left = [f for f in os.listdir(os.path.join(self.d, "results")) if f.endswith(".tmp")]
        self.assertEqual(left, [])

    # ---- result and inventory integrity (added after review) ----
    def put_result(self, rec, name="vidA__0-90.json"):
        os.makedirs(os.path.join(self.d, "results"), exist_ok=True)
        wj(os.path.join(self.d, "results", name), rec)

    def good(self, **kw):
        r = {"video_id": "vidA", "start": 0, "end": 90, "status": "ok", "http_status": 200,
             "tokens": 5, "model": "m", "note": "", "text": "real text"}
        r.update(kw)
        return r

    def assert_clean_stop(self, *args):
        r = self.run_ctb(*args)
        self.assertNotEqual(r.returncode, 0, r.stdout)
        self.assertNotIn("Traceback", r.stderr)
        return r

    def test_bad_result_files_are_never_counted(self):
        bad = [self.good(video_id="vidB"), self.good(start=1), self.good(end=91), self.good(text=""),
               self.good(text="   "), self.good(text=None), self.good(text=5), self.good(tokens=-1),
               self.good(tokens="5"), self.good(http_status=True), self.good(model=3),
               self.good(status="done"), [], "ok"]
        for rec in bad:
            self.put_result(rec)
            r = self.assert_clean_stop("coverage")
            self.assertIn("invalid", r.stderr)
            r = self.run_ctb("check")
            self.assertEqual(r.returncode, 1, (rec, r.stdout))
            os.remove(os.path.join(self.d, "results", "vidA__0-90.json"))
        self.put_result(self.good())
        self.run_ok("coverage"); self.run_ok("check")

    def edit_inv(self, fn):
        p = os.path.join(self.d, "inventory.json")
        inv = rj(p); fn(inv); wj(p, inv)

    def test_string_numbers_in_edited_inventory_are_normalised_or_rejected(self):
        def f(inv):
            for v in inv["videos"]:
                v["relevance"] = str(v["relevance"]); v["views"] = str(int(v["views"]))
        self.edit_inv(f)
        self.run_ok("rank")
        inv = rj(os.path.join(self.d, "inventory.json"))
        self.assertTrue(all(isinstance(v["relevance"], (int, float)) and not isinstance(v["relevance"], str) for v in inv["videos"]))
        for bad in ("abc", True, [1], {"a": 1}, -3, "nan", "inf"):
            self.edit_inv(lambda inv, b=bad: inv["videos"][0].__setitem__("knowledge_value", b))
            self.assert_clean_stop("rank")
            self.edit_inv(lambda inv: inv["videos"][0].__setitem__("knowledge_value", 1))

    def test_nonexistent_and_odd_dates_rejected(self):
        for dte in ("2026-02-30", "2026-13-01", "2026-00-10", "2025-02-29", "0000-01-01", "2026-1-1", "20260101"):
            with open(os.path.join(self.d, "d.csv"), "w") as f:
                f.write("video_id,length_s,upload_date\nnewv,10,%s\n" % dte)
            self.assert_clean_stop("import", "--file", os.path.join(self.d, "d.csv"))
        self.edit_inv(lambda inv: inv["videos"][0].__setitem__("upload_date", "2026-02-30"))
        self.assert_clean_stop("rank")

    def test_no_silent_overwrite_when_hard_links_unsupported(self):
        sys.path.insert(0, os.path.dirname(CTB))
        import ctb
        w = ctb.Work(self.d)
        real = os.link
        def nolink(a, b):
            raise OSError(1, "Operation not permitted")
        os.link = nolink
        try:
            with self.assertRaises(SystemExit) as cm:
                ctb.record_result(w, "vidA", 0, 90, "ok", 200, 1, "m", "", "text")
            self.assertEqual(cm.exception.code, 4)
        finally:
            os.link = real
        self.assertFalse(os.path.exists(w.rpath("vidA", 0, 90)))
        self.assertEqual([f for f in os.listdir(os.path.join(self.d, "results")) if f.endswith(".tmp")], [])

    def test_walkthrough_on_shipped_fixture(self):
        fx = os.path.join(os.path.dirname(__file__), "fixture")
        d = tempfile.mkdtemp()
        def c(*a):
            r = subprocess.run([sys.executable, CTB, "--workdir", d] + list(a), capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
            return r.stdout
        c("init")
        out = json.loads(c("import", "--file", os.path.join(fx, "videos.csv")))
        self.assertEqual(out["unique_total"], 3)
        c("rank")
        order = [x["video_id"] for x in json.loads(c("next", "--limit", "10"))["next"]]
        self.assertEqual(order, ["demoAAAAAAA", "demoBBBBBBB", "demoBBBBBBB", "demoBBBBBBB", "demoCCCCCCC"])
        with open(os.path.join(d, "t.txt"), "w") as f:
            f.write("model-reported screen text")
        for vid, s, e in (("demoAAAAAAA", 0, 90), ("demoBBBBBBB", 0, 600), ("demoBBBBBBB", 600, 1200)):
            c("claim", "--video", vid, "--start", str(s), "--end", str(e))
            c("record", "--video", vid, "--start", str(s), "--end", str(e), "--status", "ok", "--model", "m", "--text-file", os.path.join(d, "t.txt"))
        cov = json.loads(c("coverage", "--write", os.path.join(d, "COVERAGE_MANIFEST.md")))
        self.assertEqual(cov["visual_pass"], {"done": 1, "partial": 1, "remaining": 1, "blocked": 0, "no_windows": 0})
        c("check")
        self.assertTrue(os.path.exists(os.path.join(d, "COVERAGE_MANIFEST.md")))


if __name__ == "__main__":
    unittest.main()
