import math
from typing import List


def sharpe_ratio(
    pnl_series: List[float], periods_per_year: float = 31536000.0
) -> float:
    """
    Computes annualized Sharpe Ratio from a cumulative PnL series.
    periods_per_year defaults to seconds in a year (assuming 1 update per second avg).
    Assumes a zero risk-free rate (common simplification for quick backtests).
    """
    if len(pnl_series) < 2:
        return 0.0

    # Extract returns from cumulative PnL
    returns = [pnl_series[i] - pnl_series[i - 1] for i in range(1, len(pnl_series))]

    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    std_dev = math.sqrt(variance)

    if std_dev == 0.0:
        return 0.0

    # Annualize
    return (mean_return / std_dev) * math.sqrt(periods_per_year)


def max_drawdown(pnl_series: List[float]) -> float:
    """
    Computes maximum drawdown (drop from peak) in the PnL series.
    Returns a positive float representing the loss amount.
    """
    if not pnl_series:
        return 0.0

    peak = pnl_series[0]
    max_dd = 0.0

    for pnl in pnl_series:
        if pnl > peak:
            peak = pnl
        dd = peak - pnl
        if dd > max_dd:
            max_dd = dd

    return max_dd


def win_rate(pnl_series: List[float]) -> float:
    """
    Returns percentage of ticks where PnL increased or stayed flat.
    """
    if len(pnl_series) < 2:
        return 0.0

    wins = sum(
        1 for i in range(1, len(pnl_series)) if pnl_series[i] >= pnl_series[i - 1]
    )
    return wins / (len(pnl_series) - 1)


def fill_rate(filled_volume: float, quoted_volume: float) -> float:
    """Return filled volume divided by quoted volume (0.0 if no quoted volume)."""
    try:
        if quoted_volume <= 0.0:
            return 0.0
        return filled_volume / quoted_volume
    except Exception:
        return 0.0


def average_inventory(inventories: List[float]) -> float:
    """Return average inventory over a series. Returns 0.0 for empty input."""
    if not inventories:
        return 0.0
    return sum(inventories) / len(inventories)


def inventory_std(inventories: List[float]) -> float:
    """Return standard deviation of inventory series (0.0 for empty or constant)."""
    if not inventories:
        return 0.0
    mean = sum(inventories) / len(inventories)
    variance = sum((x - mean) ** 2 for x in inventories) / len(inventories)
    return math.sqrt(variance)
