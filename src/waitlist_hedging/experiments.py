from __future__ import annotations

from dataclasses import replace
from itertools import product
from statistics import mean
from typing import Any

from .config import SimulationConfig
from .diagnostics import (
    aggregate_outcomes,
    confirmation_by_hedger_congestion,
    confirmation_by_waitlist_position,
    independence_diagnostic,
)
from .equilibrium import default_profile, find_equilibrium
from .models import SimulationOutcome
from .planner import planner_benchmark
from .simulator import run_simulation
from .strategies import Strategy


def scenario_profiles(config: SimulationConfig) -> dict[str, dict[str, Strategy]]:
    type_names = [row.name for row in config.traveller_types]
    profiles: dict[str, dict[str, Strategy]] = {}
    definitions = {
        "no_hedging": "single",
        "all_hedge2_timely": "hedge2_timely",
        "all_hedge2_late": "hedge2_late",
        "all_hedge3_late": "hedge3_late",
    }
    for scenario, strategy_name in definitions.items():
        strategy = Strategy.from_name(strategy_name)
        if strategy.booking_count > len(config.trains):
            continue
        profiles[scenario] = {type_name: strategy for type_name in type_names}
    return profiles


def run_scenario_comparison(
    config: SimulationConfig,
    runs: int = 20,
    seed_start: int = 2000,
) -> tuple[list[dict[str, Any]], dict[str, list[SimulationOutcome]]]:
    if runs < 1:
        raise ValueError("runs must be at least 1.")
    rows: list[dict[str, Any]] = []
    all_outcomes: dict[str, list[SimulationOutcome]] = {}
    for scenario, profile in scenario_profiles(config).items():
        outcomes = [
            run_simulation(config, seed=seed_start + index, strategy_profile=profile)
            for index in range(runs)
        ]
        all_outcomes[scenario] = outcomes
        rows.append({"scenario": scenario, "runs": runs, **aggregate_outcomes(outcomes)})
    rows.append({
        "scenario": "planner_optimum",
        "runs": runs,
        **planner_benchmark(config, runs=runs, seed_start=seed_start + 20000),
    })
    return rows, all_outcomes


def run_equilibrium_experiment(
    config: SimulationConfig,
    evaluation_runs: int = 6,
    seed_start: int = 4000,
    max_iterations: int = 12,
) -> dict[str, Any]:
    result = find_equilibrium(
        config,
        initial_profile=default_profile(config, "single"),
        evaluation_runs=evaluation_runs,
        seed_start=seed_start,
        max_iterations=max_iterations,
    )
    return {
        "strategy_profile": {
            name: strategy.name for name, strategy in result.strategy_profile.items()
        },
        "converged": result.converged,
        "cycle_detected": result.cycle_detected,
        "iterations": result.iterations,
        "best_response_gaps": result.best_response_gaps,
        "outcome_summary": result.outcome_summary,
        "history": result.history,
    }


def run_policy_sweep(
    config: SimulationConfig,
    runs_per_policy: int = 3,
    seed_start: int = 6000,
    cap_values: tuple[float, ...] = (0.15, 0.25, 0.35),
    refund_values: tuple[float, ...] = (0.0, 30.0),
    chart_values: tuple[float, ...] = (4.0, 8.0, 10.0),
    solve_equilibrium: bool = False,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    policy_index = 0
    for cap, refund, chart_hours in product(cap_values, refund_values, chart_values):
        policy_config = replace(
            config,
            waitlist_cap_fraction=cap,
            early_release_refund=refund,
            chart_hours_before_departure=chart_hours,
        )
        policy_config.validate()
        policy_seed = seed_start + policy_index * 100
        if solve_equilibrium:
            equilibrium = find_equilibrium(
                policy_config,
                initial_profile=default_profile(policy_config, "single"),
                evaluation_runs=max(2, runs_per_policy),
                seed_start=policy_seed,
                max_iterations=8,
            )
            profile = equilibrium.strategy_profile
            equilibrium_status = "cycle" if equilibrium.cycle_detected else (
                "converged" if equilibrium.converged else "iteration_limit"
            )
            summary = equilibrium.outcome_summary
            strategy_profile = ";".join(
                f"{name}:{strategy.name}" for name, strategy in profile.items()
            )
        else:
            profile = {
                row.name: Strategy.from_name("hedge2_late")
                for row in policy_config.traveller_types
            }
            outcomes = [
                run_simulation(
                    policy_config,
                    seed=policy_seed + index,
                    strategy_profile=profile,
                )
                for index in range(runs_per_policy)
            ]
            summary = aggregate_outcomes(outcomes)
            equilibrium_status = "not_solved"
            strategy_profile = ";".join(
                f"{name}:{strategy.name}" for name, strategy in profile.items()
            )
        rows.append(
            {
                "waitlist_cap_fraction": cap,
                "early_release_refund": refund,
                "chart_hours_before_departure": chart_hours,
                "equilibrium_status": equilibrium_status,
                "strategy_profile": strategy_profile,
                **summary,
            }
        )
        policy_index += 1
    return rows


def run_confirmation_diagnostics(
    config: SimulationConfig,
    runs: int = 30,
    seed_start: int = 8000,
) -> tuple[list[dict[str, float]], dict[str, float]]:
    profile = {
        row.name: Strategy.from_name("hedge2_late")
        for row in config.traveller_types
    }
    outcomes = [
        run_simulation(config, seed=seed_start + index, strategy_profile=profile)
        for index in range(runs)
    ]
    return (
        confirmation_by_hedger_congestion(outcomes),
        confirmation_by_waitlist_position(outcomes),
        independence_diagnostic(outcomes),
    )
