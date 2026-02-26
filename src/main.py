import sys
from traceback import print_exc
from toolkit.kokoo import is_time_past, timer
from constants import O_SETG, logging
from helper import Helper
from memorydb import Memorydb  # Switched from Jsondb
from strategy import Strategy
from symbols import Symbols
from rich.console import Console
from rich.live import Live
from rich.table import Table

def generate_table(strgy):
    """
    Directly accesses Strategy object properties. 
    Raw values, no formatting, no dict iteration.
    """
    table = Table(title=f"Live Monitor: {strgy._id}")
    table.add_column("Property", style="yellow")
    
    # Simple logic for table color
    style = "green" if strgy._ltp > strgy._fill_price else "red"
    table.add_column("Value", style=style)

    # Raw property access
    table.add_row("Symbol", str(strgy._symbol))
    table.add_row("Fill Price", str(strgy._fill_price))
    table.add_row("LTP", str(strgy._ltp))
    table.add_row("Target", str(strgy._target))
    table.add_row("Stop", str(strgy._stop))
    table.add_row("Function", str(strgy._fn))
    
    return table


def create_one_strategy(list_of_orders):
    try:
        if not list_of_orders or not (order_item := list_of_orders[0]):
            return None
        buy_order = order_item.get("buy_order")
        info = Helper.symbol_info(buy_order["exchange"], buy_order["symbol"])
        if not info: return None
        exchange_stops = O_SETG.get("stops", {}).get(buy_order["exchange"])
        if exchange_stops:
            info["stops"] = exchange_stops
        return Strategy({}, order_item["id"], buy_order, info)
    except Exception as e:
        logging.error(f"Error while creating strategy: {e}")
        return None

def _init():
    logging.info("HAPPY TRADING")
    exchanges = O_SETG["exchanges"]
    for ex in exchanges:
        Symbols(ex).get_exchange_token_map_finvasia()
    Helper.api()

def run_strategies(strategies, trades_from_api, live):
    remaining_strategies = []
    try:
        position_count = Helper.position_count()
        for strgy in strategies:
            completed_buy_order_id = strgy.run(trades_from_api, Helper.get_quotes(), position_count)

            if completed_buy_order_id:
                logging.debug(f"COMPLETED buy {completed_buy_order_id}")
                Helper.completed_trades.append(completed_buy_order_id)
            else:
                remaining_strategies.append(strgy)
                live.update(generate_table(strgy))
    except Exception as e:
        print_exc()
        logging.error(f"{e} while run_strategies")
    finally:
        return remaining_strategies

def main():
    try:
        _init()
        console = Console()
        strategies = [] # Persistent list in memory

        with Live(Table(title="Initializing..."), console=console, auto_refresh=True) as live:
            while not is_time_past(O_SETG["trade"]["stop"]):
                
                active_ids = [s._id for s in strategies]
                trades_from_api = Helper.trades()
                
                # Using the new Memory db signature
                new_trades = Memorydb.filter_trades(
                    trades_from_api, 
                    Helper.completed_trades, 
                    active_ids
                )
                
                if strgy_new := create_one_strategy(new_trades):
                    strategies.append(strgy_new)

                strategies = run_strategies(strategies, trades_from_api, live)
                timer(0.05)

    except KeyboardInterrupt:
        sys.exit()
    except Exception as e:
        print_exc()
        logging.error(f"{e} while init")

if __name__ == "__main__":
    main()
