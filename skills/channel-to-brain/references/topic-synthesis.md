# Topic synthesis layer (default core step)

Owner's standing instruction (2026-11-27): the package carries a topic-organised synthesis layer built from the existing claims. Reason: a retest on 300 generic questions showed that people ask by topic, while the per-video notes and the principle groups are organised by video and by idea.

## What it is
A folder `synthesis/` with `INDEX.md` and one file per area. Each area has topics; each topic lists claims by type (method steps, decision rules, principles, mental models, mistakes, a few examples). Every line is copied unchanged from a video note with its video ID. Verification tags and detail tags stay on the line. Nothing is rewritten, nothing is added, so nothing in it is more reliable than its source line.

## Steps
1. Run after the principle layer and the resources step (SKILL.md 7.12 and 7.13), before the graph step.
2. Write the topic map from the subject of the channel (a general map of the field, 3 areas of about 12 topics, each topic with 5 to 15 keywords). Do not write it from test questions or their key points. Save it as `topics.json` in the work folder: `{"Area": {"Topic": ["keyword", ...]}}`.
3. Run `scripts/topic_synthesis.py <package> topics.json`. No model call and no cost.
4. Read `synthesis/INDEX.md` and a sample of topics. Fix keywords that pull in unrelated lines or miss obvious ones, then run again.
5. List the layer in the README and COVERAGE with its limits. Keep `synthesis/INDEX.md` out of search tests, because it only repeats topic names.
6. Re-run the graph step if the graph should include the layer.

## What it did (first use, Selim package, 2026-11-27)
On 300 generic questions it moved the new package from 26.4 to 27.2 percent of key points (60 questions read), against 31.7 for the older package. The layer re-groups claims the package already had, so it can improve finding, not coverage. Expect a small gain. State this when reporting.

## Limits
- Keyword selection, not meaning.
- Topics overlap, and a line can sit at the edge of a topic.
- Claim types come from a model labelling pass and are unverified.
- The layer holds no new knowledge.
