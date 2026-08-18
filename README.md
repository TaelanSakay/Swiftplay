# Swiftplay

Swiftplay is a cryptocurrency market-making system built for Binance.US BTCUSD. The core architectural philosophy of Swiftplay is a focus on **decision-quality quoting** rather than pure execution speed.

## Architecture: The Decision-Centric Design

A common pitfall in trading system design is tightly coupling the market data feed, order book logic, and trading strategies. 

Swiftplay avoids this by explicitly separating **Decision Logic** from **Execution & I/O**:
- **The Core:** The strategy (Decision Engine) is pure business logic. It takes current market state and features as inputs, and returns a `Quote` action with an explicit reasoning trace.
- **The Periphery:** Data feeds (WebSocket or historical replay), limit order book simulation, and execution engines are decoupled boundaries.

This provides key benefits:
1. **Unit Testability:** Strategies can be extensively unit-tested using synthetic market states without requiring a live connection or complex data fixtures.
2. **Seamless Backtesting:** We can swap a live WebSocket feed for a historical file replay, and a live execution engine for a Limit Order Book (LOB) simulator, without changing a single line of the decision logic.
3. **Observability:** By returning explicit reasoning traces (e.g., expected value, fill probability, inventory penalty), strategies become inspectable and debuggable.

## Known Limitations

- **Queue Position Tracking:** Binance's public depth stream only provides L2 data (aggregate quantity per price level), not L3 (individual order-level data). This means we cannot distinguish whether a depth decrease at a price level is due to fills or cancellations, or whether it happened ahead of or behind our resting order. **Our approximation:** We treat all depth decreases at a price level as reducing the volume ahead of our order. This is a standard simplifying assumption used in LOB backtesting without L3 data, though it tends to be slightly optimistic on fill probability.
- **Historical Sample Synchronization:** The original `data/sample_btcusd_depth.jsonl` was recorded without proper REST snapshot/WebSocket sequence synchronization, causing approximately 97.6% of replay ticks to show a crossed order book because stale price levels remained in the reconstructed state. `scripts/fetch_historical_data.py` now follows Binance's documented synchronization procedure, preserves `U`/`u`/`pu` sequence fields, and records discontinuities explicitly. Results generated from the original sample should be considered invalid; regenerate the sample before relying on backtest metrics.

## Feature Overview

- **Decision Engine Interface:** Swappable strategies (Fixed Spread, Inventory-aware, EV-based).
- **LOB Simulation:** Realistic Limit Order Book modeling with queue position and partial fills.
- **Backtesting Harness:** Framework to evaluate strategies on Sharpe ratio, PnL, and max drawdown.
- **Risk Management:** Extensible limits on inventory, max drawdown, and volatility.

## Quick Start

### Installation

```bash
make install
```

### Running Tests

```bash
make test
```

### Linting

```bash
make lint
```

## Performance

We included a small benchmark/profiling suite in `scripts/` to establish a baseline before any native optimizations.

On the bundled sample (~64 updates) the baseline (before algorithmic feature optimizations) was:

- Throughput: ~718 updates/sec
- Median per-update latency: ~1007 µs
- P99 per-update latency: ~2692 µs

After incremental algorithmic improvements (cached best-price lookups and top-N level access), the same sample measured:

- Throughput: ~2136 updates/sec
- Median per-update latency: ~151 µs
- P99 per-update latency: ~761 µs

These numbers establish the pre-C++ baseline. See `scripts/benchmark.py` and `scripts/profile_lob.py` for reproduction steps and raw profiles (`.prof` files) saved by the profiler.

## Fill Probability Model

The fill model is trained from `FixedSpreadStrategy` replay examples in `data/training/fill_labels.csv`. Each quote side contributes one example containing distance from mid, spread, order-book imbalance, OFI, and realized volatility. The label is whether the quote crossed within the next tick. Training uses a time-based 80/20 split so later observations remain held out.

Two scikit-learn baselines are compared:

- Logistic Regression: AUC `0.7824`, log loss `0.0849`, calibration MCE `0.1575`
- Gradient Boosting: AUC `0.8165`, log loss `0.0804`, calibration MCE `0.1582`

Gradient Boosting was selected on held-out AUC and is saved under `src/swiftplay/models/artifacts/`. The trained estimator is a drop-in implementation of `FillProbabilityEstimator` for `EVQuotingStrategy`.

On the current sample, the heuristic EV strategy produced total PnL `-$227,444.53` and Sharpe `-1152.34`; the trained estimator produced `-$224,540.57` and Sharpe `-1134.87`. Both used a volume-based fill rate near `85.5%`, after fixing the previous event-count accounting bug. These PnL and Sharpe values are not performance claims: the current EV strategy allows inventory to grow far beyond its nominal limit because its penalty is not a hard risk control. Add explicit inventory limits before using this comparison to judge model quality.

Generate and train the model with:

```bash
$env:PYTHONPATH="src"
py -3 -m swiftplay.models.generate_training_data --data data/sample_btcusd_depth.jsonl --spread 80 --lookahead-ticks 1
py -3 -m swiftplay.models.train_fill_model --data data/training/fill_labels.csv
```
