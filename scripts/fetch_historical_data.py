#!/usr/bin/env python3
import argparse
import asyncio
import json
import requests
import time
import sys
from typing import Any

try:
    import websockets
except ImportError:
    print("Please install websockets package: pip install websockets")
    sys.exit(1)

def get_snapshot(symbol: str) -> dict:
    url = f"https://api.binance.us/api/v3/depth?symbol={symbol.upper()}&limit=1000"
    print(f"Fetching REST snapshot from {url}")
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    
    return {
        'timestamp': int(time.time() * 1000),
        'lastUpdateId': data['lastUpdateId'],
        'bids': data['bids'],
        'asks': data['asks'],
        'is_snapshot': True
    }

async def _buffer_events(ws: Any, events: list[dict]) -> None:
    """Receive raw depth events while the REST snapshot is being fetched."""
    async for message in ws:
        events.append(json.loads(message))


def _event_update(event: dict) -> dict:
    """Keep the depth payload and sequence metadata needed for replay/debugging."""
    update = {
        'timestamp': event.get('E', int(time.time() * 1000)),
        'bids': event.get('b', []),
        'asks': event.get('a', []),
    }
    for field in ('U', 'u', 'pu'):
        if field in event:
            update[field] = event[field]
    return update


def _is_bridge(event: dict, last_update_id: int) -> bool:
    first_update = event.get('U')
    final_update = event.get('u')
    return (
        first_update is not None
        and final_update is not None
        and first_update <= last_update_id + 1 <= final_update
    )


async def _synchronize_stream(
    ws: Any, symbol: str, snapshot_timeout: float = 10.0
) -> tuple[dict, list[dict]]:
    """Synchronize a Binance diff stream with a REST depth snapshot."""
    buffered: list[dict] = []
    receiver = asyncio.create_task(_buffer_events(ws, buffered))
    try:
        for attempt in range(1, 4):
            snapshot = await asyncio.wait_for(
                asyncio.to_thread(get_snapshot, symbol), timeout=snapshot_timeout
            )
            last_update_id = snapshot['lastUpdateId']

            deadline = time.monotonic() + snapshot_timeout
            bridge_index = None
            while bridge_index is None:
                for index, event in enumerate(buffered):
                    if event.get('u', -1) <= last_update_id:
                        continue
                    if _is_bridge(event, last_update_id):
                        bridge_index = index
                        break
                if bridge_index is not None:
                    return snapshot, buffered[bridge_index:]
                if time.monotonic() >= deadline:
                    print(
                        f"No snapshot bridge found for lastUpdateId={last_update_id}; "
                        f"retrying snapshot ({attempt}/3)",
                        file=sys.stderr,
                    )
                    break
                await asyncio.sleep(0.05)

        raise RuntimeError('Unable to synchronize REST snapshot with depth stream')
    finally:
        receiver.cancel()
        await asyncio.gather(receiver, return_exceptions=True)


async def record_stream(symbol: str, duration_min: float, output_path: str) -> None:
    ws_url = f"wss://stream.binance.us:9443/ws/{symbol.lower()}@depth"

    print(f"Connecting to {ws_url}...")
    async with websockets.connect(ws_url) as ws:
        snapshot, buffered = await _synchronize_stream(ws, symbol)

        with open(output_path, 'w') as f:
            f.write(json.dumps(snapshot) + '\n')
            f.flush()

            previous_u = None
            for event in buffered:
                update = _event_update(event)
                if previous_u is not None:
                    previous_pu = event.get('pu')
                    sequence_ok = (
                        previous_pu == previous_u
                        if previous_pu is not None
                        else event.get('U') == previous_u + 1
                    )
                    if not sequence_ok:
                        gap = {
                            'timestamp': update['timestamp'],
                            'sequence_gap': True,
                            'previous_u': previous_u,
                            'U': event.get('U'),
                            'u': event.get('u'),
                            'pu': event.get('pu'),
                        }
                        print(f"Sequence gap detected: {gap}", file=sys.stderr)
                        f.write(json.dumps(gap) + '\n')
                        f.flush()
                        return

                f.write(json.dumps(update) + '\n')
                f.flush()
                previous_u = event.get('u')

            print(f"Recording synchronized stream for {duration_min} minutes...")
            end_time = time.time() + (duration_min * 60)
            while time.time() < end_time:
                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    event = json.loads(message)
                    update = _event_update(event)
                    previous_pu = event.get('pu')
                    sequence_ok = (
                        previous_pu == previous_u
                        if previous_pu is not None
                        else event.get('U') == previous_u + 1
                    )
                    if not sequence_ok:
                        gap = {
                            'timestamp': update['timestamp'],
                            'sequence_gap': True,
                            'previous_u': previous_u,
                            'U': event.get('U'),
                            'u': event.get('u'),
                            'pu': event.get('pu'),
                        }
                        print(f"Sequence gap detected: {gap}", file=sys.stderr)
                        f.write(json.dumps(gap) + '\n')
                        f.flush()
                        return
                    f.write(json.dumps(update) + '\n')
                    f.flush()
                    previous_u = event.get('u')
                except asyncio.TimeoutError:
                    continue

    print(f"Finished recording. Data saved to {output_path}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Binance L2 Depth Data")
    parser.add_argument('--duration', type=float, required=True, help='Duration in minutes to record')
    parser.add_argument('--output', type=str, required=True, help='Output file path (.jsonl)')
    parser.add_argument('--symbol', type=str, default='btcusd', help='Trading pair symbol (default: btcusd)')
    args = parser.parse_args()

    asyncio.run(record_stream(args.symbol, args.duration, args.output))

if __name__ == '__main__':
    main()
