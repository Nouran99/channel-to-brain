# Worked example (fictional data, mock model, no cost)

This shows what the principle layer produces. The two notes below are invented. The model answers came from a stand-in, not a real model, so the grouping is trivial. Real output is larger and still unverified.

## Input: `videos/demoAAA.md` (idea section on top, Spoken window block as the source record)
```
# Demo video A: Start with the audience

## Principles and strategy
- Name the audience before you write the task.

## Spoken
### Window 00:00-10:00
- ~01:05 Validate demand before you build anything, because building first wastes months. [details unreliable: ExampleBot 9.9]
- Set the cache size to 512 in the hosting panel.
- Hello and welcome to the channel.
```

## Commands (from the repo root, with the real work and package folders)
```
S=skills/channel-to-brain/scripts
python3 $S/principle_layer.py claims  --pkg PKG --work WORK
python3 $S/principle_layer.py type    --pkg PKG --work WORK --model-config model.json   # model call, capped
python3 $S/principle_layer.py parse   --pkg PKG --work WORK
python3 $S/principle_layer.py groups  --pkg PKG --work WORK --model-config model.json --desc "short topic description" --groups 22
# read the groups, write merge.json (drop, merge, rename), then:
python3 $S/principle_layer.py merge   --pkg PKG --work WORK --merge-file merge.json
python3 $S/principle_layer.py overview --pkg PKG --work WORK --model-config model.json --desc "short topic description"
python3 $S/principle_layer.py pages   --pkg PKG --work WORK
python3 $S/principle_layer.py graph    --pkg PKG --work WORK
python3 $S/principle_layer.py check    --pkg PKG --work WORK
python3 $S/graph_check.py PKG/graph/extraction.json --manifest PKG/graph/coverage_manifest.json
```

## Output: `principles/INDEX.md`
```
# Principles and strategy layer (UNVERIFIED, model-grouped)

Principle-first view of the material. Each group page starts with a short model-written overview, then the top claims, then every grouped claim by video. Group titles, assignments and overviews are model judgement on model-written notes, a second unverified layer. Spot check: not spot-checked (fictional). Open the cited video note to check any line.
Exact versions, names, prices and dates are low-weight tags, never a reason to doubt the principle. Only core claims (principle, decision rule, mental model, mistake) are grouped, and only if they clearly fit. Everything else is in supporting_claims.csv. All claims count the same whoever says them; the video ID keeps each one traceable.

| Group | Title | Principle statement | Claims | Videos |
|---|---|---|---|---|
| [G1](G1-validate-demand-before-building.md) | Validate Demand Before Building | Check demand first. | 2 | 2 |
```

## Output: the group page
```
# G1: Validate Demand Before Building

Check demand first.

Status: UNVERIFIED. Group assignment is by a model; the claims are model notes from video windows.

## Overview (model-written, UNVERIFIED)

Check demand first. The reasoning is that building first wastes time. Apply it before any build. The material says so.

## Top claims (up to 8, clearest type first, one per video)

- Talk to five buyers before you build anything, so you do not build what nobody wants. (video demoBBB, window 00:00-10:00, line L5 of videos/demoBBB.md)
- Validate demand before you build anything, because building first wastes months. (video demoAAA, window 00:00-10:00, line L8 of videos/demoAAA.md)  [details unreliable: ExampleBot 9.9]

## All grouped claims by video


**Demo video A: Start with the audience** (demoAAA)
- Principle: Validate demand before you build anything, because building first wastes months. (window 00:00-10:00, line L8 of videos/demoAAA.md)  [details unreliable: ExampleBot 9.9]

**Demo video B: Review before sending** (demoBBB)
- Principle: Talk to five buyers before you build anything, so you do not build what nobody wants. (window 00:00-10:00, line L5 of videos/demoBBB.md)
```

## Output: `supporting_claims.csv`
```
video_id,window,type,group,claim,source_file,line
demoAAA,00:00-10:00,detail,detail,Set the cache size to 512 in the hosting panel.,videos/demoAAA.md,9
demoAAA,00:00-10:00,filler,filler,Hello and welcome to the channel.,videos/demoAAA.md,10
demoBBB,00:00-10:00,detail,detail,Click the blue button on the settings page.,videos/demoBBB.md,6
```

## Output: graph check on the generated graph
`graph_check.py` result: ok=True, nodes=9, edges=8, principles per video {"v:demoAAA": 1, "v:demoBBB": 1}.
