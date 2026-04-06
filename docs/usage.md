# enclose-horse-solver usage

A CLI tool that reads a CSV map exported from [enclose.horse](https://enclose.horse) and returns the optimal fence placement using integer programming (CP-SAT).

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Installation

```
git clone <repo>
cd enclose-horse-solver
uv sync
```

## Running

```bash
# Find the minimum-wall enclosure
uv run solver.py map.csv

# Solve for at most N walls
uv run solver.py map.csv --walls 13

# Override the auto-detected puzzle mode
uv run solver.py map.csv --walls 13 --mode lovebirds
```

## CSV format

Export your puzzle from enclose.horse as a CSV. Each cell contains one of:

| Value | Meaning |
|-------|---------|
| *(empty)* | Grass — can be inside or outside |
| `W` | Water — must remain outside the enclosure |
| `H` | Horse — must be inside the enclosure |
| `U` | Unicorn — must be inside the enclosure |
| `P` | Apple — inside the enclosure scores +10 |
| `Z` | Bees — inside the enclosure scores −5 |
| `C` | Cherry — inside the enclosure scores +3 |
| `A`–`Z`* | Portal pair — both ends must be on the same side |

\* excluding W, H, U, P, Z, C (i.e. A, B, D–O, Q–Y)

## Puzzle modes

Modes are auto-detected from the animals present on the map:

| Animals | Auto-detected mode |
|---------|--------------------|
| 1 horse or unicorn | `standard` |
| 2 horses | `lovebirds` |
| 1 horse + 1 unicorn | `horse_unicorn` |

`costly_walls` is never auto-detected; pass `--mode costly_walls` explicitly.

**Lovebirds:** the two horses must be connected within the same enclosure (directly or via a portal).

**Costly Walls:** each wall placed deducts 6 points from your score; the solver maximises the net score.

## Output

The solver prints the grid with fence segments overlaid using Unicode box-drawing characters.  Enclosed cells are marked with `*`.

```
+   +   +───+   +
  .   . │*H*│ .  
+   +   +───+   +
```

## How it works

The puzzle is modelled as a constraint satisfaction problem:

- A binary variable `enclosed[r,c]` represents whether each cell is inside the enclosure.
- **Hard constraints:** horse/unicorn cells must be enclosed; water cells must be outside; portal pairs must be on the same side.
- **Connectivity:** a spanning arborescence rooted at the first animal ensures all enclosed cells form a single connected region (no isolated islands).
- **Wall budget:** if `--walls N` is given, at most N walls may be placed; otherwise the minimum is found.
- **Objective:**
  - Default / fixed budget: maximise score (apples +10, cherries +3, bees −5 per enclosed cell).
  - `costly_walls` mode: maximise score minus 6 × wall count.

The solver uses [Google OR-Tools CP-SAT](https://developers.google.com/optimization/reference/python/sat/python/cp_model) and guarantees an optimal solution.
