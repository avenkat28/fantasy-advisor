"""Scheduled refresh, pregame forecast capture, and optional Vercel publication."""
import argparse
from datetime import datetime, timezone
import json
import subprocess

import pandas as pd

from backend.scripts.build_player_stats import ROOT
from backend.scripts.refresh_current_data import refresh
from backend.api.data import DataRepository
from backend.api.predictions import PredictionService
from backend.api.tracking import save_forecasts
from backend.scripts.refine_models import refine


def latest_complete_week(data, season):
    games = data.schedules[data.schedules.season.eq(season) & data.schedules.game_type.eq('REG')]
    observed = data.players[data.players.season.eq(season) & data.players.position.isin(['QB', 'RB', 'WR', 'TE'])]
    observed = observed[observed.fantasy_points_ppr.notna()]
    coverage = set(zip(observed.game_id, observed.team))
    latest = None
    for week, schedule in games.groupby('week', sort=True):
        if schedule[['home_score', 'away_score']].isna().any().any():
            break
        if any((game.game_id, team) not in coverage for game in schedule.itertuples()
               for team in (game.home_team, game.away_team)):
            break
        latest = int(week)
    return latest


def train_completed_week(data, season):
    week = latest_complete_week(data, season)
    if week is None:
        return None
    checkpoint = ROOT / 'reports' / f'weekly-training-{season}.json'
    if checkpoint.exists() and json.loads(checkpoint.read_text())['week'] >= week:
        return None
    report = refine(ROOT, season, holdout_weeks=min(week, 2), activate=True, through_week=week)
    pending = checkpoint.with_suffix('.tmp')
    pending.write_text(json.dumps(dict(week=week, version=report['version'],
                                      production_changed=report['production_changed'])) + '\n')
    pending.replace(checkpoint)
    return report['version']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    now_utc = datetime.now(timezone.utc)
    parser.add_argument('--season', type=int, default=now_utc.year - (now_utc.month <= 2))
    parser.add_argument('--deploy', action='store_true', help='Publish refreshed data using the authenticated Vercel CLI')
    parser.add_argument('--skip-refinement', action='store_true', help='Refresh data and forecasts without retraining')
    args = parser.parse_args()
    manifest = refresh(ROOT, args.season)
    data = DataRepository(ROOT)
    trained = None if args.skip_refinement else train_completed_week(data, args.season)
    service = PredictionService(data)
    if not all(p in service.models for p in ['QB', 'RB', 'WR', 'TE', 'K', 'DST']):
        raise RuntimeError('All six trained models are required to capture forecasts')
    now = pd.Timestamp.now().normalize()
    games = data.context[data.context.season.eq(args.season) & data.context.season_type.eq('REG')
                         & data.context.game_date.ge(now) & data.context.game_date.le(now + pd.Timedelta(days=14))]
    captured = {}
    for week in sorted(games.week.unique()):
        captured[int(week)] = save_forecasts(service, args.season, int(week))
    print(json.dumps(dict(snapshot=manifest, trained=trained, captured=captured), indent=2))
    if args.deploy:
        subprocess.run(['vercel', 'deploy', '--prod', '--yes'], cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
