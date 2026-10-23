# FantasyAdvisor

A personal portfolio project for NFL fantasy football predictions and data-driven start/sit recommendations. The stack is FastAPI, pandas/scikit-learn/XGBoost, and Next.js/TypeScript/Tailwind, with PostgreSQL and possible Sleeper integration planned.

Tasks 1–3 implement historical weekly data ingestion, leakage-safe player/matchup features, and separately evaluated RB/WR fantasy-point models. Task 4 adds a local FastAPI backend. Task 5 adds the Next.js analytics frontend. Database integration remains future work.

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

## FastAPI backend (Task 4)

Install and launch from the repository root:

```bash
source .venv312/bin/activate
python -m pip install -r backend/requirements-dev.txt
uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8000
```

Open [Swagger UI](http://127.0.0.1:8000/docs) or `/openapi.json`. Run offline tests with `MPLCONFIGDIR=.matplotlib python -m pytest backend/tests -q`. All original pipeline/training commands above still work; Tasks 1–3 are unchanged.

| GET endpoint | Parameters | Result |
| --- | --- | --- |
| `/api/health` | None | Loaded RB/WR model availability, local data availability, status/version |
| `/api/players` | `search` (partial name, case insensitive), `limit=50` | Unique RB/WR players, latest observed team |
| `/api/players/{player_id}` | Player ID | Five recent historical games with season/week/type, opportunity metrics, career snapshot averages, future scheduled opponent if available |
| `/api/projections/{player_id}` | Required `season`, `week` | Pregame full-PPR prediction, matchup features, provenance, missing inputs and limitations |
| `/api/projections` | Required `season`, `week`; optional `position=RB\|WR`, `limit=50`, `offset=0` | Descending projections, eligible players unavailable for projection and reasons, total |
| `/api/compare` | Required `player1_id`, `player2_id`, `season`, `week` | Two projections, signed player1-minus-player2 difference, recommendation, evidence and close-call flag |
| `/api/model/performance` | None | Actual Task 3 metrics, baseline comparisons and chronological periods |
| `/api/predictions/history` | Required `player_id`; `limit=100`, `offset=0` | Saved held-out test predictions, actual points and absolute errors |

Limits must be 1–500, offsets nonnegative, seasons 2023–2100, weeks 1–18. Inference supports regular-season 2025 onward with the current model; earlier seasons overlap its training period. Unknown players/schedules/matchups return 404, unsupported positions/insufficient history/invalid inputs return 422, missing datasets/models return 503. Errors consistently contain `{"error":{"code":"...","message":"..."}}`; unexpected errors return a generic 500 and log details server-side. Health remains reachable when files are absent and reports `degraded`. Missing performance/history exports return `available: false`; a known player with no held-out records returns an empty history.

Example requests:

```bash
curl 'http://127.0.0.1:8000/api/players?search=McCaffrey&limit=5'
curl 'http://127.0.0.1:8000/api/players/00-0033280'
curl 'http://127.0.0.1:8000/api/projections/00-0033280?season=2025&week=10'
curl 'http://127.0.0.1:8000/api/projections?season=2025&week=10&position=RB&limit=10'
curl 'http://127.0.0.1:8000/api/compare?player1_id=00-0033280&player2_id=00-0036322&season=2025&week=10'
curl 'http://127.0.0.1:8000/api/model/performance'
curl 'http://127.0.0.1:8000/api/predictions/history?player_id=00-0033280'
```

Actual local-model response excerpt for McCaffrey, generated during Task 4 verification (historical replay, not a current forecast):

```json
{
  "player_id": "00-0033280",
  "player_name": "C.McCaffrey",
  "position": "RB",
  "team": "SF",
  "season": 2025,
  "week": 10,
  "opponent": "LA",
  "projected_ppr_points": 17.28369140625,
  "model_version": "ppr-v1",
  "prediction_type": "pregame",
  "data_as_of": "2025-11-09T00:00:00Z",
  "last_statistical_game": "2025-11-02",
  "historical_games": 32,
  "missing_features": []
}
```

**Files and configuration.** Defaults use `data/processed/player_weekly_2023_2025.parquet`, `data/raw/schedules_2023_2025.parquet`, trusted `models/ppr-v1/{RB,WR}.joblib` bundles, `reports/ml/training_report.json`, and `reports/ml/test_predictions.csv`. Override paths with `FANTASY_PLAYERS`, `FANTASY_SCHEDULES`, and `FANTASY_MODELS` (model directory). Snapshots/models load once at startup; restart after replacing them. Joblib files must come from a trusted source. Evaluation/history files already exist from Task 3; the original training command regenerates both from the original chronological held-out split if lost.

CORS defaults to `http://localhost:3000`; override the single explicit origin with `FANTASY_CORS_ORIGIN`. `FANTASY_CLOSE_CALL_POINTS` defaults to `2.0` PPR points and must be finite/nonnegative. A higher projection wins even within that threshold, accompanied by a close-call explanation; exact ties have no recommended player. This threshold is a product rule, not calibrated model confidence.

**How it works.** `backend/api/main.py` contains thin routes and application startup, `schemas.py` declares public response models, `data.py` provides local data access, `predictions.py` builds pregame inputs and selects cached position-specific model pipelines, and `comparison.py` implements the pure comparison rule. Keeping storage behind a repository lets a later PostgreSQL implementation preserve the API contracts.

Pregame feature generation discards target-day and later player records before feature calculation. It appends identifier-only placeholders for real scheduled games and calls the unchanged Task 2 shifted feature builder. Placeholders have unknown outcomes; no fictional statistics are supplied. The saved Task 3 schema is checked exactly and its trained pipeline supplies preprocessing/imputation. Features are batched per game date and cached with a bounded cache. Eligibility is rechecked on every request so cached predictions cannot bypass roster freshness. Requests never download data. Tests mutate/delete target and future outcomes and compare generated inputs with the original historical feature pipeline.

**Current data and eligibility.** The backend automatically uses `data/current.json` when a validated refresh has been published, otherwise it uses the original historical files. Refresh explicitly (requires internet), then restart the API:

```bash
python -m backend.scripts.refresh_current_data --season 2026
uvicorn backend.api.main:app --reload
```

The refresh downloads nflverse player statistics, schedules, and weekly rosters, reuses Task 1 scoring/cleaning, validates identifiers and schedule joins, and publishes a new immutable folder with an atomic manifest switch. Failed downloads/validation leave the working snapshot intact. Original Task 1–3 datasets and model artifacts are preserved. Repeat the command to update data; requests never trigger downloads. Arrange a local daily scheduler if desired; scheduling is not installed automatically. Restart even with `--reload`, since data-file changes do not reliably reload Uvicorn.

A verified download on October 23, 2026 provided a complete 2026 regular-season schedule, statistics through October 22, and weekly rosters through week 7. Week 7 upcoming-game projections now work locally. Week 8 returns `422 roster_unavailable` until the source publishes that weekly roster and you refresh. No matchup or roster is invented. `/api/health` exposes the published snapshot's observation timestamp, file paths, latest statistical game, counts and sources.

For seasons with published roster coverage, eligibility uses the exact requested week's roster, its source status code `ACT`, and at least one earlier career appearance. Team/position come from that roster, allowing veterans to use prior-season history and respecting observed team changes. Other source statuses receive `roster_not_eligible`; roster-only rookies are searchable and have empty historical details but receive `insufficient_data` for projection. Weekly results include those unavailable reasons. Membership/status is a source roster classification, not a guarantee of game-day availability; injury descriptions are not inferred.

Every roster download is stamped with its actual local observation time. Only snapshots observed before the game's conservative midnight UTC cutoff can establish eligibility. Previous observations are retained across refreshes. A snapshot must match the week and be no more than seven days old; later weeks are never inferred from an earlier roster. Historical weekly labels alone cannot prove pregame availability, so newly downloaded old rosters cannot be backdated. For historical 2025-and-earlier replay without published roster coverage, the prior same-season-appearance rule remains. Newer seasons require a published roster snapshot and never silently fall back to that heuristic.

`feature_cutoff` is the scheduled game-date boundary; all target-day and later statistics are excluded before feature generation. `data_as_of` is capped by the snapshot observation timestamp when one exists, so upcoming projections never claim future data availability. `snapshot_observed_at` and `roster_observed_at` expose local download provenance; `last_statistical_game` is the latest included player appearance. Historical snapshots may contain later source corrections, so date filtering alone does not establish exact historical publication time. Same-day observations are conservatively excluded because Task 2 uses dates rather than kickoff timestamps. Responses also identify the eligibility source and raw roster status code.

The current ppr-v1 model is unchanged: it trained on 2023–2024 and was selected using 2025 weeks 1–9. No calibrated intervals or confidence percentages exist. Missing features and stale history are exposed; preprocessing uses the saved training pipeline. Only saved 2025 weeks 10–18 test records are reported as held-out evaluation. Refreshing input data does not establish model accuracy in 2026: newer held-out evaluation and model retraining remain needed before treating current-season estimates as validated recommendations.

See [current snapshot design and verification](docs/current_data.md) for the publication contract and tests.

## Next.js frontend (Task 5)

A dark, responsive analytics workspace now connects to the FastAPI backend using Next.js App Router, React, TypeScript, Tailwind CSS, Recharts and Lucide React.

Start the backend from the repository root:

```bash
source .venv312/bin/activate
uvicorn backend.api.main:app --host localhost --port 8000
```

Start the frontend in a second terminal (Node 22.16+):

```bash
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000. `NEXT_PUBLIC_API_BASE_URL` defaults to `http://localhost:8000`; the explicit backend CORS origin defaults to `http://localhost:3000`. Configure both when using different hosts. Production API addresses must be reachable from the user's browser; no production URL is hardcoded.

Available pages: dashboard `/`, weekly projections `/projections`, player search `/players`, player research `/players/[playerId]`, start/sit `/compare`, and evaluation `/performance`. Selection persists across pages and defaults to actual roster coverage exposed in health metadata. Historical player research and saved evaluation work independently of trained model availability. Projection, ranking and comparison features require the relevant loaded models and valid schedule/roster/history. Missing data produces explicit loading, empty, error and retry states.

Frontend checks, from `frontend/`: `npm run typecheck`, `npm run lint`, `npm test`, and `npm run build`. Use `npm start` for the production server. `npm run test:e2e` runs optional desktop/mobile Chrome checks against both live services. See [frontend setup, architecture, testing and limitations](frontend/README.md) for details. Backend changes are limited to reporting actual roster-week coverage in `/api/health`; model training and API prediction logic are unchanged by Task 5.

### Backend performance on small hosting instances

Weekly requests batch model inference once per position and reuse player/roster lookups within the request. Rolling features use vectorized grouped operations with the same shift-before-rolling semantics as Task 2. Concurrent requests share a lock around cold feature generation so they do not rebuild the same date simultaneously. Eligibility is still checked for each request; no long-lived projection cache bypasses roster freshness. Render/Uvicorn logs include weekly projection counts and elapsed seconds after a successful calculation.

A local before/after comparison on the real 2026 week 7 snapshot measured 6.63 seconds versus 1.71 seconds for a cold weekly request, with all 225 projection values matching within 0.000001 PPR and all unavailable reasons matching. Warm requests measured about 0.72 seconds locally. Hosting timings depend on available CPU and memory; these are not guarantees for Render's free tier. The 78-test backend suite includes grouped-window equivalence, batched-vs-individual inference, concurrent feature caching, and the original leakage tests. Redeploy the backend after pushing the performance changes; model/data artifacts do not need to be regenerated.

## Deploy both services on Vercel

The repository now includes a Vercel-ready inference backend: root `app.py`, `.python-version`, `requirements.txt`, `.vercelignore`, and `vercel.json`. Keep the existing Next.js project rooted at `frontend`; create a second Vercel project rooted at the repository root using the FastAPI preset. Root requirements omit training/download tools and use the official same-version CPU-only XGBoost package on Linux x86_64 to avoid CUDA/NCCL dependencies. Original development/training requirements remain unchanged.

The backend build runs `python -m backend.scripts.check_deployment` and fails if the published snapshot, models or evaluation artifacts are missing. All artifacts must be committed before deployment. After the new API passes health and projection checks, point the existing frontend's `NEXT_PUBLIC_API_BASE_URL` at its assigned Vercel domain and redeploy the frontend. Set backend `FANTASY_CORS_ORIGIN` to the exact frontend production origin. Keep Render running until the migration is verified.

See the [complete Vercel deployment steps](docs/vercel_deployment.md), including Git commands, dashboard settings, troubleshooting and verification limits. The estimated Linux inference dependency size is 444.6 MB uncompressed; the actual Vercel build must confirm that runtime overhead plus artifacts fit the standard bundle limit. All 84 offline backend tests pass locally; live Vercel performance and the Linux CPU model runtime still require deployment verification.
