import math
import os
from swiftplay.backtest.metrics import sharpe_ratio, max_drawdown, win_rate
from swiftplay.backtest.engine import BacktestRunner, BacktestConfig
from swiftplay.backtest.compare import run_comparison
from swiftplay.decision.fixed_spread import FixedSpreadStrategy
from swiftplay.decision.strategies import InventoryAwareStrategy
from swiftplay.decision.ev_quoting import EVQuotingStrategy
from swiftplay.decision.heuristic_fill_estimator import HeuristicFillEstimator
from swiftplay.data_feed.replay import HistoricalReplayFeed


def test_metrics_math() -> None:
    # Known PnL series: linearly increasing by 1.0 each step
    # PnL: 0.0, 1.0, 2.0, 3.0, 4.0
    # Returns: 1.0, 1.0, 1.0, 1.0
    # Mean return = 1.0, std dev = 0.0
    pnl = [0.0, 1.0, 2.0, 3.0, 4.0]

    assert max_drawdown(pnl) == 0.0
    # Sharpe ratio with 0 variance is mathematically defined here
    # as 0.0 per requirements
    assert sharpe_ratio(pnl) == 0.0
    assert win_rate(pnl) == 1.0

    # Series with drawdown
    pnl_dd = [0.0, 10.0, 5.0, 15.0, 8.0]
    # Drop from 10 to 5 (dd = 5)
    # Drop from 15 to 8 (dd = 7) -> max
    assert max_drawdown(pnl_dd) == 7.0

    assert sharpe_ratio(pnl_dd) != 0.0


def test_integration_backtest_runner() -> None:
    """
    NOTE: The sample data used here is extremely short (~2 mins).
    This is for testing execution fidelity, not true strategy performance.
    """
    sample_path = "data/sample_btcusd_depth.jsonl"
    if not os.path.exists(sample_path):
        return

    strategy = FixedSpreadStrategy(spread=10.0, order_qty=1.0)
    feed = HistoricalReplayFeed(sample_path, speed_multiplier=None)
    config = BacktestConfig(initial_capital=100000.0)

    runner = BacktestRunner(strategy, feed, config)
    history = runner.run()

    assert len(history) > 0
    assert runner.quotes_placed > 0

    pnl_series = [step.pnl for step in history]
    # Check that we computed PnL correctly (shouldn't just be NaNs)
    assert not math.isnan(pnl_series[-1])


def test_integration_run_comparison() -> None:
    sample_path = "data/sample_btcusd_depth.jsonl"
    if not os.path.exists(sample_path):
        return

    config = BacktestConfig(initial_capital=100000.0)

    strategies = {
        "Fixed": FixedSpreadStrategy(spread=10.0, order_qty=1.0),
        "Inventory": InventoryAwareStrategy(half_spread=5.0, quote_qty=1.0),
        "EV": EVQuotingStrategy(
            fill_estimator=HeuristicFillEstimator(decay_factor=5000.0),
            quote_qty=1.0,
            max_inventory=10.0,
        ),
    }

    result = run_comparison(strategies, sample_path, config)

    assert len(result.results) == 3
    for name in ["Fixed", "Inventory", "EV"]:
        assert name in result.results
        assert "total_pnl" in result.results[name]

    markdown = result.to_markdown_table()
    assert "Strategy" in markdown
    assert "Fixed" in markdown
    assert "Inventory" in markdown
    assert "EV" in markdown
