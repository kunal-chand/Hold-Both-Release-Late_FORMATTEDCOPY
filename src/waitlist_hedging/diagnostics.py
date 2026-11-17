from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any, Iterable

from .models import SimulationOutcome
from .strategies import Strategy


def aggregate_outcomes(outcomes: Iterable[SimulationOutcome]) -> dict[str, float]:
    rows = list(outcomes)
    if not rows:
        return {}
    metrics = rows[0].metrics.keys()
    return {name: mean(row.metrics[name] for row in rows) for name in metrics}


def confirmation_by_hedger_congestion(
    outcomes: Iterable[SimulationOutcome],
) -> list[dict[str, float]]:
    groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for outcome in outcomes:
        for record in outcome.ticket_records:
            if record["was_waitlisted"]:
                groups[int(record["other_hedgers_on_train"])].append(record)
    result = []
    for congestion, records in sorted(groups.items()):
        result.append(
            {
                "other_hedgers_on_train": float(congestion),
                "waitlisted_tickets": float(len(records)),
                "confirmation_probability": mean(
                    float(record["confirmed_before_chart"]) for record in records
                ),
            }
        )
    return result


def independence_diagnostic(
    outcomes: Iterable[SimulationOutcome],
) -> dict[str, float]:
    rows = list(outcomes)
    attempts_by_train: dict[int, list[bool]] = defaultdict(list)
    for outcome in rows:
        for record in outcome.ticket_records:
            attempts_by_train[int(record["train_index"])].append(
                bool(record["confirmed_at_departure"])
            )

    marginal_probabilities = {
        train_index: mean(float(value) for value in values)
        for train_index, values in attempts_by_train.items()
        if values
    }
    actual_any: list[float] = []
    independent_any: list[float] = []
    for outcome in rows:
        for traveller in outcome.traveller_outcomes:
            if len(traveller.booked_train_indices) <= 1:
                continue
            actual_any.append(float(bool(traveller.confirmed_train_indices)))
            not_confirmed = 1.0
            for train_index in set(traveller.booked_train_indices):
                p = marginal_probabilities.get(train_index, 0.0)
                not_confirmed *= 1.0 - p
            independent_any.append(1.0 - not_confirmed)
    return {
        "hedger_observations": float(len(actual_any)),
        "actual_any_train_confirmation": mean(actual_any) if actual_any else 0.0,
        "independence_prediction": mean(independent_any) if independent_any else 0.0,
        "absolute_gap": abs(mean(actual_any) - mean(independent_any)) if actual_any else 0.0,
    }


def strategy_profile_from_outcome(outcome: SimulationOutcome) -> dict[str, Strategy]:
    return {
        name: Strategy.from_name(strategy_name)
        for name, strategy_name in outcome.type_strategy_profile.items()
        if name != "focal_overrides"
    }


def confirmation_by_waitlist_position(
    outcomes: Iterable[SimulationOutcome],
) -> list[dict[str, float]]:
    groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for outcome in outcomes:
        for record in outcome.ticket_records:
            if record["was_waitlisted"] and record["waitlist_position"] is not None:
                groups[int(record["waitlist_position"])].append(record)
    return [
        {
            "waitlist_position": float(position),
            "waitlisted_tickets": float(len(records)),
            "confirmation_probability": mean(
                float(record["confirmed_before_chart"]) for record in records
            ),
        }
        for position, records in sorted(groups.items())
    ]
