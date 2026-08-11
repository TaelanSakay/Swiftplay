import math
from typing import Dict, Any
from dataclasses import dataclass
from swiftplay.decision.interfaces import QuoteDecisionEngine
from swiftplay.data_feed.replay import HistoricalReplayFeed
from .engine import BacktestRunner, BacktestConfig
from .metrics import sharpe_ratio, max_drawdown, win_rate


@dataclass
class ComparisonResult:
    results: Dict[str, Dict[str, Any]]

    def to_markdown_table(self) -> str:
        if not self.results:
            return "No results."

        headers = [
            "Strategy",
            "Total PnL",
            "Sharpe",
            "Max DD",
            "Win Rate",
            "Fill Rate",
            "Avg Inv",
        ]

        # Format rows
        rows = []
        for name, metrics in self.results.items():
            row = [
                name,
                f"${metrics.get('total_pnl', 0.0):.2f}",
                f"{metrics.get('sharpe_ratio', 0.0):.2f}",
                f"${metrics.get('max_drawdown', 0.0):.2f}",
                f"{metrics.get('win_rate', 0.0) * 100:.1f}%",
                f"{metrics.get('fill_rate', 0.0) * 100:.2f}%",
                f"{metrics.get('average_inventory', 0.0):.2f}",
            ]
            rows.append(row)

        # Build markdown string
        header_str = "| " + " | ".join(headers) + " |"
        sep_str = "|" + "|".join(["---"] * len(headers)) + "|"

        table = [header_str, sep_str]
        for row in rows:
            table.append("| " + " | ".join(row) + " |")

        return "\n".join(table)


def run_comparison(
    strategies: Dict[str, QuoteDecisionEngine],
    data_feed_path: str,
    config: BacktestConfig,
) -> ComparisonResult:

    results = {}

    for name, strategy in strategies.items():
        feed = HistoricalReplayFeed(data_feed_path, speed_multiplier=None)
        runner = BacktestRunner(strategy, feed, config)
        history = runner.run()

        if not history:
            continue

        pnl_series = [step.pnl for step in history]
        total_pnl = pnl_series[-1] if pnl_series else 0.0
        sharpe = sharpe_ratio(pnl_series)
        mdd = max_drawdown(pnl_series)
        w_rate = win_rate(pnl_series)

        fill_rate = 0.0
        if runner.quotes_placed > 0:
            fill_rate = runner.quotes_filled / runner.quotes_placed

        avg_inv = sum(step.inventory for step in history) / len(history)

        # Calculate inventory standard deviation
        inv_variance = sum((step.inventory - avg_inv) ** 2 for step in history) / len(
            history
        )
        inv_std = math.sqrt(inv_variance)

        results[name] = {
            "total_pnl": total_pnl,
            "sharpe_ratio": sharpe,
            "max_drawdown": mdd,
            "win_rate": w_rate,
            "fill_rate": fill_rate,
            "average_inventory": avg_inv,
            "inventory_std": inv_std,
        }

    return ComparisonResult(results=results)
