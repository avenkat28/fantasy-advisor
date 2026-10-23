"""Current refresh and roster point-in-time contracts; no external downloads."""
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.api.data import DataRepository
from backend.api.main import create_app
from backend.api.predictions import PredictionService
from backend.scripts.build_player_stats import SCORING_WEIGHTS
from backend.scripts.refresh_current_data import normalize_rosters, publish_snapshot, refresh
from backend.tests.test_api import setup  # noqa: F401 -- shared synthetic fixture


def roster_frame():
    return pd.DataFrame([
        dict(gsis_id='a', full_name='Player A', position='WR', team='BUF', season=2025, week=4, status='ACT'),
        dict(gsis_id='b', full_name='Player B', position='RB', team='KC', season=2025, week=4, status='ACT'),
        dict(gsis_id='rookie', full_name='New Rookie', position='WR', team='BUF', season=2025, week=4, status='ACT'),
    ])


def published(setup):
    data, _, root = setup
    stats = data.players.drop(columns=['game_date', 'is_home']).copy()
    stats = stats[stats.week.lt(4) & stats.season.eq(2025)]
    for column in SCORING_WEIGHTS:
        if column not in stats:
            stats[column] = 0.
    manifest = publish_snapshot(root, 2025, stats, data.schedules, roster_frame(), '2025-09-28T12:00:00Z')
    return DataRepository(root), manifest


def test_publish_preserves_original_and_validates(setup):
    _, _, root = setup
    original = (root / 'data/processed/player_weekly_2023_2025.parquet').read_bytes()
    data, manifest = published(setup)
    assert data.snapshot == manifest
    assert len(data.rosters) == 3
    assert data.players.season.eq(2024).any()
    assert (root / 'data/processed/player_weekly_2023_2025.parquet').read_bytes() == original
    assert data.players[data.players.season.eq(2025)].week.max() == 3


def test_roster_changes_team_and_supports_career_history(setup):
    data, _ = published(setup)
    # A last played for KC; the roster now places A on BUF before the matchup.
    # Remove same-season history: a verified weekly roster allows a veteran's prior season history.
    data.players = data.players[~(data.players.player_id.eq('a') & data.players.season.eq(2025))]
    service = PredictionService(data)
    result = service.project('a', 2025, 4)
    assert result['team'] == 'BUF'
    assert result['opponent'] == 'KC'
    assert result['eligibility_source'] == 'weekly_roster'
    assert result['historical_games'] == 2
    assert result['roster_week'] == 4
    assert result['roster_observed_at'].startswith('2025-09-28')
    row = service.day_features(2025, 4, '2025-09-29')
    assert bool(row[row.player_id.eq('a')].iloc[0].changed_team)


def test_roster_only_players_search_details_and_unavailable(setup):
    data, _ = published(setup)
    with TestClient(create_app(data, PredictionService(data))) as c:
        assert c.get('/api/players?search=rookie').json()[0]['player_id'] == 'rookie'
        detail = c.get('/api/players/rookie')
        assert detail.status_code == 200
        assert detail.json()['recent_games'] == []
        assert c.get('/api/projections/rookie?season=2025&week=4').json()['error']['code'] == 'insufficient_data'
        result = c.get('/api/projections?season=2025&week=4').json()
        assert result['total'] == 2
        assert any(p['player_id'] == 'rookie' for p in result['unavailable'])


def test_roster_cannot_be_backdated_or_carried_forward(setup):
    data, _ = published(setup)
    service = PredictionService(data)
    data.rosters['observed_at'] = pd.Timestamp('2025-09-30T00:00:00Z')
    with TestClient(create_app(data, service)) as c:
        r = c.get('/api/projections/a?season=2025&week=4')
        assert r.status_code == 422
        assert r.json()['error']['code'] == 'roster_unavailable'
        assert c.get('/api/projections?season=2025&week=5').status_code == 422
    data.rosters['observed_at'] = pd.Timestamp('2025-09-01T00:00:00Z')
    assert data.roster_for_week(2025, 4, pd.Timestamp('2025-09-29')).empty


def test_archived_rosters_resolve_as_of_game(setup):
    data, _ = published(setup)
    later = data.rosters.copy()
    later['observed_at'] = pd.Timestamp('2025-09-30T00:00:00Z')
    later.loc[later.player_id.eq('a'), 'team'] = 'KC'
    data.rosters = pd.concat([data.rosters, later], ignore_index=True)
    assert PredictionService(data).project('a', 2025, 4)['team'] == 'BUF'


def test_week_roster_not_inferred_for_unpublished_current_season(setup):
    data, service, _ = setup
    data.context.loc[data.context.season.eq(2025), 'season'] = 2026
    with TestClient(create_app(data, service)) as c:
        r = c.get('/api/projections?season=2026&week=4')
        assert r.status_code == 422
        assert r.json()['error']['code'] == 'roster_unavailable'


def test_refresh_failure_keeps_working_manifest(setup):
    data, manifest = published(setup)
    root = data.root
    before = (root / 'data/current.json').read_bytes()
    class FailingLoader:
        def load_player_stats(self, *args, **kwargs):
            raise RuntimeError('Source unavailable')
    with pytest.raises(RuntimeError):
        refresh(root, 2026, FailingLoader())
    assert (root / 'data/current.json').read_bytes() == before
    assert DataRepository(root).snapshot == manifest


def test_ambiguous_rosters_rejected_and_manifest_unchanged(setup):
    data, _ = published(setup)
    before = (data.root / 'data/current.json').read_bytes()
    raw = roster_frame()
    duplicate = raw.iloc[[0]].copy()
    duplicate['team'] = 'KC'
    with pytest.raises(ValueError, match='Ambiguous'):
        normalize_rosters(pd.concat([raw, duplicate]), '2025-09-28T12:00:00Z')
    assert (data.root / 'data/current.json').read_bytes() == before


def test_new_snapshot_preserves_first_observations(setup):
    data, manifest = published(setup)
    stats = data.players[data.players.season.eq(2025)].drop(columns=['game_date', 'is_home'])
    for column in SCORING_WEIGHTS:
        if column not in stats:
            stats[column] = 0.
    publish_snapshot(data.root, 2025, stats, data.schedules, roster_frame(), '2025-09-28T18:00:00Z')
    updated = DataRepository(data.root)
    assert len(updated.rosters) == 6
    assert updated.rosters.observed_at.min() == pd.Timestamp('2025-09-28T12:00:00Z')


def test_future_statistics_do_not_replace_working_snapshot(setup):
    data, _ = published(setup)
    stats = data.players[data.players.season.eq(2025)].drop(columns=['game_date', 'is_home'])
    for column in SCORING_WEIGHTS:
        if column not in stats:
            stats[column] = 0.
    before = (data.root / 'data/current.json').read_bytes()
    with pytest.raises(ValueError, match='future games'):
        publish_snapshot(data.root, 2025, stats, data.schedules, roster_frame(), '2025-09-01T12:00:00Z')
    assert (data.root / 'data/current.json').read_bytes() == before


def test_source_roster_status_filters_recommendations(setup):
    data, _ = published(setup)
    data.rosters.loc[data.rosters.player_id.eq('a'), 'roster_status'] = 'RES'
    with TestClient(create_app(data, PredictionService(data))) as c:
        result = c.get('/api/projections/a?season=2025&week=4')
        assert result.status_code == 422
        assert result.json()['error']['code'] == 'roster_not_eligible'
        weekly = c.get('/api/projections?season=2025&week=4').json()
        assert weekly['total'] == 1
        assert any(p['code'] == 'roster_not_eligible' for p in weekly['unavailable'])


def test_missing_published_roster_degrades_health(setup):
    data, manifest = published(setup)
    (data.root / manifest['rosters']).unlink()
    reloaded = DataRepository(data.root)
    with TestClient(create_app(reloaded, PredictionService(reloaded))) as c:
        assert c.get('/api/health').json()['status'] == 'degraded'
        assert c.get('/api/projections/a?season=2025&week=4').json()['error']['code'] == 'roster_unavailable'
