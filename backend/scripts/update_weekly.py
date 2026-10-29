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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--season', type=int, default=datetime.now(timezone.utc).year)
    parser.add_argument('--deploy', action='store_true', help='Publish refreshed data using the authenticated Vercel CLI')
    args = parser.parse_args()
    manifest = refresh(ROOT, args.season)
    data = DataRepository(ROOT)
    service = PredictionService(data)
    if not all(p in service.models for p in ['RB', 'WR']):
        raise RuntimeError('Both trained models are required to capture forecasts')
    now = pd.Timestamp.now().normalize()
    games = data.context[data.context.season.eq(args.season) & data.context.season_type.eq('REG')
                         & data.context.game_date.ge(now) & data.context.game_date.le(now + pd.Timedelta(days=14))]
    captured = {}
    for week in sorted(games.week.unique()):
        captured[int(week)] = save_forecasts(service, args.season, int(week))
    print(json.dumps(dict(snapshot=manifest, captured=captured), indent=2))
    if args.deploy:
        subprocess.run(['vercel', 'deploy', '--prod', '--yes'], cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
