from functools import partial

from app import mt5_client
from app.config import StrategyConfig, get_mt5_password, is_dry_run
from app.logging_config import logger
from app.mt5_client import MT5Error
from app.schemas import OrderId, OrderResult, TradingViewAlert
from app.symbols import strip_perpetual_suffix


class OrderExecutionError(Exception):
    pass


def _compute_investment(strategy: StrategyConfig, order_ratio: float) -> float:
    return strategy.price * 1000 * order_ratio


def _build_close_request(position, strategy: StrategyConfig, symbol: str, filling_mode, tick, deviation: int) -> dict:
    if position.type == mt5_client.POSITION_TYPE_BUY:
        order_type = mt5_client.ORDER_TYPE_SELL
        close_price = tick.bid
    else:
        order_type = mt5_client.ORDER_TYPE_BUY
        close_price = tick.ask

    return {
        "action": mt5_client.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": position.volume,
        "type": order_type,
        "position": position.ticket,
        "price": close_price,
        "deviation": deviation,
        "magic": strategy.magic,
        "comment": strategy.comment,
        "type_time": mt5_client.ORDER_TIME_GTC,
        "type_filling": filling_mode,
    }


def _build_open_request(
    order_type, volume: float, strategy: StrategyConfig, symbol: str, filling_mode, tick, deviation: int
) -> dict:
    price = tick.ask if order_type == mt5_client.ORDER_TYPE_BUY else tick.bid

    return {
        "action": mt5_client.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "deviation": deviation,
        "magic": strategy.magic,
        "comment": strategy.comment,
        "type_time": mt5_client.ORDER_TIME_GTC,
        "type_filling": filling_mode,
    }


def execute_order(alert: TradingViewAlert, strategy: StrategyConfig) -> OrderResult:
    """Executes one webhook alert end-to-end against MT5.

    Runs entirely under MT5_LOCK: the MetaTrader5 API is a single
    connection per process, so two webhook requests (e.g. for two
    different strategies/accounts) must never interleave their MT5 calls.
    """
    with mt5_client.MT5_LOCK:
        dry_run = is_dry_run(strategy)
        # TradingView's perpetual-futures ticker suffix (".P", e.g.
        # "BTCUSDT.P") never matches a real MT5 symbol name, so it's
        # stripped before this is used for anything MT5-related.
        symbol = strip_perpetual_suffix(alert.symbol)

        try:
            # Real market prices (for volume sizing and order pricing)
            # always come from the MT5 terminal, even in dry-run mode, so
            # connection is required regardless of dry_run.
            password = get_mt5_password(alert.strategy)
            mt5_client.ensure_connection(strategy, password)

            if alert.order_id == OrderId.OPEN_LONG:
                return _open_position(alert, strategy, symbol, mt5_client.ORDER_TYPE_BUY, dry_run)
            elif alert.order_id == OrderId.OPEN_SHORT:
                return _open_position(alert, strategy, symbol, mt5_client.ORDER_TYPE_SELL, dry_run)
            elif alert.order_id == OrderId.CLOSE_LONG:
                return _close_positions(
                    alert, strategy, symbol, mt5_client.POSITION_TYPE_BUY, dry_run
                )
            elif alert.order_id == OrderId.CLOSE_SHORT:
                return _close_positions(
                    alert, strategy, symbol, mt5_client.POSITION_TYPE_SELL, dry_run
                )
            else:
                raise OrderExecutionError(f"Unsupported order_id: {alert.order_id}")
        except MT5Error as e:
            logger.error("MT5 error while executing order: %s", e)
            raise OrderExecutionError(str(e)) from e


def _open_position(
    alert: TradingViewAlert, strategy: StrategyConfig, symbol: str, order_type, dry_run: bool
) -> OrderResult:
    symbol_info = mt5_client.get_symbol_info(symbol)
    mt5_client.ensure_symbol_tradable(symbol_info)
    filling_mode = mt5_client.resolve_filling_mode(symbol_info)

    tick = mt5_client.get_tick(symbol)
    market_price = tick.ask if order_type == mt5_client.ORDER_TYPE_BUY else tick.bid

    investment = _compute_investment(strategy, alert.order_ratio)
    raw_volume = investment / market_price
    volume = mt5_client.normalize_volume(symbol_info, raw_volume)

    if dry_run:
        logger.info(
            "[DRY RUN] strategy=%s symbol=%s action=%s investment=%s market_price=%s volume=%s",
            alert.strategy,
            symbol,
            alert.order_id.value,
            investment,
            market_price,
            volume,
        )
        return OrderResult(
            success=True,
            dry_run=True,
            strategy=alert.strategy,
            symbol=symbol,
            action=alert.order_id.value,
            volume=volume,
            price=market_price,
            message="Dry run: no order sent to MT5",
        )

    logger.info(
        "Sending open order: strategy=%s symbol=%s type=%s volume=%s filling_mode=%s",
        alert.strategy,
        symbol,
        order_type,
        volume,
        filling_mode,
    )
    build_request = partial(
        _build_open_request, order_type, volume, strategy, symbol, filling_mode
    )
    result = mt5_client.send_order_with_retry(build_request, symbol, strategy.deviation)

    success = result.retcode == mt5_client.TRADE_RETCODE_DONE
    if not success:
        logger.error(
            "Order failed: retcode=%s comment=%s", result.retcode, result.comment
        )

    return OrderResult(
        success=success,
        dry_run=False,
        strategy=alert.strategy,
        symbol=symbol,
        action=alert.order_id.value,
        volume=volume,
        price=result.price if success else None,
        order_ticket=result.order if success else None,
        message=result.comment,
    )


def _close_positions(
    alert: TradingViewAlert, strategy: StrategyConfig, symbol: str, position_type, dry_run: bool
) -> OrderResult:
    positions = mt5_client.get_open_positions(symbol, strategy.magic)
    positions = [p for p in positions if p.type == position_type]

    if not positions:
        message = (
            f"No open {'LONG' if position_type == mt5_client.POSITION_TYPE_BUY else 'SHORT'} "
            f"position found for symbol={symbol} magic={strategy.magic}"
        )
        logger.warning(message)
        return OrderResult(
            success=False,
            dry_run=dry_run,
            strategy=alert.strategy,
            symbol=symbol,
            action=alert.order_id.value,
            message=message,
        )

    total_volume = sum(p.volume for p in positions)

    if dry_run:
        logger.info(
            "[DRY RUN] strategy=%s symbol=%s action=%s would close %d position(s) volume=%s",
            alert.strategy,
            symbol,
            alert.order_id.value,
            len(positions),
            total_volume,
        )
        return OrderResult(
            success=True,
            dry_run=True,
            strategy=alert.strategy,
            symbol=symbol,
            action=alert.order_id.value,
            volume=total_volume,
            message=f"Dry run: would close {len(positions)} position(s), no order sent to MT5",
        )

    symbol_info = mt5_client.get_symbol_info(symbol)
    filling_mode = mt5_client.resolve_filling_mode(symbol_info)

    last_result = None
    all_success = True

    for position in positions:
        build_request = partial(
            _build_close_request, position, strategy, symbol, filling_mode
        )
        logger.info(
            "Closing position: strategy=%s ticket=%s volume=%s",
            alert.strategy,
            position.ticket,
            position.volume,
        )
        result = mt5_client.send_order_with_retry(build_request, symbol, strategy.deviation)
        success = result.retcode == mt5_client.TRADE_RETCODE_DONE
        all_success = all_success and success
        last_result = result
        if not success:
            logger.error(
                "Close failed for ticket=%s: retcode=%s comment=%s",
                position.ticket,
                result.retcode,
                result.comment,
            )

    return OrderResult(
        success=all_success,
        dry_run=False,
        strategy=alert.strategy,
        symbol=symbol,
        action=alert.order_id.value,
        volume=total_volume,
        price=last_result.price if last_result else None,
        order_ticket=last_result.order if last_result else None,
        message=last_result.comment if last_result else "No positions closed",
    )
