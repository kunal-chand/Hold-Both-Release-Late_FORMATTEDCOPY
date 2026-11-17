from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .strategies import Strategy


@dataclass
class Traveller:
    traveller_id: int
    type_name: str
    values: tuple[float, ...]
    outside_option: float
    plan_change_probability: float
    cancellation_hassle: float
    booking_hour: float
    strategy: Strategy
    ticket_ids: list[int] = field(default_factory=list)
    changed_plans: bool = False
    refused_tickets: int = 0
    cancellations: int = 0
    cancellation_fees: float = 0.0
    refunds_received: float = 0.0
    hassle_cost: float = 0.0


@dataclass
class Ticket:
    ticket_id: int
    traveller_id: int
    train_index: int
    status: str
    initial_status: str
    waitlist_position: int | None = None
    was_waitlisted: bool = False
    ever_confirmed: bool = False
    redundant_before_chart: bool = False
    cancellation_reason: str | None = None
    cancellation_fee: float = 0.0
    early_refund: float = 0.0


@dataclass
class TrainState:
    confirmed_ticket_ids: list[int] = field(default_factory=list)
    waitlist_ticket_ids: list[int] = field(default_factory=list)
    resold_seats: int = 0
    refused_attempts: int = 0
    booking_attempts: int = 0


@dataclass
class TravellerOutcome:
    traveller_id: int
    type_name: str
    strategy: str
    booked_train_indices: tuple[int, ...]
    confirmed_train_indices: tuple[int, ...]
    travelled_train_index: int | None
    travelled: bool
    gross_value: float
    utility: float
    refused_tickets: int


@dataclass
class SimulationOutcome:
    seed: int
    metrics: dict[str, float]
    traveller_outcomes: list[TravellerOutcome]
    ticket_records: list[dict[str, Any]]
    train_records: list[dict[str, Any]]
    type_strategy_profile: dict[str, str]

    def to_summary_row(self, scenario: str) -> dict[str, Any]:
        return {"scenario": scenario, "seed": self.seed, **self.metrics}
