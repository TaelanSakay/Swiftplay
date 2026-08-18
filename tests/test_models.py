import math
import os

import pytest

from swiftplay.backtest.compare import run_comparison
from swiftplay.backtest.engine import BacktestConfig
from swiftplay.data_feed.replay import HistoricalReplayFeed
from swiftplay.decision.ev_quoting import EVQuotingStrategy
from swiftplay.decision.heuristic_fill_estimator import HeuristicFillEstimator
from swiftplay.decision.interfaces import MarketState
from swiftplay.features.pipeline import FeatureSnapshot
from swiftplay.models.trained_fill_estimator import TrainedFillProbabilityEstimator


ARTIFACT_DIR = "src/swiftplay/models/artifacts"
SAMPLE_PATH = "data/sample_btcusd_depth.jsonl"


@pytest.mark.skipif(
    not os.path.exists(os.path.join(ARTIFACT_DIR, "model_summary.pkl")),
    reason="trained model artifact is not available",
)
def test_trained_estimator_returns_probability() -> None:
    estimator = TrainedFillProbabilityEstimator(ARTIFACT_DIR)
    state = MarketState(
        bid_price=100.0,
        ask_price=101.0,
        bid_qty=5.0,
        ask_qty=4.0,
        timestamp=1,
    )
    features = FeatureSnapshot(
        timestamp=1,
        imbalance=0.1,
        microprice=100.4,
        ofi=0.2,
        spread=1.0,
        realized_vol=0.01,
    )

    probability = estimator.estimate(state, features, 99.5, "BUY")

    assert math.isfinite(probability)
    assert 0.0 <= probability <= 1.0


@pytest.mark.skipif(
    not os.path.exists(SAMPLE_PATH) or not os.path.exists(
        os.path.join(ARTIFACT_DIR, "model_summary.pkl")
    ),
    reason="sample data or trained model artifact is not available",
)
def test_trained_vs_heuristic_comparison() -> None:
    trained = TrainedFillProbabilityEstimator(ARTIFACT_DIR)
    strategies = {
        "Heuristic": EVQuotingStrategy(
            fill_estimator=HeuristicFillEstimator(decay_factor=5000.0),
            quote_qty=1.0,
            max_inventory=10.0,
        ),
        "Trained": EVQuotingStrategy(
            fill_estimator=trained,
            quote_qty=1.0,
            max_inventory=10.0,
        ),
    }

    result = run_comparison(strategies, SAMPLE_PATH, BacktestConfig())

    assert set(result.results) == {"Heuristic", "Trained"}
    for metrics in result.results.values():
        assert math.isfinite(metrics["total_pnl"])
        assert math.isfinite(metrics["sharpe_ratio"])
        assert 0.0 <= metrics["fill_rate"] <= 1.0
