# Standing instructions and added knowledge

The skill reads this file at the start of every run (SKILL.md, section 0.3). It holds the owner's dated instructions and knowledge added to the method. Keep it public-safe: no names of private people, no credentials, no employer or client data, no personal contact details.

## How to add an entry

Append one entry at the end of the "Entries" list. Never edit or delete an old entry. To change a decision, add a new entry that says which date it replaces. Use this exact format:

```
### YYYY-MM-DD | instruction | <short title>
Instruction: <one or two sentences, in English, what the skill must do or avoid>.
Why: <the owner's reason, one sentence, or "not stated">.
Scope: <whole method | a section number | one run type>.
Replaces: <earlier entry date and title, or "none">.
```

Use `knowledge` instead of `instruction` for added information (a fact, a source or a method the skill should know). An entry is a standing preference. It does not approve spending, sending, sharing or other consequential actions, and it never overrides section 2 of SKILL.md.

After adding an entry, run `python3 adapters/build_adapters.py` to refresh the generated copies, then `python3 -m unittest discover -s tests`.

## Entries

### 2026-11-26 | instruction | Principles first
Instruction: Capture the creator's principles, reasoning, general knowledge and practical strategy first. Exact versions, names, prices and dates are low-weight detail tags, marked unreliable, and are never a reason to stop, ask or fail a check. Currency checks are not run unless the owner asks for a specific one.
Why: The goal of a channel run is the creator's way of thinking, not the exact state of a tool at recording time.
Scope: whole method.
Replaces: none.

### 2026-11-26 | instruction | Guest and channel-owner content count the same
Instruction: Do not treat knowledge differently by who says it. Content from a guest and content from the channel owner are equal. Do not mark guest content as less reliable and do not separate it into its own section or package. Keep the source video ID for every claim.
Why: The owner cares about the information and knowledge, not the people.
Scope: whole method, notes, indexes and graph.
Replaces: none.

### 2026-11-26 | instruction | Confirmed only after search verification
Instruction: Mark nothing as confirmed unless it was verified by a search with the Perplexity-based search skill the owner provided, using the free route. The owner will not verify by hand, the verifying agent must. Everything not verified stays labeled "unverified". Verification runs only under a plan the owner has seen (unit of checking, cost, time); the cost must be zero unless she approves otherwise.
Why: Information must be sound, and she does not want to check it herself.
Scope: whole method; applies to claims, detail tags and any status label.
Replaces: refines the 2026-11-26 "Principles first" entry on checks. Without a verification run, detail tags and claims stay "unverified"; with one, only the verified ones may be labeled confirmed.

### 2026-11-26 | instruction | Verify facts only; opinions and advice stored as stated
Instruction: Only factual information is verified by search before it may be marked confirmed. Opinions, advice and personal choices are stored as stated in the channel and are not verified or marked either way. Keep the distinction between facts and opinions in the notes.
Why: Facts must be sound. Advice and choices are what the speaker said, and there is nothing to check.
Scope: whole method; narrows the "Confirmed only after search verification" entry to facts.
Replaces: refines the 2026-11-26 "Confirmed only after search verification" entry.

### 2026-11-26 | instruction | Add the principle layer steps
Instruction: Add the extra post-processing steps used on the first two channel runs (type and idea label per claim, strict principle groups, group overviews, a graph around the groups, count checks) as a standard step after the per-video notes: SKILL.md 7.12, references/principle-layer.md, scripts/principle_layer.py. Model, prices and spend cap are not defaulted; the owner decides them before any model call.
Why: The owner asked on 2026-11-26 for these extra steps to be added to the plugin.
Scope: whole method, after the per-video notes.
Replaces: none.

### 2026-11-26 | instruction | Corrections and completions beside verified facts
Instruction: When a search verification finds a fact contradicted, add the correction beside it. When it finds the fact partly right, complete the missing information. Do this automatically, with no review step. Keep the original claim exactly as said in the video. Put the correction or completion in a separate line with its sources and the access date.
Why: The owner wants the knowledge to be right without checking it by hand, and the original wording stays traceable.
Scope: whole method; applies to every fact that goes through a search verification run.
Replaces: none. Applies on top of the "Verify facts only" entry.
