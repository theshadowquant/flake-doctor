"""Flake Doctor diagnosis engine."""
from __future__ import annotations

import math
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console
from rich.status import Status

from .ast_analyzer import AstFinding, analyze_test

console = Console()

# ---------------------------------------------------------------------------
# Seeds (verified: seeds 7 and 42 give mean <= 0.42; others give > 0.42)
# ---------------------------------------------------------------------------
SEEDS = [0, 1, 7, 42, 99, 1337, 2026, 9999]
PASS_SEED = 0  # mean > 0.42 → test_03 passes when seeded with this

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class TestReport:
    name: str
    verdict: str
    root_cause: str
    culprit: Optional[str]
    fail_rate: float
    runs: int
    findings: List[AstFinding] = field(default_factory=list)
    confidence_runs: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "verdict": self.verdict,
            "root_cause": self.root_cause,
            "culprit": self.culprit,
            "fail_rate": self.fail_rate,
            "runs": self.runs,
            "findings": [
                {
                    "line": f.line,
                    "category": f.category,
                    "code_snippet": f.code_snippet,
                    "prescription": f.prescription,
                }
                for f in self.findings
            ],
            "confidence_runs": self.confidence_runs,
        }


# ---------------------------------------------------------------------------
# Plugin template
# ---------------------------------------------------------------------------

_PLUGIN_TEMPLATE = textwrap.dedent("""\
import os, sys, random, threading, time as _time

def pytest_configure(config):
    stress = os.environ.get("FD_STRESS")
    if stress is not None:
        i = int(stress)
        n_workers = (os.cpu_count() or 2) * 2
        import threading, time as _t
        def _burn():
            while True:
                _ = sum(range(100000))
        for _ in range(n_workers):
            th = threading.Thread(target=_burn, daemon=True)
            th.start()
        sys.setswitchinterval(0.05)
        _orig_sleep = _t.sleep
        _main_thread_id = threading.main_thread().ident
        def _patched_sleep(seconds):
            if threading.current_thread().ident != _main_thread_id:
                extra = 0.012 * i
                _orig_sleep(extra)
            _orig_sleep(seconds)
        _t.sleep = _patched_sleep

def pytest_runtest_setup(item):
    seed = os.environ.get("FD_SEED")
    if seed is not None:
        s = int(seed)
        random.seed(s)
        try:
            import numpy as np
            np.random.seed(s)
        except ImportError:
            pass
""")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_plugin(tmpdir: Path) -> None:
    """Write the injected plugin to tmpdir/_fd_plugin.py."""
    (tmpdir / "_fd_plugin.py").write_text(_PLUGIN_TEMPLATE, encoding="utf-8")


def _build_env(env_extra: Dict[str, str]) -> Dict[str, str]:
    env = os.environ.copy()
    env.update(env_extra)
    # Ensure PYTHONPATH includes the tmpdir (set by caller)
    return env


def _parse_junit(xml_path: Path) -> Dict[str, bool]:
    """Parse JUnit XML → {test_name: passed (True) or failed (False)}."""
    result: Dict[str, bool] = {}
    if not xml_path.exists():
        return result
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError:
        return result
    root = tree.getroot()
    # May be <testsuites><testsuite>... or just <testsuite>...
    suites = root.findall(".//testsuite") or [root]
    for suite in suites:
        for tc in suite.findall("testcase"):
            name = tc.get("name", "")
            # Strip class prefix if present (e.g. "test_01_setup_cache" or "ClassName::test_01_setup_cache")
            if "::" in name:
                name = name.split("::")[-1]
            failed = tc.find("failure") is not None or tc.find("error") is not None
            result[name] = not failed
    return result


def _run_pytest(
    nodeids: List[str],
    env_extra: Dict[str, str],
    plugin_dir: Path,
    project_root: Path,
) -> Dict[str, bool]:
    """Run pytest on the given node ids, return {test_name: passed}."""
    xml_path = plugin_dir / f"result_{uuid.uuid4().hex[:8]}.xml"
    env = _build_env(env_extra)
    # Inject plugin dir on PYTHONPATH
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(plugin_dir) + (os.pathsep + existing_pp if existing_pp else "")
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

    cmd = [
        sys.executable, "-m", "pytest",
        *nodeids,
        "-q",
        "-p", "no:cacheprovider",
        "-p", "_fd_plugin",
        f"--junitxml={xml_path}",
    ]
    try:
        subprocess.run(
            cmd,
            env=env,
            cwd=str(project_root),
            timeout=120,
            capture_output=True,
        )
    except subprocess.TimeoutExpired:
        return {}

    return _parse_junit(xml_path)


def required_clean_runs(p: float) -> Optional[int]:
    """Confidence runs: ceil(ln(0.01) / ln(1-p)). None if p<=0 or p>=1."""
    if p <= 0 or p >= 1:
        return None
    return math.ceil(math.log(0.01) / math.log(1 - p))


# ---------------------------------------------------------------------------
# Bisect polluting predecessor
# ---------------------------------------------------------------------------

def _bisect_polluter(
    target_nodeid: str,
    predecessors: List[str],
    env_extra: Dict[str, str],
    plugin_dir: Path,
    project_root: Path,
) -> Optional[str]:
    """Binary-search the predecessor that causes target to pass."""
    candidates = list(predecessors)

    def run_with(prefix: List[str]) -> bool:
        """Return True if [prefix..., target] run makes target pass."""
        result = _run_pytest(prefix + [target_nodeid], env_extra, plugin_dir, project_root)
        target_name = target_nodeid.split("::")[-1]
        return result.get(target_name, False)

    while len(candidates) > 1:
        mid = len(candidates) // 2
        half_a = candidates[:mid]
        half_b = candidates[mid:]
        if half_a and run_with(half_a):
            candidates = half_a
        elif half_b and run_with(half_b):
            candidates = half_b
        else:
            break  # can't narrow further; report remaining set

    if len(candidates) == 1:
        # Confirm
        ok = run_with(candidates)
        if ok:
            return candidates[0].split("::")[-1]

    # Return best guess (last remaining)
    return candidates[0].split("::")[-1] if candidates else None


# ---------------------------------------------------------------------------
# Main diagnosis entry point
# ---------------------------------------------------------------------------

def diagnose(test_file: str | Path) -> List[TestReport]:
    test_file = Path(test_file).resolve()
    project_root = Path.cwd()

    # Build node id prefix using absolute path
    abs_path = str(test_file)

    # Collect test names in file order
    import ast as _ast
    src = test_file.read_text(encoding="utf-8")
    tree = _ast.parse(src, filename=str(test_file))
    test_names: List[str] = []
    for node in tree.body:
        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
            if node.name.startswith("test"):
                test_names.append(node.name)

    if not test_names:
        return []

    def nodeid(name: str) -> str:
        return f"{abs_path}::{name}"

    all_nodeids = [nodeid(n) for n in test_names]

    # Temp dir for plugin + junit files
    tmpdir = Path(tempfile.mkdtemp(prefix="fd_"))
    try:
        _write_plugin(tmpdir)

        base_env = {"FD_SEED": str(PASS_SEED)}

        # ----------------------------------------------------------------
        # 1. Suite baseline: 3 runs, whole file, file order, FD_SEED=PASS_SEED
        # ----------------------------------------------------------------
        with Status("[bold blue]Step 1/5: Suite baseline...", console=console):
            suite_pass_counts: Dict[str, int] = {n: 0 for n in test_names}
            for _ in range(3):
                r = _run_pytest(all_nodeids, base_env, tmpdir, project_root)
                for name in test_names:
                    if r.get(name, False):
                        suite_pass_counts[name] += 1
            # passes_in_suite: passed ALL 3 suite runs
            passes_in_suite = {n: (suite_pass_counts[n] == 3) for n in test_names}

        # ----------------------------------------------------------------
        # 2. Isolated baseline: 3 runs of each test alone, FD_SEED=PASS_SEED
        # ----------------------------------------------------------------
        with Status("[bold blue]Step 2/5: Isolated baseline...", console=console):
            isolated_fail_counts: Dict[str, int] = {n: 0 for n in test_names}
            for name in test_names:
                for _ in range(3):
                    r = _run_pytest([nodeid(name)], base_env, tmpdir, project_root)
                    if not r.get(name, False):
                        isolated_fail_counts[name] += 1
            # fails_isolated: failed ALL 3 isolated runs
            fails_isolated = {n: (isolated_fail_counts[n] == 3) for n in test_names}

        # ----------------------------------------------------------------
        # 3. Seed sweep: 8 seeds
        # ----------------------------------------------------------------
        with Status("[bold blue]Step 3/5: Seed sweep...", console=console):
            seed_fail_counts: Dict[str, int] = {n: 0 for n in test_names}
            for seed in SEEDS:
                r = _run_pytest(all_nodeids, {"FD_SEED": str(seed)}, tmpdir, project_root)
                for name in test_names:
                    if not r.get(name, False):
                        seed_fail_counts[name] += 1
            seed_fail_rate = {n: seed_fail_counts[n] / len(SEEDS) for n in test_names}

        # ----------------------------------------------------------------
        # 4. Stress jitter: 6 stress levels, FD_SEED=PASS_SEED
        # ----------------------------------------------------------------
        with Status("[bold blue]Step 4/5: Stress jitter...", console=console):
            stress_fail_counts: Dict[str, int] = {n: 0 for n in test_names}
            for i in range(6):
                r = _run_pytest(
                    all_nodeids,
                    {"FD_STRESS": str(i), "FD_SEED": str(PASS_SEED)},
                    tmpdir,
                    project_root,
                )
                for name in test_names:
                    if not r.get(name, False):
                        stress_fail_counts[name] += 1
            stress_fail_rate = {n: stress_fail_counts[n] / 6 for n in test_names}

        # ----------------------------------------------------------------
        # 5. Order/state bisect for order-dependent tests
        # ----------------------------------------------------------------
        with Status("[bold blue]Step 5/5: Order bisect...", console=console):
            culprit_map: Dict[str, Optional[str]] = {}
            for idx, name in enumerate(test_names):
                if passes_in_suite[name] and fails_isolated[name]:
                    predecessors = [nodeid(n) for n in test_names[:idx]]
                    culprit = _bisect_polluter(
                        nodeid(name), predecessors, base_env, tmpdir, project_root
                    )
                    culprit_map[name] = culprit
                else:
                    culprit_map[name] = None

        # ----------------------------------------------------------------
        # Verdict assignment
        # ----------------------------------------------------------------
        reports: List[TestReport] = []
        for name in test_names:
            ps = passes_in_suite[name]
            fi = fails_isolated[name]
            sfr = seed_fail_rate[name]
            stfr = stress_fail_rate[name]
            culprit = culprit_map.get(name)

            # Total failures across all runs (suite + isolated)
            suite_failed_all = not ps  # failed in ALL suite runs
            # BROKEN_BUILD: fails suite (all 3), fails isolated (all 3), fails all sweeps
            is_broken = (
                (suite_pass_counts[name] == 0)   # failed all suite runs
                and fi                            # failed all isolated runs
                and seed_fail_counts[name] == len(SEEDS)  # failed all seed runs
                and stress_fail_counts[name] == 6         # failed all stress runs
            )

            if is_broken:
                verdict = "BROKEN_BUILD"
                root_cause = "Test fails unconditionally in all execution modes"
                fail_rate = 1.0
                total_runs = 3 + 3 + len(SEEDS) + 6
                conf = None
            elif ps and fi:
                verdict = "ORDER_DEPENDENT"
                root_cause = (
                    f"Passes only when preceded by {culprit}; "
                    "relies on shared state set by that test"
                )
                fail_rate = isolated_fail_counts[name] / 3
                total_runs = 3 + 3
                conf = None
            elif 0 < sfr < 1.0:
                verdict = "FLAKY_PRNG"
                root_cause = "Non-deterministic randomness: different seeds flip pass/fail"
                fail_rate = sfr
                total_runs = len(SEEDS)
                conf = required_clean_runs(sfr)
            elif 0 < stfr < 1.0:
                verdict = "FLAKY_TIMING"
                root_cause = "Timing-sensitive: thread scheduling variability flips pass/fail"
                fail_rate = stfr
                total_runs = 6
                conf = required_clean_runs(stfr)
            else:
                verdict = "STABLE"
                root_cause = "No flakiness detected"
                fail_rate = 0.0
                total_runs = 3 + 3 + len(SEEDS) + 6
                conf = None

            # AST analysis: for ORDER_DEPENDENT, analyze culprit predecessor
            if verdict == "ORDER_DEPENDENT" and culprit:
                findings = analyze_test(test_file, culprit)
            else:
                findings = analyze_test(test_file, name)

            reports.append(TestReport(
                name=name,
                verdict=verdict,
                root_cause=root_cause,
                culprit=culprit,
                fail_rate=fail_rate,
                runs=total_runs,
                findings=findings,
                confidence_runs=conf,
            ))

        # ----------------------------------------------------------------
        # Post-pass: POLLUTER promotion
        # ----------------------------------------------------------------
        order_dep_culprits = {
            r.culprit for r in reports if r.verdict == "ORDER_DEPENDENT" and r.culprit
        }
        for r in reports:
            if r.verdict == "STABLE" and r.name in order_dep_culprits:
                r.verdict = "POLLUTER"
                r.root_cause = "Pollutes shared state depended on by downstream test(s)"

        return reports

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
