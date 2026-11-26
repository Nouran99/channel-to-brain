# Verification of facts (search verification)

Only facts are verified. Opinions, advice and personal choices are stored as stated in the channel and are not verified. Nothing is marked confirmed without a search verification run by the verifying agent, using the search skill the owner provides. The owner does not verify by hand. The search skill itself is not part of this repo: the owner supplies it (set it up before the first run).

## Rules
1. Make a plan first and show it to the owner: unit of checking (for example one fact per principle group), expected cost (zero unless the owner approves otherwise), and time. Do not run before the owner agrees to the plan.
2. Keep the original claim exactly as said in the video. Never rewrite it.
3. A contradicted fact gets the correction beside it. A partly right fact gets the missing information added. This is automatic, with no review step.
4. The search shows whether a statement is generally true. It does not show that the speaker said it. "Confirmed" means true in general, not "the video said it".
5. Claims that are religious rulings, opinions or advice are recorded as sources agree or differ, never as "confirmed".
6. Report weak spots honestly: a single source, vendor-only sources, a page that failed to fetch.

## Labels
CONFIRMED (at least two independent sources agree) / CONTRADICTED / PARTLY (right in part, with the missing part added) / NOT FOUND (no source found) / OPINION (not checked) / OUTDATED (was right at the time of the video, no longer).

## Tag format, beside the original claim
Each checked claim line keeps its text; a tag follows it:
`SEARCH-CHECK: <label>; unit: <what was checked>; accessed: YYYY-MM-DD; correction or completion: <text or none>; sources: <URL 1>, <URL 2>`
Put the tag in every place the claim appears (principle pages, theme pages, video notes). `supporting_claims.csv` gets a `verification` column with the label. Graph nodes of checked claims get the attributes `verification`, `verification_unit`, `verification_has_correction` (yes or no), `verification_correction`, `verification_accessed` and `verification_sources` (in graph.json and extraction.json). A viewer such as graph.html may not display them.

## Files
A `verification/` folder in the package, ordered worst first (CONTRADICTED, PARTLY, NOT FOUND, then CONFIRMED), one entry per checked unit with its sources. The package README says how many units were checked per label and what stays unverified.
