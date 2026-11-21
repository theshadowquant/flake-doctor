"""Demo sick repo tests that exhibit various flakiness patterns."""
import os
import random
import threading
import time

SHARED_CACHE = {}

SEEDS = [0, 1, 7, 42, 99, 1337, 2026, 9999]
PASS_SEED = 0


def test_01_setup_cache():
    SHARED_CACHE["initialized"] = True
    os.environ["FLAKY_MODE"] = "ACTIVE"


def test_02_order_dependent_consumer():
    assert SHARED_CACHE.get("initialized") is True


def test_03_unseeded_ml_threshold():
    values = [random.random() for _ in range(10)]
    assert sum(values) / len(values) > 0.42


def test_04_async_race_condition():
    done = threading.Event()

    def worker():
        time.sleep(0.005)
        done.set()

    t = threading.Thread(target=worker)
    t.start()
    time.sleep(0.035)
    assert done.is_set()
    t.join()


def test_05_broken_build_control():
    assert 2 + 2 == 5
