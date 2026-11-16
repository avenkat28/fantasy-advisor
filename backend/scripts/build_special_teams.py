"""Bootstrap real kicker/DST history, source photos, and a six-position snapshot.

Run before training the expanded models. Downloads can be reused with --cached.
"""
import argparse
from datetime import datetime, timezone
import json

import pandas as pd

from backend.scoring import defense_records
from backend.scripts.build_features import build_features
from backend.scripts.build_player_stats import ROOT, clean_player_stats
from backend.scripts.refresh_current_data import publish_snapshot


def bootstrap(root=ROOT, season=2026, cached=False):
    import nflreadpy as nfl
    folder = root / 'data/raw/special_teams'
    folder.mkdir(parents=True, exist_ok=True)
    teams_path = folder / 'logos.parquet'
    if not cached or not teams_path.exists():
        nfl.load_teams().write_parquet(teams_path)
    teams = pd.read_parquet(teams_path)
    schedule_path = root / 'data/raw/schedules_2023_2025.parquet'
    schedules = pd.read_parquet(schedule_path)
    historical = []
    photos = {}
    for year in range(2023, season + 1):
        sources = {}
        for name, load in [('players', nfl.load_player_stats), ('teams', nfl.load_team_stats)]:
            path = folder / f'{name}_{year}.parquet'
            if not cached or not path.exists():
                load([year], summary_level='week').write_parquet(path)
            sources[name] = pd.read_parquet(path)
        photo_rows = sources['players'].dropna(subset=['headshot_url'])
        photos.update(photo_rows.drop_duplicates('player_id', keep='last').set_index('player_id').headshot_url.to_dict())
        if year < season:
            historical.append(pd.concat([clean_player_stats(sources['players']),
                                         defense_records(sources['teams'], schedules, teams)], ignore_index=True))
        else:
            current = sources
    historical = pd.concat(historical, ignore_index=True)
    training = historical[historical.season.le(2025)]
    features_path = root / 'data/processed/player_features_all_positions_2023_2025.parquet'
    build_features(training, schedules).to_parquet(features_path, index=False)
    (root / 'data/player_headshots.json').write_text(json.dumps(photos, indent=2) + '\n')
    current_schedule = nfl.load_schedules([season]).to_pandas()
    rosters = nfl.load_rosters_weekly([season]).to_pandas()
    try:
        injuries = nfl.load_injuries([season]).to_pandas()
        injury_error = None
    except Exception as error:
        injuries, injury_error = None, f'Injury feed unavailable: {type(error).__name__}'
    manifest = publish_snapshot(root, season, current['players'], current_schedule, rosters,
                               datetime.now(timezone.utc).isoformat(), injuries, injury_error,
                               current['teams'], teams,
                               historical_extra=historical[historical.position.isin(['K', 'DST'])])
    return dict(snapshot=manifest, training_features=str(features_path), photo_count=len(photos))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--season', type=int, default=2026)
    parser.add_argument('--cached', action='store_true')
    args = parser.parse_args()
    print(json.dumps(bootstrap(season=args.season, cached=args.cached), indent=2))


if __name__ == '__main__':
    main()
