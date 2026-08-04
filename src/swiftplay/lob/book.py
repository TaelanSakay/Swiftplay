from typing import Dict, List
from .interfaces import OrderBookSimulator
from .fills import FillEvent
from .queue_position import TrackedOrder


class OrderBook(OrderBookSimulator):
    def __init__(self) -> None:
        self.bids: Dict[float, float] = {}  # price -> qty
        self.asks: Dict[float, float] = {}  # price -> qty
        self.tracked_orders: Dict[str, TrackedOrder] = {}
        self.recent_fills: List[FillEvent] = []
        self.current_timestamp: int = 0

    @property
    def best_bid(self) -> float | None:
        valid_bids = [p for p, q in self.bids.items() if q > 0]
        return max(valid_bids) if valid_bids else None

    @property
    def best_ask(self) -> float | None:
        valid_asks = [p for p, q in self.asks.items() if q > 0]
        return min(valid_asks) if valid_asks else None

    @property
    def mid_price(self) -> float | None:
        bb = self.best_bid
        ba = self.best_ask
        if bb is not None and ba is not None:
            return (bb + ba) / 2.0
        return None

    @property
    def spread(self) -> float | None:
        bb = self.best_bid
        ba = self.best_ask
        if bb is not None and ba is not None:
            return ba - bb
        return None

    def process_market_update(self, update: dict) -> None:
        """
        Processes a depth update.
        update format: {'timestamp': int, 'bids': [[p, q]], 'asks': [[p, q]]}
        """
        self.current_timestamp = update.get("timestamp", self.current_timestamp)

        self._process_side_update(update.get("bids", []), self.bids, "BUY")
        self._process_side_update(update.get("asks", []), self.asks, "SELL")

        self._check_crosses()

    def _process_side_update(
        self, levels: list, side_book: Dict[float, float], side: str
    ) -> None:
        for price, qty in levels:
            price = float(price)
            qty = float(qty)

            old_qty = side_book.get(price, 0.0)
            side_book[price] = qty

            if qty < old_qty:
                decrease = old_qty - qty
                for order in self.tracked_orders.values():
                    if (
                        order.side == side
                        and order.price == price
                        and not order.is_filled
                        and not order.is_cancelled
                    ):
                        fills = order.process_depth_decrease(
                            decrease, self.current_timestamp
                        )
                        self.recent_fills.extend(fills)

    def place_order(self, order_id: str, side: str, price: float, qty: float) -> None:
        if order_id in self.tracked_orders:
            raise ValueError(f"Order ID {order_id} already exists.")

        volume_ahead = 0.0
        if side == "BUY":
            volume_ahead = self.bids.get(price, 0.0)
        else:
            volume_ahead = self.asks.get(price, 0.0)

        order = TrackedOrder(
            order_id, side, price, qty, volume_ahead, self.current_timestamp
        )
        self.tracked_orders[order_id] = order

        self._check_crosses()

    def cancel_order(self, order_id: str) -> None:
        if order_id in self.tracked_orders:
            self.tracked_orders[order_id].is_cancelled = True

    def get_recent_fills(self) -> List[FillEvent]:
        fills = self.recent_fills.copy()
        self.recent_fills.clear()
        return fills

    def _check_crosses(self) -> None:
        """
        Check if the market book has crossed our resting orders.
        """
        bb = self.best_bid
        ba = self.best_ask

        for order in self.tracked_orders.values():
            if order.is_filled or order.is_cancelled:
                continue

            cross_qty = 0.0
            if order.side == "BUY":
                # Crossed if the market's best ask drops <= our bid price
                if ba is not None and ba <= order.price:
                    valid = (q for p, q in self.asks.items() if p <= order.price)
                    cross_qty = sum(valid)
            else:  # SELL
                # Crossed if the market's best bid rises >= our ask price
                if bb is not None and bb >= order.price:
                    valid = (q for p, q in self.bids.items() if p >= order.price)
                    cross_qty = sum(valid)

            if cross_qty > 0:
                fills = order.process_cross(cross_qty, self.current_timestamp)
                self.recent_fills.extend(fills)
