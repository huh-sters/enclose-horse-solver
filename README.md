# enclose-horse-solver

A CLI tool that reads a CSV map exported from [enclose.horse](https://enclose.horse) and finds the optimal fence placement using integer programming (CP-SAT).

## Quick start

```bash
git clone git@github.com:huh-sters/enclose-horse-solver.git
cd enclose-horse-solver
uv sync

# Find the minimum-wall enclosure
uv run solver.py map.csv

# Solve within a wall budget
uv run solver.py map.csv --walls 13

# Override the auto-detected puzzle mode
uv run solver.py map.csv --walls 13 --mode lovebirds
uv run solver.py map.csv --mode costly_walls
```

## Documentation

Full usage reference, CSV format, puzzle modes, and how it works:
**[docs/usage.md](docs/usage.md)**

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
