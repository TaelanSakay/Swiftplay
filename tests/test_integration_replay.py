import json
import os
import tempfile

from swiftplay.data_feed.replay import HistoricalReplayFeed
from swiftplay.lob.book import OrderBook


def test_integration_data_feed_to_lob() -> None:
    """
    Test wiring the HistoricalReplayFeed directly to the OrderBook simulator.
    """
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        # Snapshot
        f.write(
            json.dumps(
                {
                    "timestamp": 1000,
                    "bids": [[100.0, 10.0], [99.0, 20.0]],
                    "asks": [[101.0, 10.0], [102.0, 20.0]],
                    "is_snapshot": True,
                }
            )
            + "\n"
        )

        # Diff - Bid drops to 0, Ask moves down
        f.write(
            json.dumps(
                {
                    "timestamp": 1001,
                    "bids": [[100.0, 0.0], [99.0, 20.0]],
                    "asks": [[100.5, 5.0]],
                }
            )
            + "\n"
        )
        file_path = f.name

    try:
        feed = HistoricalReplayFeed(file_path, speed_multiplier=None)
        book = OrderBook()

        feed_iterator = iter(feed)

        # Process snapshot
        book.process_market_update(next(feed_iterator))
        assert book.best_bid == 100.0
        assert book.best_ask == 101.0

        # Process diff
        book.process_market_update(next(feed_iterator))
        # 100.0 bid was removed (qty 0.0), so best bid drops to 99.0
        assert book.best_bid == 99.0
        # 100.5 ask was added
        assert book.best_ask == 100.5

    finally:
        # Ensure generator is closed so the file handle is released on Windows
        try:
            feed_iterator.close()
        except Exception:
            pass

        try:
            os.remove(file_path)
        except PermissionError:
            # On Windows the file may still be locked briefly; tolerate.
            pass
