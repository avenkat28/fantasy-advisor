"""Scoring, eligibility, images, and inference for kickers and team D/ST."""
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.scoring import KICKING, DEFENSE, defense_records, points_allowed_bonus, weighted_points
from backend.api.main import create_app
from backend.tests.test_api import setup  # noqa: F401
from backend.tests.test_current_data import published
from backend.scripts.build_player_stats import clean_player_stats, SCORING_WEIGHTS


def test_kicker_distance_scoring_and_unknown_components():
    row = dict.fromkeys(KICKING, 1)
    assert weighted_points(pd.DataFrame([row]), KICKING).iloc[0] == 24
    row['pat_made'] = None
    assert pd.isna(weighted_points(pd.DataFrame([row]), KICKING).iloc[0])
    with pytest.raises(ValueError, match='Missing scoring'):
        weighted_points(pd.DataFrame([row]).drop(columns='fg_made_60_'), KICKING)


def test_kicker_ingestion_uses_kicking_score_and_retains_photo():
    row = dict(player_id='k', player_name='Kicker', position='K', team='BUF',
               season=2025, week=1, season_type='REG', headshot_url='https://example.com/k.png',
               **dict.fromkeys(SCORING_WEIGHTS, 0), **dict.fromkeys(KICKING, 1))
    row['passing_tds'] = 4  # This must not become part of kicker scoring.
    result = clean_player_stats(pd.DataFrame([row])).iloc[0]
    assert result.fantasy_points_ppr == 24
    assert result.headshot_url == row['headshot_url']
    assert pd.isna(result.passing_tds)


@pytest.mark.parametrize('allowed,expected', [(0,10),(1,7),(6,7),(7,4),(13,4),(14,1),
    (20,1),(21,0),(27,0),(28,-1),(34,-1),(35,-4),(70,-4)])
def test_points_allowed_tiers(allowed, expected):
    assert points_allowed_bonus(pd.Series([allowed])).iloc[0] == expected


def test_defense_combines_team_stats_without_double_counting_fumble_tds():
    raw = pd.DataFrame([dict(team='BUF', season=2025, week=1, season_type='REG',
        game_id='g', **dict.fromkeys(DEFENSE, 1), fumble_recovery_tds=1)])
    schedules = pd.DataFrame([dict(game_id='g', home_team='BUF', away_team='KC', home_score=7, away_score=0)])
    result = defense_records(raw, schedules).iloc[0]
    # 1 sack + 2*(INT+recovery+safety+3 blocks+2pt return) + 6*(DEF TD+ST TD) + 10 shutout.
    assert result.fantasy_points_ppr == 37
    assert result.player_id == 'DST:BUF'
    schedules.loc[0, 'away_score'] = None
    assert pd.isna(defense_records(raw, schedules).iloc[0].fantasy_points_ppr)


def test_defense_without_individual_roster_and_negative_projection(setup):
    data, service, _ = setup
    # A permanent team identity uses the schedule rather than individual roster status.
    data.players.loc[data.players.player_id.eq('a'), ['player_id','position','player_name']] = ['DST:KC','DST','Kansas City D/ST']
    response = service.project('DST:KC', 2025, 4)
    assert response['eligibility_source'] == 'team_schedule'
    assert response['projected_ppr_points'] == -1
    assert response['availability'] == 'team_unit'
    with TestClient(create_app(data, service)) as client:
        assert client.get('/api/projections?season=2025&week=4&position=DST').status_code == 200
        assert client.get('/api/players/DST:KC').status_code == 200


def test_kicker_requires_observed_weekly_roster(setup):
    data, _ = published(setup)
    from backend.api.predictions import PredictionService
    data.players.loc[data.players.player_id.eq('a'), 'position'] = 'K'
    data.rosters.loc[data.rosters.player_id.eq('a'), 'position'] = 'K'
    result = PredictionService(data).project('a', 2025, 4)
    assert result['position'] == 'K'
    assert result['eligibility_source'] == 'weekly_roster'
    data.rosters.loc[data.rosters.player_id.eq('a'), 'observed_at'] = pd.Timestamp('2025-09-30T12:00Z')
    from backend.api.data import APIError
    with pytest.raises(APIError) as error:
        PredictionService(data).project('a', 2025, 4)
    assert error.value.code == 'roster_unavailable'
