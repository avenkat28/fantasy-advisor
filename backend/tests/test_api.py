"""Offline service and HTTP tests with tiny historical fixtures and trusted dummy models."""
import json

import joblib
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.api.comparison import compare_projections
from backend.api.data import DataRepository
from backend.api.main import create_app
from backend.api.predictions import PredictionService, pregame_features
from backend.ml.schema import FEATURES
from backend.scripts.build_features import build_features
from backend.tests.test_features import fixture


class ConstantModel:
    def __init__(self, value):
        self.value = value

    def predict(self, frame):
        assert list(frame.columns) == FEATURES
        return np.repeat(self.value, len(frame))


@pytest.fixture

def setup(tmp_path, monkeypatch):
    for name in ['FANTASY_PLAYERS', 'FANTASY_SCHEDULES', 'FANTASY_MODELS', 'FANTASY_CLOSE_CALL_POINTS']:
        monkeypatch.delenv(name, raising=False)
    players, schedules = fixture()
    players['season'] += 1
    schedules['season'] += 1
    schedules['gameday'] = (pd.to_datetime(schedules.gameday) + pd.DateOffset(years=1)).dt.strftime('%Y-%m-%d')
    players.loc[players.player_id.eq('b'), 'position'] = 'RB'
    for path in ['data/processed', 'data/raw', 'models/ppr-v1', 'reports/ml']:
        (tmp_path / path).mkdir(parents=True)
    players.to_parquet(tmp_path / 'data/processed/player_weekly_2023_2025.parquet')
    schedules.to_parquet(tmp_path / 'data/raw/schedules_2023_2025.parquet')
    for position, value in [('RB', 9.), ('WR', 10.)]:
        joblib.dump({'model': ConstantModel(value), 'metadata': {'position': position, 'features': FEATURES, 'version': 'test'}}, tmp_path / f'models/ppr-v1/{position}.joblib')
    (tmp_path / 'reports/ml/training_report.json').write_text(json.dumps({'version': 'test', 'periods': {'test': 'fixture'}, 'test_metrics': [{'position': 'WR', 'mae': 1.}]}))
    pd.DataFrame([dict(player_id='a', player_name='a', season=2025, week=4, actual=11., xgboost=10., absolute_error=1.)]).to_csv(tmp_path / 'reports/ml/test_predictions.csv', index=False)
    data = DataRepository(tmp_path)
    service = PredictionService(data)
    return data, service, tmp_path


@pytest.fixture

def client(setup):
    data, service, _ = setup
    with TestClient(create_app(data, service), raise_server_exceptions=False) as client:
        yield client


def test_health_search_details(client):
    assert client.get('/api/health').json()['status'] == 'ok'
    assert len(client.get('/api/players?search=A').json()) == 1
    assert client.get('/api/players?search=unknown').json() == []
    detail = client.get('/api/players/a').json()
    assert detail['data_type'] == 'historical_snapshot'
    assert len(detail['recent_games']) == 5
    assert detail['recent_games'][-1]['season'] == 2025
    assert client.get('/api/players/unknown').status_code == 404


def test_position_models_schema_weekly_comparison(client):
    params = {'season': 2025, 'week': 4}
    wr = client.get('/api/projections/a', params=params)
    rb = client.get('/api/projections/b', params=params)
    assert wr.status_code == rb.status_code == 200
    assert wr.json()['projected_ppr_points'] == 10
    assert rb.json()['projected_ppr_points'] == 9
    assert wr.json()['prediction_type'] == 'pregame'
    assert wr.json()['historical_games'] == 4
    assert 'confidence' not in wr.json()
    weekly = client.get('/api/projections', params={**params, 'limit': 1}).json()
    assert weekly['total'] == 2
    assert len(weekly['projections']) == 1
    assert weekly['projections'][0]['player_id'] == 'a'
    assert client.get('/api/projections', params={**params, 'position': 'RB'}).json()['total'] == 1
    comparison = client.get('/api/compare', params={**params, 'player1_id': 'a', 'player2_id': 'b'}).json()
    assert comparison['recommended_player_id'] == 'a'
    assert comparison['close_call']
    assert comparison['difference'] == 1


@pytest.mark.parametrize('path,status,code', [
    ('/api/projections/a?season=2026&week=4', 404, 'schedule_not_found'),
    ('/api/projections/a?season=2025&week=19', 422, 'invalid_request'),
    ('/api/projections/a?season=2025&week=1', 422, 'insufficient_data'),
    ('/api/projections/a?season=x&week=4', 422, 'invalid_request'),
    ('/api/projections?season=2025&week=4&position=QB', 422, 'invalid_request'),
    ('/api/players?limit=0', 422, 'invalid_request'),
])
def test_errors(client, path, status, code):
    response = client.get(path)
    assert response.status_code == status
    assert response.json()['error']['code'] == code


def test_missing_models_and_data(setup):
    data, _, root = setup
    (root / 'models/ppr-v1/RB.joblib').unlink()
    with TestClient(create_app(data, PredictionService(data))) as c:
        assert c.get('/api/health').json()['status'] == 'degraded'
        assert c.get('/api/projections/b?season=2025&week=4').status_code == 503
        result = c.get('/api/projections?season=2025&week=4').json()
        assert result['unavailable'][0]['code'] == 'model_unavailable'
    data.players = pd.DataFrame()
    with TestClient(create_app(data, PredictionService(data))) as c:
        assert c.get('/api/players').status_code == 503


def test_history_performance(client, setup):
    assert client.get('/api/model/performance').json()['metrics'][0]['mae'] == 1
    history = client.get('/api/predictions/history?player_id=a').json()
    assert history['evaluation_type'] == 'held_out_test'
    assert history['records'][0]['absolute_error'] == 1
    assert client.get('/api/predictions/history?player_id=b').json()['records'] == []
    data, _, _ = setup
    data.history = None
    data.report = None
    assert not client.get('/api/model/performance').json()['available']
    assert not client.get('/api/predictions/history?player_id=a').json()['available']


def test_no_future_leakage_and_exact_training_features(setup):
    data, service, _ = setup
    game = service.schedule(2025, 4).query("team == 'KC'").iloc[0]
    baseline, _ = pregame_features(data.players, data.schedules, 'a', game)
    altered = data.players.copy()
    mask = altered.game_date.ge(game.game_date)
    for column in ['fantasy_points_ppr', 'targets', 'receptions', 'rushing_yards', 'receiving_yards']:
        altered.loc[mask, column] = 999999.
    altered.loc[mask, 'team'] = 'FAKE'
    changed, _ = pregame_features(altered, data.schedules, 'a', game)
    pd.testing.assert_series_equal(baseline[FEATURES], changed[FEATURES])
    removed, _ = pregame_features(data.players[~mask], data.schedules, 'a', game)
    pd.testing.assert_series_equal(baseline[FEATURES], removed[FEATURES])
    raw = data.players.drop(columns=['game_date', 'is_home'])
    trained = build_features(raw, data.schedules)
    expected = trained[trained.player_id.eq('a') & trained.game_id.eq(game.game_id)].iloc[0]
    pd.testing.assert_series_equal(baseline[FEATURES], expected[FEATURES])


def test_comparison_tie_and_threshold():
    a = dict(player_id='a', player_name='A', projected_ppr_points=10., recent_ppr_mean_3=None, matchup_features={})
    b = {**a, 'player_id': 'b', 'player_name': 'B'}
    assert compare_projections(a, b, 2)['recommended_player_id'] is None
    b['projected_ppr_points'] = 13
    result = compare_projections(a, b, 2)
    assert result['recommended_player_id'] == 'b'
    assert not result['close_call']


def test_unsupported_bye_and_internal_errors(setup):
    data, service, _ = setup
    data.players.loc[data.players.player_id.eq('a'), 'position'] = 'QB'
    with TestClient(create_app(data, service), raise_server_exceptions=False) as c:
        assert c.get('/api/projections/a?season=2025&week=4').status_code == 422
        data.players.loc[data.players.player_id.eq('a'), 'position'] = 'WR'
        service.models['WR']['model'] = object()
        response = c.get('/api/projections/a?season=2025&week=4')
        assert response.status_code == 500
        assert response.json()['error']['message'] == 'An internal server error occurred.'
    data.context = data.context[~(data.context.week.eq(4) & data.context.team.eq('KC'))]
    with TestClient(create_app(data, service)) as c:
        assert c.get('/api/projections/a?season=2025&week=4').status_code == 404


def test_weekly_batches_inference_by_position_and_preserves_individual_results(setup):
    from unittest.mock import patch
    data, service, _ = setup
    clone = data.players[data.players.player_id.eq('a')].copy()
    clone['player_id'] = 'a2'
    clone['player_name'] = 'Second receiver'
    clone['fantasy_points_ppr'] += 5
    data.players = pd.concat([data.players, clone], ignore_index=True)

    class HistoryModel:
        def predict(self, frame):
            return frame.previous_fantasy_points_ppr.to_numpy() / 10

    service.models['WR']['model'] = HistoryModel()
    service.models['RB']['model'] = HistoryModel()
    with patch.object(service.models['WR']['model'], 'predict', wraps=service.models['WR']['model'].predict) as wr_predict, \
         patch.object(service.models['RB']['model'], 'predict', wraps=service.models['RB']['model'].predict) as rb_predict:
        projections, unavailable = service.weekly(2025, 4, None)
        assert not unavailable
        assert wr_predict.call_count == rb_predict.call_count == 1
        assert len(wr_predict.call_args.args[0]) == 2
        assert len(rb_predict.call_args.args[0]) == 1
    for projection in projections:
        individual = service.project(projection['player_id'], 2025, 4)
        assert projection['projected_ppr_points'] == individual['projected_ppr_points']
        assert projection['historical_games'] == individual['historical_games']


def test_concurrent_cold_feature_requests_build_once(setup):
    from concurrent.futures import ThreadPoolExecutor
    from unittest.mock import patch
    from backend.api.predictions import pregame_rows
    _, service, _ = setup
    with patch('backend.api.predictions.pregame_rows', wraps=pregame_rows) as build:
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(lambda _: service.day_features(2025, 4, '2025-09-29'), range(3)))
        assert build.call_count == 1
        assert all(result is results[0] for result in results)
