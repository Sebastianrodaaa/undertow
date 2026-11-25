"""Looped grid block with input re-injection and duplex invalidation.

The exact update is an integer stencil compiled from the written weight program
in `weights.py`. It uses torch tensors throughout and is deliberately small:
five local positions (self + four cardinal neighbours), one distance channel,
six parent lanes, and one invalid lane.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn

try:
    from .oracle import INF
    from .weights import load_weights
except ImportError:  # direct `python undertow/net.py` smoke run
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from undertow.oracle import INF
    from undertow.weights import load_weights

DIST = 0
INVALID = 1
PARENT0 = 2
PARENTS = ("none", "N", "E", "S", "W", "exit")
CHANNELS = 8
DIRS = ((0, 0), (-1, 0), (0, 1), (1, 0), (0, -1))


@dataclass
class GridInput:
    walkable: torch.Tensor
    exits: torch.Tensor

    @classmethod
    def from_numpy(cls, walkable, exits):
        return cls(
            torch.as_tensor(walkable, dtype=torch.bool),
            torch.as_tensor(exits, dtype=torch.bool),
        )


def initial_state(height: int, width: int, walkable=None, inf: float = INF) -> torch.Tensor:
    state = torch.zeros((height, width, CHANNELS), dtype=torch.float32)
    state[..., DIST] = inf
    state[..., PARENT0] = 1.0  # parent = none
    if walkable is not None:
        walk = torch.as_tensor(walkable, dtype=torch.bool)
        state[..., INVALID] = (~walk).float()
    return state


def shift_plane(x: torch.Tensor, dy: int, dx: int, fill: float = 0.0) -> torch.Tensor:
    """Return x sampled at relative offset (dy, dx), without wraparound."""
    h, w = x.shape[:2]
    out = torch.full_like(x, fill)
    oy0 = max(0, -dy)
    iy0 = max(0, dy)
    ox0 = max(0, -dx)
    ix0 = max(0, dx)
    sy = h - abs(dy)
    sx = w - abs(dx)
    if sy <= 0 or sx <= 0:
        return out
    out_index = [slice(None)] * x.ndim
    in_index = [slice(None)] * x.ndim
    out_index[0] = slice(oy0, oy0 + sy)
    out_index[1] = slice(ox0, ox0 + sx)
    in_index[0] = slice(iy0, iy0 + sy)
    in_index[1] = slice(ix0, ix0 + sx)
    out[tuple(out_index)] = x[tuple(in_index)]
    return out


class UndertowBlock(nn.Module):
    """One shared looped block. Its coefficients are fixed and untrained."""

    def __init__(self, weights_path: str = "weights/undertow_block.npz", enable_invalidation: bool = True):
        super().__init__()
        arrays = load_weights(weights_path)
        self.inf = float(arrays["scalars"][0])
        self.enable_invalidation = bool(enable_invalidation)
        self.register_buffer("direction_delta", torch.as_tensor(arrays["direction_delta"], dtype=torch.float32))
        self.register_buffer("parent_transition", torch.as_tensor(arrays["parent_transition"], dtype=torch.float32))

    def forward(self, state: torch.Tensor, grid_input: GridInput) -> torch.Tensor:
        walk = grid_input.walkable.bool()
        exits = grid_input.exits.bool() & walk
        d = state[..., DIST]
        inv = state[..., INVALID] > 0.5
        parent = state[..., PARENT0 : PARENT0 + len(PARENTS)]

        # Read the five fixed local positions. Invalid neighbours are not a
        # usable finite source; this keeps repair ordered behind the retreating
        # front instead of letting stale cells refill it immediately.
        invf = inv.float()
        raw = [
            shift_plane(d, -1, 0, self.inf),
            shift_plane(d, 0, 1, self.inf),
            shift_plane(d, 1, 0, self.inf),
            shift_plane(d, 0, -1, self.inf),
        ]
        valid = [
            shift_plane(invf, -1, 0, 1.0) < 0.5,
            shift_plane(invf, 0, 1, 1.0) < 0.5,
            shift_plane(invf, 1, 0, 1.0) < 0.5,
            shift_plane(invf, 0, -1, 1.0) < 0.5,
        ]
        candidates = torch.stack(
            [torch.clamp(torch.where(ok, val, torch.full_like(val, self.inf)) + 1.0, max=self.inf) for val, ok in zip(raw, valid)],
            dim=-1,
        )
        best, best_idx = candidates.min(dim=-1)

        # Parent lane order is none,N,E,S,W,exit. A child is endangered when
        # the neighbour its parent points at is invalid. If another currently
        # valid neighbour offers any finite route, the cell reparents instead
        # of joining the undertow; otherwise it resets and the front advances.
        child = torch.zeros_like(walk)
        parent_distance = torch.full_like(d, self.inf)
        parent_is_invalid = torch.zeros_like(walk)
        has_directional_parent = torch.zeros_like(walk)
        for lane, (dy, dx) in enumerate(DIRS[1:], start=1):
            lane_selected = parent[..., lane] > 0.5
            pinv = shift_plane(invf, dy, dx, 0.0) > 0.5
            child |= lane_selected & pinv
            pd = shift_plane(d, dy, dx, self.inf)
            parent_distance = torch.where(lane_selected, pd, parent_distance)
            parent_is_invalid |= lane_selected & pinv
            has_directional_parent |= lane_selected

        direct_invalid = child if self.enable_invalidation else torch.zeros_like(walk)
        hard_invalid = direct_invalid

        # An invalid lane is held until the cell is locally consistent with a
        # valid parent (or is an exit). This is the small amount of memory that
        # prevents count-to-infinity while still permitting re-flooding.
        finite = d < self.inf
        consistent_directional = (
            finite
            & has_directional_parent
            & ~parent_is_invalid
            & (d == torch.clamp(parent_distance + 1.0, max=self.inf))
        )
        consistent_exit = exits & (d == 0)
        locally_consistent = consistent_directional | consistent_exit

        if self.enable_invalidation:
            invalid_next = ~walk | hard_invalid | (inv & ~locally_consistent)
        else:
            # Ablation: the invalidation channel is zeroed except for the input
            # plane itself. Closed cells reset; their children receive no signal.
            invalid_next = ~walk

        # Ordinary min-relaxation only decreases distances. Increases are not
        # guessed locally: dependent cells must first join the undertow, which
        # is what prevents stale finite loops from surviving a closure.
        improve = best < d
        update = improve
        next_d = torch.where(update, best, d)
        current_parent_idx = parent.argmax(dim=-1)
        next_parent_idx = torch.where(update, best_idx + 1, current_parent_idx)

        next_d = torch.where(exits, torch.zeros_like(next_d), next_d)
        next_parent_idx = torch.where(exits, torch.full_like(next_parent_idx, 5), next_parent_idx)

        reset = ~walk | hard_invalid
        next_d = torch.where(reset, torch.full_like(next_d, self.inf), next_d)
        next_parent_idx = torch.where(reset, torch.zeros_like(next_parent_idx), next_parent_idx)

        next_parent = torch.nn.functional.one_hot(next_parent_idx.long(), num_classes=len(PARENTS)).float()
        next_state = torch.empty_like(state)
        next_state[..., DIST] = next_d
        next_state[..., INVALID] = invalid_next.float()
        next_state[..., PARENT0 : PARENT0 + len(PARENTS)] = next_parent
        return next_state


class DuplexRunner:
    """Persistent state owner. Edit input planes never replace or reset state."""

    def __init__(self, height: int, width: int, walkable, enable_invalidation: bool = True):
        self.block = UndertowBlock(enable_invalidation=enable_invalidation)
        self.state = initial_state(height, width, walkable=walkable)
        self.loop = 0
        self.resets = 0

    def step(self, grid_input: GridInput) -> dict:
        nxt = self.block(self.state, grid_input)
        changed = int((nxt != self.state).any(dim=-1).sum().item())
        self.state.copy_(nxt)  # in-place: edits never reset the recurrent state tensor
        self.loop += 1
        finite = torch.isfinite(self.state[..., DIST]) & (self.state[..., DIST] < self.block.inf)
        return {
            "loop": self.loop,
            "changed": changed,
            "invalid": int((self.state[..., INVALID] > 0.5).sum().item()),
            "finite": int(finite.sum().item()),
            "max_distance": int(self.state[..., DIST][finite].max().item()) if bool(finite.any()) else 0,
        }

    def distances(self) -> torch.Tensor:
        return self.state[..., DIST].clone()

    def parent_indices(self) -> torch.Tensor:
        return self.state[..., PARENT0 : PARENT0 + len(PARENTS)].argmax(dim=-1)


def run_until_stable(
    runner: DuplexRunner,
    grid_input: GridInput,
    max_loops: int = 4096,
    collect: bool = False,
) -> tuple[int, list[int]]:
    start = runner.loop
    changed_series: list[int] = []
    loops = 0
    while loops < max_loops:
        stats = runner.step(grid_input)
        loops += 1
        if collect:
            changed_series.append(stats["changed"])
        if stats["changed"] == 0:
            break
    return runner.loop - start, changed_series


if __name__ == "__main__":
    walk = torch.ones((16, 16), dtype=torch.bool)
    exits = torch.zeros((16, 16), dtype=torch.bool)
    exits[8, 8] = True
    inp = GridInput(walk, exits)
    runner = DuplexRunner(16, 16, walk.numpy())
    loops, _ = run_until_stable(runner, inp)
    assert int(runner.distances()[0, 0]) == 16
    print("stable", loops, "max", int(runner.distances().max()))
