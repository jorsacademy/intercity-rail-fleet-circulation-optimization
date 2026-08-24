from __future__ import annotations

from collections import defaultdict

from src.model import sample_data, solve_fleet_circulation


def main() -> None:
    trips, fleet = sample_data()
    solution = solve_fleet_circulation(trips, fleet)

    print(f"Optimal objective: {solution.objective:.2f}\n")

    print("Fleet assignments")
    print("-----------------")
    for trip in trips:
        print(f"{trip.trip_id}: {solution.assignments[trip.trip_id]}")

    print("\nPhysical units used")
    print("-------------------")
    for vehicle in fleet:
        print(f"{vehicle.fleet_id}: {solution.units_used[vehicle.fleet_id]}")

    successors = {(first, fleet_id): second for first, second, fleet_id in solution.links}
    starts_by_fleet = defaultdict(list)
    for trip_id, fleet_id in solution.starts:
        starts_by_fleet[fleet_id].append(trip_id)

    print("\nVehicle circulations")
    print("--------------------")
    for fleet_id in sorted(starts_by_fleet):
        for number, start_trip in enumerate(sorted(starts_by_fleet[fleet_id]), start=1):
            chain = [start_trip]
            current = start_trip
            while (current, fleet_id) in successors:
                current = successors[current, fleet_id]
                chain.append(current)
            print(f"{fleet_id} unit {number}: {' -> '.join(chain)}")


if __name__ == "__main__":
    main()
