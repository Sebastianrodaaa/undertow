#!/usr/bin/env python3
"""Live/replay websocket dashboard for the real undertow run."""

from __future__ import annotations

import argparse
import asyncio
import json
import struct
import sys
import time
import webbrowser
from pathlib import Path

import numpy as np
from aiohttp import web

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from undertow.eval import run_to_stable, stable_input, throughput  # noqa: E402
from undertow.net import DuplexRunner  # noqa: E402
from undertow.oracle import INF, bfs_distance, wrong_cells  # noqa: E402
from undertow.osm import CITIES, load_city, way_table  # noqa: E402
from undertow.weights import parameter_count  # noqa: E402
from app.voice import parse_command, synthesize_piper, transcribe_browser_audio  # noqa: E402

MAGIC = 0x55544F57


def restart_loop_cost(city, closed_ids: set[int], max_loops: int = 2500) -> int:
    inp = stable_input(city, closed_ids)
    runner = DuplexRunner(city.size, city.size, inp.walkable.numpy(), enable_invalidation=True)
    loops, _ = run_to_stable(runner, inp, max_loops)
    return int(loops)


def demo_events(city) -> list[dict]:
    """Replay script loaded from the recorded real-event JSONL when available."""
    events = []
    log_path = ROOT / "results" / "replay_session.jsonl"
    way_ids = {w.osm_id for w in city.ways}
    if log_path.exists() and city.spec.key == "paris":
        for line in log_path.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("type") == "edit" and int(row.get("way_id", -1)) in way_ids:
                events.append({
                    "loop": int(row["loop"]),
                    "way_id": int(row["way_id"]),
                    "name": str(row["name"]),
                    "action": str(row["action"]),
                })
        if events:
            return events
    pont_neuf = city.way_by_name("Pont Neuf") or next((w for w in city.ways if w.bridge and w.name), None)
    rivoli = city.way_by_name("Rue de Rivoli") or next((w for w in city.named_ways if not w.bridge), None)
    change = city.way_by_name("Pont au Change") or next((w for w in city.ways if w.bridge and w.name and w != pont_neuf), None)
    if pont_neuf:
        events.append({"loop": 150, "way_id": pont_neuf.osm_id, "name": pont_neuf.name, "action": "close"})
    if change:
        events.append({"loop": 520, "way_id": change.osm_id, "name": change.name, "action": "close"})
    if pont_neuf:
        events.append({"loop": 610, "way_id": pont_neuf.osm_id, "name": pont_neuf.name, "action": "open"})
    if rivoli:
        events.append({"loop": 690, "way_id": rivoli.osm_id, "name": rivoli.name, "action": "close"})
    if change:
        events.append({"loop": 790, "way_id": change.osm_id, "name": change.name, "action": "open"})
    return events


class Simulation:
    def __init__(self, city_key: str, mode: str = "live", speed: float = 48.0):
        self.city = load_city(city_key)
        self.mode = mode
        self.speed = float(speed)
        self.closed: set[int] = set()
        self.inp = stable_input(self.city, self.closed)
        self.oracle = bfs_distance(self.inp.walkable.numpy(), self.inp.exits.numpy())
        self.runner = DuplexRunner(self.city.size, self.city.size, self.inp.walkable.numpy(), enable_invalidation=True)
        self.ablation = DuplexRunner(self.city.size, self.city.size, self.inp.walkable.numpy(), enable_invalidation=False)
        self.events = demo_events(self.city) if mode == "replay" else []
        self.event_index = 0
        self.edit_log: list[dict] = []
        self.caption = "live flood" if mode == "live" else "replay from the committed real-event log"
        self.last_stats = {"changed": 0, "invalid": 0}
        self.restart_cache: dict[frozenset[int], int] = {}
        self.weight_count = parameter_count()
        self.measured_loops_per_second = throughput(self.city, seconds=0.8)["loops_per_second"]
        results_path = ROOT / "results" / "core_arms.json"
        if results_path.exists():
            try:
                rows = json.loads(results_path.read_text()).get("throughput", [])
                match = next((r for r in rows if r.get("city") == city_key), None)
                if match:
                    self.measured_loops_per_second = float(match["loops_per_second"])
            except Exception:
                pass
        self.recent_changed: list[int] = []

    def apply_way(self, way_id: int, action: str, source: str = "click") -> dict | None:
        way = next((w for w in self.city.ways if w.osm_id == int(way_id)), None)
        if way is None:
            return None
        if action == "close":
            self.closed.add(way.osm_id)
        else:
            self.closed.discard(way.osm_id)
        self.inp = stable_input(self.city, self.closed)
        self.oracle = bfs_distance(self.inp.walkable.numpy(), self.inp.exits.numpy())
        key = frozenset(self.closed)
        if key not in self.restart_cache:
            self.restart_cache[key] = restart_loop_cost(self.city, self.closed)
        row = {
            "loop": self.runner.loop,
            "action": action,
            "name": way.name or f"way {way.osm_id}",
            "way_id": way.osm_id,
            "source": source,
            "restart_loops": self.restart_cache[key],
            "repair_loops": None,
            "status": "repairing",
        }
        self.edit_log.append(row)
        self.caption = f'{action} {row["name"]}'
        return row

    def click(self, y: int, x: int) -> dict | None:
        way = self.city.way_at_cell(y, x)
        if way is None:
            self.caption = "no OSM street at that cell"
            return None
        action = "open" if way.osm_id in self.closed else "close"
        return self.apply_way(way.osm_id, action, source="click")

    def command(self, text: str) -> dict | None:
        names = [w.name for w in self.city.ways if w.name]
        parsed = parse_command(text, names)
        if parsed is None:
            self.caption = "command outside the street-name grammar"
            return None
        way = self.city.way_by_name(parsed.name)
        if way is None:
            return None
        return self.apply_way(way.osm_id, parsed.action, source="voice")

    def step(self) -> dict:
        while self.event_index < len(self.events) and self.events[self.event_index]["loop"] <= self.runner.loop:
            event = self.events[self.event_index]
            self.apply_way(event["way_id"], event["action"], source="replay")
            self.event_index += 1
        stats = self.runner.step(self.inp)
        self.ablation.step(self.inp)
        self.last_stats = stats
        self.recent_changed.append(int(stats["changed"]))
        if len(self.recent_changed) > 600:
            del self.recent_changed[:-600]
        for row in self.edit_log:
            if row["repair_loops"] is None and self.runner.loop > int(row["loop"]) and stats["changed"] == 0:
                row["repair_loops"] = self.runner.loop - int(row["loop"])
                row["status"] = "exact" if self.exact(stats) else "settled"
        return stats

    def field_stats(self, runner: DuplexRunner) -> tuple[int, float, bool]:
        field = runner.distances().numpy().astype(np.int32)
        walk = self.inp.walkable.numpy()
        wrong = wrong_cells(field, self.oracle, walk)
        total = max(1, int(walk.sum()))
        return int(wrong.sum()), float(1.0 - wrong.sum() / total), not bool(wrong.any())

    def exact(self, stats: dict | None = None) -> bool:
        wrong, _, exact_field = self.field_stats(self.runner)
        return bool(exact_field and (stats or self.last_stats)["changed"] == 0)

    def frame(self, frame_type: int, stats: dict) -> bytes:
        runner = self.ablation if frame_type == 1 else self.runner
        wrong, settled, exact_field = self.field_stats(runner)
        exact = bool(exact_field and stats["changed"] == 0 and frame_type == 0)
        dist = np.clip(runner.distances().numpy(), 0, INF).astype("<u2", copy=False)
        inv = runner.state[..., 1].numpy().astype(np.uint8, copy=False)
        walk = self.inp.walkable.numpy().astype(np.uint8, copy=False)
        parent = runner.parent_indices().numpy().astype(np.uint8, copy=False)
        header = bytearray(32)
        repair = next((int(r["repair_loops"]) for r in reversed(self.edit_log) if r["repair_loops"] is not None), 0)
        restart = next((int(r["restart_loops"]) for r in reversed(self.edit_log) if r["restart_loops"] is not None), 0)
        struct.pack_into(
            "<4I4Bf2I",
            header,
            0,
            MAGIC,
            int(self.runner.loop),
            int(stats["changed"]),
            int(stats["invalid"]),
            int(exact),
            int(frame_type),
            int(self.mode == "replay"),
            0,
            float(settled),
            int(repair),
            int(restart),
        )
        return bytes(header) + dist.tobytes() + inv.tobytes() + walk.tobytes() + parent.tobytes()

    def init_message(self) -> dict:
        results_summary = None
        results_path = ROOT / "results" / "core_arms.json"
        if results_path.exists():
            try:
                payload = json.loads(results_path.read_text())
                results_summary = {
                    "A": payload["arms"]["A"]["exact_rate"],
                    "B": payload["arms"]["B"]["exact_rate"],
                    "C": payload["arms"]["C"]["exact_rate"],
                    "medianRepair": payload["repair"]["A"]["median_repair_loops"],
                    "medianRestart": payload["repair"]["A"]["median_restart_loops"],
                    "scale": payload["scale_label"],
                }
            except Exception:
                results_summary = None
        return {
            "type": "init",
            "city": self.city.spec.key,
            "cityLabel": self.city.spec.label,
            "size": self.city.size,
            "mode": self.mode,
            "speed": self.speed,
            "weightCount": self.weight_count,
            "measuredLoopsPerSecond": self.measured_loops_per_second,
            "resultsSummary": results_summary,
            "checksum": self.city.checksum,
            "attribution": "(c) OpenStreetMap contributors, ODbL 1.0",
            "buildings": np.round(self.city.buildings, 2).tolist(),
            "exits": self.city.exit_points.tolist(),
            "ways": way_table(self.city),
            "events": self.events,
        }

    def telemetry(self) -> dict:
        awrong, _, _ = self.field_stats(self.ablation)
        wrong, settled, _ = self.field_stats(self.runner)
        return {
            "type": "telemetry",
            "caption": self.caption,
            "loop": self.runner.loop,
            "editLog": self.edit_log[-12:],
            "changedSeries": self.recent_changed[-240:],
            "ablationStaleCells": int(awrong),
            "wrongCells": int(wrong),
            "settled": settled,
            "throughput": self.measured_loops_per_second,
            "eventsRemaining": len(self.events) - self.event_index,
        }


async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse(max_msg_size=2 * 1024 * 1024)
    await ws.prepare(request)
    city_key = request.query.get("city", "paris")
    if city_key not in CITIES:
        city_key = "paris"
    mode = request.query.get("mode", "live")
    speed = float(request.query.get("speed", "48"))
    sim = Simulation(city_key, mode=mode, speed=speed)
    await ws.send_str(json.dumps(sim.init_message()))
    closed = asyncio.Event()

    async def produce() -> None:
        frame_count = 0
        try:
            while not closed.is_set():
                tick = time.perf_counter()
                stats = sim.step()
                frame_count += 1
                # Stream a few full tensor frames per second. The model keeps
                # looping at real speed even when an intermediate loop is not
                # serialized across the websocket.
                stride = max(1, int(round(sim.speed / 2)))
                if frame_count == 1 or frame_count % stride == 0:
                    await ws.send_bytes(sim.frame(0, stats))
                elif frame_count % (stride * 2) == 1:
                    await ws.send_bytes(sim.frame(1, stats))
                if frame_count % max(4, int(round(sim.speed / 5))) == 0:
                    await ws.send_str(json.dumps(sim.telemetry()))
                elapsed = time.perf_counter() - tick
                await asyncio.sleep(max(0.002, 1.0 / sim.speed - elapsed))
        except (asyncio.CancelledError, ConnectionResetError):
            pass
        finally:
            closed.set()

    async def consume() -> None:
        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.BINARY:
                    text = await asyncio.to_thread(transcribe_browser_audio, msg.data, str(ROOT / "results"))
                    if text:
                        sim.command(text)
                    else:
                        sim.caption = "local whisper.cpp voice unavailable"
                    await ws.send_str(json.dumps(sim.telemetry()))
                    continue
                if msg.type != web.WSMsgType.TEXT:
                    continue
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    continue
                if data.get("type") == "click":
                    sim.click(int(data.get("y", -1)), int(data.get("x", -1)))
                elif data.get("type") == "command":
                    sim.command(str(data.get("text", "")))
                elif data.get("type") == "caption":
                    sim.caption = str(data.get("text", ""))[:120]
                await ws.send_str(json.dumps(sim.telemetry()))
        finally:
            closed.set()

    producer = asyncio.create_task(produce())
    consumer = asyncio.create_task(consume())
    done, pending = await asyncio.wait({producer, consumer}, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    closed.set()
    return ws


async def index(request: web.Request) -> web.Response:
    return web.Response(text=(ROOT / "app" / "index.html").read_text(), content_type="text/html")


async def tts(request: web.Request) -> web.Response:
    text = request.query.get("text", "")[:160]
    if not text:
        return web.Response(status=400, text="missing text")
    out = ROOT / "results" / "tts-response.wav"
    ok = await asyncio.to_thread(synthesize_piper, text, str(out))
    if not ok:
        return web.Response(status=503, text="local piper voice unavailable")
    return web.FileResponse(out)


def make_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/ws", websocket_handler)
    app.router.add_get("/tts", tts)
    app.router.add_static("/fonts/", ROOT / "app" / "fonts", show_index=False)
    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8077)
    parser.add_argument("--city", default="paris", choices=list(CITIES))
    parser.add_argument("--mode", default="live", choices=["live", "replay"])
    parser.add_argument("--speed", type=float, default=48.0)
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()
    url = f"http://{args.host}:{args.port}/?city={args.city}&mode={args.mode}&speed={args.speed}"
    if args.open:
        webbrowser.open(url)
    print(url)
    web.run_app(make_app(), host=args.host, port=args.port, print=None)


if __name__ == "__main__":
    main()
