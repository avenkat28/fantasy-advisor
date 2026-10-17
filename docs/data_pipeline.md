# Historical player data pipeline

## Observed run

The real nflreadpy 0.1.5 download on October 17, 2026 returned 57,048 rows and 150 columns. Filtering to QB, RB, WR, and TE retained 18,533 rows: 6,071 for 2023, 6,141 for 2024, and 6,321 for 2025. There are 17,702 regular-season and 831 postseason records. All 37 retained columns have zero missing values; all requested optional fields were available. No duplicate player/season/season-type/week records or missing required identifiers were found. All 25 tests passed, including the generated dataset check.

## Transformation and scoring

Keep source field names to minimize translation. Preserve the short `player_name` and full `player_display_name`, team, opponent, game ID, season type, season/week, usage, offensive production, and fumble breakdowns. Rename source fantasy totals to `source_fantasy_points` and `source_fantasy_points_ppr`. Store the calculated score as `fantasy_points_ppr`.

This project's full-PPR scoring variant uses:

| Event | Points |
| --- | ---: |
| Passing yard | 0.04 |
| Passing touchdown | 4 |
| Interception thrown | -2 |
| Rushing or receiving yard | 0.1 |
| Rushing or receiving touchdown | 6 |
| Reception | 1 |
| Fumble lost, including special teams | -2 |
| Passing, rushing, or receiving two-point conversion | 2 |
| Special-teams touchdown | 6 |

No yardage bonuses, return-yard points, IDP points, or separate fumble-recovery touchdown bonus are added. League scoring varies; this explicit policy is the definition for this dataset. `fumbles_lost_total` is deducted once. Never also deduct its sack, rushing, or receiving components; non-lost fumbles incur no penalty. Missing scoring columns fail clearly, while null scoring values propagate to a null score rather than being invented as zero.

There are 87 differences from the source PPR totals. Investigation confirmed that the source totals exactly match the same formula using only sack + rushing + receiving fumbles lost; our total-fumbles policy additionally counts other lost fumbles (such as returns). These differences are intentional and source scores remain intact.

## Limitations

These are observed player-week statistics, not a complete roster-by-week grid: absent players and bye weeks are not fabricated. Both REG and POST are retained; filter REG explicitly for regular-season modeling. No injury, availability, defensive matchup, schedule forecast, or future-week features are inferred. Team abbreviations are preserved as supplied. The download is an upstream snapshot and may be revised later; direct dependency versions are pinned, but transitive dependencies are not locked. The initial inspection download at `data/raw/player_stats_inspected.parquet` is a local ignored artifact, not a pipeline input or required output.

## Complete observed source schema

This table was generated from the actual download, not assumed from documentation. Each pipeline run writes its own schema report before transforming data.

| Column | Source type |
| --- | --- |
| `player_id` | String |
| `player_name` | String |
| `player_display_name` | String |
| `position` | String |
| `position_group` | String |
| `headshot_url` | String |
| `season` | Int32 |
| `week` | Int32 |
| `season_type` | String |
| `game_id` | String |
| `team` | String |
| `opponent_team` | String |
| `completions` | Int32 |
| `attempts` | Int32 |
| `passing_yards` | Int32 |
| `passing_tds` | Int32 |
| `passing_interceptions` | Int32 |
| `sacks_suffered` | Int32 |
| `sack_yards_lost` | Int32 |
| `sack_fumbles` | Int32 |
| `sack_fumbles_lost` | Int32 |
| `passing_air_yards` | Int32 |
| `passing_yards_after_catch` | Int32 |
| `passing_first_downs` | Int32 |
| `passing_epa` | Float64 |
| `passing_cpoe` | Float64 |
| `passing_2pt_conversions` | Int32 |
| `pacr` | Float64 |
| `passing_10` | Int32 |
| `passing_16` | Int32 |
| `passing_20` | Int32 |
| `passing_40` | Int32 |
| `carries` | Int32 |
| `rushing_yards` | Int32 |
| `rushing_tds` | Int32 |
| `rushing_fumbles` | Int32 |
| `rushing_fumbles_lost` | Int32 |
| `rushing_first_downs` | Int32 |
| `rushing_epa` | Float64 |
| `rushing_2pt_conversions` | Int32 |
| `rushing_10` | Int32 |
| `rushing_12` | Int32 |
| `rushing_20` | Int32 |
| `rushing_40` | Int32 |
| `receptions` | Int32 |
| `targets` | Int32 |
| `receiving_yards` | Int32 |
| `receiving_tds` | Int32 |
| `receiving_fumbles` | Int32 |
| `receiving_fumbles_lost` | Int32 |
| `receiving_air_yards` | Int32 |
| `receiving_yards_after_catch` | Int32 |
| `receiving_first_downs` | Int32 |
| `receiving_epa` | Float64 |
| `receiving_2pt_conversions` | Int32 |
| `receiving_10` | Int32 |
| `receiving_16` | Int32 |
| `receiving_20` | Int32 |
| `receiving_40` | Int32 |
| `racr` | Float64 |
| `target_share` | Float64 |
| `air_yards_share` | Float64 |
| `wopr` | Float64 |
| `special_teams_tds` | Int32 |
| `def_tackles_solo` | Int32 |
| `def_tackles_with_assist` | Int32 |
| `def_tackle_assists` | Int32 |
| `def_tackles_for_loss` | Int32 |
| `def_tackles_for_loss_yards` | Int32 |
| `def_fumbles_forced` | Int32 |
| `def_sacks` | Float64 |
| `def_sack_yards` | Float64 |
| `def_qb_hits` | Int32 |
| `def_interceptions` | Int32 |
| `def_interception_yards` | Int32 |
| `def_pass_defended` | Int32 |
| `def_tds` | Int32 |
| `def_fumbles` | Int32 |
| `def_safeties` | Int32 |
| `def_punt_blocks` | Int32 |
| `def_pat_blocks` | Int32 |
| `def_fg_blocks` | Int32 |
| `def_2pt_atts` | Int32 |
| `def_2pt_made` | Int32 |
| `misc_yards` | Int32 |
| `fumble_recovery_own` | Int32 |
| `fumble_recovery_yards_own` | Int32 |
| `fumble_recovery_opp` | Int32 |
| `fumble_recovery_yards_opp` | Int32 |
| `fumble_recovery_tds` | Int32 |
| `penalties` | Int32 |
| `penalty_yards` | Int32 |
| `fumbles_forced_by_opp` | Int32 |
| `fumbles_not_forced` | Int32 |
| `fumbles_out_of_bounds` | Int32 |
| `fumbles_total` | Int32 |
| `fumbles_lost_total` | Int32 |
| `punt_returns` | Int32 |
| `punt_return_yards` | Int32 |
| `kickoff_returns` | Int32 |
| `kickoff_return_yards` | Int32 |
| `fg_made` | Int32 |
| `fg_att` | Int32 |
| `fg_missed` | Int32 |
| `fg_blocked` | Int32 |
| `fg_long` | Int32 |
| `fg_pct` | Float64 |
| `fg_made_0_19` | Int32 |
| `fg_made_20_29` | Int32 |
| `fg_made_30_39` | Int32 |
| `fg_made_40_49` | Int32 |
| `fg_made_50_59` | Int32 |
| `fg_made_60_` | Int32 |
| `fg_missed_0_19` | Int32 |
| `fg_missed_20_29` | Int32 |
| `fg_missed_30_39` | Int32 |
| `fg_missed_40_49` | Int32 |
| `fg_missed_50_59` | Int32 |
| `fg_missed_60_` | Int32 |
| `fg_made_list` | String |
| `fg_missed_list` | String |
| `fg_blocked_list` | String |
| `fg_made_distance` | Int32 |
| `fg_missed_distance` | Int32 |
| `fg_blocked_distance` | Int32 |
| `pat_made` | Int32 |
| `pat_att` | Int32 |
| `pat_missed` | Int32 |
| `pat_blocked` | Int32 |
| `pat_pct` | Float64 |
| `gwfg_made` | Int32 |
| `gwfg_att` | Int32 |
| `gwfg_missed` | Int32 |
| `gwfg_blocked` | Int32 |
| `gwfg_distance` | Int32 |
| `pt_att` | Int32 |
| `pt_blocked` | Int32 |
| `pt_long` | Int32 |
| `pt_yards` | Int32 |
| `pt_inside_20` | Int32 |
| `pt_out_of_bounds` | Int32 |
| `pt_downed` | Int32 |
| `pt_touchback` | Int32 |
| `pt_fair_caught` | Int32 |
| `pt_returned` | Int32 |
| `pt_return_yards` | Int32 |
| `pt_return_tds` | Int32 |
| `pt_net_yards` | Int32 |
| `fantasy_points` | Float64 |
| `fantasy_points_ppr` | Float64 |
