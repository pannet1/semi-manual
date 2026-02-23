from datetime import time
import pendulum as pdlm
from constants import O_FUTL, logging
from traceback import print_exc
from toolkit.kokoo import timer
import os


class Jsondb:
    now = pdlm.now("Asia/Kolkata")
    format_string = "HH:mm:ss DD-MM-YYYY"

    @classmethod
    def startup(cls, db_file):
        try:
            if O_FUTL.is_file_not_2day(db_file):
                # return empty list if file is not modified today
                print(f"{db_file} file not modified today")

            O_FUTL.write_file(filepath=db_file, content=[])
            cls.F_ORDERS = db_file
        except Exception as e:
            logging.error(f"{e} while startup")
            print_exc()

    @classmethod
    def write(cls, write_job):
        temp_file = cls.F_ORDERS + ".tmp"  # Marker file for the writer

        # Write to strategies.json only if marker file does not exist
        with open(temp_file, "w"):  # Create marker file (can be empty)
            pass  # This ensures the marker is created

        try:
            O_FUTL.write_file(cls.F_ORDERS, write_job)
        finally:
            # Remove the marker file after the write is completed
            os.remove(temp_file)

    @classmethod
    def read(cls):
        temp_file = cls.F_ORDERS + ".tmp"  # Marker file for synchronization

        # Wait until the marker file is deleted (indicating writer is done)
        while os.path.exists(temp_file):
            timer(0.1)  # Wait for a short interval before checking again
        else:
            return O_FUTL.json_fm_file(cls.F_ORDERS)

    @classmethod
    def filter_trades(cls, trades_from_api, completed_trades):
        try:
            new = []
            ids = []
            order_from_file = cls.read()
            if order_from_file and any(order_from_file):
                ids = [order["_id"] for order in order_from_file]
            if trades_from_api and any(trades_from_api):
                """convert list to dict with order id as key"""
                new = [
                    {"id": order["order_id"], "buy_order": order}
                    for order in trades_from_api
                    if order["side"] == "B"
                    and order["order_id"] not in ids
                    and order["order_id"] not in completed_trades
                    and order.get("tag", None) is None
                    and (
                        pdlm.from_format(
                            order["broker_timestamp"],
                            cls.format_string,
                            tz="Asia/Kolkata",
                        )
                        > cls.now
                    )
                ]
                for item in new:
                    logging.debug(f'new: {item["buy_order"]}')

        except Exception as e:
            logging.error(f"{e} while get one order")
            print_exc()
        finally:
            return new


if __name__ == "__main__":
    now = pdlm.now("Asia/Kolkata")

    o_time = pdlm.from_format(
        "09:31:00 06-10-2025", Jsondb.format_string, tz="Asia/Kolkata"
    )
    assert (
        now > o_time
    ), "time is wrong"  # Assert that the current time is greater than the time of the order
