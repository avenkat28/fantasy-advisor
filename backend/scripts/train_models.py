"""Train on 2023–24; select using 2025 weeks 1–9; test once on weeks 10–18."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from backend.ml.evaluate import evaluate, metrics
from backend.ml.predict import predict_points
from backend.ml.schema import FEATURES, feature_frame
from backend.scripts.build_features import TARGET
from backend.scripts.build_player_stats import ROOT

SEED = 42
VERSION = 'ppr-v1'


def validate_dataset(frame):
    required = set(FEATURES + [TARGET, 'player_id', 'player_name', 'position', 'season',
                              'week', 'season_type', 'game_id', 'game_date', 'team', 'opponent_team'])
    if required - set(frame):
        raise ValueError(f'Missing dataset columns: {sorted(required - set(frame))}')
    keys = ['player_id', 'season', 'season_type', 'week']
    metadata = ['player_id', 'position', 'game_id', 'game_date', 'season', 'week', 'season_type', 'team', 'opponent_team']
    if frame[metadata].isna().any().any() or frame.duplicated(keys).any() or frame.duplicated(['player_id', 'game_id']).any():
        raise ValueError('Missing identifiers or duplicate player-games')
    if not frame.season_type.isin(['REG', 'POST']).all():
        raise ValueError('Unknown season type')
    if not np.isfinite(frame[TARGET].to_numpy(dtype=float)).all():
        raise ValueError('Missing or nonfinite targets; investigate upstream')
    # Negative fantasy scores are valid; infinity and missing scores are not.
    if frame.groupby('game_id')[['season', 'week', 'season_type', 'game_date']].nunique().gt(1).any().any():
        raise ValueError('Inconsistent game metadata')
    feature_frame(frame)


def chronological_split(frame):
    frame = frame.loc[frame.position.isin(['RB', 'WR']) & frame.season_type.eq('REG')].copy()
    if not frame.week.between(1, 18).all() or not frame.season.isin([2023, 2024, 2025]).all():
        raise ValueError('Expected regular-season 2023–2025 weeks 1–18')
    frame['game_date'] = pd.to_datetime(frame.game_date, errors='raise')
    train = frame[frame.season.isin([2023, 2024])]
    validation = frame[(frame.season == 2025) & (frame.week <= 9)]
    test = frame[(frame.season == 2025) & (frame.week >= 10)]
    splits = [train, validation, test]
    if any(part.empty for part in splits):
        raise ValueError('Insufficient data for chronological split')
    if not train.game_date.max() < validation.game_date.min() or not validation.game_date.max() < test.game_date.min():
        raise ValueError('Split dates are not strictly chronological')
    for i, left in enumerate(splits):
        for right in splits[i + 1:]:
            if set(left.game_id) & set(right.game_id):
                raise ValueError('A game crosses split boundaries')
    return splits


def xgb_pipeline(depth=2, trees=150):
    return make_pipeline(SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True),
                         XGBRegressor(n_estimators=trees, max_depth=depth, learning_rate=.03,
                                      min_child_weight=20, subsample=.8, colsample_bytree=.8,
                                      reg_lambda=10, objective='reg:squarederror',
                                      tree_method='hist', random_state=SEED, n_jobs=1))


def run_training(source: Path, models: Path, output: Path):
    if models.resolve() == output.resolve() or source.resolve() in [models.resolve(), output.resolve()]:
        raise ValueError('Source, models, and reports must use separate paths')
    frame = pd.read_parquet(source)
    validate_dataset(frame)
    splits = chronological_split(frame)
    models.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    report = {'version': VERSION, 'seed': SEED, 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'schema': {c: str(t) for c, t in frame.dtypes.items()},
              'missing_values': frame.isna().sum().to_dict(), 'input_rows': len(frame),
              'excluded_postseason_rows': int(frame.season_type.eq('POST').sum()),
              'features': FEATURES, 'target': TARGET, 'positions': {},
              'periods': {'train': '2023–2024 REG', 'validation': '2025 REG weeks 1–9', 'test': '2025 REG weeks 10–18'},
              'packages': {p: importlib.metadata.version(p) for p in ['pandas', 'numpy', 'scikit-learn', 'xgboost', 'joblib', 'matplotlib']}}
    all_predictions, importances = [], []
    for position in ['RB', 'WR']:
        train, validation, test = [part[part.position == position].copy() for part in splits]
        if any(len(part) < 30 for part in [train, validation, test]):
            raise ValueError(f'Insufficient {position} records (need at least 30 per split)')
        x_train, x_val, x_test = [feature_frame(part) for part in [train, validation, test]]
        y_train = train[TARGET]
        ridge = make_pipeline(SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True),
                              StandardScaler(), Ridge(alpha=10))
        ridge.fit(x_train, y_train)
        candidates, best, best_mae = [], None, float('inf')
        for depth, trees in [(2, 150), (2, 300), (3, 150), (3, 300)]:
            model = xgb_pipeline(depth, trees)
            model.fit(x_train, y_train)
            score = metrics(validation[TARGET], model.predict(x_val))
            candidates.append(dict(max_depth=depth, n_estimators=trees, **score))
            if score['mae'] < best_mae:
                best, best_mae = model, score['mae']
        # Freeze the selected training-only fit; validation is not folded back in.
        metadata = {'version': VERSION, 'position': position, 'features': FEATURES,
                    'training_period': report['periods']['train'], 'validation_period': report['periods']['validation'],
                    'seed': SEED, 'source_sha256': report['source_sha256'], 'packages': report['packages'],
                    'hyperparameters': {k: (None if isinstance(v, float) and np.isnan(v) else v)
                                        for k, v in best[-1].get_params().items()}}
        joblib.dump({'model': best, 'metadata': metadata}, models / f'{position}.joblib')
        joblib.dump({'model': ridge, 'metadata': {**metadata, 'model_type': 'ridge', 'hyperparameters': {'alpha': 10}}}, models / f'{position}_ridge.joblib')
        (models / f'{position}_metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
        predicted = best.predict(x_test)
        reloaded = joblib.load(models / f'{position}.joblib')['model'].predict(x_test)
        np.testing.assert_array_equal(predicted, reloaded)
        identity = ['player_id', 'player_name', 'game_id', 'game_date', 'season', 'week', 'team', 'opponent_team', 'position', 'prior_games']
        results = test[identity].reset_index(drop=True)
        results['actual'] = test[TARGET].to_numpy()
        results['xgboost'] = predicted
        results['ridge'] = ridge.predict(x_test)
        fallback = float(y_train.mean())
        for window in [3, 5]:
            results[f'mean_{window}'] = test[f'fantasy_points_ppr_mean_{window}'].fillna(fallback).to_numpy()
        results['error'] = results.xgboost - results.actual
        results['absolute_error'] = results.error.abs()
        all_predictions.append(results)
        names = best[0].get_feature_names_out(FEATURES)
        importances.extend(dict(position=position, feature=str(name), importance=float(value))
                           for name, value in zip(names, best[-1].feature_importances_))
        example = json.loads(x_test.iloc[0].to_json())
        (output / f'{position}_example_features.json').write_text(json.dumps(example, indent=2) + '\n')
        demo = predict_points(models / f'{position}.joblib', example)
        np.testing.assert_allclose(demo['predicted_fantasy_points_ppr'], predicted[0], rtol=0, atol=1e-6)
        report['positions'][position] = {'counts': dict(zip(['train', 'validation', 'test'], map(len, [train, validation, test]))),
                                        'validation_candidates': candidates, 'baseline_cold_start_mean': fallback,
                                        'selected_hyperparameters': metadata['hyperparameters'],
                                        'demo_record': results.iloc[0][identity].astype(str).to_dict(),
                                        'demo_prediction': demo['predicted_fantasy_points_ppr']}
    predictions = pd.concat(all_predictions, ignore_index=True)
    predictions.to_csv(output / 'test_predictions.csv', index=False)
    pd.DataFrame(importances).to_csv(output / 'feature_importance.csv', index=False)
    examples = []
    groups = []
    for position, data in predictions.groupby('position'):
        for label, subset in [('accurate', data.nsmallest(5, 'absolute_error')), ('inaccurate', data.nlargest(5, 'absolute_error'))]:
            examples.append(subset.assign(example_type=label))
        for label, subset in [('limited_<5', data[data.prior_games < 5]), ('extensive_>=5', data[data.prior_games >= 5])]:
            if len(subset):
                groups.append(dict(position=position, history=label, count=len(subset), **metrics(subset.actual, subset.xgboost)))
    pd.concat(examples).to_csv(output / 'prediction_examples.csv', index=False)
    pd.DataFrame(groups).to_csv(output / 'history_metrics.csv', index=False)
    player_errors = predictions.groupby(['position', 'player_id', 'player_name']).agg(
        games=('error', 'size'), bias=('error', 'mean'), mae=('absolute_error', 'mean'))
    player_errors[player_errors.games >= 5].sort_values('bias').to_csv(output / 'player_bias.csv')
    comparison = evaluate(output)
    report['test_metrics'] = comparison.to_dict(orient='records')
    (output / 'training_report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(comparison.to_string(index=False))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'data/processed/player_features_2023_2025.parquet')
    parser.add_argument('--models', type=Path, default=ROOT / 'models/ppr-v1')
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/ml')
    args = parser.parse_args()
    run_training(args.input, args.models, args.output)


if __name__ == '__main__':
    main()
