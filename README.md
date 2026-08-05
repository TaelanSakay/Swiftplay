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
