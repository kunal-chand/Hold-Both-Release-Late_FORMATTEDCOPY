from waitlist_hedging.config import SimulationConfig, TrainSpec, TravellerType
from waitlist_hedging.planner import planner_assignment


def test_planner_never_exceeds_capacity():
    config = SimulationConfig(
        trains=(TrainSpec("A", 1, 10.0), TrainSpec("B", 1, 10.0)),
        traveller_types=(
            TravellerType("A-pref", 0.5, (100.0, 20.0), 5.0, 0.0, 0.0, 0.0),
            TravellerType("B-pref", 0.5, (20.0, 100.0), 5.0, 0.0, 0.0, 0.0),
        ),
        population_size=4,
        booking_earliest_hours=72.0,
        booking_latest_hours=12.0,
    )
    outcome = planner_assignment(config, seed=10)
    assert len(outcome["assigned"]) <= 2
    assert outcome["travelled"] == len(outcome["assigned"])
