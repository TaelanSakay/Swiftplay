from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from swiftplay.features.pipeline import FeatureSnapshot


@dataclass
class MarketState:
    bid_price: float
    ask_price: float
    bid_qty: float
    ask_qty: float
    timestamp: int


@dataclass
class QuoteReasoning:
    """Explicit reasoning trace for observability and analysis."""

    expected_value: float
    fill_probability_bid: float
    fill_probability_ask: float
    inventory_penalty: float
    confidence: float
    explanation: str


@dataclass
class Quote:
    bid_price: Optional[float]
    ask_price: Optional[float]
    bid_qty: Optional[float]
    ask_qty: Optional[float]
    reasoning: QuoteReasoning


class FillProbabilityEstimator(ABC):
    @abstractmethod
    def estimate(
        self,
        state: MarketState,
        features: FeatureSnapshot,
        quote_price: float,
        side: str,
    ) -> float:
        """
        Estimate the probability of a limit order at `quote_price` getting filled
        in the near future.
        """
        pass


class QuoteDecisionEngine(ABC):
    @abstractmethod
    def generate_quote(
        self, state: MarketState, features: FeatureSnapshot, inventory: float
    ) -> Quote:
        """
        Generate a quote action given the current market state, features, and inventory.

        This abstract method enforces separation of business logic from execution.
        """
        pass
