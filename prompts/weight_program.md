# Written weight-program prompt

Construct one shared looped grid block for exact four-neighbour shortest-path flood fill. No gradient descent is used for the main arm.

State per cell:

- channel 0: capped integer distance, `INF=4095`
- channel 1: invalid lane
- channels 2..7: parent one-hot over `none,N,E,S,W,exit`

Injected input every loop:

- walkable plane from the current edited OSM raster
- exit plane from real transit stops

Update:

1. Unwalkable input cells are invalid seeds.
2. A walkable cell becomes invalid when the neighbour named by its parent lane is invalid.
3. Invalid cells reset distance to `INF` and parent to `none`.
4. The invalid lane is held until the cell is locally consistent with a valid parent (or is an exit), preventing stale finite loops from refilling the retreating front.
5. Ordinary synchronous min-relaxation decreases distance toward the best finite valid cardinal neighbour and records that neighbour as parent.
6. Exits are distance zero with parent `exit`.
7. Input changes never reset the state tensor.

The matrix program in `undertow/weights.py` is generated only by closed-form modular/index formulas. `undertow/net.py` executes the exact integer stencil compiled from that program on torch CPU tensors. The committed npz must regenerate bit for bit.
