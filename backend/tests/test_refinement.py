"""Chronological boundaries for recurring model refinement."""
import pandas as pd
import pytest
from backend.scripts.refine_models import recent_split


def sample():
    return pd.DataFrame([
        dict(season=2025, week=18, season_type='REG', position='RB', game_date='2026-01-04'),
        *[dict(season=2026, week=w, season_type='REG', position='RB',
               game_date=f'2026-10-{w * 7:02}') for w in [1, 2, 3, 4]],
        dict(season=2027, week=1, season_type='REG', position='RB', game_date='2027-09-12'),
    ])


def test_recent_weeks_are_excluded_from_fit_and_future_is_excluded():
    train, test = recent_split(sample(), 2026)
    assert set(train.loc[train.season.eq(2026), 'week']) == {1, 2}
    assert set(test.week) == {3, 4}
    assert train.season.max() == test.season.max() == 2026
    assert pd.to_datetime(train.game_date).max() < pd.to_datetime(test.game_date).min()


def test_refuses_insufficient_or_overlapping_dates():
    with pytest.raises(ValueError, match='Insufficient'):
        recent_split(sample(), 2026, 4)
    frame = sample()
    frame.loc[frame.season.eq(2025), 'game_date'] = '2026-12-01'
    with pytest.raises(ValueError, match='chronological'):
        recent_split(frame, 2026)
