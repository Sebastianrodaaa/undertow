#!/usr/bin/env python3
"""Regenerate grayscale README plots and markdown tables from real results."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

OUT = Path("docs/screenshots")


def load_core(path: str = "results/core_arms.json") -> dict:
    return json.loads(Path(path).read_text())


def style() -> None:
    plt.rcParams.update({
        "figure.facecolor": "black",
        "axes.facecolor": "black",
        "savefig.facecolor": "black",
        "text.color": "white",
        "axes.labelcolor": "white",
        "xtick.color": "0.65",
        "ytick.color": "0.65",
        "axes.edgecolor": "0.35",
        "font.family": "monospace",
    })


def exact_plot(payload: dict) -> None:
    style()
    labels = ["undertow", "ablation", "restart"]
    vals = [payload["arms"][a]["exact_rate"] for a in "ABC"]
    err = []
    for a, v in zip("ABC", vals):
        lo, hi = payload["arms"][a]["exact_rate_ci95"]
        err.append([v - lo, hi - v])
    err = np.asarray(err).T
    fig, ax = plt.subplots(figsize=(7.5, 4), dpi=160)
    ax.bar(labels, vals, yerr=err, color=["white", "0.42", "0.72"], capsize=4)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("exact-trial rate")
    ax.set_title(payload["scale_label"], fontsize=10, color="0.65")
    for i, v in enumerate(vals):
        ax.text(i, min(1.0, v + 0.04), f"{v:.0%}", ha="center", color="white", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "results_exact.png")
    plt.close(fig)


def repair_plot(payload: dict) -> None:
    style()
    rows = payload["repair"]["A"]["rows"]
    ratios = [r["ratio"] for r in rows]
    names = [r["city"] for r in rows]
    fig, ax = plt.subplots(figsize=(7.5, 4), dpi=160)
    ax.scatter(np.arange(len(ratios)), ratios, color="white", s=18, alpha=0.85)
    ax.axhline(0.5, color="0.55", lw=1, ls="--")
    ax.axhline(1.0, color="0.3", lw=1, ls=":")
    ax.set_xticks(np.arange(len(ratios)))
    ax.set_xticklabels(names, rotation=65, ha="right", fontsize=7)
    ax.set_ylabel("repair loops / restart loops")
    ax.set_title("single-edit repair, undertow arm", fontsize=10, color="0.65")
    fig.tight_layout()
    fig.savefig(OUT / "results_repair.png")
    plt.close(fig)


def markdown_tables(payload: dict) -> str:
    lines = ["| arm | exact rate | 95% ci | wrong-cell fraction |", "|---|---:|---:|---:|"]
    names = {"A": "undertow", "B": "ablation", "C": "restart"}
    for key in "ABC":
        row = payload["arms"][key]
        lo, hi = row["exact_rate_ci95"]
        lines.append(f"| {names[key]} | {row['exact_rate']:.1%} | {lo:.1%}–{hi:.1%} | {row['wrong_fraction_mean']:.3%} |")
    repair = payload["repair"]["A"]
    lines += [
        "",
        "| measure | value |",
        "|---|---:|",
        f"| median repair loops | {repair['median_repair_loops']:.0f} |",
        f"| median restart loops | {repair['median_restart_loops']:.0f} |",
        f"| median repair/restart | {repair['median_ratio']:.2f} |",
        f"| cpu throughput | {np.mean([x['loops_per_second'] for x in payload['throughput']]):.0f} loops/s |",
        f"| written weights | {payload['weight_count']:,} |",
    ]
    return "\n".join(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    payload = load_core()
    exact_plot(payload)
    repair_plot(payload)
    tables = markdown_tables(payload)
    Path("results/readme_tables.md").write_text(tables + "\n")
    print(tables)


if __name__ == "__main__":
    main()
