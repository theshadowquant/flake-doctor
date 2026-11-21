"""Verify the autopsy_report.json produced by Flake Doctor."""
import json
import sys
from pathlib import Path

EXPECTED = {
    "test_01_setup_cache": {
        "verdict": "POLLUTER",
    },
    "test_02_order_dependent_consumer": {
        "verdict": "ORDER_DEPENDENT",
        "culprit": "test_01_setup_cache",
    },
    "test_03_unseeded_ml_threshold": {
        "verdict": "FLAKY_PRNG",
    },
    "test_04_async_race_condition": {
        "verdict": "FLAKY_TIMING",
    },
    "test_05_broken_build_control": {
        "verdict": "BROKEN_BUILD",
    },
}

report_path = Path("autopsy_report.json")
if not report_path.exists():
    print("FAIL: autopsy_report.json not found")
    sys.exit(1)

data = json.loads(report_path.read_text(encoding="utf-8"))
reports = {r["name"]: r for r in data}

all_pass = True
for test_name, expectations in EXPECTED.items():
    if test_name not in reports:
        print(f"FAIL [{test_name}]: not found in report")
        all_pass = False
        continue
    r = reports[test_name]
    ok = True
    for key, expected_val in expectations.items():
        actual_val = r.get(key)
        if actual_val != expected_val:
            print(f"FAIL [{test_name}]: {key}={actual_val!r}, expected {expected_val!r}")
            ok = False
            all_pass = False
    if ok:
        print(f"PASS [{test_name}]: verdict={r['verdict']}" +
              (f", culprit={r['culprit']}" if r.get('culprit') else ""))

if all_pass:
    print("\nAll 5 checks PASSED.")
    sys.exit(0)
else:
    print("\nSome checks FAILED.")
    sys.exit(1)
