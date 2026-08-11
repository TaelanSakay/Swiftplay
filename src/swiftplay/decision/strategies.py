from .interfaces import QuoteDecisionEngine, Quote, QuoteReasoning, MarketState
from swiftplay.features.pipeline import FeatureSnapshot


class InventoryAwareStrategy(QuoteDecisionEngine):
    """
    A mid-tier strategy that uses a fixed spread but skews prices based on inventory.
    """

    def __init__(
        self,
        half_spread: float = 1.0,
        quote_qty: float = 1.0,
        max_inventory: float = 10.0,
        skew_factor: float = 2.0,
    ):
        self.half_spread = half_spread
        self.quote_qty = quote_qty
        self.max_inventory = max_inventory
        self.skew_factor = skew_factor

    def generate_quote(
        self, state: MarketState, features: FeatureSnapshot, inventory: float
    ) -> Quote:
        ref_price = features.microprice
        if ref_price is None:
            ref_price = (state.bid_price + state.ask_price) / 2.0

        normalized_inv = max(
            -1.0,
            min(1.0, inventory / self.max_inventory if self.max_inventory > 0 else 0),
        )

        # If long (normalized_inv > 0), shift quotes down to encourage selling
        # and discourage buying
        price_skew = -normalized_inv * self.skew_factor

        bid = ref_price - self.half_spread + price_skew
        ask = ref_price + self.half_spread + price_skew

        # Ensure we don't cross the market too aggressively
        bid = min(bid, state.bid_price)
        ask = max(ask, state.ask_price)

        reasoning = QuoteReasoning(
            expected_value=0.0,
            fill_probability_bid=0.0,
            fill_probability_ask=0.0,
            inventory_penalty=normalized_inv,
            confidence=1.0,
            explanation=(
                f"Fixed spread shifted by {price_skew:.2f} "
                f"due to inventory {inventory}"
            ),
        )

        return Quote(
            bid_price=bid,
            ask_price=ask,
            bid_qty=self.quote_qty,
            ask_qty=self.quote_qty,
            reasoning=reasoning,
        )
