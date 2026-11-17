import pytest

from waitlist_hedging.config import SimulationConfig, TrainSpec, TravellerType


@pytest.fixture
def small_config():
    config = SimulationConfig(
        trains=(
            TrainSpec("A", 1, 10.0),
            TrainSpec("B", 1, 10.0),
        ),
        traveller_types=(
            TravellerType(
                "type-1",
                1.0,
                (100.0, 80.0),
                5.0,
                plan_change_probability=0.0,
                cancellation_hassle=1.0,
                value_noise_sd=0.0,
            ),
        ),
        population_size=2,
        waitlist_cap_fraction=1.0,
        early_release_refund=0.0,
        chart_hours_before_departure=8.0,
        resale_probability=0.0,
        empty_berth_cost=10.0,
        booking_earliest_hours=72.0,
        booking_latest_hours=12.0,
        default_strategy="single",
        seed=1,
    )
    config.validate()
    return config
