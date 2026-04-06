"""CSV parser: reads an enclose.horse map export into a Grid dataclass."""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class CellType(Enum):
    GRASS = "grass"
    WATER = "water"
    HORSE = "horse"
    UNICORN = "unicorn"
    APPLE = "apple"
    BEES = "bees"
    PORTAL = "portal"


class Mode(Enum):
    STANDARD = "standard"
    LOVEBIRDS = "lovebirds"
    HORSE_UNICORN = "horse_unicorn"


@dataclass
class Cell:
    row: int
    col: int
    type: CellType
    portal_id: str | None = None


@dataclass
class Grid:
    rows: int
    cols: int
    cells: list[list[Cell]]
    portals: dict[str, list[tuple[int, int]]] = field(default_factory=dict)

    def cell_at(self, r: int, c: int) -> Cell:
        return self.cells[r][c]

    @property
    def animals(self) -> list[Cell]:
        return [
            self.cells[r][c]
            for r in range(self.rows)
            for c in range(self.cols)
            if self.cells[r][c].type in (CellType.HORSE, CellType.UNICORN)
        ]

    def detect_mode(self) -> Mode:
        animals = self.animals
        horses = [a for a in animals if a.type == CellType.HORSE]
        unicorns = [a for a in animals if a.type == CellType.UNICORN]
        if len(horses) == 2 and not unicorns:
            return Mode.LOVEBIRDS
        if len(horses) == 1 and len(unicorns) == 1:
            return Mode.HORSE_UNICORN
        return Mode.STANDARD


# Single-character portal labels the game uses
_PORTAL_LABELS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ") - frozenset("HWUPZ")

# Direct mapping from CSV value to CellType (non-portal entries)
_VALUE_TO_TYPE: dict[str, CellType] = {
    "W": CellType.WATER,
    "H": CellType.HORSE,
    "U": CellType.UNICORN,
    "P": CellType.APPLE,
    "Z": CellType.BEES,
}


def _parse_cell(value: str, row: int, col: int) -> Cell:
    v = value.strip().upper()
    cell_type = _VALUE_TO_TYPE.get(v)
    if cell_type is not None:
        return Cell(row, col, cell_type)
    if v in _PORTAL_LABELS:
        return Cell(row, col, CellType.PORTAL, portal_id=v)
    return Cell(row, col, CellType.GRASS)


def parse_csv(path: Path) -> Grid:
    """Parse a CSV map exported from enclose.horse into a Grid."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        raw_rows = list(reader)

    max_cols = max(len(r) for r in raw_rows)
    cells: list[list[Cell]] = []
    portals: dict[str, list[tuple[int, int]]] = {}

    for r, raw_row in enumerate(raw_rows):
        row_cells: list[Cell] = []
        for c in range(max_cols):
            raw_val = raw_row[c] if c < len(raw_row) else ""
            cell = _parse_cell(raw_val, r, c)
            if cell.type == CellType.PORTAL and cell.portal_id:
                portals.setdefault(cell.portal_id, []).append((r, c))
            row_cells.append(cell)
        cells.append(row_cells)

    return Grid(
        rows=len(raw_rows),
        cols=max_cols,
        cells=cells,
        portals=portals,
    )
