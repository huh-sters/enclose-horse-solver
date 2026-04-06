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
        mode:  Puzzle mode; drives the objective (e.g. costly-walls penalty).

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

    # Connectivity: ALL enclosed cells must form a single connected region
    # containing the first animal.  Modelled as a spanning arborescence rooted
    # at the first animal: each non-root enclosed cell must have exactly one
    # enclosed "parent" neighbour with a strictly smaller BFS level.
    # This generalises the old Lovebirds-only flow constraint; lovebirds
    # connectivity is now automatically enforced because the second horse is
    # enclosed and must therefore appear in the arborescence.
    if grid.animals:
        root = grid.animals[0]
        max_level = nrows * ncols  # strict upper bound on BFS depth

        level: list[list[cp_model.IntVar]] = [
            [model.new_int_var(0, max_level, f"lev_{r}_{c}") for c in range(ncols)]
            for r in range(nrows)
        ]
        model.add(level[root.row][root.col] == 0)

        # Directed edge list: non-water adjacencies + portal teleports
        conn_edges: list[tuple[int, int, int, int]] = []
        for r in range(nrows - 1):
            for c in range(ncols):
                if CellType.WATER not in (
                    grid.cell_at(r, c).type, grid.cell_at(r + 1, c).type
                ):
                    conn_edges.append((r, c, r + 1, c))
                    conn_edges.append((r + 1, c, r, c))
        for r in range(nrows):
            for c in range(ncols - 1):
                if CellType.WATER not in (
                    grid.cell_at(r, c).type, grid.cell_at(r, c + 1).type
                ):
                    conn_edges.append((r, c, r, c + 1))
                    conn_edges.append((r, c + 1, r, c))
        for positions in grid.portals.values():
            if len(positions) == 2:
                (rp1, cp1), (rp2, cp2) = positions
                conn_edges.append((rp1, cp1, rp2, cp2))
                conn_edges.append((rp2, cp2, rp1, cp1))

        # par[(r1,c1,r2,c2)] = 1  ⟺  (r1,c1) is the tree-parent of (r2,c2)
        par: dict[tuple[int, int, int, int], cp_model.BoolVarT] = {
            e: model.new_bool_var(f"par_{e[0]}_{e[1]}_{e[2]}_{e[3]}")
            for e in conn_edges
        }

        # Parent edge requires both endpoints to be enclosed
        for (r1p, c1p, r2p, c2p), pvar in par.items():
            model.add(pvar <= enclosed[r1p][c1p])
            model.add(pvar <= enclosed[r2p][c2p])

        # Build per-cell incoming-edge lists
        incoming: dict[tuple[int, int], list[tuple[int, int, int, int, cp_model.BoolVarT]]] = {}
        for (r1p, c1p, r2p, c2p), pvar in par.items():
            incoming.setdefault((r2p, c2p), []).append((r1p, c1p, r2p, c2p, pvar))

        root_pos = (root.row, root.col)
        for r in range(nrows):
            for c in range(ncols):
                inc = incoming.get((r, c), [])
                inc_pvars = [pvar for *_, pvar in inc]

                if (r, c) == root_pos:
                    # Root has no parent
                    model.add(sum(inc_pvars) == 0)
                else:
                    # Enclosed → exactly one parent; not enclosed → no parent
                    model.add(sum(inc_pvars) == enclosed[r][c])

                # Child level must exceed parent level
                for r1p, c1p, _r2p, _c2p, pvar in inc:
                    model.add(
                        level[r][c] >= level[r1p][c1p] + 1
                    ).only_enforce_if(pvar)

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

    if mode == Mode.COSTLY_WALLS:
        sc -= _COSTLY_WALL_PENALTY * wc

    return Solution(
        wall=wall_vals,
        enclosed=enc_vals,
        wall_count=wc,
        enclosed_count=enc_count,
        score=sc,
        status="optimal" if status == cp_model.OPTIMAL else "feasible",
    )
