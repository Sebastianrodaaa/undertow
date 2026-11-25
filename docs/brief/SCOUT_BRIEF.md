# undertow scout brief (self-contained copy)

Sebastian approved the build on 2026-11-25 (Europe/Paris). The original box paths `/workspace/ai-frontier/reports/2026-11-25-undertow-brief-v2.md` and `/workspace/ai-frontier/projects.md` are intentionally not required; this copy carries the operative brief.

## Idea

Build a duplex looped weight-space program: one shared looped grid block, weights written by formula rather than gradient-trained in the main arm, that floods real OpenStreetMap street rasters with exact shortest-path distances on a CPU. Input planes are re-injected every loop. A closure or opening changes only input; the recurrent state tensor is never reset.

Each cell carries a distance channel, parent-direction lanes, and an invalid lane. Closure seeds invalid cells. Invalidation travels backward down parent pointers one hop per loop (the undertow), resets dependent stale distances, then ordinary min-relaxation re-floods. The intended benefit is repair in proportion to the affected region rather than a full restart.

## Required demo

A real local Finance Bento dashboard, live over websocket and replayable from deterministic real-run logs. Paris uses real OSM data around Ile de la Cite. The scripted beat is: flood from real transit exits; `close Pont Neuf`; undertow plus refill; BFS oracle lamp; rapid edits; tide strip; edit log; invalidation-off ablation; real end-card numbers. Sound is optional. Click edits and a strict street-name voice grammar are required; no LLM in the control path.

## Cities and data

Real OSM only: Paris (Ile de la Cite/Chatelet), Lyon (Presqu'ile), Amsterdam (canal ring), Venice (San Marco), rasterized to 256x256 four-neighbour grids. Exits come from real transit stop nodes; building centroids become dots. Downloads must be timeouts/capped/checksummed and carry ODbL attribution.

## Arms

A written duplex block; B invalidation ablation; C restart reference; D gradient-trained local block; E local Qwen2.5-Coder-7B-Instruct Q4 writer in llama.cpp on CPU only; F LoopedWSP reference only. Compute is CPU only, no paid APIs or GPU.

## Hypotheses

1. undertow ends exact against BFS in at least 99% of 200 trials.
2. median single-closure repair is at most half restart.
3. invalidation ablation leaves stale distances in at least half of closure trials.
4. gradient training stays below 90% exact on 256x256 cities within the CPU budget.
5. the local 7B writer fails to produce a passing block in the specified attempts.

Scaled runs must be labeled exactly; negative results ship honestly.

## Standing rules

No mock data in results or demo. Mock fixtures only under `tests/mock_data/`. Work on a branch, open a PR to main, do not merge. MIT plus NOTICE. Black-and-white athanor-style README. Finance Bento dashboard in color. Tests and GitHub Actions CI. Record real 1080p 16:9 and 9:16 footage plus shot list. Save the weight-program prompt in `prompts/`.
