"""CP-SAT model: finds optimal wall placement for an enclose.horse puzzle.

Walls are placed ON cells (only on grass cells).  The enclosed region is
the connected component of non-wall, non-water cells containing the
horse(s) that cannot reach the map perimeter.
"""
from __future__ import annotations

from dataclasses import dataclass

from ortools.sat.python import cp_model

from .parser import CellType, Grid, Mode

# Score contribution per cell type when the cell is enclosed
_CELL_SCORE: dict[CellType, int] = {
    CellType.GRASS: 1,
    CellType.HORSE: 1,
    CellType.UNICORN: 1,
    CellType.PORTAL: 1,
    CellType.APPLE: 11,   # 1 base + 10 bonus
    CellType.BEES: -4,    # 1 base − 5 penalty
    CellType.WATER: 0,    # never enclosed
}


@dataclass
class Solution:
    wall: list[list[bool]]      # wall[r][c] = True if a wall is placed here
    enclosed: list[list[bool]]  # enclosed[r][c] = True if cell is in the enclosed region
    wall_count: int
    enclosed_count: int
    score: int
    status: str


def build_and_solve(  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    grid: Grid,
    walls: int | None,
    mode: Mode | None = None,
) -> Solution | None:
    """Build and solve the CP-SAT model.

    Args:
        grid:  Parsed puzzle grid.
        walls: Exact number of wall cells to place.  None → minimise walls.
        mode:  Puzzle mode; drives the Lovebirds portal-bridge constraint.

    Returns:
        A Solution if one is found, otherwise None.
    """
    model = cp_model.CpModel()
    nrows, ncols = grid.rows, grid.cols

    # wall[r][c]: a wall block placed at this cell (grass only)
    wall: list[list[cp_model.BoolVarT]] = [
        [model.new_bool_var(f"wall_{r}_{c}") for c in range(ncols)]
        for r in range(nrows)
    ]

    # enclosed[r][c]: cell is inside the enclosed region
    enclosed: list[list[cp_model.BoolVarT]] = [
        [model.new_bool_var(f"enc_{r}_{c}") for c in range(ncols)]
        for r in range(nrows)
    ]

    for r in range(nrows):
        for c in range(ncols):
            cell = grid.cell_at(r, c)

            # Walls can only be placed on grass cells
            if cell.type != CellType.GRASS:
                model.add(wall[r][c] == 0)

            # Water cells are never enclosed and never walled
            if cell.type == CellType.WATER:
                model.add(enclosed[r][c] == 0)

            # A cell cannot simultaneously be a wall and be enclosed
            model.add(enclosed[r][c] + wall[r][c] <= 1)

    # Horse/unicorn cells must be enclosed
    for r in range(nrows):
        for c in range(ncols):
            if grid.cell_at(r, c).type in (CellType.HORSE, CellType.UNICORN):
                model.add(enclosed[r][c] == 1)

    # Map perimeter: every perimeter cell is accessible from outside the map.
    # A free (non-wall) perimeter cell is therefore NOT enclosed.
    # Forced by: enclosed[r][c] <= wall[r][c]  →  enclosed = 0 when wall = 0.
    perimeter = (
        [(0, c) for c in range(ncols)]
        + [(nrows - 1, c) for c in range(ncols)]
        + [(r, 0) for r in range(1, nrows - 1)]
        + [(r, ncols - 1) for r in range(1, nrows - 1)]
    )
    for r, c in perimeter:
        model.add(enclosed[r][c] <= wall[r][c])

    # Portal constraints: both ends of a portal must be on the same side of
    # the enclosure boundary (and portals cannot have walls placed on them).
    for positions in grid.portals.values():
        if len(positions) == 2:
            (r1, c1), (r2, c2) = positions
            model.add(enclosed[r1][c1] == enclosed[r2][c2])

    # Lovebirds: the two enclosed horse regions must be bridged by a portal.
    if mode == Mode.LOVEBIRDS and grid.portals:
        portal_bridge_vars: list[cp_model.BoolVarT] = []
        for positions in grid.portals.values():
            if len(positions) == 2:
                (r1, c1), _ = positions
                portal_bridge_vars.append(enclosed[r1][c1])
        if portal_bridge_vars:
            model.add_bool_or(portal_bridge_vars)

    # Outside-propagation constraints.
    # If c1 is NOT enclosed and neither c1 nor c2 is a wall, then c2 is also
    # NOT enclosed (outside status propagates through free cells).
    # Linearised: enclosed[c2] <= enclosed[c1] + wall[c1] + wall[c2]
    # Applied symmetrically so propagation works in both directions.
    def _propagate(r1: int, c1: int, r2: int, c2: int) -> None:
        if CellType.WATER in (grid.cell_at(r1, c1).type, grid.cell_at(r2, c2).type):
            return  # water blocks movement — no propagation through water
        model.add(enclosed[r2][c2] <= enclosed[r1][c1] + wall[r1][c1] + wall[r2][c2])
        model.add(enclosed[r1][c1] <= enclosed[r2][c2] + wall[r1][c1] + wall[r2][c2])

    for r in range(nrows - 1):
        for c in range(ncols):
            _propagate(r, c, r + 1, c)
    for r in range(nrows):
        for c in range(ncols - 1):
            _propagate(r, c, r, c + 1)

    # Portal teleportation also propagates outside status
    for positions in grid.portals.values():
        if len(positions) == 2:
            (r1, c1), (r2, c2) = positions
            # Portals can never have walls (they're not grass), so wall = 0 always.
            # enclosed equality is already enforced above.
            _propagate(r1, c1, r2, c2)

    # Wall count
    all_wall_vars = [wall[r][c] for r in range(nrows) for c in range(ncols)]
    total_walls = model.new_int_var(0, len(all_wall_vars), "total_walls")
    model.add(total_walls == sum(all_wall_vars))

    if walls is not None:
        model.add(total_walls == walls)

    # Objective
    score_expr = sum(
        _CELL_SCORE[grid.cell_at(r, c).type] * enclosed[r][c]
        for r in range(nrows)
        for c in range(ncols)
        if grid.cell_at(r, c).type != CellType.WATER
    )

    if walls is not None:
        model.maximize(score_expr)
    else:
        model.minimize(total_walls)

    # Solve
    solver = cp_model.CpSolver()
    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    wall_vals = [
        [bool(solver.value(wall[r][c])) for c in range(ncols)]
        for r in range(nrows)
    ]
    enc_vals = [
        [bool(solver.value(enclosed[r][c])) for c in range(ncols)]
        for r in range(nrows)
    ]
    wc = solver.value(total_walls)
    enc_count = sum(enc_vals[r][c] for r in range(nrows) for c in range(ncols))
    sc = sum(
        _CELL_SCORE[grid.cell_at(r, c).type] * enc_vals[r][c]
        for r in range(nrows)
        for c in range(ncols)
        if grid.cell_at(r, c).type != CellType.WATER
    )

    return Solution(
        wall=wall_vals,
        enclosed=enc_vals,
        wall_count=wc,
        enclosed_count=enc_count,
        score=sc,
        status="optimal" if status == cp_model.OPTIMAL else "feasible",
    )
