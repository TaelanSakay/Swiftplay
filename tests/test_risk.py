import math

from swiftplay.backtest.engine import BacktestConfig, BacktestRunner
from swiftplay.data_feed.replay import HistoricalReplayFeed
from swiftplay.decision.ev_quoting import EVQuotingStrategy
from swiftplay.decision.fixed_spread import FixedSpreadStrategy
from swiftplay.decision.heuristic_fill_estimator import HeuristicFillEstimator
from swiftplay.decision.interfaces import MarketState, Quote, QuoteReasoning
from swiftplay.decision.strategies import InventoryAwareStrategy
from swiftplay.features.pipeline import FeatureSnapshot
from swiftplay.risk import RiskConfig, RiskManager


def make_quote() -> Quote:
    return Quote(
        bid_price=99.0,
        ask_price=101.0,
        bid_qty=2.0,
        ask_qty=2.0,
        reasoning=QuoteReasoning(0.0, 0.0, 0.0, 0.0, 1.0, "test"),
    )


def make_state() -> MarketState:
    return MarketState(100.0, 101.0, 10.0, 10.0, 1)


def make_features(realized_vol: float | None) -> FeatureSnapshot:
    return FeatureSnapshot(1, 0.0, 100.5, 0.0, 1.0, realized_vol)


def apply_quote(manager: RiskManager, inventory: float, equity: float = 100.0, realized_vol: float | None = None) -> Quote:
    return manager.apply(
        make_quote(), make_state(), make_features(realized_vol), inventory, equity
    )


def test_inventory_limits_suppress_only_risk_increasing_side() -> None:
    manager = RiskManager(100.0, RiskConfig(max_inventory=10.0))

    long_quote = apply_quote(manager, inventory=10.0)
    assert long_quote.bid_qty == 0.0
    assert long_quote.ask_qty == 2.0

    short_quote = apply_quote(manager, inventory=-10.0)
    assert short_quote.bid_qty == 2.0
    assert short_quote.ask_qty == 0.0


def test_inventory_limits_cap_quantity_at_boundary() -> None:
    manager = RiskManager(100.0, RiskConfig(max_inventory=10.0))

    quote = apply_quote(manager, inventory=9.0)
    assert quote.bid_qty == 1.0
    assert quote.ask_qty == 2.0
    assert quote.bid_price < quote.ask_price


def test_drawdown_uses_starting_equity_and_latches() -> None:
    manager = RiskManager(100.0, RiskConfig(drawdown_threshold=0.20))

    apply_quote(manager, inventory=0.0, equity=80.0)
    assert manager.circuit_breaker_active

    stopped = apply_quote(manager, inventory=0.0, equity=100.0)
    assert stopped.bid_price is None
    assert stopped.ask_price is None

    manager.reset_circuit_breaker()
    assert not manager.circuit_breaker_active
    assert apply_quote(manager, inventory=0.0, equity=100.0).bid_price == 99.0


def test_volatility_widening_is_symmetric_and_monotonic() -> None:
    manager = RiskManager(
        100.0,
        RiskConfig(volatility_baseline=0.01, volatility_spread_multiplier=100.0),
    )

    low = apply_quote(manager, inventory=0.0, realized_vol=0.01)
    high = apply_quote(manager, inventory=0.0, realized_vol=0.03)

    assert low.bid_price == 99.0
    assert low.ask_price == 101.0
    assert math.isclose(high.bid_price, 97.5)
    assert math.isclose(high.ask_price, 103.5)
    assert math.isclose(100.5 - high.bid_price, high.ask_price - 100.5)
    assert high.bid_price < high.ask_price


def test_missing_or_zero_volatility_does_not_change_quote() -> None:
    manager = RiskManager(100.0, RiskConfig(volatility_baseline=0.01))

    for volatility in (None, 0.0):
        quote = apply_quote(manager, inventory=0.0, realized_vol=volatility)
        assert quote.bid_price == 99.0
        assert quote.ask_price == 101.0


def test_risk_limits_apply_to_all_strategies() -> None:
    strategies = [
        FixedSpreadStrategy(spread=10.0, order_qty=1.0),
        InventoryAwareStrategy(half_spread=5.0, quote_qty=1.0),
        EVQuotingStrategy(
            fill_estimator=HeuristicFillEstimator(decay_factor=5000.0),
            quote_qty=1.0,
            max_inventory=10.0,
        ),
    ]

    for strategy in strategies:
        manager = RiskManager(100000.0, RiskConfig(max_inventory=0.1))
        runner = BacktestRunner(
            strategy,
            HistoricalReplayFeed("data/sample_btcusd_depth.jsonl", speed_multiplier=None),
            BacktestConfig(initial_capital=100000.0, risk_manager=manager),
        )
        history = runner.run()
        inventories = [abs(step.inventory) for step in history]

        assert history
        assert max(inventories) <= 0.1 + 1e-9
        assert all(
            step.fills == [] or all(fill.fill_quantity > 0 for fill in step.fills)
            for step in history
        )
