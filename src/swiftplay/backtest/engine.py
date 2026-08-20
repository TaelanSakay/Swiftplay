from typing import List
from dataclasses import dataclass
from typing import Optional
from swiftplay.data_feed.interfaces import DataFeed
from swiftplay.lob.book import OrderBook
from swiftplay.lob.fills import FillEvent
from swiftplay.features.pipeline import FeaturePipeline
from swiftplay.decision.interfaces import QuoteDecisionEngine, MarketState
from swiftplay.risk import RiskManager


@dataclass
class BacktestConfig:
    initial_capital: float = 100000.0
    vol_window: int = 20
    imb_levels: int = 5
    risk_manager: Optional[RiskManager] = None


@dataclass
class StepRecord:
    timestamp: int
    mid_price: float
    inventory: float
    cash: float
    pnl: float
    fills: List[FillEvent]


class BacktestRunner:
    def __init__(
        self, strategy: QuoteDecisionEngine, feed: DataFeed, config: BacktestConfig
    ):
        self.strategy = strategy
        self.feed = feed
        self.config = config

        self.book = OrderBook()
        self.pipeline = FeaturePipeline(
            vol_window=config.vol_window, imb_levels=config.imb_levels
        )

        self.cash = config.initial_capital
        self.inventory = 0.0
        self.risk_manager = config.risk_manager or RiskManager(config.initial_capital)

        self.quotes_placed = 0
        self.quotes_filled = 0
        self.quoted_volume = 0.0
        self.filled_volume = 0.0
        self.invalid_quotes = 0

        self.history: List[StepRecord] = []

    def run(self) -> List[StepRecord]:
        active_bid_id = None
        active_ask_id = None

        for update in self.feed:
            # 1. Update Market
            self.book.process_market_update(update)

            # 2. Extract Features
            features = self.pipeline.compute(self.book)

            # 3. Process any fills from the depth update crossing our resting orders
            fills = self.book.get_recent_fills()
            for fill in fills:
                self.quotes_filled += 1
                self.filled_volume += fill.fill_quantity
                if fill.order_id.startswith("BID_"):
                    self.inventory += fill.fill_quantity
                    self.cash -= fill.fill_price * fill.fill_quantity
                elif fill.order_id.startswith("ASK_"):
                    self.inventory -= fill.fill_quantity
                    self.cash += fill.fill_price * fill.fill_quantity

            # 4. Record State
            mid_price = self.book.mid_price or 0.0
            unrealized = self.inventory * mid_price
            pnl = (self.cash + unrealized) - self.config.initial_capital
            equity = self.cash + unrealized
            self.risk_manager.update_equity(equity)

            self.history.append(
                StepRecord(
                    timestamp=self.book.current_timestamp,
                    mid_price=mid_price,
                    inventory=self.inventory,
                    cash=self.cash,
                    pnl=pnl,
                    fills=fills,
                )
            )

            # 5. Make new decision if book is somewhat valid
            if self.book.best_bid is not None and self.book.best_ask is not None:
                state = MarketState(
                    bid_price=self.book.best_bid,
                    ask_price=self.book.best_ask,
                    bid_qty=self.book.bids.get(self.book.best_bid, 0.0),
                    ask_qty=self.book.asks.get(self.book.best_ask, 0.0),
                    timestamp=self.book.current_timestamp,
                )

                quote = self.strategy.generate_quote(state, features, self.inventory)
                quote = self.risk_manager.apply(
                    quote, state, features, self.inventory, equity
                )
                if (
                    quote.bid_price is not None
                    and quote.ask_price is not None
                    and quote.bid_price >= quote.ask_price
                ):
                    self.invalid_quotes += 1

                # Replace resting orders
                if active_bid_id:
                    self.book.cancel_order(active_bid_id)
                if active_ask_id:
                    self.book.cancel_order(active_ask_id)

                active_bid_id = f"BID_{self.quotes_placed}"
                active_ask_id = f"ASK_{self.quotes_placed}"

                if (
                    quote.bid_price is not None
                    and quote.bid_qty is not None
                    and quote.bid_qty > 0
                ):
                    self.book.place_order(
                        active_bid_id, "BUY", quote.bid_price, quote.bid_qty
                    )
                    self.quotes_placed += 1
                    self.quoted_volume += quote.bid_qty

                if (
                    quote.ask_price is not None
                    and quote.ask_qty is not None
                    and quote.ask_qty > 0
                ):
                    self.book.place_order(
                        active_ask_id, "SELL", quote.ask_price, quote.ask_qty
                    )
                    self.quotes_placed += 1
                    self.quoted_volume += quote.ask_qty

        return self.history
