# Inspirations and closest prior work

- [Looped Weight-Space Programming](https://github.com/mbzuai-oryx/LoopedWSP) and its [project page](https://mbzuai-oryx.github.io/LoopedWSP/): fixed input instances, looped weight-space programs, full attention, maximum 128 per side in the published maze setting. MIT.
- [Simulation of Graph Algorithms with Looped Transformers](https://arxiv.org/abs/2402.01107): theoretical graph-algorithm simulation on static graphs.
- [Pathfinding Neural Cellular Automata](https://arxiv.org/abs/2301.06820) and [code](https://github.com/smearle/pathfinding-nca): learned/static maze pathfinding.
- [2D Spatial Reasoning with Adaptive Neural Cellular Automata](https://arxiv.org/abs/2610.08518): adaptive NCA spatial reasoning, again not duplex street-map repair.
- [Weight-Space Programs on Unseen Games](https://arxiv.org/abs/2611.16981): related looped weight-space construction without mid-run input edits.
- Koenig and Likhachev's D* Lite and LPA* (2002): classical incremental replanning. undertow is not a replacement for these algorithms; it asks whether a looped neural state machine can carry a related repair invariant.
- Deep-equilibrium warm starts such as [DEQ-Stereo](https://arxiv.org/abs/2610.39701): trained approximate reuse of equilibrium state, without an exactness guarantee.
- [Sage-Interaction](https://huggingface.co/internlm/Sage-Interaction) and [SHANKS](https://arxiv.org/abs/2510.06917): systems that listen or act while thinking, but do not maintain an exact algorithmic city-scale field.

No affiliation with these authors or projects is claimed.
