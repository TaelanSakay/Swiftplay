#!/usr/bin/env python3
import argparse
import asyncio
import json
import requests
import time
import sys

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
        'bids': data['bids'],
        'asks': data['asks'],
        'is_snapshot': True
    }

async def record_stream(symbol: str, duration_min: float, output_path: str) -> None:
    ws_url = f"wss://stream.binance.us:9443/ws/{symbol.lower()}@depth"
    
    with open(output_path, 'w') as f:
        # 1. Fetch and write initial snapshot
        snapshot = get_snapshot(symbol)
        f.write(json.dumps(snapshot) + '\n')
        f.flush()
        
        # 2. Connect to WebSocket and record diffs
        print(f"Connecting to {ws_url} for {duration_min} minutes...")
        end_time = time.time() + (duration_min * 60)
        
        async with websockets.connect(ws_url) as ws:
            while time.time() < end_time:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    data = json.loads(msg)
                    
                    # Extract only what the OrderBook needs
                    update = {
                        'timestamp': data.get('E', int(time.time() * 1000)),
                        'bids': data.get('b', []),
                        'asks': data.get('a', [])
                    }
                    f.write(json.dumps(update) + '\n')
                    f.flush()
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    print(f"Error reading websocket: {e}", file=sys.stderr)
                    break
                    
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
