import math
from .interfaces import FillProbabilityEstimator, MarketState
from swiftplay.features.pipeline import FeatureSnapshot


class HeuristicFillEstimator(FillProbabilityEstimator):
    """
    A simple baseline heuristic to estimate fill probability.
    Returns higher probabilities for quotes closer to the mid-price/microprice.

    TODO: Replace this placeholder with a trained ML model from `models/` later.
    """

    def __init__(self, decay_factor: float = 100.0):
        self.decay_factor = decay_factor

    def estimate(
        self,
        state: MarketState,
        features: FeatureSnapshot,
        quote_price: float,
        side: str,
    ) -> float:
        # Use microprice if available, fallback to simple mid price
        ref_price = features.microprice
        if ref_price is None:
            ref_price = (state.bid_price + state.ask_price) / 2.0

        distance = abs(quote_price - ref_price)

        # Simple exponential decay based on distance from reference price
        # Probability drops to ~0 as distance increases.
        return math.exp(-self.decay_factor * distance / ref_price)
