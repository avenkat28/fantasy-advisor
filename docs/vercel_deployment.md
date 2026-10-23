# One Vercel project, one domain

This configuration replaces the earlier two-project setup. It retains the existing `frontend/` and `backend/` code; nothing is merged into one source file. Vercel Services builds Next.js and FastAPI independently inside one project, with a shared deployment URL.

| Request | Service | Purpose |
| --- | --- | --- |
| `/`, `/players`, `/projections`, `/compare`, `/performance`, Next.js assets | `frontend` (root `frontend`) | Existing UI |
| `/api/...` | `backend` (root `.`; entrypoint `app:app`) | Existing inference API |
| `/docs`, `/docs/...`, `/openapi.json`, `/redoc` | `backend` | API documentation |

Root `vercel.json` declares `services` and ordered public rewrites. Backend build/function settings are scoped to that service; the frontend has its own npm install/build commands. Rewrites preserve the API path, so `/api/health` reaches FastAPI as `/api/health`.

## 1. Push the changes

From the repository root:

```bash
git add vercel.json .gitignore .vercelignore README.md \
  docs/vercel_deployment.md backend/tests/test_deployment.py frontend
git commit -m "Configure single-project Vercel frontend and API"
git push origin HEAD
```

The previously prepared root `app.py`, `.python-version`, `requirements.txt` and backend preflight script remain necessary. If they have not yet been committed, also stage them:

```bash
git add app.py .python-version requirements.txt backend/scripts/check_deployment.py
```

The published snapshot, RB/WR model bundles and evaluation artifacts must be tracked. They were previously force-added for Render; check with:

```bash
git ls-files data/current.json data/snapshots models/ppr-v1 reports/ml
```

The API build runs `python -m backend.scripts.check_deployment` and fails if required artifacts are missing. No training or data downloading is performed during requests.

## 2. Configure ONE Vercel project

The safest migration is a new project with a unique name such as `fantasy-advisor-unified`, while the existing UI stays online. Import the same `avenkat28/fantasy-advisor` repository. Alternatively, update the existing frontend project's settings if preserving that project/domain is preferable; its next successful deployment will replace the UI-only deployment.

Settings for the unified project:

- **Root Directory:** repository root, `./`. Never `frontend` or `backend` for this setup.
- **Application/Framework Preset:** let Vercel detect **Services** from `vercel.json`. Do not force the old FastAPI-only or Next.js-only preset.
- **Install Command, Build Command, Output Directory:** clear old dashboard overrides. The individual service settings in `vercel.json` own these commands.
- **Start Command:** none. Vercel manages both runtimes.
- **Node.js:** use 22.x or newer compatible with the frontend's Node requirement.
- **Python:** `.python-version` selects 3.12 for the backend.

**Remove `NEXT_PUBLIC_API_BASE_URL` from this project's Production and Preview environments before building.** An inherited Render/second-project/localhost value would direct browser requests outside the unified deployment. With no override, the frontend calls relative `/api/...` URLs and automatically uses the current production or preview domain.

`FANTASY_CORS_ORIGIN` is not required for same-origin browser calls. It can remain configured for an intentional separate local client, but it is not used to connect the two services in the unified setup. Do not add wildcard CORS or protection-bypass secrets. No authentication is added by this migration.

Remove any stale `FANTASY_PLAYERS`, `FANTASY_SCHEDULES` or `FANTASY_MODELS` path overrides from Render. Do not set `FANTASY_LOCAL_API_URL` on Vercel; it is only for a local proxy/test build.

Deploy. If Vercel reports that a project name already exists, open that existing project or choose a unique name; do not delete a working deployment to resolve a naming conflict. Services is currently a Vercel beta available on all plans. If your dashboard does not recognize `services`, inspect the actual error and use current Vercel tooling rather than switching back to the old `experimentalServices` syntax.

## 3. Verify the combined deployment

Use its assigned production domain:

```text
https://YOUR-PROJECT.vercel.app/
https://YOUR-PROJECT.vercel.app/api/health
https://YOUR-PROJECT.vercel.app/docs
https://YOUR-PROJECT.vercel.app/openapi.json
https://YOUR-PROJECT.vercel.app/api/projections?season=2026&week=7&limit=1
```

The root must now display the UI. Health must return `status: "ok"`, both models available and the expected data snapshot. Choose a week with eligible upcoming games at verification time; missing rosters or stale data remain explicit API errors. Check the browser Network panel: API requests should use the **same hostname** as the UI, with no calls to Render, a separate backend project or localhost.

Test projections, search, player details, comparison and evaluation on desktop and mobile. Vercel Runtime Logs show backend timing; Build Logs identify per-service build failures. Same-origin preview requests do not require a separate CORS entry for every preview URL. Deployment Protection still applies to the whole deployment and is independent of CORS.

After the combined deployment works, move the existing custom/production domain to this project if necessary. Keep the old frontend/backend/Render projects until that verification is complete. Deleting old services is a separate action; these code changes delete no hosted projects.

## Local development and checks

The normal two-terminal local workflow still works:

```bash
# Repository root
source .venv312/bin/activate
uvicorn backend.api.main:app --host localhost --port 8000

# Another terminal
cd frontend
npm ci
npm run dev
```

Open http://localhost:3000. The browser calls that origin's `/api` URLs; Next.js proxies local development API requests to localhost:8000. If an old `frontend/.env.local` contains `NEXT_PUBLIC_API_BASE_URL`, remove that line to exercise the same-origin proxy. The variable remains an explicit optional override for an intentionally split deployment.

```bash
MPLCONFIGDIR=.matplotlib python -m pytest backend/tests -q
cd frontend
npm run typecheck
npm run lint
npm test
npm run build
```

A normal production Next.js build has no localhost rewrite. `FANTASY_LOCAL_API_URL` can explicitly enable a backend proxy for a local integration-test build; do not set it in a hosted environment.

Vercel's own combined local runner is also supported with current CLI tooling:

```bash
npx vercel@latest dev --local
```

It detects both services, routes docs/API/UI through one URL, and requires no account login in local mode. The CLI prefers a conventional `.venv`/`venv` in the service root: it may select an old Python environment instead of `.venv312`. Use a compatible Python 3.12 environment for that runner. Do not overwrite an existing environment blindly. The combined configuration was exercised in an isolated checkout with its `.venv` pointing at the compatible environment.

Run the optional browser suite against a combined local runner or a local test server:

```bash
cd frontend
npm run test:e2e
```

Set `FRONTEND_TEST_URL` to another combined URL. `API_TEST_BASE_URL` is available only if the Playwright setup requests need another base URL. Browser assertions verify that UI API requests actually remain same-origin. Chrome must be installed. The regular Vitest/backend tests are offline; browser checks require running services and real artifacts.

## Runtime packaging and limitations

Root requirements remain inference-only. On Linux x86_64, official `xgboost-cpu==3.4.1` retains the same CPU inference API and model version while omitting CUDA/NCCL. Original development/training requirements are unchanged. Runtime function exclusions remove frontend source from the Python bundle, raw/processed data outside the published snapshot, plot files, local environments and caches. They preserve published snapshots, the RB/WR bundles, the evaluation report and test prediction CSV. Exclusion patterns remain under Vercel's 256-character validation limit.

The downloaded Linux CPython 3.12 dependencies total about **444.6 MB uncompressed**, before small source/artifacts and Vercel runtime overhead. The cloud build must still confirm the final bundle fits the standard 500 MB limit. The actual Linux CPU inference runtime and live Vercel latency require cloud verification; the local runner uses the existing CPU-only macOS XGBoost runtime. No model retraining, feature simplification, confidence fabrication or freshness-rule relaxation is part of this migration.

Services is beta and subject to Vercel Hobby compute/usage limits and cold starts. One project does not mean unlimited free hosting or eliminate the Python computation. The browser still has a 30-second request timeout. Memory caches belong to warm function instances and are not durable storage. Continue refreshing snapshots locally and redeploying them, or add verified external storage later. Do not write source snapshots during an API request.

References: [Services overview](https://vercel.com/docs/services), [routing](https://vercel.com/docs/services/routing), [service configuration](https://vercel.com/docs/services/config-reference), [function limits](https://vercel.com/docs/functions/limitations), and [XGBoost CPU installation](https://xgboost.readthedocs.io/en/stable/install.html).

## Verification for this change

- Backend: 95 tests passed, including service routing and configuration-length regressions.
- Frontend: 22 unit/component tests passed; TypeScript and ESLint passed.
- Production Next.js build passed with a same-origin API base and no local proxy enabled.
- Vercel CLI 65.2.0 detected and started both services in local mode.
- Six real Chrome desktop/mobile checks passed through that runner: application workflows, unavailable-week handling, shared-origin API calls, Swagger/OpenAPI, and API 404 routing.
- Artifact preflight passed with the existing real models and snapshot.

These are local checks. No Vercel project was created, changed, deleted or deployed by this task. Cloud bundle size, Linux CPU runtime and live latency still need verification after the Git push/deployment.
