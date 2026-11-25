#!/usr/bin/env python3
"""Small runnable verification suite; no test framework required."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

from app.voice import parse_command
from undertow.eval import stable_input
from undertow.net import DuplexRunner, GridInput, run_until_stable
from undertow.oracle import bfs_distance, exact_match
from undertow.osm import CITIES, MAX_DOWNLOAD_BYTES, load_city
from undertow.weights import WEIGHTS_PATH, parameter_count, regenerates_bit_for_bit


def test_weights_bit_for_bit() -> None:
    assert WEIGHTS_PATH.exists(), "committed weight npz missing"
    assert regenerates_bit_for_bit(WEIGHTS_PATH), "weights.py does not regenerate committed npz bit for bit"
    assert parameter_count() == 14376


def test_cache_boundaries() -> None:
    for key in CITIES:
        raw = Path(f"data/osm/{key}.osm.json.gz")
        sha = Path(f"data/osm/{key}.osm.sha256")
        assert raw.exists() and sha.exists(), f"missing cached real OSM extract for {key}"
        assert raw.stat().st_size <= MAX_DOWNLOAD_BYTES
        import gzip

        payload = json.loads(gzip.decompress(raw.read_bytes()).decode())
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        assert hashlib.sha256(canonical).hexdigest() == sha.read_text().split()[0]


def test_real_edit_sequences() -> None:
    # 50 random edit sequences over the real Paris OSM extract. A 96-cell
    # raster keeps CI CPU time bounded; the shipped evaluation uses 256x256.
    city = load_city("paris", size=96)
    choices = [w for w in city.ways if w.name and len(w.cells) >= 3]
    assert choices, "no named real OSM ways available"
    rng = np.random.default_rng(20261125)
    for trial in range(50):
        runner = DuplexRunner(city.size, city.size, city.walkable, enable_invalidation=True)
        state_token = runner.state
        closed: set[int] = set()
        inp = stable_input(city, closed)
        run_until_stable(runner, inp, max_loops=700)
        for _ in range(3):
            way = choices[int(rng.integers(len(choices)))]
            if rng.random() < 0.7:
                closed.add(way.osm_id)
            elif closed:
                closed.remove(next(iter(closed)))
            inp = stable_input(city, closed)
            run_until_stable(runner, inp, max_loops=900)
            assert runner.state is state_token, "recurrent state tensor was reset during an edit"
        oracle = bfs_distance(inp.walkable.numpy(), inp.exits.numpy())
        assert exact_match(runner.distances().numpy().astype(np.int32), oracle, inp.walkable.numpy()), f"trial {trial} final field mismatch"
    print("real edit sequences: 50/50 exact")


def test_ablation_only_invalidates_differently() -> None:
    city = load_city("paris", size=96)
    way = city.way_by_name("Pont Neuf") or [w for w in city.ways if w.name][0]
    base = stable_input(city, set())
    closed = stable_input(city, {way.osm_id})
    runners = [DuplexRunner(city.size, city.size, city.walkable, enable_invalidation=flag) for flag in (True, False)]
    assert runners[0].block.inf == runners[1].block.inf
    assert np.array_equal(runners[0].state.numpy(), runners[1].state.numpy())
    for runner in runners:
        run_until_stable(runner, base, max_loops=700)
        run_until_stable(runner, closed, max_loops=900)
    oracle = bfs_distance(closed.walkable.numpy(), closed.exits.numpy())
    exact_a = exact_match(runners[0].distances().numpy().astype(np.int32), oracle, closed.walkable.numpy())
    exact_b = exact_match(runners[1].distances().numpy().astype(np.int32), oracle, closed.walkable.numpy())
    assert exact_a
    assert not exact_b or not np.array_equal(runners[0].distances().numpy(), runners[1].distances().numpy())


def test_voice_whitelist() -> None:
    names = ["Pont Neuf", "Rue de Rivoli"]
    hit = parse_command("close Pont Neuf", names)
    assert hit and hit.action == "close" and hit.name == "Pont Neuf"
    assert parse_command("close the computation layer", names) is None
    assert parse_command("delete Pont Neuf", names) is None


def test_results_shape_if_present() -> None:
    path = Path("results/core_arms.json")
    if not path.exists():
        return
    payload = json.loads(path.read_text())
    assert payload["run_type"] == "core_arms_real_osm"
    assert "scale_label" in payload and "trials" in payload
    assert set(payload["arms"]) == {"A", "B", "C"}
    assert payload["weight_count"] == parameter_count()
    from scripts.plots import markdown_tables

    tables_path = Path("results/readme_tables.md")
    assert tables_path.exists()
    assert tables_path.read_text().strip() == markdown_tables(payload).strip()


def main() -> None:
    test_weights_bit_for_bit()
    test_cache_boundaries()
    test_voice_whitelist()
    test_ablation_only_invalidates_differently()
    test_real_edit_sequences()
    test_results_shape_if_present()
    print("undertow checks passed")


if __name__ == "__main__":
    main()
