"""
Queue Position Tracking

Binance's public depth stream only provides L2 data (aggregate quantity
per price level), not L3 (individual order-level data). This means we
cannot distinguish whether a depth decrease at a price level is due to
fills or cancellations, or whether it happened ahead of or behind our
resting order in the queue.

Our approximation: We treat all depth decreases at a price level as
reducing the volume
ahead of our order. This is the standard simplifying assumption used in LOB backtesting
without L3 data. It tends to be slightly optimistic on fill probability, but ensures
a tractable simulation of queue priority.
"""

from typing import List
from .fills import FillEvent


class TrackedOrder:
    def __init__(
        self,
        order_id: str,
        side: str,
        price: float,
        original_qty: float,
        volume_ahead: float,
        timestamp: int,
    ):
        self.order_id = order_id
        self.side = side
        self.price = price
        self.original_qty = original_qty
        self.remaining_qty = original_qty
        self.volume_ahead = volume_ahead
        self.creation_timestamp = timestamp
        self.is_filled = False
        self.is_cancelled = False

    def process_depth_decrease(
        self, decrease_qty: float, current_timestamp: int
    ) -> List[FillEvent]:
        """
        Process a decrease in depth at our price level.
        Any decrease first consumes volume_ahead. Once volume_ahead is 0,
        further decreases result in our order getting filled.
        """
        if self.is_filled or self.is_cancelled:
            return []

        fills = []
        if self.volume_ahead > 0:
            consumed_ahead = min(self.volume_ahead, decrease_qty)
            self.volume_ahead -= consumed_ahead
            decrease_qty -= consumed_ahead

        if decrease_qty > 0 and self.volume_ahead == 0:
            fill_qty = min(self.remaining_qty, decrease_qty)
            self.remaining_qty -= fill_qty

            if self.remaining_qty <= 0.00000001:  # Float precision epsilon
                self.remaining_qty = 0.0
                self.is_filled = True

            fills.append(
                FillEvent(
                    order_id=self.order_id,
                    fill_price=self.price,
                    fill_quantity=fill_qty,
                    timestamp=current_timestamp,
                    remaining_quantity=self.remaining_qty,
                )
            )

        return fills

    def process_cross(
        self, cross_qty: float, current_timestamp: int
    ) -> List[FillEvent]:
        """
        Process a trade that crosses our price level entirely.
        This ignores volume_ahead because the entire level is wiped out.
        """
        if self.is_filled or self.is_cancelled:
            return []

        fill_qty = min(self.remaining_qty, cross_qty)
        self.remaining_qty -= fill_qty

        if self.remaining_qty <= 0.00000001:
            self.remaining_qty = 0.0
            self.is_filled = True

        return [
            FillEvent(
                order_id=self.order_id,
                fill_price=self.price,  # Always fill at resting order's price
                fill_quantity=fill_qty,
                timestamp=current_timestamp,
                remaining_quantity=self.remaining_qty,
            )
        ]
