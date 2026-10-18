"""Known-value examples for player history, schedule validation, and defense totals."""
import json

import pandas as pd
import pytest

from backend.scripts.build_features import TARGET, build_features, run_pipeline
from backend.scripts.build_player_stats import ROOT


def fixture():
    schedules, rows = [], []
    for i, (season, week, day) in enumerate([
        (2023, 17, '2023-12-24'), (2023, 18, '2023-12-31'),
        (2024, 1, '2024-09-08'), (2024, 3, '2024-09-22'),
        (2024, 4, '2024-09-29'), (2024, 5, '2024-10-06'),
    ]):
        game = f'g{i}'
        schedules.append(dict(game_id=game, season=season, week=week, game_type='REG',
                              gameday=day, home_team='BUF', away_team='KC'))
        for player, points in [('a', 10 * (i + 1)), ('b', 2 * (i + 1))]:
            rows.append(dict(player_id=player, player_name=player, position='WR', team='KC',
                             opponent_team='BUF', season=season, week=week, season_type='REG',
                             game_id=game, fantasy_points_ppr=float(points), targets=float(i + 1),
                             receptions=float(i), passing_yards=0., rushing_yards=0.,
                             receiving_yards=float(points), carries=0., passing_tds=1.,
                             rushing_tds=2., receiving_tds=3., special_teams_tds=4.))
    return pd.DataFrame(rows), pd.DataFrame(schedules)


def test_player_windows_grouping_cross_season_and_byes():
    players, schedules = fixture()
    result = build_features(players.sample(frac=1, random_state=3), schedules)
    a = result[result.player_id == 'a'].reset_index(drop=True)
    b = result[result.player_id == 'b'].reset_index(drop=True)
    assert pd.isna(a.loc[0, 'fantasy_points_ppr_mean_3'])
    assert a.loc[1, 'fantasy_points_ppr_mean_3'] == 10
    assert a.loc[2, 'fantasy_points_ppr_mean_3'] == 15  # prior season
    assert a.loc[4, 'fantasy_points_ppr_mean_3'] == 30
    assert a.loc[5, 'fantasy_points_ppr_mean_5'] == 30
    assert a.loc[5, 'fantasy_points_ppr_mean_10'] == 30
    assert b.loc[2, 'fantasy_points_ppr_mean_3'] == 3
    assert a.loc[3, 'days_since_previous_game'] == 14  # missing week is not invented
    assert a.loc[5, 'prior_games'] == 5
    assert a.loc[2, 'fantasy_points_ppr_std_5'] == pytest.approx(7.0710678)
    assert pd.isna(a.loc[1, 'fantasy_points_ppr_std_5'])
    assert a.loc[2, 'previous_targets'] == 2
    assert a.loc[2, 'previous_receptions'] == 1
    assert a.loc[2, 'touchdowns_mean_3'] == 10
    assert a.loc[5, 'targets_trend_3_vs_5'] == 1
    assert not a.is_home.any()
    assert len(result) == len(players)
    assert 'fantasy_points_ppr' not in result
    assert 'receiving_yards' not in result


def test_defense_sums_players_before_rolling():
    players, schedules = fixture()
    result = build_features(players, schedules)
    a = result[result.player_id == 'a'].reset_index(drop=True)
    col = 'opponent_ppr_allowed_position_mean_3'
    assert pd.isna(a.loc[0, col])
    assert a.loc[1, col] == 12  # 10 + 2, not player mean 6
    assert a.loc[2, col] == 18
    assert a.loc[4, col] == 36
    assert a.loc[5, 'opponent_ppr_allowed_position_mean_5'] == 36
    assert a.loc[2, 'opponent_rushing_yards_allowed_mean_3'] == 0


def test_future_and_current_outcomes_cannot_change_earlier_inputs():
    players, schedules = fixture()
    baseline = build_features(players, schedules)
    changed = players.copy()
    columns = ['fantasy_points_ppr', 'targets', 'receptions', 'passing_yards', 'rushing_yards']
    changed.loc[changed.game_id == 'g3', columns] = 9999
    result = build_features(changed, schedules)
    columns = [c for c in baseline if c != TARGET]
    mask = baseline.game_id.isin(['g0', 'g1', 'g2', 'g3'])
    pd.testing.assert_frame_equal(baseline.loc[mask, columns], result.loc[mask, columns])


def test_missing_history_and_partial_unknown_totals():
    players, schedules = fixture()
    players.loc[players.game_id == 'g0', ['targets', 'fantasy_points_ppr']] = float('nan')
    players.loc[(players.game_id == 'g1') & (players.player_id == 'b'), 'fantasy_points_ppr'] = float('nan')
    result = build_features(players, schedules)
    a = result[result.player_id == 'a'].reset_index(drop=True)
    assert pd.isna(a.loc[1, 'targets_mean_3'])
    assert a.loc[2, 'targets_mean_3'] == 2  # ignores unknown; never imputes zero
    assert pd.isna(a.loc[2, 'opponent_ppr_allowed_position_mean_3'])
    assert pd.isna(a.loc[0, 'changed_team'])
    assert pd.isna(a.loc[0, 'days_since_previous_game'])


def test_optional_metrics_and_missing_opponent_are_supported():
    players, schedules = fixture()
    players = players.drop(columns=['opponent_team', 'game_id', 'targets', 'carries', 'special_teams_tds'])
    result = build_features(players, schedules)
    assert result.opponent_team.eq('BUF').all()
    assert 'targets_mean_3' not in result
    assert result.loc[result.game_id == 'g1', 'touchdowns_mean_3'].eq(6).all()


def test_changed_team_and_player_identity():
    players, schedules = fixture()
    players.loc[players.game_id == 'g5', 'team'] = 'BUF'
    players.loc[players.game_id == 'g5', 'opponent_team'] = 'KC'
    result = build_features(players, schedules)
    assert result.loc[result.game_id == 'g5', 'changed_team'].all()
    assert result.loc[result.game_id == 'g5', 'prior_games'].eq(5).all()


def test_defense_positions_and_yardage_are_separate():
    players, schedules = fixture()
    players.loc[players.player_id == 'b', 'position'] = 'RB'
    players.loc[players.player_id == 'a', 'passing_yards'] = 200
    players.loc[players.player_id == 'b', 'rushing_yards'] = 80
    result = build_features(players, schedules)
    second = result[result.game_id == 'g1'].set_index('player_id')
    assert second.loc['a', 'opponent_ppr_allowed_position_mean_3'] == 10
    assert second.loc['b', 'opponent_ppr_allowed_position_mean_3'] == 2
    assert second.opponent_passing_yards_allowed_mean_3.eq(200).all()
    assert second.opponent_rushing_yards_allowed_mean_3.eq(80).all()


def test_missing_defense_games_stay_inside_window():
    players, schedules = fixture()
    # No observed offensive rows in three scheduled games: unknown, not zero.
    players = players[~players.game_id.isin(['g1', 'g2', 'g3'])]
    result = build_features(players, schedules)
    fourth = result[result.game_id == 'g4']
    assert fourth.opponent_ppr_allowed_position_mean_3.isna().all()
    assert fourth.opponent_ppr_allowed_position_mean_5.eq(12).all()
    assert fourth.fantasy_points_ppr_mean_3.tolist() == [10, 2]


def test_no_optional_production_columns():
    players, schedules = fixture()
    players = players.drop(columns=['passing_yards', 'rushing_yards', 'receiving_yards',
                                    'targets', 'receptions', 'carries', 'passing_tds',
                                    'rushing_tds', 'receiving_tds', 'special_teams_tds'])
    result = build_features(players, schedules)
    assert 'touchdowns_mean_3' not in result
    assert 'opponent_passing_yards_allowed_mean_3' not in result
    assert len(result) == len(players)


@pytest.mark.parametrize('problem', ['duplicate_player', 'duplicate_schedule', 'team', 'opponent', 'game'])
def test_invalid_joins_fail(problem):
    players, schedules = fixture()
    if problem == 'duplicate_player':
        players = pd.concat([players, players.iloc[[0]]])
    elif problem == 'duplicate_schedule':
        schedules = pd.concat([schedules, schedules.iloc[[0]]])
    elif problem == 'team':
        players.loc[0, 'team'] = 'UNKNOWN'
    elif problem == 'opponent':
        players.loc[0, 'opponent_team'] = 'UNKNOWN'
    else:
        players.loc[0, 'game_id'] = 'bad'
    with pytest.raises(ValueError):
        build_features(players, schedules)


def test_pipeline_round_trip_and_manifest(tmp_path):
    players, schedules = fixture()
    source, schedule, output, report = [tmp_path / name for name in ['p.parquet', 's.parquet', 'f.parquet', 'r.json']]
    players.to_parquet(source)
    schedules.to_parquet(schedule)
    run_pipeline(source, output, report, schedule)
    manifest = json.loads(report.read_text())
    assert manifest['rows'] == 12
    assert TARGET not in manifest['feature_columns']
    assert {'position', 'team', 'season', 'season_type', 'week'} <= set(manifest['feature_columns'])
    assert 'source_fantasy_points_ppr' not in manifest['feature_columns']
    assert len(pd.read_parquet(output)) == 12
    with pytest.raises(ValueError, match='paths must differ'):
        run_pipeline(source, source, report, schedule)


def test_generated_features():
    path = ROOT / 'data/processed/player_features_2023_2025.parquet'
    if not path.exists():
        pytest.skip('Run feature pipeline first')
    features = pd.read_parquet(path)
    players = pd.read_parquet(ROOT / 'data/processed/player_weekly_2023_2025.parquet')
    assert len(features) == len(players)
    keys = ['player_id', 'season', 'season_type', 'week']
    joined = features.merge(players[keys + ['fantasy_points_ppr']], on=keys, validate='one_to_one')
    pd.testing.assert_series_equal(joined[TARGET], joined.fantasy_points_ppr, check_names=False)
