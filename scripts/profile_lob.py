import argparse
import cProfile
import pstats
import sys
from pathlib import Path

# Ensure the local src directory is importable when running this script from the repo root.
ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from swiftplay.data_feed.replay import HistoricalReplayFeed
from swiftplay.features.pipeline import FeaturePipeline
from swiftplay.lob.book import OrderBook


def profile_order_book(data_path: str, stats_file: str) -> None:
    feed = HistoricalReplayFeed(data_path, speed_multiplier=None)
    book = OrderBook()

    def run_lob():
        for update in feed:
            book.process_market_update(update)

    profiler = cProfile.Profile()
    profiler.enable()
    run_lob()
    profiler.disable()
    profiler.dump_stats(stats_file)

    ps = pstats.Stats(profiler).sort_stats("cumulative")
    print(f"OrderBook Profiling Results ({stats_file})")
    ps.print_stats(20)


def profile_full_pipeline(data_path: str, stats_file: str) -> None:
    feed = HistoricalReplayFeed(data_path, speed_multiplier=None)
    book = OrderBook()
    pipeline = FeaturePipeline()

    def run_pipeline():
        for update in feed:
            book.process_market_update(update)
            pipeline.compute(book)

    profiler = cProfile.Profile()
    profiler.enable()
    run_pipeline()
    profiler.disable()
    profiler.dump_stats(stats_file)

    ps = pstats.Stats(profiler).sort_stats("cumulative")
    print(f"Full Pipeline Profiling Results ({stats_file})")
    ps.print_stats(20)


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile Swiftplay LOB and feature pipeline")
    parser.add_argument(
        "--data",
        type=str,
        default="data/sample_btcusd_depth.jsonl",
        help="Path to historical depth JSONL file",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=".",
        help="Directory to write .prof stats files to",
    )
    args = parser.parse_args()

    try:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        lob_stats = output_dir / "profile_lob.prof"
        full_stats = output_dir / "profile_full_pipeline.prof"

        profile_order_book(args.data, str(lob_stats))
        print()
        profile_full_pipeline(args.data, str(full_stats))

        print(f"\nSaved profile stats to: {lob_stats} and {full_stats}")
    except FileNotFoundError:
        print(f"Data file not found: {args.data}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
