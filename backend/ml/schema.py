"""Explicit reviewed pregame feature contract; never infer inputs from dtypes."""
import numpy as np
import pandas as pd

FEATURES = [
    'is_home', 'fantasy_points_ppr_mean_3', 'fantasy_points_ppr_mean_5',
    'fantasy_points_ppr_mean_10', 'rushing_yards_mean_3', 'rushing_yards_mean_5',
    'receiving_yards_mean_3', 'receiving_yards_mean_5', 'receptions_mean_3',
    'receptions_mean_5', 'targets_mean_3', 'targets_mean_5', 'carries_mean_3',
    'carries_mean_5', 'touchdowns_mean_3', 'touchdowns_mean_5',
    'fantasy_points_ppr_std_5', 'previous_fantasy_points_ppr', 'previous_targets',
    'previous_receptions', 'targets_trend_3_vs_5', 'prior_games',
    'days_since_previous_game', 'changed_team',
    'opponent_ppr_allowed_position_mean_3', 'opponent_ppr_allowed_position_mean_5',
    'opponent_prior_games', 'opponent_rushing_yards_allowed_mean_3',
    'opponent_rushing_yards_allowed_mean_5',
]


def feature_frame(frame: pd.DataFrame, strict: bool = False) -> pd.DataFrame:
    missing = set(FEATURES) - set(frame)
    extra = set(frame) - set(FEATURES) if strict else set()
    if missing or extra or frame.empty:
        raise ValueError(f'Invalid feature schema: missing={sorted(missing)}, extra={sorted(extra)}')
    result = frame[FEATURES].copy()
    for column in FEATURES:
        if not pd.api.types.is_numeric_dtype(result[column]):
            raise ValueError(f'{column} must contain numeric/boolean values or null')
    result = result.astype(float)
    if np.isinf(result.to_numpy()).any():
        raise ValueError('Infinite feature values are invalid')
    return result
