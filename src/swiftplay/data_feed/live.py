from typing import Iterator
from .interfaces import DataFeed


class LiveBinanceFeed(DataFeed):
    """
    Live WebSocket feed stub.
    Implements DataFeed interface so the backtester/runner can treat live
    and historical feeds identically.
    Not implemented yet.
    """

    def __init__(self, symbol: str = "btcusd"):
        self.symbol = symbol

    def __iter__(self) -> Iterator[dict]:
        raise NotImplementedError("Live Binance feed is not yet implemented.")
