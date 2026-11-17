from waitlist_hedging.config import SimulationConfig, TrainSpec, TravellerType
from waitlist_hedging.equilibrium import find_equilibrium


def test_equilibrium_returns_a_strategy_for_each_type():
    config = SimulationConfig(
        trains=(TrainSpec("A", 3, 10.0), TrainSpec("B", 3, 10.0)),
        traveller_types=(
            TravellerType("type-1", 0.5, (100.0, 70.0), 5.0, 0.0, 1.0, 0.0),
            TravellerType("type-2", 0.5, (70.0, 100.0), 5.0, 0.0, 1.0, 0.0),
        ),
        population_size=8,
        waitlist_cap_fraction=0.5,
        booking_earliest_hours=72.0,
        booking_latest_hours=12.0,
    )
    result = find_equilibrium(config, evaluation_runs=1, max_iterations=2)
    assert set(result.strategy_profile) == {"type-1", "type-2"}
    assert result.iterations <= 2
    assert set(result.best_response_gaps) == {"type-1", "type-2"}
