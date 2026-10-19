"""Standalone inference; load only trusted local joblib artifacts."""
import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from backend.ml.schema import FEATURES, feature_frame


def predict_points(model_path: Path, features: dict) -> dict:
    bundle = joblib.load(model_path)
    if bundle['metadata']['features'] != FEATURES:
        raise ValueError('Saved model feature schema is incompatible')
    # Explicit dtype allows a single record containing null history values.
    if any(v is not None and not isinstance(v, (int, float, bool, np.number)) for v in features.values()):
        raise ValueError('Features must be numbers, booleans, or null')
    frame = feature_frame(pd.DataFrame([features], dtype=float), strict=True)
    value = float(bundle['model'].predict(frame)[0])
    if not np.isfinite(value):
        raise ValueError('Model returned a nonfinite prediction')
    return {'predicted_fantasy_points_ppr': value, 'metadata': bundle['metadata']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--features', type=Path, required=True, help='JSON object with approved features only')
    args = parser.parse_args()
    print(json.dumps(predict_points(args.model, json.loads(args.features.read_text())), indent=2))


if __name__ == '__main__':
    main()
