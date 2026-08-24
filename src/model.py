from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import lil_matrix


@dataclass(frozen=True)
class Trip:
    trip_id: str
    origin: str
    destination: str
    departure: int
    arrival: int
    demand: int
    distance_km: float


@dataclass(frozen=True)
class FleetType:
    fleet_id: str
    capacity: int
    available_units: int
    cost_per_km: float
    activation_cost: float


@dataclass
class Solution:
    objective: float
    assignments: Dict[str, str]
    starts: List[Tuple[str, str]]
    ends: List[Tuple[str, str]]
    links: List[Tuple[str, str, str]]
    units_used: Dict[str, int]


def sample_data() -> Tuple[List[Trip], List[FleetType]]:
    """Return a small deterministic synthetic timetable and fleet."""
    trips = [
        Trip("T01", "A", "B", 360, 480, 110, 180.0),
        Trip("T02", "B", "C", 520, 640, 125, 200.0),
        Trip("T03", "C", "B", 690, 810, 120, 200.0),
        Trip("T04", "B", "A", 850, 970, 105, 180.0),
        Trip("T05", "A", "D", 390, 510, 70, 160.0),
        Trip("T06", "D", "A", 560, 680, 75, 160.0),
        Trip("T07", "A", "E", 430, 550, 85, 170.0),
        Trip("T08", "E", "A", 600, 720, 90, 170.0),
    ]

    fleet = [
        FleetType("FLEET_A", 100, 2, 4.2, 650.0),
        FleetType("FLEET_B", 140, 2, 5.1, 800.0),
    ]
    return trips, fleet


def compatible_connections(
    trips: Iterable[Trip], min_turnaround: int = 30
) -> List[Tuple[int, int]]:
    """Return ordered trip pairs that can be operated by the same vehicle."""
    trip_list = list(trips)
    connections: List[Tuple[int, int]] = []

    for i, first in enumerate(trip_list):
        for j, second in enumerate(trip_list):
            if i == j:
                continue
            same_station = first.destination == second.origin
            enough_turnaround = second.departure - first.arrival >= min_turnaround
            if same_station and enough_turnaround:
                connections.append((i, j))

    return connections


def solve_fleet_circulation(
    trips: List[Trip],
    fleet: List[FleetType],
    min_turnaround: int = 30,
    empty_seat_penalty: float = 0.03,
    idle_time_penalty: float = 0.4,
) -> Solution:
    """Solve fleet assignment and daily circulation as a binary MILP."""
    if not trips:
        raise ValueError("At least one trip is required.")
    if not fleet:
        raise ValueError("At least one fleet type is required.")
    if min_turnaround < 0:
        raise ValueError("min_turnaround must be non-negative.")

    for trip in trips:
        if trip.arrival <= trip.departure:
            raise ValueError(f"Trip {trip.trip_id} must arrive after departure.")
        if trip.demand < 0 or trip.distance_km < 0:
            raise ValueError(f"Trip {trip.trip_id} has invalid demand or distance.")
        if not any(vehicle.capacity >= trip.demand for vehicle in fleet):
            raise ValueError(f"No fleet type can cover demand for trip {trip.trip_id}.")

    connections = compatible_connections(trips, min_turnaround)

    x_idx: Dict[Tuple[int, int], int] = {}
    start_idx: Dict[Tuple[int, int], int] = {}
    end_idx: Dict[Tuple[int, int], int] = {}
    link_idx: Dict[Tuple[int, int, int], int] = {}

    variable_count = 0
    for t in range(len(trips)):
        for k in range(len(fleet)):
            x_idx[t, k] = variable_count
            variable_count += 1
            start_idx[t, k] = variable_count
            variable_count += 1
            end_idx[t, k] = variable_count
            variable_count += 1

    for i, j in connections:
        for k in range(len(fleet)):
            link_idx[i, j, k] = variable_count
            variable_count += 1

    objective = np.zeros(variable_count)
    lower_bounds = np.zeros(variable_count)
    upper_bounds = np.ones(variable_count)
    integrality = np.ones(variable_count)

    for t, trip in enumerate(trips):
        for k, vehicle in enumerate(fleet):
            assignment_index = x_idx[t, k]
            operating_cost = trip.distance_km * vehicle.cost_per_km
            empty_seat_cost = empty_seat_penalty * max(0, vehicle.capacity - trip.demand)
            objective[assignment_index] = operating_cost + empty_seat_cost
            objective[start_idx[t, k]] = vehicle.activation_cost

            if vehicle.capacity < trip.demand:
                upper_bounds[assignment_index] = 0.0

    for i, j in connections:
        idle_minutes = trips[j].departure - trips[i].arrival
        for k in range(len(fleet)):
            objective[link_idx[i, j, k]] = idle_time_penalty * idle_minutes

    rows: List[Dict[int, float]] = []
    row_lower: List[float] = []
    row_upper: List[float] = []

    def add_row(coefficients: Dict[int, float], lower: float, upper: float) -> None:
        rows.append(coefficients)
        row_lower.append(lower)
        row_upper.append(upper)

    # Every scheduled trip must be assigned to exactly one fleet type.
    for t in range(len(trips)):
        add_row({x_idx[t, k]: 1.0 for k in range(len(fleet))}, 1.0, 1.0)

    # Flow conservation for each trip and fleet type.
    for t in range(len(trips)):
        for k in range(len(fleet)):
            predecessor_flow = {start_idx[t, k]: 1.0, x_idx[t, k]: -1.0}
            successor_flow = {end_idx[t, k]: 1.0, x_idx[t, k]: -1.0}

            for i, j in connections:
                if j == t:
                    predecessor_flow[link_idx[i, j, k]] = 1.0
                if i == t:
                    successor_flow[link_idx[i, j, k]] = 1.0

            add_row(predecessor_flow, 0.0, 0.0)
            add_row(successor_flow, 0.0, 0.0)

    # A circulation start represents one physical unit in use.
    for k, vehicle in enumerate(fleet):
        add_row(
            {start_idx[t, k]: 1.0 for t in range(len(trips))},
            -np.inf,
            float(vehicle.available_units),
        )

    matrix = lil_matrix((len(rows), variable_count), dtype=float)
    for row_number, coefficients in enumerate(rows):
        for column, value in coefficients.items():
            matrix[row_number, column] = value

    result = milp(
        c=objective,
        integrality=integrality,
        bounds=Bounds(lower_bounds, upper_bounds),
        constraints=LinearConstraint(
            matrix.tocsr(), np.asarray(row_lower), np.asarray(row_upper)
        ),
        options={"disp": False},
    )

    if not result.success or result.x is None:
        raise RuntimeError(f"Optimization failed: {result.message}")

    values = result.x
    assignments: Dict[str, str] = {}
    starts: List[Tuple[str, str]] = []
    ends: List[Tuple[str, str]] = []
    links: List[Tuple[str, str, str]] = []

    for t, trip in enumerate(trips):
        for k, vehicle in enumerate(fleet):
            if values[x_idx[t, k]] > 0.5:
                assignments[trip.trip_id] = vehicle.fleet_id
            if values[start_idx[t, k]] > 0.5:
                starts.append((trip.trip_id, vehicle.fleet_id))
            if values[end_idx[t, k]] > 0.5:
                ends.append((trip.trip_id, vehicle.fleet_id))

    for i, j in connections:
        for k, vehicle in enumerate(fleet):
            if values[link_idx[i, j, k]] > 0.5:
                links.append((trips[i].trip_id, trips[j].trip_id, vehicle.fleet_id))

    units_used = {
        vehicle.fleet_id: sum(1 for _, fleet_id in starts if fleet_id == vehicle.fleet_id)
        for vehicle in fleet
    }

    return Solution(
        objective=float(result.fun),
        assignments=assignments,
        starts=sorted(starts),
        ends=sorted(ends),
        links=sorted(links),
        units_used=units_used,
    )
