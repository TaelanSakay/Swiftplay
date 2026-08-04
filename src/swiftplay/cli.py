import argparse
import logging
from swiftplay.common.logging_setup import setup_logging

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Swiftplay Market Maker")
    parser.add_argument(
        "--strategy", type=str, default="fixed", help="Strategy to run (default: fixed)"
    )
    args = parser.parse_args()

    setup_logging()
    logger.info(f"Starting Swiftplay with strategy: {args.strategy}")

    # Placeholder: Initialize and run the selected strategy


if __name__ == "__main__":
    main()
