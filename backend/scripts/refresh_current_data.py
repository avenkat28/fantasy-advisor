"""Publish a validated local stats/schedule/weekly-roster snapshot atomically.

Run explicitly, outside API requests. Failed downloads never replace working data.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

import pandas as pd

from backend.scripts.build_features import schedule_context
from backend.scripts.build_player_stats import ROOT, clean_player_stats


ROSTER_COLUMNS = ['player_id', 'player_name', 'position', 'team', 'season', 'week', 'roster_status', 'observed_at']


def normalize_rosters(raw: pd.DataFrame, observed_at: str) -> pd.DataFrame:
    """Weekly labels are effective weeks, not proof of pregame publication.

    observed_at is our first observation; never backdate it to the effective week.
    Only the source roster status code is retained; no injury labels are inferred.
    """
    required = {'gsis_id', 'full_name', 'position', 'team', 'season', 'week', 'status'}
    if required - set(raw):
        raise ValueError(f'Missing weekly-roster columns: {sorted(required - set(raw))}')
    if 'game_type' in raw:
        raw = raw[raw.game_type.eq('REG')]
    roster = raw.rename(columns={'gsis_id': 'player_id', 'full_name': 'player_name', 'status': 'roster_status'}).copy()
    roster = roster[roster.position.isin(['QB', 'RB', 'WR', 'TE', 'K', 'DST']) & roster.player_id.notna()]
    roster['observed_at'] = observed_at
    # Photos are optional and must never block a valid statistics refresh.
    if 'headshot_url' not in roster:
        roster['headshot_url'] = None
    roster = roster[ROSTER_COLUMNS + ['headshot_url']].drop_duplicates()
    if roster.empty or roster[ROSTER_COLUMNS].isna().any().any():
        raise ValueError('Empty or incomplete supported weekly roster')
    if roster.duplicated(['player_id', 'season', 'week']).any():
        raise ValueError('Ambiguous player/team membership in weekly roster')
    if not roster.week.between(1, 18).all():
        raise ValueError('Expected regular-season weekly roster weeks 1–18')
    return roster


def publish_snapshot(root: Path, season: int, raw_stats: pd.DataFrame,
                     schedules: pd.DataFrame, raw_rosters: pd.DataFrame,
                     observed_at: str, injuries: pd.DataFrame | None = None, injury_error: str | None = None,
                     team_stats: pd.DataFrame | None = None, teams: pd.DataFrame | None = None,
                     historical_extra: pd.DataFrame | None = None) -> dict:
    if schedules.empty or not schedules.season.eq(season).any():
        raise ValueError(f'Source has no {season} schedule')
    stats = clean_player_stats(raw_stats)
    if team_stats is not None:
        from backend.scoring import defense_records
        stats = pd.concat([stats, defense_records(team_stats, schedules, teams)], ignore_index=True)
    stats = stats[stats.season.eq(season)]
    if stats.empty:
        raise ValueError(f'Source has no {season} player statistics')
    if stats.fantasy_points_ppr.isna().any():
        raise ValueError('Current source statistics have unknown scoring components')
    roster = normalize_rosters(raw_rosters, observed_at)
    roster = roster[roster.season.eq(season)]
    if roster.empty:
        raise ValueError(f'Source has no {season} supported weekly roster')
    # Preserve Tasks 1–3 artifacts, but replace the refreshed season as a unit.
    manifest_path = root / 'data/current.json'
    historical = root / 'data/processed/player_weekly_2023_2025.parquet'
    schedule_path = root / 'data/raw/schedules_2023_2025.parquet'
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
    if previous:
        historical = root / previous['players']
        schedule_path = root / previous['schedules']
    old = pd.read_parquet(historical)
    if historical_extra is not None:
        old = pd.concat([old[~old.position.isin(['K', 'DST'])], historical_extra], ignore_index=True)
    old_schedules = pd.read_parquet(schedule_path)
    combined = pd.concat([old[old.season.ne(season)], stats], ignore_index=True)
    schedules = pd.concat([old_schedules[old_schedules.season.ne(season)], schedules[schedules.season.eq(season)]], ignore_index=True)
    attached, context = schedule_context(combined, schedules)
    cutoff = pd.Timestamp(observed_at).tz_convert('America/New_York').tz_localize(None).normalize()
    current = attached.season.eq(season)
    if attached.loc[current, 'game_date'].gt(cutoff).any():
        raise ValueError('Statistics include target-day/future games; refusing snapshot')
    # Same-day statistical feeds can arrive before the schedule marks the game final.
    # Hold those rows until both final scores are present.
    if {'home_score', 'away_score'} <= set(schedules):
        final_games = schedules.dropna(subset=['home_score', 'away_score']).game_id
        pending = current & attached.game_date.eq(cutoff) & ~attached.game_id.isin(final_games)
    else:
        pending = current & attached.game_date.eq(cutoff)
    combined = combined.loc[~pending.to_numpy()]
    attached = attached.loc[~pending]
    # Rosters can include bye teams: validate team against the season, not against each week's games.
    if not set(roster.team) <= set(context.loc[context.season.eq(season), 'team']):
        raise ValueError('Roster teams do not match the schedule')
    folder = root / 'data/snapshots' / uuid4().hex
    folder.mkdir(parents=True)
    combined.to_parquet(folder / 'players.parquet', index=False)
    schedules.to_parquet(folder / 'schedules.parquet', index=False)
    roster.to_parquet(folder / 'rosters.parquet', index=False)
    roster_seasons = sorted(roster.season.unique().tolist())
    # Retain earlier observed weekly snapshots to support genuine point-in-time use.
    if previous and previous.get('rosters'):
        prior_roster = pd.read_parquet(root / previous['rosters'])
        roster = pd.concat([prior_roster, roster], ignore_index=True).drop_duplicates()
        roster.to_parquet(folder / 'rosters.parquet', index=False)
        roster_seasons = sorted(roster.season.unique().tolist())
    injury_path = None
    if injuries is not None and not injuries.empty:
        required = {'gsis_id', 'season', 'week', 'report_status'}
        if required - set(injuries):
            raise ValueError('Injury source is missing required columns')
        injuries = injuries[injuries.season.eq(season)].copy()
        injuries['observed_at'] = observed_at
        if previous and previous.get('injuries'):
            injuries = pd.concat([pd.read_parquet(root / previous['injuries']), injuries], ignore_index=True).drop_duplicates()
        injuries.to_parquet(folder / 'injuries.parquet', index=False)
        injury_path = str((folder / 'injuries.parquet').relative_to(root))
    manifest = dict(injuries=injury_path, injury_error=injury_error, version=1, season=season, observed_at=observed_at,
                    players=str((folder / 'players.parquet').relative_to(root)),
                    schedules=str((folder / 'schedules.parquet').relative_to(root)),
                    rosters=str((folder / 'rosters.parquet').relative_to(root)),
                    roster_seasons=roster_seasons,
                    sources=['nflreadpy.load_player_stats', 'nflreadpy.load_schedules', 'nflreadpy.load_rosters_weekly'] + (['nflreadpy.load_injuries'] if injury_path else []),
                    latest_statistical_game=attached.game_date.max().date().isoformat(),
                    rows=dict(players=len(combined), schedules=len(schedules), rosters=len(roster)))
    if team_stats is not None:
        from backend.scoring import SCORING_POLICY
        manifest['scoring_policy'] = SCORING_POLICY
        manifest['sources'] += ['nflreadpy.load_team_stats', 'nflreadpy.load_teams']
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    temporary = manifest_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(manifest, indent=2) + '\n')
    temporary.replace(manifest_path)
    return manifest


def refresh(root: Path, season: int, loader=None) -> dict:
    if loader is None:
        import nflreadpy as loader
    # Capture observation after download, so data cannot be claimed to have been known sooner.
    stats = loader.load_player_stats([season], summary_level='week').to_pandas()
    schedules = loader.load_schedules([season]).to_pandas()
    rosters = loader.load_rosters_weekly([season]).to_pandas()
    injuries, injury_error = None, None
    try:
        injuries = loader.load_injuries([season]).to_pandas()
        if injuries.empty:
            injury_error = 'No injury reports published for this season.'
    except Exception as error:
        injury_error = f'Injury feed unavailable: {type(error).__name__}'
    team_stats = loader.load_team_stats([season], summary_level='week').to_pandas() if hasattr(loader, 'load_team_stats') else None
    teams = loader.load_teams().to_pandas() if hasattr(loader, 'load_teams') else None
    observed = datetime.now(timezone.utc).isoformat()
    return publish_snapshot(root, season, stats, schedules, rosters, observed, injuries, injury_error, team_stats, teams)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--season', type=int, default=datetime.now(timezone.utc).year)
    args = parser.parse_args()
    if not 2025 <= args.season <= 2100:
        parser.error('Season must be between 2025 and 2100')
    try:
        result = refresh(ROOT, args.season)
    except Exception as error:
        parser.exit(1, f'Refresh failed; existing snapshot retained: {error}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
