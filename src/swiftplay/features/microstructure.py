from typing import Optional
from swiftplay.lob.book import OrderBook


def spread(book: OrderBook) -> Optional[float]:
    """
    Returns best_ask - best_bid, or None if book is one-sided/empty.
    """
    return book.spread


def microprice(book: OrderBook) -> Optional[float]:
    """
    Returns the volume-weighted mid price, or None if invalid book.
    """
    bb = book.best_bid
    ba = book.best_ask

    if bb is None or ba is None or ba <= bb:
        return None

    bb_size = book.bids.get(bb, 0.0)
    ba_size = book.asks.get(ba, 0.0)

    total_size = bb_size + ba_size
    if total_size == 0.0:
        return None

    return (bb * ba_size + ba * bb_size) / total_size


def order_book_imbalance(book: OrderBook, levels: int = 5) -> Optional[float]:
    """
    Returns (bid_vol - ask_vol) / (bid_vol + ask_vol) up to N levels.
    """
    bid_levels = book.get_top_levels("BUY", levels)
    ask_levels = book.get_top_levels("SELL", levels)

    bid_vol = sum(q for _, q in bid_levels)
    ask_vol = sum(q for _, q in ask_levels)

    total_vol = bid_vol + ask_vol
    if total_vol == 0.0:
        return None

    return (bid_vol - ask_vol) / total_vol


def order_flow_imbalance(book: OrderBook, prev_state: dict) -> float:
    """
    Returns OFI between prev_state and current book.
    prev_state should contain: 'best_bid', 'best_bid_size', 'best_ask', 'best_ask_size'
    """
    bb = book.best_bid
    ba = book.best_ask

    bb_size = book.bids.get(bb, 0.0) if bb is not None else 0.0
    ba_size = book.asks.get(ba, 0.0) if ba is not None else 0.0

    prev_bb = prev_state.get("best_bid")
    prev_bb_size = prev_state.get("best_bid_size", 0.0)

    prev_ba = prev_state.get("best_ask")
    prev_ba_size = prev_state.get("best_ask_size", 0.0)

    delta_w = 0.0
    if bb is not None:
        if prev_bb is None or bb > prev_bb:
            delta_w = bb_size
        elif bb == prev_bb:
            delta_w = bb_size - prev_bb_size
        else:  # bb < prev_bb
            delta_w = -prev_bb_size
    else:
        if prev_bb is not None:
            delta_w = -prev_bb_size

    delta_v = 0.0
    if ba is not None:
        if prev_ba is None or ba < prev_ba:
            delta_v = ba_size
        elif ba == prev_ba:
            delta_v = ba_size - prev_ba_size
        else:  # ba > prev_ba
            delta_v = -prev_ba_size
    else:
        if prev_ba is not None:
            delta_v = -prev_ba_size

    return delta_w - delta_v
