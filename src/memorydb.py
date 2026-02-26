import pendulum as pdlm
from traceback import print_exc
from constants import logging

class Memorydb:
    now = pdlm.now("Asia/Kolkata")
    format_string = "HH:mm:ss DD-MM-YYYY"

    @classmethod
    def filter_trades(cls, trades_from_api, completed_trades, active_ids):
        try:
            new = []
            if trades_from_api and any(trades_from_api):
                new = [
                    {"id": trade["order_id"], "buy_order": trade}
                    for trade in trades_from_api
                    if trade["side"] == "B"
                    and trade["order_id"] not in active_ids
                    and trade["order_id"] not in completed_trades
                    and trade.get("tag", None) is None
                    and (
                        pdlm.from_format(
                            trade["broker_timestamp"],
                            cls.format_string,
                            tz="Asia/Kolkata",
                        )
                        > cls.now
                    )
                ]
                for item in new:
                    logging.debug(f"new: {item['buy_order']}")
        except Exception as e:
            logging.error(f"{e} while filter_trades")
            print_exc()
        finally:
            return new
