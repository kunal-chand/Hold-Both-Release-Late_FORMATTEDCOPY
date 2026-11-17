from __future__ import annotations

from collections import defaultdict
import math
import random
from typing import Any, Mapping

from .config import SimulationConfig, TravellerType
from .models import SimulationOutcome, Ticket, TrainState, Traveller, TravellerOutcome
from .strategies import Strategy


class BookingSimulator:
    def __init__(
        self,
        config: SimulationConfig,
        seed: int,
        strategy_profile: Mapping[str, Strategy] | None = None,
        strategy_overrides: Mapping[int, Strategy] | None = None,
    ) -> None:
        config.validate()
        self.config = config
        self.seed = seed
        self.rng = random.Random(seed)
        self.strategy_profile = dict(strategy_profile or {})
        self.strategy_overrides = dict(strategy_overrides or {})
        self.travellers: dict[int, Traveller] = {}
        self.tickets: dict[int, Ticket] = {}
        self.trains = [TrainState() for _ in config.trains]
        self.attempt_records: list[dict[str, Any]] = []
        self.next_ticket_id = 0
        self.chart_processed = False
        self.redundant_waitlist_slots_at_chart = 0
        self.early_releases = 0
        self.late_releases = 0
        self.refunds_paid = 0.0
        self.cancellation_fee_revenue = 0.0

    def build_population(self) -> None:
        type_counts = self._type_counts()
        rows: list[tuple[TravellerType, Strategy]] = []
        for traveller_type in self.config.traveller_types:
            strategy = self.strategy_profile.get(
                traveller_type.name,
                Strategy.from_name(self.config.default_strategy),
            )
            rows.extend((traveller_type, strategy) for _ in range(type_counts[traveller_type.name]))
        self.rng.shuffle(rows)
        for traveller_id, (traveller_type, profile_strategy) in enumerate(rows):
            strategy = self.strategy_overrides.get(traveller_id, profile_strategy)
            noisy_values = tuple(
                max(0.0, value + self.rng.gauss(0.0, traveller_type.value_noise_sd))
                for value in traveller_type.values
            )
            booking_hour = self.rng.uniform(
                self.config.booking_latest_hours,
                self.config.booking_earliest_hours,
            )
            traveller = Traveller(
                traveller_id=traveller_id,
                type_name=traveller_type.name,
                values=noisy_values,
                outside_option=traveller_type.outside_option,
                plan_change_probability=traveller_type.plan_change_probability,
                cancellation_hassle=traveller_type.cancellation_hassle,
                booking_hour=booking_hour,
                strategy=strategy,
            )
            self.travellers[traveller_id] = traveller

    def _type_counts(self) -> dict[str, int]:
        total_share = sum(row.share for row in self.config.traveller_types)
        exact = {
            row.name: self.config.population_size * row.share / total_share
            for row in self.config.traveller_types
        }
        counts = {name: math.floor(value) for name, value in exact.items()}
        remainder = self.config.population_size - sum(counts.values())
        ranked = sorted(exact, key=lambda name: exact[name] - counts[name], reverse=True)
        for name in ranked[:remainder]:
            counts[name] += 1
        return counts

    def run(self) -> SimulationOutcome:
        self.build_population()
        events: list[tuple[float, int, int, str]] = []
        for traveller in self.travellers.values():
            events.append((-traveller.booking_hour, 1, traveller.traveller_id, "booking"))
            if self.rng.random() < traveller.plan_change_probability:
                change_hour = self.rng.uniform(0.0, traveller.booking_hour)
                events.append((-change_hour, 2, traveller.traveller_id, "plan_change"))
        events.append((-self.config.chart_hours_before_departure, 0, -1, "chart"))
        events.sort()

        for negative_hour, _, traveller_id, event_name in events:
            current_hour = -negative_hour
            if event_name == "chart":
                self._prepare_chart()
            elif event_name == "booking":
                traveller = self.travellers[traveller_id]
                if not traveller.changed_plans:
                    self._book_for_traveller(traveller)
                    self._resolve_redundancies(current_hour)
            elif event_name == "plan_change":
                traveller = self.travellers[traveller_id]
                traveller.changed_plans = True
                for ticket_id in list(traveller.ticket_ids):
                    self._cancel_ticket(ticket_id, "plan_change", current_hour)
                self._resolve_redundancies(current_hour)

        if not self.chart_processed:
            self._prepare_chart()
        self._resolve_redundancies(0.0)
        return self._build_outcome()

    def _book_for_traveller(self, traveller: Traveller) -> None:
        ranked_trains = sorted(
            range(len(self.config.trains)),
            key=lambda index: traveller.values[index],
            reverse=True,
        )
        selected = ranked_trains[: min(traveller.strategy.booking_count, len(ranked_trains))]
        for train_index in selected:
            train_spec = self.config.trains[train_index]
            train_state = self.trains[train_index]
            train_state.booking_attempts += 1
            attempt = {
                "traveller_id": traveller.traveller_id,
                "type_name": traveller.type_name,
                "strategy": traveller.strategy.name,
                "train_index": train_index,
                "train": train_spec.name,
                "ticket_id": None,
                "initial_status": "refused",
                "waitlist_position": None,
                "was_waitlisted": False,
                "confirmed_before_chart": False,
                "confirmed_at_departure": False,
            }
            if len(train_state.confirmed_ticket_ids) < train_spec.capacity:
                ticket = self._new_ticket(traveller, train_index, "confirmed", None)
                train_state.confirmed_ticket_ids.append(ticket.ticket_id)
                ticket.ever_confirmed = True
                attempt.update(
                    ticket_id=ticket.ticket_id,
                    initial_status="confirmed",
                )
            else:
                waitlist_cap = math.floor(train_spec.capacity * self.config.waitlist_cap_fraction)
                if len(train_state.waitlist_ticket_ids) < waitlist_cap:
                    position = len(train_state.waitlist_ticket_ids) + 1
                    ticket = self._new_ticket(traveller, train_index, "waitlisted", position)
                    train_state.waitlist_ticket_ids.append(ticket.ticket_id)
                    attempt.update(
                        ticket_id=ticket.ticket_id,
                        initial_status="waitlisted",
                        waitlist_position=position,
                        was_waitlisted=True,
                    )
                else:
                    traveller.refused_tickets += 1
                    train_state.refused_attempts += 1
            self.attempt_records.append(attempt)

    def _new_ticket(
        self,
        traveller: Traveller,
        train_index: int,
        status: str,
        waitlist_position: int | None,
    ) -> Ticket:
        ticket = Ticket(
            ticket_id=self.next_ticket_id,
            traveller_id=traveller.traveller_id,
            train_index=train_index,
            status=status,
            initial_status=status,
            waitlist_position=waitlist_position,
            was_waitlisted=status == "waitlisted",
        )
        self.tickets[ticket.ticket_id] = ticket
        traveller.ticket_ids.append(ticket.ticket_id)
        self.next_ticket_id += 1
        return ticket

    def _prepare_chart(self) -> None:
        if self.chart_processed:
            return
        for ticket in self.tickets.values():
            if ticket.status == "waitlisted" and self._ticket_is_redundant(ticket):
                self.redundant_waitlist_slots_at_chart += 1
                ticket.redundant_before_chart = True
                self.late_releases += 1
        self.chart_processed = True
        for train_state in self.trains:
            for ticket_id in list(train_state.waitlist_ticket_ids):
                self._cancel_ticket(ticket_id, "auto_chart", self.config.chart_hours_before_departure)
        self._resolve_redundancies(self.config.chart_hours_before_departure)

    def _ticket_is_redundant(self, ticket: Ticket) -> bool:
        traveller = self.travellers[ticket.traveller_id]
        this_value = traveller.values[ticket.train_index]
        for other_ticket_id in traveller.ticket_ids:
            if other_ticket_id == ticket.ticket_id:
                continue
            other = self.tickets[other_ticket_id]
            if other.status != "confirmed":
                continue
            other_value = traveller.values[other.train_index]
            if other_value > this_value + 1e-10:
                return True
            if abs(other_value - this_value) <= 1e-10 and other.train_index < ticket.train_index:
                return True
        return False

    def _resolve_redundancies(self, current_hour: float) -> None:
        changed = True
        while changed:
            changed = False
            for traveller in self.travellers.values():
                for ticket_id in list(traveller.ticket_ids):
                    ticket = self.tickets[ticket_id]
                    if ticket.status not in {"confirmed", "waitlisted"}:
                        continue
                    if not self._ticket_is_redundant(ticket):
                        continue
                    if traveller.strategy.release_mode == "late" and not self.chart_processed:
                        if ticket.status == "waitlisted":
                            ticket.redundant_before_chart = True
                        continue
                    self._cancel_ticket(ticket_id, "redundant", current_hour)
                    changed = True
                    break
                if changed:
                    break

    def _cancel_ticket(self, ticket_id: int, reason: str, current_hour: float) -> None:
        ticket = self.tickets[ticket_id]
        if ticket.status not in {"confirmed", "waitlisted"}:
            return
        traveller = self.travellers[ticket.traveller_id]
        train_state = self.trains[ticket.train_index]
        was_confirmed = ticket.status == "confirmed"
        pre_chart = not self.chart_processed and current_hour > self.config.chart_hours_before_departure

        if was_confirmed:
            if ticket_id in train_state.confirmed_ticket_ids:
                train_state.confirmed_ticket_ids.remove(ticket_id)
            fee = (
                self.config.confirmed_cancel_fee_early
                if pre_chart
                else self.config.confirmed_cancel_fee_post_chart
            )
        else:
            if ticket_id in train_state.waitlist_ticket_ids:
                train_state.waitlist_ticket_ids.remove(ticket_id)
            fee = self.config.waitlist_cancel_fee

        if reason == "auto_chart":
            fee = self.config.waitlist_cancel_fee
        ticket.status = "cancelled"
        ticket.cancellation_reason = reason
        ticket.cancellation_fee = fee
        traveller.cancellation_fees += fee
        self.cancellation_fee_revenue += fee

        if reason != "auto_chart":
            traveller.cancellations += 1
            traveller.hassle_cost += traveller.cancellation_hassle

        if reason == "redundant":
            if pre_chart:
                if current_hour >= self.config.refund_eligibility_hours_before_departure:
                    ticket.early_refund = self.config.early_release_refund
                    traveller.refunds_received += ticket.early_refund
                    self.refunds_paid += ticket.early_refund
                self.early_releases += 1
            else:
                self.late_releases += 1

        if was_confirmed:
            if pre_chart:
                self._promote_next_waitlisted(ticket.train_index)
            else:
                free_seats = (
                    self.config.trains[ticket.train_index].capacity
                    - len(train_state.confirmed_ticket_ids)
                    - train_state.resold_seats
                )
                if free_seats > 0 and self.rng.random() < self.config.resale_probability:
                    train_state.resold_seats += 1

    def _promote_next_waitlisted(self, train_index: int) -> None:
        train_state = self.trains[train_index]
        while train_state.waitlist_ticket_ids:
            ticket_id = train_state.waitlist_ticket_ids.pop(0)
            ticket = self.tickets[ticket_id]
            if ticket.status != "waitlisted":
                continue
            ticket.status = "confirmed"
            ticket.ever_confirmed = True
            train_state.confirmed_ticket_ids.append(ticket_id)
            return

    def _build_outcome(self) -> SimulationOutcome:
        selected_train_by_traveller: dict[int, int | None] = {}
        gross_values: dict[int, float] = {}
        passenger_utilities: dict[int, float] = {}
        traveller_rows: list[TravellerOutcome] = []
        used_fares = 0.0
        unused_confirmed_fares = 0.0

        for traveller in self.travellers.values():
            active_confirmed = [
                self.tickets[ticket_id]
                for ticket_id in traveller.ticket_ids
                if self.tickets[ticket_id].status == "confirmed"
            ]
            best_ticket = max(
                active_confirmed,
                key=lambda ticket: traveller.values[ticket.train_index],
                default=None,
            )
            travelled_train: int | None = None
            if best_ticket is not None:
                best_value = traveller.values[best_ticket.train_index]
                if best_value >= traveller.outside_option:
                    travelled_train = best_ticket.train_index
                    used_fares += self.config.trains[travelled_train].fare

            if travelled_train is None:
                gross_value = traveller.outside_option
            else:
                gross_value = traveller.values[travelled_train]

            for ticket in active_confirmed:
                if travelled_train is None or ticket.train_index != travelled_train:
                    unused_confirmed_fares += self.config.trains[ticket.train_index].fare

            gross_values[traveller.traveller_id] = gross_value
            selected_train_by_traveller[traveller.traveller_id] = travelled_train
            utility = (
                max(
                    traveller.outside_option,
                    (traveller.values[travelled_train] - self.config.trains[travelled_train].fare)
                    if travelled_train is not None
                    else traveller.outside_option,
                )
                - traveller.cancellation_fees
                - traveller.hassle_cost
                + traveller.refunds_received
                - sum(
                    self.config.trains[ticket.train_index].fare
                    for ticket in active_confirmed
                    if travelled_train is None or ticket.train_index != travelled_train
                )
            )
            passenger_utilities[traveller.traveller_id] = utility
            confirmed_train_indices = tuple(
                ticket.train_index for ticket in active_confirmed
            )
            requested_train_indices = tuple(
                row["train_index"]
                for row in self.attempt_records
                if row["traveller_id"] == traveller.traveller_id
            )
            traveller_rows.append(
                TravellerOutcome(
                    traveller_id=traveller.traveller_id,
                    type_name=traveller.type_name,
                    strategy=traveller.strategy.name,
                    booked_train_indices=requested_train_indices,
                    confirmed_train_indices=confirmed_train_indices,
                    travelled_train_index=travelled_train,
                    travelled=travelled_train is not None,
                    gross_value=gross_value,
                    utility=utility,
                    refused_tickets=traveller.refused_tickets,
                )
            )

        occupied_by_train = [0 for _ in self.config.trains]
        for train_index in selected_train_by_traveller.values():
            if train_index is not None:
                occupied_by_train[train_index] += 1
        empty_berths_by_train = []
        train_records: list[dict[str, Any]] = []
        for train_index, (train_spec, train_state) in enumerate(zip(self.config.trains, self.trains)):
            empty = max(
                0,
                train_spec.capacity - occupied_by_train[train_index] - train_state.resold_seats,
            )
            empty_berths_by_train.append(empty)
            train_records.append(
                {
                    "train": train_spec.name,
                    "capacity": train_spec.capacity,
                    "confirmed_travellers": occupied_by_train[train_index],
                    "resold_seats": train_state.resold_seats,
                    "empty_berths": empty,
                    "booking_attempts": train_state.booking_attempts,
                    "refused_attempts": train_state.refused_attempts,
                    "waitlist_cap": math.floor(
                        train_spec.capacity * self.config.waitlist_cap_fraction
                    ),
                }
            )

        total_capacity = sum(train.capacity for train in self.config.trains)
        total_waitlist_slots = sum(
            math.floor(train.capacity * self.config.waitlist_cap_fraction)
            for train in self.config.trains
        )
        hedger_ids = {
            traveller.traveller_id
            for traveller in self.travellers.values()
            if traveller.strategy.booking_count > 1
        }
        hedge_share = len(hedger_ids) / max(len(self.travellers), 1)
        hedgers_by_train: dict[int, set[int]] = defaultdict(set)
        for attempt in self.attempt_records:
            if attempt["traveller_id"] in hedger_ids:
                hedgers_by_train[attempt["train_index"]].add(attempt["traveller_id"])
        ticket_records: list[dict[str, Any]] = []
        for attempt in self.attempt_records:
            ticket_id = attempt["ticket_id"]
            ticket = self.tickets.get(ticket_id) if ticket_id is not None else None
            train_index = attempt["train_index"]
            hedgers_on_train = hedgers_by_train.get(train_index, set())
            other_hedgers = len(hedgers_on_train - {attempt["traveller_id"]})
            travelled_train = selected_train_by_traveller[attempt["traveller_id"]]
            attempt_confirmed_at_departure = bool(ticket and ticket.status == "confirmed")
            ticket_records.append(
                {
                    **attempt,
                    "ticket_status_at_departure": ticket.status if ticket else "refused",
                    "ever_confirmed": bool(ticket and ticket.ever_confirmed),
                    "confirmed_before_chart": bool(
                        ticket and ticket.was_waitlisted and ticket.ever_confirmed
                    ),
                    "confirmed_at_departure": attempt_confirmed_at_departure,
                    "other_hedgers_on_train": other_hedgers,
                    "hedge_share": hedge_share,
                    "redundant_waitlist_at_chart": bool(
                        ticket
                        and ticket.was_waitlisted
                        and ticket.redundant_before_chart
                        and ticket.status == "cancelled"
                        and ticket.cancellation_reason == "auto_chart"
                    ),
                }
            )

        refused_attempts = sum(row["ticket_id"] is None for row in self.attempt_records)
        turned_away = sum(
            traveller.refused_tickets > 0
            and selected_train_by_traveller[traveller.traveller_id] is None
            for traveller in self.travellers.values()
        )
        initial_waitlist_tickets = [
            ticket for ticket in self.tickets.values() if ticket.was_waitlisted
        ]
        confirmed_waitlist_tickets = sum(ticket.ever_confirmed for ticket in initial_waitlist_tickets)
        waitlist_confirmation_rate = (
            confirmed_waitlist_tickets / len(initial_waitlist_tickets)
            if initial_waitlist_tickets
            else 0.0
        )
        empty_berths = sum(empty_berths_by_train)
        empty_berth_share = empty_berths / max(total_capacity, 1)
        social_value = sum(gross_values.values())
        total_hassle_cost = sum(traveller.hassle_cost for traveller in self.travellers.values())
        social_welfare = (
            social_value
            - self.config.empty_berth_cost * empty_berths
            - total_hassle_cost
        )
        passenger_utility_sum = sum(passenger_utilities.values())
        total_tickets = len(self.attempt_records)
        profile = {
            traveller_type.name: self.strategy_profile.get(
                traveller_type.name,
                Strategy.from_name(self.config.default_strategy),
            ).name
            for traveller_type in self.config.traveller_types
        }
        if self.strategy_overrides:
            profile["focal_overrides"] = str(len(self.strategy_overrides))

        metrics = {
            "population": float(len(self.travellers)),
            "travelled": float(sum(row.travelled for row in traveller_rows)),
            "travel_probability": sum(row.travelled for row in traveller_rows)
            / max(len(self.travellers), 1),
            "hedgers": float(len(hedger_ids)),
            "hedge_share": hedge_share,
            "empty_berths": float(empty_berths),
            "empty_berth_share": empty_berth_share,
            "refused_ticket_attempts": float(refused_attempts),
            "travellers_turned_away": float(turned_away),
            "redundant_waitlist_slots_at_chart": float(self.redundant_waitlist_slots_at_chart),
            "redundant_waitlist_slot_share": self.redundant_waitlist_slots_at_chart
            / max(total_waitlist_slots, 1),
            "refunds_paid": self.refunds_paid,
            "cancellation_fee_revenue": self.cancellation_fee_revenue,
            "fare_revenue": used_fares,
            "unused_confirmed_fares": unused_confirmed_fares,
            "early_releases": float(self.early_releases),
            "late_releases": float(self.late_releases),
            "ticket_attempts": float(total_tickets),
            "accepted_tickets": float(sum(row["ticket_id"] is not None for row in self.attempt_records)),
            "waitlisted_tickets": float(len(initial_waitlist_tickets)),
            "waitlist_confirmation_rate": waitlist_confirmation_rate,
            "gross_social_value": social_value,
            "hassle_cost": total_hassle_cost,
            "social_welfare": social_welfare,
            "passenger_utility_sum": passenger_utility_sum,
            "mean_traveller_utility": passenger_utility_sum / max(len(self.travellers), 1),
            "railway_net_transfers": used_fares + unused_confirmed_fares
            + self.cancellation_fee_revenue - self.refunds_paid,
        }
        return SimulationOutcome(
            seed=self.seed,
            metrics=metrics,
            traveller_outcomes=traveller_rows,
            ticket_records=ticket_records,
            train_records=train_records,
            type_strategy_profile=profile,
        )


def run_simulation(
    config: SimulationConfig,
    seed: int | None = None,
    strategy_profile: Mapping[str, Strategy] | None = None,
    strategy_overrides: Mapping[int, Strategy] | None = None,
) -> SimulationOutcome:
    actual_seed = config.seed if seed is None else seed
    return BookingSimulator(
        config=config,
        seed=actual_seed,
        strategy_profile=strategy_profile,
        strategy_overrides=strategy_overrides,
    ).run()
