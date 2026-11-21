"""Throwaway seed-check script."""
import random

seeds = [0, 1, 7, 42, 99, 1337, 2026, 9999]
print(f"{'Seed':>6}  {'Mean':>8}  {'Pass?':>6}")
print("-" * 28)
results = []
for s in seeds:
    random.seed(s)
    values = [random.random() for _ in range(10)]
    mean = sum(values) / len(values)
    passed = mean > 0.42
    results.append((s, mean, passed))
    print(f"{s:>6}  {mean:>8.4f}  {'YES' if passed else 'NO':>6}")

has_pass = any(r[2] for r in results)
has_fail = any(not r[2] for r in results)
print(f"\nhas_pass={has_pass}  has_fail={has_fail}")
pass_seeds = [r[0] for r in results if r[2]]
print(f"pass_seeds={pass_seeds}")
