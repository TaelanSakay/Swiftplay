from swiftplay.decision.interfaces import (
    QuoteDecisionEngine,
    MarketState,
    Quote,
    QuoteReasoning,
)
from swiftplay.features.pipeline import FeatureSnapshot


class FixedSpreadStrategy(QuoteDecisionEngine):
    """
    A trivial strategy that places quotes at a fixed spread around the mid-price.
    Used primarily for testing the scaffolding and interfaces end-to-end.
    """

    def __init__(self, spread: float, order_qty: float):
        self.spread = spread
        self.order_qty = order_qty

    def generate_quote(
        self, state: MarketState, features: FeatureSnapshot, inventory: float
    ) -> Quote:
        mid_price = (state.bid_price + state.ask_price) / 2.0

        bid_price = mid_price - (self.spread / 2.0)
        ask_price = mid_price + (self.spread / 2.0)

        reasoning = QuoteReasoning(
            expected_value=self.spread,  # Trivial
            fill_probability_bid=0.5,  # Trivial
            fill_probability_ask=0.5,  # Trivial
            inventory_penalty=0.0,
            confidence=1.0,
            explanation="Fixed spread logic applied.",
        )

        return Quote(
            bid_price=bid_price,
            ask_price=ask_price,
            bid_qty=self.order_qty,
            ask_qty=self.order_qty,
            reasoning=reasoning,
        )
