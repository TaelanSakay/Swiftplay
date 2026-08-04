from abc import ABC, abstractmethod
from typing import List
from .fills import FillEvent


class OrderBookSimulator(ABC):
    """
    Interface for the limit order book simulator.
    Decouples the decision engine from the mechanics of the book.
    """

    @property
    @abstractmethod
    def best_bid(self) -> float | None:
        pass

    @property
    @abstractmethod
    def best_ask(self) -> float | None:
        pass

    @property
    @abstractmethod
    def mid_price(self) -> float | None:
        pass

    @property
    @abstractmethod
    def spread(self) -> float | None:
        pass

    @abstractmethod
    def process_market_update(self, update: dict) -> None:
        """
        Feed snapshot or diff data to the book.
        Update format should match Binance L2 depth
        (e.g. {'bids': [[price, qty]], 'asks': [[price, qty]]}).
        """
        pass

    @abstractmethod
    def place_order(self, order_id: str, side: str, price: float, qty: float) -> None:
        """
        Place our own limit order into the simulated book.
        side should be 'BUY' or 'SELL'.
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> None:
        """
        Cancel an active order we placed.
        """
        pass

    @abstractmethod
    def get_recent_fills(self) -> List[FillEvent]:
        """
        Retrieve and clear fills generated since the last call to this method.
        """
        pass
