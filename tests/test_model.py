"""Tests for src/model.py."""
from pathlib import Path

from src.model import build_and_solve
from src.parser import CellType, parse_csv

FIXTURE = Path(__file__).parent / "fixtures" / "day98_lovebirds.csv"


def test_minimum_wall_solve_finds_solution():
    grid = parse_csv(FIXTURE)
    solution = build_and_solve(grid, walls=None)
    assert solution is not None


def test_minimum_wall_count_is_positive():
    grid = parse_csv(FIXTURE)
    solution = build_and_solve(grid, walls=None)
    assert solution is not None
    assert solution.wall_count > 0


def test_all_animals_are_inside():
    grid = parse_csv(FIXTURE)
    solution = build_and_solve(grid, walls=None)
    assert solution is not None
    for animal in grid.animals:
        assert solution.inside[animal.row][animal.col], (
            f"Animal at ({animal.row},{animal.col}) not enclosed"
        )


def test_water_cells_are_outside():
    grid = parse_csv(FIXTURE)
    solution = build_and_solve(grid, walls=None)
    assert solution is not None
    for r in range(grid.rows):
        for c in range(grid.cols):
            if grid.cell_at(r, c).type == CellType.WATER:
                assert not solution.inside[r][c], (
                    f"Water at ({r},{c}) should not be inside the enclosure"
                )


def test_portal_pairs_on_same_side():
    grid = parse_csv(FIXTURE)
    solution = build_and_solve(grid, walls=None)
    assert solution is not None
    for portal_id, positions in grid.portals.items():
        if len(positions) == 2:
            (r1, c1), (r2, c2) = positions
            assert solution.inside[r1][c1] == solution.inside[r2][c2], (
                f"Portal {portal_id} ends are on different sides of the enclosure"
            )


def test_exact_wall_count_constraint():
    grid = parse_csv(FIXTURE)
    sol_min = build_and_solve(grid, walls=None)
    assert sol_min is not None
    # Solve again with the exact minimum wall count
    sol_exact = build_and_solve(grid, walls=sol_min.wall_count)
    assert sol_exact is not None
    assert sol_exact.wall_count == sol_min.wall_count


def test_infeasible_returns_none():
    grid = parse_csv(FIXTURE)
    # Requesting 1 wall is impossible for any real puzzle
    solution = build_and_solve(grid, walls=1)
    assert solution is None


def test_solution_status_is_optimal_for_minimise():
    grid = parse_csv(FIXTURE)
    solution = build_and_solve(grid, walls=None)
    assert solution is not None
    assert solution.status == "optimal"


def test_lovebirds_portal_bridge():
    """In Lovebirds mode the two enclosures must be bridged by a portal."""
    from src.parser import Mode
    grid = parse_csv(FIXTURE)
    assert grid.detect_mode() == Mode.LOVEBIRDS
    solution = build_and_solve(grid, walls=None, mode=Mode.LOVEBIRDS)
    assert solution is not None
    # At least one portal pair must have both cells inside
    portal_bridged = any(
        solution.inside[r][c]
        for positions in grid.portals.values()
        if len(positions) == 2
        for r, c in positions
    )
    assert portal_bridged, "Lovebirds solution must have at least one portal pair inside"
