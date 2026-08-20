#!/usr/bin/env python3
"""
Generate labeled training data for fill probability prediction.

Runs a backtest with FixedSpreadStrategy and records:
- Features at quote placement time
- Distance from mid price
- Whether the quote filled within a time window
"""

import csv
import os
from typing import Any, Dict, List
from swiftplay.data_feed.replay import HistoricalReplayFeed
from swiftplay.decision.fixed_spread import FixedSpreadStrategy
from swiftplay.decision.interfaces import MarketState
from swiftplay.lob.book import OrderBook
from swiftplay.features.pipeline import FeaturePipeline


def generate_training_data(
    data_path: str,
    output_path: str,
    spread: float = 10.0,
    order_qty: float = 1.0,
    fill_lookahead_ticks: int = 1,
) -> None:
    """
    Generate labeled training data by running a FixedSpreadStrategy backtest.

    Args:
        data_path: Path to historical depth JSONL file
        output_path: Path to output CSV file
        spread: Quote spread from mid price
        order_qty: Order quantity
        fill_lookahead_ticks: Number of ticks ahead to check for fill
    """
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    feed = HistoricalReplayFeed(data_path, speed_multiplier=None)
    book = OrderBook()
    pipeline = FeaturePipeline()
    strategy = FixedSpreadStrategy(spread=spread, order_qty=order_qty)

    quotes_placed: List[Dict[str, Any]] = []

    # Simulate the same quote lifecycle as BacktestRunner. Each row is created
    # when a real order is placed and is labeled from fills for that order ID,
    # rather than inferred from a future market snapshot.
    active_rows: Dict[str, Dict[str, Any]] = {}
    order_number = 0
    for update in feed:
        book.process_market_update(update)
        fills = book.get_recent_fills()
        for fill in fills:
            row = active_rows.pop(fill.order_id, None)
            if row is not None:
                row["filled"] = 1
                quotes_placed.append(row)

        # With a one-tick horizon, an unfilled order is replaced here. For a
        # longer horizon, retain it until its age reaches that horizon.
        expired_ids = []
        for order_id, row in active_rows.items():
            row["age"] += 1
            if row["age"] >= fill_lookahead_ticks:
                row["filled"] = 0
                quotes_placed.append(row)
                expired_ids.append(order_id)
        for order_id in expired_ids:
            book.cancel_order(order_id)
            del active_rows[order_id]

        features = pipeline.compute(book)
        best_bid = book.best_bid
        best_ask = book.best_ask
        if best_bid is None or best_ask is None:
            continue

        state = MarketState(
            bid_price=best_bid,
            ask_price=best_ask,
            bid_qty=book.bids.get(best_bid, 0.0),
            ask_qty=book.asks.get(best_ask, 0.0),
            timestamp=book.current_timestamp,
        )
        quote = strategy.generate_quote(state, features, 0.0)
        mid_price = (best_bid + best_ask) / 2.0
        common = {
            "microprice": features.microprice or mid_price,
            "spread": features.spread or 0.0,
            "imbalance": features.imbalance or 0.0,
            "ofi": features.ofi or 0.0,
            "realized_vol": features.realized_vol or 0.0,
        }

        order_number += 1
        if quote.bid_price is not None and quote.bid_qty is not None and quote.bid_qty > 0:
            order_id = f"TRAIN_BID_{order_number}"
            book.place_order(order_id, "BUY", quote.bid_price, quote.bid_qty)
            active_rows[order_id] = {
                **common,
                "ofi_signed": common["ofi"],
                "imbalance_signed": common["imbalance"],
                "distance_from_mid": abs(quote.bid_price - mid_price),
                "filled": 0,
                "age": 0,
            }
        if quote.ask_price is not None and quote.ask_qty is not None and quote.ask_qty > 0:
            order_id = f"TRAIN_ASK_{order_number}"
            book.place_order(order_id, "SELL", quote.ask_price, quote.ask_qty)
            active_rows[order_id] = {
                **common,
                "ofi_signed": -common["ofi"],
                "imbalance_signed": -common["imbalance"],
                "distance_from_mid": abs(quote.ask_price - mid_price),
                "filled": 0,
                "age": 0,
            }

    for row in active_rows.values():
        row["filled"] = 0
        quotes_placed.append(row)

    # Write CSV
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "microprice",
                "spread",
                "imbalance",
                "ofi",
                "imbalance_signed",
                "ofi_signed",
                "realized_vol",
                "distance_from_mid",
                "filled",
            ],
        )
        writer.writeheader()
        for record in quotes_placed:
            record.pop("age", None)
            writer.writerow(record)

    print(f"Generated {len(quotes_placed)} training examples -> {output_path}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate fill probability training data")
    parser.add_argument(
        "--data",
        type=str,
        default="data/sample_btcusd_depth.jsonl",
        help="Path to historical depth JSONL file",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/training/fill_labels.csv",
        help="Path to output training CSV file",
    )
    parser.add_argument(
        "--spread", type=float, default=10.0, help="Quote spread from mid price"
    )
    parser.add_argument(
        "--order-qty", type=float, default=1.0, help="Order quantity per quote"
    )
    parser.add_argument(
        "--lookahead-ticks",
        type=int,
        default=1,
        help="Ticks ahead to check for fill",
    )
    args = parser.parse_args()

    generate_training_data(
        args.data,
        args.output,
        spread=args.spread,
        order_qty=args.order_qty,
        fill_lookahead_ticks=args.lookahead_ticks,
    )


if __name__ == "__main__":
    main()