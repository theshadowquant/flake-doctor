"""Verify patch canary test: asserts canary test is detected as BROKEN_BUILD and original file is unchanged."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from flakedoctor.engine import diagnose
from flakedoctor.patcher import build_patch, verify_fix


def main() -> None:
    demo_path = Path("demo_sick_repo/test_patient_zero.py")
    if not demo_path.exists():
        print(f"FAIL: {demo_path} does not exist")
        sys.exit(1)

    # 1. Record original file SHA-256
    orig_bytes = demo_path.read_bytes()
    orig_sha256 = hashlib.sha256(orig_bytes).hexdigest()
    print(f"Original file recorded: {demo_path} (sha256: {orig_sha256[:12]}...)")

    # 2. Diagnose original file
    print("Diagnosing original test file...")
    before_reports = diagnose(demo_path)

    # 3. Build patch
    patched_source, diff = build_patch(demo_path, before_reports)

    # 4. Append canary test that always fails
    canary_test_code = "\n\ndef test_canary_always_fails():\n    assert False\n"
    patched_source_with_canary = patched_source + canary_test_code

    print("Verifying fix with canary test appended...")
    vres = verify_fix(demo_path, patched_source_with_canary, before_reports=before_reports)

    # 5. Check canary test verdict
    canary_report = next((r for r in vres.reports if r.name == "test_canary_always_fails"), None)
    if not canary_report:
        print("FAIL: test_canary_always_fails was not executed or reported")
        sys.exit(1)

    if canary_report.verdict != "BROKEN_BUILD":
        print(f"FAIL: test_canary_always_fails expected BROKEN_BUILD, got {canary_report.verdict}")
        sys.exit(1)

    print(f"PASS: test_canary_always_fails verified as {canary_report.verdict}")

    # 6. Verify verified_file and patched_sha256
    expected_patched_sha256 = hashlib.sha256(patched_source_with_canary.encode("utf-8")).hexdigest()
    if vres.patched_sha256 != expected_patched_sha256:
        print(f"FAIL: patched_sha256 mismatch: {vres.patched_sha256} != {expected_patched_sha256}")
        sys.exit(1)

    if not Path(vres.verified_file).exists():
        print(f"FAIL: verified_file on disk not found: {vres.verified_file}")
        sys.exit(1)

    print(f"PASS: verified_file confirmed on disk at {vres.verified_file}")

    # 7. Assert original file on disk is completely untouched
    current_bytes = demo_path.read_bytes()
    current_sha256 = hashlib.sha256(current_bytes).hexdigest()
    if current_sha256 != orig_sha256:
        print(f"FAIL: Original file was modified on disk! ({current_sha256} != {orig_sha256})")
        sys.exit(1)

    print("PASS: Original file sha256 unchanged on disk.")
    print("\nAll verify_patch_canary checks PASSED.")


if __name__ == "__main__":
    main()
