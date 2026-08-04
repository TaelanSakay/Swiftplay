from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class MarketState:
    bid_price: float
    ask_price: float
    bid_qty: float
    ask_qty: float
    timestamp: int


@dataclass
class Features:
    # Extracted feature signals
    order_book_imbalance: float
    microprice: float
    realized_volatility: float


@dataclass
class QuoteReasoning:
    """Explicit reasoning trace for observability and analysis."""

    expected_value: float
    fill_probability: float
    inventory_penalty: float
    confidence: float


@dataclass
class Quote:
    bid_price: Optional[float]
    ask_price: Optional[float]
    bid_qty: Optional[float]
    ask_qty: Optional[float]
    reasoning: QuoteReasoning


class QuoteDecisionEngine(ABC):
    @abstractmethod
    def generate_quote(self, state: MarketState, features: Features) -> Quote:
        """
        Generate a quote action given the current market state and features.

        This abstract method enforces separation of business logic from execution.
        """
        pass
