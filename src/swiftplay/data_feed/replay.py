import json
import time
from typing import Iterator, Optional
from .interfaces import DataFeed


class HistoricalReplayFeed(DataFeed):
    """
    Reads a JSONL file of historical order book updates and yields them in order.
    Supports a speed multiplier for backtesting or demo playback.
    """

    def __init__(self, file_path: str, speed_multiplier: Optional[float] = None):
        self.file_path = file_path
        self.speed_multiplier = speed_multiplier

    def __iter__(self) -> Iterator[dict]:
        with open(self.file_path, "r") as f:
            last_event_time = None
            last_real_time = None

            for line in f:
                if not line.strip() or line.startswith("#"):
                    continue

                update = json.loads(line)

                # Apply speed multiplier if requested (> 0)
                if self.speed_multiplier is not None and self.speed_multiplier > 0:
                    event_time = update.get("timestamp")
                    if event_time is not None:
                        current_real_time = time.time()

                        if last_event_time is not None and last_real_time is not None:
                            # Event time diff in seconds
                            # (Binance timestamps are in milliseconds)
                            event_diff_sec = (event_time - last_event_time) / 1000.0
                            real_diff_sec = current_real_time - last_real_time

                            target_diff = event_diff_sec / self.speed_multiplier
                            sleep_time = target_diff - real_diff_sec

                            if sleep_time > 0:
                                time.sleep(sleep_time)

                        last_event_time = event_time
                        last_real_time = time.time()

                yield update
