# launch-film shot list

Committed real captures are in this directory. They are screen recordings of the actual websocket-backed replay dashboard, not mockups. Grayscale README derivatives live in `docs/screenshots/`.

| shot | file | duration | action |
|---|---|---:|---|
| 16:9 launch plate | `undertow-16x9.mp4` | 55 s | Paris replay boots; the forward tide fills; Pont Neuf is closed mid-run; invalidation retreats; the oracle lamp moves through repair; the rapid logged edit sequence runs and the ablation split is toggled. Browser video capture slows the websocket before the scripted endcard threshold; the endcard remains implemented in the app but is not reached inside this real capture. |
| 9:16 vertical cut | `undertow-9x16.mp4` | 55 s | Same real run framed for short-form video. |
| README loop | `../docs/screenshots/demo.gif` | about 18 s | Grayscale 8 fps conversion of the 16:9 capture. |
| Hero still | `../docs/screenshots/hero.png` | still | Grayscale 1920x1080 capture from a fresh replay. |

Production notes:

- Source viewport: exact 1920x1080 and 1080x1920.
- Capture path: Playwright real Chrome video, converted with ffmpeg to H.264 MP4.
- No frame is hand-drawn; every map frame is decoded from the binary state stream.
- Replay is deterministic re-simulation from the committed real-event JSONL log. The speed parameter is real wall-clock target speed, but browser serialization can lower achieved frame throughput; the KPI reports isolated model throughput separately.
- The launch capture uses a 240 loops/s target so the complete real event log fits the film; achieved browser throughput is lower under video capture, while the isolated CPU KPI is shown in-frame. Loop count and oracle state are visible in-frame.
