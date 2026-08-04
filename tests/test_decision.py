from swiftplay.decision.fixed_spread import FixedSpreadStrategy
from swiftplay.decision.interfaces import MarketState, Features


def test_fixed_spread_strategy() -> None:
    strategy = FixedSpreadStrategy(spread=10.0, order_qty=1.0)

    state = MarketState(
        bid_price=60000.0,
        ask_price=60002.0,
        bid_qty=5.0,
        ask_qty=5.0,
        timestamp=1625097600,
    )

    features = Features(
        order_book_imbalance=0.5, microprice=60001.0, realized_volatility=0.01
    )

    quote = strategy.generate_quote(state, features)

    # Mid price is 60001.0
    # Spread is 10.0
    assert quote.bid_price == 59996.0
    assert quote.ask_price == 60006.0
    assert quote.bid_qty == 1.0
    assert quote.ask_qty == 1.0
    assert quote.reasoning.expected_value == 10.0
    assert quote.reasoning.confidence == 1.0
