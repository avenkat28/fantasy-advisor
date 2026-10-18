# Historical features and defensive matchups

Task 2 builds features without training a model or changing Task 1. Run from the repository root:

```bash
source .venv312/bin/activate
# Only needed if the cleaned Task 1 file does not exist:
python -m backend.scripts.build_player_stats
python -m backend.scripts.build_features
python -m pytest backend/tests -q
```

The feature command accepts `--input`, `--output`, `--report`, and `--schedules` paths. All four must differ. It reads the existing cleaned Parquet, reuses its player IDs and PPR calculation, and reads a cached schedule snapshot. If the schedule path is absent, it calls `nflreadpy.load_schedules` for the input seasons and saves that snapshot; this requires internet access. Remove or change the snapshot path explicitly to refresh it. Player statistics are never downloaded again by this command.

## Output and input inspection

The October 18, 2026 run inspected 18,533 rows and 37 columns in `data/processed/player_weekly_2023_2025.parquet`, with no missing source values. The cached nflverse schedules contain 855 games across 2023–2025, including postseason. Team abbreviations matched exactly; no alias rewriting was necessary.

Outputs (ignored by Git):

- `data/processed/player_features_2023_2025.parquet`: 18,533 rows × 45 columns, one row per observed player/game.
- `data/processed/feature_report.json`: input dtypes and missing counts, output dimensions and missing counts, explicit identifier/input/target column lists, and available touchdown components.
- `data/raw/schedules_2023_2025.parquet`: reproducible local schedule snapshot.

The output contains 39 candidate input columns, five metadata columns (`player_id`, `player_name`, `player_display_name`, `game_id`, `game_date`), and the target `target_fantasy_points_ppr`. Position/team/season/week are retained as categorical/context inputs. Use the report's `feature_columns` to select inputs; never select every numeric output column, which would include the target. Raw current-game production and both source fantasy totals are excluded entirely.

## Player history

Rows are sorted by player ID, actual game date, and game ID. Within each player, `shift(1)` precedes `rolling()` so the current outcome cannot enter its own features.

| Columns | Definition |
| --- | --- |
| `fantasy_points_ppr_mean_3/5/10` | Mean PPR in the previous 3, 5, or 10 observed appearances. |
| `passing_yards_mean_3/5`, `rushing_yards_mean_3/5`, `receiving_yards_mean_3/5` | Mean prior production in yards. |
| `receptions_mean_3/5`, `targets_mean_3/5`, `carries_mean_3/5` | Mean prior usage. Optional metrics are omitted if absent from the input schema. |
| `touchdowns_mean_3/5` | Mean sum of available passing, rushing, receiving, and special-teams TD components. No aggregate TD field is added again. Passing and receiving TDs count separately for their respective players; this is a player production count, not a team scoring total. Missing components are listed in the report. |
| `fantasy_points_ppr_std_5` | Sample standard deviation (`ddof=1`) in the previous 5 appearances; requires two known observations. |
| `previous_fantasy_points_ppr`, `previous_targets`, `previous_receptions` | Exactly the preceding observed appearance, including its missing value if unknown. |
| `targets_trend_3_vs_5` | Three-game target mean minus five-game target mean. |
| `prior_games` | Count of preceding appearances in this dataset, including appearances with an unknown metric. |
| `days_since_previous_game` | Calendar-day gap between observed appearances. |
| `changed_team` | Whether team differs from the previous appearance; unknown for first appearances. |

Means require at least one known observation and use only the last N appearances; nulls within that window are ignored, never converted to zero. An entirely unknown window remains null. Histories continue across seasons, postseason, team changes, and position changes using stable player IDs. Missing weeks and byes do not create player appearances. Offseason gaps remain visible in days-since-previous-game. First appearances have unknown history, not zero production. History is limited to 2023 onward, so a veteran's first row is not necessarily their NFL debut. Window lengths describe appearances, not calendar weeks or a guarantee of N non-null values.

## Opponent history and context

Schedules provide opponent, home/away (`is_home`), game ID, and date. Existing opponent/game IDs must agree with the schedule. Required identifiers, duplicate player-weeks, ambiguous schedule joins, unknown game types, and unmatched teams fail explicitly rather than multiplying or dropping rows. No weather, odds, or injuries are added.

`defensive_features()` first sums PPR across all offensive players of each position against a defense in a game. Thus two WRs scoring 10 and 2 count as 12 allowed to WR, not an average of 6. A defense/game/position grid includes every scheduled game even if no player of that position was observed. Missing or partially unknown totals remain unknown; they are not interpreted as zero.

After sorting by date, the grid shifts within defense/position before rolling, producing `opponent_ppr_allowed_position_mean_3/5`. These are the defense's previous scheduled games, not the player's appearances. `opponent_prior_games` counts preceding scheduled games. Passing and rushing yards are separately summed across retained positions at defense/game level, then shifted and rolled into `opponent_passing_yards_allowed_mean_3/5` and `opponent_rushing_yards_allowed_mean_3/5`. These are gross player yards, not net passing yards after sacks. Non-QB/RB/WR/TE trick-play yardage is unavailable in Task 1 and excluded; these features are not guaranteed to equal official team defensive yardage.

No current game's PPR or yardage enters its own defensive features. Null totals occupy their schedule slot, preventing the window from silently stretching to older games. Means ignore unknown totals within the fixed window. Schedule dates, not week-number resets, establish chronological order across seasons.

## Missing data, validation, and training considerations

No records were removed or duplicated. On this run, 861 players' first appearances have missing rolling/lag context, 1,666 rows lack two prior PPR observations for standard deviation, and 339 rows have no preceding defensive history. The report records each column's exact missing count. Reliable historical offensive snap percentage is absent from the retained Task 1 schema; `previous_offensive_snap_percentage` is deliberately unavailable. No separate snap download or zero imputation is introduced.

All 41 tests passed, including Task 1 tests. Synthetic examples cover known player means, independent players, cross-season history, byes, sample standard deviation, lagged usage, partial touchdown schemas, team changes, separate defensive positions and yardage, summed position totals, unknown scheduled games, missing values, duplicate rejection, schedule mismatches, output/manifest round trips, and invariance of earlier/current input features after changing later/current outcomes.

Before training, use chronological train/validation/test periods, fit any imputers/encoders only on training data, decide whether to include postseason and offseason history, and retain missing-history signals. This is an observed-appearance dataset, not a roster/availability forecast or an upcoming-game inference service. It cannot teach whether an absent player will participate. Upstream statistics may also be revised after games, so historical snapshots do not guarantee strict point-in-time publication availability. Review scoring policy in `data_pipeline.md` and validate defensive coverage against team totals if exact official yardage is required.
