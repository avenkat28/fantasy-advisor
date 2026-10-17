"""Tests for weekly player statistics and PPR scoring."""

import json

import pandas as pd
import pytest

from backend.scripts.build_player_stats import (
    ROOT, SCORING_WEIGHTS, calculate_ppr, clean_player_stats, run_pipeline, validate_records,
)


def sample_row():
    return {
        **dict.fromkeys(SCORING_WEIGHTS, 0),
        "player_id": "test-player", "player_name": "Test Player", "position": "QB",
        "team": "BUF", "season": 2025, "season_type": "REG", "week": 1,
    }


def test_ppr_scoring_and_no_double_counting():
    row = sample_row()
    row.update(passing_yards=250, passing_tds=2, passing_interceptions=1,
               rushing_yards=30, rushing_tds=1, receptions=4, receiving_yards=50,
               receiving_tds=1, fumbles_lost_total=1, rushing_fumbles_lost=1,
               passing_2pt_conversions=1, rushing_2pt_conversions=1,
               receiving_2pt_conversions=1, special_teams_tds=1)
    # Only the total lost-fumble count contributes a penalty.
    assert calculate_ppr(pd.DataFrame([row])).iloc[0] == pytest.approx(50)


def test_negative_yards_and_unknown_scoring_input():
    row = sample_row()
    row["rushing_yards"] = -10
    assert calculate_ppr(pd.DataFrame([row])).iloc[0] == -1
    row["receptions"] = None
    assert pd.isna(calculate_ppr(pd.DataFrame([row])).iloc[0])


def test_missing_scoring_column_is_rejected():
    with pytest.raises(ValueError, match="Missing scoring columns"):
        calculate_ppr(pd.DataFrame([sample_row()]).drop(columns="receptions"))


def test_duplicates_are_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        validate_records(pd.DataFrame([sample_row(), sample_row()]))


@pytest.mark.parametrize("column", ["player_id", "player_name", "position", "team", "season", "week", "season_type"])
@pytest.mark.parametrize("value", [None, " "])
def test_missing_identifiers_are_rejected(column, value):
    row = sample_row()
    row[column] = value
    with pytest.raises(ValueError, match="Missing required identifier"):
        validate_records(pd.DataFrame([row]))


def test_filter_positions_and_preserve_source_scores():
    row = sample_row()
    row["fantasy_points_ppr"] = 99
    defender = {**row, "player_id": "defender", "position": "LB"}
    result = clean_player_stats(pd.DataFrame([row, defender]))
    assert len(result) == 1
    assert result.iloc[0]["source_fantasy_points_ppr"] == 99
    assert result.iloc[0]["fantasy_points_ppr"] == 0


def test_generated_dataset_integrity():
    path = ROOT / "data/processed/player_weekly_2023_2025.parquet"
    if not path.exists():
        pytest.skip("Run pipeline first to check the generated dataset")
    frame = pd.read_parquet(path)
    validate_records(frame)
    assert set(frame["season"]) == {2023, 2024, 2025}
    assert set(frame["position"]) <= {"QB", "RB", "WR", "TE"}
    pd.testing.assert_series_equal(frame["fantasy_points_ppr"], calculate_ppr(frame), check_names=False)
    assert frame["fantasy_points_ppr"].notna().all()


def mock_download(monkeypatch, rows):
    import nflreadpy
    import polars as pl

    def load(seasons, summary_level):
        assert seasons == [2023, 2024, 2025]
        assert summary_level == "week"
        return pl.DataFrame(rows)

    monkeypatch.setattr(nflreadpy, "load_player_stats", load)


def test_pipeline_writes_parquet_and_report(monkeypatch, tmp_path):
    rows = [{**sample_row(), "season": season} for season in [2023, 2024, 2025]]
    mock_download(monkeypatch, rows)
    output = tmp_path / "processed" / "players.parquet"
    inspection = tmp_path / "reports" / "schema.json"
    report = run_pipeline(output, inspection)
    assert report["records_retrieved"] == 3
    assert report["records_processed"] == 3
    assert json.loads(inspection.read_text())["records_processed"] == 3
    assert len(pd.read_parquet(output)) == 3


def test_pipeline_rejects_incomplete_seasons(monkeypatch, tmp_path):
    mock_download(monkeypatch, [sample_row()])
    output = tmp_path / "players.parquet"
    inspection = tmp_path / "schema.json"
    with pytest.raises(ValueError, match="all requested seasons"):
        run_pipeline(output, inspection)
    assert not output.exists()
    assert json.loads(inspection.read_text())["records_retrieved"] == 1


def test_download_failure_does_not_create_dataset(monkeypatch, tmp_path):
    import nflreadpy

    def fail(*args, **kwargs):
        raise RuntimeError("Download unavailable")

    monkeypatch.setattr(nflreadpy, "load_player_stats", fail)
    output = tmp_path / "players.parquet"
    with pytest.raises(RuntimeError, match="Download unavailable"):
        run_pipeline(output, tmp_path / "schema.json")
    assert not output.exists()


def test_output_and_report_paths_must_differ(tmp_path):
    path = tmp_path / "output.parquet"
    with pytest.raises(ValueError, match="different paths"):
        run_pipeline(path, path)


def test_missing_source_column_is_rejected():
    raw = pd.DataFrame([sample_row()]).drop(columns="passing_yards")
    with pytest.raises(ValueError, match="Source schema changed"):
        clean_player_stats(raw)
