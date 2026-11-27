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
- Topic synthesis layer (SKILL.md 7.14, `references/topic-synthesis.md`, `scripts/topic_synthesis.py`): claims grouped by topic with video IDs and tags kept, a default core step. Owner instruction of 2026-11-27. First measured effect on the 300-question test: small (26.4 to 27.2).
- Design principle added to SKILL.md section 1 and the instructions log (owner, 2026-11-27): use the knowledge for decisions outside the channel; linking ideas matters more than transcribing.
- Standing rule (owner, 2026-11-27): each step that proves effective in the decision-transfer test is added as a default step with its measured result. First baseline: old 25.8, new 25.0 of 100 on 30 scenarios; connections between principles scored 0 for both.
- Link layer (SKILL.md 7.15, `references/link-layer.md`, `scripts/link_layer.py`), experimental, run when the owner asks for it, added at the owner's request on 2026-11-27: decision cards and typed links written by the running agent, no paid API call. Measured on one package: retrieval over 100 scenarios 66 (old), 67 (cards), 75 (cards plus links); decision pilot option match 100 in all conditions (saturated), point coverage 80, 82, 86. Section 1 now states the two rules: cards and links by the agent, Gemini key for reading videos only.
- Known gaps: no client load or validator run, no live model call.

## 0.1.0 (2026-11-25)
- First version: skill, three worker roles, four commands, adapters for Claude, ChatGPT, Codex, OpenCode and Gemini CLI, offline-tested helper scripts, knowledge-graph step, license.
