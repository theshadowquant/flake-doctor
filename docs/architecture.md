# Flake Doctor Architecture

Flake Doctor is an autonomous root-cause diagnosis engine and AST auto-patcher for non-deterministic pytest test suites.

```mermaid
flowchart TD
    TF["Test File (*.py)"] --> AST["AST Analyzer (ast_analyzer.py)"]
    TF --> ENG["Diagnosis Engine (engine.py)"]

    subgraph ENG_PHASES ["5 Forensic Perturbation Phases"]
        S1["1. Suite Baseline (3 runs, in-order)"]
        S2["2. Isolated Baseline (3 runs each, standalone)"]
        S3["3. Seed Sweeper (8 PRNG seeds)"]
        S4["4. Stress Jitter (6 levels schedule perturbation)"]
        S5["5. Order Bisect (O(log N) state pollution search)"]
    end

    ENG --> ENG_PHASES

    ENG_PHASES --> VR["Verdict Rules Engine"]
    AST --> VR

    subgraph VERDICTS ["Diagnostic Verdicts"]
        V1["POLLUTER"]
        V2["ORDER_DEPENDENT"]
        V3["FLAKY_PRNG"]
        V4["FLAKY_TIMING"]
        V5["BROKEN_BUILD"]
        V6["STABLE"]
    end

    VR --> VERDICTS

    VERDICTS --> REP["Forensic Autopsy Report (CLI / JSON)"]
    VERDICTS --> PATCH["Auto-Patcher (patcher.py)"]

    PATCH --> DIFF["Unified Diff (fixes.patch)"]
    PATCH --> VF["Verify-Fix Engine (verify_fix)"]
    VF --> ENG
    VF --> AFTER["After Fix Verification Table"]
```

## Forensic Pipeline Overview

1. **AST Analyzer**: Performs static single-pass inspection of test function ASTs for `UNSEEDED_PRNG`, `TIMING_RACE`, `CLOCK_DEPENDENCY`, and `STATE_POLLUTION`.
2. **Suite Baseline**: Runs the test suite 3 times in original order with a deterministic baseline seed (`PASS_SEED`) to establish a ground-truth pass rate.
3. **Isolated Baseline**: Runs each test independently 3 times in an isolated subprocess to detect order dependency and isolation failures.
4. **Order Bisection**: If a test passes in suite order but fails in isolation, performs binary search bisection across preceding tests to pinpoint the exact culprit test polluting state.
5. **Seed Sweeper**: Runs suite across 8 deterministic PRNG seeds to measure variance and identify seed-dependent thresholds.
6. **Stress Jitter Sweep**: Injects thread scheduling contention and delay perturbations into worker threads to reveal race conditions.
7. **Statistical Confidence**: Computes required clean consecutive runs $N = \lceil \ln(0.01) / \ln(1 - p) \rceil$ to achieve 99% confidence.
8. **Auto-Patcher & Closed Loop Verification**: Transforms flaky patterns via AST-guided rewriting (`monkeypatch`, seeding, synchronization) and proves fixes pass clean runs without mutating original files.
