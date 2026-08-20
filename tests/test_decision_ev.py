import math
import os
from swiftplay.decision.interfaces import MarketState
from swiftplay.decision.ev_quoting import EVQuotingStrategy
from swiftplay.decision.strategies import InventoryAwareStrategy
from swiftplay.decision.heuristic_fill_estimator import HeuristicFillEstimator
from swiftplay.features.pipeline import FeatureSnapshot, FeaturePipeline
from swiftplay.lob.book import OrderBook
from swiftplay.data_feed.replay import HistoricalReplayFeed


def test_ev_quoting_strategy() -> None:
    estimator = HeuristicFillEstimator(decay_factor=100.0)
    strategy = EVQuotingStrategy(
        fill_estimator=estimator,
        quote_qty=1.0,
        max_inventory=10.0,
        risk_aversion=1.0,
        tick_size=0.1,
        levels_to_scan=10,
    )

    state = MarketState(
        bid_price=100.0, ask_price=100.2, bid_qty=10.0, ask_qty=10.0, timestamp=1000
    )

    features = FeatureSnapshot(
        timestamp=1000,
        imbalance=0.0,
        microprice=100.1,
        ofi=0.0,
        spread=0.2,
        realized_vol=0.01,
    )

    # 1. Neutral inventory
    quote_neutral = strategy.generate_quote(state, features, inventory=0.0)
    assert quote_neutral.bid_price is not None
    assert quote_neutral.ask_price is not None
    assert quote_neutral.bid_price < quote_neutral.ask_price

    reasoning = quote_neutral.reasoning
    assert reasoning.inventory_penalty == 0.0
    assert reasoning.confidence > 0.0
    assert "Maximized EV around microprice" in reasoning.explanation

    # 2. Long inventory skew test
    # If inventory is long, bid EV goes down (penalty), ask EV goes up (reward)
    # This should skew quotes downward
    quote_long = strategy.generate_quote(state, features, inventory=10.0)
    assert quote_long.bid_price is not None
    assert quote_long.ask_price is not None
    assert "Skewing quotes" in quote_long.reasoning.explanation

    assert quote_long.bid_price <= quote_neutral.bid_price
    assert quote_long.ask_price <= quote_neutral.ask_price


def test_ev_skips_crossed_market() -> None:
    strategy = EVQuotingStrategy(HeuristicFillEstimator(decay_factor=100.0))
    state = MarketState(
        bid_price=100.2, ask_price=100.0, bid_qty=10.0, ask_qty=10.0, timestamp=1000
    )
    features = FeatureSnapshot(
        timestamp=1000,
        imbalance=0.0,
        microprice=None,
        ofi=0.0,
        spread=None,
        realized_vol=0.01,
    )

    quote = strategy.generate_quote(state, features, inventory=0.0)

    assert quote.bid_price is None
    assert quote.ask_price is None
    assert "crossed or locked" in quote.reasoning.explanation


def test_confidence_based_sizing_scales_down_without_going_below_floor() -> None:
    strategy = EVQuotingStrategy(
        fill_estimator=HeuristicFillEstimator(decay_factor=100.0),
        quote_qty=4.0,
        max_inventory=10.0,
        min_quantity_scale=0.3,
    )

    state = MarketState(
        bid_price=100.0, ask_price=100.2, bid_qty=10.0, ask_qty=10.0, timestamp=1000
    )
    features = FeatureSnapshot(
        timestamp=1000,
        imbalance=0.0,
        microprice=100.1,
        ofi=0.0,
        spread=0.2,
        realized_vol=0.01,
    )

    low_confidence = strategy.generate_quote(state, features, inventory=0.0)
    assert low_confidence.bid_qty is not None
    assert low_confidence.ask_qty is not None
    assert low_confidence.bid_qty >= 1.2
    assert low_confidence.ask_qty >= 1.2

    # A higher-confidence quote should use a larger size than the floor.
    strategy_with_high_confidence = EVQuotingStrategy(
        fill_estimator=HeuristicFillEstimator(decay_factor=100.0),
        quote_qty=4.0,
        max_inventory=10.0,
        min_quantity_scale=0.3,
    )
    quote = strategy_with_high_confidence.generate_quote(state, features, inventory=0.0)
    assert quote.bid_qty is not None
    assert quote.ask_qty is not None
    assert quote.bid_qty <= 4.0
    assert quote.ask_qty <= 4.0

    inventory_cap_limit = EVQuotingStrategy(
        fill_estimator=HeuristicFillEstimator(decay_factor=100.0),
        quote_qty=10.0,
        max_inventory=3.0,
        min_quantity_scale=0.3,
    )
    capped = inventory_cap_limit.generate_quote(state, features, inventory=2.5)
    assert capped.bid_qty is not None
    assert capped.ask_qty is not None
    assert capped.bid_qty <= 3.0 - 2.5
    assert capped.ask_qty <= 3.0 + 2.5


def test_inventory_aware_strategy() -> None:
    strategy = InventoryAwareStrategy(
        half_spread=1.0, quote_qty=1.0, max_inventory=10.0, skew_factor=2.0
    )

    state = MarketState(
        bid_price=100.0, ask_price=100.2, bid_qty=10.0, ask_qty=10.0, timestamp=1000
    )

    features = FeatureSnapshot(
        timestamp=1000,
        imbalance=0.0,
        microprice=100.1,
        ofi=0.0,
        spread=0.2,
        realized_vol=0.01,
    )

    # Base quote with 0 inventory
    # ref = 100.1. bid = 100.1 - 1.0 = 99.1, ask = 100.1 + 1.0 = 101.1
    q_base = strategy.generate_quote(state, features, inventory=0.0)
    assert q_base.bid_price is not None
    assert q_base.ask_price is not None
    assert math.isclose(q_base.bid_price, 99.1)
    assert math.isclose(q_base.ask_price, 101.1)

    # Long inventory 10.0 (normalized = 1.0)
    # bid = 99.1 - 2.0 = 97.1
    # ask = 101.1 - 2.0 = 99.1, but clamped to state.ask_price (100.2)
    # to prevent crossing
    q_long = strategy.generate_quote(state, features, inventory=10.0)
    assert q_long.bid_price is not None
    assert q_long.ask_price is not None
    assert math.isclose(q_long.bid_price, 97.1)
    assert math.isclose(q_long.ask_price, 100.2)


def test_integration_ev_decision() -> None:
    sample_path = "data/sample_btcusd_depth.jsonl"
    if not os.path.exists(sample_path):
        return

    feed = HistoricalReplayFeed(sample_path, speed_multiplier=None)
    book = OrderBook()
    pipeline = FeaturePipeline(vol_window=20, imb_levels=5)

    estimator = HeuristicFillEstimator(
        decay_factor=5000.0
    )  # Larger decay for BTC prices ~60k
    strategy = EVQuotingStrategy(
        fill_estimator=estimator,
        quote_qty=0.1,
        max_inventory=1.0,
        risk_aversion=1.0,
        tick_size=0.1,
        levels_to_scan=5,
    )

    updates = 0
    for update in feed:
        book.process_market_update(update)
        snapshot = pipeline.compute(book)

        if (
            snapshot.microprice is not None
            and book.best_bid is not None
            and book.best_ask is not None
        ):
            state = MarketState(
                bid_price=book.best_bid,
                ask_price=book.best_ask,
                bid_qty=1.0,
                ask_qty=1.0,
                timestamp=book.current_timestamp,
            )

            quote = strategy.generate_quote(state, snapshot, inventory=0.0)

            assert quote.bid_price is not None
            assert quote.ask_price is not None
            assert quote.bid_price < quote.ask_price
            assert quote.reasoning.explanation != ""

            updates += 1
            if updates > 5:
                break

    assert updates > 0
