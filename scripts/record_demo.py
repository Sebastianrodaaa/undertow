#!/usr/bin/env python3
"""Record the real replay dashboard at 1080p in 16:9 and 9:16.

Requires the Python `playwright` package but uses the system Chrome binary; no
hosted or paid service is involved. The recording is the real websocket state
stream in replay mode at the displayed loop rate.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CHROME = shutil.which("google-chrome") or shutil.which("chrome") or shutil.which("chromium")
URL = "http://127.0.0.1:8077/?city=paris&mode=replay&speed=240"


def convert(src: Path, dest: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "21", str(dest)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def make_gif(video: Path) -> None:
    gif = ROOT / "docs/screenshots/demo.gif"
    gif.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-ss", "4", "-t", "18", "-i", str(video),
            "-vf", "fps=8,scale=720:-1:flags=lanczos,format=gray", str(gif),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def capture_screenshot(page, path: Path) -> None:
    color = path.with_suffix(".color.png")
    page.screenshot(path=str(color), full_page=True)
    from PIL import Image

    img = Image.open(color).convert("L")
    img.save(path)
    color.unlink(missing_ok=True)


def record_one(playwright, width: int, height: int, out: Path, seconds: float) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        browser = playwright.chromium.launch(
            executable_path=CHROME,
            headless=True,
            args=["--disable-gpu", "--no-sandbox", "--autoplay-policy=no-user-gesture-required"],
        )
        context = browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=1,
            record_video_dir=tmp,
            record_video_size={"width": width, "height": height},
        )
        page = context.new_page()
        page.goto(URL, wait_until="networkidle")
        # The deterministic replay itself closes Pont Neuf, performs the rapid
        # edit sequence, and refills. Toggle the split during the ablation beat.
        page.wait_for_timeout(int(seconds * 1000 * 0.52))
        if width == 1920:
            capture_screenshot(page, ROOT / "docs/screenshots/hero.png")
        try:
            page.click("#ablview", timeout=1000)
        except Exception:
            pass
        page.wait_for_timeout(int(seconds * 1000 * 0.36))
        try:
            page.click("#mainview", timeout=1000)
        except Exception:
            pass
        page.wait_for_timeout(int(seconds * 1000 * 0.12) + 500)
        video = page.video
        context.close()
        browser.close()
        src = Path(video.path())
        convert(src, out)


def ensure_server() -> subprocess.Popen:
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "app/server.py"), "--port", "8077", "--city", "paris", "--mode", "replay", "--speed", "240"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(80):
        try:
            import urllib.request

            urllib.request.urlopen(URL, timeout=0.5).read(100)
            return proc
        except Exception:
            time.sleep(0.25)
    proc.kill()
    raise RuntimeError("dashboard server did not start")


def main() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit("install playwright first: python3 -m pip install --user playwright") from exc
    if not CHROME:
        raise SystemExit("system Chrome/Chromium not found")
    outdir = ROOT / "videos"
    outdir.mkdir(exist_ok=True)
    server = ensure_server()
    try:
        with sync_playwright() as p:
            record_one(p, 1920, 1080, outdir / "undertow-16x9.mp4", seconds=55.0)
            record_one(p, 1080, 1920, outdir / "undertow-9x16.mp4", seconds=55.0)
        make_gif(outdir / "undertow-16x9.mp4")
    finally:
        server.terminate()
    print("wrote videos/undertow-16x9.mp4 videos/undertow-9x16.mp4 docs/screenshots/demo.gif docs/screenshots/hero.png")


if __name__ == "__main__":
    main()
