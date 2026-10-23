"""Public API contracts. Historical observations are distinct from projections."""
from typing import Any, Literal
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class Health(BaseModel):
    status: str
    application: str = 'FantasyAdvisor'
    version: str = '0.4.0'
    models_available: dict[str, bool]
    data_available: bool
    snapshot: dict[str, Any] | None = None


class Player(BaseModel):
    player_id: str
    player_name: str
    position: str
    team: str


class PlayerDetails(Player):
    season: int
    week: int
    recent_games: list[dict[str, Any]]
    historical_averages: dict[str, float | None]
    upcoming_opponent: str | None
    data_type: str = 'historical_snapshot'


class Projection(Player):
    season: int
    week: int
    opponent: str
    projected_ppr_points: float
    model_version: str
    prediction_type: Literal['pregame'] = 'pregame'
    prediction_timestamp: str
    data_as_of: str
    feature_cutoff: str | None = None
    last_statistical_game: str
    historical_games: int
    missing_features: list[str]
    recent_ppr_mean_3: float | None
    matchup_features: dict[str, float | None]
    eligibility_source: str = 'historical_appearance'
    roster_week: int | None = None
    roster_status: str | None = None
    roster_observed_at: str | None = None
    snapshot_observed_at: str | None = None
    limitations: list[str]


class Unavailable(BaseModel):
    player_id: str
    code: str
    message: str


class WeeklyProjections(BaseModel):
    projections: list[Projection]
    unavailable: list[Unavailable]
    total: int
    offset: int
    limit: int
    eligibility: str


class Comparison(BaseModel):
    player1: Projection
    player2: Projection
    difference: float
    recommended_player_id: str | None
    close_call: bool
    close_call_threshold: float
    explanation: str


class Performance(BaseModel):
    available: bool
    model_version: str | None = None
    periods: dict[str, str] = {}
    metrics: list[dict[str, Any]] = []
    message: str | None = None


class HistoryRecord(BaseModel):
    player_id: str
    player_name: str
    season: int
    week: int
    predicted_ppr_points: float
    actual_ppr_points: float
    absolute_error: float


class PredictionHistory(BaseModel):
    available: bool
    evaluation_type: str = 'held_out_test'
    records: list[HistoryRecord]
    message: str | None = None
