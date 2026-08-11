import math
import os
from swiftplay.lob.book import OrderBook
from swiftplay.features.microstructure import (
    spread,
    microprice,
    order_book_imbalance,
    order_flow_imbalance,
)
from swiftplay.features.volatility import realized_volatility
from swiftplay.features.pipeline import FeaturePipeline
from swiftplay.data_feed.replay import HistoricalReplayFeed


def test_spread() -> None:
    book = OrderBook()
    assert spread(book) is None

    book.process_market_update({"bids": [[100.0, 1.0]], "asks": [[101.0, 1.0]]})
    assert spread(book) == 1.0


def test_microprice() -> None:
    book = OrderBook()
    # Empty book
    assert microprice(book) is None

    # Division by zero case (bids and asks have 0 size)
    book.process_market_update({"bids": [[100.0, 0.0]], "asks": [[101.0, 0.0]]})
    assert microprice(book) is None

    # Normal case
    book.process_market_update({"bids": [[100.0, 2.0]], "asks": [[102.0, 8.0]]})
    # bb=100.0 (size 2.0), ba=102.0 (size 8.0)
    # expected: (100.0 * 8.0 + 102.0 * 2.0) / 10.0 = (800.0 + 204.0) / 10.0 = 100.4
    mprice = microprice(book)
    assert mprice is not None
    assert math.isclose(mprice, 100.4)


def test_order_book_imbalance() -> None:
    book = OrderBook()
    # Empty book
    assert order_book_imbalance(book) is None

    # Symmetric book
    book.process_market_update({"bids": [[100.0, 5.0]], "asks": [[101.0, 5.0]]})
    assert order_book_imbalance(book) == 0.0

    # Heavy bid side
    book.process_market_update({"bids": [[100.0, 15.0]], "asks": [[101.0, 5.0]]})
    # expected = (15 - 5) / (15 + 5) = 10 / 20 = 0.5
    assert order_book_imbalance(book) == 0.5


def test_order_flow_imbalance() -> None:
    book = OrderBook()
    # Initial state
    book.process_market_update({"bids": [[100.0, 5.0]], "asks": [[101.0, 5.0]]})
    prev_state = {
        "best_bid": 100.0,
        "best_bid_size": 5.0,
        "best_ask": 101.0,
        "best_ask_size": 5.0,
    }

    # 1. Size changes at same price
    book.process_market_update({"bids": [[100.0, 7.0]], "asks": [[101.0, 4.0]]})
    # bid delta = 7.0 - 5.0 = +2.0
    # ask delta = 4.0 - 5.0 = -1.0
    # OFI = bid delta - ask delta = 2.0 - (-1.0) = 3.0
    ofi = order_flow_imbalance(book, prev_state)
    assert ofi == 3.0

    # Update prev_state manually for next check
    prev_state = {
        "best_bid": 100.0,
        "best_bid_size": 7.0,
        "best_ask": 101.0,
        "best_ask_size": 4.0,
    }

    # 2. Price level changes (disappears)
    book.process_market_update(
        {"bids": [[100.0, 0.0], [99.0, 10.0]], "asks": [[101.0, 4.0]]}
    )
    # best bid drops to 99.0
    # bid delta = -7.0 (previous size removed)
    # ask delta = 0.0 (no change)
    # OFI = -7.0 - 0.0 = -7.0
    ofi = order_flow_imbalance(book, prev_state)
    assert ofi == -7.0


def test_realized_volatility() -> None:
    # Insufficient data
    assert realized_volatility([], window=5) is None
    assert realized_volatility([100.0], window=5) is None

    # Valid data
    prices = [100.0, 101.0, 100.5, 102.0]
    vol = realized_volatility(prices, window=5)
    assert vol is not None
    assert vol > 0.0


def test_integration_feature_pipeline() -> None:
    # Use real sample data
    sample_path = "data/sample_btcusd_depth.jsonl"
    if not os.path.exists(sample_path):
        return  # Skip if sample data isn't present

    feed = HistoricalReplayFeed(sample_path, speed_multiplier=None)
    book = OrderBook()
    pipeline = FeaturePipeline(vol_window=20, imb_levels=5)

    valid_snapshots = 0

    for update in feed:
        book.process_market_update(update)
        snapshot = pipeline.compute(book)

        # Verify basic invariants if book is populated
        if snapshot.spread is not None:
            assert snapshot.spread > 0

        if snapshot.imbalance is not None:
            assert -1.0 <= snapshot.imbalance <= 1.0

        if snapshot.microprice is not None:
            assert book.best_bid is not None and book.best_ask is not None
            assert book.best_bid <= snapshot.microprice <= book.best_ask

        valid_snapshots += 1

    assert valid_snapshots > 0
