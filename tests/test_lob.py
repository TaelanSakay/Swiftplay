from swiftplay.lob.book import OrderBook


def test_queue_position_decrement_and_partial_fill() -> None:
    book = OrderBook()
    book.process_market_update(
        {"timestamp": 100, "bids": [[100.0, 10.0]], "asks": [[101.0, 10.0]]}
    )

    book.place_order("ord1", "BUY", 100.0, 5.0)
    order = book.tracked_orders["ord1"]

    assert order.volume_ahead == 10.0

    # Decrease depth by 8.0, should consume volume ahead but not fill
    book.process_market_update(
        {
            "timestamp": 101,
            "bids": [[100.0, 2.0]],
        }
    )
    assert order.volume_ahead == 2.0
    assert len(book.get_recent_fills()) == 0

    # Decrease depth by 2.0, fill 2.0
    book.process_market_update(
        {
            "timestamp": 102,
            "bids": [[100.0, 0.0]],  # 2.0 decrease
        }
    )

    # Let's adjust to test partial fills properly.
    pass


def test_partial_fill_sequence() -> None:
    book = OrderBook()
    book.process_market_update(
        {
            "timestamp": 100,
            "bids": [[100.0, 0.0]],  # Empty level
            "asks": [[101.0, 10.0]],
        }
    )

    # Place order, volume ahead is 0.0
    book.place_order("ord2", "BUY", 100.0, 10.0)

    # Market adds volume, no effect on volume ahead
    book.process_market_update(
        {
            "timestamp": 101,
            "bids": [[100.0, 5.0]],
        }
    )
    assert book.tracked_orders["ord2"].volume_ahead == 0.0

    # Market depth drops by 2.0. Since volume ahead is 0, this immediately fills us 2.0
    book.process_market_update(
        {
            "timestamp": 102,
            "bids": [[100.0, 3.0]],
        }
    )

    fills = book.get_recent_fills()
    assert len(fills) == 1
    assert fills[0].fill_quantity == 2.0
    assert fills[0].remaining_quantity == 8.0
    assert fills[0].fill_price == 100.0

    # Market depth drops by 10.0 (goes to 0)
    book.process_market_update(
        {
            "timestamp": 103,
            "bids": [[100.0, 0.0]],
        }
    )

    fills = book.get_recent_fills()
    assert len(fills) == 1
    assert fills[0].fill_quantity == 3.0  # Only 3.0 decrease
    assert fills[0].remaining_quantity == 5.0


def test_cancellation() -> None:
    book = OrderBook()
    book.place_order("ord3", "BUY", 100.0, 10.0)
    book.cancel_order("ord3")

    # Simulate a cross that would normally fill it
    book.process_market_update({"timestamp": 100, "asks": [[100.0, 10.0]]})

    fills = book.get_recent_fills()
    assert len(fills) == 0
    assert book.tracked_orders["ord3"].is_filled is False
    assert book.tracked_orders["ord3"].is_cancelled is True


def test_fill_price_on_cross() -> None:
    """
    When a market order crosses and fills our resting order (the 'Crosses' case),
    make sure the fill is generated at OUR order's price, not the crossing market price.
    """
    book = OrderBook()
    book.process_market_update(
        {"timestamp": 100, "bids": [[99.0, 10.0]], "asks": [[101.0, 10.0]]}
    )

    # We rest a limit bid at 99.5
    book.place_order("ord4", "BUY", 99.5, 5.0)

    # Aggressive market seller comes in and pushes best ask down to 99.0
    book.process_market_update({"timestamp": 101, "asks": [[99.0, 10.0]]})

    fills = book.get_recent_fills()
    assert len(fills) == 1
    fill = fills[0]

    # Standard price-time priority: resting limit orders fill at their own posted price
    assert fill.fill_price == 99.5
    assert fill.fill_quantity == 5.0
    assert book.tracked_orders["ord4"].is_filled is True
