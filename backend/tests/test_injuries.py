from types import SimpleNamespace

import pandas as pd
import pytest

from backend.api.injuries import adjust_injury


@pytest.mark.parametrize('status,practice,expected', [
    ('Out', 'Full Participation in Practice', 0),
    ('Doubtful', None, 2.5),
    ('Questionable', 'Limited Participation in Practice', 6.75),
    (None, 'Did Not Participate In Practice', 8),
    (None, 'Full Participation in Practice', 10),
])
def test_status_and_participation(status, practice, expected):
    metadata = dict(player_id='a', team='NE', season=2025, week=4,
                    feature_cutoff='2025-09-28T17:00:00Z')
    data = SimpleNamespace(injuries=pd.DataFrame([dict(
        gsis_id='a', team='NE', season=2025, week=4, report_status=status,
        practice_status=practice, report_primary_injury='Knee',
        observed_at='2025-09-27T12:00:00Z')]))
    result = adjust_injury(data, metadata, 10)
    assert result['projected_ppr_points'] == pytest.approx(expected)
    assert result['base_projected_ppr_points'] == 10
    assert result['injury_description'] == 'Knee'
    data.injuries['week'] = 3
    assert adjust_injury(data, metadata, 10)['availability'] == 'unknown'
    data.injuries['week'] = 4
    data.injuries['team'] = 'NYJ'
    assert adjust_injury(data, metadata, 10)['availability'] == 'unknown'


@pytest.mark.parametrize('roster', ['IR', 'RES', 'INA', 'PUP', 'NFI', 'SUS'])
def test_unavailable_roster_without_injury_feed(roster):
    result = adjust_injury(SimpleNamespace(injuries=pd.DataFrame()), dict(
        player_id='a', season=2025, week=4, roster_status=roster,
        feature_cutoff='2025-09-28T17:00:00Z'), 10)
    assert result['projected_ppr_points'] == 0
    assert result['availability'] == 'unavailable'
