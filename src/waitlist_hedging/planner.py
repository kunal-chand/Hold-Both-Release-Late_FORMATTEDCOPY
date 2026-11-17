from __future__ import annotations

from collections import deque
from statistics import mean
from typing import Any

from .config import SimulationConfig
from .simulator import BookingSimulator


class _Edge:
    def __init__(self, to: int, reverse: int, capacity: int, cost: float) -> None:
        self.to = to
        self.reverse = reverse
        self.capacity = capacity
        self.cost = cost


def _add_edge(graph: list[list[_Edge]], source: int, target: int, capacity: int, cost: float) -> _Edge:
    forward = _Edge(target, len(graph[target]), capacity, cost)
    backward = _Edge(source, len(graph[source]), 0, -cost)
    graph[source].append(forward)
    graph[target].append(backward)
    return forward


def planner_assignment(config: SimulationConfig, seed: int) -> dict[str, Any]:
    population_builder = BookingSimulator(config, seed)
    population_builder.build_population()
    travellers = list(population_builder.travellers.values())
    n_travellers = len(travellers)
    n_trains = len(config.trains)

    source = 0
    traveller_start = 1
    train_start = traveller_start + n_travellers
    sink = train_start + n_trains
    graph: list[list[_Edge]] = [[] for _ in range(sink + 1)]
    assignment_edges: dict[tuple[int, int], _Edge] = {}

    for traveller_position, traveller in enumerate(travellers):
        traveller_node = traveller_start + traveller_position
        _add_edge(graph, source, traveller_node, 1, 0.0)
        _add_edge(graph, traveller_node, sink, 1, 0.0)
        for train_index in range(n_trains):
            surplus = traveller.values[train_index] - traveller.outside_option
            if surplus > 0:
                edge = _add_edge(
                    graph,
                    traveller_node,
                    train_start + train_index,
                    1,
                    -surplus,
                )
                assignment_edges[(traveller.traveller_id, train_index)] = edge

    for train_index, train in enumerate(config.trains):
        _add_edge(graph, train_start + train_index, sink, train.capacity, 0.0)

    flow = 0
    while flow < n_travellers:
        distance = [float("inf")] * len(graph)
        previous_node = [-1] * len(graph)
        previous_edge = [-1] * len(graph)
        in_queue = [False] * len(graph)
        queue: deque[int] = deque([source])
        distance[source] = 0.0
        in_queue[source] = True

        while queue:
            node = queue.popleft()
            in_queue[node] = False
            for edge_index, edge in enumerate(graph[node]):
                if edge.capacity <= 0:
                    continue
                candidate = distance[node] + edge.cost
                if candidate + 1e-12 < distance[edge.to]:
                    distance[edge.to] = candidate
                    previous_node[edge.to] = node
                    previous_edge[edge.to] = edge_index
                    if not in_queue[edge.to]:
                        queue.append(edge.to)
                        in_queue[edge.to] = True
        if previous_node[sink] == -1:
            raise RuntimeError("Planner assignment flow could not route every traveller.")

        node = sink
        while node != source:
            parent = previous_node[node]
            edge = graph[parent][previous_edge[node]]
            edge.capacity -= 1
            graph[node][edge.reverse].capacity += 1
            node = parent
        flow += 1

    assigned: dict[int, int] = {}
    for (traveller_id, train_index), edge in assignment_edges.items():
        if edge.capacity == 0:
            assigned[traveller_id] = train_index

    gross_value = 0.0
    for traveller in travellers:
        train_index = assigned.get(traveller.traveller_id)
        gross_value += (
            traveller.values[train_index]
            if train_index is not None
            else traveller.outside_option
        )
    total_capacity = sum(train.capacity for train in config.trains)
    empty_berths = total_capacity - len(assigned)
    hassle_cost = 0.0
    social_welfare = gross_value - config.empty_berth_cost * empty_berths
    return {
        "seed": seed,
        "population": n_travellers,
        "travelled": len(assigned),
        "travel_probability": len(assigned) / max(n_travellers, 1),
        "empty_berths": empty_berths,
        "empty_berth_share": empty_berths / max(total_capacity, 1),
        "gross_social_value": gross_value,
        "hassle_cost": hassle_cost,
        "social_welfare": social_welfare,
        "travellers_turned_away": 0,
        "refunds_paid": 0.0,
        "assigned": assigned,
    }


def planner_benchmark(
    config: SimulationConfig,
    runs: int = 10,
    seed_start: int = 12000,
) -> dict[str, float]:
    outcomes = [planner_assignment(config, seed_start + index) for index in range(runs)]
    metric_names = (
        "population",
        "travelled",
        "travel_probability",
        "empty_berths",
        "empty_berth_share",
        "gross_social_value",
        "hassle_cost",
        "social_welfare",
        "travellers_turned_away",
        "refunds_paid",
    )
    return {name: mean(float(row[name]) for row in outcomes) for name in metric_names}
