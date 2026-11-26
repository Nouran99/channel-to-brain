# Principle layer (runs after the per-video notes exist)

Adds a principle-first layer on top of the per-video notes: type and idea label per spoken claim, strict principle groups, a short overview per group, group pages, a graph around the groups, and count checks. It was built and used on two channels. Everything it produces is model output and stays labelled UNVERIFIED until a search verification run says otherwise (SKILL.md 7.8).

Helper: `scripts/principle_layer.py` (standard library only, offline-tested with a mock model). It has no default model, price, spend cap or channel. The owner decides the model and cap before any model call (SKILL.md section 2). The key comes from an environment variable only.

## Input
A package folder with `videos/<id>.md`, one note per video. Spoken claims are the bullet lines under "Spoken" sections inside "### Window HH:MM-HH:MM" blocks. On-screen items are skipped. A trailing `[details unreliable: ...]` tag stays in the note and is copied to the pages.

## Rules that hold in every step
1. The goal is ways of thinking, general principles and practical strategy. Exact versions, names, prices and dates are low-weight detail tags and never a reason to stop.
2. The speaker does not matter. Guest, host and podcast claims count the same. No marker for guest or multi-speaker content, no separate section. Write "the material", not "the creator". Keep the video ID on every claim.
3. Only facts are verified. Opinions, advice and personal choices are stored as stated in the channel and need no verification. Nothing is marked confirmed without a search verification (see the instructions log). A contradicted fact gets a correction beside it and a partly right fact gets the missing information added, automatically and with no review step. The original claim stays as said in the video; the correction is a separate line with sources and the access date.
4. Tell the owner the expected cost before any model call. Stop on the first API error, no retries. Saved responses are never run again.
5. Never use em dashes in outputs.

## Steps (run in this order; `--pkg` is the package folder, `--work` a work folder)
1. `claims`: parse every spoken claim (free). Result `claims.json`.
2. `type`: pass 1, one call per video (chunks of 150 claims). One line per claim: `number|type|label`. Types: principle, decision_rule, method_step, mistake, mental_model, example_story, detail, filler. The label is 3 to 7 words, the same label for the same idea inside a video. Then `parse` (free) writes `claims_typed.json` and reports how many claims stayed unlabeled.
3. `groups`: pass 2. Propose sharp groups (one reusable actionable principle each, no overlap, fewer and sharper, each with a "what does NOT belong" sentence) from a seeded random sample of up to 700 core claims, with a last group "None of these". Then assign each core claim strictly by what the claim itself says; when unsure use None. Only core types (principle, decision_rule, mental_model, mistake) are grouped. Method steps, examples, details and filler stay out and go to `supporting_claims.csv`. Assigning from the idea label alone was tried and was poor, so it is not a step.
4. Read and fix the groups yourself (free, no model call). Read every group page and 6 random core claims per group. Drop a group whose claims do not match its title (its claims go to None), merge overlapping groups, rename generic or misleading titles, and write the result as `merge.json`: `{"drop": ["G1"], "merge": {"G8": {"from": ["G8","G16"], "title": "...", "statement": "..."}}, "rename": {"G7": "New title"}}`. Then `merge` (renumbers G1..Gn, None last).
5. `overview`: one call per group from up to 30 sampled claims, principle first, one per video round robin. 3 to 4 plain sentences, last sentence "Caveat: ..." if the claims are tool-specific or disagree. Treat Caveat lines as hints: the model can invent a conflict between claims from different tools or videos. "the creator" becomes "the material".
6. `pages`: writes `principles/INDEX.md`, one page per group (title, statement, status line, overview, top claims, all grouped claims by video) and `supporting_claims.csv`. Every claim line ends with `(video ID, window, line Ln of videos/ID.md)` and its detail tag. Top claims are picked by rule (type priority, longer first, one per video, 40 to 300 characters, at most 8), not by quality, so a loose fit can appear: say so in the report.
7. `graph`: writes `graph/extraction.json` and `graph/coverage_manifest.json` for `graph_check.py`. Nodes: video, claim or principle (with file and line), principle group, one coverage node. Edges: claim to video `from_video` EXTRACTED (1.0); core claim to group `instance_of_group` INFERRED (0.5, basis stated). Group communities and the Graphify build follow the knowledge-graph step (section 14); this helper does not need Graphify.
8. `check`: count checks. Claims parsed equal claims in the groups file, each claim appears once, unlabeled count is reported, principles per video.
9. README gets a "start here" block (principle layer, group count, grouped and ungrouped core claims, claim-type counts, the honest limit). COVERAGE gets one line per pass (what, model, cost).

## Reporting and honest limits
- Fit spot check: 6 random core claims per group judged by a reviewer as fits or does not fit, reported with the numbers. Also report the share of core claims in no group, claims per group, the share from the top video per group and near duplicates. A same-author check is labelled so (SKILL.md section 4).
- Overview spot check: read every overview and verify named details and numbers against the claims.
- Known failure modes: catch-all groups absorb unrelated claims; tool tutorials give few real principles; the model replaces names and versions with ones from training (they stay tags); video download can be blocked so nothing can be checked against frames.
- Never label anything verified without a search verification run.

## Prompts
They are in `scripts/principle_layer.py` (P_TYPE, P_GROUPS, P_ASSIGN, P_OVERVIEW) and are the ones used on the two channels, with the creator wording made neutral.
