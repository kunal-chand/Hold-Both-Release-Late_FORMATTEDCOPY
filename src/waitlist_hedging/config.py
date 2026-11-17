from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TrainSpec:
    name: str
    capacity: int
    fare: float


@dataclass(frozen=True)
class TravellerType:
    name: str
    share: float
    values: tuple[float, ...]
    outside_option: float
    plan_change_probability: float = 0.04
    cancellation_hassle: float = 2.0
    value_noise_sd: float = 4.0


@dataclass(frozen=True)
class SimulationConfig:
    trains: tuple[TrainSpec, ...]
    traveller_types: tuple[TravellerType, ...]
    population_size: int = 120
    waitlist_cap_fraction: float = 0.25
    early_release_refund: float = 0.0
    refund_eligibility_hours_before_departure: float = 24.0
    chart_hours_before_departure: float = 8.0
    resale_probability: float = 0.25
    waitlist_cancel_fee: float = 60.0
    confirmed_cancel_fee_early: float = 80.0
    confirmed_cancel_fee_post_chart: float = 150.0
    empty_berth_cost: float = 25.0
    booking_earliest_hours: float = 72.0
    booking_latest_hours: float = 12.0
    default_strategy: str = "single"
    seed: int = 329

    def validate(self) -> None:
        if not 2 <= len(self.trains) <= 5:
            raise ValueError("The model expects between 2 and 5 trains.")
        if self.population_size < 1:
            raise ValueError("population_size must be positive.")
        if not 0.0 <= self.waitlist_cap_fraction <= 1.0:
            raise ValueError("waitlist_cap_fraction must be between 0 and 1.")
        if not 0.0 <= self.resale_probability <= 1.0:
            raise ValueError("resale_probability must be between 0 and 1.")
        if self.chart_hours_before_departure < 0:
            raise ValueError("chart_hours_before_departure cannot be negative.")
        if self.refund_eligibility_hours_before_departure < 0:
            raise ValueError("refund_eligibility_hours_before_departure cannot be negative.")
        if self.booking_latest_hours <= self.chart_hours_before_departure:
            raise ValueError(
                "booking_latest_hours must be greater than chart_hours_before_departure "
                "so the configured booking window occurs before charting."
            )
        if self.booking_earliest_hours < self.booking_latest_hours:
            raise ValueError("booking_earliest_hours must be >= booking_latest_hours.")
        if any(t.capacity < 1 for t in self.trains):
            raise ValueError("Every train must have at least one berth.")
        if any(len(t.values) != len(self.trains) for t in self.traveller_types):
            raise ValueError("Each traveller type must have one value per train.")
        if not self.traveller_types:
            raise ValueError("At least one traveller type is required.")
        if sum(t.share for t in self.traveller_types) <= 0:
            raise ValueError("Traveller type shares must sum to a positive number.")
        for traveller_type in self.traveller_types:
            if traveller_type.share < 0:
                raise ValueError("Traveller type shares cannot be negative.")
            if not 0.0 <= traveller_type.plan_change_probability <= 1.0:
                raise ValueError("Plan-change probabilities must be between 0 and 1.")
            if traveller_type.cancellation_hassle < 0 or traveller_type.value_noise_sd < 0:
                raise ValueError("Hassle and value-noise parameters cannot be negative.")

    def with_overrides(self, **kwargs: Any) -> "SimulationConfig":
        updated = replace(self, **kwargs)
        updated.validate()
        return updated


def default_config() -> SimulationConfig:
    config = SimulationConfig(
        trains=(
            TrainSpec("Train A", 30, 42.0),
            TrainSpec("Train B", 28, 38.0),
            TrainSpec("Train C", 26, 35.0),
        ),
        traveller_types=(
            TravellerType("A-preferring", 0.40, (145.0, 118.0, 96.0), 25.0),
            TravellerType("B-preferring", 0.35, (116.0, 145.0, 105.0), 25.0),
            TravellerType("C-preferring", 0.25, (111.0, 103.0, 142.0), 25.0),
        ),
    )
    config.validate()
    return config


def config_from_dict(data: dict[str, Any]) -> SimulationConfig:
    trains = tuple(TrainSpec(**row) for row in data["trains"])
    traveller_types = tuple(
        TravellerType(
            name=row["name"],
            share=float(row["share"]),
            values=tuple(float(value) for value in row["values"]),
            outside_option=float(row["outside_option"]),
            plan_change_probability=float(row.get("plan_change_probability", 0.04)),
            cancellation_hassle=float(row.get("cancellation_hassle", 2.0)),
            value_noise_sd=float(row.get("value_noise_sd", 4.0)),
        )
        for row in data["traveller_types"]
    )
    allowed = {
        "population_size",
        "waitlist_cap_fraction",
        "early_release_refund",
        "refund_eligibility_hours_before_departure",
        "chart_hours_before_departure",
        "resale_probability",
        "waitlist_cancel_fee",
        "confirmed_cancel_fee_early",
        "confirmed_cancel_fee_post_chart",
        "empty_berth_cost",
        "booking_earliest_hours",
        "booking_latest_hours",
        "default_strategy",
        "seed",
    }
    config = SimulationConfig(
        trains=trains,
        traveller_types=traveller_types,
        **{key: value for key, value in data.items() if key in allowed},
    )
    config.validate()
    return config


def load_config(path: str | Path) -> SimulationConfig:
    with Path(path).open("r", encoding="utf-8") as handle:
        return config_from_dict(json.load(handle))


def config_to_dict(config: SimulationConfig) -> dict[str, Any]:
    return {
        "trains": [
            {"name": train.name, "capacity": train.capacity, "fare": train.fare}
            for train in config.trains
        ],
        "traveller_types": [
            {
                "name": traveller_type.name,
                "share": traveller_type.share,
                "values": list(traveller_type.values),
                "outside_option": traveller_type.outside_option,
                "plan_change_probability": traveller_type.plan_change_probability,
                "cancellation_hassle": traveller_type.cancellation_hassle,
                "value_noise_sd": traveller_type.value_noise_sd,
            }
            for traveller_type in config.traveller_types
        ],
        "population_size": config.population_size,
        "waitlist_cap_fraction": config.waitlist_cap_fraction,
        "early_release_refund": config.early_release_refund,
        "refund_eligibility_hours_before_departure": config.refund_eligibility_hours_before_departure,
        "chart_hours_before_departure": config.chart_hours_before_departure,
        "resale_probability": config.resale_probability,
        "waitlist_cancel_fee": config.waitlist_cancel_fee,
        "confirmed_cancel_fee_early": config.confirmed_cancel_fee_early,
        "confirmed_cancel_fee_post_chart": config.confirmed_cancel_fee_post_chart,
        "empty_berth_cost": config.empty_berth_cost,
        "booking_earliest_hours": config.booking_earliest_hours,
        "booking_latest_hours": config.booking_latest_hours,
        "default_strategy": config.default_strategy,
        "seed": config.seed,
    }
