# Efficiency and review rules (per stage)

Added 2026-11-27 at the owner's request. Rules A and A2 are standing rules and are in SKILL.md (sections 1, 3 and 7.11). The per-stage suggestions in B are reasoning only. None is measured. Keep a suggestion only after an approved run shows it helps, and record the result next to it.

## A. Subagents and a reviewer on every task
See SKILL.md 7.11, rules 11 to 14. In short: fresh context per worker, a reviewer with fresh context on every task, local checks first then the client's own model, one fix round, then ask the user. Quality matters more than cost.

## A2. When the Gemini API may be used
Only when YouTube data is needed, and only with the user's approval each time. Everything else runs on the client's normal quota.

## B. Suggestions per stage (reasoning only, none measured)

### 1 Setup
- Cache the "missing public skills" check result in the work folder so later runs and stages do not re-read skill lists.

### 2 Collect (free tier)
- Captions first. The audio model only for videos with no captions (already the design).
- Use the ctb.py ranking to spend the free quota on the highest knowledge-value videos first. Skip Shorts and very short, low-value videos before any model call.
- Frames every 5 s are the largest token cost. Send a frame only when it differs from the previous one (local ffmpeg or hash check, no model). Skip talking-head stretches. Keep slides and screens.
- Ask for short structured output (JSON fields: quote, timestamp) instead of prose summaries.
- Keep the resume log per video ID, and add segment-level resume for partial videos so a 503 does not repeat finished segments.
- On 503s, wait and ask before any retry or model switch (owner rule).

### 3 Analysis roles
- Each role gets only its slice (one video's notes). The reviewer gets claims and sources only.
- The reviewer runs the local checks first (ctb.py check, quote match) and sends only failures to a model. This also catches wrong names and years.

### 4 Verify against current sources
- Verify only claims that can go stale: versions, model names, prices, tools, years. Skip timeless method claims.
- Official source first, one fetch per entity, cached in a file so the same tool is not re-checked per video.
- Keep "said in YEAR" separate from "current".

### 5 Cards, links, merge
- Keep the older cards next to the new ones (already approved). Dedupe by id and quote check, do not regenerate cards.
- Do not re-extract cards from videos that already have checked cards.
- Do merge and trust labels with local scripts where possible (id match, near-duplicate text). Use a model only for real conflicts. Where creators give no tie-breaker, the merge says so.

### 6 Knowledge graph
- Run with no model backend, as in the pilot. Run graph_check.py before use. Build the graph from cards and links, not raw notes.
- Rebuild only changed videos if the tool supports it. Unverified, check first.

### 7 Private repo and pack
- Log per video ID (already).
- Put a short index file first and keep cards as small files, so a client loads only the cards a question needs.

### Question time (clients)
- Retrieve top cards by tags and links instead of loading the whole pack. The answer cites card ids so a wrong answer can be traced.

### Priority if only three
1. Frame dedupe and structured output (stage 2).
2. Local checks before any model (stages 3 and 5).
3. Small indexed cards (stage 7).

## C. Not verified
- How much each suggestion saves. A measurement needs a model run on a sample, which needs the owner's approval each time.
- Whether fresh-context subagents and a reviewer on every task cost more tokens in total. Owner decision: quality matters more than cost, so the reviewer runs on every task.
