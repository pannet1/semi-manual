from enum import IntEnum
from traceback import print_exc
from constants import logging
from helper import Helper
import pendulum as pdlm


class BuyType(IntEnum):
    START = 0
    LOW = 1
    BREAK = 2


class AutoBuy:
    """
    Auto Buy
    - stores a buy symbol as key
    """

    buy_symbols = {}

    def __init__(self, pdlm_args: dict):
        self.pdlm_args = pdlm_args

    def _new(self, symbol, qty_low_ltp: dict):
        self.buy_symbols[symbol] = qty_low_ltp

    def _lesser_quantity(self, symbol, quantity):
        self.buy_symbols[symbol]["quantity"] = quantity

    def init(self, symbol: str, qty_low_ltp: dict):
        """
        init new buy order
        qty_low_ltp = {
            "low": low,
            "quantity": quantity
            "product": product
            "exchange": exchange
        }

        """
        if not self.buy_symbols.get(symbol, None):
            qty_low_ltp["status"] = BuyType.START
            qty_low_ltp["next_trade"] = pdlm.now()
            self._new(symbol, qty_low_ltp)

        quantity = qty_low_ltp["quantity"]
        if self.buy_symbols[symbol]["quantity"] > quantity:
            self._lesser_quantity(symbol, quantity)

    def _update_low(self, symbol, ltp):
        if ltp < self.buy_symbols[symbol]["low"]:
            self.buy_symbols[symbol]["status"] = BuyType.LOW

    def is_breakout(self, ltps):
        try:
            for symbol in self.buy_symbols.keys():
                ltp = ltps.get(symbol, None)
                if (
                    ltp
                    and float(ltp) > self.buy_symbols[symbol]["low"]
                    and self.buy_symbols[symbol]["status"] == BuyType.LOW
                    and pdlm.now() > self.buy_symbols[symbol]["next_trade"]
                ):
                    bargs = dict(
                        symbol=symbol,
                        quantity=self.buy_symbols[symbol]["quantity"],
                        product=self.buy_symbols[symbol]["product"],
                        side="B",
                        price=float(ltp) + 2,
                        trigger_price=0,
                        order_type="LIMIT",
                        exchange=self.buy_symbols[symbol]["exchange"],
                    )
                    logging.debug(bargs)
                    order_id = Helper.one_side(bargs)
                    self.buy_symbols[symbol]["status"] = BuyType.START
                    self.buy_symbols[symbol]["next_trade"] = pdlm.now().add(
                        **self.pdlm_args
                    )
                    if not order_id or not isinstance(order_id, str):
                        logging.error(f"Invalid buy order response: {order_id}")
                    else:
                        # update TRADE TIME
                        logging.info(f"AUTOBUY {symbol} order {order_id} is placed")

                if ltp is not None:
                    self._update_low(symbol, float(ltp))
                else:
                    logging.error(f"Invalid ltp for {symbol}")
        except Exception as e:
            print_exc()
            print(f"{e} while is_breakout")
