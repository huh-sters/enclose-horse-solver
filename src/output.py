"""Terminal renderer: draws the puzzle grid with walls and enclosed region."""
from __future__ import annotations

from rich.console import Console
from rich.text import Text

from .model import Solution
from .parser import CellType, Grid

# Rich style per cell type (for cells NOT in the enclosed region)
_OUTSIDE_STYLE: dict[CellType, str] = {
    CellType.GRASS:   "dim white",
    CellType.WATER:   "bold blue",
    CellType.HORSE:   "bold red",
    CellType.UNICORN: "bold magenta",
    CellType.APPLE:   "bold yellow",
    CellType.BEES:    "bold red",
    CellType.CHERRY:  "bold red",
    CellType.PORTAL:  "bold yellow",
}

# Rich style per cell type when ENCLOSED (green background)
_ENCLOSED_STYLE: dict[CellType, str] = {
    CellType.GRASS:   "white on dark_green",
    CellType.WATER:   "bold blue",           # water is never enclosed
    CellType.HORSE:   "bold red on dark_green",
    CellType.UNICORN: "bold magenta on dark_green",
    CellType.APPLE:   "bold yellow on dark_green",
    CellType.BEES:    "bold red on dark_green",
    CellType.CHERRY:  "bold red on dark_green",
    CellType.PORTAL:  "bold yellow on dark_green",
}

_WALL_STYLE = "bold white on dark_blue"


def _cell_label(cell_type: CellType, portal_id: str | None) -> str:
    if cell_type == CellType.PORTAL:
        return portal_id or "?"
    return {
        CellType.GRASS:   "~",
        CellType.WATER:   "W",
        CellType.HORSE:   "H",
        CellType.UNICORN: "U",
        CellType.APPLE:   "P",
        CellType.BEES:    "Z",
        CellType.CHERRY:  "C",
    }.get(cell_type, "?")


def render(grid: Grid, solution: Solution) -> Text:
    """Return a rich Text object rendering the grid."""
    nrows, ncols = grid.rows, grid.cols
    text = Text()

    # Column header
    text.append("   ")
    for c in range(ncols):
        text.append(f"{c:^3}", style="dim cyan")
    text.append("\n")

    for r in range(nrows):
        text.append(f"{r:2} ", style="dim cyan")
        for c in range(ncols):
            cell = grid.cell_at(r, c)
            is_wall = solution.wall[r][c]
            is_enc = solution.enclosed[r][c]

            if is_wall:
                text.append(" # ", style=_WALL_STYLE)
            elif is_enc:
                label = _cell_label(cell.type, cell.portal_id)
                text.append(f" {label} ", style=_ENCLOSED_STYLE[cell.type])
            else:
                label = _cell_label(cell.type, cell.portal_id)
                text.append(f" {label} ", style=_OUTSIDE_STYLE[cell.type])
        text.append("\n")

    return text


def print_result(grid: Grid, solution: Solution) -> None:
    """Print the solution summary and rendered grid to the terminal."""
    console = Console()
    console.print()
    console.print(f"[bold green]Status:[/]         {solution.status}")
    console.print(f"[bold green]Walls used:[/]     {solution.wall_count}")
    console.print(f"[bold green]Enclosed cells:[/] {solution.enclosed_count}")
    score_colour = "green" if solution.score >= 0 else "red"
    console.print(f"[bold {score_colour}]Score:[/]          {solution.score:+d}")
    console.print()
    console.print(render(grid, solution))
