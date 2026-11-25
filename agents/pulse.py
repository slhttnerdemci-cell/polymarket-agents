from core.orderbook import BookSnapshot


def calculate_imbalance(book: BookSnapshot, depth: int) -> float | None:
    """I = (D_in - D_out) / (D_in + D_out). None when the book is empty."""
    if book.empty() or not book.ok:
        return None
    bid_depth = book.depth("bid", depth)
    ask_depth = book.depth("ask", depth)
    total = bid_depth + ask_depth
    if total <= 0:
        return None
    return (bid_depth - ask_depth) / total
