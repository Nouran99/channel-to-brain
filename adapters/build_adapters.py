#!/usr/bin/env python3
"""Regenerate the per-client agent, command and ChatGPT files from the Claude sources.

Single source of truth: adapters/claude/agents/*.md, adapters/claude/commands/*.md and
skills/channel-to-brain/SKILL.md. Run from the repo root: python3 adapters/build_adapters.py
Use --check to fail if committed generated files differ. No network, writes only inside the repo.
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda *p: os.path.join(ROOT, *p)

# Gemini tool names from https://geminicli.com/docs/reference/tools/
GEMINI_TOOLS = {
    "Read": ["read_file", "read_many_files"], "Grep": ["grep_search"], "Glob": ["glob", "list_directory"],
    "Write": ["write_file"], "Edit": ["replace"], "WebFetch": ["web_fetch"], "WebSearch": ["google_web_search"],
}
# OpenCode permission actions from https://opencode.ai/docs/agents/
OC_ACTIONS = {
    "Read": ["read", "glob", "grep"], "Grep": ["grep"], "Glob": ["glob"], "Write": ["edit"], "Edit": ["edit"],
    "WebFetch": ["webfetch"], "WebSearch": ["websearch"],
}
ALL_OC = ["read", "glob", "grep", "edit", "shell", "webfetch", "websearch", "subagent"]

def split_fm(text):
    m = re.match(r"---\n(.*?)\n---\n(.*)\Z", text, re.S)
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" ") and not line.startswith("-"):
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm, m.group(2)

def body_for_other(body):
    return body.replace("preloaded channel-to-brain skill", "channel-to-brain skill (load it first)")

def q(s):  # TOML basic string
    return json.dumps(s, ensure_ascii=False)

def gen():
    out = {}
    for fn in sorted(os.listdir(J("adapters", "claude", "agents"))):
        fm, body = split_fm(open(J("adapters", "claude", "agents", fn), encoding="utf-8").read())
        name, desc = fm["name"], fm["description"]
        tools = [t.strip() for t in fm["tools"].split(",")]
        b = body_for_other(body).strip() + "\n"
        # Gemini: agents/*.md, tools whitelist
        gt = ["activate_skill"]  # lets the agent load the channel-to-brain skill
        for t in tools:
            gt += [x for x in GEMINI_TOOLS[t] if x not in gt]
        out[f"agents/{name}.md"] = (
            "---\nname: %s\ndescription: %s\nkind: local\ntools:\n%s\n---\n%s"
            % (name.replace("-", "_"), desc, "\n".join(f"  - {x}" for x in gt), b))
        # OpenCode: deny by default, allow named actions
        allow = ["skill"]  # lets the agent load the channel-to-brain skill
        for t in tools:
            allow += [x for x in OC_ACTIONS[t] if x not in allow]
        rules = [("*", "deny")] + [(a, "allow") for a in allow]
        perms = "\n".join(f'  - action: "{a}"\n    resource: "*"\n    effect: {e}' for a, e in rules)
        out[f"adapters/opencode/agents/{name}.md"] = (
            "---\ndescription: %s\nmode: subagent\npermissions:\n%s\n---\n%s" % (desc, perms, b))
        # Codex: standalone TOML
        cb = b.replace("You have no write tools, so you cannot edit any file.", "Do not write or edit any file. This agent file cannot enforce that in Codex, so the session's sandbox and approval settings apply and you must follow the rule yourself.")
        cb = cb.replace("You have no write tools.", "Do not write or edit any file. This agent file cannot enforce that in Codex, so the session's sandbox and approval settings apply and you must follow the rule yourself.")
        out[f"adapters/codex/agents/{name}.toml"] = (
            "name = %s\ndescription = %s\ndeveloper_instructions = %s\n" % (q(name), q(desc), q(cb)))
    for fn in sorted(os.listdir(J("adapters", "claude", "commands"))):
        fm, body = split_fm(open(J("adapters", "claude", "commands", fn), encoding="utf-8").read())
        cmd = fn[:-3]
        desc = fm["description"]
        # Gemini TOML (commands/<name>.toml); {{args}} replaces $ARGUMENTS
        gb = body_for_other(body).strip().replace("$ARGUMENTS", "{{args}}")
        out[f"commands/{cmd}.toml"] = "description = %s\nprompt = %s\n" % (q(desc), q(gb + "\n"))
        ob = body_for_other(body).strip()
        out[f"adapters/opencode/commands/{cmd}.md"] = "---\ndescription: %s\n---\n%s\n" % (desc, ob)
    # ChatGPT: instructions-only skill folder. No scripts shipped, because script execution
    # and network access in ChatGPT skills are not documented, so they are unverified.
    skill = open(J("skills", "channel-to-brain", "SKILL.md"), encoding="utf-8").read()
    m = re.match(r"(---\n.*?\n---\n)(.*)\Z", skill, re.S)
    note = (
        "\n> ChatGPT adapter. Scope: understand and review analysis results that were imported from a client that ran the work "
        "(for example Claude Code, Codex or Gemini CLI). This copy ships without scripts. Whether ChatGPT skills can run "
        "scripts or reach the network is not documented in the sources checked, so it is unverified. Do not run, simulate or "
        "replace live model or API analysis here, do not claim ctb.py or analyze.py ran here, and do not recreate their counts "
        "by hand as if machine-checked. Sections below about running scripts, live calls, credentials or building the "
        "inventory describe other clients: do not perform them. If the user asks for that work, say it needs a client with a "
        "shell and network and ask which route to use. When reviewing imported results, use only the files the user gave, "
        "label any count as read from those files and not machine-checked, and keep the ask-first rule.\n")
    body = m.group(2)
    a1 = "Helper scripts ship in the scripts/ folder of this skill, tested offline with mocks only (section 13)."
    b1 = ("Helper scripts (scripts/ctb.py, scripts/analyze.py) belong to the shared core and are available in clients with a shell. "
          "They are NOT shipped in this ChatGPT copy and are unverified in ChatGPT. Mock-tested only (section 13).")
    a2 = "- Helper scripts (Python 3 standard library only), in the scripts/ folder next to this file."
    b2 = "- Helper scripts (Python 3 standard library only) are in the shared core's scripts/ folder, not in this ChatGPT copy."
    assert a1 in body and a2 in body
    body = body.replace(a1, b1).replace(a2, b2)
    out["adapters/chatgpt/channel-to-brain/SKILL.md"] = m.group(1) + note + body
    out["adapters/chatgpt/channel-to-brain/references/knowledge-graph-step.md"] = open(
        J("skills", "channel-to-brain", "references", "knowledge-graph-step.md"), encoding="utf-8").read()
    # Codex and ChatGPT plugin: a generated subfolder, so marketplace source.path matches OpenAI's documented
    # example shape (./plugins/<name>). Copy of the shared skill plus a portable plugin.json.
    base = J("skills", "channel-to-brain")
    for r, d, f in os.walk(base):
        d[:] = [x for x in d if x != "__pycache__"]
        for fn in f:
            rel = os.path.relpath(os.path.join(r, fn), base).replace(os.sep, "/")
            out["plugins/channel-to-brain/skills/channel-to-brain/" + rel] = open(os.path.join(r, fn), encoding="utf-8").read()
    out["plugins/channel-to-brain/plugin.json"] = json.dumps({
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "name": "channel-to-brain", "version": "0.1.0",
        "description": "A method for turning a creator's public YouTube channel into a source-attributed knowledge plugin, with honest coverage counts and an ask-first rule."}, indent=2) + "\n"
    return out

def main():
    out = gen()
    bad = 0
    for rel, txt in out.items():
        p = J(*rel.split("/"))
        if "--check" in sys.argv:
            if not os.path.exists(p) or open(p, encoding="utf-8").read() != txt:
                print("DIFF", rel); bad += 1
        else:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "w", encoding="utf-8").write(txt)
    print("checked" if "--check" in sys.argv else "wrote", len(out), "files", "bad=%d" % bad)
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
