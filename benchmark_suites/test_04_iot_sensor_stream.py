"""IoT Sensor Telemetry Stream Test Suite."""
import random
import threading
import time


def test_sensor_telemetry_stream():
    packet_received = threading.Event()

    def stream_producer():
        time.sleep(0.005)
        packet_received.set()

    worker = threading.Thread(target=stream_producer)
    worker.start()
    time.sleep(0.035)
    assert packet_received.is_set()
    worker.join()


def test_sensor_noise_distribution():
    readings = [random.random() for _ in range(10)]
    assert sum(readings) / len(readings) > 0.42


def test_celsius_to_fahrenheit():
    celsius = 25.0
    fahrenheit = (celsius * 9 / 5) + 32
    assert fahrenheit == 77.0
