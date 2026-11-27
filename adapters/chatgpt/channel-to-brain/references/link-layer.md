# Link layer (experimental step 7.15)

Status: experimental, run when the owner asks for it. Added at the owner's request on 2026-11-27 with its measured numbers. It does not replace the principle layer or the topic synthesis layer.

## What it is
Decision cards and typed links between them, so knowledge from a channel can be used for decisions outside the channel (SKILL.md section 1, design principle). Linking matters more than transcribing.

- A card is one decision unit with fields: situation, condition, action, reason, exception. Every field the card fills is copied or closely paraphrased from a claim, with the video ID and the time. Empty fields stay empty.
- A link joins two cards: supports, requires, refines, applies-when, pulls-against, same-as. A pulls-against link shows a contradiction instead of hiding it.
- Who does the work: the agent that runs the plugin writes the cards and links. It is not a paid API call (owner rule, 2026-11-27, instructions log). The Gemini key stays for reading videos only.

## Steps
1. Run after the principle layer (7.12) and the topic synthesis (7.14).
2. `python3 scripts/link_layer.py select <package> cand.json` picks candidate claims. No model call.
3. The agent writes `cards.jsonl` and `edges.jsonl` from the candidates.
4. `python3 scripts/link_layer.py check <package> cards.jsonl edges.jsonl` checks that every card and link points to a real claim and that fields are traceable.
5. Optional: `situation` runs the decision-path check on a scenarios file, `stability` compares two independent link passes.
6. Keep the layer labelled UNVERIFIED like its source claims. Do not write cards from test scenarios.

## Measured results (first use, Selim package, 2026-11-27)
- Size: 111 cards, 59 links.
- Retrieval test on 100 scenarios, the right source in the top 5: old package 66%, cards 67%, cards plus links 75%. The gain comes from the links.
- Decision pilot on 25 dev scenarios: option match was 100% in all three conditions, so it is saturated and shows nothing. Point coverage (reasoning points found) was 80%, 82% and 86% for old, cards, cards plus links. Small gain, one run.
- The dev scenarios were written from the old notes, so they cannot reward a more accurate extraction. The test half stays locked and is run once at the end.

## Limits
- One package, one run, small differences. Treat 86 versus 80 as a hint, not a proof.
- Cards from auto captions inherit caption errors; unclear numbers must be flagged.
- The agent's judgement picks the links; the stability check shows how much two passes agree.
