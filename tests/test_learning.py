from waitlist_hedging.config import SimulationConfig, TrainSpec, TravellerType
from waitlist_hedging.learning import run_type_level_learning


def test_learning_explores_actions_and_returns_a_policy():
    config = SimulationConfig(
        trains=(TrainSpec("A", 4, 10.0), TrainSpec("B", 4, 10.0)),
        traveller_types=(
            TravellerType("type-1", 0.5, (100.0, 70.0), 5.0, 0.0, 1.0, 0.0),
            TravellerType("type-2", 0.5, (70.0, 100.0), 5.0, 0.0, 1.0, 0.0),
        ),
        population_size=8,
        waitlist_cap_fraction=0.5,
        booking_earliest_hours=72.0,
        booking_latest_hours=12.0,
    )
    result = run_type_level_learning(config, seasons=4, seed_start=5)
    assert set(result["learned_policy"]) == {"type-1", "type-2"}
    assert len(result["history"]) == 8
    for type_name in ("type-1", "type-2"):
        assert sum(result["action_counts"][type_name].values()) == 4
