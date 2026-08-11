from dataclasses import dataclass
from typing import Optional, Dict, Any
from collections import deque
from swiftplay.lob.book import OrderBook
from .microstructure import (
    spread,
    microprice,
    order_book_imbalance,
    order_flow_imbalance,
)
from .volatility import realized_volatility


@dataclass
class FeatureSnapshot:
    timestamp: int
    imbalance: Optional[float]
    microprice: Optional[float]
    ofi: float
    spread: Optional[float]
    realized_vol: Optional[float]


class FeaturePipeline:
    def __init__(self, vol_window: int = 20, imb_levels: int = 5):
        self.vol_window = vol_window
        self.imb_levels = imb_levels

        self.prev_state: Dict[str, Any] = {}
        self.price_history: deque[float] = deque(maxlen=vol_window)

    def compute(self, book: OrderBook) -> FeatureSnapshot:
        spr = spread(book)
        mprice = microprice(book)
        imb = order_book_imbalance(book, levels=self.imb_levels)
        ofi = order_flow_imbalance(book, self.prev_state)

        mid = book.mid_price
        if mid is not None:
            self.price_history.append(mid)

        rvol = realized_volatility(list(self.price_history), self.vol_window)

        bb = book.best_bid
        ba = book.best_ask
        self.prev_state = {
            "best_bid": bb,
            "best_bid_size": book.bids.get(bb, 0.0) if bb is not None else 0.0,
            "best_ask": ba,
            "best_ask_size": book.asks.get(ba, 0.0) if ba is not None else 0.0,
        }

        return FeatureSnapshot(
            timestamp=book.current_timestamp,
            imbalance=imb,
            microprice=mprice,
            ofi=ofi,
            spread=spr,
            realized_vol=rvol,
        )
