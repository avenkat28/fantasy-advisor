"""Contract, temporal integrity, metrics, and persistence regression tests."""
import json

import joblib
import numpy as np
import pandas as pd
import pytest

from backend.ml.evaluate import metrics
from backend.ml.predict import predict_points
from backend.ml.schema import FEATURES, feature_frame
from backend.scripts.build_features import TARGET, build_features
from backend.scripts.build_player_stats import ROOT
from backend.scripts.train_models import chronological_split, validate_dataset, xgb_pipeline
from backend.tests.test_features import fixture


def test_allowlist_excludes_outcomes_and_identifiers():
    forbidden = {TARGET, 'fantasy_points_ppr', 'source_fantasy_points_ppr', 'passing_yards',
                 'rushing_yards', 'receiving_yards', 'targets', 'receptions', 'carries',
                 'passing_tds', 'rushing_tds', 'receiving_tds', 'special_teams_tds',
                 'offense_snaps', 'offense_pct', 'player_id', 'player_name', 'position', 'season'}
    assert not set(FEATURES) & forbidden
    assert len(set(FEATURES)) == len(FEATURES)
    frame = pd.DataFrame({c: [1.] for c in FEATURES} | {TARGET: [999.], 'carries': [999.]})
    assert list(feature_frame(frame)) == FEATURES


def test_future_and_current_outcomes_do_not_change_approved_features():
    players, schedule = fixture()
    before = build_features(players, schedule)
    players.loc[players.game_id.isin(['g3', 'g4', 'g5']),
                ['fantasy_points_ppr', 'targets', 'carries', 'receiving_yards', 'rushing_yards']] = 99999
    after = build_features(players, schedule)
    mask = before.game_id.isin(['g0', 'g1', 'g2', 'g3'])
    pd.testing.assert_frame_equal(feature_frame(before.loc[mask]), feature_frame(after.loc[mask]))


def split_fixture():
    return pd.DataFrame([dict(position=p, season=s, week=w, season_type='REG',
                              game_date=d, game_id=str(s) + str(w))
                         for p in ['RB', 'WR'] for s, w, d in
                         [(2023, 1, '2023-09-10'), (2024, 18, '2025-01-05'),
                          (2025, 9, '2025-11-02'), (2025, 10, '2025-11-09')]])


def test_chronological_game_splits():
    train, val, test = chronological_split(split_fixture())
    assert set(train.season) == {2023, 2024}
    assert val.week.eq(9).all() and test.week.eq(10).all()
    assert train.game_date.max() < val.game_date.min() < test.game_date.min()
    assert not set(val.game_id) & set(test.game_id)
    bad = split_fixture()
    bad.loc[bad.week == 10, 'game_date'] = '2025-10-01'
    with pytest.raises(ValueError, match='chronological'):
        chronological_split(bad)
    bad = split_fixture()
    bad['game_id'] = 'same'
    with pytest.raises(ValueError, match='crosses'):
        chronological_split(bad)


def test_metrics_known_values():
    result = metrics([0, 2, 4], [1, 2, 3])
    assert result == pytest.approx(dict(mae=2 / 3, rmse=np.sqrt(2 / 3), r2=.75, bias=0))
    assert metrics([0, 1], [1, 2])['bias'] == 1
    with pytest.raises(ValueError):
        metrics([np.nan], [1])


@pytest.mark.parametrize('position', ['RB', 'WR'])
def test_model_round_trip_and_strict_inference(tmp_path, position):
    rng = np.random.default_rng(42)
    x = pd.DataFrame(rng.normal(size=(40, len(FEATURES))), columns=FEATURES)
    model = xgb_pipeline(trees=3).fit(x, x.iloc[:, 1] * 2)
    path = tmp_path / f'{position}.joblib'
    joblib.dump({'model': model, 'metadata': {'features': FEATURES, 'position': position}}, path)
    np.testing.assert_array_equal(model.predict(x), joblib.load(path)['model'].predict(x))
    record = x.iloc[0].to_dict()
    result = predict_points(path, record)
    assert np.isfinite(result['predicted_fantasy_points_ppr'])
    assert result['metadata']['position'] == position
    assert result['predicted_fantasy_points_ppr'] == pytest.approx(float(model.predict(x.iloc[:1])[0]))
    for changed in [dict(record, **{TARGET: 99}), {k: v for k, v in record.items() if k != FEATURES[0]},
                    dict(record, is_home='1'), dict(record, is_home=float('inf'))]:
        with pytest.raises(ValueError):
            predict_points(path, changed)
    null_record = dict(record, fantasy_points_ppr_mean_3=None)
    assert np.isfinite(predict_points(path, null_record)['predicted_fantasy_points_ppr'])


def test_real_dataset_validation_and_upstream_reproduction():
    path = ROOT / 'data/processed/player_features_2023_2025.parquet'
    if not path.exists():
        pytest.skip('Run data pipelines first')
    frame = pd.read_parquet(path)
    validate_dataset(frame)
    for bad in [pd.concat([frame, frame.iloc[:1]]), frame.assign(**{TARGET: np.inf})]:
        with pytest.raises(ValueError):
            validate_dataset(bad)
    players = pd.read_parquet(ROOT / 'data/processed/player_weekly_2023_2025.parquet')
    schedules = pd.read_parquet(ROOT / 'data/raw/schedules_2023_2025.parquet')
    rebuilt = build_features(players, schedules)
    pd.testing.assert_frame_equal(frame, rebuilt)


@pytest.mark.parametrize('position', ['RB', 'WR'])
def test_generated_models(position):
    path = ROOT / f'models/ppr-v1/{position}.joblib'
    if not path.exists():
        pytest.skip('Run training first')
    record = json.loads((ROOT / f'reports/ml/{position}_example_features.json').read_text())
    first = predict_points(path, record)
    assert first == predict_points(path, record)
    assert np.isfinite(first['predicted_fantasy_points_ppr'])
    assert first['metadata']['position'] == position
