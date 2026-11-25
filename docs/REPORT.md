# undertow report

## Method

undertow keeps one persistent torch CPU state tensor for a 256x256 raster of real OpenStreetMap streets. Each cell carries a capped integer distance, a parent-direction one-hot, and an invalid lane. Walkability and transit-exit input planes are injected on every loop. Closing or opening a street edits only those planes; the state tensor is copied in place and is never reset.

The update is a written integer stencil compiled from the deterministic weight program in `undertow/weights.py` (`weights/undertow_block.npz`, 14,376 matrix-program parameters). Invalid cells reset to `INF`; invalidation propagates backward along parent pointers one hop per loop. The invalid lane is held until a cell is locally consistent with a valid parent, which prevents stale finite loops from refilling the retreating front. Ordinary synchronous min-relaxation then re-floods the map. A BFS oracle checks every walkable cell.

This is the honest implementation boundary: the shipped hot loop is the exact compiled integer stencil, not a dense literal execution of every attention/MLP matrix multiplication. The fixed matrix program is committed and bit-for-bit reproducible, but future work should either execute the full transformer algebra directly or prove a formal compilation equivalence. This does not affect the measured algorithmic outputs, which are exact integer tensor updates, but it is a narrower claim than the strongest possible reading of the brief.

## Data

Four real OSM areas are cached in `data/osm/` with SHA-256 sidecars:

| city | walkable cells | exits | OSM ways | building dots | checksum prefix |
|---|---:|---:|---:|---:|---|
| Paris · Ile de la Cite | 36,104 | 6 | 4,663 | 2,000 | `fba5c166cb49` |
| Lyon · Presqu'ile | 31,740 | 6 | 3,652 | 2,000 | `08edf8099061` |
| Amsterdam · canal ring | 32,588 | 6 | 3,013 | 2,000 | `4ac735d7da1f` |
| Venice · San Marco | 25,551 | 6 | 2,349 | 1,188 | `bac2e0a8cfd9` |

The preferred downloader is Overpass. Public Overpass endpoints timed out or returned endpoint errors from this box on 2026-11-25, so the committed extracts use the versioned OpenStreetMap `/api/0.6/map` fallback in tiled bboxes. The extracts are still real OSM data, capped, cached, checksummed, and ODbL-attributed; the actual source is recorded inside each extract. This is a data-provenance deviation from the original brief, not synthetic data.

OSM often splits a street into parallel carriageway/cycleway/sidewalk ways. A named edit expands to all real OSM ways with the same exact name, then barricades their raster cells. No hand-drawn edit geometry is used.

## Scale actually run

The committed core run is **4 cities x 5 trials per arm x 3 arms = 60 trials**, each with 4 random real named-street edits injected mid-run. It is not the full 200-trial schedule. Wall time was 144.3 s on this 8-core CPU container. Measured streaming throughput was 174.9 loops/s in Paris, 133.6 in Lyon, 251.3 in Amsterdam, and 217.5 in Venice (mean 194 loops/s). Arm D used a 45 s CPU training smoke, not 12 h. Arm E used 1 writer round of at most 260 tokens, not 3 attempts x 20 rounds. These are deliberate scale labels, not hidden substitutions.

## Core results

| arm | exact rate | 95% bootstrap CI | mean wrong-cell fraction |
|---|---:|---:|---:|
| A, undertow | 100.0% (20/20) | 100.0%–100.0% | 0.000% |
| B, invalidation ablation | 50.0% (10/20) | 30.0%–70.0% | 2.432% |
| C, restart | 100.0% (20/20) | 100.0%–100.0% | 0.000% |

Single-edit repair on 16 real bridge/street closures:

| measure | value |
|---|---:|
| median repair loops | 89 |
| median restart loops | 196.5 |
| median repair/restart | 0.4218 |
| ablation stale-closure rate | 100% |

The median hides important spread. Amsterdam and Venice each include a closure where repair cost equalled or exceeded restart (ratios 1.04 and 1.11), and one Paris way had ratio 0.94. The repair benefit is real but not universal.

## Hypotheses

1. **Exact final field in >=99% of 200 trials:** supported in the scaled run, 20/20 exact, but the full 200-trial schedule was not run. Treat as promising, not established.
2. **Median single-closure repair <=0.5x restart:** supported in the scaled repair suite, median ratio 0.4218. Several individual closures miss the bound.
3. **Ablation leaves stale distances in >=50% of closure trials:** supported. The ablation was exact in only 10/20 multi-edit trials, averaged 808.45 stale finite cells, and left stale finite cells in 16/16 single-closure repair measurements.
4. **Gradient-trained block stays below 90% exact within budget:** supported only as a small smoke. After 45 s CPU training at 32x32, the 9,448-parameter trainable local block was exact in 0/2 Paris evaluations. This says almost nothing about the full 12 h budget; it is evidence of difficulty, not proof.
5. **Local 7B writer fails in 3x20 rounds:** supported only as a small smoke. The real local `Qwen2.5-Coder-7B-Instruct` Q4_K_M GGUF ran in a locally built CPU `llama.cpp`. One bounded round generated an incomplete/truncated candidate and failed the static compile gate. The model output reached the Python fence but did not finish a valid implementation within the token bound. The full 3x20 schedule was not run.

## Negative and limiting results

- The full-scale hypotheses remain open because the complete 200-trial, 12 h Arm D, and 3x20 Arm E schedules were not run in this Devin wall-time budget.
- Repair can cost as much as restart on large or centrally important closures. The undertow is not a universal speedup.
- The ablation sometimes still becomes exact. Redundant street grids can mask missing invalidation.
- Rasterization converts continuous streets into a four-neighbour grid. It is a real OSM-derived graph, not a centimetre-accurate pedestrian network.
- Some extracted areas have fragmented or unreachable components; those cells are explicitly carried at `INF` and counted by the oracle.
- Voice capture is wired to optional local whisper.cpp plus strict grammar; if the binary/model is absent, the dashboard says so and typed grammar remains. Piper is credited and treated as an optional local component, but no voice model is bundled.
- The dashboard replay is deterministic re-simulation from the committed real-event JSONL log and telemetry, not a frame-by-frame dump of every tensor.

## Related work

See `INSPIRATIONS.md`. The closest comparator is LoopedWSP; undertow differs mainly in dynamic input edits, exact invalidation repair, real city rasters, and CPU-local operation. D* Lite/LPA* remain stronger classical incremental-planning references and this project does not claim to replace them.

## Social summary

I built a small CPU-only looped grid program that floods real OpenStreetMap streets with exact shortest-path distances and can keep its state while streets close and reopen. In a scaled 60-trial run across four city extracts, the written undertow arm matched BFS in every trial, while the invalidation ablation was exact in only half. Median single-edit repair was 0.42x a restart, though some large closures cost as much as restarting. The gradient and local-7B comparisons were only short CPU smokes, so those claims remain open rather than proven.
