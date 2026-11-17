from __future__ import annotations

import random
from statistics import mean
from typing import Any

from .config import SimulationConfig
from .simulator import run_simulation
from .strategies import Strategy, available_strategies


def run_type_level_learning(
    config: SimulationConfig,
    seasons: int = 100,
    alpha: float = 0.15,
    epsilon: float = 0.20,
    epsilon_decay: float = 0.985,
    epsilon_min: float = 0.02,
    seed_start: int = 15000,
) -> dict[str, Any]:
    if seasons < 1:
        raise ValueError("seasons must be at least 1.")
    if not 0.0 < alpha <= 1.0:
        raise ValueError("alpha must be in (0, 1].")
    if not 0.0 <= epsilon <= 1.0 or not 0.0 <= epsilon_min <= 1.0:
        raise ValueError("epsilon values must be between 0 and 1.")
    if not 0.0 < epsilon_decay <= 1.0:
        raise ValueError("epsilon_decay must be in (0, 1].")

    rng = random.Random(seed_start)
    types = [row.name for row in config.traveller_types]
    strategies = available_strategies(len(config.trains))
    strategy_names = [strategy.name for strategy in strategies]
    q_values = {
        type_name: {strategy_name: 0.0 for strategy_name in strategy_names}
        for type_name in types
    }
    action_counts = {
        type_name: {strategy_name: 0 for strategy_name in strategy_names}
        for type_name in types
    }
    exploration_orders = {
        type_name: list(strategy_names)
        for type_name in types
    }
    for order in exploration_orders.values():
        rng.shuffle(order)

    history: list[dict[str, Any]] = []
    for season in range(seasons):
        epsilon_now = max(epsilon_min, epsilon * (epsilon_decay ** season))
        profile: dict[str, Strategy] = {}
        for type_name in types:
            untried = [
                name for name in exploration_orders[type_name]
                if action_counts[type_name][name] == 0
            ]
            if untried:
                chosen_name = untried[0]
            elif rng.random() < epsilon_now:
                chosen_name = rng.choice(strategy_names)
            else:
                best_q = max(q_values[type_name].values())
                best_actions = [
                    name for name, value in q_values[type_name].items()
                    if value >= best_q - 1e-10
                ]
                chosen_name = rng.choice(best_actions)
            profile[type_name] = Strategy.from_name(chosen_name)

        outcome = run_simulation(
            config,
            seed=seed_start + 1000 + season,
            strategy_profile=profile,
        )
        for type_name in types:
            rewards = [
                traveller.utility
                for traveller in outcome.traveller_outcomes
                if traveller.type_name == type_name
            ]
            reward = mean(rewards) if rewards else 0.0
            chosen_name = profile[type_name].name
            old_q = q_values[type_name][chosen_name]
            q_values[type_name][chosen_name] = old_q + alpha * (reward - old_q)
            action_counts[type_name][chosen_name] += 1
            history.append(
                {
                    "season": season + 1,
                    "traveller_type": type_name,
                    "strategy": chosen_name,
                    "mean_private_utility": reward,
                    "q_value_after_update": q_values[type_name][chosen_name],
                    "epsilon": epsilon_now,
                    "action_count": action_counts[type_name][chosen_name],
                    "social_welfare": outcome.metrics["social_welfare"],
                    "travel_probability": outcome.metrics["travel_probability"],
                    "empty_berth_share": outcome.metrics["empty_berth_share"],
                }
            )

    learned_policy = {
        type_name: max(q_values[type_name], key=q_values[type_name].get)
        for type_name in types
    }
    return {
        "seasons": seasons,
        "alpha": alpha,
        "initial_epsilon": epsilon,
        "epsilon_decay": epsilon_decay,
        "epsilon_min": epsilon_min,
        "learned_policy": learned_policy,
        "q_values": q_values,
        "action_counts": action_counts,
        "history": history,
    }
