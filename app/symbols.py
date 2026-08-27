def strip_perpetual_suffix(symbol: str) -> str:
    """Strips TradingView's perpetual-futures suffix (e.g. "BTCUSDT.P" ->
    "BTCUSDT") so the resulting name matches the broker's MT5 symbol."""
    if symbol.upper().endswith(".P"):
        return symbol[:-2]
    return symbol
