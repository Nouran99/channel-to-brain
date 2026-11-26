# Creator resources (default step)

Owner's standing rule (2026-11-27): every resource that is available through a video description is added to the package automatically. It is a default step of the pipeline, not an optional extra.

## What counts
Anything the creator published and links from a video description or from pages those descriptions link to: free guides and PDFs, newsletter posts, workshop slides, prompt files, public documents, public pages. Paid course content is not included. Private groups and chats are not included.

## Steps
1. Collect: during inventory (SKILL.md 7.1 and 7.3) save every link found in each description with its video ID in the links index. Do not open shortlinks blindly; resolve them through an allowed tool or leave them listed as unresolved.
2. Fetch: read each public resource through an allowed route. A resource that needs a login, a payment or a permission the user has not given is listed as not read, with the reason. Never sign in with someone's credentials to read a resource.
3. Note: write notes in the same style as video notes, in `resources/` (the creator's own wording in short excerpts or paraphrase, not whole files). Keep counts honest: pages, posts, files read and not read.
4. Secret check (required before anything is saved to the package): run `scripts/resource_scan.py resources/`. It reports emails, phone numbers, API keys, private keys, credential-style lines, URLs with credentials, session or cookie lines and long tokens, without printing the values. Strip each finding or exclude the file, then run it again until it prints "clean". Names and phone numbers of commenters and private contacts are left out. One newsletter file once exposed login data, so this check is never skipped. A file that cannot be read as text is excluded or converted first.
5. Currency: dated claims in guides (model names, prices, features) get the same fact check as video claims (SKILL.md 7.8). Until checked they carry the CHECK flag.
6. Report: list in the README and COVERAGE what was added, what was not read and why, and that resource claims are not covered by the video-note search tags unless they carry one.
7. Local first: resources stay in the local package until the owner approves the package. No upload before that.

## Limits to state
- Notes are not the raw files.
- The graph and claim counts may not include resources unless the graph step was re-run after adding them.
- Links in descriptions can be dead, renamed or changed.
