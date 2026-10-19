"""Metrics and charts shared by training and standalone evaluation."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def metrics(actual, predicted):
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    if actual.shape != predicted.shape or actual.ndim != 1 or not len(actual):
        raise ValueError('Expected equal nonempty one-dimensional arrays')
    if not (np.isfinite(actual).all() and np.isfinite(predicted).all()):
        raise ValueError('Metrics require finite values')
    return dict(mae=float(mean_absolute_error(actual, predicted)),
                rmse=float(np.sqrt(mean_squared_error(actual, predicted))),
                r2=float(r2_score(actual, predicted)) if len(actual) > 1 else None,
                bias=float(np.mean(predicted - actual)))


def evaluate(output: Path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    predictions = pd.read_csv(output / 'test_predictions.csv')
    importance = pd.read_csv(output / 'feature_importance.csv')
    rows = []
    for position, frame in predictions.groupby('position'):
        for model in ['mean_3', 'mean_5', 'ridge', 'xgboost']:
            rows.append(dict(position=position, model=model, **metrics(frame.actual, frame[model])))
        fig, axes = plt.subplots(2, 2, figsize=(12, 9))
        axes[0, 0].scatter(frame.actual, frame.xgboost, alpha=.25, s=10)
        limits = [min(frame.actual.min(), frame.xgboost.min()), max(frame.actual.max(), frame.xgboost.max())]
        axes[0, 0].plot(limits, limits, 'k--')
        axes[0, 0].set(xlabel='Actual PPR', ylabel='Predicted PPR', title=f'{position}: actual vs predicted')
        comparison = pd.DataFrame(rows).query('position == @position').set_index('model')
        comparison[['mae', 'rmse']].plot.bar(ax=axes[0, 1], rot=0, title='Test error (lower is better)')
        top = importance[importance.position == position].nlargest(12, 'importance')
        axes[1, 0].barh(top.feature.iloc[::-1], top.importance.iloc[::-1])
        axes[1, 0].set_title('XGBoost normalized gain importance')
        axes[1, 1].hist(frame.xgboost - frame.actual, bins=35)
        axes[1, 1].axvline(0, color='black', linestyle='--')
        axes[1, 1].set(xlabel='Prediction minus actual PPR', title='Prediction error distribution')
        fig.tight_layout()
        fig.savefig(output / f'{position}_evaluation.png', dpi=160)
        plt.close(fig)
    comparison = pd.DataFrame(rows)
    comparison.to_csv(output / 'metrics.csv', index=False)
    return comparison


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('reports/ml'))
    print(evaluate(parser.parse_args().output).to_string(index=False))
