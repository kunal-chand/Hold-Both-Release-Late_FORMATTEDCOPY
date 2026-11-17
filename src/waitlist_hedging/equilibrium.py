from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any, Mapping

from .config import SimulationConfig
from .simulator import BookingSimulator, run_simulation
from .strategies import Strategy, available_strategies


@dataclass
class EquilibriumResult:
    strategy_profile: dict[str, Strategy]
    converged: bool
    cycle_detected: bool
    iterations: int
    history: list[dict[str, Any]]
    best_response_gaps: dict[str, float]
    outcome_summary: dict[str, float]


def default_profile(config: SimulationConfig, strategy_name: str = "single") -> dict[str, Strategy]:
    strategy = Strategy.from_name(strategy_name)
    return {traveller_type.name: strategy for traveller_type in config.traveller_types}


def representative_ids(config: SimulationConfig, seed: int) -> dict[str, int]:
    builder = BookingSimulator(config, seed)
    builder.build_population()
    result: dict[str, int] = {}
    for traveller in builder.travellers.values():
        result.setdefault(traveller.type_name, traveller.traveller_id)
    return result


def focal_strategy_payoff(
    config: SimulationConfig,
    profile: Mapping[str, Strategy],
    focal_type: str,
    candidate: Strategy,
    seeds: list[int],
) -> float:
    payoffs: list[float] = []
    for seed in seeds:
        focal_id = representative_ids(config, seed)[focal_type]
        outcome = run_simulation(
            config,
            seed=seed,
            strategy_profile=profile,
            strategy_overrides={focal_id: candidate},
        )
        focal_result = next(
            row for row in outcome.traveller_outcomes if row.traveller_id == focal_id
        )
        payoffs.append(focal_result.utility)
    return mean(payoffs)


def summarize_profile(
    config: SimulationConfig,
    profile: Mapping[str, Strategy],
    seeds: list[int],
) -> dict[str, float]:
    outcomes = [
        run_simulation(config, seed=seed, strategy_profile=profile)
        for seed in seeds
    ]
    metric_names = outcomes[0].metrics.keys()
    return {
        metric: mean(outcome.metrics[metric] for outcome in outcomes)
        for metric in metric_names
    }


def find_equilibrium(
    config: SimulationConfig,
    initial_profile: Mapping[str, Strategy] | None = None,
    evaluation_runs: int = 8,
    seed_start: int = 1000,
    max_iterations: int = 20,
) -> EquilibriumResult:
    if evaluation_runs < 1:
        raise ValueError("evaluation_runs must be at least 1.")
    if max_iterations < 1:
        raise ValueError("max_iterations must be at least 1.")

    profile = dict(initial_profile or default_profile(config))
    strategies = available_strategies(len(config.trains))
    type_names = [row.name for row in config.traveller_types]
    evaluation_seeds = [seed_start + index for index in range(evaluation_runs)]
    history: list[dict[str, Any]] = []
    visited: dict[tuple[tuple[str, str], ...], int] = {}
    cycle_detected = False
    converged = False
    iterations = 0

    def profile_key(candidate: Mapping[str, Strategy]) -> tuple[tuple[str, str], ...]:
        return tuple((name, candidate[name].name) for name in type_names)

    visited[profile_key(profile)] = 0
    for iteration in range(1, max_iterations + 1):
        iterations = iteration
        changes_this_round = 0
        for type_name in type_names:
            payoffs = {
                strategy.name: focal_strategy_payoff(
                    config,
                    profile,
                    type_name,
                    strategy,
                    evaluation_seeds,
                )
                for strategy in strategies
            }
            current_name = profile[type_name].name
            best_value = max(payoffs.values())
            if payoffs[current_name] >= best_value - 1e-8:
                chosen_name = current_name
            else:
                chosen_name = sorted(
                    name for name, value in payoffs.items() if value >= best_value - 1e-8
                )[0]
            chosen = Strategy.from_name(chosen_name)
            history.append(
                {
                    "iteration": iteration,
                    "traveller_type": type_name,
                    "old_strategy": current_name,
                    "new_strategy": chosen_name,
                    "current_payoff": payoffs[current_name],
                    "best_payoff": best_value,
                    "best_response_gain": best_value - payoffs[current_name],
                    "payoffs": payoffs,
                }
            )
            if chosen_name != current_name:
                profile[type_name] = chosen
                changes_this_round += 1

        if changes_this_round == 0:
            converged = True
            break
        key = profile_key(profile)
        if key in visited:
            cycle_detected = True
            break
        visited[key] = iteration

    best_response_gaps: dict[str, float] = {}
    for type_name in type_names:
        payoffs = {
            strategy.name: focal_strategy_payoff(
                config,
                profile,
                type_name,
                strategy,
                evaluation_seeds,
            )
            for strategy in strategies
        }
        best_response_gaps[type_name] = max(payoffs.values()) - payoffs[profile[type_name].name]

    outcome_seeds = [seed_start + 10000 + index for index in range(evaluation_runs)]
    outcome_summary = summarize_profile(config, profile, outcome_seeds)
    return EquilibriumResult(
        strategy_profile=profile,
        converged=converged,
        cycle_detected=cycle_detected,
        iterations=iterations,
        history=history,
        best_response_gaps=best_response_gaps,
        outcome_summary=outcome_summary,
    )


def profile_from_names(names: Mapping[str, str]) -> dict[str, Strategy]:
    return {type_name: Strategy.from_name(strategy_name) for type_name, strategy_name in names.items()}
