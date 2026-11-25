"""Mocked tests for scripts/analyze.py. No network: the transport is a fake function."""
import csv, json, os, sys, tempfile, threading, unittest, urllib.error, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

SD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills", "channel-to-brain", "scripts")
sys.path.insert(0, SD)
import ctb, analyze  # noqa: E402

KEY = "SECRET-KEY-VALUE"


def ok_resp(text="screen text"):
    return 200, json.dumps({"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}],
                            "usageMetadata": {"totalTokenCount": 42}})


class A(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        rows = [{"video_id": "v1", "length_s": "1300", "relevance": "5", "knowledge_value": "1"},
                {"video_id": "v2", "length_s": "100", "relevance": "1", "knowledge_value": "1"}]
        with open(os.path.join(self.d, "v.csv"), "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0])); wr.writeheader(); wr.writerows(rows)
        with open(os.path.join(self.d, "prompt.txt"), "w") as f:
            f.write("Describe what is on screen.")
        with open(os.path.join(self.d, "ctb.config.json"), "w") as f:
            json.dump({"analyze": {"model": "test-model", "key_env_name": "CTB_KEY", "prompt_file": "prompt.txt",
                                   "max_calls_per_run": 10, "min_seconds_between_calls": 3}}, f)
        os.makedirs(os.path.join(self.d, "results"))
        w = ctb.Work(self.d); w.save({"videos": []})
        import argparse
        ctb.cmd_import(w, argparse.Namespace(file=os.path.join(self.d, "v.csv")))
        ctb.cmd_rank(w, None)
        self.w = ctb.Work(self.d)
        self.log = []
        self.sleeps = []

    def setcfg(self, upd, replace=False):
        p = os.path.join(self.d, "ctb.config.json")
        with open(p) as f:
            c = json.load(f)
        c["analyze"] = upd if replace else dict(c["analyze"], **upd)
        with open(p, "w") as f:
            json.dump(c, f)
        self.w = ctb.Work(self.d)

    def go(self, transport, live=True, limit=None, key=KEY):
        return analyze.run(self.w, limit, live, transport, self.sleeps.append, {"CTB_KEY": key}, self.log.append)

    def test_dry_run_makes_no_calls_and_hides_key(self):
        def boom(*a): raise AssertionError("network called in dry run")
        self.assertEqual(self.go(boom, live=False), 0)
        text = "\n".join(self.log)
        self.assertIn("DRY RUN v1 0-600", text)
        self.assertNotIn(KEY, text)
        self.assertEqual(os.listdir(os.path.join(self.d, "results")), [])

    def test_live_run_records_in_rank_order_and_paces(self):
        seen = []
        def t(url, headers, body, timeout):
            seen.append((url, headers, body)); return ok_resp()
        self.assertEqual(self.go(t), 0)
        self.assertEqual(len(seen), 4)  # v1: 3 windows, v2: 1
        self.assertIn("test-model:generateContent", seen[0][0])
        fd = seen[0][2]["contents"][0]["parts"][0]
        self.assertEqual(fd["fileData"]["fileUri"], "https://www.youtube.com/watch?v=v1")
        self.assertEqual(fd["videoMetadata"]["startOffset"], "0s")
        self.assertEqual(fd["videoMetadata"]["endOffset"], "600s")
        self.assertEqual(seen[0][1]["x-goog-api-key"], KEY)
        self.assertEqual(self.sleeps, [3, 3, 3])
        self.assertEqual(self.go(t), 0)  # resume: nothing missing, no new calls
        self.assertEqual(len(seen), 4)
        c = ctb.coverage(self.w)
        self.assertEqual(c["visual_pass"]["done"], 2)

    def test_503_stops_without_retry_and_blocks_window(self):
        n = []
        def t(*a): n.append(1); return 503, '{"error": "high demand"}'
        self.assertEqual(self.go(t), 1)
        self.assertEqual(len(n), 1)  # no automatic retry, no further windows
        self.assertIn("Ask the user before any retry", "\n".join(self.log))
        self.assertEqual(self.w.state("v1", 0, 600), "blocked")
        calls = []
        def t2(*a): calls.append(1); return ok_resp()
        self.assertEqual(self.go(t2), 1)  # new run refuses while a block awaits the user
        self.assertEqual(calls, [])
        self.assertEqual(analyze.run(self.w, None, True, t2, self.sleeps.append, {"CTB_KEY": KEY}, self.log.append,
                                     accepted_blocks_note="user accepted this gap"), 0)
        self.assertEqual(self.w.state("v1", 0, 600), "blocked")  # still a disclosed gap, never retried
        self.assertEqual(self.w.state("v1", 600, 1200), "done")

    def test_filter_reason_and_empty_text_are_blocks(self):
        def t(*a):
            return 200, json.dumps({"candidates": [{"finishReason": "RECITATION"}]})
        self.assertEqual(self.go(t), 1)
        self.assertEqual(self.w.state("v1", 0, 600), "blocked")
        with open(self.w.rpath("v1", 0, 600)) as f:
            self.assertIn("RECITATION", json.load(f)["note"])

    def test_timeout_is_recorded_and_stops(self):
        def t(*a): raise TimeoutError("slow")
        self.assertEqual(self.go(t), 1)
        self.assertEqual(self.w.state("v1", 0, 600), "blocked")

    def test_key_never_in_results_or_log(self):
        def t(*a): return 400, "bad request echo " + KEY
        self.go(t)
        blob = "\n".join(self.log)
        for fn in os.listdir(os.path.join(self.d, "results")):
            with open(os.path.join(self.d, "results", fn)) as f:
                blob += f.read()
        self.assertNotIn(KEY, blob)

    def test_missing_config_or_key_refuses(self):
        self.assertEqual(self.go(lambda *a: ok_resp(), key=""), 2)
        self.setcfg({"key_env_name": "CTB_KEY", "prompt_file": "prompt.txt"}, replace=True)
        self.assertEqual(self.go(lambda *a: ok_resp()), 2)  # no default model assumed

    def test_limit_caps_calls(self):
        n = []
        def t(*a): n.append(1); return ok_resp()
        self.go(t, limit=2)
        self.assertEqual(len(n), 2)

    def test_two_workers_cannot_take_same_window(self):
        self.assertIsNone(ctb.claim_window(self.w, "v1", 0, 600, "a"))
        self.assertIsNotNone(ctb.claim_window(self.w, "v1", 0, 600, "b"))

    # ---- hardening tests ----
    def refuses(self, upd, expect):
        self.setcfg(upd)
        called = []
        def t(*a): called.append(1); return ok_resp()
        self.assertEqual(self.go(t), 2)
        self.assertEqual(called, [])
        self.assertIn(expect, "\n".join(self.log))

    def test_config_validated_before_network(self):
        self.refuses({"endpoint_template": "http://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"}, "https")
        self.refuses({"endpoint_template": "https://evil.example/v1beta/models/{model}:generateContent"}, "allowed_hosts")
        self.refuses({"endpoint_template": "https://user:pw@generativelanguage.googleapis.com/x/{model}"}, "credentials")
        self.refuses({"endpoint_template": "https://generativelanguage.googleapis.com:8443/x/{model}"}, "443")
        self.refuses({"fps": 30}, "fps")
        self.refuses({"model": "bad model; rm"}, "model")
        self.refuses({"key_env_name": "AIza-not-a-name"}, "environment variable name")
        self.refuses({"prompt_file": "missing.txt"}, "prompt_file")
        self.refuses({"max_calls_per_run": 0}, "max_calls_per_run")
        self.refuses({"request_template": {"contents": "no prompt here"}}, "{prompt}")
        self.refuses({"video_url_template": "http://www.youtube.com/watch?v={video_id}"}, "https")

    def test_allowed_host_can_be_configured_but_must_match(self):
        self.setcfg({"endpoint_template": "https://example-proxy.test/v1beta/models/{model}:generateContent",
                     "allowed_hosts": ["example-proxy.test"]})
        self.assertEqual(self.go(lambda *a: ok_resp(), live=False), 0)

    def test_default_transport_refuses_before_sending_anything(self):
        with mock.patch("urllib.request.build_opener") as bo:
            with self.assertRaises(ValueError):
                analyze.default_transport("http://generativelanguage.googleapis.com/x", {"x-goog-api-key": KEY}, {}, 5)
            with self.assertRaises(ValueError):
                analyze.default_transport("https://other.example/x", {"x-goog-api-key": KEY}, {}, 5)
            bo.assert_not_called()

    def test_redirects_are_not_followed(self):
        seen = []
        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                seen.append((self.path, self.headers.get("x-goog-api-key")))
                if self.path == "/start":
                    self.send_response(302); self.send_header("Location", "/other"); self.end_headers()
                else:
                    self.send_response(200); self.end_headers(); self.wfile.write(b"{}")
            def log_message(self, *a): pass
        srv = HTTPServer(("127.0.0.1", 0), H)
        th = threading.Thread(target=srv.serve_forever, daemon=True); th.start()
        try:
            opener = urllib.request.build_opener(analyze.NoRedirect)
            req = urllib.request.Request("http://127.0.0.1:%d/start" % srv.server_port, data=b"{}", headers={"x-goog-api-key": KEY}, method="POST")
            with self.assertRaises(urllib.error.HTTPError) as cm:
                opener.open(req, timeout=5)
            self.assertEqual(cm.exception.code, 302)
        finally:
            srv.shutdown(); srv.server_close()
        self.assertEqual([p for p, _ in seen], ["/start"])  # never requested /other

    def test_classify_is_conservative_and_never_raises(self):
        good = {"candidates": [{"content": {"parts": [{"text": "hi"}]}, "finishReason": "STOP"}]}
        self.assertEqual(analyze.classify(200, json.dumps(good))[0], "ok")
        nofin = {"candidates": [{"content": {"parts": [{"text": "hi"}]}}]}
        rs, _, _, note = analyze.classify(200, json.dumps(nofin))
        self.assertEqual(rs, "filter"); self.assertIn("missing", note)
        for fin in ("MAX_TOKENS", "SAFETY", "RECITATION", "OTHER"):
            c = {"candidates": [{"content": {"parts": [{"text": "hi"}]}, "finishReason": fin}]}
            self.assertEqual(analyze.classify(200, json.dumps(c))[0], "filter")
        bad = ["[]", "null", '"x"', "{", "", '{"candidates": "x"}', '{"candidates": [1]}',
               '{"candidates": [{"content": {"parts": "x"}, "finishReason": "STOP"}]}',
               '{"candidates": [{"content": 5, "finishReason": "STOP"}]}',
               '{"candidates": [{"content": {"parts": [5, null]}, "finishReason": "STOP"}]}',
               '{"usageMetadata": "x", "candidates": []}']
        for raw in bad:
            rs = analyze.classify(200, raw)[0]
            self.assertIn(rs, ("error", "filter"), raw)
        self.assertEqual(analyze.classify(500, "x")[0], "error")

    def test_malformed_200_blocks_and_leaves_no_stuck_claim(self):
        self.assertEqual(self.go(lambda *a: (200, "not json")), 1)
        self.assertEqual(self.w.state("v1", 0, 600), "blocked")
        self.assertFalse(os.path.exists(self.w.cpath("v1", 0, 600)))

    def test_unexpected_exception_in_transport_leaves_no_stuck_claim(self):
        def t(*a): raise RuntimeError("boom " + KEY)
        self.assertEqual(self.go(t), 1)
        self.assertFalse(os.path.exists(self.w.cpath("v1", 0, 600)))
        self.assertNotIn(KEY, "\n".join(self.log))
        with open(self.w.rpath("v1", 0, 600)) as f:
            self.assertNotIn(KEY, f.read())

    def test_default_body_matches_documented_shape(self):
        part = analyze.DEFAULT_BODY["contents"][0]["parts"][0]
        self.assertEqual(sorted(part), ["fileData", "videoMetadata"])
        self.assertEqual(list(part["fileData"]), ["fileUri"])  # mimeType optional in the reference, omitted
        self.assertEqual(sorted(part["videoMetadata"]), ["endOffset", "fps", "startOffset"])
        self.assertEqual(analyze.DEFAULT_HEADER, "x-goog-api-key")
        self.assertEqual(analyze.DEFAULT_ENDPOINT, "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent")

    def test_end_to_end_dry_then_mock_live_on_shipped_fixture(self):
        import shutil, subprocess
        fx = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixture")
        d = tempfile.mkdtemp()
        shutil.copy(os.path.join(fx, "prompt.txt"), d)
        w0 = ctb.Work(d); os.makedirs(w0.res_dir); w0.save({"videos": []})
        import argparse
        ctb.cmd_import(w0, argparse.Namespace(file=os.path.join(fx, "videos.csv"))); ctb.cmd_rank(w0, None)
        with open(os.path.join(d, "ctb.config.json"), "w") as f:
            json.dump({"analyze": {"model": "test-model", "key_env_name": "CTB_KEY", "prompt_file": "prompt.txt",
                                   "min_seconds_between_calls": 0}}, f)
        w = ctb.Work(d)
        out = []
        self.assertEqual(analyze.run(w, 2, False, None, lambda s: None, {"CTB_KEY": KEY}, out.append), 0)
        self.assertTrue(any("demoAAAAAAA" in x for x in out))
        self.assertEqual(os.listdir(w.res_dir), [])
        # the real CLI refuses a live run without the key variable, before any network
        r = subprocess.run([sys.executable, os.path.join(SD, "analyze.py"), "--workdir", d, "run", "--confirm-live"],
                           capture_output=True, text=True, env={k: v for k, v in os.environ.items() if k != "CTB_KEY"})
        self.assertEqual(r.returncode, 2)
        self.assertIn("CTB_KEY is not set", r.stdout)
        self.assertEqual(analyze.run(w, None, True, lambda *a: ok_resp(), lambda s: None, {"CTB_KEY": KEY}, out.append), 0)
        cov = ctb.coverage(w)
        self.assertEqual(cov["visual_pass"]["done"], 3)
        self.assertEqual(cov["visual_pass"]["remaining"] + cov["visual_pass"]["blocked"] + cov["visual_pass"]["partial"], 0)


if __name__ == "__main__":
    unittest.main()
