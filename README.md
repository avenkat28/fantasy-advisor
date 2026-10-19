# FantasyAdvisor

A personal portfolio project for NFL fantasy football predictions and data-driven start/sit recommendations. The eventual stack is FastAPI, pandas/scikit-learn/XGBoost, PostgreSQL, and Next.js/TypeScript/Tailwind, with possible Sleeper integration.

Tasks 1–3 implement historical weekly data ingestion, leakage-safe player/matchup features, and separately evaluated RB/WR fantasy-point models. API, database, and frontend development remain future work.

## Setup

Use Python 3.12 (the pinned pandas version requires Python 3.11+):

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements-dev.txt
python -m backend.scripts.build_player_stats
python -m backend.scripts.build_features
python -m pytest backend/tests -q
```

Run commands from the repository root. In the development environment used for this task, the compatible environment is `.venv312`: use `source .venv312/bin/activate`. The system Python 3.9 is too old. Dependencies include the data loader, dataframe/Parquet tools, scikit-learn, XGBoost, matplotlib, joblib and pytest. macOS XGBoost requires the OpenMP runtime (`brew install libomp`).

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
| `backend/requirements.txt` | Pins direct runtime dependencies. |
| `backend/requirements-dev.txt` | Adds pytest to runtime dependencies. |
| `backend/__init__.py`, `backend/scripts/__init__.py` | Declare importable packages for module execution and tests. |
| `backend/scripts/build_player_stats.py` | Downloads and inspects the source; filters positions, calculates PPR, validates identifiers/uniqueness, and writes Parquet and a report. |
| `backend/tests/test_player_stats.py` | Tests scoring, unknown inputs, position filtering, identifiers, duplicates, and generated data when present. |
| `frontend/README.md` | Reserves and explains the future frontend directory. |
| `data/.gitkeep` | Keeps the empty data directory tracked without datasets. |
| `docs/data_pipeline.md` | Records the inspected schema, scoring choices, results, and limitations. |
| `README.md` | Project goal, setup, commands, and file guide. |

## Feature engineering (Task 2)

`backend/scripts/build_features.py` reads the cleaned dataset and a cached nflverse schedule, then writes `data/processed/player_features_2023_2025.parquet` and `feature_report.json`. The observed output has 18,533 rows and 45 columns. It includes lagged player production/usage, consistency, position-specific opponent PPR allowed, opponent yardage, and game context. Current-game statistics are excluded from inputs; actual PPR is stored only as `target_fantasy_points_ppr`.

See [docs/feature_engineering.md](docs/feature_engineering.md) for feature definitions, missing-history rules, sources, commands, run results, and training limitations. `backend/tests/test_features.py` verifies the calculations and leakage protection with synthetic games. The feature report explicitly lists input, metadata, and target columns. Historical snap percentage remains unavailable.

## Machine learning (Task 3)

See [docs/machine_learning.md](docs/machine_learning.md) for the exact 29-feature pregame contract, chronological evaluation, measured results, artifact locations, diagnostics and limitations.

```bash
source .venv312/bin/activate
python -m pip install -r backend/requirements-dev.txt
MPLCONFIGDIR=.matplotlib python -m backend.scripts.train_models
MPLCONFIGDIR=.matplotlib python -m backend.ml.evaluate
python -m backend.ml.predict --model models/ppr-v1/RB.joblib --features reports/ml/RB_example_features.json
MPLCONFIGDIR=.matplotlib python -m pytest backend/tests -q
```

Implementation: `backend/ml/{schema,predict,evaluate}.py`, `backend/scripts/train_models.py`, and `backend/tests/test_models.py`. Trained pipelines live in `models/ppr-v1/`; metrics, per-game predictions and charts live in `reports/ml/`. Generated artifacts are ignored by Git.
