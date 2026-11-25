from core.orderbook import OrderBook
from core import config

def calculate_imbalance(book: OrderBook) -> float:
    bid_depth = book.get_depth("bid", config.IMBALANCE_DEPTH)
    ask_depth = book.get_depth("ask", config.IMBALANCE_DEPTH)
    total = bid_depth + ask_depth
    if total == 0:
        return 0.0
    return (bid_depth - ask_depth) / total
