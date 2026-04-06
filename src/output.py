"""Terminal renderer: draws the puzzle grid with fence segments overlaid."""
from __future__ import annotations

from rich.console import Console

from .model import Solution
from .parser import CellType, Grid

# Cell display characters
_CELL_CHAR: dict[CellType, str] = {
    CellType.GRASS: ".",
    CellType.WATER: "W",
    CellType.HORSE: "H",
    CellType.UNICORN: "U",
    CellType.APPLE: "P",
    CellType.BEES: "Z",
    CellType.PORTAL: "?",  # overridden below using portal_id
}

_H_WALL = "─"   # horizontal fence segment
_V_WALL = "│"   # vertical fence segment
_CORNER = "+"


def _cell_char(cell_type: CellType, portal_id: str | None) -> str:
    if cell_type == CellType.PORTAL:
        return portal_id or "?"
    return _CELL_CHAR.get(cell_type, "?")


def render(grid: Grid, solution: Solution) -> str:  # pylint: disable=too-many-locals
    """Return a Unicode string showing the grid with fence segments."""
    nrows, ncols = grid.rows, grid.cols
    inside = solution.inside
    lines: list[str] = []

    for r in range(nrows):
        # ── Horizontal edge row (top boundary of row r) ──────────────────
        h_line = ""
        for c in range(ncols):
            upper_in = inside[r - 1][c] if r > 0 else False
            this_in = inside[r][c]
            h_line += _CORNER
            h_line += (_H_WALL * 3) if (this_in != upper_in) else "   "
        h_line += _CORNER
        lines.append(h_line)

        # ── Content row ──────────────────────────────────────────────────
        c_line = ""
        for c in range(ncols):
            left_in = inside[r][c - 1] if c > 0 else False
            this_in = inside[r][c]
            c_line += _V_WALL if (this_in != left_in) else " "
            cell = grid.cell_at(r, c)
            ch = _cell_char(cell.type, cell.portal_id)
            marker = "*" if this_in else " "
            c_line += f"{marker}{ch}{marker}"
        right_in = inside[r][ncols - 1]
        c_line += _V_WALL if right_in else " "
        lines.append(c_line)

    # ── Bottom perimeter edge row ─────────────────────────────────────────
    h_line = ""
    for c in range(ncols):
        this_in = inside[nrows - 1][c]
        h_line += _CORNER
        h_line += (_H_WALL * 3) if this_in else "   "
    h_line += _CORNER
    lines.append(h_line)

    return "\n".join(lines)


def print_result(grid: Grid, solution: Solution) -> None:
    """Print the solution summary and rendered grid to the terminal."""
    console = Console()
    console.print(f"\n[bold green]Status:[/]     {solution.status}")
    console.print(f"[bold green]Walls used:[/] {solution.wall_count}")
    if solution.score:
        colour = "green" if solution.score >= 0 else "red"
        console.print(f"[bold {colour}]Score:[/]      {solution.score:+d}")
    console.print()
    console.print(render(grid, solution))
    console.print()
