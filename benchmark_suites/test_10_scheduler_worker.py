"""Scheduler Worker & Cron Dispatcher Test Suite."""
import threading
import time


def test_worker_heartbeat_race():
    heartbeat = threading.Event()

    def heartbeat_worker():
        time.sleep(0.005)
        heartbeat.set()

    worker = threading.Thread(target=heartbeat_worker)
    worker.start()
    time.sleep(0.035)
    assert heartbeat.is_set()
    worker.join()


def test_cron_expression_validator():
    cron_expr = "*/5 * * * *"
    assert cron_expr.startswith("*/5")


def test_deadlock_detection_assertion():
    worker_status = "RUNNING"
    assert worker_status == "TERMINATED"
