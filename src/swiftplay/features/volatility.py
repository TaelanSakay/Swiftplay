import math
from typing import Optional, List


def realized_volatility(price_history: List[float], window: int) -> Optional[float]:
    """
    Returns rolling realized volatility (std dev of log returns) over the given window.
    Returns None if price_history has fewer than 2 data points or invalid prices.
    """
    prices = price_history[-window:] if window > 0 else price_history

    if len(prices) < 2:
        return None

    returns = []
    for i in range(1, len(prices)):
        prev = prices[i - 1]
        curr = prices[i]

        if prev <= 0 or curr <= 0:
            return None

        returns.append(math.log(curr / prev))

    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / len(returns)
    return math.sqrt(variance)
