import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "skills", "channel-to-brain", "scripts"))
import resource_scan as rs  # noqa: E402


class ResourceScanTest(unittest.TestCase):
    def kinds(self, text):
        return {k for _n, k in rs.scan_text(text)}

    def test_flags_secrets(self):
        self.assertIn("email", self.kinds("write to someone" + "@example.com"))
        self.assertIn("credential-line", self.kinds("pass" + "word: hunter2"))
        self.assertIn("api-key", self.kinds("key sk-" + "abcdefgh12345678"))
        self.assertIn("phone", self.kinds("call +20 114 194 7879"))
        self.assertIn("url-with-credentials", self.kinds("https://user:" + "pw@host.example/x"))
        self.assertIn("private-key", self.kinds("-----BEGIN RSA " + "PRIVATE KEY-----"))

    def test_plain_notes_and_slugs_are_clean(self):
        self.assertEqual(rs.scan_text("A guide about the future of free tools\nhttps://x.example/ai-stack-for-business-free-course"), [])

    def test_main_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            ok = os.path.join(d, "a.md")
            open(ok, "w").write("plain note\n")
            self.assertEqual(rs.main([ok]), 0)
            bad = os.path.join(d, "b.md")
            open(bad, "w").write("token" + ": abc123\n")
            self.assertEqual(rs.main([bad]), 1)


if __name__ == "__main__":
    unittest.main()
