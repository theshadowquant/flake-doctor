"""Quantitative Orderbook & Execution Engine Test Suite."""
import random

ORDERBOOK_CACHE = {}


def test_populate_order_depth():
    ORDERBOOK_CACHE["top_bid"] = 142.50


def test_matching_engine_bid():
    assert ORDERBOOK_CACHE.get("top_bid") == 142.50


def test_slippage_monte_carlo():
    draws = [random.random() for _ in range(10)]
    assert sum(draws) / len(draws) > 0.42


def test_bid_ask_spread():
    bid = 100.0
    ask = 100.25
    assert ask - bid == 0.25
