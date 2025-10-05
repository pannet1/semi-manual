from pprint import pprint
from helper import Helper

completed_orders = ["24112101509333"]
ids = ["24112101507734"]


def read():
    new_orders = []
    orders_from_api = Helper.orders()
    if orders_from_api and any(orders_from_api):
        """convert list to dict with order id as key"""
        new_orders = [
            {"id": order["order_id"], "buy_order": order}
            for order in orders_from_api
            if order["side"] == "B"
            and order["status"] == "COMPLETE"
            and order["order_id"] not in ids
            and order["order_id"] not in completed_orders.copy()
        ]
    pprint(new_orders)
    return new_orders


def create_strategy(list_of_orders):
    try:
        if any(list_of_orders):
            order_item = list_of_orders[0]
            if any(order_item):
                b = order_item["buy_order"]
                print(b)
    except Exception as e:
        print(f"{e} while creating strategy")


if __name__ == "__main__":
    list_of_orders = read()
    create_strategy(list_of_orders)
