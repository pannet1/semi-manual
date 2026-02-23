from traceback import print_exc

from constants import O_SETG, logging
from helper import Helper
from symbols import find_colval_from_exch_symbol


class Strategy:
    def __init__(self, attribs: dict, id: str, buy_order: dict, symbol_info: dict):
        if any(attribs):
            self.__dict__.update(attribs)
        else:
            self._id = id
            self._buy_order = buy_order
            self._symbol = symbol_info["symbol"]
            self._fill_price = float(buy_order["fill_price"])
            self._exchange = self._buy_order["exchange"]
            self._prefix, self._option_type = find_colval_from_exch_symbol(
                option_exchange=self._exchange,
                ts=symbol_info["symbol"],
            )
            if isinstance(self._option_type, str):
                self._option_type += "E"

            # todo low to be removed
            self._low = float(symbol_info["low"])
            self._ltp = float(symbol_info["ltp"])
            # remove condition from mai
            # self._condition = symbol_info["condition"]
            self.stops = symbol_info["stops"]
            self._sell_order = ""
            self._orders = []
            self._conditions = [
                "self._fill_price < self._stop",
                "self._ltp > self._target",
                "self._ltp < self._stop",
            ]
            # stop set from outside
            self._set_target_and_stop()

    def _set_target_and_stop(self):
        try:
            # Default target
            target_str = "2%"

            # Deep lookup using walrus operator
            if (targets := O_SETG.get("targets")) and isinstance(targets, dict):
                if (ex_targets := targets.get(self._exchange)) and (
                    val := ex_targets.get(self._option_type)
                ):
                    target_str = str(val).strip()

            # Calculation logic
            if target_str.endswith("%"):
                pct_value = float(target_str.replace("%", ""))
                target_buffer = (pct_value * self._fill_price) / 100
            else:
                target_buffer = float(target_str)

            # Final definitive float cleaning
            self._target = float(f"{(self._fill_price + target_buffer):.2f}")

            logging.info(f"Target set at: {self._target}")

            # self.stops = {"CE": 12, .. }
            if val := self.stops.get(self._prefix):
                self._stop = val[self._option_type]
            else:
                self._stop = self._low

            logging.info(f"Stop set at: {self._stop}")

            self._fn = "try_to_exit"

        except Exception as e:
            logging.error(f"Error in target or stop setting: {e}")
            print_exc()

    def _exit_trade(self):
        try:
            limit_price = self._get_aggressive_sell_price()
            sargs = dict(
                symbol=self._buy_order["symbol"],
                quantity=abs(int(self._buy_order["quantity"])),
                product=self._buy_order["product"],
                side="S",
                price=limit_price,
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
            self._fn = "remove_me"

        except Exception as e:
            logging.error(f"{e} while place sell order")
            print_exc()

    def _modify_order(self):
        limit_price = self._get_aggressive_sell_price()
        args = dict(
            symbol=self._buy_order["symbol"],
            order_id=self._sell_order,
            exchange=self._buy_order["exchange"],
            quantity=abs(int(self._buy_order["quantity"])),
            order_type="LIMIT",
            price=limit_price,
            trigger_price=0.00,
        )
        logging.debug(f"modify order {args}")
        resp = Helper.modify_order(args)
        logging.debug(f"order id: {args['order_id']} modify {resp=}")

    def remove_me(self):
        try:
            for order in self._orders:
                if self._sell_order == order["order_id"]:
                    return self._id
            self._modify_order()
        except Exception as e:
            logging.error(f"{e} get order from book")
            print_exc()

    def try_to_exit(self):
        try:
            for condition in self._conditions:
                result = eval(condition)
                if result:
                    self._exit_trade()
                    logging.info(
                        f"exiting because of {condition} s:{self._stop} f:{self._fill_price} t:{self._target}"
                    )
                    logging.info(
                        f"exiting because of {condition} s:{self._stop} f:{self._fill_price} t:{self._target}"
                    )
                    return
        except Exception as e:
            logging.error(f"{e} while exit order")
            print_exc()

    def run(self, orders, ltps):
        try:
            self._orders = orders
            ltp = ltps.get(self._symbol, None)
            if ltp is not None:
                self._ltp = float(ltp)
            return getattr(self, self._fn)()
        except Exception as e:
            logging.error(f"{e} in run for buy order {self._id}")
            print_exc()

    def _get_aggressive_sell_price(self):
        """
        Calculates a Sell Limit price to act as a Market Order.
        Ensures the price is at least one tick below LTP to guarantee execution.
        """
        # 1. Determine Tick Size based on Exchange
        # MCX often uses 1.0 or 0.05; NSE uses 0.05
        tick = 1.0 if self._buy_order["exchange"] == "MCX" else 0.05

        # 2. Calculate initial aggressive price (e.g., 0.1% below LTP)
        raw_price = self._ltp * 0.999

        # 3. Align to Tick
        tick_aligned = round(raw_price / tick) * tick

        # 4. FORCE STEP-DOWN: If rounding brought us back to LTP,
        # manually subtract one tick to ensure we are 'worse' than LTP.
        if tick_aligned >= self._ltp:
            tick_aligned -= tick

        # 5. Clean the float precision for the API
        # Using 'g' or 'f' formatting depending on tick size
        # to handle whole numbers (MCX) or decimals (NSE)
        return float(f"{tick_aligned:.2f}")
