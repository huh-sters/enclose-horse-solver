"""Tests for src/parser.py."""
from pathlib import Path

import pytest

from src.parser import CellType, Mode, parse_csv

FIXTURE = Path(__file__).parent / "fixtures" / "day98_lovebirds.csv"


def test_parse_returns_correct_dimensions():
    grid = parse_csv(FIXTURE)
    assert grid.rows == 15
    assert grid.cols == 15


def test_animals_are_horses():
    grid = parse_csv(FIXTURE)
    animals = grid.animals
    assert len(animals) == 2
    for a in animals:
        assert a.type == CellType.HORSE


def test_water_cells_present():
    grid = parse_csv(FIXTURE)
    water_cells = [
        grid.cell_at(r, c)
        for r in range(grid.rows)
        for c in range(grid.cols)
        if grid.cell_at(r, c).type == CellType.WATER
    ]
    assert len(water_cells) > 0


def test_portals_detected():
    grid = parse_csv(FIXTURE)
    assert "A" in grid.portals
    assert "B" in grid.portals
    assert len(grid.portals["A"]) == 2
    assert len(grid.portals["B"]) == 2


def test_apple_cells_present():
    grid = parse_csv(FIXTURE)
    apples = [
        grid.cell_at(r, c)
        for r in range(grid.rows)
        for c in range(grid.cols)
        if grid.cell_at(r, c).type == CellType.APPLE
    ]
    assert len(apples) > 0


def test_bees_cells_present():
    grid = parse_csv(FIXTURE)
    bees = [
        grid.cell_at(r, c)
        for r in range(grid.rows)
        for c in range(grid.cols)
        if grid.cell_at(r, c).type == CellType.BEES
    ]
    assert len(bees) > 0


def test_mode_lovebirds():
    grid = parse_csv(FIXTURE)
    assert grid.detect_mode() == Mode.LOVEBIRDS


def test_cell_coordinates_match_position():
    grid = parse_csv(FIXTURE)
    for r in range(grid.rows):
        for c in range(grid.cols):
            cell = grid.cell_at(r, c)
            assert cell.row == r
            assert cell.col == c


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        parse_csv(Path("nonexistent.csv"))
