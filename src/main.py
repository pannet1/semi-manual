import os
from traceback import print_exc

from toolkit.kokoo import is_time_past, timer

from constants import O_SETG, S_DATA, logging
from helper import Helper
from jsondb import Jsondb
from strategy import Strategy
from symbols import Symbols


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
        strgy = None
        info = None

        if any(list_of_orders):
            order_item = list_of_orders[0]
            if any(order_item):
                b = order_item["buy_order"]
                info = Helper.symbol_info(b["exchange"], b["symbol"])
                if info:
                    logging.info(f"CREATE new strategy {order_item['id']} {info}")
                    stops = O_SETG.get("stops", None)
                    if stops:
                        info["stops"] = stops.get(b["exchange"], {})
                    strgy = Strategy(
                        {}, order_item["id"], order_item["buy_order"], info
                    )
        return strgy
    except Exception as e:
        logging.error(f"{e} while creating strategy")
        print_exc()


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
        #
        write_job = []
        for strgy in strategies:
            ltps = Helper.get_quotes()
            completed_buy_order_id = strgy.run(trades_from_api, ltps)

            obj_dict = strgy.__dict__
            obj_dict.pop("_orders")
            for k, v in obj_dict.items():
                if not isinstance(v, (dict, list)):
                    print(k, v)
            timer(0.5)

            if completed_buy_order_id:
                logging.debug(f"COMPLETED buy {completed_buy_order_id}")
                Helper.completed_trades.append(completed_buy_order_id)
            else:
                write_job.append(obj_dict)
        else:
            os.system("cls" if os.name == "nt" else "clear")

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
