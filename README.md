# Flake Doctor

**Flake Doctor** is an autonomous forensic diagnostic engine and closed-loop AST auto-patcher for flaky pytest suites. Instead of naively re-running failing tests until they pass (hiding real bugs), Flake Doctor subjects tests to targeted environmental perturbations (execution reordering, PRNG seed sweeping, and thread-scheduling jitter), calculates rigorous statistical confidence bounds, and generates AST-guided healing patches that turn flaky tests into stable tests while keeping true regression bugs flagged.

## Why Flaky Tests Hurt

Flaky tests erode developer trust in CI/CD, turning green test suites into noisy lotteries and masking genuine regressions until they reach production. Engineering teams lose hours rerunning failed builds or adding arbitrary sleeps, only to have tests fail unpredictably on different runners or under CPU contention. Naive retry loops do not solve flakiness; they institutionalize technical debt and hide race conditions.

## Installation

```bash
# Clone the repository
git clone https://github.com/your-org/flake-doctor.git
cd flake-doctor

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### 1. Basic Scan & Forensic Autopsy
Run Flake Doctor against any pytest test file:
```bash
python -m flakedoctor.cli scan demo_sick_repo/test_patient_zero.py
```

### 2. Export Structured JSON
Export machine-readable forensic results with ISO timestamps and confidence metrics:
```bash
python -m flakedoctor.cli scan demo_sick_repo/test_patient_zero.py --json autopsy_report.json
```

### 3. Generate Healing Patches
Preview unified diffs of proposed AST code fixes without modifying the original test files:
```bash
python -m flakedoctor.cli scan demo_sick_repo/test_patient_zero.py --patch
```

### 4. Closed-Loop Fix Verification
Generate AST patches and immediately re-verify the healed tests through the full 5-stage perturbation engine:
```bash
python -m flakedoctor.cli scan demo_sick_repo/test_patient_zero.py --verify-fix
```

## How It Works

Flake Doctor uses a multi-tiered forensic engine combining static AST analysis with 4 dynamic perturbation detectors:

1. **Order & State Bisect**: Evaluates tests in suite order vs. isolated execution. When a test passes in suite but fails alone, an $O(\log N)$ bisection algorithm isolates the exact upstream polluter mutating shared memory (`os.environ` or module globals).
2. **PRNG Seed Sweep**: Runs the suite across 8 deterministic seeds `[0, 1, 7, 42, 99, 1337, 2026, 9999]`. Tests that flip between pass and fail are diagnosed as `FLAKY_PRNG`.
3. **Schedule-Stress Sweep**: Injects dynamic schedule jitter and thread preemption into worker threads across 6 stress levels ($i \in [0..5]$). Tests sensitive to thread timing are diagnosed as `FLAKY_TIMING`.
4. **Regression Separation (`BROKEN_BUILD`)**: Tests that fail across all execution modes, seeds, and stress levels are classified as genuine bugs, never masked as flaky tests.

### Statistical Confidence Formula

For any test with an observed sweep failure rate $p \in (0, 1)$, Flake Doctor computes the minimum consecutive clean runs $N$ needed to guarantee with 99% confidence that the flake is not merely dormant:

$$N = \left\lceil \frac{\ln(0.01)}{\ln(1 - p)} \right\rceil$$

For example:
- A test with $p = 0.50$ failure rate requires $N = 7$ clean runs.
- A test with $p = 0.25$ failure rate requires $N = 17$ clean runs.

## Limitations

- **Heuristic Failure Rates**: Sweep failure rates are empirical estimates derived from Flake Doctor's targeted perturbation design, not theoretical ground-truth probabilities in arbitrary production environments.
- **Framework Support**: Currently tailored specifically for `pytest` test runners.
- **AST Pattern Scope**: Static code analysis detects common Python flakiness patterns (unseeded `random`, bare `time.sleep`, global dict mutation, unmocked system clocks); domain-specific or C-extension race conditions may require custom synchronization logic.
- **Patching Suggestions**: Auto-patcher rewrites represent high-fidelity heuristic recommendations; developers should review proposed diffs before committing to mission-critical test suites.
