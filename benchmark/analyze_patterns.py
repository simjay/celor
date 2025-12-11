#!/usr/bin/env python3
"""Analyze violation patterns in detail to understand diversity."""

import json
from collections import Counter
from pathlib import Path

BENCHMARK_DIR = Path(__file__).parent
RESULTS_DIR = BENCHMARK_DIR / "results"

with open(RESULTS_DIR / "validation_results.json") as f:
    data = json.load(f)

results = data['results']

print("=" * 70)
print("DETAILED VIOLATION PATTERN ANALYSIS")
print("=" * 70)

# Group by specific violation ID combinations (not just types)
violation_id_combos = {}
for r in results:
    # Create signature from sorted violation IDs
    violation_ids = sorted([v['id'] for v in r['violations']])
    sig = tuple(violation_ids)
    
    if sig not in violation_id_combos:
        violation_id_combos[sig] = []
    violation_id_combos[sig].append(r['file'])

print(f"\n✅ Total unique violation ID combinations: {len(violation_id_combos)}")
print(f"   Target: 20-30 patterns for Fix Bank evaluation")

if len(violation_id_combos) >= 20 and len(violation_id_combos) <= 30:
    print(f"   ✅ SUCCESS: Within target range!")
elif len(violation_id_combos) < 20:
    print(f"   ⚠️  WARNING: Below target (need {20 - len(violation_id_combos)} more)")
else:
    print(f"   ⚠️  WARNING: Above target (have {len(violation_id_combos) - 30} extra)")

# Show top patterns
print(f"\n=== Top 30 Violation ID Patterns ===")
sorted_patterns = sorted(violation_id_combos.items(), key=lambda x: -len(x[1]))
for i, (sig, files) in enumerate(sorted_patterns[:30], 1):
    print(f"\nPattern {i}: {len(files)} cases")
    print(f"  Violations: {', '.join(sig)}")
    print(f"  Files: {', '.join(files[:5])}{' ...' if len(files) > 5 else ''}")

# Summary statistics
pattern_sizes = Counter(len(files) for files in violation_id_combos.values())
print(f"\n=== Pattern Size Distribution ===")
for size, count in sorted(pattern_sizes.items()):
    print(f"  Patterns with {size} case(s): {count}")

print("\n" + "=" * 70)

