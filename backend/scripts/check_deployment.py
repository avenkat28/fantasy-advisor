"""Fail the backend build if its bundled inference artifacts cannot be loaded."""
import json
from pathlib import Path

from backend.api.data import DataRepository
from backend.api.predictions import PredictionService
from backend.scripts.build_player_stats import ROOT


def check_deployment(root: Path = ROOT) -> dict:
    if not (root / 'data/current.json').is_file():
        raise ValueError('Missing data/current.json. Commit the published snapshot before deploying.')
    repository = DataRepository(root)
    if repository.snapshot is None:
        raise ValueError('Deployment requires the published snapshot; remove FANTASY_PLAYERS/FANTASY_SCHEDULES overrides.')
    for name in ['players', 'schedules', 'rosters']:
        path = root / repository.snapshot[name]
        if not path.is_file():
            raise ValueError(f'Missing published {name} file: {path.relative_to(root)}')
    if repository.players.empty or repository.context.empty or repository.rosters.empty:
        raise ValueError('Published player, schedule and roster datasets must be nonempty.')
    predictions = PredictionService(repository)
    missing = {'RB', 'WR'} - set(predictions.models)
    if missing:
        raise ValueError(f'Missing or incompatible model bundles: {sorted(missing)}')
    if not repository.report or repository.history is None:
        raise ValueError('Missing reports/ml/training_report.json or reports/ml/test_predictions.csv.')
    return {
        'ready': True,
        'models': sorted(predictions.models),
        'snapshot_observed_at': repository.snapshot['observed_at'],
        'season': repository.snapshot['season'],
        'player_rows': len(repository.players),
        'roster_rows': len(repository.rosters),
    }


if __name__ == '__main__':
    print(json.dumps(check_deployment(), indent=2))
