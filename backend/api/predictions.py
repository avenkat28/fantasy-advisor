"""Pregame inference using the unchanged Task 2/3 feature and model contracts."""
from datetime import datetime, timezone
from functools import lru_cache
import logging
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from backend.api.data import APIError, DataRepository
from backend.ml.schema import FEATURES, feature_frame
from backend.scripts.build_features import build_features

logger = logging.getLogger(__name__)
ELIGIBILITY = 'Published seasons use the requested weekly roster with source status ACT, observed before the game (maximum age 7 days), plus at least one earlier career appearance. Seasons through 2025 without roster snapshots use earlier same-season appearances. Membership does not verify game availability.'


def pregame_features(players: pd.DataFrame, schedules: pd.DataFrame, player_id: str,
                     game: pd.Series) -> tuple[pd.Series, pd.DataFrame]:
    """Remove target-day and future outcomes, then append an unobserved schedule row.

    The placeholder contains identifiers only, never fabricated game statistics.
    Task 2's shifted calculations produce the exact training feature definitions.
    """
    date = pd.Timestamp(game.game_date)
    history = players[players.game_date < date].copy()
    own = history[history.player_id.eq(player_id)].sort_values('game_date')
    if own.empty or not own.season.eq(game.season).any():
        raise APIError(422, 'insufficient_data', 'No earlier appearance in the requested season; roster membership cannot be established.')
    last = own.iloc[-1]
    result = pregame_rows(players, schedules, pd.DataFrame([game]), date)
    row = result[result.player_id.eq(player_id) & result.game_id.eq(game.game_id)].iloc[0]
    return row, own


def pregame_rows(players: pd.DataFrame, schedules: pd.DataFrame, games: pd.DataFrame,
                 date: pd.Timestamp, candidates: pd.DataFrame | None = None) -> pd.DataFrame:
    """Batch all eligible player placeholders on one date; calculate history once."""
    history = players[players.game_date < date].copy()
    latest = history.sort_values('game_date').drop_duplicates('player_id', keep='last')
    if candidates is not None:
        latest = candidates[candidates.player_id.isin(latest.player_id)].copy()
    placeholders = []
    for _, game in games.iterrows():
        eligible = latest[latest.team.eq(game.team) & latest.position.isin(['RB', 'WR'])]
        if candidates is None:
            eligible = eligible[eligible.season.eq(game.season)]
        for _, last in eligible.iterrows():
            placeholder = {c: np.nan for c in players.columns}
            for c in ['player_id', 'player_name', 'player_display_name', 'position']:
                if c in players:
                    placeholder[c] = last.get(c, last.player_name)
            placeholder.update(team=game.team, season=game.season, week=game.week,
                               season_type=game.season_type, game_id=game.game_id,
                               opponent_team=game.opponent_team)
            placeholders.append(placeholder)
    raw = pd.concat([history, pd.DataFrame(placeholders)], ignore_index=True).drop(columns=['game_date', 'is_home'], errors='ignore')
    safe_schedule = schedules[pd.to_datetime(schedules.gameday) <= date]
    result = build_features(raw, safe_schedule)
    return result[result.game_date.eq(date)]



class PredictionService:
    def __init__(self, repository: DataRepository, model_dir: Path | None = None):
        self.data = repository
        directory = model_dir or Path(os.getenv('FANTASY_MODELS', str(repository.root / 'models/ppr-v1')))
        self.models = {}
        for position in ['RB', 'WR']:
            path = directory / f'{position}.joblib'
            if path.exists():
                try:
                    bundle = joblib.load(path)
                    if bundle['metadata']['features'] != FEATURES or bundle['metadata']['position'] != position:
                        raise ValueError('Incompatible artifact')
                    if not callable(getattr(bundle['model'], 'predict', None)):
                        raise ValueError('Invalid model')
                    self.models[position] = bundle
                except Exception:
                    logger.exception('Could not load %s model', position)

    def schedule(self, season: int, week: int) -> pd.DataFrame:
        if self.data.context.empty:
            raise APIError(404, 'schedule_not_found', 'Local schedule data is unavailable.')
        games = self.data.context[(self.data.context.season == season) & (self.data.context.week == week) & self.data.context.season_type.eq('REG')]
        if games.empty:
            raise APIError(404, 'schedule_not_found', 'No regular-season schedule found for this season/week in the local snapshot.')
        return games

    @lru_cache(maxsize=32)
    def day_features(self, season: int, week: int, date: str) -> pd.DataFrame:
        games = self.schedule(season, week)
        cutoff = pd.Timestamp(date)
        return pregame_rows(self.data.players, self.data.schedules, games[games.game_date.eq(cutoff)], cutoff,
                            self.data.candidates(season, week, cutoff))

    def project(self, player_id: str, season: int, week: int) -> dict:
        records = self.data.records(player_id)
        games = self.schedule(season, week)
        roster_based = self.data.roster_season(season)
        if roster_based:
            # Resolve the team from the weekly snapshot, then enforce its actual game's cutoff.
            roster = self.data.roster_for_week(season, week, games.game_date.max())
            selected = roster[roster.player_id.eq(player_id)] if not roster.empty else roster
            if selected.empty:
                raise APIError(422, 'roster_unavailable', 'Player has no fresh observed roster record for the requested week.')
            last = selected.iloc[-1]
        else:
            candidates = self.data.candidates(season, week, games.game_date.min())
            selected = candidates[candidates.player_id.eq(player_id)]
            if selected.empty:
                raise APIError(422, 'insufficient_data', 'No earlier appearance in the requested season; roster membership cannot be established.')
            last = selected.iloc[-1]
        position = last.position
        if position not in ['RB', 'WR']:
            raise APIError(422, 'unsupported_position', 'Only RB and WR are supported.')
        if position not in self.models:
            raise APIError(503, 'model_unavailable', f'The trained {position} model is unavailable or incompatible.')
        # Existing ppr-v1 fits 2023/24. Earlier retrospective predictions would use a future-trained model.
        if season < 2025:
            raise APIError(422, 'training_period', 'ppr-v1 pregame inference is supported for seasons 2025 onward.')
        matchup = games[games.team.eq(last.team)]
        if matchup.empty:
            raise APIError(404, 'matchup_not_found', 'No scheduled matchup for the most recently observed team (possibly a bye).')
        game = matchup.iloc[0]
        if roster_based:
            known = self.data.roster_for_week(season, week, game.game_date)
            known = known[known.player_id.eq(player_id)] if not known.empty else known
            if known.empty:
                raise APIError(422, 'roster_unavailable', 'Weekly roster was not observed before this game cutoff.')
            last = known.iloc[-1]
            if last.team != game.team:
                raise APIError(422, 'roster_unavailable', 'Roster membership changed after the game cutoff.')
        if roster_based and last.roster_status != 'ACT':
            raise APIError(422, 'roster_not_eligible', 'Weekly roster source status is not ACT; this API does not infer game availability.')
        if records.empty or records[records.game_date < game.game_date].empty:
            raise APIError(422, 'insufficient_data', 'No earlier career game statistics; rookie/cold-start projections are not supported.')
        rows = self.day_features(season, week, str(game.game_date))
        selected = rows[rows.player_id.eq(player_id) & rows.game_id.eq(game.game_id)]
        if selected.empty:
            raise APIError(422, 'insufficient_data', 'No unambiguous pregame feature row is available.')
        row = selected.iloc[0]
        own = records[records.game_date < game.game_date]
        inputs = feature_frame(pd.DataFrame([row[FEATURES].to_dict()], dtype=float), strict=True)
        bundle = self.models[position]
        value = float(bundle['model'].predict(inputs)[0])
        if not np.isfinite(value):
            raise ValueError('Nonfinite model prediction')
        as_of = pd.Timestamp(game.game_date).isoformat() + 'Z'
        feature_cutoff = as_of
        if self.data.snapshot:
            as_of = min(pd.Timestamp(as_of), pd.Timestamp(self.data.snapshot['observed_at'])).isoformat()
        last_date = pd.Timestamp(own.game_date.max()).date().isoformat()
        limits = ['No calibrated uncertainty intervals are available.',
                  'No verified injury or game-availability feed; roster membership does not establish availability.',
                  'ppr-v1 trained on 2023–2024; validation selected on 2025 weeks 1–9.',
                  'Same-day statistics excluded; feature_cutoff is the game-date boundary. Source snapshots may contain later corrections.']
        if roster_based:
            limits.append('Weekly roster membership is observed, not a verified transaction effective timestamp.')
        else:
            limits.append('Historical replay: team inferred from latest earlier same-season appearance.')
        if (game.game_date - own.game_date.max()).days > 28:
            limits.append('Player statistics are more than 28 days old.')
        return dict(**self.data.identity(last), season=season, week=week, opponent=str(game.opponent_team),
                    projected_ppr_points=value, model_version=bundle['metadata']['version'], prediction_type='pregame',
                    prediction_timestamp=datetime.now(timezone.utc).isoformat(), data_as_of=as_of, feature_cutoff=feature_cutoff,
                    last_statistical_game=last_date, historical_games=int(row.prior_games),
                    missing_features=inputs.columns[inputs.isna().iloc[0]].tolist(),
                    recent_ppr_mean_3=None if pd.isna(row.fantasy_points_ppr_mean_3) else float(row.fantasy_points_ppr_mean_3),
                    matchup_features={c: None if pd.isna(row[c]) else float(row[c]) for c in FEATURES if c.startswith('opponent_')},
                    eligibility_source='weekly_roster' if roster_based else 'historical_appearance',
                    roster_week=int(last.week) if roster_based else None,
                    roster_status=str(last.roster_status) if roster_based else None,
                    roster_observed_at=last.observed_at.isoformat() if roster_based else None,
                    snapshot_observed_at=self.data.snapshot.get('observed_at') if self.data.snapshot else None,
                    limitations=limits)

    def weekly(self, season: int, week: int, position: str | None) -> tuple[list, list]:
        games = self.schedule(season, week)
        if self.data.roster_season(season):
            latest = self.data.roster_for_week(season, week, games.game_date.max())
            if latest.empty:
                raise APIError(422, 'roster_unavailable', 'No fresh weekly roster for this week. Refresh local data when the source publishes it.')
        else:
            latest = self.data.candidates(season, week, games.game_date.min())
        latest = latest[latest.position.isin([position] if position else ['RB', 'WR'])]
        predictions, unavailable = [], []
        for player_id in latest.player_id:
            try:
                predictions.append(self.project(str(player_id), season, week))
            except APIError as error:
                unavailable.append(dict(player_id=player_id, code=error.code, message=error.message))
        predictions.sort(key=lambda p: p['projected_ppr_points'], reverse=True)
        return predictions, unavailable
