# Intercity Rail Fleet Circulation Optimization

A compact mixed-integer optimization project for assigning fleet types to scheduled passenger trips and building feasible daily vehicle circulations.

The model is intentionally generic. All data are synthetic, and no real or fictional transport operator is referenced.

## Problem

A passenger transport network has a fixed timetable. Each scheduled trip has an origin, destination, departure time, arrival time, passenger demand, and route distance. Several fleet types are available, each with a seat capacity, limited number of physical units, operating cost, and activation cost.

The optimization model decides:

- which fleet type operates each trip,
- which compatible trips are linked into the same physical vehicle circulation,
- where each vehicle circulation starts and ends.

The objective minimizes total operating and circulation cost while respecting passenger capacity, timetable compatibility, turnaround time, station continuity, and fleet availability.

## Mathematical structure

Binary decision variables:

- `x[t,k] = 1` if trip `t` is assigned to fleet type `k`,
- `y[i,j,k] = 1` if a vehicle of fleet type `k` operates trip `j` immediately after trip `i`,
- `s[t,k] = 1` if trip `t` starts a vehicle circulation of fleet type `k`,
- `e[t,k] = 1` if trip `t` ends a vehicle circulation of fleet type `k`.

Core constraints include:

1. Exactly one fleet type is assigned to every trip.
2. A fleet type can only be assigned when its capacity covers passenger demand.
3. A connection is allowed only when the first trip ends where the next trip begins and the minimum turnaround time is satisfied.
4. Flow conservation ensures that every assigned trip has exactly one predecessor or circulation start, and exactly one successor or circulation end.
5. The number of circulation starts for each fleet type cannot exceed the number of available physical units.

## Objective

The objective combines:

- distance-based operating cost,
- vehicle activation cost,
- empty-seat penalty,
- idle-time penalty between connected trips.

These weights are illustrative and can be replaced with calibrated operational data.

## Installation

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Run

```bash
python -m src.run
```

## Test

```bash
pytest -q
```

The test suite verifies trip coverage, passenger capacity, fleet availability, station continuity, minimum turnaround feasibility, circulation flow conservation, and the deterministic optimum of the included synthetic instance.

## Solver

The model uses `scipy.optimize.milp`, which is backed by HiGHS. No commercial optimization solver is required.

## Synthetic example

The included instance contains eight scheduled trips and two fleet types. The verified optimum assigns the higher-capacity fleet to the four high-demand trips and uses two units of the smaller fleet for the remaining four trips. The solution requires three physical vehicle circulations.

For the included objective coefficients, the optimal objective value is `8845.40`.

## Project structure

```text
.
├── LICENSE
├── README.md
├── requirements.txt
├── src
│   ├── __init__.py
│   ├── model.py
│   └── run.py
└── tests
    └── test_model.py
```

## License

Non-commercial use only. Commercial use, sale, sublicensing for commercial purposes, paid-service integration, or incorporation into a commercial product is prohibited without separate written permission. See `LICENSE` for the full terms.
