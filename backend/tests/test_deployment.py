"""Deployment preflight uses the real local repository contracts, with offline fixtures."""
import pytest

from backend.scripts.check_deployment import check_deployment
from backend.tests.test_api import setup  # noqa: F401 -- shared synthetic fixture
from backend.tests.test_current_data import published


def test_vercel_entrypoint_exports_existing_app():
    from app import app
    from backend.api.main import app as existing
    assert app is existing


def test_preflight_accepts_complete_published_snapshot(setup):
    data, _ = published(setup)
    result = check_deployment(data.root)
    assert result['ready']
    assert result['models'] == ['RB', 'WR']


def test_preflight_rejects_missing_manifest(tmp_path):
    with pytest.raises(ValueError, match='data/current.json'):
        check_deployment(tmp_path)


@pytest.mark.parametrize('path', ['models/ppr-v1/RB.joblib', 'reports/ml/test_predictions.csv'])
def test_preflight_rejects_missing_artifacts(setup, path):
    data, _ = published(setup)
    (data.root / path).unlink()
    with pytest.raises(ValueError, match='Missing'):
        check_deployment(data.root)


def test_preflight_rejects_mixed_source_overrides(setup, monkeypatch):
    data, _ = published(setup)
    monkeypatch.setenv('FANTASY_PLAYERS', str(data.players_path))
    with pytest.raises(ValueError, match='remove FANTASY_PLAYERS'):
        check_deployment(data.root)
