from abc import ABC, abstractmethod
from typing import Iterator


class DataFeed(ABC):
    """
    Common interface for market data feeds (live and historical).
    """

    @abstractmethod
    def __iter__(self) -> Iterator[dict]:
        """
        Yields market updates formatted for the OrderBook simulator.
        Format: {'timestamp': int, 'bids': [[price, qty]], 'asks': [[price, qty]]}
        """
        pass
