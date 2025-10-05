from traceback import print_exc
import re
from stock_brokers.finvasia.finvasia import Finvasia
from stock_brokers.finvasia.api_helper import (
    make_order_modify_args,
    make_order_place_args,
    post_order_hook,
)
from toolkit.datastruct import filter_dictionary_by_keys
from constants import O_CNFG, logging, O_SETG
import pendulum as pdlm
from toolkit.kokoo import blink, timer
from wserver import Wserver


def find_underlying(symbol):
    try:
        for underlying, low in O_SETG["MCX"].items():
            # starts with any alpha
            pattern = re.compile(r"[A-Za-z]+")
            symbol_begin = pattern.match(symbol).group()
            underlying_begin = pattern.match(underlying).group()
            # If the symbol begins with the alpha of underlying
            if symbol_begin.startswith(underlying_begin):
                return underlying, low
        return None  # Return None if no match is found
    except Exception as e:
        print(f"{e} while find underlying regex")
        print_exc()
        return None


def find_mcx_exit_condition(symbol):
    try:
        condition = "self._ltp < self._low"
        call_or_put = re.search(r"(P|C)(?=\d+$)", symbol).group(1)
        if call_or_put == "P":
            condition = "self._ltp > self._low"
    except Exception as e:
        print(f"{e} while find mcx exit condtion")
        print_exc()
    finally:
        return condition


def send_messages(msg):
    print(msg)


def login():
    api = Finvasia(**O_CNFG)
    if api.authenticate():
        message = "api connected"
        send_messages(message)
        return api
    else:
        send_messages("Failed to authenticate. .. exiting")
        __import__("sys").exit(1)


# add a decorator to check if wait_till is past
def is_not_rate_limited(func):
    # Decorator to enforce a 1-second delay between calls
    def wrapper(*args, **kwargs):
        now = pdlm.now()
        if now < Helper.wait_till:
            blink()
        Helper.wait_till = now.add(seconds=1)
        return func(*args, **kwargs)

    return wrapper


class Helper:
    _api = None
    subscribed = {}
    completed_trades = []

    @classmethod
    @property
    def api(cls):
        if cls._api is None:
            cls._api = login()
            cls.ws = Wserver(cls._api, ["NSE:24"])
        cls.wait_till = pdlm.now().add(seconds=1)
        return cls._api

    @classmethod
    def _subscribe_till_ltp(cls, ws_key):
        try:
            quotes = cls.ws.ltp
            ltp = quotes.get(ws_key, None)
            while ltp is None:
                cls.ws.api.subscribe([ws_key], feed_type="d")
                quotes = cls.ws.ltp
                ltp = quotes.get(ws_key, None)
                timer(0.25)
        except Exception as e:
            logging.error(f"{e} while get ltp")
            print_exc()
            cls._subscribe_till_ltp(ws_key)

    @classmethod
    def symbol_info(cls, exchange, symbol):
        try:
            low = False
            if exchange == "MCX":
                resp = find_underlying(symbol)
                if resp:
                    symbol, low = resp
            if cls.subscribed.get(symbol, None) is None:
                token = cls.api.instrument_symbol(exchange, symbol)
                now = pdlm.now()
                fm = now.replace(hour=9, minute=0, second=0, microsecond=0).timestamp()
                to = now.replace(hour=9, minute=17, second=0, microsecond=0).timestamp()
                key = exchange + "|" + str(token)
                if not low:
                    resp = cls.api.historical(exchange, token, fm, to)
                    low = resp[-2]["intl"]
                cls.subscribed[symbol] = {
                    "symbol": symbol,
                    "key": key,
                    # "low": 0,
                    "low": low,
                    "ltp": cls._subscribe_till_ltp(key),
                }
            if cls.subscribed.get(symbol, None) is not None:
                quotes = cls.ws.ltp
                ws_key = cls.subscribed[symbol]["key"]
                cls.subscribed[symbol]["ltp"] = quotes[ws_key]
                return cls.subscribed[symbol]
        except Exception as e:
            logging.error(f"{e} while symbol info")
            print_exc()

    @classmethod
    def get_quotes(cls):
        try:
            quote = {}
            ltps = cls.ws.ltp
            quote = {
                symbol: ltps.get(values["key"])
                for symbol, values in cls.subscribed.items()
            }
        except Exception as e:
            logging.error(f"{e} while getting quote")
            print_exc()
        finally:
            return quote

    @classmethod
    def ltp(cls, exchange, token):
        try:
            resp = cls.api.scriptinfo(exchange, token)
            if resp is not None:
                return float(resp["lp"])
            else:
                raise ValueError("ltp is none")
        except Exception as e:
            message = f"{e} while ltp"
            send_messages(message)
            print_exc()

    @classmethod
    def one_side(cls, bargs):
        try:
            bargs = make_order_place_args(**bargs)
            resp = cls.api.order_place(**bargs)
            return resp
        except Exception as e:
            message = f"helper error {e} while placing order"
            send_messages(message)
            print_exc()

    @classmethod
    def modify_order(cls, args):
        try:
            args = make_order_modify_args(**args)
            resp = cls.api.order_modify(**args)
            return resp
        except Exception as e:
            message = f"helper error {e} while modifying order"
            send_messages(message)
            print_exc()

    @classmethod
    def orders(cls):
        try:
            orders = cls.api.orders
            if any(orders):
                # print(orders[0].keys())
                return post_order_hook(*orders)
            return [{}]

        except Exception as e:
            send_messages(f"Error fetching orders: {e}")
            print_exc()

    @classmethod
    @is_not_rate_limited
    def trades(cls):
        try:
            from_api = []  # Return an empty list on failure
            keys = [
                "exchange",
                "symbol",
                "order_id",
                "quantity",
                "side",
                "product",
                "price_type",
                "fill_shares",
                "average_price",
                "exchange_order_id",
                "tag",
                "validity",
                "price_precison",
                "tick_size",
                "fill_timestamp",
                "fill_quantity",
                "fill_price",
                "source",
                "broker_timestamp",
            ]
            from_api = cls.api.trades
            if from_api:
                # Apply filter to each order item
                from_api = [filter_dictionary_by_keys(item, keys) for item in from_api]

        except Exception as e:
            send_messages(f"Error fetching trades: {e}")
            print_exc()
        finally:
            return from_api

    @classmethod
    def close_positions(cls):
        for pos in cls.api.positions:
            if pos["quantity"] == 0:
                continue
            else:
                quantity = abs(pos["quantity"])

            send_messages(f"trying to close {pos['symbol']}")
            if pos["quantity"] < 0:
                args = dict(
                    symbol=pos["symbol"],
                    quantity=quantity,
                    disclosed_quantity=quantity,
                    product="M",
                    side="B",
                    order_type="MKT",
                    exchange="NFO",
                    tag="close",
                )
                resp = cls.api.order_place(**args)
                send_messages(f"api responded with {resp}")
            elif quantity > 0:
                args = dict(
                    symbol=pos["symbol"],
                    quantity=quantity,
                    disclosed_quantity=quantity,
                    product="M",
                    side="S",
                    order_type="MKT",
                    exchange="NFO",
                    tag="close",
                )
                resp = cls.api.order_place(**args)
                send_messages(f"api responded with {resp}")

    @classmethod
    def pnl(cls, key="urmtom"):
        try:
            ttl = 0
            resp = [{}]
            resp = cls.api.positions
            """
            keys = [
                "symbol",
                "quantity",
                "last_price",
                "urmtom",
                "rpnl",
            ]
            """
            if any(resp):
                pd.DataFrame(resp).to_csv(S_DATA + "positions.csv", index=False)
                # calc value
                for pos in resp:
                    ttl += pos[key]
        except Exception as e:
            message = f"while calculating {e}"
            send_messages(f"api responded with {message}")
            print_exc()
        finally:
            return ttl


if __name__ == "__main__":
    from pprint import pprint
    import pandas as pd
    from constants import S_DATA

    Helper.api

    def trades():
        resp = Helper.trades()
        pd.DataFrame(resp).to_csv(S_DATA + "trades.csv", index=False)

    def orders():
        resp = Helper.orders()
        if any(resp):
            pd.DataFrame(resp).to_csv(S_DATA + "orders.csv", index=False)

    def history(exchange, symbol):
        token = Helper.api.instrument_symbol(exchange, symbol)
        fm = pdlm.now().replace(hour=9, minute=0, second=0, microsecond=0).timestamp()
        to = pdlm.now().replace(hour=9, minute=17, second=0, microsecond=0).timestamp()
        resp = Helper.api.historical(exchange, token, fm, to)
        pprint(resp)
        print(resp[-2]["intl"])

    def modify():
        args = {
            "symbol": "NIFTY28NOV24C23400",
            "exchange": "NFO",
            "order_id": "24112200115699",
            "price": 0.0,
            "price_type": "MARKET",
            "quantity": 25,
        }
        resp = Helper.modify_order(args)
        print(resp)

    def margin():
        resp = Helper.api.margins
        print(resp)

    orders()
    margin()
    resp = Helper.pnl("rpnl")
    print(resp)
