"""Tests for src/model.py."""
from pathlib import Path

from src.model import build_and_solve
from src.parser import CellType, Mode, parse_csv

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


def test_all_animals_are_enclosed():
    grid = parse_csv(FIXTURE)
    solution = build_and_solve(grid, walls=None)
    assert solution is not None
    for animal in grid.animals:
        assert solution.enclosed[animal.row][animal.col], (
            f"Animal at ({animal.row},{animal.col}) not enclosed"
        )


def test_water_cells_not_enclosed():
    grid = parse_csv(FIXTURE)
    solution = build_and_solve(grid, walls=None)
    assert solution is not None
    for r in range(grid.rows):
        for c in range(grid.cols):
            if grid.cell_at(r, c).type == CellType.WATER:
                assert not solution.enclosed[r][c], (
                    f"Water at ({r},{c}) should not be enclosed"
                )


def test_walls_only_on_grass():
    grid = parse_csv(FIXTURE)
    solution = build_and_solve(grid, walls=None)
    assert solution is not None
    for r in range(grid.rows):
        for c in range(grid.cols):
            if solution.wall[r][c]:
                assert grid.cell_at(r, c).type == CellType.GRASS, (
                    f"Wall at ({r},{c}) is not a grass cell"
                )


def test_cell_not_both_wall_and_enclosed():
    grid = parse_csv(FIXTURE)
    solution = build_and_solve(grid, walls=None)
    assert solution is not None
    for r in range(grid.rows):
        for c in range(grid.cols):
            assert not (solution.wall[r][c] and solution.enclosed[r][c]), (
                f"Cell ({r},{c}) is both a wall and enclosed"
            )


def test_portal_pairs_on_same_side():
    grid = parse_csv(FIXTURE)
    solution = build_and_solve(grid, walls=None)
    assert solution is not None
    for portal_id, positions in grid.portals.items():
        if len(positions) == 2:
            (r1, c1), (r2, c2) = positions
            assert solution.enclosed[r1][c1] == solution.enclosed[r2][c2], (
                f"Portal {portal_id} ends are on different sides"
            )


def test_wall_budget_not_exceeded():
    grid = parse_csv(FIXTURE)
    solution = build_and_solve(grid, walls=13, mode=Mode.LOVEBIRDS)
    assert solution is not None
    assert solution.wall_count <= 13


def test_infeasible_returns_none():
    grid = parse_csv(FIXTURE)
    # 0 walls is impossible: the horses are surrounded by free cells on two sides
    solution = build_and_solve(grid, walls=0)
    assert solution is None


def test_solution_status_optimal_for_minimise():
    grid = parse_csv(FIXTURE)
    solution = build_and_solve(grid, walls=None)
    assert solution is not None
    assert solution.status == "optimal"


def test_enclosed_count_matches_field():
    grid = parse_csv(FIXTURE)
    solution = build_and_solve(grid, walls=None)
    assert solution is not None
    manual_count = sum(
        solution.enclosed[r][c]
        for r in range(grid.rows)
        for c in range(grid.cols)
    )
    assert solution.enclosed_count == manual_count


def test_lovebirds_portal_bridge():
    """In Lovebirds mode the two enclosures must be bridged by a portal."""
    grid = parse_csv(FIXTURE)
    assert grid.detect_mode() == Mode.LOVEBIRDS
    solution = build_and_solve(grid, walls=None, mode=Mode.LOVEBIRDS)
    assert solution is not None
    portal_bridged = any(
        solution.enclosed[r][c]
        for positions in grid.portals.values()
        if len(positions) == 2
        for r, c in positions
    )
    assert portal_bridged, "Lovebirds solution must have at least one portal pair enclosed"
