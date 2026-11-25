"""Arm D: gradient-trained looped grid block.

This is intentionally a real training harness, not a scripted verdict. The
scaled run committed in results/ uses short CPU wall-clock budgets and says so.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

from .net import CHANNELS, DIST, INVALID, PARENT0, initial_state, shift_plane
from .oracle import INF, bfs_distance, exact_match
from .osm import load_city
from .eval import stable_input

IN_CHANNELS = 2
LOCAL_POSITIONS = ((0, 0), (-1, 0), (0, 1), (1, 0), (0, -1))


class TrainableGridBlock(nn.Module):
    """Trainable five-position local block with the same state/input interface."""

    def __init__(self, hidden: int = 160):
        super().__init__()
        in_features = (CHANNELS + IN_CHANNELS) * len(LOCAL_POSITIONS)
        self.fc1 = nn.Conv2d(in_features, hidden, kernel_size=1)
        self.fc2 = nn.Conv2d(hidden, CHANNELS, kernel_size=1)

    def forward(self, state_hwc: torch.Tensor, walk: torch.Tensor, exits: torch.Tensor) -> torch.Tensor:
        # state/input are NHWC planes for one batch; local positions are the
        # same self+N/E/S/W stencil as the written block.
        x = torch.cat((state_hwc, walk[..., None].float(), exits[..., None].float()), dim=-1)
        parts = [shift_plane(x, dy, dx, 0.0) for dy, dx in LOCAL_POSITIONS]
        local = torch.cat(parts, dim=-1).permute(2, 0, 1).unsqueeze(0)
        out = self.fc2(torch.relu(self.fc1(local))).squeeze(0).permute(1, 2, 0)
        return out


def random_map(size: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    walk = rng.random((size, size)) > 0.24
    walk[size // 2, :] = True
    walk[:, size // 2] = True
    exits = np.zeros_like(walk)
    exits[size // 2, size // 2] = True
    walk[size // 2, size // 2] = True
    return walk, exits


def train_round(seconds: float = 60.0, size: int = 32, seed: int = 0, unroll: int = 10) -> dict:
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    model = TrainableGridBlock()
    opt = torch.optim.AdamW(model.parameters(), lr=3e-3, weight_decay=1e-5)
    start = time.perf_counter()
    batches = 0
    losses: list[float] = []
    while time.perf_counter() - start < seconds:
        walk_np, exits_np = random_map(size, rng)
        # Mid-run edit during training: close a random vertical segment after
        # half the rollout. This exposes the training loop to input mutation.
        close_x = int(rng.integers(size // 4, 3 * size // 4))
        close_y0 = int(rng.integers(0, size // 2))
        close_y1 = int(rng.integers(close_y0 + 2, size))
        edited = walk_np.copy()
        edited[close_y0:close_y1, close_x] = False
        state = initial_state(size, size, walkable=walk_np)
        walk0 = torch.as_tensor(walk_np, dtype=torch.bool)
        walk1 = torch.as_tensor(edited, dtype=torch.bool)
        exits = torch.as_tensor(exits_np, dtype=torch.bool)
        target = torch.as_tensor(bfs_distance(edited, exits_np), dtype=torch.float32) / float(INF)
        loss = torch.tensor(0.0)
        for step in range(unroll):
            walk = walk0 if step < unroll // 2 else walk1
            state = model(state, walk, exits)
            loss = loss + torch.nn.functional.mse_loss(state[..., DIST] / float(INF), target) / unroll
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        batches += 1
        losses.append(float(loss.detach()))
    elapsed = time.perf_counter() - start
    return {
        "model": model,
        "batches": batches,
        "train_seconds": elapsed,
        "final_loss": losses[-1] if losses else None,
        "mean_last10_loss": float(np.mean(losses[-10:])) if losses else None,
        "parameter_count": int(sum(p.numel() for p in model.parameters())),
    }


def evaluate_model(model: nn.Module, city_key: str = "paris", trials: int = 2, max_loops: int = 700) -> dict:
    city = load_city(city_key)
    rows = []
    for trial in range(trials):
        inp = stable_input(city, set())
        state = initial_state(city.size, city.size, walkable=inp.walkable.numpy())
        with torch.no_grad():
            for _ in range(max_loops):
                nxt = model(state, inp.walkable, inp.exits)
                if torch.allclose(nxt, state, atol=1e-4):
                    state = nxt
                    break
                state = nxt
        field = torch.clamp(torch.round(state[..., DIST]), max=INF).numpy().astype(np.int32)
        oracle = bfs_distance(inp.walkable.numpy(), inp.exits.numpy())
        rows.append({"trial": trial, "exact": bool(exact_match(field, oracle, inp.walkable.numpy()))})
    return {"city": city_key, "trials": trials, "exact_rate": float(np.mean([r["exact"] for r in rows])), "rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--size", type=int, default=32)
    parser.add_argument("--trials", type=int, default=2)
    parser.add_argument("--out", default="results/arm_d_gradient.json")
    args = parser.parse_args()
    result = train_round(seconds=args.seconds, size=args.size)
    model = result.pop("model")
    result["evaluation"] = evaluate_model(model, trials=args.trials)
    result["scale_label"] = f"CPU smoke: {args.seconds:.0f}s training at {args.size}x{args.size}, {args.trials} city evaluation trials"
    result["hypothesis_4_supported"] = bool(result["evaluation"]["exact_rate"] < 0.9)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2, sort_keys=True))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
