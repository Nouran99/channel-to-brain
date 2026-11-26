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
