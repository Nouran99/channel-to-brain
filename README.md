# Channel to Brain (plugin, v0.1.0)

Channel to Brain is a method for turning a creator's public YouTube channel into a source-attributed knowledge plugin for an AI assistant. It keeps honest coverage counts by unique video ID and follows an ask-first rule: when a problem, unclear point or important decision comes up, the agent stops and asks the user. It never retries, switches model or route, or installs anything on its own.

Status: v0.1.0, prepared for your test. It has not been loaded in Claude Chat or Claude Code, and `claude plugin validate` has not been run. Two offline-tested Python helper scripts ship with it (see below). No hooks, MCP servers or bin/ folder ship with it, and nothing here installs software.

## What this package is, and is not
Included: the method (skill), three worker roles, four commands, and two Python 3 helper scripts (standard library only) with offline tests.
- `skills/channel-to-brain/scripts/ctb.py`: inventory by unique video ID, ranking, window plan, claim/record/resume, result checks, coverage counts. No network. Runs in Claude Code and in Claude Chat's code sandbox (needs "Code execution and file creation" on).
- `skills/channel-to-brain/scripts/analyze.py`: the model-call queue. Needs outbound HTTPS, so it is for Claude Code (or another shell with network). Claude Chat on an individual plan documents network access to package sources only, so in Chat the work runs on result files imported from a Code run.
Tested: offline only (mock transport, fictional fixture). Not tested: any live call, any client load, `claude plugin validate`. Request shape checked against Google's reference on 2026-11-25 (endpoint, `x-goog-api-key` header, `fileData.fileUri`, `videoMetadata` startOffset/endOffset/fps in (0, 24]; `mimeType` is optional and omitted). Re-check it before the first live call.
No hooks, no MCP servers, no bin/ folder, nothing installed. Running the scripts is the user's step and each live run needs the user's go-ahead (`--confirm-live`).
Safety behaviour of the scripts: dry run by default; HTTPS only, to a host in `allowed_hosts` (default generativelanguage.googleapis.com), checked before the key is attached, and redirects are never followed; config is validated before any network call; one request at a time; success needs HTTP 200, non-empty text and finishReason exactly STOP, and any other result (error, timeout, malformed response, empty or filtered output) is recorded as blocked and the run stops with no retry, never leaving a claim stuck; a later run refuses to start until the user decides on each block; the key is read from an environment variable named in config and is never printed or saved.

### Minimal use (Claude Code, the user runs these; paths are from the plugin root)
Set `S=skills/channel-to-brain/scripts` (in an installed plugin, use the skill folder's scripts directory) and make a work folder `W`.
1. `python3 $S/ctb.py --workdir W init`, then `python3 $S/ctb.py --workdir W import --file tests/fixture/videos.csv` (your own file needs columns video_id, length_s, upload_date as YYYY-MM-DD or empty, views, relevance, knowledge_value, title; video IDs may contain only letters, digits, _ and -), then `rank`.
2. Add to `W/ctb.config.json`: `{"analyze": {"model": "<chosen model>", "key_env_name": "<ENV VAR NAME>", "prompt_file": "prompt.txt"}}`. Copy `tests/fixture/prompt.txt` to `W/prompt.txt` or write your own from SKILL 7.4. The model is not defaulted. Other keys: allowed_hosts, endpoint_template, auth_header, fps, video_url_template, request_template, max_calls_per_run, min_seconds_between_calls, timeout_seconds.
3. `python3 $S/analyze.py --workdir W run --limit 1` prints a dry run and sends nothing. Add `--confirm-live` only when the user says go, with the key already in that environment variable.
4. `python3 $S/ctb.py --workdir W coverage` and `check` report counts by unique ID and file problems. A stale claim left by a crash shows up in `next` and `check`; `release` it only when no worker is running.
Limits: a result counts as done only if its ID, window, status, text and numbers check out. Concurrency safety holds for several workers on one machine's local filesystem (exclusive file create for claims, link-based publish for results). It is not tested on network drives or synced folders, and only the coordinator should write the inventory (import, rank).

## Contents
- `skills/channel-to-brain/SKILL.md`: the full method. The agents preload it, which adds its size to each subagent's context.
- `skills/channel-to-brain/scripts/`: ctb.py, analyze.py.
- `agents/`: channel-researcher (web read-only), channel-analyst (drafts notes from saved result files, no API calls), channel-reviewer (local evidence only). Each has the required `name` and `description`.
- `commands/`: start, status, checkpoint, package-check.
- `tests/`: TESTS.md (client prompts, test report), test_ctb.py, test_analyze.py. Run `python3 -m unittest discover -s tests` from the plugin root.

## Roles
The coordinator is the main session, not an agent file. Claude Code's docs say a subagent can start its own subagents only while a depth limit allows it, so workers report back to the main session, which alone assigns work and runs the single API queue. In Claude Chat the plugin's agents are ignored, so one session plays the roles in sequence.

## What works where (from Anthropic's plugin support table, checked 2026-11-25)
| Part | Claude Chat | Claude Code |
|---|---|---|
| Skill | Loads | Loads |
| Commands | Load as a skill that Claude applies when the task fits. No typed slash commands | Typed commands, for example /channel-to-brain:start |
| Agents (subagents) | Ignored. One session plays coordinator, researcher, analyst and reviewer in sequence | Loads (researcher, analyst, reviewer) |
| Hooks, local MCP, bin/ | None used | None used |

The ask-first rule comes from the text of the skill and of each command. Command files use only a `description` field, so in both clients Claude may apply a command on its own; every command only prepares, reports or asks.

## Roadmap
1. Claude Code and Claude Chat: this package. In Code the main session is the coordinator and three roles (researcher, analyst, reviewer) are native subagents. In Chat the same four roles run as sequential passes by one session.
2. ChatGPT and Codex: planned, not built. Needs its own check of each client's current official docs.
3. OpenCode and Gemini: planned, not built. Same check.
4. Generalize to other clients afterwards.
Nothing in phases 2 to 4 is supported or tested by this package.

## Install (the user does these steps)
- Claude Chat (claude.ai or desktop): Customize > Plugins > Add > Upload plugin, choose the zip. Skills need Code execution and file creation turned on (Settings > Capabilities). Read the skill before turning it on.
- Claude Code: from the folder that contains `channel-to-brain/`, run `claude plugin validate ./channel-to-brain`, then start a session with `claude --plugin-dir ./channel-to-brain`.
Sources: https://claude.com/docs/plugins/platform-support , https://claude.com/docs/plugins/build

## Smoke tests
See `tests/TESTS.md`: nine runnable prompts with a small fictional fixture and expected outcomes. They are internal checks written by the package author. Nothing is "verified in client" until the user runs them.

## License
No license file or license field is set.

## Clients and the ask-first limit
One package for both clients. Command files use only a `description` field because Anthropic documents a hard error for unsupported frontmatter keys on claude.ai skill uploads. Claude Code supports `disable-model-invocation: true` (typed-only commands) but this package does not set it, so commands are not typed-only. You can add it to your own copy for Claude Code. Claude Chat ignores agents; the roles run in sequence. analyze.py needs network and is for Claude Code or another shell.
