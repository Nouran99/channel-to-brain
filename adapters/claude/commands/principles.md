---
description: Build the principle layer for a finished set of per-video notes (description only, runs nothing before the owner sees the plan and cost).
---
Follow section 7.12 of the channel-to-brain skill and `references/principle-layer.md` for the package folder given as the argument: $ARGUMENTS

Run the free `claims` step first and report the claim count per video. Then show the owner the plan: the steps, the model, its price and spend cap (the owner decides them, there are no defaults), the expected cost and the time. Do not make any model call before the owner agrees. Stop on the first API error and ask. Keep every claim as said, with its video ID. Everything the layer produces is unverified until a search verification run (references/verification.md).
