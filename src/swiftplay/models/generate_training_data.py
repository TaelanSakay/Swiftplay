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
from typing import List, Dict, Any
from swiftplay.data_feed.replay import HistoricalReplayFeed
from swiftplay.decision.fixed_spread import FixedSpreadStrategy
from swiftplay.lob.book import OrderBook
from swiftplay.features.pipeline import FeaturePipeline


def generate_training_data(
    data_path: str,
    output_path: str,
    spread: float = 10.0,
    order_qty: float = 1.0,
    fill_lookahead_ticks: int = 5,
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

    # Replay the full data file and record book/feature state at each tick
    history = []
    for update in feed:
        book.process_market_update(update)
        features = pipeline.compute(book)
        history.append((features, book.best_bid, book.best_ask))

    quotes_placed: List[Dict[str, Any]] = []

    # Generate labels: one row per side per tick
    for tick_idx, (features, best_bid, best_ask) in enumerate(history):
        if best_bid is None or best_ask is None:
            continue
        if features.microprice is None:
            continue

        mid_price = (best_bid + best_ask) / 2.0
        bid_quote_price = mid_price - strategy.spread / 2.0
        ask_quote_price = mid_price + strategy.spread / 2.0

        # Check if bid filled in lookahead window
        bid_filled = 0
        for j in range(1, min(fill_lookahead_ticks + 1, len(history) - tick_idx)):
            future_features, future_best_bid, future_best_ask = history[tick_idx + j]
            if future_best_ask is not None and future_best_ask <= bid_quote_price:
                bid_filled = 1
                break

        # Check if ask filled in lookahead window
        ask_filled = 0
        for j in range(1, min(fill_lookahead_ticks + 1, len(history) - tick_idx)):
            future_features, future_best_bid, future_best_ask = history[tick_idx + j]
            if future_best_bid is not None and future_best_bid >= ask_quote_price:
                ask_filled = 1
                break

        common = {
            "microprice": features.microprice,
            "spread": features.spread or 0.0,
            "imbalance": features.imbalance or 0.0,
            "ofi": features.ofi or 0.0,
            "realized_vol": features.realized_vol or 0.0,
        }

        # One row for the bid side
        quotes_placed.append({
            **common,
            "distance_from_mid": mid_price - bid_quote_price,
            "filled": bid_filled,
        })
        # One row for the ask side
        quotes_placed.append({
            **common,
            "distance_from_mid": ask_quote_price - mid_price,
            "filled": ask_filled,
        })

    # Write CSV
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "microprice",
                "spread",
                "imbalance",
                "ofi",
                "realized_vol",
                "distance_from_mid",
                "filled",
            ],
        )
        writer.writeheader()
        for record in quotes_placed:
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
        default=5,
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