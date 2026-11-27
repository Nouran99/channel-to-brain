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

### 2026-11-26 | instruction | No live model run without the owner's approval each time
Instruction: Any live model run (any call that can cost money) needs the owner's approval every time. An earlier approval does not carry over to the next run. Keep it that way as the standing rule.
Why: She wants control over every spend. It confirms her answer to the question whether live runs need approval each time ("keep it always like that").
Scope: whole method; applies to every step that calls a model, including the principle layer and any verification mode that costs money.
Replaces: none. Applies on top of the no-defaults rule for model, prices and spend cap.

### 2026-11-26 | instruction | Ship the search verification skill inside the plugin
Instruction: Include the search skill used for verification inside the plugin (references/deep-research-skill.md, free native mode), so a new user can run the verification step without anything from the owner's Drive.
Why: The verification flow was not runnable from the repo alone.
Scope: verification step (SKILL.md 7.8, references/verification.md).
Replaces: none.


### 2026-11-27 | instruction | Add resources from video descriptions automatically
Instruction: Any resource available in a video description (guides, newsletter, workshop material, public pages) is added to the package automatically, as a default step of the pipeline. Keep the no-credentials check: one newsletter file once exposed login data, so strip or exclude any secret before saving.
Why: The owner wants the package to include the creator's own written material, not only video speech.
Scope: every channel run; first applied to the Selim package. Resources stay local until the owner approves the package.
Replaces: none.

### 2026-11-27 | instruction | Topic synthesis layer is a default core step
Instruction: Build a topic-organised synthesis layer on top of the principles from the existing claims, by reading and writing, with no live model run. Keep every claim traceable to its video ID and keep verification tags beside facts. Make it a default core step of the plugin.
Why: The old package answered topic questions better; the owner wants the new one organised by topic.
Scope: every channel run; first applied to the Selim package.
Replaces: none.

### 2026-11-27 | instruction | Design principle: knowledge for decisions outside the channel
Instruction: The goal is to use the channel's knowledge for decisions that are not part of the channel, by understanding the creator's way of thinking and decision mechanisms. Linking the content together, like a neural network, is more important than transcribing it.
Why: The owner wants a working model of how the creator thinks and decides, not a copy of the content.
Scope: every channel run and how packages are judged; recorded in SKILL.md section 1.
Replaces: none. It refines the earlier principles-first goal.

### 2026-11-27 | instruction | Add every step that proves effective
Instruction: Any extra step that proves effective must be added to Channel to Brain, so the final goal is reached: links that help use the knowledge for thinking, inference and decision-making. Each step is added with its measured result, where effective means shown by the decision-transfer test.
Why: The plugin should keep improving toward decisions outside the channel.
Scope: every channel run; recorded in SKILL.md section 1.
Replaces: none.

### 2026-11-27 | instruction | Cards and links are done by the agent, not by a paid API call
Instruction: Steps 2 and 3 (decision cards and links between them) are done by the agent itself that runs the plugin (Instinct, Claude, OpenAI or any agent), not by a paid API call.
Why: The owner does not want per-run model cost for work the running agent can do.
Scope: every channel run, link-layer steps.
Replaces: none.

### 2026-11-27 | instruction | The Gemini API key is for content extraction analysis only
Instruction: The Gemini API key is used only for content extraction analysis, which means reading the videos. It is not used for cards, links, grouping or scoring. This is a general rule.
Why: Keeps paid model use limited to the one step that needs a video-reading model.
Scope: every channel run.
Replaces: none.
