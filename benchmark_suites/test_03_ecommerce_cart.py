"""E-Commerce Cart and Checkout Test Suite."""
import os
import threading
import time

ACTIVE_SESSION = {}


def test_init_cart_session():
    ACTIVE_SESSION["cart_id"] = "cart_999"
    os.environ["CART_TOKEN"] = "tok_live_xyz"


def test_checkout_requires_session():
    assert ACTIVE_SESSION.get("cart_id") == "cart_999"


def test_async_inventory_reserve():
    reserved = threading.Event()

    def reserve_worker():
        time.sleep(0.005)
        reserved.set()

    th = threading.Thread(target=reserve_worker)
    th.start()
    time.sleep(0.035)
    assert reserved.is_set()
    th.join()


def test_discount_tier():
    cart_total = 200.0
    discount = 0.15
    assert cart_total - (cart_total * discount) == 170.0
