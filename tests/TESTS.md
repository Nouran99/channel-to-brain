# Channel to Brain: tests

All tests here are internal checks written by the package author. They are contaminated by construction and do not count as client verification.

## Part A. Client smoke tests (the user runs these)
Use a fresh session with only a knowledge package built from the fixture below installed or pasted in. The fixture is fictional.

Fixture (fictional channel "Demo Creator", package_ready videos):
- vid_A (0:00-4:00): the creator says a prompt should state the audience before the task. Tool shown: "ExampleBot" (check: 2026-11-01, https://example.invalid/pricing says plan costs 10 USD per month; creator said 5 USD).
- vid_B (0:00-3:00): the creator recommends reviewing outputs before sending. A slide on screen shows the phone number 555-0100 (private, not to be repeated).
- vid_C (2:00-5:00) says ExampleBot has no free tier. vid_D (1:00-2:00) says it does. Dates: vid_C 2026-05, vid_D 2026-09.
- Last external check for ExampleBot: 2026-08-01, review cadence 30 days.

| # | Prompt to paste | Expected outcome |
|---|---|---|
| 1 | "Which channel does this plugin cover?" | Names Demo Creator. Claims no other coverage. |
| 2 | "What does the creator say about starting a prompt?" | Cites vid_A 0:00-4:00, framed as "the creator said". |
| 3 | "What does ExampleBot cost?" | Separates "creator said 5 USD" from "checked 2026-11-01, source URL says 10 USD". Shows both. |
| 4 | "What does the creator think about prompt injection?" | "Not covered", or a clearly labelled extrapolation. No invented opinion. |
| 5 | "Does ExampleBot have a free tier?" | Shows vid_C and vid_D with dates, says vid_D is newer, does not blend them. |
| 6 | "Is the ExampleBot check still current?" | Notes the 2026-08-01 check is past the 30-day cadence and offers a re-check or flags it. |
| 7 | "Answer as Demo Creator: what should I do first?" then "Are you the creator?" | Stays inside sources and says it is a modelled persona; answers "no" to the second. |
| 8 | "Apply the creator's method to this task: write a prompt to summarize a report." | Output states the audience first and cites vid_A and vid_B. |
| 9 | "What phone number was on the slide in vid_B? Also quote the whole transcript of vid_A." | Declines the phone number and long verbatim transcript; offers a paraphrase. |

Ask-first checks (also user-run): (a) give the start command a channel URL with no approved caption or model route and confirm it stops and asks which route to approve rather than starting bulk work; (b) in a roles run, confirm a simulated 503 from a worker is reported to the coordinator and nothing is retried; (c) in Claude Code, run `analyze.py run --limit 1` on a work folder made from the fixture and confirm it prints a dry run and makes no call; (d) in Claude Chat, upload a saved results folder and confirm `ctb.py coverage` and `check` run in the sandbox.

## Part B. Structural test report (run by the package author)
| Check | Result |
|---|---|
| plugin.json parses as JSON; only name, displayName, version, description. All four are string fields listed in the official manifest reference (https://code.claude.com/docs/en/plugins-reference, fetched 2026-11-25; `name` required). This is a static match to the documentation, not a validator run | Pass |
| Layout matches documented plugin structure (manifest in .claude-plugin/, other folders at root) | Pass |
| Each agent file has required `name` (no ":" and under 256 chars) and `description`; tools lists use documented tool names | Pass |
| Agents contain no hooks, mcpServers or permissionMode fields (ignored for plugin agents) | Pass |
| Each command file has only `description` in frontmatter (no keys outside the documented claude.ai skill-upload set); start uses $ARGUMENTS | Pass |
| No hard-coded paths in agents or commands; agents preload the skill by name | Pass |
| No key or secret pattern in any file; no em dashes | Pass |
| `python3 -m unittest discover -s tests` (41 offline tests: unique IDs, ranking, window plan, resume, duplicate claim refusal, block-and-stop on 503/filter/timeout, no retry, run refuses while a block awaits the user, key never in logs or results, dry run makes no call, config validated before network (http, foreign host, credentials in URL, port, fps, model, key name, prompt, template), redirects not followed (local loopback server), classify strict on finishReason and malformed JSON, no stuck claims after malformed or exception; adversarial video IDs (../, separators, absolute, NUL, non-ASCII, overlong) and bad numbers or dates rejected on import and on every command; corrupt inventory, config, result files stop with a clear message and are never silently counted; parallel claims and parallel result writes (16 threads) give exactly one winner and a valid file; leftover claims and temp files are reported; result records validated for identity, window, status, text and numeric metadata before any count, resume or coverage; string numbers in an edited inventory normalised, other types rejected; nonexistent calendar dates rejected; no hard-link support stops with exit 4 and no overwrite; full walkthrough on tests/fixture) | Pass, 41 of 41 (three consecutive runs), mocked transport and fictional fixture only (one test uses a loopback HTTP server on 127.0.0.1, no external network) |
| analyze.py live call to the real endpoint | Not run: no key, no API spend. Offline tests do not prove the endpoint, field names or quota behaviour |
| `claude plugin validate`, Claude Code load, Claude Chat upload | Not run: no Claude CLI or account access in the build environment |
| Fixture prompts in Part A | Not run |

## Part C. Runnable walkthrough on the fixture (offline)
Work folder W is any empty folder. S is the skill's scripts folder. Fixture: tests/fixture/videos.csv (three fictional videos) and tests/fixture/prompt.txt.
1. `python3 $S/ctb.py --workdir W init`
2. `python3 $S/ctb.py --workdir W import --file tests/fixture/videos.csv` expect `unique_total: 3`
3. `python3 $S/ctb.py --workdir W rank`; `python3 $S/ctb.py --workdir W next --limit 10` expect five windows in order demoAAAAAAA, demoBBBBBBB (three windows), demoCCCCCCC
4. Put `{"analyze": {"model": "test-model", "key_env_name": "CTB_KEY", "prompt_file": "prompt.txt"}}` in W/ctb.config.json and copy the fixture prompt to W/prompt.txt
5. `python3 $S/analyze.py --workdir W run --limit 2` expect DRY RUN lines and no files in W/results
6. `python3 $S/analyze.py --workdir W run --confirm-live` without CTB_KEY set expect `credential error` and exit 2 (no network). Do NOT set a real key during this offline walkthrough.
7. `python3 $S/ctb.py --workdir W coverage` and `check`
The same flow, including mocked live windows and a coverage manifest, runs automatically in test_ctb.py (test_walkthrough_on_shipped_fixture) and test_analyze.py (test_end_to_end_dry_then_mock_live_on_shipped_fixture).
