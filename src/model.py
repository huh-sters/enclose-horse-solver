"""CP-SAT model: finds optimal wall placement for an enclose.horse puzzle."""
from __future__ import annotations

from dataclasses import dataclass

from ortools.sat.python import cp_model

from .parser import CellType, Grid, Mode


@dataclass
class Solution:
    inside: list[list[bool]]  # inside[r][c] = True if cell is enclosed
    wall_count: int
    score: int
    status: str


def build_and_solve(  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    grid: Grid,
    walls: int | None,
    mode: Mode | None = None,  # noqa: ARG001  # pylint: disable=unused-argument
) -> Solution | None:
    """Build and solve the CP-SAT model.

    Args:
        grid:  Parsed puzzle grid.
        walls: If given, the enclosure perimeter must be exactly this many
               fence segments.  If None, the minimum is found.
        mode:  Puzzle mode (currently unused; all animals are simply forced
               inside, which handles all three modes correctly).

    Returns:
        A Solution if one is found, otherwise None.
    """
    model = cp_model.CpModel()
    nrows, ncols = grid.rows, grid.cols

    # Boolean variable: is this cell inside the enclosure?
    inside: list[list[cp_model.BoolVarT]] = [
        [model.new_bool_var(f"in_{r}_{c}") for c in range(ncols)]
        for r in range(nrows)
    ]

    # Hard constraints: animals inside, water outside.
    for r in range(nrows):
        for c in range(ncols):
            cell = grid.cell_at(r, c)
            if cell.type in (CellType.HORSE, CellType.UNICORN):
                model.add(inside[r][c] == 1)
            elif cell.type == CellType.WATER:
                model.add(inside[r][c] == 0)

    # Portal constraints: both ends of each portal must be on the same side.
    for positions in grid.portals.values():
        if len(positions) == 2:
            (r1, c1), (r2, c2) = positions
            model.add(inside[r1][c1] == inside[r2][c2])

    # Lovebirds constraint: the two horses must be connected via a portal.
    # Because inside[A1] == inside[A2] is already enforced, requiring one portal
    # pair to be inside is equivalent to requiring the two enclosed regions to be
    # bridged (both ends of that portal act as a passage between regions).
    if mode == Mode.LOVEBIRDS and grid.portals:
        portal_bridge_vars: list[cp_model.BoolVarT] = []
        for positions in grid.portals.values():
            if len(positions) == 2:
                (r1, c1), _ = positions
                # inside[r1][c1] == inside[r2][c2] is already guaranteed;
                # use either end as the "portal is bridging" indicator.
                portal_bridge_vars.append(inside[r1][c1])
        if portal_bridge_vars:
            model.add_bool_or(portal_bridge_vars)

    # Wall (fence segment) variables.
    # Rules:
    #   • Water cells are natural barriers: any boundary with a water cell is
    #     free (no fence segment needed).
    #   • The map perimeter is an escape route: a perimeter edge beside a
    #     non-water inside cell DOES cost a fence segment.
    #   • All other interior edges cost a fence segment when the two cells
    #     are on different sides of the enclosure.
    wall_vars: list[cp_model.BoolVarT] = []

    def _add_perimeter_edge(r1: int, c1: int, label: str) -> None:
        """Perimeter edge: free if the cell is water, otherwise costs a wall."""
        if grid.cell_at(r1, c1).type == CellType.WATER:
            return
        w = model.new_bool_var(label)
        model.add(w == inside[r1][c1])
        wall_vars.append(w)

    def _add_interior_edge(r1: int, c1: int, r2: int, c2: int, label: str) -> None:
        """Interior edge: free if either cell is water, otherwise costs a wall
        when the two cells are on opposite sides of the enclosure boundary.
        Encodes w = |inside[r1][c1] - inside[r2][c2]|.
        """
        if CellType.WATER in (grid.cell_at(r1, c1).type, grid.cell_at(r2, c2).type):
            return  # water boundary: natural barrier, no fence needed
        w = model.new_bool_var(label)
        model.add(w >= inside[r1][c1] - inside[r2][c2])
        model.add(w >= inside[r2][c2] - inside[r1][c1])
        model.add(w <= inside[r1][c1] + inside[r2][c2])
        model.add(w <= 2 - inside[r1][c1] - inside[r2][c2])
        wall_vars.append(w)

    # Perimeter edges (map boundary is passable — escape route for the animal)
    for c in range(ncols):
        _add_perimeter_edge(0, c, f"wp_top_{c}")
        _add_perimeter_edge(nrows - 1, c, f"wp_bot_{c}")
    for r in range(nrows):
        _add_perimeter_edge(r, 0, f"wp_left_{r}")
        _add_perimeter_edge(r, ncols - 1, f"wp_right_{r}")

    # Interior horizontal edges (between row r and row r+1)
    for r in range(nrows - 1):
        for c in range(ncols):
            _add_interior_edge(r, c, r + 1, c, f"wh_{r}_{c}")

    # Interior vertical edges (between col c and col c+1)
    for r in range(nrows):
        for c in range(ncols - 1):
            _add_interior_edge(r, c, r, c + 1, f"wv_{r}_{c}")

    total_walls = model.new_int_var(0, len(wall_vars), "total_walls")
    model.add(total_walls == sum(wall_vars))

    if walls is not None:
        model.add(total_walls == walls)

    # Score terms: apples (+10) and bees (-5) if inside.
    score_terms: list[tuple[int, cp_model.BoolVarT]] = []
    for r in range(nrows):
        for c in range(ncols):
            cell = grid.cell_at(r, c)
            if cell.type == CellType.APPLE:
                score_terms.append((10, inside[r][c]))
            elif cell.type == CellType.BEES:
                score_terms.append((-5, inside[r][c]))

    if walls is not None and score_terms:
        # Fixed wall count: maximise score.
        model.maximize(sum(coeff * var for coeff, var in score_terms))
    elif walls is None:
        # No wall count specified: minimise perimeter.
        model.minimize(total_walls)

    solver = cp_model.CpSolver()
    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    inside_vals = [
        [bool(solver.value(inside[r][c])) for c in range(ncols)]
        for r in range(nrows)
    ]
    wc = solver.value(total_walls)
    sc = sum(coeff * solver.value(var) for coeff, var in score_terms)

    return Solution(
        inside=inside_vals,
        wall_count=wc,
        score=sc,
        status="optimal" if status == cp_model.OPTIMAL else "feasible",
    )
