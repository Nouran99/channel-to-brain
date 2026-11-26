# Changelog

## 0.2.0 (2026-11-26, updated 2026-11-27), personal use, not yet loaded in any client
- Principles first: the skill now captures principles, reasoning and strategy first; names, versions, prices and dates are low-weight unreliable detail tags. Default combined prompt in `skills/channel-to-brain/prompt.default.txt`.
- Instructions log (`references/instructions-log.md`): dated owner instructions the skill reads at the start of every run, with an append format.
- Principle layer (SKILL.md 7.12, `references/principle-layer.md`, `scripts/principle_layer.py`, `/principles` command): type and label per claim, strict principle groups, overviews, pages, graph, count checks. No default model, price or cap. Example config and worked example added.
- Verification rules (`references/verification.md`): facts only, correction or completion beside the original claim with sources and access date; opinions and advice stored as stated.
- `graph_check.py` understands principle and detail-tag nodes and counts principles per video.
- Docs: quick start, status line, test counts, smoke tests updated. 84+ offline tests (run the command for the current count).
- The search method for verification is included: `references/deep-research-skill.md`, a copy of the MIT-licensed deep-research skill by Eric Andrade (notice in `references/deep-research-LICENSE-MIT.txt`). Native mode only, no cost.
- Instructions log: no live model run without the owner's approval each time.
- Creator resources (SKILL.md 7.13, `references/resources.md`, `scripts/resource_scan.py`): resources linked in video descriptions are added by default, with a required secret check. Owner rule of 2026-11-27.
- Known gaps: no client load or validator run, no live model call.

## 0.1.0 (2026-11-25)
- First version: skill, three worker roles, four commands, adapters for Claude, ChatGPT, Codex, OpenCode and Gemini CLI, offline-tested helper scripts, knowledge-graph step, license.
