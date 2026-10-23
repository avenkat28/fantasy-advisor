"""Build historical, leakage-safe player and opponent features (no model training)."""

import argparse
import json
from pathlib import Path

import pandas as pd

from backend.scripts.build_player_stats import ROOT, IDENTIFIERS, validate_records

POSITIONS = ["QB", "RB", "WR", "TE"]
TARGET = "target_fantasy_points_ppr"
METRICS = ["passing_yards", "rushing_yards", "receiving_yards", "receptions", "targets", "carries"]
TD_COLUMNS = ["passing_tds", "rushing_tds", "receiving_tds", "special_teams_tds"]


def schedule_context(players: pd.DataFrame, schedules: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Validate exact team abbreviations and attach one schedule row per team-game."""
    required = {"game_id", "season", "week", "game_type", "gameday", "home_team", "away_team"}
    if required - set(schedules):
        raise ValueError(f"Missing schedule columns: {sorted(required - set(schedules))}")
    schedules = schedules.loc[schedules.season.isin(players.season.unique())].copy()
    if not schedules.game_type.isin(["REG", "WC", "DIV", "CON", "SB"]).all():
        raise ValueError("Expected regular-season and postseason schedules only")
    if schedules.game_id.isna().any() or schedules.game_id.duplicated().any():
        raise ValueError("Missing or duplicate schedule game IDs")
    sides = []
    for home in [True, False]:
        side = schedules[["game_id", "season", "week", "game_type", "gameday"]].copy()
        side["team"] = schedules["home_team" if home else "away_team"]
        side["opponent_team"] = schedules["away_team" if home else "home_team"]
        side["is_home"] = home
        sides.append(side)
    context = pd.concat(sides, ignore_index=True)
    context["game_date"] = pd.to_datetime(context.pop("gameday"), errors="raise")
    if context.isna().any().any() or context.duplicated(["season", "week", "team"]).any():
        raise ValueError("Incomplete or ambiguous team-game schedule")
    context["season_type"] = context.pop("game_type").map(lambda x: "REG" if x == "REG" else "POST")
    join = ["season", "season_type", "week", "team"]
    attached = players.merge(context, on=join, how="left", validate="many_to_one", suffixes=("", "_schedule"))
    if attached.game_date.isna().any():
        raise ValueError("Player teams/weeks do not match schedule; check team abbreviations")
    for column in ["game_id", "opponent_team"]:
        scheduled = column + "_schedule"
        if scheduled in attached:
            known = attached[column].notna()
            if attached.loc[known, column].ne(attached.loc[known, scheduled]).any():
                raise ValueError(f"Player {column} disagrees with schedule")
            attached[column] = attached.pop(scheduled)
    return attached, context


def prior_rolling(frame: pd.DataFrame, groups: list[str], column: str, window: int, std: bool = False) -> pd.Series:
    """Shift within a group BEFORE rolling; missing observations are never imputed."""
    grouped = frame.groupby(groups, sort=False)
    shifted = grouped[column].shift(1)
    windows = shifted.groupby([frame[key] for key in groups], sort=False).rolling(
        window, min_periods=2 if std else 1)
    result = windows.std() if std else windows.mean()
    # Grouped rolling returns group keys plus the original row index. Restore
    # source order explicitly; no Python callback is needed for each player.
    return result.droplevel(list(range(len(groups)))).reindex(frame.index)



def known_sum(values: pd.Series) -> float:
    """A partially unknown game total must remain unknown."""
    return values.sum(min_count=len(values))


def defensive_features(players: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    """Sum all players before rolling once per defense/game/position."""
    keys = ["game_id", "opponent_team", "position"]
    totals = players.groupby(keys, as_index=False)["fantasy_points_ppr"].agg(known_sum)
    totals = totals.rename(columns={"opponent_team": "team", "fantasy_points_ppr": "allowed_ppr"})
    # A schedule grid keeps an unobserved position/game as unknown rather than
    # skipping it and accidentally using games outside the requested window.
    grid = context.merge(pd.DataFrame({"position": POSITIONS}), how="cross")
    grid = grid.merge(totals, on=["game_id", "team", "position"], how="left", validate="one_to_one")
    grid = grid.sort_values(["team", "position", "game_date", "game_id"])
    for window in [3, 5]:
        grid[f"opponent_ppr_allowed_position_mean_{window}"] = prior_rolling(
            grid, ["team", "position"], "allowed_ppr", window)
    grid["opponent_prior_games"] = grid.groupby(["team", "position"]).cumcount()
    yard_columns = [c for c in ["passing_yards", "rushing_yards"] if c in players]
    yards = players.groupby(["game_id", "opponent_team"], as_index=False)[yard_columns].agg(known_sum)
    yards = yards.rename(columns={"opponent_team": "team"})
    defense = context.merge(yards, on=["game_id", "team"], how="left", validate="one_to_one")
    defense = defense.sort_values(["team", "game_date", "game_id"])
    for column in yard_columns:
        for window in [3, 5]:
            name = f"opponent_{column}_allowed_mean_{window}"
            defense[name] = prior_rolling(defense, ["team"], column, window)
    features = [c for c in defense if c.startswith("opponent_") and c != "opponent_team"]
    grid = grid.merge(defense[["game_id", "team"] + features], on=["game_id", "team"], validate="many_to_one")
    columns = [c for c in grid if c.startswith("opponent_") and c != "opponent_team"]
    return grid[["game_id", "team", "position"] + columns].rename(columns={"team": "opponent_team"})


def build_features(players: pd.DataFrame, schedules: pd.DataFrame) -> pd.DataFrame:
    validate_records(players)
    if "fantasy_points_ppr" not in players:
        raise ValueError("Missing Task 1 fantasy_points_ppr target")
    if not players.position.isin(POSITIONS).all() or players.empty:
        raise ValueError("Expected nonempty QB/RB/WR/TE dataset")
    frame, context = schedule_context(players.copy(), schedules)
    frame = frame.sort_values(["player_id", "game_date", "game_id"]).reset_index(drop=True)
    if frame.duplicated(["player_id", "game_date"]).any():
        raise ValueError("Ambiguous same-day player appearances")
    output_columns = list(IDENTIFIERS) + [c for c in ["player_display_name"] if c in frame]
    output_columns += ["game_id", "opponent_team", "game_date", "is_home"]
    metrics = [c for c in METRICS if c in frame]
    touchdown_columns = [c for c in TD_COLUMNS if c in frame]
    if touchdown_columns:
        frame["touchdowns"] = frame[touchdown_columns].sum(axis=1, min_count=len(touchdown_columns))
        metrics.append("touchdowns")
    for column in ["fantasy_points_ppr"] + metrics:
        for window in ([3, 5, 10] if column == "fantasy_points_ppr" else [3, 5]):
            name = f"{column}_mean_{window}"
            frame[name] = prior_rolling(frame, ["player_id"], column, window)
            output_columns.append(name)
    name = "fantasy_points_ppr_std_5"
    frame[name] = prior_rolling(frame, ["player_id"], "fantasy_points_ppr", 5, std=True)
    output_columns.append(name)
    grouped = frame.groupby("player_id", sort=False)
    for column in ["fantasy_points_ppr", "targets", "receptions"]:
        if column in frame:
            name = f"previous_{column}"
            frame[name] = grouped[column].shift(1)
            output_columns.append(name)
    if "targets" in frame:
        frame["targets_trend_3_vs_5"] = frame.targets_mean_3 - frame.targets_mean_5
        output_columns.append("targets_trend_3_vs_5")
    frame["prior_games"] = grouped.cumcount()
    frame["days_since_previous_game"] = (frame.game_date - grouped.game_date.shift(1)).dt.days
    previous_team = grouped.team.shift(1)
    frame["changed_team"] = frame.team.ne(previous_team).astype("boolean").mask(previous_team.isna())
    output_columns += ["prior_games", "days_since_previous_game", "changed_team"]
    frame[TARGET] = frame.fantasy_points_ppr
    result = frame[output_columns + [TARGET]].merge(
        defensive_features(frame, context), on=["game_id", "opponent_team", "position"],
        how="left", validate="many_to_one")
    validate_records(result)
    return result


def run_pipeline(source: Path, output: Path, report_path: Path, schedule_path: Path) -> dict:
    paths = [source, output, report_path, schedule_path]
    if len({p.resolve() for p in paths}) != len(paths):
        raise ValueError("Input, output, schedule, and report paths must differ")
    players = pd.read_parquet(source)
    if schedule_path.exists():
        schedules = pd.read_parquet(schedule_path)
    else:
        import nflreadpy as nfl
        schedules = nfl.load_schedules(sorted(players.season.unique().tolist())).to_pandas()
        schedule_path.parent.mkdir(parents=True, exist_ok=True)
        schedules.to_parquet(schedule_path, index=False)
    features = build_features(players, schedules)
    identifiers = ["player_id", "player_name", "player_display_name", "game_id", "game_date"]
    inputs = [c for c in features if c not in identifiers + [TARGET]]
    report = {
        "source": str(source), "schedule_source": "nflreadpy.load_schedules / nflverse schedules",
        "schedule_snapshot": str(schedule_path), "rows": len(features), "columns": len(features.columns),
        "source_schema": {c: str(t) for c, t in players.dtypes.items()},
        "source_missing_values": players.isna().sum().to_dict(),
        "feature_columns": inputs, "identifier_columns": [c for c in identifiers if c in features],
        "target_column": TARGET, "missing_values": features.isna().sum().to_dict(),
        "unavailable_player_metrics": sorted(set(METRICS) - set(players)),
        "unavailable_features": ["previous_offensive_snap_percentage"],
        "touchdown_components": [c for c in TD_COLUMNS if c in players],
        "unavailable_touchdown_components": sorted(set(TD_COLUMNS) - set(players)),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    features.to_parquet(output, index=False)
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Saved {report['rows']} rows x {report['columns']} columns to {output}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/processed/player_weekly_2023_2025.parquet")
    parser.add_argument("--output", type=Path, default=ROOT / "data/processed/player_features_2023_2025.parquet")
    parser.add_argument("--report", type=Path, default=ROOT / "data/processed/feature_report.json")
    parser.add_argument("--schedules", type=Path, default=ROOT / "data/raw/schedules_2023_2025.parquet")
    args = parser.parse_args()
    try:
        run_pipeline(args.input, args.output, args.report, args.schedules)
    except Exception as error:
        parser.exit(1, f"Feature pipeline failed: {error}\n")


if __name__ == "__main__":
    main()
