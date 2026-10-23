# Deploy entirely on Vercel

Use two Vercel projects connected to the same GitHub repository:

| Project | Root Directory | Framework | Purpose |
| --- | --- | --- | --- |
| Existing `fantasy-advisor` frontend | `frontend` | Next.js | Existing UI |
| New `fantasy-advisor-api` backend | Repository root (`./`) | FastAPI | Existing API and model inference |

This moves both services to Vercel without rewriting the API. It does not combine them into one Vercel project. Vercel's Services feature is another possible architecture; this deployment uses the simpler separate-project setup.

## 1. Push the deployment files

From the repository root:

```bash
git add app.py requirements.txt .python-version .vercelignore vercel.json \
  backend/scripts/check_deployment.py backend/tests/test_deployment.py \
  docs/vercel_deployment.md README.md
git commit -m "Prepare inference backend for Vercel"
git push origin HEAD
```

The published snapshot, two model bundles and evaluation report/test predictions must also be tracked. They were previously force-added for Render. Verify before deploying:

```bash
git ls-files data/current.json data/snapshots models/ppr-v1 reports/ml
```

If missing, explicitly add the inference artifacts, not local environments or credentials:

```bash
git add -f data/current.json data/snapshots/ \
  models/ppr-v1/RB.joblib models/ppr-v1/WR.joblib \
  reports/ml/training_report.json reports/ml/test_predictions.csv
git commit -m "Include inference artifacts"
git push origin HEAD
```

Do not train models or download NFL datasets during a Vercel request. Refresh locally using the existing command and publish an updated snapshot when needed.

## 2. Create the new backend project

In Vercel, choose Add New → Project, then import `avenkat28/fantasy-advisor` again. Multiple projects can use the same repo.

- Name: `fantasy-advisor-api` (or another available name).
- Root Directory: repository root, `./`. Do **not** use `backend` or `frontend`.
- Framework Preset: FastAPI (normally detected from the root requirements).
- Build Command: use the checked-in `vercel.json` value, `python -m backend.scripts.check_deployment`.
- Install Command: leave the framework default; Vercel installs root `requirements.txt` automatically.
- Output Directory: leave the framework default.
- No Uvicorn Start Command is needed. Vercel invokes the exported ASGI app.
- Python version: controlled by `.python-version` (`3.12`).

Set this backend environment variable for Production:

```dotenv
FANTASY_CORS_ORIGIN=https://fantasy-advisor-omega.vercel.app
```

No trailing slash. Don't copy Render path overrides (`FANTASY_PLAYERS`, `FANTASY_SCHEDULES`, `FANTASY_MODELS`) unless intentionally changing the bundled-artifact layout. No secrets are needed for the current public read-only API.

Deploy and use the **actual assigned production URL** from Vercel's Domains settings. The project name does not guarantee a particular domain. Keep production API access public for browser calls; if Deployment Protection requires Vercel sign-in, anonymous API requests will not work. Do not embed a protection-bypass secret in `NEXT_PUBLIC_*` variables. Preview environments need their own deliberate access/CORS setup.

## 3. Verify the backend before switching the frontend

Open these URLs with the actual backend hostname:

```text
https://YOUR-API.vercel.app/api/health
https://YOUR-API.vercel.app/docs
https://YOUR-API.vercel.app/api/projections?season=2026&week=7&limit=1
```

Health must return `status: "ok"`, both models available, local data available and the expected snapshot metadata. The root `/` can return 404; it is not a UI. Projection availability still depends on roster observation time, freshness and valid schedules. Choose a week with eligible upcoming games at verification time.

Use Vercel Runtime Logs to inspect the elapsed timing added by the prediction service. If builds fail, inspect Build Logs. Missing required artifacts fail the preflight rather than quietly deploying an unusable prediction service. A missing `xgboost-cpu` wheel or bundle-limit error is a packaging failure, not a reason to switch model versions silently.

## 4. Switch the existing frontend project

In the existing frontend project's Settings → Environment Variables, change Production:

```dotenv
NEXT_PUBLIC_API_BASE_URL=https://YOUR-API.vercel.app
```

Use the full HTTPS origin, without a trailing `/api`. Redeploy the frontend after saving: `NEXT_PUBLIC_*` values are embedded at build time. Keep its Root Directory `frontend` and framework Next.js. The repository-root FastAPI configuration belongs to the new API project; do not point the existing UI project at the repository root.

Test dashboard, projections, search, player details, comparison and historical model evaluation through `https://fantasy-advisor-omega.vercel.app`. Verify browser network requests now target Vercel rather than Render and check for CORS or authentication failures.

## 5. Retire Render after verification

Keep Render until all pages work against the new API and measured cold/warm response times are acceptable. Once verified, suspend/delete only the old Render backend if desired. No model retraining or data regeneration is required for migration.

## Packaging and verification details

`app.py` exports the exact existing `backend.api.main.app`. Root `requirements.txt` is inference-only; `backend/requirements*.txt` remain the local/training dependency lists. The Linux x86_64 deployment uses official `xgboost-cpu==3.4.1` instead of the CUDA/NCCL-enabled distribution. The same model version and CPU inference interface are retained. Other platforms use the original distribution at the same version. Training utilities, nflreadpy, matplotlib and Polars are not part of the deployment requirements.

`vercel.json` uses the FastAPI preset, a 60-second function limit, and function-bundle exclusions for frontend assets, unused plot files and raw/processed data outside the published snapshot, local environments and caches. It does not exclude the published snapshots, RB/WR model bundles, training evaluation report or test prediction CSV. The source directories are not mounted as public static assets. `.vercelignore` also prevents local environments and credentials from entering CLI upload source.

The Linux CPython 3.12 wheels and transitive dependencies were downloaded and inspected: about **444.6 MB uncompressed**, before the small source/data/model artifacts and Vercel runtime overhead. This is an estimate, not a completed Vercel bundle; the actual build enforces the standard 500 MB limit. Vercel may change dependency resolution or runtime overhead. The Linux CPU package's real model inference has not been executed in this macOS environment (Docker's daemon was unavailable); verify the Vercel health/projection endpoints before switching traffic. Local startup/preflight and the 84-test offline backend suite passed with the existing CPU-only macOS runtime.

The hosting platform does not change the model's statistical accuracy or add security features to application code. Cold starts, usage limits and data freshness still apply. The frontend retains its 30-second request timeout, so verify complete requests meet that budget. Memory/feature caches are reused only within warm function instances; they are not durable storage. Snapshots must be refreshed/redeployed or stored externally, not updated in the read-only deployed source at request time. A Vercel Hobby deployment is not a guarantee of unlimited free compute or particular latency.

References: [Vercel FastAPI](https://vercel.com/docs/frameworks/backend/fastapi), [Python runtime](https://vercel.com/docs/functions/runtimes/python), [function limits](https://vercel.com/docs/functions/limitations), and [official XGBoost CPU installation](https://xgboost.readthedocs.io/en/stable/install.html).
