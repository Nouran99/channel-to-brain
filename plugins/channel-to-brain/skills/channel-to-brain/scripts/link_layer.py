#!/usr/bin/env python3
"""Link layer for Channel to Brain: decision cards, links, conflicts, decision paths.
Standard library only. No model call. The agent that runs the plugin writes cards and links
(see references/link-layer.md); this script selects candidates and checks the agent's work.

Usage:
  link_layer.py select <package> [out.json]
  link_layer.py check <package> <cards.jsonl> <edges.jsonl>
  link_layer.py situation <package> <cards.jsonl> <edges.jsonl> <scenarios.json>
  link_layer.py stability <package> <cards.jsonl> <edges_a.jsonl> <edges_b.jsonl>
"""
import collections
import json
import math
import os
import random
import re
import sys

EDGE_TYPES = ("supports", "requires", "refines", "applies-when", "pulls-against", "same-as")
CARD_FIELDS = ("situation", "condition", "action", "reason", "exception")
STOP = set("a an the and or of to in on for with is are be by as at from that this it its you your he his they their not no if then when can will would should must may do does so than too very more most one two three".split())


def tok(s):
    return [w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP and len(w) > 2]


def load_graph(pkg):
    return json.load(open(os.path.join(pkg, "graph", "extraction.json"), encoding="utf-8"))


def video_lines(pkg, vid):
    p = os.path.join(pkg, "videos", vid + ".md")
    return open(p, encoding="utf-8").read().split("\n") if os.path.exists(p) else None


def clean(t):
    t = re.sub(r"^\s*[-*]\s*", "", t)
    t = re.sub(r"^~?\d[\d:]*\s*", "", t)
    return t.strip()


def select(pkg):
    g = load_graph(pkg)
    groups = {n["id"]: n for n in g["nodes"] if n["kind"] == "concept"}
    claims = {n["id"]: n for n in g["nodes"] if n["kind"] == "claim"}
    grp = {}
    for e in g["edges"]:
        if e["relation"] == "instance_of_group":
            grp[e["source"]] = e["target"]
    out = []
    for cid, gid in grp.items():
        n = claims.get(cid)
        if not n or n["stance"] not in ("decision_rule", "mental_model", "mistake"):
            continue
        vid = cid.split(":")[1]
        ln = int(n["source_location"].lstrip("L"))
        L = video_lines(pkg, vid)
        text = clean(L[ln - 1]) if L and ln <= len(L) else n["label"]
        out.append({"id": cid, "type": n["stance"], "group": gid, "group_label": groups[gid]["label"], "video": vid, "line": ln, "text": text})
    out.sort(key=lambda x: (x["group"], x["video"], x["line"]))
    return out


def read_jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def check(pkg, cards, edges):
    errs, warn = [], []
    ids = {}
    for c in cards:
        if c.get("id") in ids:
            errs.append("duplicate card " + str(c.get("id")))
        ids[c.get("id")] = c
    nostate = collections.Counter()
    for c in cards:
        cid = c.get("id")
        if not c.get("action") or c["action"] == "not stated":
            errs.append(f"{cid}: card has no action")
        if not c.get("sources"):
            errs.append(f"{cid}: no sources")
        for f in CARD_FIELDS:
            if c.get(f, "not stated") == "not stated":
                nostate[f] += 1
        src_text = []
        for s in c.get("sources", []):
            L = video_lines(pkg, s.get("video", ""))
            if L is None or not (1 <= s.get("line", 0) <= len(L)):
                errs.append(f"{cid}: source {s} does not exist")
            else:
                src_text.append(L[s["line"] - 1])
        if src_text:
            st = set(tok(" ".join(src_text)))
            body = tok(" ".join(c.get(f, "") for f in CARD_FIELDS if c.get(f, "not stated") != "not stated"))
            cov = sum(1 for w in body if w in st) / max(1, len(body))
            if cov < 0.5:
                errs.append(f"{cid}: only {cov:.0%} of card words appear in the cited lines")
    cross = 0
    deg = collections.Counter()
    for i, e in enumerate(edges):
        eid = f"edge {i} {e.get('from')}->{e.get('to')}"
        if e.get("type") not in EDGE_TYPES:
            errs.append(f"{eid}: type {e.get('type')} not allowed")
        for k in ("from", "to"):
            if e.get(k) not in ids:
                errs.append(f"{eid}: {k} is not a card")
        ev = e.get("evidence", [])
        if len(ev) < 2:
            errs.append(f"{eid}: needs two source lines")
            continue
        vids = set()
        for s in ev[:2]:
            L = video_lines(pkg, s.get("video", ""))
            if L is None or not (1 <= s.get("line", 0) <= len(L)):
                errs.append(f"{eid}: evidence {s} does not exist")
            vids.add(s.get("video"))
        if e.get("from") in ids and e.get("to") in ids:
            a, b = ids[e["from"]], ids[e["to"]]
            sa = {(s["video"], s["line"]) for s in a.get("sources", [])}
            sb = {(s["video"], s["line"]) for s in b.get("sources", [])}
            e0 = (ev[0].get("video"), ev[0].get("line"))
            e1 = (ev[1].get("video"), ev[1].get("line"))
            if e0 not in sa and e0 not in sb:
                warn.append(f"{eid}: first evidence line is not a source of either card")
            if not e.get("reason"):
                errs.append(f"{eid}: no reason")
            if a.get("sources", [{}])[0].get("video") != b.get("sources", [{}])[0].get("video"):
                cross += 1
        deg[e.get("from")] += 1
        deg[e.get("to")] += 1
    return {"cards": len(cards), "edges": len(edges), "errors": errs, "warnings": warn[:5], "no_stated": dict(nostate),
            "cards_without_links": sum(1 for c in cards if deg[c["id"]] == 0), "cross_video_edges": cross,
            "edge_types": dict(collections.Counter(e.get("type") for e in edges))}


CHANNEL_WORDS = set("marketing marketer ads ad ai agency campaign campaigns seo social media client clients facebook google tiktok linkedin claude chatgpt gemini".split())


def bm25(docs, q, k=5):
    N = len(docs)
    df = collections.Counter(w for d in docs for w in set(d))
    avg = sum(len(d) for d in docs) / max(N, 1)
    sc = []
    for i, d in enumerate(docs):
        tf = collections.Counter(d)
        s = 0.0
        for w in set(q):
            if w in tf:
                idf = math.log(1 + (N - df[w] + 0.5) / (df[w] + 0.5))
                s += idf * tf[w] * 2.2 / (tf[w] + 1.2 * (0.25 + 0.75 * len(d) / avg))
        sc.append((s, i))
    sc.sort(key=lambda x: -x[0])
    return [i for s, i in sc[:k] if s > 0]


def gid(g):
    return g.split(":")[-1].split("-")[0].upper() if g else g


def situation(pkg, cards, edges, scen_path):
    """Retrieve by situation text with the channel's own keywords removed.
    Hit@k: a retrieved item belongs to one of the scenario's expected groups.
    Linked recall: expected groups covered by top-5 plus one-hop neighbours through edges.
    The old floor retrieves over every grouped claim line (the old package content, no cards, no links)."""
    scen = json.load(open(scen_path, encoding="utf-8"))
    g = load_graph(pkg)
    claims = {n["id"]: n for n in g["nodes"] if n["kind"] == "claim"}
    grp = {e["source"]: e["target"] for e in g["edges"] if e["relation"] == "instance_of_group"}
    old = []
    for cid, gg in grp.items():
        n = claims.get(cid)
        if not n:
            continue
        L = video_lines(pkg, cid.split(":")[1])
        ln = int(n["source_location"].lstrip("L"))
        t = clean(L[ln - 1]) if L and ln <= len(L) else n["label"]
        old.append((gid(gg), tok(t)))
    cdocs = [(gid(c["group"]), tok(" ".join(str(c.get(f, "")) for f in ("situation", "condition", "action", "reason")))) for c in cards]
    idx = {c["id"]: i for i, c in enumerate(cards)}
    nb = collections.defaultdict(set)
    for e in edges:
        if e["from"] in idx and e["to"] in idx:
            nb[idx[e["from"]]].add(idx[e["to"]])
            nb[idx[e["to"]]].add(idx[e["from"]])
    res = {"old": [0, 0, 0.0], "new": [0, 0, 0.0], "linked": [0, 0, 0.0]}
    for s in scen:
        want = set(s[3])
        q = [w for w in tok(s[2]) if w not in CHANNEL_WORDS]
        r_old = bm25([d for _, d in old], q, 5)
        r_new = bm25([d for _, d in cdocs], q, 5)
        for name, r, docs in (("old", r_old, old), ("new", r_new, cdocs)):
            if r and docs[r[0]][0] in want:
                res[name][0] += 1
            if any(docs[i][0] in want for i in r):
                res[name][1] += 1
            res[name][2] += len({docs[i][0] for i in r} & want) / len(want)
        exp = set(r_new)
        for i in r_new:
            exp |= nb[i]
        res["linked"][2] += len({cdocs[i][0] for i in exp} & want) / len(want)
        if any(cdocs[i][0] in want for i in exp):
            res["linked"][1] += 1
    n = len(scen)
    return {"scenarios": n, **{k: {"hit_at_1": v[0] / n, "hit_at_5": v[1] / n, "group_recall": round(v[2] / n, 3)} for k, v in res.items()}}


def stability(edges_a, edges_b):
    """Compare two independently written edge files: pair overlap and type agreement."""
    pa = {frozenset((e["from"], e["to"])): e["type"] for e in edges_a}
    pb = {frozenset((e["from"], e["to"])): e["type"] for e in edges_b}
    both = set(pa) & set(pb)
    return {"edges_a": len(pa), "edges_b": len(pb), "pair_overlap_jaccard": round(len(both) / max(len(set(pa) | set(pb)), 1), 3),
            "type_agreement_on_shared": round(sum(pa[k] == pb[k] for k in both) / max(len(both), 1), 3)}


def main(a):
    if len(a) < 2:
        print(__doc__)
        return 2
    cmd, pkg = a[0], a[1]
    if cmd == "select":
        c = select(pkg)
        if len(a) > 2:
            json.dump(c, open(a[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(json.dumps({"candidates": len(c), "by_type": dict(collections.Counter(x["type"] for x in c))}))
        return 0
    cards, edges = read_jsonl(a[2]), read_jsonl(a[3])
    if cmd == "check":
        r = check(pkg, cards, edges)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 1 if r["errors"] else 0
    if cmd == "situation":
        print(json.dumps(situation(pkg, cards, edges, a[4]), indent=1))
        return 0
    if cmd == "stability":
        print(json.dumps(stability(edges, read_jsonl(a[4])), indent=1))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
