"""
    Purchase price for each trade plus 5% should be auto exit separately
    Options stike chart respective 9.16 one min candle low will be stop loss
    Buy will be manual  and sell will be algo with both target and stoploss.
    Multiple trades will be triggered and to be tracked separetely.
"""

from constants import logging, O_SETG
from helper import Helper
from traceback import print_exc


class Strategy:
    def __init__(self, attribs: dict, id: str, buy_order: dict, symbol_info: dict):
        if any(attribs):
            self.__dict__.update(attribs)
        else:
            self._id = id
            self._buy_order = buy_order
            self._symbol = symbol_info["symbol"]
            self._fill_price = float(buy_order["fill_price"])
            self._low = float(symbol_info["low"])
            self._ltp = float(symbol_info["ltp"])
            self._stop = float(symbol_info["low"])
            self._condition = symbol_info["condition"]
            exchange = self._buy_order["exchange"]
            self._target = O_SETG["targets"][exchange]
            self._sell_order = ""
            self._orders = []
            self._set_target_and_stop()
            self._fn = "place_sell_order"

    def _set_target_and_stop(self):
        try:
            target_buffer = self._target * self._fill_price / 100
            target_virtual = self._fill_price + target_buffer
            self._target = target_virtual
            if self._buy_order["exchange"] != "MCX":
                if self._fill_price < self._low:
                    self._target = min(target_virtual, self._low)
            self._target = round(self._target / 0.05) * 0.05

            if eval(self._condition):
                self._stop = 0.00

        except Exception as e:
            print_exc()
            print(f"{e} while set target")

    def _is_target_reached(self):
        try:
            flag = False
            for order in self._orders:
                if self._sell_order == order["order_id"]:
                    logging.debug(
                        f"{self._buy_order['symbol']} target order {self._sell_order} is reached"
                    )
                    flag = True
        except Exception as e:
            logging.error(f"{e} get order from book")
            print_exc()
        finally:
            return flag

    def place_sell_order(self):
        try:
            self._fn = "exit_order"
            sargs = dict(
                symbol=self._buy_order["symbol"],
                quantity=abs(int(self._buy_order["quantity"])),
                product=self._buy_order["product"],
                side="S",
                price=self._target,
                trigger_price=0,
                order_type="LIMIT",
                exchange=self._buy_order["exchange"],
                tag="exit",
            )
            logging.debug(sargs)
            self._sell_order = Helper.one_side(sargs)

            # Validate sell order response
            if not self._sell_order or not isinstance(self._sell_order, str):
                logging.error(f"Invalid sell order response: {self._sell_order}")
                __import__("sys").exit(1)
            else:
                logging.info(
                    f"TARGET order for {self._buy_order} is {self._sell_order}"
                )

        except Exception as e:
            logging.error(f"{e} while place sell order")
            print_exc()

    def exit_order(self):
        try:
            if self._stop == 0:
                logging.debug(f"REMOVING {self._id} order because {self._stop}")
                return self._id
            elif self._is_target_reached():
                return self._id
            elif eval(self._condition):
                logging.debug(f"REMOVING {self._id} because {self._condition} met")
                if self._buy_order["exchange"] == "MCX":
                    exit_buffer = 50 * self._fill_price / 100
                    exit_virtual = self._fill_price - exit_buffer
                else:
                    exit_buffer = 2 * self._ltp / 100
                    exit_virtual = self._ltp - exit_buffer
                args = dict(
                    symbol=self._buy_order["symbol"],
                    order_id=self._sell_order,
                    exchange=self._buy_order["exchange"],
                    quantity=abs(int(self._buy_order["quantity"])),
                    order_type="LIMIT",
                    price=round(exit_virtual / 0.05) * 0.05,
                    trigger_price=0.00,
                )
                logging.debug(f"modify order {args}")
                resp = Helper.modify_order(args)
                logging.debug(f"order id: {args['order_id']} modify {resp=}")
                return self._id
            else:
                return None

        except Exception as e:
            logging.error(f"{e} while exit order")
            print_exc()

    def run(self, orders, ltps):
        try:
            self._orders = orders
            ltp = ltps.get(self._symbol, None)
            if ltp is not None:
                self._ltp = float(ltp)
            result = getattr(self, self._fn)()
            return result
        except Exception as e:
            logging.error(f"{e} in run for buy order {self._id}")
            print_exc()
