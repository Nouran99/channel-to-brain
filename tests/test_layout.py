"""Layout checks for the per-client adapters. Offline, no network. These check files against the
documented formats; they do not load anything in a real client."""
import json, os, re, subprocess, sys, unittest
try:
    import jsonschema
except ImportError:
    jsonschema = None
try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)

def fm(path):
    m = re.match(r"---\n(.*?)\n---\n", open(path, encoding="utf-8").read(), re.S)
    return m.group(1) if m else None

class Layout(unittest.TestCase):
    def test_manifests_are_valid_json(self):
        for f in (".claude-plugin/plugin.json", "plugins/channel-to-brain/plugin.json", ".agents/plugins/marketplace.json", "gemini-extension.json"):
            json.load(open(P(*f.split("/"))))

    def test_author_and_license_as_chosen(self):
        # The user chose the author name and the PolyForm Noncommercial license on 2026-11-26.
        for f in (".claude-plugin/plugin.json", "plugins/channel-to-brain/plugin.json", "gemini-extension.json"):
            d = json.load(open(P(*f.split("/"))))
            for k in ("repository", "homepage"):
                self.assertNotIn(k, d, f)
            if f == ".claude-plugin/plugin.json":
                self.assertEqual(d.get("author"), {"name": "Nouran Darwish"}, f)
                self.assertEqual(d.get("license"), "PolyForm-Noncommercial-1.0.0", f)
            else:
                self.assertNotIn("author", d, f)
                self.assertNotIn("license", d, f)
        with open(P("LICENSE"), encoding="utf-8") as fh:
            lic = fh.read()
        self.assertTrue(lic.startswith("Required Notice: Copyright 2026 Nouran Darwish\n"))
        self.assertIn("# PolyForm Noncommercial License 1.0.0", lic)

    @unittest.skipIf(jsonschema is None, "needs the jsonschema package")
    def test_plugin_json_against_official_schema(self):
        # tests/schemas/agent-plugins-plugin.schema.json is the raw file from
        # https://agent-plugins.org/schemas/1.0.0/plugin.schema.json (fetched 2026-11-25, unmodified).
        schema = json.load(open(P("tests", "schemas", "agent-plugins-plugin.schema.json")))
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(json.load(open(P("plugins", "channel-to-brain", "plugin.json"))), schema)

    def test_marketplace_against_documented_shape(self):
        # No official marketplace schema was found. Checked against the fields and values shown at
        # https://developers.openai.com/plugins/build/plugins (marketplace metadata section).
        m = json.load(open(P(".agents", "plugins", "marketplace.json")))
        self.assertTrue(m["name"])
        self.assertTrue(m["plugins"])
        for e in m["plugins"]:
            self.assertEqual(e["source"]["source"], "local")
            path = e["source"]["path"]
            self.assertTrue(path.startswith("./") and len(path) > 2, path)
            target = P(*path[2:].split("/"))
            self.assertTrue(os.path.isfile(os.path.join(target, "plugin.json")), path)
            self.assertEqual(json.load(open(os.path.join(target, "plugin.json")))["name"], e["name"])
            self.assertTrue(os.path.isdir(os.path.join(target, "skills")))
            self.assertIn(e["policy"]["installation"], ("AVAILABLE", "INSTALLED_BY_DEFAULT", "NOT_AVAILABLE"))
            self.assertIn(e["policy"]["authentication"], ("ON_INSTALL", "ON_USE"))

    def test_claude_overrides_exclude_gemini_defaults(self):
        # https://code.claude.com/docs/en/plugins-reference : "commands" and "agents" replace the default
        # commands/ and agents/ scan, so root agents/ and commands/ (Gemini files) are not loaded by Claude.
        d = json.load(open(P(".claude-plugin", "plugin.json")))
        self.assertIn("agents", d)
        self.assertIn("commands", d)
        for p in d["agents"]:
            self.assertFalse(p.startswith("./agents/"), p)
        self.assertFalse(str(d["commands"]).startswith("./commands"))

    def test_readme_walkthrough_runs(self):
        import tempfile
        txt = open(P("README.md"), encoding="utf-8").read()
        m = re.search(r"```bash\n(set -e\n.*?)```", txt, re.S)
        self.assertTrue(m, "README walkthrough block missing")
        with tempfile.TemporaryDirectory() as tmp:
            env = {k: v for k, v in os.environ.items() if k != "CTB_KEY"}
            env["W"] = os.path.join(tmp, "w")
            os.makedirs(env["W"])
            r = subprocess.run(["bash", "-c", m.group(1)], cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("DRY RUN", r.stdout)
            self.assertFalse(os.path.exists(os.path.join(env["W"], "results")) and os.listdir(os.path.join(env["W"], "results")))

    def test_claude_paths_exist_and_have_dot_slash(self):
        d = json.load(open(P(".claude-plugin", "plugin.json")))
        paths = d["agents"] + [d["commands"]]
        for p in paths:
            self.assertTrue(p.startswith("./"), p)
            self.assertTrue(os.path.exists(P(*p[2:].split("/"))), p)

    def test_claude_agents_have_claude_schema(self):
        for fn in os.listdir(P("adapters", "claude", "agents")):
            h = fm(P("adapters", "claude", "agents", fn))
            self.assertIn("tools: ", h)
            self.assertNotIn("kind:", h)

    def test_gemini_agents_schema(self):
        for fn in os.listdir(P("agents")):
            h = fm(P("agents", fn))
            self.assertIn("kind: local", h)
            self.assertRegex(h, r"name: [a-z0-9_]+\n")
            self.assertNotIn("skills:", h)
            self.assertIn("  - activate_skill", h)
            known = {"activate_skill", "read_file", "read_many_files", "grep_search", "glob", "list_directory", "write_file", "replace", "web_fetch", "google_web_search"}
            tools = re.findall(r"^  - (\w+)$", h, re.M)
            self.assertTrue(set(tools) <= known, tools)

    def test_note_format_contract(self):
        skill = open(P("skills", "channel-to-brain", "SKILL.md"), encoding="utf-8").read()
        self.assertIn("## Spoken", skill)
        self.assertIn("### Window HH:MM-HH:MM", skill)
        ref = open(P("skills", "channel-to-brain", "references", "principle-layer.md"), encoding="utf-8").read()
        self.assertIn("## Spoken", ref)
        self.assertIn("references/verification.md", skill)
        self.assertTrue(os.path.exists(P("skills", "channel-to-brain", "references", "verification.md")))

    @unittest.skipIf(tomllib is None, 'needs Python 3.11+ tomllib')
    def test_gemini_commands_toml(self):
        for fn in os.listdir(P("commands")):
            self.assertTrue(fn.endswith(".toml"))
            d = tomllib.load(open(P("commands", fn), "rb"))
            self.assertIn("prompt", d)
            self.assertNotIn("$ARGUMENTS", d["prompt"])

    @unittest.skipIf(tomllib is None, 'needs Python 3.11+ tomllib')
    def test_codex_agents_required_fields(self):
        for fn in os.listdir(P("adapters", "codex", "agents")):
            d = tomllib.load(open(P("adapters", "codex", "agents", fn), "rb"))
            for k in ("name", "description", "developer_instructions"):
                self.assertTrue(d.get(k), (fn, k))

    def test_opencode_files(self):
        for fn in os.listdir(P("adapters", "opencode", "agents")):
            h = fm(P("adapters", "opencode", "agents", fn))
            self.assertIn("mode: subagent", h)
            self.assertIn("permissions:", h)
            acts = re.findall(r'action: "([^"]+)"', h)
            self.assertEqual(acts[0], "*")
            self.assertIn("skill", acts)
            self.assertTrue(set(acts) <= {"*", "shell", "edit", "subagent", "read", "glob", "grep", "webfetch", "websearch", "skill"}, acts)
            self.assertEqual(set(re.findall(r"effect: (\w+)", h)) - {"deny", "allow"}, set())
            self.assertNotIn('action: "shell"', h)
        for fn in os.listdir(P("adapters", "opencode", "commands")):
            self.assertIn("description:", fm(P("adapters", "opencode", "commands", fn)))

    def test_skill_name_rules(self):
        for f in (("skills", "channel-to-brain", "SKILL.md"), ("adapters", "chatgpt", "channel-to-brain", "SKILL.md")):
            h = fm(P(*f))
            name = re.search(r"^name: (.+)$", h, re.M).group(1)
            self.assertEqual(name, "channel-to-brain")
            desc = re.search(r"^description: (.+)$", h, re.M).group(1)
            self.assertLessEqual(len(desc), 1024)

    def test_chatgpt_note_scoped_to_imported_results(self):
        t = open(P("adapters", "chatgpt", "channel-to-brain", "SKILL.md"), encoding="utf-8").read()
        self.assertIn("imported from a client that ran the work", t)
        self.assertIn("do not perform them", t)
        self.assertNotIn("ship in the scripts/ folder of this skill", t)
        self.assertIn("NOT shipped in this ChatGPT copy", t)
        note = t.split("\n> ChatGPT adapter.", 1)[1].split("\n", 1)[0]
        self.assertNotIn("by hand as if machine-checked.", note.replace("recreate their counts by hand as if machine-checked.", ""))
        self.assertIn("Do not run, simulate or replace live model or API analysis", note)

    def test_plugin_folder_skill_matches_shared_skill(self):
        for r, d, f in os.walk(P("skills", "channel-to-brain")):
            d[:] = [x for x in d if x != "__pycache__"]
            for fn in f:
                rel = os.path.relpath(os.path.join(r, fn), P("skills", "channel-to-brain"))
                self.assertEqual(open(os.path.join(r, fn), encoding="utf-8").read(),
                                 open(P("plugins", "channel-to-brain", "skills", "channel-to-brain", rel), encoding="utf-8").read(), rel)

    def test_chatgpt_folder_has_no_scripts(self):
        self.assertEqual(sorted(os.listdir(P("adapters", "chatgpt", "channel-to-brain"))), ["LICENSE", "SKILL.md", "references"])
        self.assertEqual(sorted(os.listdir(P("adapters", "chatgpt", "channel-to-brain", "references"))), ["instructions-log.md", "knowledge-graph-step.md", "model-config.example.json", "principle-layer.md", "verification.md"])

    def test_principles_first_and_instructions_log(self):
        base = P("skills", "channel-to-brain")
        skill = open(os.path.join(base, "SKILL.md"), encoding="utf-8").read()
        self.assertIn("Principles first", skill)
        self.assertIn("references/instructions-log.md", skill)
        self.assertIn("PRINCIPLES_INDEX", skill)
        self.assertNotIn("TOPIC_INDEX", skill)
        log = open(os.path.join(base, "references", "instructions-log.md"), encoding="utf-8").read()
        self.assertIn("## Entries", log)
        self.assertRegex(log, r"### \d{4}-\d{2}-\d{2} \| (instruction|knowledge) \| ")
        default = open(os.path.join(base, "prompt.default.txt"), encoding="utf-8").read()
        fixture = open(P("tests", "fixture", "prompt.txt"), encoding="utf-8").read()
        self.assertEqual(default, fixture)

    def test_graph_and_private_repo_steps_are_required(self):
        skill = open(P("skills", "channel-to-brain", "SKILL.md"), encoding="utf-8").read()
        ref = open(P("skills", "channel-to-brain", "references", "knowledge-graph-step.md"), encoding="utf-8").read()
        readme = open(P("README.md"), encoding="utf-8").read()
        for text in (skill, ref, readme):
            self.assertNotIn("off by default", text)
            self.assertNotIn("Only on the user's request", text)
            self.assertNotIn("Optional knowledge-graph", text)
        for needle in ("## 14. Required step: knowledge graph export", "## 15. Required step: private GitHub repository",
                       "## 16. Completion criteria", "knowlege", "Mandatory does not waive approval", "not skipped"):
            self.assertIn(needle, skill, needle)
        self.assertIn("PRIVATE", skill)
        self.assertIn("incomplete", readme)

    def test_generated_files_in_sync(self):
        r = subprocess.run([sys.executable, P("adapters", "build_adapters.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)

if __name__ == "__main__":
    unittest.main()
