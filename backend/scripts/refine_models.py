"""Train refreshed candidates with a chronological, recent-week evaluation.

Artifacts are isolated from production. Reported metrics precede the final refit.
Injury reports are exported for review, never backdated into training features.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import joblib
import pandas as pd

from backend.api.data import DataRepository
from backend.api.tracking import weekly_results
from backend.ml.evaluate import metrics
from backend.ml.schema import FEATURES, feature_frame
from backend.scripts.build_features import TARGET, build_features
from backend.scripts.build_player_stats import ROOT
from backend.scripts.train_models import validate_dataset, xgb_pipeline


def recent_split(frame, season, holdout_weeks=2):
    regular = frame[frame.season_type.eq('REG') & frame.position.isin(['RB', 'WR'])].copy()
    weeks = sorted(regular.loc[regular.season.eq(season), 'week'].unique())
    if holdout_weeks < 1 or len(weeks) <= holdout_weeks:
        raise ValueError('Insufficient current-season weeks for chronological evaluation')
    first = weeks[-holdout_weeks]
    train = regular[(regular.season < season) | (regular.season.eq(season) & regular.week.lt(first))]
    test = regular[regular.season.eq(season) & regular.week.ge(first)]
    if train.empty or test.empty or pd.to_datetime(train.game_date).max() >= pd.to_datetime(test.game_date).min():
        raise ValueError('Training and evaluation dates must be strictly chronological')
    return train, test


def refine(root=ROOT, season=2026, holdout_weeks=2, activate=False):
    data = DataRepository(root)
    data.require_data()
    frame = build_features(data.players, data.schedules)
    validate_dataset(frame)
    train, test = recent_split(frame, season, holdout_weeks)
    version = 'ppr-refined-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    output = root / 'reports' / version
    models = root / 'models' / version
    output.mkdir(parents=True)
    models.mkdir(parents=True)
    latest_week = int(test.week.max())
    results = weekly_results(data, season, latest_week)
    (output / 'weekly_results.json').write_text(json.dumps(results, indent=2, allow_nan=False) + '\n')
    injuries = data.injuries
    if not injuries.empty:
        injuries[injuries.season.eq(season) & injuries.week.eq(latest_week)].to_csv(output / 'weekly_injuries.csv', index=False)
    report = dict(version=version, snapshot=data.snapshot, season=season, latest_week=latest_week,
                  evaluation_weeks=sorted(map(int, test.week.unique())), positions={},
                  injury_policy='Reports exported as observed. No retrospective injury features; existing pregame availability rules remain in use.',
                  evaluation_policy='Recent observed games, including a possibly incomplete week. Fixed hyperparameters; no tuning on evaluation outcomes. Final candidate refit includes evaluation games and requires future prospective monitoring.',
                  production_changed=False)
    predictions = []
    for position in ['RB', 'WR']:
        fit = train[train.position.eq(position)]
        held = test[test.position.eq(position)]
        if min(len(fit), len(held)) < 30:
            raise ValueError(f'Insufficient {position} observations')
        # Frozen benchmark avoids scoring a previously refreshed model on its own training games.
        incumbent = joblib.load(root / 'models/ppr-v1' / f'{position}.joblib')
        if incumbent['metadata']['features'] != FEATURES:
            raise ValueError('Incompatible incumbent features')
        model = xgb_pipeline(depth=2, trees=300)
        model.fit(feature_frame(fit), fit[TARGET])
        x_test = feature_frame(held)
        pred = model.predict(x_test)
        old = incumbent['model'].predict(x_test)
        baseline = held.fantasy_points_ppr_mean_3.fillna(fit[TARGET].mean())
        scores = {name: metrics(held[TARGET], values) for name, values in [('candidate', pred), ('incumbent', old), ('recent_mean_3', baseline)]}
        report['positions'][position] = dict(train_rows=len(fit), evaluation_rows=len(held), metrics=scores,
            improves_mae_and_rmse=all(scores['candidate'][m] < scores['incumbent'][m] for m in ['mae', 'rmse']))
        rows = held[['player_id', 'player_name', 'season', 'week', 'position', 'game_date']].copy()
        rows = rows.assign(actual=held[TARGET], candidate=pred, incumbent=old, recent_mean_3=baseline)
        predictions.append(rows)
        # Fit deployable candidate only after its evaluation predictions are frozen.
        final = frame[frame.position.eq(position) & frame.season_type.eq('REG') & frame.season.le(season)]
        model.fit(feature_frame(final), final[TARGET])
        metadata = dict(version=version, position=position, features=FEATURES,
                        training_period=f'Regular-season observed games through {season} week {latest_week}',
                        source_sha256=hashlib.sha256(data.players_path.read_bytes()).hexdigest(),
                        evaluation_report=str(output.relative_to(root) / 'report.json'))
        joblib.dump(dict(model=model, metadata=metadata), models / f'{position}.joblib')
        report['positions'][position]['final_fit_rows'] = len(final)
    pd.concat(predictions).to_csv(output / 'evaluation_predictions.csv', index=False)
    if activate and all(p['improves_mae_and_rmse'] for p in report['positions'].values()):
        pointer = root / 'models/current.json'
        report['previous_active_model'] = json.loads(pointer.read_text()) if pointer.exists() else None
        temporary = pointer.with_suffix('.tmp')
        temporary.write_text(json.dumps(dict(directory=str(models.relative_to(root)),
                                             report=str((output / 'report.json').relative_to(root)))))
        temporary.replace(pointer)
        report['production_changed'] = True
    (output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps(dict(report=str(output / 'report.json'), models=str(models), **report), indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--season', type=int, default=datetime.now(timezone.utc).year)
    parser.add_argument('--holdout-weeks', type=int, default=2)
    parser.add_argument('--activate', action='store_true', help='Activate when both positions beat frozen ppr-v1 on MAE and RMSE')
    args = parser.parse_args()
    refine(season=args.season, holdout_weeks=args.holdout_weeks, activate=args.activate)


if __name__ == '__main__':
    main()
