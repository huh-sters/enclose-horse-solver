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
    CellType.CHERRY: 4,   # 1 base + 3 bonus
    CellType.WATER: 0,    # never enclosed
}

# Wall cost in Costly Walls mode
_COSTLY_WALL_PENALTY = 6


@dataclass
class Solution:
    """Holds the solved wall placement and enclosed region for a puzzle."""

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

    # Lovebirds: both horses must be in the same connected enclosed region.
    # Enforced by sending one unit of flow from horse1 to horse2 through
    # the enclosed region (portals treated as directed edges).
    if mode == Mode.LOVEBIRDS and len(grid.animals) >= 2:
        h1 = grid.animals[0]
        h2 = grid.animals[1]

        # Build directed edge list over non-water adjacencies + portal teleports
        directed_edges: list[tuple[int, int, int, int]] = []
        for r in range(nrows - 1):
            for c in range(ncols):
                if CellType.WATER not in (grid.cell_at(r, c).type, grid.cell_at(r + 1, c).type):
                    directed_edges.append((r, c, r + 1, c))
                    directed_edges.append((r + 1, c, r, c))
        for r in range(nrows):
            for c in range(ncols - 1):
                if CellType.WATER not in (grid.cell_at(r, c).type, grid.cell_at(r, c + 1).type):
                    directed_edges.append((r, c, r, c + 1))
                    directed_edges.append((r, c + 1, r, c))
        for positions in grid.portals.values():
            if len(positions) == 2:
                (rp1, cp1), (rp2, cp2) = positions
                directed_edges.append((rp1, cp1, rp2, cp2))
                directed_edges.append((rp2, cp2, rp1, cp1))

        # One boolean flow variable per directed edge
        flow: dict[tuple[int, int, int, int], cp_model.BoolVarT] = {
            e: model.new_bool_var(f"flow_{e[0]}_{e[1]}_{e[2]}_{e[3]}")
            for e in directed_edges
        }

        # Flow may only traverse enclosed cells
        for (r1f, c1f, r2f, c2f), fvar in flow.items():
            model.add(fvar <= enclosed[r1f][c1f])
            model.add(fvar <= enclosed[r2f][c2f])

        # Build out/in adjacency lists keyed by cell
        out_flow: dict[tuple[int, int], list] = {}
        in_flow: dict[tuple[int, int], list] = {}
        for (r1f, c1f, r2f, c2f), fvar in flow.items():
            out_flow.setdefault((r1f, c1f), []).append(fvar)
            in_flow.setdefault((r2f, c2f), []).append(fvar)

        h1_pos = (h1.row, h1.col)
        h2_pos = (h2.row, h2.col)

        # Flow conservation at intermediate nodes (in == out)
        for r in range(nrows):
            for c in range(ncols):
                if (r, c) in (h1_pos, h2_pos):
                    continue
                if grid.cell_at(r, c).type == CellType.WATER:
                    continue
                outs = out_flow.get((r, c), [])
                ins = in_flow.get((r, c), [])
                if outs or ins:
                    model.add(sum(outs) == sum(ins))

        # Horse1 is source: net outflow = 1
        model.add(
            sum(out_flow.get(h1_pos, [])) - sum(in_flow.get(h1_pos, [])) == 1
        )
        # Horse2 is sink: net inflow = 1
        model.add(
            sum(in_flow.get(h2_pos, [])) - sum(out_flow.get(h2_pos, [])) == 1
        )

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
        model.add(total_walls <= walls)

    # Objective
    score_expr = sum(
        _CELL_SCORE[grid.cell_at(r, c).type] * enclosed[r][c]
        for r in range(nrows)
        for c in range(ncols)
        if grid.cell_at(r, c).type != CellType.WATER
    )

    if mode == Mode.COSTLY_WALLS:
        # Each wall costs 6 points; maximise net score regardless of wall count.
        model.maximize(score_expr - _COSTLY_WALL_PENALTY * total_walls)
    elif walls is not None:
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
