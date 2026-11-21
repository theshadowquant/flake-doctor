"""Flake Doctor Web Console Verification Script.

Tests web server startup, HTML design tokens, security boundaries, async scan workflow, and API workflows.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def main() -> None:
    port = 8765
    host = "127.0.0.1"
    base_url = f"http://{host}:{port}"
    demo_path = Path("demo_sick_repo/test_patient_zero.py")
    orig_demo_code = demo_path.read_text(encoding="utf-8")
    bak_path = demo_path.with_name(demo_path.name + ".bak")

    # Start server in default mode (FD_ALLOW_CUSTOM_CODE not set / default "0")
    server_env = os.environ.copy()
    server_env["FD_ALLOW_CUSTOM_CODE"] = "0"
    cmd = [sys.executable, "-m", "flakedoctor.cli", "web", "--port", str(port)]

    print(f"Starting server: {' '.join(cmd)}", flush=True)
    server_proc = subprocess.Popen(
        cmd,
        env=server_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    all_passed = True

    try:
        # Wait for server to come online
        started = False
        t0 = time.time()
        while time.time() - t0 < 15.0:
            if is_port_open(host, port):
                started = True
                break
            time.sleep(0.3)

        if not started:
            print("FAIL: Server failed to start on 127.0.0.1 within timeout.", flush=True)
            sys.exit(1)

        print("Web server online on 127.0.0.1", flush=True)

        # Check 1: GET / returns 200, checks tokens
        try:
            with urllib.request.urlopen(f"{base_url}/") as resp:
                status = resp.status
                html = resp.read().decode("utf-8")
                assert status == 200, f"Expected 200, got {status}"
                assert "#F7DFD2" in html, "HTML missing #F7DFD2 canvas gradient token"
                assert "Instrument Serif" in html, "HTML missing Instrument Serif typography"
                assert "#0B1120" not in html, "Forbidden color #0B1120 found in HTML"
                assert "#0F172A" not in html, "Forbidden color #0F172A found in HTML"
                print("PASS: GET / returned 200 and matches editorial design constraints", flush=True)
        except Exception as e:
            print(f"FAIL [GET /]: {e}", flush=True)
            all_passed = False

        # Check 2: GET /api/files returns valid JSON
        try:
            with urllib.request.urlopen(f"{base_url}/api/files") as resp:
                status = resp.status
                data = json.loads(resp.read().decode("utf-8"))
                assert status == 200, f"Expected 200, got {status}"
                assert "files" in data and isinstance(data["files"], list), "Invalid files list"
                assert len(data["files"]) >= 1, "Expected test files in repository"
                print(f"PASS: GET /api/files returned 200 with {len(data['files'])} files", flush=True)
        except Exception as e:
            print(f"FAIL [GET /api/files]: {e}", flush=True)
            all_passed = False

        # Check 3: Path traversal rejection (security check)
        try:
            bad_payload = json.dumps({"file_path": "../evil.py"}).encode("utf-8")
            req = urllib.request.Request(
                f"{base_url}/api/scan",
                data=bad_payload,
                headers={"Content-Type": "application/json"},
            )
            rejected = False
            try:
                urllib.request.urlopen(req)
            except urllib.error.HTTPError as he:
                if he.code == 400:
                    rejected = True
            assert rejected, "Server did not reject path traversal with 400"
            print("PASS: Traversal path with '..' rejected with HTTP 400", flush=True)
        except Exception as e:
            print(f"FAIL [Security traversal rejection]: {e}", flush=True)
            all_passed = False

        # Check 4: Custom code disabled by default -> HTTP 403
        try:
            custom_payload = json.dumps({"custom_code": "def test_foo(): assert True"}).encode("utf-8")
            req = urllib.request.Request(
                f"{base_url}/api/scan",
                data=custom_payload,
                headers={"Content-Type": "application/json"},
            )
            rejected_403 = False
            try:
                urllib.request.urlopen(req)
            except urllib.error.HTTPError as he:
                if he.code == 403:
                    err_body = json.loads(he.read().decode("utf-8"))
                    if "custom code disabled" in err_body.get("error", ""):
                        rejected_403 = True
            assert rejected_403, "Server did not reject custom code with HTTP 403 when FD_ALLOW_CUSTOM_CODE=0"
            print("PASS: Custom code rejected with HTTP 403 when disabled by default", flush=True)
        except Exception as e:
            print(f"FAIL [Custom code disabled rejection]: {e}", flush=True)
            all_passed = False

        # Check 5: POST /api/scan on demo file (async or cached workflow)
        demo_file = "demo_sick_repo/test_patient_zero.py"
        try:
            print("Running POST /api/scan on demo file...", flush=True)
            scan_payload = json.dumps({"file_path": demo_file}).encode("utf-8")
            req = urllib.request.Request(
                f"{base_url}/api/scan",
                data=scan_payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                status = resp.status
                scan_data = json.loads(resp.read().decode("utf-8"))
                assert status in (200, 202), f"Expected 200 or 202, got {status}"

                # If async job started, poll until complete
                if scan_data.get("status") == "running" and "job_id" in scan_data:
                    job_id = scan_data["job_id"]
                    print(f"Polling async job {job_id}...", flush=True)
                    poll_t0 = time.time()
                    while time.time() - poll_t0 < 120:
                        time.sleep(1.0)
                        with urllib.request.urlopen(f"{base_url}/api/scan/{job_id}", timeout=10) as poll_resp:
                            poll_data = json.loads(poll_resp.read().decode("utf-8"))
                            if poll_data.get("status") == "done":
                                scan_data = poll_data
                                break
                            elif poll_data.get("status") == "error":
                                raise RuntimeError(f"Scan job failed: {poll_data.get('error')}")

                assert "results" in scan_data, f"Missing results key in scan response: {scan_data}"

                results_map = {r["name"]: r["verdict"] for r in scan_data["results"]}
                expected_verdicts = {
                    "test_01_setup_cache": "POLLUTER",
                    "test_02_order_dependent_consumer": "ORDER_DEPENDENT",
                    "test_03_unseeded_ml_threshold": "FLAKY_PRNG",
                    "test_04_async_race_condition": "FLAKY_TIMING",
                    "test_05_broken_build_control": "BROKEN_BUILD",
                }
                for tname, exp_verdict in expected_verdicts.items():
                    actual_v = results_map.get(tname)
                    assert actual_v == exp_verdict, f"{tname}: expected {exp_verdict}, got {actual_v}"

                print("PASS: POST /api/scan returned valid results with all 5 expected verdicts", flush=True)
        except Exception as e:
            print(f"FAIL [POST /api/scan]: {e}", flush=True)
            all_passed = False

        # Check 6: POST /api/fix returns 200 with diff, tests 01-04 STABLE, verified_file and patched_sha256
        try:
            print("Running POST /api/fix on demo file...", flush=True)
            fix_payload = json.dumps({"file_path": demo_file, "action": "apply"}).encode("utf-8")
            req = urllib.request.Request(
                f"{base_url}/api/fix",
                data=fix_payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                status = resp.status
                fix_data = json.loads(resp.read().decode("utf-8"))
                assert status == 200, f"Expected 200, got {status}"
                assert fix_data.get("diff"), "Missing diff in fix response"
                assert "after" in fix_data, "Missing after list in fix response"
                assert "verified_file" in fix_data, "Missing verified_file in fix response"
                assert "patched_sha256" in fix_data, "Missing patched_sha256 in fix response"

                after_map = {r["name"]: r["verdict"] for r in fix_data["after"]}
                assert after_map.get("test_01_setup_cache") == "STABLE", f"test_01 is {after_map.get('test_01_setup_cache')}"
                assert after_map.get("test_02_order_dependent_consumer") == "STABLE", f"test_02 is {after_map.get('test_02_order_dependent_consumer')}"
                assert after_map.get("test_03_unseeded_ml_threshold") == "STABLE", f"test_03 is {after_map.get('test_03_unseeded_ml_threshold')}"
                assert after_map.get("test_04_async_race_condition") == "STABLE", f"test_04 is {after_map.get('test_04_async_race_condition')}"
                assert after_map.get("test_05_broken_build_control") == "BROKEN_BUILD", f"test_05 is {after_map.get('test_05_broken_build_control')}"
                print("PASS: POST /api/fix returned 200 with valid diff, verified_file, and tests 01-04 healed to STABLE", flush=True)

            # Restore original demo file so repo remains clean
            restore_payload = json.dumps({"file_path": demo_file, "action": "restore"}).encode("utf-8")
            req_restore = urllib.request.Request(
                f"{base_url}/api/fix",
                data=restore_payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req_restore, timeout=30) as resp:
                assert resp.status == 200
                print("PASS: Restored original test file successfully", flush=True)
        except Exception as e:
            print(f"FAIL [POST /api/fix]: {e}", flush=True)
            all_passed = False

    finally:
        print("Stopping web server...", flush=True)
        server_proc.terminate()
        try:
            server_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server_proc.kill()
        print("Web server stopped.", flush=True)

        demo_path.write_text(orig_demo_code, encoding="utf-8")
        if bak_path.exists():
            bak_path.unlink(missing_ok=True)

    # Check 7: Test with FD_ALLOW_CUSTOM_CODE=1
    print("\nTesting server with FD_ALLOW_CUSTOM_CODE=1...", flush=True)
    custom_port = 8766
    custom_base_url = f"http://{host}:{custom_port}"
    custom_env = os.environ.copy()
    custom_env["FD_ALLOW_CUSTOM_CODE"] = "1"
    custom_server_cmd = [sys.executable, "-m", "flakedoctor.cli", "web", "--port", str(custom_port)]
    custom_proc = subprocess.Popen(
        custom_server_cmd,
        env=custom_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        started = False
        t0 = time.time()
        while time.time() - t0 < 15.0:
            if is_port_open(host, custom_port):
                started = True
                break
            time.sleep(0.3)

        assert started, "Server with FD_ALLOW_CUSTOM_CODE=1 failed to start"

        # Check payload > 20KB rejected with 413
        large_code = "def test_big():\n    pass\n" + ("# filler\n" * 3000)
        large_payload = json.dumps({"custom_code": large_code}).encode("utf-8")
        req_large = urllib.request.Request(
            f"{custom_base_url}/api/scan",
            data=large_payload,
            headers={"Content-Type": "application/json"},
        )
        rejected_413 = False
        try:
            urllib.request.urlopen(req_large)
        except urllib.error.HTTPError as he:
            if he.code == 413:
                rejected_413 = True
        assert rejected_413, "Server did not reject body > 20KB with HTTP 413"
        print("PASS: Request with body > 20KB rejected with HTTP 413", flush=True)

        # Check valid custom code accepted (returns 200 or 202)
        valid_code = "def test_clean():\n    assert 1 == 1\n"
        valid_payload = json.dumps({"custom_code": valid_code}).encode("utf-8")
        req_valid = urllib.request.Request(
            f"{custom_base_url}/api/scan",
            data=valid_payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req_valid, timeout=30) as resp:
            assert resp.status in (200, 202), f"Expected 200/202 for valid custom code, got {resp.status}"
        print("PASS: Valid custom code accepted from localhost with HTTP 200/202", flush=True)
    except Exception as e:
        print(f"FAIL [FD_ALLOW_CUSTOM_CODE=1 tests]: {e}", flush=True)
        all_passed = False
    finally:
        custom_proc.terminate()
        try:
            custom_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            custom_proc.kill()

    if all_passed:
        print("\nAll verify_web checks PASSED.", flush=True)
        sys.exit(0)
    else:
        print("\nSome verify_web checks FAILED.", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
