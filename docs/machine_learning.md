# Full-PPR prediction (Task 3)

The model predicts points conditional on an observed RB/WR appearance. The target is Task 2's `target_fantasy_points_ppr`, copied from Task 1's documented full-PPR scoring calculation (including lost fumbles, two-point conversions and special-teams touchdowns). Negative scores are valid. The pipeline rejects missing/nonfinite targets, duplicate player-games, missing identifiers, inconsistent game metadata, missing approved columns and infinite inputs. It records source dtypes, null counts and a SHA-256 dataset fingerprint in `reports/ml/training_report.json`.

## Reproduce

From the repository root, use Python 3.12 and the existing data files:

```bash
source .venv312/bin/activate
python -m pip install -r backend/requirements-dev.txt
# macOS only, if XGBoost reports a missing libomp runtime:
brew install libomp
# Rebuild only if necessary:
python -m backend.scripts.build_player_stats
python -m backend.scripts.build_features
MPLCONFIGDIR=.matplotlib python -m backend.scripts.train_models
MPLCONFIGDIR=.matplotlib python -m backend.ml.evaluate --output reports/ml
python -m backend.ml.predict --model models/ppr-v1/RB.joblib --features reports/ml/RB_example_features.json
python -m backend.ml.predict --model models/ppr-v1/WR.joblib --features reports/ml/WR_example_features.json
MPLCONFIGDIR=.matplotlib python -m pytest backend/tests -q
```

Training accepts `--input`, `--models`, and `--output`. It overwrites artifacts at those destinations; choose new directories for another experiment. Evaluation reads saved test predictions and importance values and regenerates metrics and figures without fitting. Inference uses `predict_points(model_path, features)` from `backend.ml.predict` independently of training. Its JSON-compatible dictionary must contain exactly the 29 approved numeric/boolean features; missing history is represented by null. Missing keys, extra fields (including outcomes/targets), strings and infinity are rejected. Null values are imputed by the saved pipeline. Only load trusted joblib files. Position is selected by the artifact, so callers must choose the correct RB or WR model.

## Features and leakage review

Both position models use the exact allowlist in `backend/ml/schema.py` (also saved in each model's metadata):

- Schedule context: `is_home`.
- Historical points: `fantasy_points_ppr_mean_3`, `fantasy_points_ppr_mean_5`, `fantasy_points_ppr_mean_10`, `fantasy_points_ppr_std_5`, `previous_fantasy_points_ppr`.
- Historical production/opportunity: `rushing_yards_mean_3`, `rushing_yards_mean_5`, `receiving_yards_mean_3`, `receiving_yards_mean_5`, `receptions_mean_3`, `receptions_mean_5`, `targets_mean_3`, `targets_mean_5`, `carries_mean_3`, `carries_mean_5`, `touchdowns_mean_3`, `touchdowns_mean_5`, `previous_targets`, `previous_receptions`, `targets_trend_3_vs_5`.
- Historical context: `prior_games`, `days_since_previous_game`, `changed_team`.
- Opponent history: `opponent_ppr_allowed_position_mean_3`, `opponent_ppr_allowed_position_mean_5`, `opponent_prior_games`, `opponent_rushing_yards_allowed_mean_3`, `opponent_rushing_yards_allowed_mean_5`.

Every production field above is shifted before rolling in Task 2. Schedule home/away and a player's assigned team can be known pregame; rest and team-change flags compare against previous appearances. Current-game production, participation, raw fantasy totals, target, identity, position, team labels, dates, season/week and passing-yard features are excluded. No categorical encoding is needed: position has its own model, and home/team-change flags are numeric. Identifiers remain only in reports.

Review found no upstream leakage requiring a rewrite. Tests perturb current and later production and verify all approved earlier/current inputs remain identical; another test rebuilds the cached real features and compares them exactly. Histories continue across seasons and can include prior postseason games, but every fitting/evaluation target is regular season. Date order is checked across splits, and game IDs cannot cross boundaries.

## Evaluation design and models

Training uses 2023–2024 regular-season games, validation uses 2025 weeks 1–9, and the final test uses weeks 10–18. The week boundary was chosen before examining results. All player records in each NFL game remain together. This is sequential one-game-ahead evaluation: later validation/test games may use outcomes from completed earlier games in those periods. It does not simulate forecasting the entire season from its opening date. No test outcomes enter model selection or preprocessing fitting. Training rejects fewer than 30 position records in any split.

Three-game and five-game PPR means use Task 2's partial-window means; no history falls back to that position's training target mean. Ridge uses training median imputation, missing-value indicators, standardization and fixed alpha 10. XGBoost uses training median imputation and missing indicators, with no scaling. A small validation-only search selects minimum MAE among depth 2/3 and 150/300 trees. All candidates use learning rate .03, minimum child weight 20, L2 regularization 10, row/column sampling .8, seed 42 and one CPU worker. The selected fit remains trained on 2023–2024; there is no post-selection refit on validation.

XGBoost was chosen for nonlinear relationships and interactions in tabular opportunity and matchup data, with shallow regularized trees limiting complexity. See its [official project documentation](https://xgboost.readthedocs.io/en/stable/). Baselines establish whether its added complexity helps on this split. Feature importance reports normalized gain; this is an association in the fitted model, and correlated rolling windows can share or obscure importance.

MAE is average absolute point error; RMSE penalizes larger errors; R² compares squared error to a constant test mean; bias is prediction minus actual, so positive values indicate overprediction. All models are scored on identical test rows, separately for RB/WR. History groups use fewer than five versus at least five prior observed appearances since the dataset begins in 2023.

## Artifacts and diagnostics

Generated models and reports are ignored by Git. `models/ppr-v1/{RB,WR}.joblib` each contains the XGBoost pipeline and metadata; `{RB,WR}_ridge.joblib` saves each baseline pipeline. JSON metadata stores the ordered features, version, seed, training/validation periods, hyperparameters, package versions and dataset fingerprint. Targets and datasets are never put into model input matrices or serialized training records. Reloaded model predictions are checked against the entire test set exactly.

`reports/ml/` contains:

- `training_report.json`: schema audit, counts, validation candidates, chosen parameters, test metrics and historical demo identities.
- `metrics.csv`, `test_predictions.csv`: metrics and per-game actual/predicted values for all four models.
- `feature_importance.csv`, `history_metrics.csv`, `player_bias.csv`: gain importance, limited/extensive history errors, and per-player bias for players with at least five test appearances.
- `prediction_examples.csv`: five most accurate and five least accurate test predictions per position.
- `RB_evaluation.png`, `WR_evaluation.png`: actual vs predicted, baseline error comparison, importance and error distribution, in four-panel matplotlib figures.
- `{RB,WR}_example_features.json`: only approved inputs from a real held-out historical record for the standalone CLI demonstration.

## Limits before API integration

This dataset contains observed appearances, not roster availability or explicit DNP rows. Performance cannot establish whether an injured/inactive player will play, or validate a general start/sit service. Unknown injuries, depth-chart shifts and unexpected opportunities are possible sources of error; the available data cannot identify their causes for an individual bad prediction. Player bias is descriptive over a small sample, not evidence of a stable player effect. No live injury, snap, weather or depth-chart information is included.

History is truncated at 2023, so limited history need not mean rookie status. Offseason gaps and stale player roles may weaken historical averages. Revised source statistics and absence of timestamped release snapshots prevent a strict historical publication-time guarantee. Defensive rushing yardage is derived from retained offensive positions, not official team totals. Only one half-season test period is available; evaluate additional rolling season folds and prospective data before deployment. Do not retune on this test period and keep calling it untouched. Package versions and hardware changes may affect cross-environment reproducibility; the run manifest records versions, while exact serialization checks cover the current environment.

## Measured results — October 19, 2026

The successful local run used the cached real 2023–2025 dataset, with no synthetic training rows. The source contains 18,533 rows and 45 columns, with no duplicate player-games or invalid targets. Missing inputs are historical context, handled by training-only imputers.

| Position | Train | Validation | Test | Selected depth / trees |
| --- | ---: | ---: | ---: | --- |
| RB | 3010 | 785 | 790 | 3 / 300 |
| WR | 4917 | 1254 | 1257 | 2 / 300 |

| Position | Model | MAE | RMSE | R² | Bias |
| --- | --- | ---: | ---: | ---: | ---: |
| RB | mean_3 | 4.737 | 6.907 | 0.310 | +0.042 |
| RB | mean_5 | 4.467 | 6.537 | 0.382 | +0.010 |
| RB | ridge | 4.378 | 6.352 | 0.416 | -0.180 |
| RB | xgboost | 4.529 | 6.408 | 0.406 | +0.050 |
| WR | mean_3 | 4.493 | 6.320 | 0.234 | +0.242 |
| WR | mean_5 | 4.327 | 6.043 | 0.299 | +0.284 |
| WR | ridge | 4.473 | 5.942 | 0.323 | +0.868 |
| WR | xgboost | 4.341 | 5.841 | 0.345 | +0.611 |

XGBoost beats the three-game average on MAE/RMSE for both positions. For RB, it loses to Ridge on both measures and to the five-game mean on MAE (while improving RMSE). For WR it improves RMSE over every baseline and MAE over Ridge, but its MAE is slightly worse than the five-game mean. These results do not justify claiming an across-the-board XGBoost improvement. Keep the baseline models as candidates for future prospective evaluation; do not use this test to retune.

RB leading normalized gain importance: `fantasy_points_ppr_mean_5` (0.240), `carries_mean_3` (0.130), `fantasy_points_ppr_mean_10` (0.114), `carries_mean_5` (0.059), `missingindicator_opponent_ppr_allowed_position_mean_3` (0.031).

WR leading normalized gain importance: `fantasy_points_ppr_mean_5` (0.194), `fantasy_points_ppr_mean_10` (0.166), `targets_mean_5` (0.125), `receptions_mean_5` (0.109), `targets_mean_3` (0.073).

| Position | History | Test rows | MAE | RMSE | Bias |
| --- | --- | ---: | ---: | ---: | ---: |
| RB | limited_<5 | 36 | 3.183 | 4.389 | +0.772 |
| RB | extensive_>=5 | 754 | 4.594 | 6.489 | +0.016 |
| WR | limited_<5 | 56 | 2.633 | 3.429 | +0.246 |
| WR | extensive_>=5 | 1201 | 4.421 | 5.930 | +0.629 |

Limited-history groups have lower absolute errors but negative R² on this sample; their outcomes have different variance and lower errors do not establish better generalization. These groups are small (36 RB and 56 WR appearances).

| Example | Position | Player | Season/week | Actual | XGBoost |
| --- | --- | --- | --- | ---: | ---: |
| accurate | RB | T.Spears | 2025/11 | 8.40 | 8.41 |
| inaccurate | RB | J.Gibbs | 2025/12 | 55.40 | 16.46 |
| accurate | WR | D.Mooney | 2025/11 | 6.40 | 6.39 |
| inaccurate | WR | P.Nacua | 2025/16 | 46.50 | 18.76 |

Across players with at least five held-out appearances, RB examples include underprediction of J.Gibbs (mean bias −8.15 over 9 games) and overprediction of R.Dowdle (+4.10 over 8). WR examples include underprediction of P.Nacua (−5.15 over 9) and overprediction of M.Pittman (+6.10 over 8). These are observed errors; the dataset does not establish injury or playing-time causes. Full examples and player aggregates are saved in the report CSVs.
