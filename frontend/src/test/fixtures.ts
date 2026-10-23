/** Synthetic data is restricted to automated tests. */
import type {
  Comparison,
  Health,
  Performance,
  PlayerDetails,
  PredictionHistory,
  Projection,
  WeeklyProjections,
} from "@/lib/types";
export const player: Projection = {
  player_id: "test-a",
  player_name: "Test Runner",
  position: "RB",
  team: "AAA",
  opponent: "BBB",
  season: 2026,
  week: 7,
  projected_ppr_points: 18.5,
  model_version: "test-v1",
  prediction_type: "pregame",
  prediction_timestamp: "2026-10-23T12:00:00Z",
  data_as_of: "2026-10-23T12:00:00Z",
  feature_cutoff: "2026-10-25T00:00:00Z",
  last_statistical_game: "2026-10-18",
  historical_games: 12,
  missing_features: [],
  recent_ppr_mean_3: 15,
  matchup_features: { opponent_ppr_allowed_position_mean_3: 22 },
  eligibility_source: "weekly_roster",
  roster_week: 7,
  roster_status: "ACT",
  roster_observed_at: "2026-10-23T12:00:00Z",
  snapshot_observed_at: "2026-10-23T12:00:00Z",
  limitations: ["Test limitation"],
};
export const receiver: Projection = {
  ...player,
  player_id: "test-b",
  player_name: "Test Receiver",
  position: "WR",
  projected_ppr_points: 17,
};
export const weekly: WeeklyProjections = {
  projections: [player, receiver],
  unavailable: [],
  total: 2,
  offset: 0,
  limit: 500,
  eligibility: "Test eligibility rule",
};
export const health: Health = {
  status: "ok",
  application: "FantasyAdvisor",
  version: "test",
  models_available: { RB: true, WR: true },
  data_available: true,
  snapshot: {
    season: 2026,
    observed_at: "2026-10-23T12:00:00Z",
    latest_statistical_game: "2026-10-22",
    roster_weeks: { "2026": [1, 7] },
    rows: { players: 2, schedules: 1, rosters: 2 },
  },
};
export const performance: Performance = {
  available: true,
  model_version: "test-v1",
  periods: { train: "Test training period", test: "Test held-out period" },
  metrics: [
    {
      position: "RB",
      model: "xgboost",
      mae: 4.12,
      rmse: 5.14,
      r2: 0.3,
      bias: 0.1,
    },
    {
      position: "WR",
      model: "xgboost",
      mae: 5.01,
      rmse: 6.3,
      r2: 0.2,
      bias: -0.1,
    },
  ],
  message: null,
};
export const comparison: Comparison = {
  player1: player,
  player2: receiver,
  difference: 1.5,
  recommended_player_id: player.player_id,
  close_call: true,
  close_call_threshold: 2,
  explanation: "The backend says this is a close decision.",
};
export const details: PlayerDetails = {
  ...player,
  season: 2026,
  week: 6,
  data_type: "historical_snapshot",
  upcoming_opponent: "BBB",
  historical_averages: { fantasy_points_ppr: 15 },
  recent_games: [
    {
      season: 2026,
      week: 6,
      season_type: "REG",
      team: "AAA",
      fantasy_points_ppr: 16,
      carries: 10,
      targets: 5,
    },
  ],
};
export const history: PredictionHistory = {
  available: true,
  evaluation_type: "held_out_test",
  records: [],
  message: null,
};
