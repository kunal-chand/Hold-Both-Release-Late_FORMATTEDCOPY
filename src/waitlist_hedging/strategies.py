from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Strategy:
    booking_count: int
    release_mode: str = "timely"

    def __post_init__(self) -> None:
        if self.booking_count < 1:
            raise ValueError("booking_count must be at least 1.")
        if self.release_mode not in {"timely", "late"}:
            raise ValueError("release_mode must be 'timely' or 'late'.")

    @property
    def name(self) -> str:
        if self.booking_count == 1:
            return "single"
        return f"hedge{self.booking_count}_{self.release_mode}"

    @classmethod
    def from_name(cls, name: str) -> "Strategy":
        if name == "single":
            return cls(1, "timely")
        if not name.startswith("hedge"):
            raise ValueError(f"Unknown strategy: {name}")
        count_text, release_mode = name.removeprefix("hedge").split("_", 1)
        return cls(int(count_text), release_mode)


def available_strategies(number_of_trains: int) -> tuple[Strategy, ...]:
    strategies = [Strategy(1)]
    for count in range(2, number_of_trains + 1):
        strategies.append(Strategy(count, "timely"))
        strategies.append(Strategy(count, "late"))
    return tuple(strategies)
