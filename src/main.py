import subprocess
import sys
import time
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


def generate_table(strategies):
    # Create the structure based on your existing data
    table = Table(title="Strategy Monitor")
    table.add_column("Strategy")
    table.add_column("Key")
    table.add_column("Value")

    for strgy in strategies:
        # Using your logic to filter obj_dict
        obj_dict = strgy.__dict__
        s_id = obj_dict.get("id", "N/A")

        for k, v in obj_dict.items():
            # Exclude dicts, lists, and your specific _orders key
            if k != "_orders" and not isinstance(v, (dict, list)):
                table.add_row(str(s_id), str(k), str(v))
    return table


def strategies_to_run_from_file():
    try:
        strategies = []
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
        # 1. Early exit: Check if list is empty or first item is invalid
        if not list_of_orders or not (order_item := list_of_orders[0]):
            return None

        # 2. Extract frequently used variables early
        buy_order = order_item.get("buy_order")
        if not buy_order:
            return None

        # 3. Fetch info and exit if not found
        info = Helper.symbol_info(buy_order["exchange"], buy_order["symbol"])
        if not info:
            return None

        logging.info(f"CREATE new strategy {order_item['id']} {info}")

        # 4. Handle 'stops' more efficiently
        # Using .get().get() prevents nested if/else blocks
        exchange_stops = O_SETG.get("stops", {}).get(buy_order["exchange"])
        if exchange_stops:
            info["stops"] = exchange_stops

        # 5. Return the object directly
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


def run_strategies(strategies, trades_from_api):
    try:
        write_job = []
        for strgy in strategies:
            completed_buy_order_id = strgy.run(
                trades_from_api, Helper.get_quotes(), Helper.position_count()
            )

            obj_dict = strgy.__dict__
            obj_dict.pop("_orders")
            for k, v in obj_dict.items():
                if not isinstance(v, (dict, list)):
                    print(k, v)
            print("*" * 40)
            timer(0.5)

            if completed_buy_order_id:
                logging.debug(f"COMPLETED buy {completed_buy_order_id}")
                Helper.completed_trades.append(completed_buy_order_id)
            else:
                write_job.append(obj_dict)
        else:
            print("\n")

    except Exception as e:
        print_exc()
        logging.error(f"{e} while run_strategies")
    finally:
        return write_job


def main():
    try:
        _init()
        # auto_buy = AutoBuy(O_SETG["sleep_for"])
        while not is_time_past(O_SETG["trade"]["stop"]):
            # previously ran strategies are read from file
            strategies: list = strategies_to_run_from_file()

            trades_from_api = Helper.trades()
            strgy = create_one_strategy(
                Jsondb.filter_trades(trades_from_api, Helper.completed_trades)
            )
            if strgy:
                strategies.append(strgy)

            write_job = run_strategies(strategies, trades_from_api)
            Jsondb.write(write_job)

            # auto_buy.is_breakout(Helper.get_quotes())
    except KeyboardInterrupt:
        __import__("sys").exit()
    except Exception as e:
        print_exc()
        logging.error(f"{e} while init")


if __name__ == "__main__":
    main()
