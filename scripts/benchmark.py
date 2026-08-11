import argparse
import statistics
import sys
import time
from pathlib import Path
from typing import Dict

# Ensure the local src directory is importable when running this script from the repo root.
ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from swiftplay.data_feed.replay import HistoricalReplayFeed
from swiftplay.features.pipeline import FeaturePipeline
from swiftplay.lob.book import OrderBook


def _percentile(sorted_values, percentile: float) -> float:
    if not sorted_values:
        return 0.0
    if percentile <= 0:
        return sorted_values[0]
    if percentile >= 1:
        return sorted_values[-1]

    rank = percentile * (len(sorted_values) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = rank - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * weight


def run_benchmark(data_path: str) -> Dict[str, float]:
    feed = HistoricalReplayFeed(data_path, speed_multiplier=None)
    book = OrderBook()
    pipeline = FeaturePipeline()

    per_update_latencies = []
    total_updates = 0

    start_wall = time.perf_counter()
    for update in feed:
        tick_start = time.perf_counter()
        book.process_market_update(update)
        pipeline.compute(book)
        tick_end = time.perf_counter()

        per_update_latencies.append((tick_end - tick_start) * 1_000_000.0)
        total_updates += 1
    end_wall = time.perf_counter()

    total_time = end_wall - start_wall
    throughput = total_updates / total_time if total_time > 0 else 0.0
    sorted_latencies = sorted(per_update_latencies)

    stats = {
        "total_updates": total_updates,
        "total_time_seconds": total_time,
        "updates_per_second": throughput,
        "median_latency_us": statistics.median(sorted_latencies)
        if sorted_latencies
        else 0.0,
        "p99_latency_us": _percentile(sorted_latencies, 0.99),
    }
    return stats


def print_summary(stats: Dict[str, float]) -> None:
    print("Benchmark Summary")
    print("-----------------")
    print(f"Total updates processed: {stats['total_updates']}")
    print(f"Total wall-clock time: {stats['total_time_seconds']:.6f} sec")
    print(f"Throughput: {stats['updates_per_second']:.2f} updates/sec")
    print(f"Median per-update latency: {stats['median_latency_us']:.2f} µs")
    print(f"P99 per-update latency: {stats['p99_latency_us']:.2f} µs")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Swiftplay LOB pipeline")
    parser.add_argument(
        "--data",
        type=str,
        default="data/sample_btcusd_depth.jsonl",
        help="Path to historical depth JSONL file",
    )
    args = parser.parse_args()

    try:
        stats = run_benchmark(args.data)
    except FileNotFoundError:
        print(f"Data file not found: {args.data}", file=sys.stderr)
        sys.exit(1)

    print_summary(stats)


if __name__ == "__main__":
    main()
