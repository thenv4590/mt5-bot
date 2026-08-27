from app.symbols import strip_perpetual_suffix


def test_strips_dot_p_suffix():
    assert strip_perpetual_suffix("BTCUSDT.P") == "BTCUSDT"
    assert strip_perpetual_suffix("ETHUSDT.P") == "ETHUSDT"


def test_leaves_normal_symbol_unchanged():
    assert strip_perpetual_suffix("BTCUSD") == "BTCUSD"
    assert strip_perpetual_suffix("ETHUSD") == "ETHUSD"


def test_is_case_insensitive_on_suffix():
    assert strip_perpetual_suffix("BTCUSDT.p") == "BTCUSDT"


def test_does_not_strip_p_in_the_middle():
    assert strip_perpetual_suffix("XAUUSD") == "XAUUSD"
