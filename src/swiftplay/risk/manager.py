from dataclasses import dataclass, replace
from typing import Optional

from swiftplay.decision.interfaces import MarketState, Quote
from swiftplay.features.pipeline import FeatureSnapshot


@dataclass
class RiskConfig:
    max_inventory: float = 10.0
    # 0.02% of the default $100,000 baseline is approximately $20.
    drawdown_threshold: float = 0.0002
    volatility_baseline: float = 0.0
    volatility_spread_multiplier: float = 100.0


class RiskManager:
    """Apply portfolio-level controls to strategy-generated quotes."""

    def __init__(self, starting_equity: float, config: Optional[RiskConfig] = None):
        if starting_equity <= 0.0:
            raise ValueError("starting_equity must be positive")
        self.starting_equity = starting_equity
        self.config = config or RiskConfig()
        if not 0.0 < self.config.drawdown_threshold <= 1.0:
            raise ValueError("drawdown_threshold must be between 0 and 1")
        if self.config.max_inventory <= 0.0:
            raise ValueError("max_inventory must be positive")
        self.peak_equity = starting_equity
        self.circuit_breaker_active = False

    def update_equity(self, equity: float) -> None:
        self.peak_equity = max(self.peak_equity, equity)
        drawdown = (self.peak_equity - equity) / self.peak_equity
        if drawdown >= self.config.drawdown_threshold:
            self.circuit_breaker_active = True

    def reset_circuit_breaker(self) -> None:
        self.circuit_breaker_active = False
        self.peak_equity = self.starting_equity

    def apply(
        self,
        quote: Quote,
        state: MarketState,
        features: FeatureSnapshot,
        inventory: float,
        equity: float,
    ) -> Quote:
        self.update_equity(equity)
        if self.circuit_breaker_active:
            return replace(
                quote, bid_price=None, ask_price=None, bid_qty=None, ask_qty=None
            )

        bid_qty = quote.bid_qty
        ask_qty = quote.ask_qty
        if bid_qty is not None:
            bid_qty = self._allowed_buy_quantity(bid_qty, inventory)
        if ask_qty is not None:
            ask_qty = self._allowed_sell_quantity(ask_qty, inventory)

        bid_price, ask_price = self._widen_for_volatility(
            quote.bid_price, quote.ask_price, state, features
        )
        if bid_price is not None and ask_price is not None and bid_price >= ask_price:
            bid_price = None
            ask_price = None
            bid_qty = None
            ask_qty = None

        return replace(
            quote,
            bid_price=bid_price,
            ask_price=ask_price,
            bid_qty=bid_qty,
            ask_qty=ask_qty,
        )

    def _allowed_buy_quantity(self, requested: float, inventory: float) -> float:
        if inventory >= self.config.max_inventory:
            return 0.0
        return max(0.0, min(requested, self.config.max_inventory - inventory))

    def _allowed_sell_quantity(self, requested: float, inventory: float) -> float:
        if inventory <= -self.config.max_inventory:
            return 0.0
        return max(0.0, min(requested, self.config.max_inventory + inventory))

    def _widen_for_volatility(
        self,
        bid_price: Optional[float],
        ask_price: Optional[float],
        state: MarketState,
        features: FeatureSnapshot,
    ) -> tuple[Optional[float], Optional[float]]:
        volatility = features.realized_vol
        if (
            bid_price is None
            or ask_price is None
            or volatility is None
            or volatility <= self.config.volatility_baseline
        ):
            return bid_price, ask_price

        market_mid = (state.bid_price + state.ask_price) / 2.0
        base_half_spread = abs(ask_price - bid_price) / 2.0
        extra_half_spread = (
            volatility - self.config.volatility_baseline
        ) * self.config.volatility_spread_multiplier
        half_spread = base_half_spread + extra_half_spread
        return market_mid - half_spread, market_mid + half_spread
