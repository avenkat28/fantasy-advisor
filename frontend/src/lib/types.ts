/** Mirrors backend/api/schemas.py. Null means unavailable, never zero. */
export interface Player {
  player_id: string;
  player_name: string;
  position: string;
  team: string;
}
export interface Snapshot {
  season: number;
  observed_at: string;
  latest_statistical_game: string;
  roster_weeks?: Record<string, number[]>;
  rows: { players: number; schedules: number; rosters: number };
}
export interface Health {
  status: string;
  application: string;
  version: string;
  models_available: Record<string, boolean>;
  data_available: boolean;
  snapshot: Snapshot | null;
}
export interface HistoricalGame {
  season: number;
  week: number;
  season_type: string;
  team: string;
  fantasy_points_ppr?: number | null;
  rushing_yards?: number | null;
  receiving_yards?: number | null;
  receptions?: number | null;
  targets?: number | null;
  carries?: number | null;
}
export interface PlayerDetails extends Player {
  season: number;
  week: number;
  recent_games: HistoricalGame[];
  historical_averages: Record<string, number | null>;
  upcoming_opponent: string | null;
  data_type: string;
}
export interface Projection extends Player {
  season: number;
  week: number;
  opponent: string;
  injury_status?: string | null;
  injury_adjustment?: string | null;
  base_projected_ppr_points?: number | null;
  projected_ppr_points: number;
  model_version: string;
  prediction_type: "pregame";
  prediction_timestamp: string;
  data_as_of: string;
  feature_cutoff: string | null;
  last_statistical_game: string;
  historical_games: number;
  missing_features: string[];
  recent_ppr_mean_3: number | null;
  matchup_features: Record<string, number | null>;
  eligibility_source: string;
  roster_week: number | null;
  roster_status: string | null;
  roster_observed_at: string | null;
  snapshot_observed_at: string | null;
  limitations: string[];
}
export interface Unavailable {
  player_id: string;
  code: string;
  message: string;
}
export interface WeeklyProjections {
  projections: Projection[];
  unavailable: Unavailable[];
  total: number;
  offset: number;
  limit: number;
  eligibility: string;
}
export interface Comparison {
  player1: Projection;
  player2: Projection;
  difference: number;
  recommended_player_id: string | null;
  close_call: boolean;
  close_call_threshold: number;
  explanation: string;
}
export interface Metric {
  position: string;
  model: string;
  mae: number;
  rmse: number;
  r2: number | null;
  bias: number;
}
export interface Performance {
  available: boolean;
  model_version: string | null;
  periods: Record<string, string>;
  metrics: Metric[];
  message: string | null;
}
export interface HistoryRecord {
  player_id: string;
  player_name: string;
  season: number;
  week: number;
  predicted_ppr_points: number;
  actual_ppr_points: number;
  absolute_error: number;
}
export interface PredictionHistory {
  available: boolean;
  evaluation_type: string;
  records: HistoryRecord[];
  message: string | null;
}
export interface Selection {
  season: number;
  week: number;
}

export interface WeeklyResults {
  season: number; week: number; message: string;
  metrics: {model: string; count: number; mae: number; rmse: number; bias: number}[];
  records: {player_id: string; player_name: string; position: string; projected: number | null; actual: number | null; baseline: number | null; error: number | null; captured_at: string | null}[];
}
