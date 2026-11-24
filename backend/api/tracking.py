"""Persist pregame forecasts and score only forecasts captured before kickoff day."""
import json

import pandas as pd


def archive_path(root, season, week):
    return root / 'data/forecasts' / str(season) / f'{week}.json'


def load_forecasts(root, season, week):
    path = archive_path(root, season, week)
    return json.loads(path.read_text()) if path.exists() else []


def save_forecasts(service, season, week):
    path = archive_path(service.data.root, season, week)
    existing = load_forecasts(service.data.root, season, week)
    predictions, _ = service.weekly(season, week, None)
    now = pd.Timestamp.now(tz='UTC')
    # Keep completed games immutable; update only games that have not started.
    future = [p for p in predictions if pd.Timestamp(p.get('game_kickoff', p['feature_cutoff'])) > now]
    ids = {p['player_id'] for p in future}
    rows = [p for p in existing if p['player_id'] not in ids] + future
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(rows, indent=2))
    temp.replace(path)
    return len(future)


def weekly_results(data, season, week, current=None):
    saved = load_forecasts(data.root, season, week)
    actuals = pd.DataFrame(columns=['fantasy_points_ppr', 'position', 'player_name'])
    if not data.players.empty:
        players = data.players
        actuals = players[players.season.eq(season) & players.week.eq(week) & players.season_type.eq('REG')
                          & players.fantasy_points_ppr.notna()].set_index('player_id')
    rows = []
    for p in saved:
        actual = float(actuals.loc[p['player_id'], 'fantasy_points_ppr']) if p['player_id'] in actuals.index else None
        pred = p['projected_ppr_points']
        baseline = p.get('recent_ppr_mean_3')
        rows.append(dict(player_id=p['player_id'], player_name=p['player_name'], position=p['position'],
                         projected=pred, actual=actual, baseline=baseline,
                         error=None if actual is None else pred - actual,
                         captured_at=p['prediction_timestamp']))
    saved_ids = {r['player_id'] for r in rows}
    for player_id, row in actuals.iterrows():
        if player_id not in saved_ids and row.position in ['QB', 'RB', 'WR', 'TE', 'K', 'DST']:
            rows.append(dict(player_id=player_id, player_name=row.player_name, position=row.position,
                             projected=None, actual=float(row.fantasy_points_ppr), baseline=None, error=None, captured_at=None))
    scored = [r for r in rows if r['actual'] is not None and r['projected'] is not None]
    metrics = []
    for name, field in [('Model', 'projected'), ('Recent 3-game average', 'baseline')]:
        pairs = [r for r in scored if r['baseline'] is not None]
        if pairs:
            errors = [r[field] - r['actual'] for r in pairs]
            metrics.append(dict(model=name, count=len(errors), mae=sum(abs(e) for e in errors)/len(errors),
                                rmse=(sum(e*e for e in errors)/len(errors))**.5, bias=sum(errors)/len(errors)))
    if current is not None:
        by_id = {row['player_id']: row for row in rows}
        for prediction in current:
            player_id = prediction['player_id']
            if player_id not in by_id:
                row = dict(player_id=player_id, player_name=prediction['player_name'], position=prediction['position'],
                           projected=None, actual=None, baseline=None, error=None, captured_at=None)
                rows.append(row)
                by_id[player_id] = row
            by_id[player_id]['current_projection'] = prediction['projected_ppr_points']
    return dict(season=season, week=week, records=rows, metrics=metrics,
                message='Only forecasts saved before the game are scored. Missing actuals remain pending; no forecast is backfilled.')
