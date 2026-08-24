import pytest

from src.model import sample_data, solve_fleet_circulation


def test_sample_solution_is_optimal_and_complete():
    trips, fleet = sample_data()
    solution = solve_fleet_circulation(trips, fleet)

    assert solution.objective == pytest.approx(8845.40, abs=1e-6)
    assert set(solution.assignments) == {trip.trip_id for trip in trips}
    assert solution.units_used == {"FLEET_A": 2, "FLEET_B": 1}
    assert len(solution.starts) == 3
    assert len(solution.ends) == 3


def test_capacity_and_fleet_availability_are_respected():
    trips, fleet = sample_data()
    solution = solve_fleet_circulation(trips, fleet)

    trip_by_id = {trip.trip_id: trip for trip in trips}
    fleet_by_id = {vehicle.fleet_id: vehicle for vehicle in fleet}

    for trip_id, fleet_id in solution.assignments.items():
        assert fleet_by_id[fleet_id].capacity >= trip_by_id[trip_id].demand

    for fleet_id, units_used in solution.units_used.items():
        assert units_used <= fleet_by_id[fleet_id].available_units


def test_links_respect_station_continuity_turnaround_and_flow():
    trips, fleet = sample_data()
    solution = solve_fleet_circulation(trips, fleet, min_turnaround=30)

    trip_by_id = {trip.trip_id: trip for trip in trips}
    incoming = {(trip.trip_id, vehicle.fleet_id): 0 for trip in trips for vehicle in fleet}
    outgoing = {(trip.trip_id, vehicle.fleet_id): 0 for trip in trips for vehicle in fleet}

    for first_id, second_id, fleet_id in solution.links:
        first = trip_by_id[first_id]
        second = trip_by_id[second_id]

        assert first.destination == second.origin
        assert second.departure - first.arrival >= 30
        assert solution.assignments[first_id] == fleet_id
        assert solution.assignments[second_id] == fleet_id

        outgoing[first_id, fleet_id] += 1
        incoming[second_id, fleet_id] += 1

    start_set = set(solution.starts)
    end_set = set(solution.ends)

    for trip in trips:
        assigned_fleet = solution.assignments[trip.trip_id]
        key = (trip.trip_id, assigned_fleet)
        assert incoming[key] + int(key in start_set) == 1
        assert outgoing[key] + int(key in end_set) == 1
