# Channel to Brain (v0.1.0)

Channel to Brain is a method for turning a creator's public YouTube channel into a source-attributed knowledge plugin for an AI assistant. It keeps honest coverage counts by unique video ID and follows an ask-first rule: when a problem, unclear point or important decision comes up, the agent stops and asks the user. It never retries, switches model or route, or installs anything on its own.

Status: prepared for your test. Nothing here has been loaded in any client, and no client validator has been run. The ask-first rule lives in the text of the skill and commands in every client. The clients enforce different things, so the guards are not equivalent.

## One source, several clients
One canonical skill (`skills/channel-to-brain/`) plus a thin adapter per client. The agent and command files outside the Claude folder are generated from the Claude files by `adapters/build_adapters.py`; `python3 adapters/build_adapters.py --check` fails if they drift.

| Client | What loads | Install | Gaps |
|---|---|---|---|
| Claude Code | Skill, 3 agents, 4 commands (`.claude-plugin/plugin.json` points to `adapters/claude/`) | `claude plugin validate ./channel-to-brain`, then `claude --plugin-dir ./channel-to-brain` | Commands are description-only, so not typed-only |
| Claude Chat | Skill (agents ignored, commands act as skills) | Customize > Plugins > Add > Upload plugin, with a zip of this repo. Needs Code execution on | Network documented for package sources only: run `ctb.py` there, not live analysis |
| Codex | Skill, via the generated plugin folder `plugins/channel-to-brain/` listed in `.agents/plugins/marketplace.json` | `codex plugin marketplace add Nouran99/channel-to-brain`, then install `channel-to-brain` from that marketplace (restart the ChatGPT desktop app if you use it there). Or copy `skills/channel-to-brain/` to `.agents/skills/` | Agents are copy-in: copy `adapters/codex/agents/*.toml` to `.codex/agents/`. They cannot restrict tools: the session's sandbox applies |
| Gemini CLI | Extension: skill, 3 agents (`agents/`), 4 TOML commands (`commands/`) | `gemini extensions install https://github.com/Nouran99/channel-to-brain` | Subagents are a preview feature and cannot call other subagents, so the main session coordinates |
| OpenCode | Skill from `.agents/skills` | Copy `skills/channel-to-brain/` to `.agents/skills/`, `adapters/opencode/agents/*.md` to `.opencode/agents/`, `adapters/opencode/commands/*.md` to `.opencode/commands/` | No plugin bundle for these parts: copy-in |
| ChatGPT | Instructions only | Upload `adapters/chatgpt/channel-to-brain/` (Plugins > Skills > Create > Upload from your computer) | No scripts shipped. Whether ChatGPT skills can run scripts or reach the network is not documented in the sources checked: unverified. Use it to understand and review analysis results imported from a client with a shell |

The Codex plugin folder is generated, not hand-edited: `adapters/build_adapters.py` copies the shared skill into `plugins/channel-to-brain/skills/` and writes its `plugin.json`, so `source.path` is `./plugins/channel-to-brain`, the shape in OpenAI's marketplace example. The marketplace add and install steps were not run here.

Why the folders are laid out this way: Claude Code and Gemini CLI both look for `agents/` and `commands/` at an extension root but with different file formats (Gemini: `kind`, `tools` names, TOML commands). The Claude manifest names its own files under `adapters/claude/`, which replaces its default scan, so the root `agents/` and `commands/` are Gemini's.

## Scripts: what runs where
- `skills/channel-to-brain/scripts/ctb.py`: inventory by unique video ID, ranking, window plan, claim/record/resume, result checks, coverage counts. No network. Python 3 standard library.
- `skills/channel-to-brain/scripts/analyze.py`: the model-call queue. It makes outbound HTTPS calls to the configured endpoint when run with `--confirm-live`, so it needs a client with a shell and network. Dry run is the default and sends nothing. Each live run needs the user's go-ahead.
- `skills/channel-to-brain/scripts/graph_check.py`: structure checks (dangling edges, anchors, linked claims, coverage node, manifest labels) for the optional knowledge-graph step. No network. It does not judge whether a claim is right.
- Tests use fictional fixtures and a mocked transport. No live call has been made: the endpoint, field names and quota behaviour are unproven. Request shape was read from Google's reference on 2026-11-25 (https://ai.google.dev/api/generate-content). Re-check before the first live call.
- Safety behaviour of `analyze.py`: HTTPS only, to a host in `allowed_hosts` checked before the key is attached; redirects never followed; config validated before any call; one request at a time; success needs HTTP 200, non-empty text and finishReason STOP; any other result stops the run with no retry. The key is read from the environment variable named in the config and is never printed, logged or saved.

### Minimal use (the user runs these from the repo root)
This walkthrough runs on the fictional fixture, sends nothing and needs no key. `tests/test_layout.py` runs this exact block.
```bash
set -e
S=skills/channel-to-brain/scripts
W=${W:-work}                      # any empty folder
python3 $S/ctb.py --workdir $W init
python3 $S/ctb.py --workdir $W import --file tests/fixture/videos.csv
python3 $S/ctb.py --workdir $W rank
python3 $S/ctb.py --workdir $W next --limit 10
cp tests/fixture/prompt.txt $W/prompt.txt
echo '{"analyze": {"model": "test-model", "key_env_name": "CTB_KEY", "prompt_file": "prompt.txt"}}' > $W/ctb.config.json
python3 $S/analyze.py --workdir $W run --limit 2          # dry run, no network
python3 $S/ctb.py --workdir $W coverage
python3 $S/ctb.py --workdir $W check
```
For your own channel: your CSV needs columns video_id, length_s, upload_date (YYYY-MM-DD or empty), views, relevance, knowledge_value, title; write your own prompt from SKILL 7.4; set `"model"` to the model you choose (there is no default) and `"key_env_name"` to the NAME of the environment variable that holds your key. A live run is `analyze.py --workdir W run --confirm-live`. Do it only when the user says go, with the key already in that variable.

## Optional knowledge-graph step (off by default)
Only on the user's request. The method is in `skills/channel-to-brain/references/knowledge-graph-step.md` and SKILL.md section 14. It uses Graphify (Graphify-Labs/graphify, PyPI `graphifyy`, two y), which was run once in a pilot at version 0.9.119 with no model backend. It was not run in any client from this repo. Installing it, a backend, a key, an upload and any spend are each the user's decision. The notes stay the authority and the graph never replaces them. Claude Chat and ChatGPT install nothing: they can only read an exported graph.

## Roles
The coordinator is the main session in every client, not an agent file. Workers (researcher, analyst, reviewer) report back to it. Where agents are ignored or not installed (Claude Chat, ChatGPT, or Codex and OpenCode without the copied files), one session plays the roles in sequence.

## Layout
- `skills/channel-to-brain/`: SKILL.md and `scripts/`.
- `.claude-plugin/plugin.json`, `adapters/claude/`: Claude.
- `.agents/plugins/marketplace.json`, `plugins/channel-to-brain/` (generated, with an Agent Plugins `plugin.json`), `adapters/codex/agents/`: Codex.
- `gemini-extension.json`, `agents/`, `commands/`: Gemini CLI.
- `adapters/opencode/`: OpenCode. `adapters/chatgpt/`: ChatGPT.
- `skills/channel-to-brain/references/`: the optional graph step.
- `tests/`: TESTS.md (client prompts), unit and layout tests. Run `python3 -m unittest discover -s tests` from the repo root. Two TOML parse checks need Python 3.11 and skip below it. The manifest schema check needs the `jsonschema` package and skips without it.

## Sources for the formats
- Claude: https://code.claude.com/docs/en/plugins-reference , https://claude.com/docs/plugins/platform-support
- OpenAI: https://developers.openai.com/plugins/build/plugins , https://developers.openai.com/plugins/concepts/plugins , https://learn.chatgpt.com/docs/build-skills , https://learn.chatgpt.com/docs/agent-configuration/subagents , https://agent-plugins.org/schemas/1.0.0/plugin.schema.json
- Gemini CLI: https://geminicli.com/docs/extensions/reference/ , https://geminicli.com/docs/core/subagents/ , https://geminicli.com/docs/cli/custom-commands/
- OpenCode: https://opencode.ai/docs/skills , https://opencode.ai/docs/agents/ , https://opencode.ai/docs/commands/
- Skill format: https://agentskills.io/specification

## Smoke tests
See `tests/TESTS.md`: runnable prompts with a fictional fixture. They are the package author's internal checks. Nothing is "verified in client" until the user runs them.

## License
No license file or license field is set.
