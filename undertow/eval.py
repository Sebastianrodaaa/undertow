"""Evaluation harness. Every number written here comes from a real local run."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch

from .net import DuplexRunner, GridInput
from .oracle import INF, bfs_distance, wrong_cells
from .osm import CITIES, CityGrid, closed_walkable, load_city
from .weights import parameter_count, sha256


def stable_input(city: CityGrid, closed_ids: set[int] | None = None) -> GridInput:
    walk = closed_walkable(city, closed_ids or set())
    return GridInput.from_numpy(walk, city.exits)


def run_to_stable(runner: DuplexRunner, inp: GridInput, max_loops: int, series: list[int] | None = None) -> tuple[int, bool]:
    start = runner.loop
    for _ in range(max_loops):
        stats = runner.step(inp)
        if series is not None:
            series.append(int(stats["changed"]))
        if stats["changed"] == 0:
            return runner.loop - start, True
    return runner.loop - start, False


def choose_editable_ways(city: CityGrid) -> list:
    named = [w for w in city.ways if w.name and len(w.cells) >= 6]
    return named or [w for w in city.ways if len(w.cells) >= 6]


def random_events(city: CityGrid, seed: int, count: int) -> list[dict]:
    rng = np.random.default_rng(seed)
    choices = choose_editable_ways(city)
    if not choices:
        raise ValueError(f"no editable OSM ways in {city.spec.key}")
    # Bridges are the interesting failure case, but ordinary named streets are
    # included so closures are not hand-selected.
    weights = np.asarray([3.0 if w.bridge else 1.0 for w in choices], dtype=float)
    weights /= weights.sum()
    events = []
    loop = int(rng.integers(20, 45))
    closed: set[int] = set()
    for index in range(count):
        way = choices[int(rng.choice(len(choices), p=weights))]
        if way.osm_id in closed:
            action = "open"
            closed.remove(way.osm_id)
        elif rng.random() < 0.78:
            action = "close"
            closed.add(way.osm_id)
        else:
            # Pick a previously closed way to reopen when one exists; otherwise
            # this remains a closure, so every event is a real map edit.
            if closed:
                way_id = int(rng.choice(sorted(closed)))
                way = next(w for w in choices if w.osm_id == way_id)
                action = "open"
                closed.remove(way_id)
            else:
                action = "close"
                closed.add(way.osm_id)
        events.append({"loop": loop, "way_id": way.osm_id, "name": way.name, "action": action})
        loop += int(rng.integers(8, 22))
    return events


def simulate_trial(
    city: CityGrid,
    arm: str,
    seed: int,
    edit_count: int,
    max_loops: int = 2200,
    collect: bool = False,
) -> dict:
    rng = np.random.default_rng(seed + 17)
    events = random_events(city, seed, edit_count)
    closed: set[int] = set()
    runner = DuplexRunner(city.size, city.size, city.walkable, enable_invalidation=(arm != "B"))
    inp = stable_input(city, closed)
    event_index = 0
    last_event_loop = max(e["loop"] for e in events)
    series: list[int] = []
    converged = False
    loops_run = 0
    resets = 0
    started = time.perf_counter()

    for loop in range(max_loops):
        while event_index < len(events) and events[event_index]["loop"] <= loop:
            event = events[event_index]
            if event["action"] == "close":
                closed.add(int(event["way_id"]))
            else:
                closed.discard(int(event["way_id"]))
            inp = stable_input(city, closed)
            if arm == "C":
                runner = DuplexRunner(city.size, city.size, inp.walkable.numpy(), enable_invalidation=True)
                resets += 1
            event_index += 1
        stats = runner.step(inp)
        loops_run += 1
        if collect:
            series.append(int(stats["changed"]))
        if loop > last_event_loop and stats["changed"] == 0:
            converged = True
            break

    oracle = bfs_distance(inp.walkable.numpy(), inp.exits.numpy())
    field = runner.distances().numpy().astype(np.int32)
    wrong = wrong_cells(field, oracle, inp.walkable.numpy())
    stale_finite = wrong & (field < INF)
    elapsed = time.perf_counter() - started
    return {
        "arm": arm,
        "seed": int(seed),
        "city": city.spec.key,
        "edit_count": int(edit_count),
        "events": events,
        "loops_run": int(loops_run),
        "converged": bool(converged),
        "exact": bool(converged and not wrong.any()),
        "wrong_cells": int(wrong.sum()),
        "wrong_fraction": float(wrong.sum() / max(1, inp.walkable.numpy().sum())),
        "stale_finite_cells": int(stale_finite.sum()),
        "state_resets": int(resets),
        "wall_seconds": elapsed,
        "changed_series": series if collect else [],
    }


def repair_benchmark(city: CityGrid, way, arm: str = "A", max_loops: int = 2200) -> dict:
    base = stable_input(city, set())
    runner = DuplexRunner(city.size, city.size, city.walkable, enable_invalidation=(arm != "B"))
    initial_loops, initial_converged = run_to_stable(runner, base, max_loops)
    closed = stable_input(city, {way.osm_id})
    repair_loops, repair_converged = run_to_stable(runner, closed, max_loops)

    restart = DuplexRunner(city.size, city.size, closed.walkable.numpy(), enable_invalidation=True)
    restart_loops, restart_converged = run_to_stable(restart, closed, max_loops)
    oracle = bfs_distance(closed.walkable.numpy(), closed.exits.numpy())
    wrong = wrong_cells(runner.distances().numpy().astype(np.int32), oracle, closed.walkable.numpy())
    return {
        "city": city.spec.key,
        "way_id": int(way.osm_id),
        "name": way.name,
        "arm": arm,
        "initial_loops": int(initial_loops),
        "repair_loops": int(repair_loops),
        "restart_loops": int(restart_loops),
        "ratio": float(repair_loops / max(1, restart_loops)),
        "exact": bool(repair_converged and not wrong.any()),
        "wrong_cells": int(wrong.sum()),
        "stale_finite_cells": int((wrong & (runner.distances().numpy() < INF)).sum()),
        "converged": bool(repair_converged and restart_converged and initial_converged),
    }


def bootstrap_ci(values: list[float], seed: int = 0, samples: int = 2000) -> list[float]:
    if not values:
        return [0.0, 0.0]
    arr = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(arr), size=(samples, len(arr)))
    means = arr[idx].mean(axis=1)
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def throughput(city: CityGrid, seconds: float = 2.0) -> dict:
    inp = stable_input(city, set())
    runner = DuplexRunner(city.size, city.size, city.walkable, enable_invalidation=True)
    runner.step(inp)  # warm up torch kernels before timing
    start = time.perf_counter()
    loops = 0
    while time.perf_counter() - start < seconds:
        runner.step(inp)
        loops += 1
    elapsed = time.perf_counter() - start
    return {"city": city.spec.key, "loops_per_second": loops / elapsed, "loops": loops, "seconds": elapsed}


def run_core_evaluation(city_keys: list[str], trials_per_city: int, edit_count: int, out_path: str | Path) -> dict:
    torch.set_num_threads(max(1, min(8, torch.get_num_threads())))
    started = time.time()
    all_trials = []
    repairs = []
    throughputs = []
    city_meta = {}
    for key in city_keys:
        city = load_city(key)
        city_meta[key] = {
            "label": city.spec.label,
            "bbox": city.spec.bbox,
            "checksum": city.checksum,
            "walkable_cells": int(city.walkable.sum()),
            "exit_count": int(len(city.exit_points)),
            "way_count": int(len(city.ways)),
            "building_dots": int(len(city.buildings)),
        }
        throughputs.append(throughput(city, seconds=1.5))
        editable = choose_editable_ways(city)
        bridge_first = sorted(editable, key=lambda w: (not w.bridge, -len(w.cells)))
        for arm in ("A", "B", "C"):
            for trial in range(trials_per_city):
                seed = 10_000 + 1_000 * city_keys.index(key) + 100 * trial
                result = simulate_trial(city, arm, seed, edit_count=edit_count)
                result["changed_series"] = []
                all_trials.append(result)
        # Repair is measured on the largest available bridge/named way, then a
        # deterministic rotation of other editable real OSM ways.
        repair_ways = bridge_first[: min(4, len(bridge_first))]
        for arm in ("A", "B"):
            for way in repair_ways:
                repairs.append(repair_benchmark(city, way, arm=arm))

    def rows_for(arm: str) -> list[dict]:
        return [r for r in all_trials if r["arm"] == arm]

    arms = {}
    for arm in ("A", "B", "C"):
        rows = rows_for(arm)
        exact_values = [float(r["exact"]) for r in rows]
        arms[arm] = {
            "trials": len(rows),
            "exact_rate": float(np.mean(exact_values)) if rows else 0.0,
            "exact_rate_ci95": bootstrap_ci(exact_values),
            "wrong_fraction_mean": float(np.mean([r["wrong_fraction"] for r in rows])) if rows else 0.0,
            "stale_finite_cells_mean": float(np.mean([r["stale_finite_cells"] for r in rows])) if rows else 0.0,
            "converged_rate": float(np.mean([r["converged"] for r in rows])) if rows else 0.0,
        }
    repair_a = [r for r in repairs if r["arm"] == "A"]
    repair_b = [r for r in repairs if r["arm"] == "B"]
    payload = {
        "run_type": "core_arms_real_osm",
        "scale_label": f"{len(city_keys)} cities x {trials_per_city} trials per arm, {edit_count} edits per trial",
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "wall_seconds": time.time() - started,
        "cpu_count": int(torch.get_num_threads()),
        "torch_version": torch.__version__,
        "weights_sha256": sha256(),
        "weight_count": parameter_count(),
        "cities": city_meta,
        "throughput": throughputs,
        "arms": arms,
        "repair": {
            "A": {
                "median_repair_loops": float(np.median([r["repair_loops"] for r in repair_a])) if repair_a else 0.0,
                "median_restart_loops": float(np.median([r["restart_loops"] for r in repair_a])) if repair_a else 0.0,
                "median_ratio": float(np.median([r["ratio"] for r in repair_a])) if repair_a else 0.0,
                "rows": repair_a,
            },
            "B": {
                "median_repair_loops": float(np.median([r["repair_loops"] for r in repair_b])) if repair_b else 0.0,
                "median_restart_loops": float(np.median([r["restart_loops"] for r in repair_b])) if repair_b else 0.0,
                "median_ratio": float(np.median([r["ratio"] for r in repair_b])) if repair_b else 0.0,
                "stale_trial_rate": float(np.mean([r["stale_finite_cells"] > 0 for r in repair_b])) if repair_b else 0.0,
                "rows": repair_b,
            },
        },
        "trials": all_trials,
    }
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cities", nargs="+", default=list(CITIES), choices=list(CITIES))
    parser.add_argument("--trials-per-city", type=int, default=5)
    parser.add_argument("--edit-count", type=int, default=4)
    parser.add_argument("--out", default="results/core_arms.json")
    args = parser.parse_args()
    payload = run_core_evaluation(args.cities, args.trials_per_city, args.edit_count, args.out)
    print(json.dumps({"out": args.out, "scale": payload["scale_label"], "arms": payload["arms"], "wall_seconds": payload["wall_seconds"]}, indent=2))


if __name__ == "__main__":
    main()
