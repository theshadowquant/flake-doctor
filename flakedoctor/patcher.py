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


def _extract_culprit_monkeypatch_lines(culprit_node: ast.FunctionDef) -> Tuple[str, List[str]]:
    """Extract state-setting lines and determine fixture name with consistent double quotes."""
    lines_to_add: list[str] = []
    state_name = "cache"
    for stmt in culprit_node.body:
        if isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                if isinstance(t, ast.Subscript):
                    # Value formatting
                    if isinstance(stmt.value, ast.Constant):
                        val_str = f'"{stmt.value.value}"' if isinstance(stmt.value.value, str) else str(stmt.value.value)
                    else:
                        val_str = ast.unparse(stmt.value)

                    # Key formatting
                    if isinstance(t.slice, ast.Constant) and isinstance(t.slice.value, str):
                        key_str = f'"{t.slice.value}"'
                    else:
                        key_str = ast.unparse(t.slice)

                    if isinstance(t.value, ast.Attribute) and ast.unparse(t.value) == "os.environ":
                        lines_to_add.append(f'monkeypatch.setenv({key_str}, {val_str})')
                    elif isinstance(t.value, ast.Name):
                        container = t.value.id
                        clean = container.lower().replace("shared_", "")
                        if clean:
                            state_name = clean
                        lines_to_add.append(f'monkeypatch.setitem({container}, {key_str}, {val_str})')
    fixture_name = f"initialized_{state_name}"
    return fixture_name, lines_to_add


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

    fixtures_to_insert: list[str] = []
    need_pytest_import = False

    for start_line, end_line, name, func_node in test_funcs:
        rep = report_map.get(name)
        if not rep:
            continue

        verdict = rep.verdict

        if verdict == "BROKEN_BUILD":
            # Add comment line above the test
            def_idx = start_line - 1
            indent = " " * (len(lines[def_idx]) - len(lines[def_idx].lstrip()))
            comment = f"{indent}# flakedoctor: genuine failure, fix the code under test, not the test\n"
            lines.insert(def_idx, comment)

        elif verdict == "POLLUTER":
            # Rewrite def signature to include monkeypatch and use double quotes
            func_lines = lines[start_line - 1 : end_line]
            def_line = func_lines[0]
            if "monkeypatch" not in def_line:
                new_def = re.sub(
                    r"\((.*?)\)",
                    lambda m: f"({m.group(1)}, monkeypatch)" if m.group(1).strip() else "(monkeypatch)",
                    def_line,
                )
                func_lines[0] = new_def

            new_func_lines = []
            for line in func_lines:
                m_env = re.search(r'os\.environ\[["\'](.*?)["\']\]\s*=\s*["\']?(.*?)["\']?\s*$', line.strip())
                m_item = re.search(r'([A-Z0-9_]+)\[["\'](.*?)["\']\]\s*=\s*(.*)', line)
                indent = " " * (len(line) - len(line.lstrip()))
                if "os.environ[" in line:
                    m_env_match = re.search(r'os\.environ\[["\'](.*?)["\']\]\s*=\s*(.*)', line)
                    if m_env_match:
                        k = m_env_match.group(1).strip()
                        v = m_env_match.group(2).strip().strip("'\"")
                        new_func_lines.append(f'{indent}monkeypatch.setenv("{k}", "{v}")\n')
                    else:
                        new_func_lines.append(line)
                elif m_item and not line.strip().startswith("os.environ"):
                    container = m_item.group(1).strip()
                    k = m_item.group(2).strip()
                    v = m_item.group(3).strip()
                    new_func_lines.append(f'{indent}monkeypatch.setitem({container}, "{k}", {v})\n')
                else:
                    new_func_lines.append(line)

            lines[start_line - 1 : end_line] = new_func_lines

        elif verdict == "ORDER_DEPENDENT":
            # For ORDER_DEPENDENT, generate a module-level fixture and add comment above consumer
            culprit_name = rep.culprit
            fixture_name = "initialized_cache"
            culprit_lines_to_add: list[str] = []
            if culprit_name:
                c_node = _find_function_node(tree, culprit_name)
                if c_node:
                    fixture_name, culprit_lines_to_add = _extract_culprit_monkeypatch_lines(c_node)

            need_pytest_import = True
            fixture_body = "\n".join(f"    {stmt}" for stmt in culprit_lines_to_add)
            fixture_code = f"@pytest.fixture\ndef {fixture_name}(monkeypatch):\n{fixture_body}\n\n\n"
            if fixture_code not in fixtures_to_insert:
                fixtures_to_insert.append(fixture_code)

            func_lines = lines[start_line - 1 : end_line]
            def_line = func_lines[0]
            # Replace signature to accept fixture_name
            new_def = re.sub(
                r"\((.*?)\)",
                lambda m: f"({m.group(1)}, {fixture_name})" if m.group(1).strip() else f"({fixture_name})",
                def_line,
            )
            func_lines[0] = new_def

            # Comment above consumer
            def_idx = start_line - 1
            indent = " " * (len(lines[def_idx]) - len(lines[def_idx].lstrip()))
            comment = f"{indent}# flakedoctor: dependency on {culprit_name} made explicit via fixture\n"
            func_lines.insert(0, comment)

            lines[start_line - 1 : end_line] = func_lines

        elif verdict == "FLAKY_PRNG":
            # Insert random.seed(42) as first body line
            # If literal range(10) in sampling comprehension, change to range(1000)
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

    # Insert module-level fixtures above the first test
    if fixtures_to_insert:
        # Find line number of the first test
        min_test_line = min(t[0] for t in test_funcs)
        # Find where to place fixture (above first test)
        insert_idx = min_test_line - 1
        all_fixtures = "".join(reversed(fixtures_to_insert))
        lines.insert(insert_idx, all_fixtures)

    # Insert import pytest if needed and missing
    if need_pytest_import and not any("import pytest" in l for l in lines):
        # Insert after existing imports
        last_import_idx = 0
        for i, l in enumerate(lines):
            if l.startswith("import ") or l.startswith("from "):
                last_import_idx = i + 1
        lines.insert(last_import_idx, "import pytest\n")

    patched_source = "".join(lines)

    # Calculate path relative to repo root
    try:
        rel_path = test_file.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        rel_path = test_file.as_posix()

    diff = list(difflib.unified_diff(
        original_source.splitlines(keepends=True),
        patched_source.splitlines(keepends=True),
        fromfile=f"a/{rel_path}",
        tofile=f"b/{rel_path}",
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
