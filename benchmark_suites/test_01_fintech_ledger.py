"""Fintech Ledger Test Suite - Simulates account debit/credit and risk Monte Carlo."""
import random

LEDGER_STATE = {}


def test_credit_account():
    LEDGER_STATE["account_101"] = 5000.0


def test_verify_balance():
    assert LEDGER_STATE.get("account_101") == 5000.0


def test_monte_carlo_var():
    sims = [random.random() for _ in range(10)]
    assert sum(sims) / len(sims) > 0.42


def test_fee_calculation():
    amount = 1000.0
    fee_rate = 0.025
    assert amount * fee_rate == 25.0
