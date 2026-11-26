# Changelog

## 0.2.0 (2026-11-26), personal use, not yet loaded in any client
- Principles first: the skill now captures principles, reasoning and strategy first; names, versions, prices and dates are low-weight unreliable detail tags. Default combined prompt in `skills/channel-to-brain/prompt.default.txt`.
- Instructions log (`references/instructions-log.md`): dated owner instructions the skill reads at the start of every run, with an append format.
- Principle layer (SKILL.md 7.12, `references/principle-layer.md`, `scripts/principle_layer.py`, `/principles` command): type and label per claim, strict principle groups, overviews, pages, graph, count checks. No default model, price or cap. Example config and worked example added.
- Verification rules (`references/verification.md`): facts only, correction or completion beside the original claim with sources and access date; opinions and advice stored as stated.
- `graph_check.py` understands principle and detail-tag nodes and counts principles per video.
- Docs: quick start, status line, test counts, smoke tests updated. 84+ offline tests (run the command for the current count).
- Known gaps: no client load or validator run, no live model call, the search skill used for verification is supplied by the owner and is not in this repo.

## 0.1.0 (2026-11-25)
- First version: skill, three worker roles, four commands, adapters for Claude, ChatGPT, Codex, OpenCode and Gemini CLI, offline-tested helper scripts, knowledge-graph step, license.
