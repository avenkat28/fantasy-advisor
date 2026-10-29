import json

import pandas as pd

from backend.api.tracking import archive_path, weekly_results
from backend.tests.test_api import setup  # noqa: F401


def test_injury_adjustment_is_point_in_time(setup):
    data, service, _ = setup
    metadata = service.project('a', 2025, 4)
    data.injuries = pd.DataFrame([dict(gsis_id='a', season=2025, week=4, report_status='Out', observed_at='2025-09-28T12:00:00Z')])
    result = service.injury_adjustment(metadata, 10.)
    assert result['projected_ppr_points'] == 0
    assert result['base_projected_ppr_points'] == 10
    data.injuries['observed_at'] = '2025-09-30T12:00:00Z'
    assert service.injury_adjustment(metadata, 10.)['projected_ppr_points'] == 10
    data.injuries['observed_at'] = '2025-09-28T12:00:00Z'
    data.injuries['report_status'] = 'Questionable'
    assert service.injury_adjustment(metadata, 10.)['projected_ppr_points'] == 10


def test_results_compare_matched_baseline_without_backfill(setup):
    data, service, root = setup
    p = service.project('a', 2025, 4)
    path = archive_path(root, 2025, 4)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps([p]))
    results = weekly_results(data, 2025, 4)
    assert len(results['metrics']) == 2
    assert results['metrics'][0]['count'] == results['metrics'][1]['count'] == 1
    assert any(r['projected'] is None and r['actual'] is not None for r in results['records'])
    path.unlink()
    assert weekly_results(data, 2025, 4)['metrics'] == []
