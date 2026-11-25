"""Strict voice-command grammar over known OSM street names.

The parser is intentionally deterministic and has no LLM. whisper.cpp/Piper are
optional local binaries; when absent the dashboard still accepts typed commands
through the same grammar.
"""

from __future__ import annotations

import shutil
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ParsedCommand:
    action: str
    name: str
    confidence: float = 1.0


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().casefold()
    return " ".join(text.replace("-", " ").replace("_", " ").split())


def parse_command(text: str, street_names: list[str]) -> ParsedCommand | None:
    """Parse only `close|open|reopen <known OSM street name>`."""
    cleaned = normalize(text)
    action = None
    for word, act in (("close", "close"), ("ferme", "close"), ("open", "open"), ("reopen", "open"), ("ouvre", "open")):
        if cleaned.startswith(word + " "):
            action = act
            remainder = cleaned[len(word) :].strip()
            break
    if action is None:
        return None
    by_norm = {normalize(name): name for name in street_names if name}
    if remainder in by_norm:
        return ParsedCommand(action, by_norm[remainder], 1.0)
    # Conservative containment match: the full known street name must be spoken.
    matches = [original for norm, original in by_norm.items() if norm and norm in remainder]
    if len(matches) == 1:
        return ParsedCommand(action, matches[0], 0.8)
    return None


def whisper_available() -> bool:
    return bool(shutil.which("whisper-cli") or shutil.which("whisper.cpp") or shutil.which("main"))


def piper_available() -> bool:
    return bool(shutil.which("piper"))


def transcribe_wav_whispercpp(wav_path: str, model_path: str) -> str | None:
    binary = shutil.which("whisper-cli") or shutil.which("whisper.cpp") or shutil.which("main") or "third_party/whisper.cpp/build/bin/whisper-cli"
    if not binary or not Path(binary).exists() and shutil.which(binary) is None:
        return None
    proc = subprocess.run(
        [binary, "-m", model_path, "-f", wav_path, "-nt", "-np"],
        text=True,
        capture_output=True,
        timeout=30,
    )
    if proc.returncode != 0:
        return None
    return " ".join(line.strip() for line in proc.stdout.splitlines() if line.strip())


def transcribe_browser_audio(blob: bytes, workdir: str, model_path: str = "models/ggml-base.en.bin") -> str | None:
    """Decode browser microphone audio with ffmpeg and transcribe via whisper.cpp."""
    import os
    import tempfile

    if not os.path.exists(model_path):
        return None
    with tempfile.TemporaryDirectory(dir=workdir) as tmp:
        src = os.path.join(tmp, "voice.webm")
        wav = os.path.join(tmp, "voice.wav")
        with open(src, "wb") as fh:
            fh.write(blob)
        conv = subprocess.run(
            ["ffmpeg", "-y", "-i", src, "-ar", "16000", "-ac", "1", wav],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        if conv.returncode != 0:
            return None
        return transcribe_wav_whispercpp(wav, model_path)


def synthesize_piper(text: str, wav_path: str, model_path: str = "models/piper-voice.onnx") -> bool:
    binary = shutil.which("piper")
    if not binary or not Path(model_path).exists():
        return False
    proc = subprocess.run(
        [binary, "--model", model_path, "--output_file", wav_path],
        input=text,
        text=True,
        capture_output=True,
        timeout=20,
    )
    return proc.returncode == 0 and Path(wav_path).exists()
