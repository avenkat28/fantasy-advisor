# FantasyAdvisor frontend

Next.js App Router, React, strict TypeScript, Tailwind CSS, Recharts, and Lucide React. Requires Node 22.16 or newer (Node 26 was used for verification). Run commands in this directory unless noted otherwise.

## Local setup

```bash
npm ci
cp .env.example .env.local
npm run dev
```

Open http://localhost:3000. The `.env.example` documents an optional override. For the unified deployment, leave it unset:

```dotenv
# NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

The default is same-origin `/api` requests. Local Next.js development proxies these requests to FastAPI at localhost:8000; Vercel Services routes them to Python in production. Remove an old `NEXT_PUBLIC_API_BASE_URL` line from `.env.local` and remove the variable from the unified Vercel project. An explicit browser-visible URL remains optional for an intentionally separate backend, which requires matching CORS. Never place credentials in public variables. Restart/rebuild after changing them.

In another terminal, from the **repository root**:

```bash
source .venv312/bin/activate
python -m pip install -r backend/requirements-dev.txt
uvicorn backend.api.main:app --host localhost --port 8000
```

The browser calls http://localhost:3000/api through a development proxy, so local API calls are same-origin. FastAPI also keeps its explicit local CORS setting for direct split-client development. API docs are at http://localhost:8000/docs. In the unified Vercel deployment, `/docs` and `/openapi.json` share the UI domain.

## Pages

| Route | Purpose | Model artifacts required? |
| --- | --- | --- |
| `/` | Weekly top RB/WR projections, actual evaluation summary, matchup/research shortcuts | Rankings require models; evaluation uses saved report |
| `/projections` | RB/WR filters, name search, ascending/descending PPR sort, 25-row pages and unavailable-player reasons | Yes |
| `/players` | Debounced partial-name search, keyboard-accessible result links | No; local player/roster data required |
| `/players/[playerId]` | Historical game log, observed averages/usage, chart, selected-week projection, matchup metadata, saved held-out accuracy | Historical research/history work independently; projection needs model |
| `/compare` | Search/select two players, selected-week backend recommendation and actual explanation | Both relevant models required |
| `/performance` | Saved MAE/RMSE/R²/bias, baseline chart/table, chronological evaluation periods | Saved evaluation report only |

Season/week selection is shared across routes and persisted locally. On first visit, `/api/health` supplies the snapshot season and actual `roster_weeks` coverage; the latest covered week is selected. Without coverage metadata, week 1 is an explicit fallback, not a claim of current NFL week. Every regular-season week remains selectable. Missing data is shown as an error with a retry option; no sample NFL data is substituted.

The API client integrates all nine backend endpoints. `src/lib/types.ts` mirrors the Pydantic response schemas. `api.ts` owns URL configuration, encoded parameters, 30-second timeouts, abort signals, and structured error parsing. `use-resource.ts` cancels obsolete loads and prevents stale responses from being shown after selection changes. Components independently load player history and projections so missing models do not break research pages.

`src/components/shell.tsx` supplies shared desktop/mobile navigation. `season-provider.tsx` owns selected season/week and startup health metadata. Small UI components handle panels, loading/errors, null-safe numbers and badges. `projection-table.tsx`, `player-search.tsx`, and `charts.tsx` are shared across pages. The dynamic route delegates to `player-profile.tsx`. All charts have corresponding value tables; responsive tables scroll horizontally on narrow screens. Native buttons, selects, result links, visible focus states, reduced-motion styles and a skip link support keyboard access.

## Validation

```bash
npm run typecheck
npm run lint
npm test
npm run build
npm start
```

The lockfile pins the resolved dependency tree. Vitest/Testing Library tests are offline and contain the only synthetic player data. Coverage includes dashboard rendering, navigation, selected-week persistence, player search/retry, null/empty/error handling, projection sorting/search, excluded players, backend comparison decisions, historical research without a model, actual metrics rendering, and typed HTTP error handling.

The standalone build and dev commands use Next.js's supported Webpack mode because Turbopack worker socket creation failed in the development sandbox. Vercel's own local Services runner may start its framework dev integration independently. No runtime functionality depends on Turbopack. Run `npm start` after a successful build for a production server.

Optional live browser checks require a combined Services runner (see the deployment guide), real model/data artifacts, and an installed Google Chrome:

```bash
npm run test:e2e
```

Playwright uses desktop Chrome and a mobile viewport, checks real backend integration across pages, and verifies an unpublished week produces an error. It discovers players/week from the loaded snapshot instead of fixed player fixtures. Set `FRONTEND_TEST_URL` for a different combined URL; Playwright setup requests use that same URL by default. Browser checks assert that API requests stay on the UI origin. Install Chrome or change the Playwright channel to a locally available Chromium installation on another machine. Browser tests are separate from offline unit tests.

## Data limitations

The current snapshot supports upcoming 2026 week 7 games. Week 8 roster coverage was unavailable during verification. Refresh data from the repository root with `python -m backend.scripts.refresh_current_data --season 2026`, then restart FastAPI. Source freshness/eligibility errors are shown rather than converted into zero projections. Weekly search/sort operate on up to 500 loaded API rows, with a notice if more results exist. The weekly unavailable list identifies players by the IDs supplied by the backend.

Profile recent averages describe up to five latest recorded appearances, not necessarily the pregame history for the selected week. They are labeled separately from projections and can include postseason games. Missing scores render `—`; no values are invented. Historical accuracy comes exclusively from saved held-out predictions and is empty for players outside the original test split.

The frontend does not add injury reporting, verified game-day availability, calibrated confidence, automatic data refresh, authentication, payments, betting or roster synchronization. Current ppr-v1 accuracy is historical, not 2026 validation. Confirm current-source coverage, implement a verified injury/availability feed, and evaluate/retrain on newer held-out games before presenting current-season estimates as validated recommendations. Do not set `FANTASY_LOCAL_API_URL` in Vercel; it is only an explicit local integration-test proxy setting. See [single-project deployment](../docs/vercel_deployment.md) for the current hosting setup.
