"""AST-based analyzer for detecting common flakiness patterns in test functions."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class AstFinding:
    line: int
    category: str
    code_snippet: str
    prescription: str


def _dotted_name(node: ast.expr) -> str:
    """Extract dotted attribute name from an AST node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _get_module_uppercase_dicts(tree: ast.Module) -> set[str]:
    """Collect names of module-level UPPERCASE assignments that look like dicts."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id.isupper():
                    if isinstance(node.value, ast.Dict):
                        names.add(t.id)
    return names


def _has_seed_before(func_node: ast.FunctionDef, call_lineno: int) -> bool:
    """Check if the function already seeds PRNG before the given line."""
    seed_calls = {
        "random.seed",
        "np.random.seed",
        "numpy.random.seed",
    }
    for node in ast.walk(func_node):
        if isinstance(node, ast.Call) and node.lineno < call_lineno:
            name = _dotted_name(node.func)
            if name in seed_calls:
                return True
            # default_rng(<arg>) or random.Random(<arg>)
            if name in ("default_rng", "np.random.default_rng", "numpy.random.default_rng", "random.Random"):
                if node.args or node.keywords:
                    return True
    return False


def analyze_test(source_path: str | Path, func_name: str) -> List[AstFinding]:
    """Analyze a single test function for flakiness patterns.

    Returns a list of AstFinding instances.
    """
    source_path = Path(source_path)
    source_text = source_path.read_text(encoding="utf-8")
    source_lines = source_text.splitlines()
    tree = ast.parse(source_text, filename=str(source_path))

    module_uppercase_dicts = _get_module_uppercase_dicts(tree)

    # Find the target function node
    func_node: ast.FunctionDef | None = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == func_name:
                func_node = node
                break

    if func_node is None:
        return []

    findings: List[AstFinding] = []

    class _Visitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            name = _dotted_name(node.func)

            # --- UNSEEDED_PRNG ---
            is_random_call = (
                (name.startswith("random.") and name != "random.seed" and name != "random.Random")
                or name.startswith("np.random.")
                or name.startswith("numpy.random.")
            )
            if is_random_call:
                if not _has_seed_before(func_node, node.lineno):
                    snippet = source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else ""
                    findings.append(AstFinding(
                        line=node.lineno,
                        category="UNSEEDED_PRNG",
                        code_snippet=snippet,
                        prescription=(
                            "Seeding makes the test reproducible, not correct. "
                            "Also increase the sample size or assert with a tolerance."
                        ),
                    ))

            # --- TIMING_RACE ---
            if name in ("time.sleep", "sleep"):
                snippet = source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else ""
                findings.append(AstFinding(
                    line=node.lineno,
                    category="TIMING_RACE",
                    code_snippet=snippet,
                    prescription=(
                        "Replace time.sleep with thread.join(timeout=2.0) or threading.Event.wait()."
                    ),
                ))

            # --- CLOCK_DEPENDENCY ---
            if name.endswith(("datetime.now", "datetime.utcnow", "date.today", "time.time")):
                snippet = source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else ""
                findings.append(AstFinding(
                    line=node.lineno,
                    category="CLOCK_DEPENDENCY",
                    code_snippet=snippet,
                    prescription=(
                        "Use monkeypatch.setattr or freezegun.freeze_time() to control time."
                    ),
                ))

            self.generic_visit(node)

        def visit_Assign(self, node: ast.Assign) -> None:
            self._check_state_pollution(node.targets, node)
            self.generic_visit(node)

        def visit_AugAssign(self, node: ast.AugAssign) -> None:
            self._check_state_pollution([node.target], node)
            self.generic_visit(node)

        def _check_state_pollution(self, targets, node: ast.stmt) -> None:
            for target in targets:
                if not isinstance(target, ast.Subscript):
                    continue
                # os.environ[...]
                container_name = _dotted_name(target.value)
                if container_name == "os.environ":
                    snippet = source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else ""
                    findings.append(AstFinding(
                        line=node.lineno,
                        category="STATE_POLLUTION",
                        code_snippet=snippet,
                        prescription=(
                            "Use monkeypatch.setenv() or monkeypatch.setitem() to avoid leaking "
                            "environment changes to other tests."
                        ),
                    ))
                    continue
                # any module-level UPPERCASE dict
                if isinstance(target.value, ast.Name) and target.value.id in module_uppercase_dicts:
                    snippet = source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else ""
                    findings.append(AstFinding(
                        line=node.lineno,
                        category="STATE_POLLUTION",
                        code_snippet=snippet,
                        prescription=(
                            "Use monkeypatch.setitem() to avoid mutating shared module-level state "
                            "across tests."
                        ),
                    ))

    _Visitor().visit(func_node)
    return findings


if __name__ == "__main__":
    import sys
    test_file = Path("demo_sick_repo/test_patient_zero.py")
    for fn in ("test_01_setup_cache", "test_03_unseeded_ml_threshold", "test_04_async_race_condition"):
        print(f"\n=== {fn} ===")
        for f in analyze_test(test_file, fn):
            print(f"  Line {f.line}: [{f.category}] {f.code_snippet!r}")
            print(f"    -> {f.prescription}")
