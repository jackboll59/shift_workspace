import code
import shift


def market_buy(ticker):
    """Submit a market buy for 1 lot (100 shares) and return the order."""
    order = shift.Order(shift.Order.Type.MARKET_BUY, ticker, 1)
    trader.submit_order(order)
    return order


def market_sell(ticker):
    """Submit a market sell for 1 lot (100 shares) and return the order."""
    order = shift.Order(shift.Order.Type.MARKET_SELL, ticker, 1)
    trader.submit_order(order)
    return order


def portfolio_balance():
    """Print buying power, realized profit/loss, and open positions."""
    summary = trader.get_portfolio_summary()
    print(f"Buying power: {summary.get_total_bp():,.2f}")
    print(f"Realized P/L: {summary.get_total_realized_pl():,.2f}")
    print("Open positions (shares):")
    has_positions = False
    for ticker, item in trader.get_portfolio_items().items():
        long_shares = item.get_long_shares()
        short_shares = item.get_short_shares()
        if long_shares or short_shares:
            print(f"  {ticker}: long={long_shares}, short={short_shares}")
            has_positions = True
    if not has_positions:
        print("  None")


if __name__ == "__main__":
    username = "username goes here"
    password = "password goes here"
    with shift.Trader(username) as trader:
        trader.connect("initiator.cfg", password)
        if not trader.is_connected():
            raise RuntimeError("SHIFT connection failed")
        code.interact(
            banner=(
                "Connected. Each call submits 1 lot (100 shares).\n"
                "Try: order = market_buy('AAPL')\n"
                "Or:  order = market_sell('AAPL')\n"
                "Inspect: trader.get_order(order.id)\n"
                "Balance: portfolio_balance()\n"
                "Press Ctrl-D to exit and disconnect."
            ),
            local=globals(),
        )
