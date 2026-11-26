#!/usr/bin/env python3
"""Principle layer for Channel to Brain: runs after the per-video notes exist.
Standard library only. Nothing is hardcoded per channel: package folder, work folder, model and prices
come from arguments or a config file. There is no default model, key, price or spend cap.

Steps (SKILL.md section 7.12, references/principle-layer.md):
  claims   parse spoken claims from <pkg>/videos/*.md        (free)
  type     model pass 1: type and idea label per claim       (model call, capped, stops on first error)
  parse    read the pass 1 responses into claims_typed.json  (free)
  groups   model pass 2: propose sharp groups from a sample, then assign core claims strictly (model call)
  merge    apply an edited merge.json (drop, merge, rename, renumber) after a human-style read (free)
  overview model pass 3: one short overview per group (model call)
  pages    write principles/INDEX.md, group pages and supporting_claims.csv (free)
  graph    write graph/extraction.json and coverage manifest for graph_check.py (free)
  check    count checks (free)
Model config JSON: {"endpoint": "https://.../{model}:generateContent", "model": "...", "key_env_name": "ENV_NAME",
 "price_in_per_m": 0.0, "price_out_per_m": 0.0, "hard_cap_usd": 0.0, "temperature": 0.1,
 "auth_header": "x-goog-api-key"}  (auth_header is optional; example file: references/model-config.example.json)
The key is read from the named environment variable only and is never printed or saved.
Every output is labelled UNVERIFIED unless a search verification run (SKILL.md 7.8) says otherwise.
"""
import argparse, collections, csv, glob, json, os, random, re, sys, urllib.error, urllib.request

TYPES = ("principle", "decision_rule", "method_step", "mistake", "mental_model", "example_story", "detail", "filler")
CORE = ("principle", "decision_rule", "mental_model", "mistake")
PRIORITY = {t: i for i, t in enumerate(CORE)}
LABEL = {"principle": "Principle", "decision_rule": "Decision rule", "mental_model": "Mental model",
         "mistake": "Mistake to avoid", "method_step": "Method step", "example_story": "Example or story"}
CHUNK = 150

P_TYPE = ("You get numbered claims from one YouTube video (claims are English notes made by a model). For EVERY claim return one line: number|type|label\n"
          "type is exactly one of: principle, decision_rule, method_step, mistake, mental_model, example_story, detail, filler.\n"
          "- principle: a general truth or belief about how things work or what matters\n"
          "- decision_rule: an if/then or \"do X not Y\" rule for choosing or acting\n"
          "- method_step: a step, tactic or procedure someone can follow\n"
          "- mistake: a mistake or trap to avoid\n"
          "- mental_model: a way of thinking, framing or analogy\n"
          "- example_story: a personal story, case or example that illustrates something\n"
          "- detail: a specific tool, product, version, price, number or setting with no general lesson\n"
          "- filler: greeting, plug, intro, outro, nothing of substance\n"
          "label: 3 to 7 English words naming the underlying idea (for example \"consistency beats motivation\"). Use the SAME label for claims about the same idea in this video. Do not invent content. Output only the lines, nothing else.")
P_GROUPS = ("Below are claims from {n} YouTube videos ({desc}). Each is a principle, decision rule, mental model or mistake as noted by a model. Propose {k} SHARP principle groups. "
            "Rules: each group is one specific, reusable, actionable principle a learner could apply anywhere (good: \"Validate demand before building\"; bad: \"Marketing\" or \"Tools and workflows\"). "
            "Groups must not overlap. Prefer fewer, sharper groups over many vague ones. Output only lines: G<number>|group title (3 to 8 words)|one sentence stating the principle|one short sentence saying what does NOT belong. "
            "Last line: G{k1}|None of these|Claims that are tool-specific steps, settings or facts with no general principle.\nClaims (type: claim):\n{items}")
P_ASSIGN = ("Assign each numbered claim to the ONE group whose principle it clearly states or directly illustrates. If it is only a tool-specific step, setting, fact, personal remark or something that fits no group well, use the last group (None). "
            "Be strict: when unsure, use None. Groups:\n{groups}\nOutput only lines: id|G<number>. Every id must appear once.\nClaims (id|type|claim):\n{items}")
P_OVERVIEW = ("Below are claims that a model noted from YouTube videos ({desc}). They are grouped under the principle \"{title}\" ({stmt}). "
              "Write a reader overview of 3 to 4 plain sentences: what the material advises in this group, the reasoning behind it, and how to apply it in practice. "
              "Use only the claims below, invent nothing, ignore exact versions, prices and dates. If the claims are mostly tool-specific or disagree, say so in one last sentence starting \"Caveat:\". No bullet points, no markdown.\nClaims:\n{items}")


def die(msg, code=2):
    print(msg, file=sys.stderr)
    sys.exit(code)


def rj(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def wj(p, d):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)


def clean(t):
    """Strip a leading timestamp tag and replace long dashes."""
    t = re.sub(r"^~?\(?\d{1,2}:\d{2}(\s*-\s*\d{1,2}:\d{2})?\)?\s*[-:]?\s*", "", t.strip())
    return t.replace("\u2014", " - ").replace("\u2013", "-")


# ---------- free steps ----------
def parse_claims(pkg):
    out = []
    for f in sorted(glob.glob(os.path.join(pkg, "videos", "*.md"))):
        vid = os.path.basename(f)[:-3]
        L = open(f, encoding="utf-8").read().split("\n")
        sec = win = None
        onscr = False
        title = L[0].lstrip("# ").strip() if L else vid
        n = 0
        claims = []
        for i, l in enumerate(L, 1):
            if l.startswith("## "):
                sec = l
            m = re.match(r"### Window (\S+)", l)
            if m:
                win, onscr = m.group(1), False
            if l.startswith("**On screen"):
                onscr = True
            if sec and "Spoken" in sec and win and not onscr and l.strip() and not l.startswith(("#", "**", "_No spoken")):
                t = l[2:] if l.startswith("- ") else l
                t = re.sub(r"\s+\[details unreliable:.*\]\s*$", "", t)
                t = re.sub(r"^~\d{1,2}:\d{2}\s*", "", t).strip()
                n += 1
                claims.append({"n": n, "win": win, "line": i, "text": t})
        out.append({"video": vid, "title": title, "file": "videos/%s.md" % vid, "claims": claims})
    return out


def parse_lines(text, ncols):
    for ln in text.split("\n"):
        p = [x.strip() for x in ln.strip().split("|")]
        if len(p) >= ncols and p[0].rstrip(".").isdigit():
            yield p


def parse_typed(videos, resp_dir):
    rows, missing = [], 0
    for v in videos:
        lab = {}
        for f in glob.glob(os.path.join(resp_dir, "%s__*.json" % v["video"])):
            for p in parse_lines(rj(f)["text"], 3):
                if p[1].lower() in TYPES:
                    lab[int(p[0].rstrip("."))] = (p[1].lower(), "|".join(p[2:]))
        for c in v["claims"]:
            t, l = lab.get(c["n"], ("unlabeled", "unlabeled"))
            missing += t == "unlabeled"
            rows.append({"video": v["video"], "title": v["title"], "file": v["file"], "n": c["n"], "win": c["win"],
                         "line": c["line"], "text": c["text"], "type": t, "label": l})
    return rows, missing


def parse_groups(text):
    G = {}
    for ln in text.split("\n"):
        p = [x.strip() for x in ln.strip().split("|")]
        if len(p) >= 3 and re.match(r"G\d+$", p[0]):
            G[p[0]] = [p[1], p[2]]
    return G


def apply_merge(data, cfg):
    """cfg: {"drop": ["G1"], "merge": {"G8": {"from": ["G8","G16"], "title": "...", "statement": "..."}}, "rename": {"G7": "New title"}}.
    Dropped groups go to None. Groups are renumbered G1..Gn with None last. Overviews are cleared for changed groups."""
    G, R, none = data["groups"], data["claims"], data["none"]
    remap = {}
    for new, m in (cfg.get("merge") or {}).items():
        for o in m["from"]:
            remap[o] = new
    drop = set(cfg.get("drop") or [])
    for r in R:
        r["group_before_merge"] = r["group"]
        if r["group"] in drop:
            r["group"] = none
        elif r["group"] in remap:
            r["group"] = remap[r["group"]]
    NG = {}
    for g, v in G.items():
        if g in drop or (g in remap and remap[g] != g):
            continue
        t, s = v[0], v[1]
        if g in (cfg.get("merge") or {}):
            t, s = cfg["merge"][g]["title"], cfg["merge"][g]["statement"]
        if g in (cfg.get("rename") or {}):
            t = cfg["rename"][g]
        NG[g] = [t, s]
    ids = [g for g in NG if g != none]
    mp = {g: "G%d" % (i + 1) for i, g in enumerate(ids)}
    mp[none] = "G%d" % (len(ids) + 1)
    for r in R:
        r["group"] = mp.get(r["group"], r["group"])
    return {"groups": {mp[g]: v for g, v in NG.items()}, "claims": R, "none": mp[none]}


def group_rows(data):
    by = collections.defaultdict(list)
    for r in data["claims"]:
        if r["group"] in data["groups"] and r["group"] != data["none"]:
            by[r["group"]].append(r)
    return by


def top_claims(rows, limit=8):
    rs = sorted(rows, key=lambda r: (PRIORITY.get(r["type"], 9), -min(len(r["text"]), 200)))
    seen, out = set(), []
    for r in rs:
        if r["video"] in seen or not 40 <= len(clean(r["text"])) <= 300:
            continue
        seen.add(r["video"])
        out.append(r)
        if len(out) >= limit:
            break
    return out


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50]


def tag_of(pkg, r, cache):
    f = os.path.join(pkg, r["file"])
    if f not in cache:
        cache[f] = open(f, encoding="utf-8").read().split("\n")
    try:
        m = re.search(r"(\[details unreliable:.*\])\s*$", cache[f][r["line"] - 1])
    except IndexError:
        m = None
    return ("  " + m.group(1)) if m else ""


def cite(r):
    return "(video %s, window %s, line L%d of %s)" % (r["video"], r["win"], r["line"], r["file"])


def build_pages(pkg, data, spot):
    out = os.path.join(pkg, "principles")
    os.makedirs(out, exist_ok=True)
    for f in glob.glob(os.path.join(out, "*.md")):
        os.remove(f)
    G, R, none = data["groups"], data["claims"], data["none"]
    by = group_rows(data)
    cache = {}
    idx = ["# Principles and strategy layer (UNVERIFIED, model-grouped)", "",
           "Principle-first view of the material. Each group page starts with a short model-written overview, then the top claims, then every grouped claim by video. "
           "Group titles, assignments and overviews are model judgement on model-written notes, a second unverified layer. Spot check: %s. Open the cited video note to check any line." % spot,
           "Exact versions, names, prices and dates are low-weight tags, never a reason to doubt the principle. Only core claims (principle, decision rule, mental model, mistake) are grouped, and only if they clearly fit. "
           "Everything else is in supporting_claims.csv. All claims count the same whoever says them; the video ID keeps each one traceable.", "",
           "| Group | Title | Principle statement | Claims | Videos |", "|---|---|---|---|---|"]
    order = sorted(by, key=lambda g: -len(by[g]))
    for g in order:
        rows = by[g]
        core = [r for r in rows if r["type"] in CORE]
        idx.append("| [%s](%s-%s.md) | %s | %s | %d | %d |" % (g, g, slug(G[g][0]), clean(G[g][0]), clean(G[g][1]), len(rows), len({r["video"] for r in rows})))
        L = ["# %s: %s" % (g, clean(G[g][0])), "", clean(G[g][1]), "",
             "Status: UNVERIFIED. Group assignment is by a model; the claims are model notes from video windows.", ""]
        if len(G[g]) > 2:
            L += ["## Overview (model-written, UNVERIFIED)", "", G[g][2], ""]
        L += ["## Top claims (up to 8, clearest type first, one per video)", ""]
        L += ["- %s %s%s" % (clean(r["text"]), cite(r), tag_of(pkg, r, cache)) for r in top_claims(rows)]
        L += ["", "## All grouped claims by video", ""]
        cur = None
        for r in sorted(core, key=lambda r: (r["video"], r["n"])):
            if r["video"] != cur:
                cur = r["video"]
                L += ["", "**%s** (%s)" % (clean(r["title"])[:90], cur)]
            L.append("- %s: %s (window %s, line L%d of %s)%s" % (LABEL[r["type"]], clean(r["text"]), r["win"], r["line"], r["file"], tag_of(pkg, r, cache)))
        with open(os.path.join(out, "%s-%s.md" % (g, slug(G[g][0]))), "w", encoding="utf-8") as f:
            f.write("\n".join(L) + "\n")
    with open(os.path.join(out, "INDEX.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(idx) + "\n")
    with open(os.path.join(pkg, "supporting_claims.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["video_id", "window", "type", "group", "claim", "source_file", "line"])
        for r in R:
            if r["group"] not in by:
                w.writerow([r["video"], r["win"], r["type"], "no group" if r["type"] in CORE else r["type"], clean(r["text"]), r["file"], r["line"]])
    return {"groups": len(order), "grouped": sum(len(v) for v in by.values())}


def build_graph(data, cov_text, pkg):
    """Writes nodes and edges for graph_check.py: video, claim, principle (group) and one coverage node.
    Claim to video: EXTRACTED. Claim to group: INFERRED (model assigned), with a stated basis. detail_tag nodes are not created."""
    G, R, none = data["groups"], data["claims"], data["none"]
    nodes, edges = [], []
    vids = {}
    for r in R:
        vids.setdefault(r["video"], r)
    for v, r in vids.items():
        nodes.append({"id": "v:" + v, "label": r["title"][:60], "kind": "video", "source_file": r["file"], "source_location": "L1",
                      "caveat": "UNVERIFIED model output"})
    used = ({r["group"] for r in R} & set(G)) - {none}
    for g, v in G.items():
        if g in used:
            nodes.append({"id": "g:" + g, "label": v[0], "kind": "concept", "source_file": "principles/INDEX.md", "source_location": "L1",
                          "full_text": v[1], "caveat": "model-made principle group, unverified"})
    for r in R:
        cid = "c:%s:%d" % (r["video"], r["n"])
        loc = "L%d" % r["line"]
        nodes.append({"id": cid, "label": clean(r["text"])[:70], "kind": "principle" if r["type"] in CORE else "claim", "stance": r["type"],
                      "source_file": r["file"], "source_location": loc, "caveat": "window %s; unverified" % r["win"]})
        edges.append({"source": cid, "target": "v:" + r["video"], "relation": "from_video", "confidence": "EXTRACTED", "confidence_score": 1.0,
                      "source_file": r["file"], "source_location": loc})
        if r["group"] in used:
            edges.append({"source": cid, "target": "g:" + r["group"], "relation": "instance_of_group", "confidence": "INFERRED", "confidence_score": 0.5,
                          "source_file": r["file"], "source_location": loc, "basis": "model assigned this claim to the group from its text; unverified"})
    nodes.append({"id": "coverage", "label": "Coverage and limits", "kind": "coverage", "source_file": "COVERAGE.md", "source_location": "L1", "full_text": cov_text})
    first = next(iter(vids))
    edges.append({"source": "coverage", "target": "v:" + first, "relation": "describes", "confidence": "INFERRED", "confidence_score": 0.3,
                  "source_file": "COVERAGE.md", "source_location": "L1", "basis": "package-level limits apply to every video"})
    man = {r["file"]: {"mode": "deterministic parse plus model labels, no human review"} for r in vids.values()}
    man["principles/INDEX.md"] = {"mode": "model-made principle groups, unverified"}
    man["COVERAGE.md"] = {"mode": "deterministic script (coverage text)"}
    return {"nodes": nodes, "edges": edges, "hyperedges": []}, man


def check(videos, data):
    """Count checks. Reports problems, never edits anything."""
    problems = []
    R = data["claims"]
    total = sum(len(v["claims"]) for v in videos)
    if len(R) != total:
        problems.append("claims in groups file %d, claims parsed from notes %d" % (len(R), total))
    keys = [(r["video"], r["n"]) for r in R]
    if len(keys) != len(set(keys)):
        problems.append("a claim appears more than once")
    unl = sum(1 for r in R if r["type"] == "unlabeled")
    by = group_rows(data)
    per_video = collections.Counter(r["video"] for g in by.values() for r in g)
    return {"ok": not problems, "problems": problems, "claims": len(R), "unlabeled": unl, "groups": len(by),
            "grouped": sum(len(v) for v in by.values()), "principles_per_video": dict(per_video)}


# ---------- model steps ----------
class Model:
    def __init__(self, cfgpath):
        c = rj(cfgpath)
        for k in ("endpoint", "model", "key_env_name", "price_in_per_m", "price_out_per_m", "hard_cap_usd"):
            if k not in c:
                die("model config needs %s (there are no defaults; the owner decides model, prices and cap)" % k)
        for k in ("endpoint", "model", "key_env_name"):
            if not isinstance(c[k], str) or not c[k].strip() or c[k].startswith("REPLACE"):
                die("model config field %s is empty or still the example placeholder" % k)
        if not c["endpoint"].startswith("https://"):
            die("endpoint must start with https://")
        if not (isinstance(c["hard_cap_usd"], (int, float)) and c["hard_cap_usd"] >= 0):
            die("hard_cap_usd must be a number, 0 or more")
        self.c = c
        self.key = os.environ.get(c["key_env_name"], "")
        if not self.key:
            die("environment variable %s is not set" % c["key_env_name"])
        self.spent = 0.0

    def __call__(self, prompt):
        if self.spent >= self.c["hard_cap_usd"]:
            die("STOP: spend cap reached (%.4f of %.4f). Ask the owner before continuing." % (self.spent, self.c["hard_cap_usd"]), 3)
        body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": self.c.get("temperature", 0.1)}}
        req = urllib.request.Request(self.c["endpoint"].format(model=self.c["model"]), data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", self.c.get("auth_header", "x-goog-api-key"): self.key})
        try:
            d = json.load(urllib.request.urlopen(req, timeout=300))
        except urllib.error.HTTPError as ex:
            die("STOP: HTTP %d. No retry. Report to the owner. %s" % (ex.code, ex.read().decode("utf8", "replace")[:120]), 3)
        except Exception as ex:
            die("STOP: %s. No retry. Report to the owner." % type(ex).__name__, 3)
        c = (d.get("candidates") or [{}])[0]
        text = "".join(p.get("text", "") for p in c.get("content", {}).get("parts", []))
        u = d.get("usageMetadata", {})
        self.spent += u.get("promptTokenCount", 0) * self.c["price_in_per_m"] / 1e6 + \
            (u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0)) * self.c["price_out_per_m"] / 1e6
        if c.get("finishReason") != "STOP" or not text:
            die("STOP: finish reason %s. No retry. Report to the owner." % c.get("finishReason"), 3)
        return text


def run_type(model, videos, resp_dir):
    os.makedirs(resp_dir, exist_ok=True)
    for v in videos:
        for ci in range(0, len(v["claims"]), CHUNK):
            f = os.path.join(resp_dir, "%s__%d.json" % (v["video"], ci // CHUNK))
            if os.path.exists(f):
                continue  # resumable: a saved success is never run again
            chunk = v["claims"][ci:ci + CHUNK]
            txt = "\n".join("%d. %s" % (c["n"], c["text"][:400]) for c in chunk)
            t = model(P_TYPE + "\n\nVideo title: " + v["title"] + "\n\nClaims:\n" + txt)
            wj(f, {"video": v["video"], "chunk": ci // CHUNK, "ns": [c["n"] for c in chunk], "text": t})
    return model.spent


def run_groups(model, rows, k, desc, seed, sample):
    core = [i for i, r in enumerate(rows) if r["type"] in CORE]
    random.seed(seed)
    samp = random.sample(core, min(sample, len(core)))
    t = model(P_GROUPS.format(n=len({r["video"] for r in rows}), desc=desc, k=k, k1=k + 1,
                              items="\n".join("%s: %s" % (rows[i]["type"], clean(rows[i]["text"])[:220]) for i in samp)))
    G = parse_groups(t)
    if len(G) < 2:
        die("STOP: could not read groups from the model answer. Report to the owner.", 3)
    none = list(G)[-1]
    gtxt = "\n".join("%s: %s - %s" % (g, v[0], v[1]) for g, v in G.items())
    out = {}
    for b in range(0, len(core), CHUNK):
        part = core[b:b + CHUNK]
        t = model(P_ASSIGN.format(groups=gtxt, items="\n".join("%d|%s|%s" % (i, rows[i]["type"], clean(rows[i]["text"])[:260]) for i in part)))
        for p in parse_lines(t, 2):
            if p[1] in G:
                out[int(p[0])] = p[1]
    cs = set(core)
    for i, r in enumerate(rows):
        r["group"] = (out.get(i) or none) if i in cs else ("support" if r["type"] in ("method_step", "example_story") else r["type"])
    return {"groups": G, "claims": rows, "none": none}


def run_overview(model, data, desc):
    by = group_rows(data)
    for g, rows in by.items():
        rs = sorted(rows, key=lambda r: (PRIORITY.get(r["type"], 9), -min(len(clean(r["text"])), 200)))
        seen, pick = collections.Counter(), []
        for rnd in range(3):
            for r in rs:
                if len(pick) < 30 and seen[r["video"]] == rnd and r not in pick and 40 <= len(clean(r["text"])) <= 400:
                    pick.append(r)
                    seen[r["video"]] += 1
        t = model(P_OVERVIEW.format(desc=desc, title=data["groups"][g][0], stmt=data["groups"][g][1],
                                    items="\n".join("- " + clean(r["text"])[:300] for r in pick)))
        t = t.strip().replace("\u2014", " - ").replace("the creator", "the material").replace("The creator", "The material")
        data["groups"][g] = data["groups"][g][:2] + [t]
    return model.spent


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["claims", "type", "parse", "groups", "merge", "overview", "pages", "graph", "check"])
    ap.add_argument("--pkg", required=True, help="package folder that holds videos/*.md")
    ap.add_argument("--work", required=True, help="work folder for json files and model responses")
    ap.add_argument("--model-config")
    ap.add_argument("--desc", default="one channel", help="short plain description of the channel topics")
    ap.add_argument("--groups", type=int, default=22, help="number of groups to ask for")
    ap.add_argument("--sample", type=int, default=700)
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--merge-file")
    ap.add_argument("--spot", default="not yet spot-checked")
    ap.add_argument("--coverage-text", default="Model-made layer over model-made notes. Unverified. See COVERAGE.md.")
    a = ap.parse_args(argv)
    W = lambda n: os.path.join(a.work, n)
    if a.step == "claims":
        v = parse_claims(a.pkg)
        wj(W("claims.json"), v)
        print(json.dumps({"videos": len(v), "claims": sum(len(x["claims"]) for x in v)}))
    elif a.step == "type":
        if not a.model_config:
            die("--model-config is required")
        m = Model(a.model_config)
        run_type(m, rj(W("claims.json")), W("out"))
        print(json.dumps({"spent_usd": round(m.spent, 4)}))
    elif a.step == "parse":
        rows, miss = parse_typed(rj(W("claims.json")), W("out"))
        wj(W("claims_typed.json"), rows)
        print(json.dumps({"claims": len(rows), "unlabeled": miss, "types": dict(collections.Counter(r["type"] for r in rows))}))
    elif a.step == "groups":
        if not a.model_config:
            die("--model-config is required")
        m = Model(a.model_config)
        d = run_groups(m, rj(W("claims_typed.json")), a.groups, a.desc, a.seed, a.sample)
        wj(W("grouped.json"), d)
        print(json.dumps({"groups": len(d["groups"]) - 1, "spent_usd": round(m.spent, 4)}))
    elif a.step == "merge":
        if not a.merge_file:
            die("--merge-file is required")
        d = apply_merge(rj(W("grouped.json")), rj(a.merge_file))
        wj(W("grouped_merged.json"), d)
        print(json.dumps({"groups": len(d["groups"]) - 1}))
    elif a.step == "overview":
        if not a.model_config:
            die("--model-config is required")
        m = Model(a.model_config)
        src = W("grouped_merged.json") if os.path.exists(W("grouped_merged.json")) else W("grouped.json")
        d = rj(src)
        run_overview(m, d, a.desc)
        wj(W("grouped_final.json"), d)
        print(json.dumps({"spent_usd": round(m.spent, 4)}))
    else:
        final = next((W(n) for n in ("grouped_final.json", "grouped_merged.json", "grouped.json") if os.path.exists(W(n))), None)
        if not final:
            die("no grouped file found in the work folder")
        d = rj(final)
        if a.step == "pages":
            print(json.dumps(build_pages(a.pkg, d, a.spot)))
        elif a.step == "graph":
            g, man = build_graph(d, a.coverage_text, a.pkg)
            wj(os.path.join(a.pkg, "graph", "extraction.json"), g)
            wj(os.path.join(a.pkg, "graph", "coverage_manifest.json"), man)
            print(json.dumps({"nodes": len(g["nodes"]), "edges": len(g["edges"])}))
        else:
            r = check(rj(W("claims.json")), d)
            print(json.dumps(r, indent=1))
            sys.exit(0 if r["ok"] else 1)


if __name__ == "__main__":
    main()
