from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import default_config, load_config
from .learning import run_type_level_learning
from .experiments import (
    run_confirmation_diagnostics,
    run_equilibrium_experiment,
    run_policy_sweep,
    run_scenario_comparison,
)
from .reporting import write_csv, write_json
from .simulator import run_simulation
from .strategies import Strategy
from .visualization import (
    plot_confirmation_by_congestion,
    plot_learning_history,
    plot_scenario_comparison,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="waitlist-hedging",
        description="Simulate strategic waitlist hedging and railway policy rules.",
    )
    parser.add_argument("--config", type=Path, default=None, help="JSON model configuration")
    parser.add_argument("--output", type=Path, default=Path("outputs"), help="Output directory")
    subparsers = parser.add_subparsers(dest="command", required=True)

    simulate = subparsers.add_parser("simulate", help="Run one simulation seed")
    simulate.add_argument("--strategy", default="hedge2_late")
    simulate.add_argument("--seed", type=int, default=None)

    scenarios = subparsers.add_parser("scenarios", help="Compare fixed strategy baselines")
    scenarios.add_argument("--runs", type=int, default=20)
    scenarios.add_argument("--seed-start", type=int, default=2000)

    equilibrium = subparsers.add_parser("equilibrium", help="Compute type-level best-response equilibrium")
    equilibrium.add_argument("--runs", type=int, default=6)
    equilibrium.add_argument("--seed-start", type=int, default=4000)
    equilibrium.add_argument("--max-iterations", type=int, default=12)

    sweep = subparsers.add_parser("sweep", help="Compare caps, refunds, and chart times")
    sweep.add_argument("--runs", type=int, default=3)
    sweep.add_argument("--seed-start", type=int, default=6000)
    sweep.add_argument("--solve-equilibrium", action="store_true")

    diagnose = subparsers.add_parser("diagnose", help="Measure congestion-dependent confirmation rates")
    diagnose.add_argument("--runs", type=int, default=30)
    diagnose.add_argument("--seed-start", type=int, default=8000)

    learn = subparsers.add_parser("learn", help="Run type-level reinforcement learning over seasons")
    learn.add_argument("--seasons", type=int, default=100)
    learn.add_argument("--alpha", type=float, default=0.15)
    learn.add_argument("--epsilon", type=float, default=0.20)
    learn.add_argument("--epsilon-decay", type=float, default=0.985)
    learn.add_argument("--seed-start", type=int, default=15000)

    all_runs = subparsers.add_parser("all", help="Run baselines, equilibrium, and confirmation diagnostics")
    all_runs.add_argument("--runs", type=int, default=20)
    all_runs.add_argument("--equilibrium-runs", type=int, default=4)
    all_runs.add_argument("--diagnostic-runs", type=int, default=20)
    all_runs.add_argument("--with-sweep", action="store_true")
    all_runs.add_argument("--solve-sweep-equilibrium", action="store_true")
    all_runs.add_argument("--with-learning", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    config = load_config(args.config) if args.config else default_config()
    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.command == "simulate":
        profile = {
            row.name: Strategy.from_name(args.strategy)
            for row in config.traveller_types
        }
        outcome = run_simulation(config, seed=args.seed, strategy_profile=profile)
        write_json(output_dir / "single_run.json", {
            "seed": outcome.seed,
            "strategy_profile": outcome.type_strategy_profile,
            "metrics": outcome.metrics,
            "train_records": outcome.train_records,
            "ticket_records": outcome.ticket_records,
        })
        print(json.dumps(outcome.metrics, indent=2))
        print(f"Saved: {output_dir / 'single_run.json'}")
        return

    if args.command == "scenarios":
        rows, outcomes = run_scenario_comparison(config, args.runs, args.seed_start)
        write_csv(output_dir / "scenario_comparison.csv", rows)
        write_json(output_dir / "scenario_comparison.json", rows)
        plot_scenario_comparison(rows, output_dir / "figures")
        diagnostic_rows = []
        for scenario, scenario_outcomes in outcomes.items():
            diagnostic_rows.append({
                "scenario": scenario,
                **independence_diagnostic(scenario_outcomes),
            })
        write_csv(output_dir / "independence_diagnostic.csv", diagnostic_rows)
        print(f"Saved scenario results and plots to: {output_dir}")
        return

    if args.command == "equilibrium":
        result = run_equilibrium_experiment(
            config,
            evaluation_runs=args.runs,
            seed_start=args.seed_start,
            max_iterations=args.max_iterations,
        )
        write_json(output_dir / "equilibrium.json", result)
        write_csv(output_dir / "equilibrium_history.csv", result["history"])
        print(json.dumps({key: value for key, value in result.items() if key != "history"}, indent=2))
        print(f"Saved: {output_dir / 'equilibrium.json'}")
        return

    if args.command == "sweep":
        rows = run_policy_sweep(
            config,
            runs_per_policy=args.runs,
            seed_start=args.seed_start,
            solve_equilibrium=args.solve_equilibrium,
        )
        write_csv(output_dir / "policy_sweep.csv", rows)
        write_json(output_dir / "policy_sweep.json", rows)
        print(f"Saved {len(rows)} policy combinations to: {output_dir}")
        return

    if args.command == "learn":
        result = run_type_level_learning(
            config,
            seasons=args.seasons,
            alpha=args.alpha,
            epsilon=args.epsilon,
            epsilon_decay=args.epsilon_decay,
            seed_start=args.seed_start,
        )
        write_csv(output_dir / "learning_history.csv", result["history"])
        plot_learning_history(result["history"], output_dir / "figures" / "learning_reward_by_season.png")
        write_json(output_dir / "learned_policy.json", {
            key: value for key, value in result.items() if key != "history"
        })
        print(json.dumps({key: value for key, value in result.items() if key != "history"}, indent=2))
        print(f"Saved learning results to: {output_dir}")
        return

    if args.command == "diagnose":
        congestion_rows, position_rows, independence = run_confirmation_diagnostics(
            config, runs=args.runs, seed_start=args.seed_start
        )
        write_csv(output_dir / "confirmation_by_congestion.csv", congestion_rows)
        write_csv(output_dir / "confirmation_by_waitlist_position.csv", position_rows)
        write_json(output_dir / "independence_diagnostic.json", independence)
        if congestion_rows:
            plot_confirmation_by_congestion(
                congestion_rows,
                output_dir / "figures" / "confirmation_by_congestion.png",
            )
        print(json.dumps(independence, indent=2))
        print(f"Saved diagnostics to: {output_dir}")
        return

    if args.command == "all":
        scenario_rows, scenario_outcomes = run_scenario_comparison(
            config, runs=args.runs, seed_start=2000
        )
        write_csv(output_dir / "scenario_comparison.csv", scenario_rows)
        write_json(output_dir / "scenario_comparison.json", scenario_rows)
        plot_scenario_comparison(scenario_rows, output_dir / "figures")
        equilibrium_result = run_equilibrium_experiment(
            config,
            evaluation_runs=args.equilibrium_runs,
            seed_start=4000,
        )
        write_json(output_dir / "equilibrium.json", equilibrium_result)
        write_csv(output_dir / "equilibrium_history.csv", equilibrium_result["history"])
        congestion_rows, position_rows, independence = run_confirmation_diagnostics(
            config, runs=args.diagnostic_runs, seed_start=8000
        )
        write_csv(output_dir / "confirmation_by_congestion.csv", congestion_rows)
        write_csv(output_dir / "confirmation_by_waitlist_position.csv", position_rows)
        write_json(output_dir / "independence_diagnostic.json", independence)
        if congestion_rows:
            plot_confirmation_by_congestion(
                congestion_rows,
                output_dir / "figures" / "confirmation_by_congestion.png",
            )
        if args.with_learning:
            learning_result = run_type_level_learning(config, seasons=60, seed_start=15000)
            write_csv(output_dir / "learning_history.csv", learning_result["history"])
            plot_learning_history(
                learning_result["history"],
                output_dir / "figures" / "learning_reward_by_season.png",
            )
            write_json(output_dir / "learned_policy.json", {
                key: value for key, value in learning_result.items() if key != "history"
            })
        if args.with_sweep:
            sweep_rows = run_policy_sweep(
                config,
                runs_per_policy=max(2, args.equilibrium_runs),
                seed_start=6000,
                solve_equilibrium=args.solve_sweep_equilibrium,
            )
            write_csv(output_dir / "policy_sweep.csv", sweep_rows)
            write_json(output_dir / "policy_sweep.json", sweep_rows)
        print(f"Completed experiment suite. Results are in: {output_dir}")
        return


if __name__ == "__main__":
    main()
