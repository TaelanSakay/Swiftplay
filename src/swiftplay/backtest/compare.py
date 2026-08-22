from typing import Any, Dict, Mapping
from dataclasses import dataclass
from swiftplay.decision.interfaces import QuoteDecisionEngine
from swiftplay.data_feed.replay import HistoricalReplayFeed
from .engine import BacktestRunner, BacktestConfig
from .metrics import (
    average_inventory,
    fill_rate as calculate_fill_rate,
    inventory_std,
    max_drawdown,
    sharpe_ratio,
    win_rate,
)


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
            "Max Abs Inv",
            "Breaker",
            "Invalid Quotes",
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
                f"{metrics.get('max_abs_inventory', 0.0):.2f}",
                (
                    "active"
                    if metrics.get("circuit_breaker_active", False)
                    else "inactive"
                ),
                str(metrics.get("invalid_quotes", 0)),
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
    strategies: Mapping[str, QuoteDecisionEngine],
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

        fill_rate = calculate_fill_rate(runner.filled_volume, runner.quoted_volume)
        inventories = [step.inventory for step in history]
        avg_inv = average_inventory(inventories)
        inventory_deviation = inventory_std(inventories)
        max_abs_inventory = max((abs(value) for value in inventories), default=0.0)

        results[name] = {
            "total_pnl": total_pnl,
            "sharpe_ratio": sharpe,
            "max_drawdown": mdd,
            "win_rate": w_rate,
            "fill_rate": fill_rate,
            "average_inventory": avg_inv,
            "inventory_std": inventory_deviation,
            "max_abs_inventory": max_abs_inventory,
            "circuit_breaker_active": runner.risk_manager.circuit_breaker_active,
            "invalid_quotes": runner.invalid_quotes,
        }

    return ComparisonResult(results=results)
