"""Vercel Serverless Function entry point for Flake Doctor."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from flakedoctor.engine import diagnose
from flakedoctor.patcher import build_patch
from flakedoctor.web import (
    HTML_PAGE_TEMPLATE,
    FlakeDoctorHandler,
    _get_all_test_files,
    _is_safe_test_path,
)

# Vercel BaseHTTPRequestHandler entrypoint
class handler(FlakeDoctorHandler):
    pass


# WSGI callable entrypoint (universal fallback for any Python serverless runtime)
def app(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "/") or "/"

    if method == "GET":
        if path in ("/", "/index.html"):
            html = HTML_PAGE_TEMPLATE.replace(
                "__PAGE_TITLE__", "Flake Doctor | Forensic Test Diagnostics"
            ).encode("utf-8")
            start_response("200 OK", [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(html))),
            ])
            return [html]
        elif path == "/api/files":
            files = _get_all_test_files()
            data = json.dumps({"files": files}).encode("utf-8")
            start_response("200 OK", [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(data))),
                ("Access-Control-Allow-Origin", "*"),
            ])
            return [data]

    elif method == "POST":
        content_length = int(environ.get("CONTENT_LENGTH", 0) or 0)
        body_bytes = environ["wsgi.input"].read(content_length) if content_length > 0 else b"{}"
        try:
            req_data = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            err = json.dumps({"error": "Invalid JSON"}).encode("utf-8")
            start_response("400 Bad Request", [("Content-Type", "application/json")])
            return [err]

        if path == "/api/scan":
            custom_code = req_data.get("custom_code")
            file_path_str = req_data.get("file_path")
            if custom_code is not None:
                try:
                    target_file = Path("benchmark_suites") / "_judge_custom_live.py"
                    target_file.parent.mkdir(exist_ok=True)
                    target_file.write_text(custom_code, encoding="utf-8")
                except OSError:
                    target_file = Path(tempfile.gettempdir()) / "_judge_custom_live.py"
                    target_file.write_text(custom_code, encoding="utf-8")
            elif file_path_str:
                if not _is_safe_test_path(file_path_str):
                    err = json.dumps({"error": "Path traversal or forbidden path"}).encode("utf-8")
                    start_response("400 Bad Request", [("Content-Type", "application/json")])
                    return [err]
                target_file = Path(file_path_str)
            else:
                err = json.dumps({"error": "Missing file_path or custom_code"}).encode("utf-8")
                start_response("400 Bad Request", [("Content-Type", "application/json")])
                return [err]

            if not target_file.exists():
                err = json.dumps({"error": f"File not found: {target_file}"}).encode("utf-8")
                start_response("404 Not Found", [("Content-Type", "application/json")])
                return [err]

            t0 = time.monotonic()
            try:
                reports = diagnose(target_file)
                _, diff = build_patch(target_file, reports)
                elapsed = time.monotonic() - t0
                sub_count = getattr(reports[0], "_subprocess_count", 0) if reports else 0
                resp = json.dumps({
                    "results": [r.to_dict() for r in reports],
                    "diff": diff,
                    "file_path": target_file.as_posix(),
                    "scan_time": elapsed,
                    "subprocess_count": sub_count,
                }).encode("utf-8")
                start_response("200 OK", [
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(resp))),
                    ("Access-Control-Allow-Origin", "*"),
                ])
                return [resp]
            except Exception as e:
                err = json.dumps({"error": str(e)}).encode("utf-8")
                start_response("500 Internal Server Error", [("Content-Type", "application/json")])
                return [err]

        elif path == "/api/fix":
            file_path_str = req_data.get("file_path")
            action = req_data.get("action", "apply")
            if not file_path_str:
                err = json.dumps({"error": "Missing file_path"}).encode("utf-8")
                start_response("400 Bad Request", [("Content-Type", "application/json")])
                return [err]
            if not _is_safe_test_path(file_path_str):
                err = json.dumps({"error": "Path traversal or forbidden path"}).encode("utf-8")
                start_response("400 Bad Request", [("Content-Type", "application/json")])
                return [err]

            target_file = Path(file_path_str)
            bak_file = target_file.with_name(target_file.name + ".bak")

            if action == "restore":
                if bak_file.exists():
                    try:
                        shutil.copy2(bak_file, target_file)
                        bak_file.unlink(missing_ok=True)
                    except OSError:
                        pass
                resp = json.dumps({"status": "restored"}).encode("utf-8")
                start_response("200 OK", [("Content-Type", "application/json")])
                return [resp]

            if action == "apply":
                if not target_file.exists():
                    err = json.dumps({"error": f"File not found: {target_file}"}).encode("utf-8")
                    start_response("404 Not Found", [("Content-Type", "application/json")])
                    return [err]

                try:
                    before_reports = diagnose(target_file)
                    patched_src, diff = build_patch(target_file, before_reports)

                    # Backup and write patch; gracefully fall back to /tmp if read-only
                    try:
                        if not bak_file.exists():
                            shutil.copy2(target_file, bak_file)
                        target_file.write_text(patched_src, encoding="utf-8")
                        eval_file = target_file
                    except OSError:
                        eval_file = Path(tempfile.gettempdir()) / target_file.name
                        eval_file.write_text(patched_src, encoding="utf-8")

                    after_reports = diagnose(eval_file)
                    after_map = {r.name: r for r in after_reports}
                    healed = 0
                    for b in before_reports:
                        aft = after_map.get(b.name)
                        if aft and b.verdict != aft.verdict and aft.verdict == "STABLE":
                            healed += 1

                    remaining_bugs = sum(1 for r in after_reports if r.verdict == "BROKEN_BUILD")
                    resp = json.dumps({
                        "status": "applied",
                        "before": [r.to_dict() for r in before_reports],
                        "after": [r.to_dict() for r in after_reports],
                        "diff": diff,
                        "healed": healed,
                        "remaining_bugs": remaining_bugs,
                    }).encode("utf-8")
                    start_response("200 OK", [
                        ("Content-Type", "application/json"),
                        ("Content-Length", str(len(resp))),
                        ("Access-Control-Allow-Origin", "*"),
                    ])
                    return [resp]
                except Exception as e:
                    err = json.dumps({"error": str(e)}).encode("utf-8")
                    start_response("500 Internal Server Error", [("Content-Type", "application/json")])
                    return [err]

    start_response("404 Not Found", [("Content-Type", "text/plain")])
    return [b"Not Found"]
