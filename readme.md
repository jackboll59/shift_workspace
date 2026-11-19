# `run.py`: SHIFT API quick reference

This guide describes the current [run.py](run.py). Start with the tables for a quick lookup, then read the walkthrough for the full flow. Line numbers refer to the file as reviewed and may shift after edits.

The script connects to SHIFT, subscribes to market data, and runs a simple momentum strategy on **AAPL and MSFT**. Each strategy buys when the midpoint rises, sells when it falls, and attempts to close its position after a **15-second window measured by simulation trade timestamps**.

## Quick reference: objects and calls

`shift` is the library. `trader` is the connected account interface. Objects returned by its getters provide quotes, positions, and account totals.

### Connection and market data

| Code used in this file | Purpose / result |
| --- | --- |
| `shift.Trader(username)` | Create the account interface. |
| `trader.connect("initiator.cfg", password)` | Connect using a configuration file and account password. |
| `trader.sub_all_order_book()` | Subscribe to all order book data streams. |
| `trader.get_last_trade_time()` | Get the latest trade timestamp in the simulation as a Python `datetime`. |
| `trader.get_best_price(ticker)` | Get a `shift.BestPrice` quote object. |
| `best_price.get_bid_price()` | Get the best bid price. |
| `best_price.get_ask_price()` | Get the best ask price. |

API details: [Trader documentation](https://github.com/hanlonlab/shift-python/wiki/Trader) and [BestPrice documentation](https://github.com/hanlonlab/shift-python/wiki/BestPrice).

### Orders

| Code used in this file | Purpose / result |
| --- | --- |
| `shift.Order(type, ticker, size)` | Construct an order; construction alone does not send it. |
| `shift.Order.Type.MARKET_BUY` | Buy at available market prices. |
| `shift.Order.Type.MARKET_SELL` | Sell at available market prices. |
| `trader.submit_order(order)` | Send the order for processing. |
| `trader.get_waiting_list()` | Get pending orders that can be considered for cancellation. |
| `order.symbol` | Read the order's ticker; this is an attribute, not a method. |
| `trader.submit_cancellation(order)` | Request cancellation of that order. |

**Units in this example:** `size` is in lots of **100 shares**. `order_size = 5` therefore requests **500 shares**. Position getters below return shares, so closing orders divide by 100.

```python
# This snippet submits an order when run with a connected trader.
order = shift.Order(shift.Order.Type.MARKET_BUY, "AAPL", 5)
trader.submit_order(order)
```

Submitting an order is different from receiving a fill. Likewise, requesting cancellation is different from confirming that it completed. The API exposes `order.id`, `order.status`, and `order.executed_size`; this script does not inspect them. See [Order documentation](https://github.com/hanlonlab/shift-python/wiki/Order).

### Positions and account totals

| Code used in this file | Purpose / result |
| --- | --- |
| `trader.get_portfolio_item(ticker)` | Get the position/accounting object for one symbol. |
| `item.get_long_shares()` | Number of long shares. |
| `item.get_short_shares()` | Number of short shares. |
| `item.get_realized_pl()` | Realized profit/loss for that symbol. |
| `trader.get_portfolio_summary()` | Get the account summary object. |
| `summary.get_total_realized_pl()` | Account-wide realized profit/loss. |
| `summary.get_total_bp()` | Account-wide buying power. |

API details: [PortfolioItem documentation](https://github.com/hanlonlab/shift-python/wiki/PortfolioItem) and [PortfolioSummary documentation](https://github.com/hanlonlab/shift-python/wiki/PortfolioSummary).

For example, this chained expression:

```python
trader.get_portfolio_item(ticker).get_realized_pl()
```

means “get this ticker's portfolio object, then ask that object for realized P/L.”

## Trading terms used here

| Term | Meaning in this script |
| --- | --- |
| Bid | Best price buyers currently offer. |
| Ask | Best price sellers currently request. |
| Midpoint / midprice | `(best_bid + best_ask) / 2`; calculated by the script, not a guaranteed execution price. |
| Long | Shares held that the script can sell to reduce the position. |
| Short | Shares sold short that the script can buy back to close. |
| Buying power (`bp`) | Account capacity available for trading, subject to SHIFT's rules. |
| Realized P/L | Profit/loss recognized on closed trades; open positions can still have unrealized P/L. |

## Execution flow

```text
Entry point: create Trader → connect → subscribe → main(trader)
    main: choose end time and record account starting P/L
        start strategy(AAPL) in a thread
        start strategy(MSFT) in another thread
            each strategy: read midpoint → buy/sell → pause → repeat
            each strategy: cancel pending orders → attempt to close position
        wait for both threads
        repeat cleanup for AAPL and MSFT
        print final buying power and change in realized P/L
```

### 1. Entry point — lines 174–181

`if __name__ == "__main__":` runs this block when you execute `python run.py`; importing the file does not run this block.

The `with shift.Trader(...) as trader:` block manages the Trader's context. Inside it, the script connects using `initiator.cfg`, sleeps for one second, subscribes to all order books, sleeps again, and calls `main(trader)`. The sleeps give setup time to progress; the code does not explicitly verify data readiness. Credentials are omitted from this guide.

### 2. `main(trader)` — lines 120–171

This function coordinates timing, workers, and final reporting:

1. Read the latest simulation trade time and use it as `start_time`.
2. Set `end_time = start_time + timedelta(seconds=15)`.
3. Record the account's initial realized P/L.
4. Create one `Thread` per ticker, passing the same `trader` and `end_time` to each.
5. Start the threads with a one-second pause after each start.
6. Wait until the latest simulation trade time reaches the end time, then `join()` each worker.
7. Attempt cancellation and position closure again for both symbols.
8. Print final buying power and the change in account realized P/L.

The market-open waiting loop normally does nothing with the current `start_time = current` setting. The commented `datetime.combine(...)` lines show an alternative schedule using specific times on the simulation date.

The ticker threads share one account and its buying power. Their price comparisons are separate, but their financial resources are shared. The second worker starts later and therefore has less time before the common deadline.

### 3. `strategy(trader, ticker, endtime)` — lines 55–117

Before looping, the function records the symbol's starting realized P/L, sets a one-second pause and five-lot order size, and saves an initial midpoint as `previous_price`.

Each iteration cancels pending orders for that symbol, reads another quote, and applies this rule:

| New midpoint compared with previous midpoint | Action |
| --- | --- |
| Higher | Submit a market buy for 5 lots. |
| Lower | Submit a market sell for 5 lots. |
| Equal | Submit no new order. |

It then saves the new midpoint and sleeps for one second. This is a simple momentum rule: it assumes the latest price movement will continue. It does not forecast from a historical series.

For example, a bid of `100.00` and ask of `100.10` produce a midpoint of `100.05`. If the next midpoint is `100.07`, the strategy submits a 500-share buy. The fill price can differ from `100.07` because that value is only the quote midpoint.

Buying can reduce an existing short position; selling can reduce an existing long position. Selling beyond the existing long position can create a short position, as the source comments explain.

After the loop, the worker requests cancellations, attempts to close its position, and prints:

```python
current_symbol_realized_pl - initial_symbol_realized_pl
```

### 4. `cancel_orders(trader, ticker)` — lines 11–16

This helper scans the account's waiting list, filters by `order.symbol == ticker`, requests each matching cancellation, and sleeps one second after each request. It cancels orders; it does not close already filled positions.

That ticker filter matters because both workers use the same account. The sleep also means cancellation can add several seconds to an iteration if several matching orders are waiting.

### 5. `close_positions(trader, ticker)` — lines 19–52

This helper reads the symbol's portfolio item and submits opposite-side orders:

| Holding found | Closing order | Size calculation |
| --- | --- | --- |
| Long shares | Market sell | `int(long_shares / 100)` lots |
| Short shares | Market buy | `int(short_shares / 100)` lots |

For example, 500 long shares produce a sell order of size `5`. Each submission is followed by a one-second pause. The function attempts closure but does not check whether the resulting position is zero.

## Settings to find quickly

| To change… | Edit… | Current value / location |
| --- | --- | --- |
| Symbols traded | `tickers` in `main()` | `["AAPL", "MSFT"]`, line 139 |
| Trading window | `timedelta(seconds=15)` | 15 simulation timestamp seconds, line 127 |
| Order size | `order_size` in `strategy()` | 5 lots / 500 shares, line 64 |
| Pause between strategy iterations | `check_freq` | 1 real second, line 63 |
| Main loop polling pause | `check_frequency` | 1 real second, line 122 |
| Buy/sell decision | Midpoint comparisons in `strategy()` | Lines 83–98 |
| Account and connection | Entry point | `Trader(...)` and `connect(...)`, lines 175–176 |

## Details that affect how you interpret a run

These observations come from the current code:

- **Two clocks are involved.** `sleep(1)` pauses for a real second. The stopping condition uses the latest simulation trade timestamp, which may advance at a different rate or stop advancing. Thus, this is not necessarily a 15-second wall-clock run. The API defines that timestamp in its [Trader documentation](https://github.com/hanlonlab/shift-python/wiki/Trader).
- **The deadline is checked between iterations.** Cancellation delays and sleeps can carry an iteration beyond the deadline, and cleanup takes additional time.
- **A one-second pause is not a completion check.** The `[ORDER_SUBMITTED]` message records a submission attempt, not a confirmed fill. Cleanup repeats in `main()`, but neither cleanup pass verifies that orders are gone and positions are zero.
- **Positions can accumulate.** The strategy does not enforce a position limit or check buying power before submitting. The source specifically notes that closing shorts requires sufficient buying power and that closing positions requires liquidity.
- **Closure assumes whole lots.** `int(shares / 100)` truncates. If a position were not a multiple of 100 shares, this calculation would leave a remainder or produce a zero-lot order below 100 shares.
- **Final P/L is realized P/L only.** Both printed deltas subtract a starting realized P/L value. Remaining open exposure would not be fully represented by those numbers. Account-wide P/L also includes any other activity on that account during the interval.
- **Worker failures are not handled explicitly.** An exception in a strategy thread is not collected and re-raised by `main()`. `join()` waits for termination and has no timeout here; it can wait indefinitely if a worker never exits.

## Python syntax worth recognizing

| Syntax | Meaning here |
| --- | --- |
| `trader: shift.Trader`, `ticker: str` | Type hints documenting intended argument types; they do not enforce them at runtime. |
| `Thread(target=strategy, args=(trader, ticker, end_time))` | Prepare a worker that will call `strategy(...)` when started. |
| `thread.start()` / `thread.join()` | Start a worker / wait for it to finish. |
| `timedelta(seconds=15)` | A duration added to a `datetime` to create the deadline. |
| `f"...{ticker}..."` | Insert a variable's value into a string. |
| `print(..., flush=True)` | Flush output immediately so logs appear promptly. |

`datetime` and the alias `dt` are used only in the commented scheduling examples; `timedelta` is used in the active code.
