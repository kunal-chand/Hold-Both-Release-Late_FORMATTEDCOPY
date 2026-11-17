from __future__ import annotations

from pathlib import Path
from typing import Any


def plot_scenario_comparison(rows: list[dict[str, Any]], output_dir: str | Path) -> list[Path]:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("Install matplotlib to generate plots: pip install matplotlib") from exc

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    scenarios = [row["scenario"] for row in rows]
    for metric, ylabel, filename in (
        ("social_welfare", "Social welfare (model units)", "social_welfare_by_scenario.png"),
        ("empty_berth_share", "Empty berths / total capacity", "empty_berth_share_by_scenario.png"),
        ("travel_probability", "Share of travellers who travel", "travel_probability_by_scenario.png"),
        ("refunds_paid", "Refunds paid (INR model units)", "refunds_paid_by_scenario.png"),
    ):
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.bar(scenarios, [row.get(metric, 0.0) for row in rows])
        ax.set_ylabel(ylabel)
        ax.set_title(metric.replace("_", " ").title())
        ax.tick_params(axis="x", labelrotation=20)
        fig.tight_layout()
        path = output / filename
        fig.savefig(path, dpi=160)
        plt.close(fig)
        paths.append(path)
    return paths


def plot_confirmation_by_congestion(
    rows: list[dict[str, float]], output_path: str | Path
) -> Path:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("Install matplotlib to generate plots: pip install matplotlib") from exc
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(
        [row["other_hedgers_on_train"] for row in rows],
        [row["confirmation_probability"] for row in rows],
        marker="o",
    )
    ax.set_xlabel("Other hedging travellers booking the same train")
    ax.set_ylabel("P(waitlisted ticket confirms before chart)")
    ax.set_ylim(0, 1)
    ax.set_title("Confirmation probability under endogenous congestion")
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)
    return output


def plot_learning_history(rows: list[dict[str, Any]], output_path: str | Path) -> Path:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("Install matplotlib to generate plots: pip install matplotlib") from exc
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    by_season: dict[int, list[float]] = {}
    for row in rows:
        by_season.setdefault(int(row["season"]), []).append(float(row["mean_private_utility"]))
    seasons = sorted(by_season)
    averages = [sum(by_season[season]) / len(by_season[season]) for season in seasons]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(seasons, averages)
    ax.set_xlabel("Booking season")
    ax.set_ylabel("Mean type-level private utility")
    ax.set_title("Type-level reinforcement learning")
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)
    return output
