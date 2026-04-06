#!/usr/bin/env python3
"""enclose-horse-solver: optimally solve enclose.horse puzzles.

Usage:
    uv run solver.py map.csv --walls 13
    uv run solver.py map.csv
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

import typer

from src.model import build_and_solve
from src.output import print_result
from src.parser import Mode, parse_csv

app = typer.Typer(
    help="Solve enclose.horse puzzles optimally using CP-SAT integer programming.",
    add_completion=False,
)


class ModeArg(str, Enum):
    STANDARD = "standard"
    LOVEBIRDS = "lovebirds"
    HORSE_UNICORN = "horse_unicorn"


@app.command()
def main(
    csv_file: Path = typer.Argument(..., help="CSV map exported from enclose.horse"),
    walls: Optional[int] = typer.Option(
        None, "--walls", "-w", min=1,
        help="Exact number of fence segments to use.  Omit to find the minimum.",
    ),
    mode: Optional[ModeArg] = typer.Option(
        None, "--mode", "-m",
        help="Override auto-detected puzzle mode.",
    ),
) -> None:
    if not csv_file.exists():
        typer.echo(f"Error: file not found: {csv_file}", err=True)
        raise typer.Exit(1)

    grid = parse_csv(csv_file)
    detected = grid.detect_mode()
    resolved_mode = Mode[mode.value.upper()] if mode else detected

    typer.echo(
        f"Grid: {grid.rows}×{grid.cols}  |  "
        f"Animals: {len(grid.animals)}  |  "
        f"Mode: {resolved_mode.value}"
    )

    if walls is not None:
        typer.echo(f"Solving for exactly {walls} walls …")
    else:
        typer.echo("Solving for minimum walls …")

    solution = build_and_solve(grid, walls, resolved_mode)

    if solution is None:
        typer.echo(
            "No solution found. "
            "Try a different --walls value or check the map file.",
            err=True,
        )
        raise typer.Exit(2)

    print_result(grid, solution)


if __name__ == "__main__":
    app()
