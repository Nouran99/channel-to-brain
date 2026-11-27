#!/usr/bin/env python3
"""Topic synthesis layer for Channel to Brain. Standard library only, no model call, no network.

Groups the existing claims of a package by topic so a question can be answered from one place.
Every line is a claim copied unchanged from a video note, with its video ID. Verification tags and
detail tags stay on the line. Nothing is rewritten and nothing is added.

Usage: topic_synthesis.py <package-folder> <topics.json>
topics.json: {"Area name": {"Topic name": ["keyword", ...], ...}, ...}
The topic map is a general subject map for the channel's field. Write it from the subject, not from
test questions. Input: <package>/supporting_claims.csv (columns video_id, type, line, source_file) and
<package>/videos/*.md. Output: <package>/synthesis/INDEX.md and one <AREA>.md per area."""
import collections
import csv
import json
import os
import re
import sys

ORDER = [("method_step", "Method steps"), ("decision_rule", "Decision rules"), ("principle", "Principles"),
         ("mental_model", "Mental models"), ("mistake", "Mistakes to avoid"), ("example", "Examples and stories")]
CAP = {"example": 3}
PER_TOPIC = 36
PER_TYPE = 12
PER_VIDEO = 5


def build(pkg, topics):
    rows = list(csv.DictReader(open(os.path.join(pkg, "supporting_claims.csv"), encoding="utf-8")))
    titles = {}
    for f in os.listdir(os.path.join(pkg, "videos")):
        if f.endswith(".md"):
            titles[f[:-3]] = open(os.path.join(pkg, "videos", f), encoding="utf-8").readline().strip("# \n").lower()
    cache = {}

    def line(r):
        p = os.path.join(pkg, r["source_file"])
        if p not in cache:
            cache[p] = open(p, encoding="utf-8").read().split("\n")
        return cache[p][int(r["line"]) - 1].lstrip("- ").strip()

    kinds = dict(ORDER)
    out_dir = os.path.join(pkg, "synthesis")
    os.makedirs(out_dir, exist_ok=True)
    index = ["# Topic synthesis", "",
             "A topic-organised view of the claims. Every line is a claim taken unchanged from a video note in videos/, with its video ID. "
             "Verification tags and detail tags stay on the line. Lines are selected by topic keywords and ordered by type, method steps first.", "",
             "Limits: selection is by keyword match, so a line can sit at the edge of a topic and some relevant lines can be missing. "
             "Topics overlap. Claim types and keywords are mechanical and unverified. Only lines with a SEARCH-CHECK tag are verified.", ""]
    stats = {}
    for area, tops in topics.items():
        doc = [f"# {area}: topic synthesis", "", "Format: claim text (video ID). Tags are kept from the video note.", ""]
        for name, kws in tops.items():
            kws = [k.lower() for k in kws]
            cand = []
            for r in rows:
                if r["type"] not in kinds:
                    continue
                t = line(r)
                tl = t.lower()
                h = sum(1 for k in kws if k in tl)
                if h == 0 or len(t) < 40:
                    continue
                cand.append((h + 0.5 * sum(1 for k in kws if k in titles.get(r["video_id"], "")), r, t))
            cand.sort(key=lambda x: -x[0])
            seen, pv, pick = set(), collections.Counter(), collections.defaultdict(list)
            for _sc, r, t in cand:
                t = re.sub(r"^~?\d[\d:]*\s*", "", t)
                key = re.sub(r"\W+", "", t.lower())[:80]
                ty = r["type"]
                if key in seen or pv[r["video_id"]] >= PER_VIDEO or len(pick[ty]) >= CAP.get(ty, PER_TYPE):
                    continue
                if sum(len(v) for v in pick.values()) >= PER_TOPIC:
                    break
                seen.add(key)
                pv[r["video_id"]] += 1
                pick[ty].append(f'- {t} ({r["video_id"]})')
            n = sum(len(v) for v in pick.values())
            stats[(area, name)] = n
            doc += [f"## {name}", "", f"Matching claims selected: {n} of {len(cand)} matches.", ""]
            for ty, lab in ORDER:
                if pick[ty]:
                    doc += [f"### {lab}", ""] + pick[ty] + [""]
        safe = re.sub(r"[^A-Z0-9]+", "_", area.upper()).strip("_")
        open(os.path.join(out_dir, safe + ".md"), "w", encoding="utf-8").write("\n".join(doc))
        index += [f"## {area}", f"File: synthesis/{safe}.md", ""] + [f"- {n} ({stats[(area, n)]} claims)" for n in tops] + [""]
    open(os.path.join(out_dir, "INDEX.md"), "w", encoding="utf-8").write("\n".join(index))
    return stats


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    stats = build(argv[0], json.load(open(argv[1], encoding="utf-8")))
    print(json.dumps({"topics": len(stats), "claims": sum(stats.values())}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
