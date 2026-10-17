"""Download, inspect, validate, and save weekly offensive player statistics."""

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SEASONS = [2023, 2024, 2025]
KEY = ["player_id", "season", "season_type", "week"]
IDENTIFIERS = KEY + ["player_name", "position", "team"]
SCORING_WEIGHTS = {
    "passing_yards": 0.04,
    "passing_tds": 4,
    "passing_interceptions": -2,
    "rushing_yards": 0.1,
    "rushing_tds": 6,
    "receptions": 1,
    "receiving_yards": 0.1,
    "receiving_tds": 6,
    "fumbles_lost_total": -2,
    "passing_2pt_conversions": 2,
    "rushing_2pt_conversions": 2,
    "receiving_2pt_conversions": 2,
    "special_teams_tds": 6,
}
OPTIONAL = [
    "game_id", "opponent_team", "targets", "carries", "attempts", "completions",
    "fumbles_total", "sack_fumbles", "sack_fumbles_lost", "rushing_fumbles",
    "rushing_fumbles_lost", "receiving_fumbles", "receiving_fumbles_lost",
    "fantasy_points", "fantasy_points_ppr",
]


def calculate_ppr(frame: pd.DataFrame) -> pd.Series:
    """Calculate the documented scoring variant; unknown inputs stay unknown."""
    missing = set(SCORING_WEIGHTS) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing scoring columns: {sorted(missing)}")
    points = pd.Series(0.0, index=frame.index)
    for column, weight in SCORING_WEIGHTS.items():
        points = points + pd.to_numeric(frame[column], errors="raise") * weight
    return points.round(4)


def validate_records(frame: pd.DataFrame) -> None:
    """Reject missing identifiers and ambiguous player-week rows."""
    missing = set(IDENTIFIERS) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing identifier columns: {sorted(missing)}")
    for column in IDENTIFIERS:
        if frame[column].isna().any() or frame[column].astype(str).str.strip().eq("").any():
            raise ValueError(f"Missing required identifier: {column}")
    if frame.duplicated(KEY).any():
        raise ValueError("Duplicate player-week records")


def clean_player_stats(raw: pd.DataFrame) -> pd.DataFrame:
    """Keep QB/RB/WR/TE weekly rows without imputing missing statistics."""
    required = set(IDENTIFIERS) | set(SCORING_WEIGHTS)
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"Source schema changed; missing columns: {sorted(missing)}")
    frame = raw.loc[raw["position"].isin(["QB", "RB", "WR", "TE"])].copy()
    columns = list(dict.fromkeys(IDENTIFIERS + list(SCORING_WEIGHTS) + OPTIONAL))
    frame = frame[[column for column in columns if column in frame.columns]]
    if "player_display_name" in raw.columns:
        frame["player_display_name"] = raw.loc[frame.index, "player_display_name"]
    frame = frame.rename(columns={
        "fantasy_points": "source_fantasy_points",
        "fantasy_points_ppr": "source_fantasy_points_ppr",
    })
    validate_records(frame)
    frame["fantasy_points_ppr"] = calculate_ppr(frame)
    return frame.sort_values(KEY).reset_index(drop=True)


def run_pipeline(output: Path, inspection: Path) -> dict:
    """Inspect every download before transformation; propagate download failures."""
    import nflreadpy as nfl

    if output.resolve() == inspection.resolve():
        raise ValueError("Dataset and inspection report must use different paths")

    raw = nfl.load_player_stats(SEASONS, summary_level="week")
    report = {
        "seasons_requested": SEASONS,
        "records_retrieved": raw.height,
        "columns": {name: str(dtype) for name, dtype in raw.schema.items()},
    }
    inspection.parent.mkdir(parents=True, exist_ok=True)
    inspection.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Retrieved {raw.height} records. Available columns: {raw.columns}")
    frame = clean_player_stats(raw.to_pandas())
    if frame.empty:
        raise ValueError("No offensive player statistics returned")
    if set(frame["season"].unique()) != set(SEASONS):
        raise ValueError("Download did not contain all requested seasons")
    report.update({
        "records_processed": len(frame),
        "records_by_season": frame.groupby("season").size().to_dict(),
        "records_by_season_type": frame.groupby("season_type").size().to_dict(),
        "missing_values": frame.isna().sum().to_dict(),
        "unavailable_optional_columns": sorted(set(OPTIONAL) - set(raw.columns)),
    })
    if "source_fantasy_points_ppr" in frame:
        comparable = frame[["fantasy_points_ppr", "source_fantasy_points_ppr"]].dropna()
        report["source_ppr_mismatches"] = int((
            (comparable.iloc[:, 0] - comparable.iloc[:, 1]).abs() > 0.001
        ).sum())
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output, index=False)
    inspection.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Saved {len(frame)} records to {output}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/processed/player_weekly_2023_2025.parquet")
    parser.add_argument("--inspection", type=Path, default=ROOT / "data/processed/schema_report.json")
    args = parser.parse_args()
    try:
        run_pipeline(args.output, args.inspection)
    except Exception as error:
        parser.exit(1, f"Pipeline failed: {error}\n")


if __name__ == "__main__":
    main()
