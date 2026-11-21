"""API Rate Limiter & Token Bucket Test Suite."""
import threading
import time


def test_token_bucket_refill_race():
    refilled = threading.Event()

    def refill_worker():
        time.sleep(0.005)
        refilled.set()

    t = threading.Thread(target=refill_worker)
    t.start()
    time.sleep(0.035)
    assert refilled.is_set()
    t.join()


def test_rate_limit_header_parsing():
    headers = {"X-RateLimit-Remaining": "42"}
    assert int(headers["X-RateLimit-Remaining"]) == 42


def test_unreachable_exhaustion():
    remaining_quota = 0
    assert remaining_quota > 0
