from dataclasses import replace

from waitlist_hedging.config import SimulationConfig, TrainSpec, TravellerType, default_config
from waitlist_hedging.simulator import BookingSimulator, run_simulation
from waitlist_hedging.strategies import Strategy


def test_simulation_respects_capacity_and_waitlist_caps(small_config):
    outcome = run_simulation(small_config, seed=10)
    for train in outcome.train_records:
        assert train["confirmed_travellers"] + train["resold_seats"] <= train["capacity"]
        assert train["waitlist_cap"] == 1
    assert 0.0 <= outcome.metrics["travel_probability"] <= 1.0
    assert 0.0 <= outcome.metrics["empty_berth_share"] <= 1.0


def test_pre_chart_cancellation_promotes_first_waitlisted_ticket(small_config):
    simulator = BookingSimulator(small_config, seed=5)
    simulator.build_population()
    first, second = list(simulator.travellers.values())
    confirmed = simulator._new_ticket(first, 0, "confirmed", None)
    queued = simulator._new_ticket(second, 0, "waitlisted", 1)
    simulator.trains[0].confirmed_ticket_ids.append(confirmed.ticket_id)
    simulator.trains[0].waitlist_ticket_ids.append(queued.ticket_id)

    simulator._cancel_ticket(confirmed.ticket_id, "redundant", 20.0)

    assert confirmed.status == "cancelled"
    assert queued.status == "confirmed"
    assert queued.ever_confirmed is True
    assert simulator.trains[0].confirmed_ticket_ids == [queued.ticket_id]
    assert simulator.trains[0].waitlist_ticket_ids == []


def test_chart_cancels_waitlist_without_promotion(small_config):
    simulator = BookingSimulator(small_config, seed=6)
    simulator.build_population()
    first, second = list(simulator.travellers.values())
    confirmed = simulator._new_ticket(first, 0, "confirmed", None)
    queued = simulator._new_ticket(second, 0, "waitlisted", 1)
    simulator.trains[0].confirmed_ticket_ids.append(confirmed.ticket_id)
    simulator.trains[0].waitlist_ticket_ids.append(queued.ticket_id)

    simulator._prepare_chart()

    assert simulator.chart_processed is True
    assert queued.status == "cancelled"
    assert confirmed.status == "confirmed"
    assert simulator.trains[0].confirmed_ticket_ids == [confirmed.ticket_id]
    assert simulator.trains[0].waitlist_ticket_ids == []


def test_refunds_are_reported_but_not_subtracted_from_social_welfare():
    base = default_config()
    profile = {
        traveller_type.name: Strategy.from_name("hedge2_timely")
        for traveller_type in base.traveller_types
    }
    no_refund = replace(base, early_release_refund=0.0)
    with_refund = replace(base, early_release_refund=25.0)
    first = run_simulation(no_refund, seed=321, strategy_profile=profile)
    second = run_simulation(with_refund, seed=321, strategy_profile=profile)

    assert first.metrics["social_welfare"] == second.metrics["social_welfare"]
    assert second.metrics["refunds_paid"] >= first.metrics["refunds_paid"]
    assert second.metrics["passenger_utility_sum"] >= first.metrics["passenger_utility_sum"]


def test_waitlist_confirmation_rates_are_endogenous(small_config):
    profile = {"type-1": Strategy.from_name("hedge2_late")}
    outcome = run_simulation(small_config, seed=14, strategy_profile=profile)
    for record in outcome.ticket_records:
        if record["was_waitlisted"]:
            assert "other_hedgers_on_train" in record
            assert "confirmed_before_chart" in record


def test_early_release_refund_requires_tau_r_threshold(small_config):
    eligible_config = replace(
        small_config,
        early_release_refund=20.0,
        refund_eligibility_hours_before_departure=24.0,
    )
    simulator = BookingSimulator(eligible_config, seed=8)
    simulator.build_population()
    traveller = next(iter(simulator.travellers.values()))
    ticket = simulator._new_ticket(traveller, 0, "confirmed", None)
    simulator.trains[0].confirmed_ticket_ids.append(ticket.ticket_id)

    simulator._cancel_ticket(ticket.ticket_id, "redundant", 20.0)
    assert traveller.refunds_received == 0.0

    second_simulator = BookingSimulator(eligible_config, seed=9)
    second_simulator.build_population()
    second_traveller = next(iter(second_simulator.travellers.values()))
    second_ticket = second_simulator._new_ticket(second_traveller, 0, "confirmed", None)
    second_simulator.trains[0].confirmed_ticket_ids.append(second_ticket.ticket_id)
    second_simulator._cancel_ticket(second_ticket.ticket_id, "redundant", 30.0)
    assert second_traveller.refunds_received == 20.0


def test_equal_valued_confirmations_keep_one_ticket(small_config):
    simulator = BookingSimulator(small_config, seed=12)
    simulator.build_population()
    traveller = next(iter(simulator.travellers.values()))
    traveller.values = (100.0, 100.0)
    first = simulator._new_ticket(traveller, 0, "confirmed", None)
    second = simulator._new_ticket(traveller, 1, "confirmed", None)
    simulator.trains[0].confirmed_ticket_ids.append(first.ticket_id)
    simulator.trains[1].confirmed_ticket_ids.append(second.ticket_id)

    simulator._resolve_redundancies(30.0)

    assert first.status == "confirmed"
    assert second.status == "cancelled"
