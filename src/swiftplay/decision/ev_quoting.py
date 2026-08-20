from .interfaces import (
    QuoteDecisionEngine,
    Quote,
    QuoteReasoning,
    MarketState,
    FillProbabilityEstimator,
)
from .inventory import compute_inventory_penalty
from swiftplay.features.pipeline import FeatureSnapshot


class EVQuotingStrategy(QuoteDecisionEngine):
    """
    A strategy that calculates bid and ask quotes by maximizing expected value (EV).
    EV = (fill_probability * expected_edge) - inventory_penalty
    """

    def __init__(
        self,
        fill_estimator: FillProbabilityEstimator,
        quote_qty: float = 1.0,
        max_inventory: float = 10.0,
        risk_aversion: float = 1.0,
        tick_size: float = 0.1,
        levels_to_scan: int = 10,
        min_quantity_scale: float = 0.3,
    ):
        self.fill_estimator = fill_estimator
        self.quote_qty = quote_qty
        self.max_inventory = max_inventory
        self.risk_aversion = risk_aversion
        self.tick_size = tick_size
        self.levels_to_scan = levels_to_scan
        self.min_quantity_scale = min_quantity_scale

    def generate_quote(
        self, state: MarketState, features: FeatureSnapshot, inventory: float
    ) -> Quote:
        if state.bid_price >= state.ask_price:
            reasoning = QuoteReasoning(
                expected_value=0.0,
                fill_probability_bid=0.0,
                fill_probability_ask=0.0,
                inventory_penalty=0.0,
                confidence=0.0,
                explanation="Skipped quote because the market book is crossed or locked.",
            )
            return Quote(
                bid_price=None,
                ask_price=None,
                bid_qty=None,
                ask_qty=None,
                reasoning=reasoning,
            )

        ref_price = features.microprice
        if ref_price is None:
            ref_price = (state.bid_price + state.ask_price) / 2.0

        best_bid_ev, best_bid_price, best_bid_prob = float("-inf"), None, 0.0
        best_ask_ev, best_ask_price, best_ask_prob = float("-inf"), None, 0.0

        # Scan potential bid prices
        bid_penalty = compute_inventory_penalty(
            inventory, self.max_inventory, "BUY", self.risk_aversion
        )
        for i in range(self.levels_to_scan):
            price = state.bid_price - (i * self.tick_size)
            prob = self.fill_estimator.estimate(state, features, price, "BUY")
            edge = ref_price - price
            ev = (prob * edge) - bid_penalty
            if ev > best_bid_ev:
                best_bid_ev, best_bid_price, best_bid_prob = ev, price, prob

        # Scan potential ask prices
        ask_penalty = compute_inventory_penalty(
            inventory, self.max_inventory, "SELL", self.risk_aversion
        )
        for i in range(self.levels_to_scan):
            price = state.ask_price + (i * self.tick_size)
            prob = self.fill_estimator.estimate(state, features, price, "SELL")
            edge = price - ref_price
            ev = (prob * edge) - ask_penalty
            if ev > best_ask_ev:
                best_ask_ev, best_ask_price, best_ask_prob = ev, price, prob

        # If confidence (prob) is extremely low, or EV is negative,
        # we can widen or cancel.
        # For simplicity, we just output the EV maximizing quotes.
        confidence = (best_bid_prob + best_ask_prob) / 2.0

        explanation = f"Maximized EV around microprice {ref_price:.2f}. "
        if abs(inventory) > self.max_inventory * 0.5:
            explanation += f"Skewing quotes to manage {inventory} inventory."

        reasoning = QuoteReasoning(
            expected_value=best_bid_ev + best_ask_ev,
            fill_probability_bid=best_bid_prob,
            fill_probability_ask=best_ask_prob,
            inventory_penalty=max(abs(bid_penalty), abs(ask_penalty)),
            confidence=confidence,
            explanation=explanation,
        )

        # Confidence scales size by a configurable floor, but inventory still
        # remains the hard ceiling. This keeps low-confidence quotes from
        # shrinking all the way to zero while preserving the existing max
        # inventory guard as the final constraint.
        bid_qty = self.quote_qty * max(self.min_quantity_scale, min(1.0, confidence))
        ask_qty = self.quote_qty * max(self.min_quantity_scale, min(1.0, confidence))

        if inventory >= self.max_inventory:
            bid_qty = 0.0
        elif inventory + bid_qty > self.max_inventory:
            bid_qty = self.max_inventory - inventory
        if inventory <= -self.max_inventory:
            ask_qty = 0.0
        elif inventory - ask_qty < -self.max_inventory:
            ask_qty = self.max_inventory + inventory

        bid_qty = max(0.0, bid_qty)
        ask_qty = max(0.0, ask_qty)

        return Quote(
            bid_price=best_bid_price,
            ask_price=best_ask_price,
            bid_qty=bid_qty,
            ask_qty=ask_qty,
            reasoning=reasoning,
        )
