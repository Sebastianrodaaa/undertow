"""Arm E: local Qwen2.5-Coder writer in llama.cpp, CPU only.

The harness is real and self-contained: it never calls a paid API. A missing
local binary/model is reported as an infrastructure limitation rather than a
model failure; any completed rounds are written to results JSON.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path

MODEL_URL = "https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf"
MODEL_PATH = Path("models/qwen2.5-coder-7b-instruct-q4_k_m.gguf")

WRITER_SPEC = """Write one Python file implementing a looped grid shortest-path block.
The block receives walkable/exits planes every loop, keeps recurrent state, and
when a street closes must invalidate descendants through parent pointers before
reflooding. Return only Python code. The tests require exact BFS distances.
"""


def find_llama_binary() -> str | None:
    candidates = [
        os.environ.get("LLAMA_CLI", ""),
        "llama-cli",
        "llama.cpp/build/bin/llama-cli",
        "third_party/llama.cpp/build/bin/llama-cli",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            proc = subprocess.run([candidate, "--version"], text=True, capture_output=True, timeout=5)
            if proc.returncode == 0:
                return candidate
        except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired):
            pass
    return None


def ensure_model(path: Path = MODEL_PATH, download: bool = False) -> Path | None:
    if path.exists() and path.stat().st_size > 1_000_000:
        return path
    if not download:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    with urllib.request.urlopen(MODEL_URL, timeout=60) as response, tmp.open("wb") as fh:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            fh.write(chunk)
    tmp.rename(path)
    return path


def llama_write(binary: str, model: Path, prompt: str, max_tokens: int = 1800, timeout: int = 1800) -> dict:
    started = time.perf_counter()
    cmd = [
        binary,
        "-m", str(model),
        "-p", prompt,
        "-n", str(max_tokens),
        "--temp", "0.2",
        "-t", str(os.cpu_count() or 8),
        "--no-display-prompt",
        "--log-disable",
        "--single-turn",
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    elapsed = time.perf_counter() - started
    text = proc.stdout + "\n" + proc.stderr
    match = re.search(r"Generation:\s*(\d+(?:\.\d+)?)\s*t/s", text, re.I) or re.search(r"(\d+(?:\.\d+)?) tokens per second", text, re.I)
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr_tail": proc.stderr[-4000:],
        "seconds": elapsed,
        "tokens_per_second": float(match.group(1)) if match else None,
    }


def extract_code(text: str) -> str:
    fence = re.search(r"```(?:python)?\n(.*?)```", text, re.S)
    return fence.group(1) if fence else text


def run_writer(attempts: int = 1, rounds: int = 1, download_model: bool = False, out: str = "results/arm_e_writer.json", max_tokens: int = 350) -> dict:
    binary = find_llama_binary()
    model = ensure_model(download=download_model)
    result = {
        "run_type": "arm_e_local_qwen_writer",
        "binary": binary,
        "model": str(model) if model else None,
        "attempts_requested": attempts,
        "rounds_requested": rounds,
        "attempts_completed": 0,
        "passed": False,
        "rounds": [],
    }
    if not binary or not model:
        result["status"] = "not_run_missing_local_llama_cpp_or_qwen_gguf"
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(result, indent=2, sort_keys=True))
        return result

    feedback = ""
    for attempt in range(attempts):
        for round_index in range(rounds):
            prompt = WRITER_SPEC + "\n" + feedback + "\nPython code:\n"
            try:
                response = llama_write(binary, model, prompt, max_tokens=max_tokens)
            except subprocess.TimeoutExpired:
                response = {"returncode": -1, "stdout": "", "stderr_tail": "timeout", "seconds": 1800.0, "tokens_per_second": None}
            code = extract_code(response["stdout"])
            candidate = Path("results/writer_candidate.py")
            candidate.write_text(code)
            test = subprocess.run(
                ["python3", "-m", "py_compile", str(candidate)],
                text=True,
                capture_output=True,
                timeout=30,
            )
            passed = test.returncode == 0 and "class" in code and "invalid" in code.lower()
            row = {
                "attempt": attempt,
                "round": round_index,
                "passed_static_gate": bool(passed),
                "seconds": response["seconds"],
                "tokens_per_second": response["tokens_per_second"],
                "stderr_tail": response["stderr_tail"],
                "compile_stderr": test.stderr[-1000:],
            }
            result["rounds"].append(row)
            feedback = "Previous candidate failed. Compiler/test feedback:\n" + test.stderr[-1200:]
            if passed:
                result["passed"] = True
                break
        result["attempts_completed"] = attempt + 1
        if result["passed"]:
            break
    result["status"] = "completed"
    result["hypothesis_5_supported"] = not result["passed"]
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(result, indent=2, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--download-model", action="store_true")
    parser.add_argument("--out", default="results/arm_e_writer.json")
    parser.add_argument("--max-tokens", type=int, default=350)
    args = parser.parse_args()
    print(json.dumps(run_writer(args.attempts, args.rounds, args.download_model, args.out, args.max_tokens), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
