"""Local snapshot repository; no request-time network access."""
import json
import os
from pathlib import Path

import pandas as pd

from backend.scripts.build_features import schedule_context
from backend.scripts.build_player_stats import ROOT


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


class DataRepository:
    def __init__(self, root: Path = ROOT):
        self.root = root
        manifest_path = root / 'data/current.json'
        self.snapshot = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
        # Explicit path overrides opt out of the published snapshot as a unit.
        if os.getenv('FANTASY_PLAYERS') or os.getenv('FANTASY_SCHEDULES'):
            self.snapshot = None
        players_default = root / (self.snapshot['players'] if self.snapshot else 'data/processed/player_weekly_2023_2025.parquet')
        schedules_default = root / (self.snapshot['schedules'] if self.snapshot else 'data/raw/schedules_2023_2025.parquet')
        self.players_path = Path(os.getenv('FANTASY_PLAYERS', str(players_default)))
        self.schedule_path = Path(os.getenv('FANTASY_SCHEDULES', str(schedules_default)))
        roster_path = root / self.snapshot['rosters'] if self.snapshot else None
        self.rosters = pd.read_parquet(roster_path) if roster_path is not None and roster_path.exists() else pd.DataFrame()
        if not self.rosters.empty:
            self.rosters['observed_at'] = pd.to_datetime(self.rosters.observed_at, utc=True)
        self.players = pd.read_parquet(self.players_path) if self.players_path.exists() else pd.DataFrame()
        self.schedules = pd.read_parquet(self.schedule_path) if self.schedule_path.exists() else pd.DataFrame()
        self.context = pd.DataFrame()
        if not self.players.empty and not self.schedules.empty:
            self.players, self.context = schedule_context(self.players, self.schedules)
        self.report_dir = root / 'reports/ml'
        self.report = self.read_json('training_report.json')
        path = self.report_dir / 'test_predictions.csv'
        self.history = pd.read_csv(path) if path.exists() else None

    def read_json(self, name: str) -> dict | None:
        path = self.report_dir / name
        return json.loads(path.read_text()) if path.exists() else None

    def require_data(self):
        if self.players.empty:
            raise APIError(503, 'data_unavailable', 'Local player dataset is unavailable.')

    def roster_season(self, season: int) -> bool:
        return self.snapshot is not None and season in self.snapshot.get('roster_seasons', [])

    def roster_for_week(self, season: int, week: int, cutoff=None) -> pd.DataFrame:
        if self.rosters.empty:
            return self.rosters.copy()
        available = pd.Timestamp.now(tz='UTC')
        if cutoff is not None:
            available = min(available, pd.Timestamp(cutoff).tz_localize('UTC'))
        rows = self.rosters[self.rosters.season.eq(season) & self.rosters.week.eq(week) & self.rosters.observed_at.le(available)]
        # Do not silently carry an old roster snapshot indefinitely.
        rows = rows[rows.observed_at.ge(available - pd.Timedelta(days=7))]
        return rows.sort_values('observed_at').drop_duplicates('player_id', keep='last')

    def candidates(self, season: int, week: int, cutoff) -> pd.DataFrame:
        if self.roster_season(season):
            rows = self.roster_for_week(season, week, cutoff)
            if rows.empty:
                raise APIError(422, 'roster_unavailable', 'No fresh weekly roster observed before this game cutoff. Refresh local data; historical rosters cannot be backdated.')
            return rows[rows.roster_status.eq('ACT')]
        # Historical replay compatibility only; never silently infer new-season rosters.
        if season > 2025:
            raise APIError(422, 'roster_unavailable', 'A published weekly roster snapshot is required for seasons after 2025.')
        prior = self.players[self.players.game_date < cutoff]
        latest = prior.sort_values('game_date').drop_duplicates('player_id', keep='last')
        return latest[latest.season.eq(season) & latest.position.isin(['RB', 'WR'])]

    def records(self, player_id: str) -> pd.DataFrame:
        self.require_data()
        rows = self.players[self.players.player_id.eq(player_id)]
        if rows.empty and (self.rosters.empty or not self.rosters.player_id.eq(player_id).any()):
            raise APIError(404, 'player_not_found', 'Player was not found in the local snapshot.')
        order = ['game_date'] if 'game_date' in rows else ['season', 'week']
        return rows.sort_values(order)

    @staticmethod
    def identity(row) -> dict:
        return {key: str(row[key]) for key in ['player_id', 'player_name', 'position', 'team']}

    def catalog(self) -> pd.DataFrame:
        order = ['game_date'] if 'game_date' in self.players else ['season', 'week']
        latest = self.players.sort_values(order).drop_duplicates('player_id', keep='last')
        if not self.rosters.empty:
            observed = self.rosters[self.rosters.observed_at.le(pd.Timestamp.now(tz='UTC'))]
            observed = observed.sort_values(['season', 'week', 'observed_at']).drop_duplicates('player_id', keep='last')
            latest = pd.concat([latest, observed], ignore_index=True).drop_duplicates('player_id', keep='last')
        return latest

    def search(self, search: str, limit: int) -> list[dict]:
        self.require_data()
        latest = self.catalog()
        latest = latest[latest.position.isin(['RB', 'WR'])]
        names = latest.get('player_display_name', latest.player_name).fillna(latest.player_name)
        mask = names.str.contains(search, case=False, regex=False) | latest.player_name.str.contains(search, case=False, regex=False)
        return [self.identity(row) for _, row in latest[mask].sort_values('player_name').head(limit).iterrows()]

    def details(self, player_id: str) -> dict:
        rows = self.records(player_id)
        last = rows.iloc[-1] if not rows.empty else self.catalog().query('player_id == @player_id').iloc[-1]
        identity = self.catalog()
        identity = identity[identity.player_id.eq(player_id)].iloc[-1]
        if identity.position not in ['RB', 'WR']:
            raise APIError(422, 'unsupported_position', 'Only RB and WR are supported.')
        metrics = [c for c in ['fantasy_points_ppr', 'rushing_yards', 'receiving_yards', 'receptions', 'targets', 'carries'] if c in rows]
        recent = json.loads(rows.tail(5)[['season', 'week', 'season_type', 'team'] + metrics].to_json(orient='records'))
        upcoming = None
        if not self.context.empty:
            future = self.context[(self.context.team == identity.team) & (self.context.game_date > max(rows.game_date.max() if not rows.empty else pd.Timestamp.min, pd.Timestamp.now().normalize()))].sort_values('game_date')
            if not future.empty:
                upcoming = str(future.iloc[0].opponent_team)
        averages = {c: None if pd.isna(rows[c].mean()) else float(rows[c].mean()) for c in metrics}
        return dict(**self.identity(identity), season=int(last.season), week=int(last.week), recent_games=recent,
                    historical_averages=averages, upcoming_opponent=upcoming)
