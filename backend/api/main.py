"""Run with: uvicorn backend.api.main:app --reload."""
from contextlib import asynccontextmanager
import logging
import os
from typing import Annotated, Literal

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api import schemas as s
from backend.api.comparison import compare_projections
from backend.api.data import APIError, DataRepository
from backend.api.predictions import ELIGIBILITY, PredictionService

Season = Annotated[int, Query(ge=2023, le=2100)]
Week = Annotated[int, Query(ge=1, le=18)]
Limit = Annotated[int, Query(ge=1, le=500)]
Offset = Annotated[int, Query(ge=0)]


def create_app(repository: DataRepository | None = None, predictions: PredictionService | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        app.state.data = repository if repository is not None else DataRepository()
        app.state.predictions = predictions if predictions is not None else PredictionService(app.state.data)
        app.state.threshold = float(os.getenv('FANTASY_CLOSE_CALL_POINTS', '2.0'))
        if not 0 <= app.state.threshold < float('inf'):
            raise ValueError('Close-call threshold must be finite and nonnegative')
        yield

    app = FastAPI(title='FantasyAdvisor', version='0.4.0', lifespan=lifespan,
                  responses={code: {'model': s.ErrorResponse} for code in [404, 422, 500, 503]})
    app.add_middleware(CORSMiddleware, allow_origins=[os.getenv('FANTASY_CORS_ORIGIN', 'http://localhost:3000')],
                       allow_methods=['GET'], allow_headers=['Content-Type'])

    @app.exception_handler(APIError)
    async def api_error(request, error):
        return JSONResponse(status_code=error.status, content={'error': {'code': error.code, 'message': error.message}})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return JSONResponse(status_code=422, content={'error': {'code': 'invalid_request', 'message': 'Invalid path or query parameters.'}})

    @app.exception_handler(Exception)
    async def internal_error(request, error):
        logging.getLogger(__name__).exception('API request failed', exc_info=error)
        return JSONResponse(status_code=500, content={'error': {'code': 'internal_error', 'message': 'An internal server error occurred.'}})

    @app.get('/api/health', response_model=s.Health)
    def health(request: Request):
        models = {p: p in request.app.state.predictions.models for p in ['RB', 'WR']}
        data = request.app.state.data
        available = not data.players.empty and not data.context.empty and (data.snapshot is None or not data.rosters.empty)
        snapshot = None
        if data.snapshot is not None:
            snapshot = {**data.snapshot, 'roster_weeks': {str(int(season)): sorted(rows.week.unique().tolist())
                        for season, rows in data.rosters.groupby('season')} if not data.rosters.empty else {}}
        return dict(status='ok' if all(models.values()) and available else 'degraded', models_available=models, data_available=available, snapshot=snapshot)

    @app.get('/api/players', response_model=list[s.Player])
    def players(request: Request, search: str = '', limit: Limit = 50):
        return request.app.state.data.search(search, limit)

    @app.get('/api/players/{player_id}', response_model=s.PlayerDetails)
    def player(request: Request, player_id: str):
        return request.app.state.data.details(player_id)

    @app.get('/api/projections', response_model=s.WeeklyProjections)
    def weekly(request: Request, season: Season, week: Week, position: Literal['RB', 'WR'] | None = None,
               limit: Limit = 50, offset: Offset = 0):
        predictions, unavailable = request.app.state.predictions.weekly(season, week, position)
        return dict(projections=predictions[offset:offset + limit], unavailable=unavailable,
                    total=len(predictions), offset=offset, limit=limit, eligibility=ELIGIBILITY)

    @app.get('/api/projections/{player_id}', response_model=s.Projection)
    def projection(request: Request, player_id: str, season: Season, week: Week):
        return request.app.state.predictions.project(player_id, season, week)

    @app.get('/api/compare', response_model=s.Comparison)
    def compare(request: Request, player1_id: str, player2_id: str, season: Season, week: Week):
        service = request.app.state.predictions
        return compare_projections(service.project(player1_id, season, week), service.project(player2_id, season, week), request.app.state.threshold)

    @app.get('/api/model/performance', response_model=s.Performance)
    def performance(request: Request):
        report = request.app.state.data.report
        if not report or not report.get('test_metrics'):
            return dict(available=False, message='Task 3 evaluation artifacts are unavailable.')
        return dict(available=True, model_version=report['version'], periods=report['periods'], metrics=report['test_metrics'])

    @app.get('/api/predictions/history', response_model=s.PredictionHistory)
    def history(request: Request, player_id: str, limit: Limit = 100, offset: Offset = 0):
        data = request.app.state.data
        data.records(player_id)
        if data.history is None:
            return dict(available=False, records=[], message='Saved held-out test predictions are unavailable. Run the original Task 3 training export.')
        rows = data.history[data.history.player_id.eq(player_id)].sort_values(['season', 'week']).iloc[offset:offset + limit]
        return dict(available=True, records=[dict(player_id=row.player_id, player_name=row.player_name,
                    season=int(row.season), week=int(row.week), predicted_ppr_points=float(row.xgboost),
                    actual_ppr_points=float(row.actual), absolute_error=float(row.absolute_error)) for _, row in rows.iterrows()])

    return app


app = create_app()
