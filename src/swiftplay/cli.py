import argparse
import logging
import os
import sys
from typing import Dict
from swiftplay.common.logging_setup import setup_logging
from swiftplay.backtest.engine import BacktestConfig
from swiftplay.backtest.compare import run_comparison
from swiftplay.decision.interfaces import QuoteDecisionEngine
from swiftplay.decision.fixed_spread import FixedSpreadStrategy
from swiftplay.decision.strategies import InventoryAwareStrategy
from swiftplay.decision.ev_quoting import EVQuotingStrategy
from swiftplay.decision.heuristic_fill_estimator import HeuristicFillEstimator

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Swiftplay Market Maker")
    subparsers = parser.add_subparsers(dest="command")

    # Existing live command (placeholder)
    live_parser = subparsers.add_parser("live", help="Run strategy in live mode")
    live_parser.add_argument(
        "--strategy", type=str, default="fixed", help="Strategy to run (default: fixed)"
    )

    # Backtest command
    backtest_parser = subparsers.add_parser("backtest", help="Run backtest comparison")
    backtest_parser.add_argument(
        "--data", type=str, required=True, help="Path to historical L2 depth JSONL file"
    )
    backtest_parser.add_argument(
        "--strategies",
        type=str,
        default="fixed_spread,inventory_aware,ev_quoting",
        help="Comma-separated list of strategies to run",
    )

    # Benchmark command
    benchmark_parser = subparsers.add_parser(
        "benchmark", help="Run benchmark on market data"
    )
    benchmark_parser.add_argument(
        "--data",
        type=str,
        default="data/sample_btcusd_depth.jsonl",
        help="Path to historical L2 depth JSONL file",
    )

    args = parser.parse_args()
    setup_logging()

    if args.command == "live":
        logger.info(f"Starting Swiftplay with strategy: {args.strategy}")
        # Placeholder: Initialize and run the selected strategy

    elif args.command == "backtest":
        logger.info(f"Running backtest with data: {args.data}")

        if not os.path.exists(args.data):
            logger.error(f"Data file not found: {args.data}")
            sys.exit(1)

        strategy_names = args.strategies.split(",")
        strategies: Dict[str, QuoteDecisionEngine] = {}

        for name in strategy_names:
            name = name.strip()
            if name == "fixed_spread":
                strategies["Fixed Spread"] = FixedSpreadStrategy(
                    spread=10.0, order_qty=1.0
                )
            elif name == "inventory_aware":
                strategies["Inventory Aware"] = InventoryAwareStrategy(
                    half_spread=5.0, quote_qty=1.0
                )
            elif name == "ev_quoting":
                strategies["EV Quoting"] = EVQuotingStrategy(
                    fill_estimator=HeuristicFillEstimator(decay_factor=5000.0),
                    quote_qty=1.0,
                    max_inventory=10.0,
                )
            else:
                logger.warning(f"Unknown strategy: {name}")

        if not strategies:
            logger.error("No valid strategies provided.")
            sys.exit(1)

        config = BacktestConfig(initial_capital=100000.0)
        result = run_comparison(strategies, args.data, config)

        print("\nBacktest Comparison Results:")
        print(result.to_markdown_table())
        print(
            "\nNote: Current sample data is very short. "
            "Use a larger dataset for meaningful metrics."
        )

    elif args.command == "benchmark":
        logger.info(f"Running benchmark with data: {args.data}")

        if not os.path.exists(args.data):
            logger.error(f"Data file not found: {args.data}")
            sys.exit(1)

        import subprocess

        benchmark_script = os.path.join(
            os.path.dirname(__file__), "..", "..", "scripts", "benchmark.py"
        )
        benchmark_script = os.path.abspath(benchmark_script)

        subprocess.run(
            [sys.executable, benchmark_script, "--data", args.data], check=True
        )

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
