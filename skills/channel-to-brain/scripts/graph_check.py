#!/usr/bin/env python3
"""Structure checks for a Channel to Brain knowledge-graph extraction or Graphify graph.json.
Standard library only, no network.

Usage: python3 graph_check.py extraction.json [--manifest coverage_manifest.json]
Accepts a top-level object with "nodes" and either "edges" (extraction input) or "links" (graph.json).
Exit 0 when every check passes, 1 otherwise. Prints a JSON summary. This checks structure only: it
cannot tell whether a claim is right.
"""
import argparse, json, math, sys

CONF = ("EXTRACTED", "INFERRED", "AMBIGUOUS")
LINK_RELATIONS = ("from_video", "references")


def _s(v):
    return isinstance(v, str) and v.strip() != ""


def _score_ok(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 0 <= v <= 1


def check(data, manifest=None):
    problems = []
    if not isinstance(data, dict):
        return {"ok": False, "problems": ["root must be a JSON object"], "counts": {}}
    nodes = data.get("nodes")
    edges = data.get("edges", data.get("links"))
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return {"ok": False, "problems": ["file needs a nodes list and an edges (or links) list"], "counts": {}}
    ids = {}
    for n in nodes:
        i = n.get("id") if isinstance(n, dict) else None
        if not _s(i):
            problems.append("node that is not an object with a string id")
            continue
        if i in ids:
            problems.append("duplicate node id: " + i)
        ids[i] = n
    linked = set()
    conf_count = {}
    for idx, e in enumerate(edges):
        if not isinstance(e, dict):
            problems.append("edge %d is not an object" % idx)
            continue
        s, t = e.get("source"), e.get("target")
        if not (_s(s) and _s(t)) or s not in ids or t not in ids:
            problems.append("dangling or malformed edge %d: %r -> %r" % (idx, s, t))
            continue
        name = "%s -> %s" % (s, t)
        c = e.get("confidence")
        if not (isinstance(c, str) and c in CONF):
            problems.append("bad confidence on edge %s: %r" % (name, c))
        else:
            conf_count[c] = conf_count.get(c, 0) + 1
        if not _score_ok(e.get("confidence_score")):
            problems.append("confidence_score must be a finite number from 0 to 1 on edge " + name)
        if not (_s(e.get("source_file")) and _s(e.get("source_location"))):
            problems.append("edge without source_file and source_location: " + name)
        if c in ("INFERRED", "AMBIGUOUS") and not _s(e.get("basis")):
            problems.append("%s edge without basis: %s" % (c, name))
        if e.get("relation") in LINK_RELATIONS:
            a, b = ids[s], ids[t]
            for v, other in ((s, b), (t, a)):
                if ids[v].get("kind") == "video" and other.get("kind") == "claim":
                    linked.add(v)
    for i, n in ids.items():
        k = n.get("kind")
        if k == "claim" and not (_s(n.get("source_file")) and _s(n.get("source_location"))):
            problems.append("claim without source_file and source_location: " + i)
        if k == "video" and i not in linked:
            problems.append("video with no linked claim: " + i)
    # Coverage evidence is a coverage node, or a manifest that labels every source file (checked below).
    if manifest is None and not any(n.get("kind") == "coverage" for n in ids.values()):
        problems.append("no coverage node and no manifest")
    if manifest is not None:
        if not isinstance(manifest, dict):
            problems.append("manifest must be a JSON object keyed by source file")
        else:
            files = {n.get("source_file") for n in ids.values() if n.get("kind") in ("claim", "video")}
            for f in sorted(x for x in files if _s(x)):
                m = manifest.get(f)
                if not isinstance(m, dict) or not _s(m.get("mode")):
                    problems.append("source file not labelled with a mode in the manifest: " + f)
    counts = {"nodes": len(ids), "edges": len(edges), "confidence": conf_count}
    return {"ok": not problems, "problems": problems, "counts": counts}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("extraction")
    ap.add_argument("--manifest")
    a = ap.parse_args(argv)
    try:
        with open(a.extraction, encoding="utf-8") as f:
            data = json.load(f)
        manifest = None
        if a.manifest:
            with open(a.manifest, encoding="utf-8") as f:
                manifest = json.load(f)
    except (OSError, ValueError) as ex:
        print(json.dumps({"ok": False, "problems": ["cannot read input: %s" % ex]}))
        return 1
    res = check(data, manifest)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
