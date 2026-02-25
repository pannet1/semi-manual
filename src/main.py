import subprocess
import sys
from traceback import print_exc

from toolkit.kokoo import is_time_past, timer

from constants import O_SETG, S_DATA, logging
from helper import Helper
from jsondb import Jsondb
from strategy import Strategy
from symbols import Symbols

# --- Auto-install Rich ---
try:
    from rich.console import Console
    from rich.live import Live
    from rich.table import Table
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "rich"])
    from rich.console import Console
    from rich.live import Live
    from rich.table import Table


def generate_table(strgy):
    """Accepts ONE strategy object and returns a table for it."""
    obj_dict = strgy.__dict__
    s_id = obj_dict.get("_id", "N/A")

    table = Table(title=f"Live Monitor: {s_id}")
    table.add_column("Key", style="yellow")
    table.add_column("Value", style="green")

    for k, v in obj_dict.items():
        if not isinstance(v, (dict, list)):
            table.add_row(str(k), str(v))
    return table


def strategies_to_run_from_file():
    strategies = []
    try:
        list_of_attribs = Jsondb.read()
        if list_of_attribs and any(list_of_attribs):
            for attribs in list_of_attribs:
                strgy = Strategy(attribs, "", {}, {})
                strategies.append(strgy)
    except Exception as e:
        logging.error(f"{e} while strategies_to_run_from_file")
        print_exc()
    finally:
        return strategies


def create_one_strategy(list_of_orders):
    try:
        if not list_of_orders or not (order_item := list_of_orders[0]):
            return None

        buy_order = order_item.get("buy_order")
        if not buy_order:
            return None

        info = Helper.symbol_info(buy_order["exchange"], buy_order["symbol"])
        if not info:
            return None

        logging.info(f"CREATE new strategy {order_item['id']} {info}")

        exchange_stops = O_SETG.get("stops", {}).get(buy_order["exchange"])
        if exchange_stops:
            info["stops"] = exchange_stops

        return Strategy({}, order_item["id"], buy_order, info)

    except Exception as e:
        logging.error(f"Error while creating strategy: {e}")
        print_exc()
        return None


def _init():
    logging.info("HAPPY TRADING")
    exchanges = O_SETG["exchanges"]
    for ex in exchanges:
        Symbols(ex).get_exchange_token_map_finvasia()
    F_ORDERS = S_DATA + "orders.json"
    Jsondb.startup(F_ORDERS)
    Helper.api()


def run_strategies(strategies, trades_from_api, live):
    try:
        write_job = []
        for strgy in strategies:
            # 1. Run the strategy logic
            completed_buy_order_id = strgy.run(
                trades_from_api, Helper.get_quotes(), Helper.position_count()
            )

            # 2. Update the terminal "In-Place" for this specific strategy
            # This replaces your old print(k, v) logic
            live.update(generate_table(strgy))

            # 3. Handle the data structure for writing
            obj_dict = strgy.__dict__.copy()
            if "_orders" in obj_dict:
                obj_dict.pop("_orders")

            # 4. Timer to give you time to see the data before the next one appears
            timer(0.5)

            if completed_buy_order_id:
                logging.debug(f"COMPLETED buy {completed_buy_order_id}")
                Helper.completed_trades.append(completed_buy_order_id)
            else:
                write_job.append(obj_dict)

    except Exception as e:
        print_exc()
        logging.error(f"{e} while run_strategies")
    finally:
        return write_job


def main():
    try:
        _init()
        console = Console()

        # We wrap the main loop in Live once
        with Live(
            Table(title="Initializing..."), console=console, auto_refresh=True
        ) as live:
            while not is_time_past(O_SETG["trade"]["stop"]):
                strategies: list = strategies_to_run_from_file()

                trades_from_api = Helper.trades()
                strgy_new = create_one_strategy(
                    Jsondb.filter_trades(trades_from_api, Helper.completed_trades)
                )
                if strgy_new:
                    strategies.append(strgy_new)

                # Pass the 'live' object into your strategy runner
                write_job = run_strategies(strategies, trades_from_api, live)

                Jsondb.write(write_job)

    except KeyboardInterrupt:
        sys.exit()
    except Exception as e:
        print_exc()
        logging.error(f"{e} while init")


if __name__ == "__main__":
    main()
