import json
import os
import tempfile
import time

from swiftplay.data_feed.replay import HistoricalReplayFeed


def test_historical_replay_feed_parsing() -> None:
    # Create temporary jsonl file
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write("# Dummy comment\n")
        f.write(
            json.dumps({"timestamp": 100, "bids": [[100.0, 1.0]], "asks": []}) + "\n"
        )
        f.write("\n")
        f.write(
            json.dumps({"timestamp": 200, "bids": [[101.0, 1.0]], "asks": []}) + "\n"
        )
        file_path = f.name

    try:
        feed = HistoricalReplayFeed(file_path, speed_multiplier=None)
        updates = list(feed)

        assert len(updates) == 2
        assert updates[0]["timestamp"] == 100
        assert updates[1]["timestamp"] == 200
    finally:
        try:
            os.remove(file_path)
        except PermissionError:
            # Windows may keep the file locked briefly; tolerate removal failure.
            pass


def test_historical_replay_feed_speed_multiplier() -> None:
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        # 100ms apart
        f.write(json.dumps({"timestamp": 1000, "bids": [], "asks": []}) + "\n")
        f.write(json.dumps({"timestamp": 1100, "bids": [], "asks": []}) + "\n")
        file_path = f.name

    try:
        # Real-time replay
        feed = HistoricalReplayFeed(file_path, speed_multiplier=1.0)
        start_time = time.time()
        list(feed)
        duration = time.time() - start_time

        # Should take roughly 0.1 seconds (100ms)
        assert duration >= 0.08

        # 10x replay
        feed_fast = HistoricalReplayFeed(file_path, speed_multiplier=10.0)
        start_time_fast = time.time()
        list(feed_fast)
        duration_fast = time.time() - start_time_fast

        # Should take roughly 0.01 seconds
        assert duration_fast < 0.05
    finally:
        try:
            os.remove(file_path)
        except PermissionError:
            # Windows may keep the file locked briefly; tolerate removal failure.
            pass
