"""AST-guided auto-patcher and fix verification for Flake Doctor."""
from __future__ import annotations

import ast
import difflib
import re
import shutil
import tempfile
from pathlib import Path
from typing import List, Tuple

from .engine import TestReport, diagnose


def _find_function_node(tree: ast.Module, func_name: str) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == func_name:
                return node
    return None


def _extract_culprit_monkeypatch_lines(source_lines: list[str], culprit_node: ast.FunctionDef) -> list[str]:
    """Extract and convert state-setting lines from culprit into monkeypatch statements."""
    lines_to_add: list[str] = []
    for stmt in culprit_node.body:
        if isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                if isinstance(t, ast.Subscript):
                    # os.environ["K"] = v
                    val_str = ast.unparse(stmt.value)
                    if isinstance(t.value, ast.Attribute) and ast.unparse(t.value) == "os.environ":
                        key_str = ast.unparse(t.slice)
                        lines_to_add.append(f'monkeypatch.setenv({key_str}, {val_str})')
                    elif isinstance(t.value, ast.Name):
                        container = t.value.id
                        key_str = ast.unparse(t.slice)
                        lines_to_add.append(f'monkeypatch.setitem({container}, {key_str}, {val_str})')
    return lines_to_add


def build_patch(test_file: Path, reports: List[TestReport]) -> Tuple[str, str]:
    """Build patched source code and unified diff.
    
    Returns (patched_source, unified_diff).
    """
    test_file = Path(test_file)
    original_source = test_file.read_text(encoding="utf-8")
    lines = original_source.splitlines(keepends=True)
    tree = ast.parse(original_source, filename=str(test_file))

    report_map = {r.name: r for r in reports}

    # Locate all test functions with their start/end lines
    test_funcs: list[Tuple[int, int, str, ast.FunctionDef]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            test_funcs.append((node.lineno, getattr(node, "end_lineno", node.lineno), node.name, node))

    # Sort test functions from BOTTOM to TOP so modifying lower lines doesn't invalidate line numbers
    test_funcs.sort(key=lambda x: x[0], reverse=True)

    for start_line, end_line, name, func_node in test_funcs:
        rep = report_map.get(name)
        if not rep:
            continue

        verdict = rep.verdict

        if verdict == "BROKEN_BUILD":
            # Add comment line above the test: # flakedoctor: genuine failure, fix the code under test, not the test
            def_idx = start_line - 1
            indent = " " * (len(lines[def_idx]) - len(lines[def_idx].lstrip()))
            comment = f"{indent}# flakedoctor: genuine failure, fix the code under test, not the test\n"
            lines.insert(def_idx, comment)

        elif verdict == "POLLUTER":
            # Rewrite test_01 def signature to include monkeypatch
            # and rewrite body writes to monkeypatch.setitem / monkeypatch.setenv
            func_lines = lines[start_line - 1 : end_line]
            def_line = func_lines[0]
            if "monkeypatch" not in def_line:
                new_def = re.sub(r"\((.*?)\)", lambda m: f"({m.group(1)}, monkeypatch)" if m.group(1).strip() else "(monkeypatch)", def_line)
                func_lines[0] = new_def

            new_func_lines = []
            for line in func_lines:
                # Check for os.environ["..."] = ...
                m_env = re.search(r'os\.environ\[(.*?)\]\s*=\s*(.*)', line)
                m_item = re.search(r'([A-Z0-9_]+)\[(.*?)\]\s*=\s*(.*)', line)
                indent = " " * (len(line) - len(line.lstrip()))
                if m_env:
                    k, v = m_env.group(1).strip(), m_env.group(2).strip()
                    new_func_lines.append(f"{indent}monkeypatch.setenv({k}, {v})\n")
                elif m_item and not line.strip().startswith("os.environ"):
                    container, k, v = m_item.group(1).strip(), m_item.group(2).strip(), m_item.group(3).strip()
                    new_func_lines.append(f"{indent}monkeypatch.setitem({container}, {k}, {v})\n")
                else:
                    new_func_lines.append(line)

            lines[start_line - 1 : end_line] = new_func_lines

        elif verdict == "ORDER_DEPENDENT":
            # Add monkeypatch as parameter of the consumer
            # Insert culprit's state-setting statements at top of consumer's body
            culprit_name = rep.culprit
            culprit_lines_to_add: list[str] = []
            if culprit_name:
                c_node = _find_function_node(tree, culprit_name)
                if c_node:
                    culprit_lines_to_add = _extract_culprit_monkeypatch_lines(lines, c_node)

            func_lines = lines[start_line - 1 : end_line]
            def_line = func_lines[0]
            if "monkeypatch" not in def_line:
                new_def = re.sub(r"\((.*?)\)", lambda m: f"({m.group(1)}, monkeypatch)" if m.group(1).strip() else "(monkeypatch)", def_line)
                func_lines[0] = new_def

            # Find body indentation from first non-def line
            indent = "    "
            for l in func_lines[1:]:
                if l.strip():
                    indent = " " * (len(l) - len(l.lstrip()))
                    break

            # Insert culprit setup statements at top of body
            insertions = [f"{indent}{stmt}\n" for stmt in culprit_lines_to_add]
            new_func_lines = [func_lines[0]] + insertions + func_lines[1:]
            lines[start_line - 1 : end_line] = new_func_lines

        elif verdict == "FLAKY_PRNG":
            # Insert random.seed(42) as first body line
            # If literal range(10) in sampling comprehension, change to range(1000)
            # Add # flakedoctor: seeded and enlarged sample as trailing comment
            func_lines = lines[start_line - 1 : end_line]
            indent = "    "
            for l in func_lines[1:]:
                if l.strip():
                    indent = " " * (len(l) - len(l.lstrip()))
                    break

            new_func_lines = [func_lines[0], f"{indent}random.seed(42)\n"]
            for l in func_lines[1:]:
                if "range(10)" in l:
                    l_mod = l.replace("range(10)", "range(1000)")
                    l_mod = l_mod.rstrip() + "  # flakedoctor: seeded and enlarged sample\n"
                    new_func_lines.append(l_mod)
                else:
                    new_func_lines.append(l)

            lines[start_line - 1 : end_line] = new_func_lines

        elif verdict == "FLAKY_TIMING":
            # If function assigns X = threading.Event(), replace MAIN-thread time.sleep(...) line
            # (the one after .start()) with X.wait(timeout=2.0)
            # Else if assigns threading.Thread to T, replace with T.join(timeout=2.0)
            # Leave worker sleep untouched
            func_lines = lines[start_line - 1 : end_line]
            event_name = None
            thread_name = None
            for node_stmt in ast.walk(func_node):
                if isinstance(node_stmt, ast.Assign):
                    if isinstance(node_stmt.value, ast.Call):
                        fn_name = ast.unparse(node_stmt.value.func)
                        if "Event" in fn_name and node_stmt.targets:
                            event_name = ast.unparse(node_stmt.targets[0])
                        elif "Thread" in fn_name and node_stmt.targets:
                            thread_name = ast.unparse(node_stmt.targets[0])

            started = False
            new_func_lines = []
            for l in func_lines:
                if ".start()" in l:
                    started = True
                    new_func_lines.append(l)
                elif started and ("time.sleep(" in l or "sleep(" in l) and not l.strip().startswith("assert"):
                    indent = " " * (len(l) - len(l.lstrip()))
                    if event_name:
                        new_func_lines.append(f"{indent}{event_name}.wait(timeout=2.0)\n")
                    elif thread_name:
                        new_func_lines.append(f"{indent}{thread_name}.join(timeout=2.0)\n")
                    else:
                        new_func_lines.append(l)
                    started = False  # only replace the first sleep after start()
                else:
                    new_func_lines.append(l)

            lines[start_line - 1 : end_line] = new_func_lines

    patched_source = "".join(lines)
    diff = list(difflib.unified_diff(
        original_source.splitlines(keepends=True),
        patched_source.splitlines(keepends=True),
        fromfile=f"a/{test_file.name}",
        tofile=f"b/{test_file.name}",
    ))
    unified_diff = "".join(diff)
    return patched_source, unified_diff


def verify_fix(test_file: Path, patched_source: str) -> List[TestReport]:
    """Write patched source to temp dir as patched_<name>.py and diagnose."""
    tmpdir = Path(tempfile.mkdtemp(prefix="fd_verify_"))
    try:
        patched_path = tmpdir / f"patched_{test_file.name}"
        patched_path.write_text(patched_source, encoding="utf-8")
        reports = diagnose(patched_path)
        return reports
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
