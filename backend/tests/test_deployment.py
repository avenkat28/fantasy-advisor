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


@pytest.mark.parametrize('path,expected', [
    ('/', 'frontend'), ('/players/example', 'frontend'),
    ('/projections', 'frontend'), ('/api/health', 'backend'),
    ('/api/projections', 'backend'), ('/api/unknown', 'backend'),
    ('/docs', 'backend'), ('/docs/oauth2-redirect', 'backend'),
    ('/openapi.json', 'backend'), ('/redoc', 'backend'),
])
def test_single_project_public_routing(path, expected):
    import json
    import re
    from backend.scripts.build_player_stats import ROOT
    configuration = json.loads((ROOT / 'vercel.json').read_text())
    for rule in configuration['rewrites']:
        if re.fullmatch(rule['source'], path):
            assert rule['destination']['service'] == expected
            break
    else:
        pytest.fail(f'No service owns {path}')


def test_services_config_keeps_runtime_settings_scoped_and_within_vercel_limits():
    import json
    from backend.scripts.build_player_stats import ROOT
    configuration = json.loads((ROOT / 'vercel.json').read_text())
    for key in ['framework', 'buildCommand', 'installCommand', 'functions']:
        assert key not in configuration
    for service in configuration['services'].values():
        assert (ROOT / service['root']).is_dir()
        for options in service.get('functions', {}).values():
            assert len(options.get('excludeFiles', '')) <= 256
