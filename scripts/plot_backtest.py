import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from swiftplay.backtest.compare import run_comparison
from swiftplay.backtest.engine import BacktestConfig, BacktestRunner
from swiftplay.data_feed.replay import HistoricalReplayFeed
from swiftplay.decision.ev_quoting import EVQuotingStrategy
from swiftplay.decision.fixed_spread import FixedSpreadStrategy
from swiftplay.decision.heuristic_fill_estimator import HeuristicFillEstimator
from swiftplay.decision.interfaces import QuoteDecisionEngine
from swiftplay.decision.strategies import InventoryAwareStrategy
from swiftplay.risk import RiskConfig, RiskManager


def build_strategy(name: str) -> QuoteDecisionEngine:
    if name == "fixed_spread":
        return FixedSpreadStrategy(spread=10.0, order_qty=1.0)
    if name == "inventory_aware":
        return InventoryAwareStrategy(half_spread=5.0, quote_qty=1.0)
    if name == "ev_quoting":
        return EVQuotingStrategy(
            fill_estimator=HeuristicFillEstimator(decay_factor=5000.0),
            quote_qty=1.0,
            max_inventory=10.0,
        )
    raise ValueError(f"Unsupported strategy: {name}")


def run_single_strategy(strategy_name: str, data_path: str) -> tuple[list[float], list[float], list[int], str]:
    strategy = build_strategy(strategy_name)
    feed = HistoricalReplayFeed(data_path, speed_multiplier=None)
    config = BacktestConfig(
        initial_capital=100000.0,
        risk_manager=RiskManager(
            100000.0,
            RiskConfig(max_inventory=10.0, drawdown_threshold=0.0002),
        ),
    )
    runner = BacktestRunner(strategy, feed, config)
    history = runner.run()

    pnl_series = [step.pnl for step in history]
    inventory_series = [step.inventory for step in history]
    timestamps = [idx for idx in range(len(history))]
    return pnl_series, inventory_series, timestamps, strategy_name


def plot_single_strategy(strategy_name: str, data_path: str) -> Path:
    pnl, inventory, indices, _ = run_single_strategy(strategy_name, data_path)

    output_dir = Path("docs")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "backtest_pnl_inventory.png"

    fig, (ax_pnl, ax_inv) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    fig.suptitle(f"{strategy_name.replace('_', ' ').title()} Backtest: PnL and Inventory")

    ax_pnl.plot(indices, pnl, color="tab:blue", linewidth=2)
    ax_pnl.set_ylabel("Cumulative PnL ($)")
    ax_pnl.grid(True, alpha=0.3)
    ax_pnl.set_title("Cumulative PnL")

    ax_inv.plot(indices, inventory, color="tab:orange", linewidth=2)
    ax_inv.set_xlabel("Tick Index")
    ax_inv.set_ylabel("Inventory (BTC)")
    ax_inv.grid(True, alpha=0.3)
    ax_inv.set_title("Inventory")

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(output_path, dpi=200)
    plt.close(fig)
    return output_path


def plot_strategy_comparison(data_path: str) -> Path:
    names = ["fixed_spread", "inventory_aware", "ev_quoting"]
    output_dir = Path("docs")
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "backtest_strategy_comparison.png"

    fig, ax = plt.subplots(figsize=(12, 6))
    for name in names:
        pnl, _, indices, _ = run_single_strategy(name, data_path)
        label = name.replace("_", " ").title()
        ax.plot(indices, pnl, linewidth=2, label=label)

    ax.set_xlabel("Tick Index")
    ax.set_ylabel("Cumulative PnL ($)")
    ax.set_title("Strategy Comparison: Cumulative PnL")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate backtest visualizations for Swiftplay.")
    parser.add_argument("--strategy", default="ev_quoting", choices=["fixed_spread", "inventory_aware", "ev_quoting"], help="Strategy to plot")
    parser.add_argument("--data", default="data/sample_btcusd_depth.jsonl", help="Path to historical depth file")
    args = parser.parse_args()

    single_path = plot_single_strategy(args.strategy, args.data)
    comparison_path = plot_strategy_comparison(args.data)

    print(f"Saved single-strategy plot: {single_path} ({single_path.stat().st_size} bytes)")
    print(f"Saved comparison plot: {comparison_path} ({comparison_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
