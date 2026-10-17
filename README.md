# FantasyAdvisor

A personal portfolio project for NFL fantasy football predictions and data-driven start/sit recommendations. The eventual stack is FastAPI, pandas/scikit-learn/XGBoost, PostgreSQL, and Next.js/TypeScript/Tailwind, with possible Sleeper integration.

Task 1 implements only a historical weekly data pipeline. No API routes, model, database, or frontend application have been built.

## Setup

Use Python 3.12 (the pinned pandas version requires Python 3.11+):

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements-dev.txt
python -m backend.scripts.build_player_stats
python -m pytest backend/tests -q
```

Run commands from the repository root. In the development environment used for this task, the compatible environment is `.venv312`: use `source .venv312/bin/activate`. The system Python 3.9 is too old. Dependencies are limited to the data loader, dataframe/Parquet tools, and pytest; FastAPI and ML packages will be added when needed.

The pipeline needs internet access to GitHub. Download errors are printed and cause a nonzero exit; no substitute data is generated. Unit test fixtures are synthetic and never used as downloaded data.

Optional output paths:

```bash
python -m backend.scripts.build_player_stats --output data/processed/players.parquet --inspection data/processed/schema_report.json
```

## Source and output

[nflreadpy](https://nflreadpy.nflverse.com/api/load_functions/) loads [nflverse player statistics](https://github.com/nflverse/nflverse-data/releases/tag/stats_player) with `load_player_stats([2023, 2024, 2025], summary_level="week")`. It returns a Polars dataframe; the pipeline records its actual schema before converting to pandas. The initial real download was inspected before transformation code was written.

- `data/processed/player_weekly_2023_2025.parquet`: cleaned weekly QB/RB/WR/TE records, including regular season and postseason. `season_type` distinguishes them.
- `data/processed/schema_report.json`: all source column names/types, record counts, missing values, and source score comparison. Regenerated on each successful run; a source-schema-only report is written before transformation.
- [docs/data_pipeline.md](docs/data_pipeline.md): scoring policy, complete observed columns, run results, and limitations.

Generated datasets and local environments are ignored by Git. Read the result with `pd.read_parquet("data/processed/player_weekly_2023_2025.parquet")`.

## File guide

| File | Purpose |
| --- | --- |
| `.gitignore` | Excludes environments, caches, credentials, frontend build files, and generated data. |
| `backend/requirements.txt` | Pins the three direct runtime dependencies. |
| `backend/requirements-dev.txt` | Adds pytest to runtime dependencies. |
| `backend/__init__.py`, `backend/scripts/__init__.py` | Declare importable packages for module execution and tests. |
| `backend/scripts/build_player_stats.py` | Downloads and inspects the source; filters positions, calculates PPR, validates identifiers/uniqueness, and writes Parquet and a report. |
| `backend/tests/test_player_stats.py` | Tests scoring, unknown inputs, position filtering, identifiers, duplicates, and generated data when present. |
| `frontend/README.md` | Reserves and explains the future frontend directory. |
| `data/.gitkeep` | Keeps the empty data directory tracked without datasets. |
| `docs/data_pipeline.md` | Records the inspected schema, scoring choices, results, and limitations. |
| `README.md` | Project goal, setup, commands, and file guide. |

Next small task: create a leakage-safe feature dataset using each player's prior games, starting with lagged PPR and rolling usage averages, with tests that exclude the current and future weeks.
