#!/usr/bin/env python3
"""
Benchmark Runner: Compare CeLoR vs Pure-LLM on 30 broken Kubernetes manifests.

This script executes three approaches:
1. CeLoR Cold Start (no Fix Bank)
2. CeLoR Warm Start (with Fix Bank from cold start)
3. Pure-LLM Baseline (iterative LLM calls)

Collects comprehensive metrics and generates comparison reports.
"""

import json
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from celor.core.controller import repair_artifact
from celor.core.cegis.synthesizer import SynthConfig
from celor.core.fixbank import FixBank
from celor.k8s.artifact import K8sArtifact
from celor.k8s.examples import get_k8s_template_and_holes
from celor.k8s.oracle_config import get_oracles_for_scenario
from celor.llm.adapter import LLMAdapter

# Setup logging
# Use INFO level for detailed template/synthesis tracking
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)
# Reduce noise from other loggers
logging.getLogger("celor.core.cegis.loop").setLevel(logging.WARNING)
logging.getLogger("celor.llm").setLevel(logging.WARNING)

# Configuration
BENCHMARK_DIR = Path(__file__).parent
PROJECT_ROOT = BENCHMARK_DIR.parent
MANIFESTS_DIR = BENCHMARK_DIR / "manifests"
RESULTS_DIR = BENCHMARK_DIR / "results"
FIXBANK_DIR = BENCHMARK_DIR / "fixbank"
FIXBANK_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

# Ensure config.json is found (it's in project root)
import os
import sys
# Change to project root so config.json can be found
os.chdir(PROJECT_ROOT)

# Benchmark configuration
MAX_ITERS = 10
MAX_CANDIDATES = 1000
TIMEOUT_SECONDS = 60.0
PURE_LLM_MAX_ITERATIONS = 10  # Max LLM iterations for pure-LLM approach


def run_celor_cold_start(case_id: int, manifest_path: Path, fixbank: Optional[FixBank] = None, llm_adapter: Optional[LLMAdapter] = None) -> Dict[str, Any]:
    """Run CeLoR cold start (no Fix Bank) on a single case.
    
    Args:
        case_id: Case number (1-100)
        manifest_path: Path to broken manifest
        fixbank: Fix Bank instance (optional, for learning)
        llm_adapter: LLM adapter to reuse (optional, will create if None)
        
    Returns:
        Dictionary with metrics
    """
    print(f"  CeLoR Cold: case_{case_id:03d}...", end=" ", flush=True)
    
    start_time = time.time()
    
    try:
        # Load artifact
        artifact = K8sArtifact.from_file(str(manifest_path))
        
        # Setup oracles (benchmark config, no external for speed)
        oracles = get_oracles_for_scenario("benchmark", include_external=False)
        
        # Check initial violations (must do this before LLM adapter to catch errors early)
        initial_violations = []
        for oracle in oracles:
            initial_violations.extend(oracle(artifact))
        
        if not initial_violations:
            elapsed = time.time() - start_time
            print(f"✅ (no violations)")
            return {
                "case_id": case_id,
                "status": "success",
                "success": True,
                "time_seconds": elapsed,
                "llm_calls": 0,
                "iterations": 0,
                "candidates_tried": 0,
                "constraints_learned": 0,
                "fixbank_hit": False,
                "initial_violations": len(initial_violations),
                "final_violations": 0,
                "violations_fixed": 0,
                "error": None
            }
        
        # Use provided LLM adapter or create one if not provided
        if llm_adapter is None:
            try:
                llm_adapter = LLMAdapter()
            except Exception as e:
                # If LLM adapter fails, still record violations
                elapsed = time.time() - start_time
                print(f"❌ LLM ERROR ({elapsed:.1f}s): {str(e)[:50]}")
                return {
                    "case_id": case_id,
                    "status": "error",
                    "success": False,
                    "time_seconds": elapsed,
                    "llm_calls": 0,
                    "iterations": 0,
                    "candidates_tried": 0,
                    "constraints_learned": 0,
                    "fixbank_hit": False,
                    "initial_violations": len(initial_violations),
                    "final_violations": len(initial_violations),
                    "violations_fixed": 0,
                    "error": str(e)
                }
        
        # Setup synthesis config
        config = SynthConfig(
            max_candidates=MAX_CANDIDATES,
            timeout_seconds=TIMEOUT_SECONDS
        )
        
        # Run repair (with Fix Bank for learning, but skip lookups in cold start)
        # Add debug: log LLM template if generated
        repaired_artifact, metadata = repair_artifact(
            artifact=artifact,
            oracles=oracles,
            max_iters=MAX_ITERS,
            config=config,
            fixbank=fixbank,  # Cold start - use Fix Bank to learn (but skip lookups)
            llm_adapter=llm_adapter,
            default_template_fn=get_k8s_template_and_holes,
            skip_fixbank_lookup=True  # Cold start: skip lookups, but still write to Fix Bank
        )
        
        # Add template info to metadata for debugging
        if "template_ops" not in metadata:
            metadata["template_ops"] = []
        if "hole_space_keys" not in metadata:
            metadata["hole_space_keys"] = []
        
        # Check final violations
        final_violations = []
        for oracle in oracles:
            final_violations.extend(oracle(repaired_artifact))
        
        elapsed = time.time() - start_time
        success = metadata["status"] == "success" and len(final_violations) == 0
        
        if success:
            print(f"✅ ({elapsed:.1f}s)")
        else:
            print(f"❌ ({elapsed:.1f}s, {metadata['status']})")
        
        return {
            "case_id": case_id,
            "status": metadata["status"],
            "success": success,
            "time_seconds": elapsed,
            "llm_calls": metadata.get("llm_calls", 0),
            "iterations": metadata.get("iterations", 0),
            "candidates_tried": metadata.get("tried_candidates", 0),
            "constraints_learned": len(metadata.get("constraints", [])),
            "fixbank_hit": metadata.get("fixbank_hit", False),
            "initial_violations": len(initial_violations),
            "final_violations": len(final_violations),
            "violations_fixed": len(initial_violations) - len(final_violations),
            "error": None
        }
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ ERROR ({elapsed:.1f}s): {str(e)[:50]}")
        # Try to get violations even on error
        try:
            artifact = K8sArtifact.from_file(str(manifest_path))
            oracles = get_oracles_for_scenario("benchmark", include_external=False)
            initial_violations = []
            for oracle in oracles:
                initial_violations.extend(oracle(artifact))
        except:
            initial_violations = []
        
        return {
            "case_id": case_id,
            "status": "error",
            "success": False,
            "time_seconds": elapsed,
            "llm_calls": 0,
            "iterations": 0,
            "candidates_tried": 0,
            "constraints_learned": 0,
            "fixbank_hit": False,
            "initial_violations": len(initial_violations),
            "final_violations": len(initial_violations),
            "violations_fixed": 0,
            "error": str(e)
        }


def run_celor_warm_start(case_id: int, manifest_path: Path, fixbank: FixBank, llm_adapter: Optional[LLMAdapter] = None) -> Dict[str, Any]:
    """Run CeLoR warm start (with Fix Bank) on a single case.
    
    Args:
        case_id: Case number (1-100)
        manifest_path: Path to broken manifest
        fixbank: Fix Bank instance (from cold start)
        
    Returns:
        Dictionary with metrics
    """
    print(f"  CeLoR Warm: case_{case_id:03d}...", end=" ", flush=True)
    
    start_time = time.time()
    
    try:
        # Load artifact
        artifact = K8sArtifact.from_file(str(manifest_path))
        
        # Setup oracles
        oracles = get_oracles_for_scenario("benchmark", include_external=False)
        
        # Check initial violations
        initial_violations = []
        for oracle in oracles:
            initial_violations.extend(oracle(artifact))
        
        if not initial_violations:
            elapsed = time.time() - start_time
            print(f"✅ (no violations)")
            return {
                "case_id": case_id,
                "status": "success",
                "success": True,
                "time_seconds": elapsed,
                "llm_calls": 0,
                "iterations": 0,
                "candidates_tried": 0,
                "constraints_learned": 0,
                "constraints_reused": 0,
                "fixbank_hit": False,
                "initial_violations": len(initial_violations),
                "final_violations": 0,
                "violations_fixed": 0,
                "error": None
            }
        
        # Use provided LLM adapter or create one if not provided
        if llm_adapter is None:
            try:
                llm_adapter = LLMAdapter()
            except Exception as e:
                elapsed = time.time() - start_time
                print(f"❌ LLM ERROR ({elapsed:.1f}s): {str(e)[:50]}")
                return {
                    "case_id": case_id,
                    "status": "error",
                    "success": False,
                    "time_seconds": elapsed,
                    "llm_calls": 0,
                    "iterations": 0,
                    "candidates_tried": 0,
                    "constraints_learned": 0,
                    "constraints_reused": 0,
                    "fixbank_hit": False,
                    "initial_violations": len(initial_violations),
                    "final_violations": len(initial_violations),
                    "violations_fixed": 0,
                    "error": str(e)
                }
        
        # Setup synthesis config
        config = SynthConfig(
            max_candidates=MAX_CANDIDATES,
            timeout_seconds=TIMEOUT_SECONDS
        )
        
        # Run repair (with Fix Bank)
        repaired_artifact, metadata = repair_artifact(
            artifact=artifact,
            oracles=oracles,
            max_iters=MAX_ITERS,
            config=config,
            fixbank=fixbank,  # Warm start - use Fix Bank
            llm_adapter=llm_adapter,
            default_template_fn=get_k8s_template_and_holes
        )
        
        # Check final violations
        final_violations = []
        for oracle in oracles:
            final_violations.extend(oracle(repaired_artifact))
        
        elapsed = time.time() - start_time
        success = metadata["status"] == "success" and len(final_violations) == 0
        
        # Count reused constraints
        constraints_reused = len(metadata.get("constraints", [])) if metadata.get("fixbank_hit") else 0
        
        if success:
            hit_miss = "HIT" if metadata.get("fixbank_hit") else "MISS"
            print(f"✅ {hit_miss} ({elapsed:.1f}s)")
        else:
            print(f"❌ ({elapsed:.1f}s, {metadata['status']})")
        
        return {
            "case_id": case_id,
            "status": metadata["status"],
            "success": success,
            "time_seconds": elapsed,
            "llm_calls": metadata.get("llm_calls", 0),
            "iterations": metadata.get("iterations", 0),
            "candidates_tried": metadata.get("tried_candidates", 0),
            "constraints_learned": len(metadata.get("constraints", [])),
            "constraints_reused": constraints_reused,
            "fixbank_hit": metadata.get("fixbank_hit", False),
            "initial_violations": len(initial_violations),
            "final_violations": len(final_violations),
            "violations_fixed": len(initial_violations) - len(final_violations),
            "error": None
        }
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ ERROR ({elapsed:.1f}s): {str(e)[:50]}")
        return {
            "case_id": case_id,
            "status": "error",
            "success": False,
            "time_seconds": elapsed,
            "llm_calls": 0,
            "iterations": 0,
            "candidates_tried": 0,
            "constraints_learned": 0,
            "constraints_reused": 0,
            "fixbank_hit": False,
            "initial_violations": 0,
            "final_violations": 0,
            "violations_fixed": 0,
            "error": str(e)
        }


def run_pure_llm_baseline(case_id: int, manifest_path: Path, llm_adapter: Optional[LLMAdapter] = None) -> Dict[str, Any]:
    """Run Pure-LLM baseline (iterative LLM calls) on a single case.
    
    This simulates a pure LLM approach that iteratively calls the LLM
    to fix violations until all are resolved or max iterations reached.
    
    Args:
        case_id: Case number (1-100)
        manifest_path: Path to broken manifest
        
    Returns:
        Dictionary with metrics
    """
    print(f"  Pure-LLM:   case_{case_id:03d}...", end=" ", flush=True)
    
    start_time = time.time()
    llm_calls = 0
    iterations = 0
    
    try:
        # Load artifact
        artifact = K8sArtifact.from_file(str(manifest_path))
        
        # Setup oracles
        oracles = get_oracles_for_scenario("benchmark", include_external=False)
        
        # Check initial violations
        initial_violations = []
        for oracle in oracles:
            initial_violations.extend(oracle(artifact))
        
        if not initial_violations:
            elapsed = time.time() - start_time
            print(f"✅ (no violations)")
            return {
                "case_id": case_id,
                "status": "success",
                "success": True,
                "time_seconds": elapsed,
                "llm_calls": 0,
                "iterations": 0,
                "initial_violations": len(initial_violations),
                "final_violations": 0,
                "violations_fixed": 0,
                "error": None
            }
        
        # Use provided LLM adapter or create one if not provided
        if llm_adapter is None:
            try:
                llm_adapter = LLMAdapter()
            except Exception as e:
                elapsed = time.time() - start_time
                print(f"❌ LLM ERROR ({elapsed:.1f}s): {str(e)[:50]}")
                return {
                    "case_id": case_id,
                    "status": "error",
                    "success": False,
                    "time_seconds": elapsed,
                    "llm_calls": 0,
                    "iterations": 0,
                    "initial_violations": len(initial_violations),
                    "final_violations": len(initial_violations),
                    "violations_fixed": 0,
                    "error": str(e)
                }
        
        # Iterative LLM repair with feedback tracking
        current_artifact = artifact
        previous_feedback = None  # Track feedback from previous attempts
        
        for iteration in range(PURE_LLM_MAX_ITERATIONS):
            iterations = iteration + 1
            
            # Check current violations
            current_violations = []
            for oracle in oracles:
                current_violations.extend(oracle(current_artifact))
            
            if not current_violations:
                # Success!
                elapsed = time.time() - start_time
                print(f"✅ ({iterations} iters, {elapsed:.1f}s)")
                return {
                    "case_id": case_id,
                    "status": "success",
                    "success": True,
                    "time_seconds": elapsed,
                    "llm_calls": llm_calls,
                    "iterations": iterations,
                    "initial_violations": len(initial_violations),
                    "final_violations": 0,
                    "violations_fixed": len(initial_violations),
                    "error": None
                }
            
            # Call LLM to generate concrete patch (no synthesis, pure LLM)
            try:
                patch = llm_adapter.propose_concrete_patch(
                    current_artifact, current_violations, domain="k8s",
                    previous_feedback=previous_feedback
                )
                llm_calls += 1
                
                # Store violations before applying patch
                violations_before = len(current_violations)
                
                # Apply patch directly (no synthesis)
                from celor.k8s.patch_dsl import apply_k8s_patch
                patched_files = apply_k8s_patch(current_artifact.files, patch)
                test_artifact = K8sArtifact(files=patched_files)
                
                # Check violations after applying patch
                violations_after = []
                for oracle in oracles:
                    violations_after.extend(oracle(test_artifact))
                
                # Always update artifact (even if it didn't fix everything)
                # This allows LLM to see progress and iterate
                current_artifact = test_artifact
                
                if len(violations_after) == 0:
                    # Success - all violations fixed
                    previous_feedback = None
                elif len(violations_after) < violations_before:
                    # Made progress but some violations remain
                    previous_feedback = f"Previous attempt: Fixed {violations_before - len(violations_after)} violations. Remaining: {[v.id for v in violations_after]}"
                else:
                    # No progress or made things worse
                    previous_feedback = f"Previous attempt: Applied patch but violations remain ({len(violations_after)} violations). Remaining: {[v.id for v in violations_after]}"
                    
            except Exception as e:
                # LLM call or patch application failed
                llm_calls += 1
                previous_feedback = f"Previous attempt failed: {str(e)[:100]}"
                continue
        
        # Max iterations reached
        final_violations = []
        for oracle in oracles:
            final_violations.extend(oracle(current_artifact))
        
        elapsed = time.time() - start_time
        success = len(final_violations) == 0
        
        if success:
            print(f"✅ ({iterations} iters, {elapsed:.1f}s)")
        else:
            print(f"❌ ({iterations} iters, {elapsed:.1f}s, {len(final_violations)} violations)")
        
        return {
            "case_id": case_id,
            "status": "max_iters" if not success else "success",
            "success": success,
            "time_seconds": elapsed,
            "llm_calls": llm_calls,
            "iterations": iterations,
            "initial_violations": len(initial_violations),
            "final_violations": len(final_violations),
            "violations_fixed": len(initial_violations) - len(final_violations),
            "error": None
        }
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ ERROR ({elapsed:.1f}s): {str(e)[:50]}")
        return {
            "case_id": case_id,
            "status": "error",
            "success": False,
            "time_seconds": elapsed,
            "llm_calls": llm_calls,
            "iterations": iterations,
            "initial_violations": 0,
            "final_violations": 0,
            "violations_fixed": 0,
            "error": str(e)
        }


def get_diverse_case_ids(total_cases: int = 30) -> List[int]:
    """Select diverse case IDs maintaining variety across violation patterns.
    
    Strategy: Select cases to ensure coverage of all 30 patterns from generate_manifests.py.
    Each pattern represents different violation combinations and environments.
    We select approximately half from each pattern to maintain variety.
    
    Pattern distribution (case ranges):
    - Patterns 1-4: Simple violations (cases 1-18)
    - Patterns 5-9: Two-violation combinations (cases 19-36)
    - Patterns 10-14: ECR + other violations (cases 37-54)
    - Patterns 15-19: Three-violation combinations (cases 55-71)
    - Patterns 20-25: Four-violation combinations (cases 72-90)
    - Patterns 26-30: Complex violations (cases 91-100)
    
    Args:
        total_cases: Number of cases to select (default: 30)
        
    Returns:
        List of case IDs (1-100) selected to maintain variety
    """
    # Pattern boundaries from generate_manifests.py
    # Format: (start_case, end_case, pattern_name)
    pattern_ranges = [
        (1, 6, "ECR non-prod"), (7, 10, "ECR prod"), (11, 15, "Security"),
        (16, 18, "Resource"), (19, 22, "ECR+Security non-prod"), (23, 25, "ECR+Security prod"),
        (26, 29, "ECR+Resource non-prod"), (30, 32, "ECR+Resource prod"), (33, 36, "Security+Resource"),
        (37, 40, "ECR+Label prod"), (41, 43, "ECR+Label non-prod"), (44, 47, "ECR+Replicas prod"),
        (48, 51, "ECR+Profile prod"), (52, 54, "ECR+Priority prod"), (55, 58, "ECR+Security+Resource non-prod"),
        (59, 62, "ECR+Security+Resource prod"), (63, 65, "ECR+Security+Label prod"), (66, 68, "ECR+Resource+Label prod"),
        (69, 71, "ECR+Replicas+Profile prod"), (72, 74, "ECR+Security+Resource+Label non-prod"), (75, 78, "ECR+Security+Resource+Label prod"),
        (79, 81, "ECR+Security+Replicas prod"), (82, 84, "ECR+Resource+Replicas prod"), (85, 87, "ECR+Security+Resource+Replicas prod"),
        (88, 90, "ECR+Security+Resource+Label+Replicas prod"), (91, 92, "ECR+Security+Resource+Profile prod"),
        (93, 94, "ECR+Security+Resource+Priority prod"), (95, 96, "ECR+Security+Resource+Label+Profile prod"),
        (97, 98, "ECR+Security+Resource+Label+Priority prod"), (99, 100, "All violations prod")
    ]
    
    case_ids = []
    cases_per_pattern = total_cases // len(pattern_ranges)
    remaining_cases = total_cases % len(pattern_ranges)
    
    # Select cases from each pattern
    for i, (start, end, pattern_name) in enumerate(pattern_ranges):
        pattern_size = end - start + 1
        # Select approximately half from each pattern (or at least 1)
        select_count = max(1, min(cases_per_pattern, pattern_size))
        if i < remaining_cases:  # Distribute remaining cases
            select_count += 1
        
        # Select evenly spaced cases within this pattern
        if select_count >= pattern_size:
            # Take all cases in this pattern
            pattern_cases = list(range(start, end + 1))
        else:
            # Select evenly spaced cases
            step = pattern_size / select_count
            pattern_cases = []
            for j in range(select_count):
                case_id = start + int(j * step)
                if case_id > end:
                    case_id = end
                pattern_cases.append(case_id)
            pattern_cases = sorted(list(set(pattern_cases)))
        
        case_ids.extend(pattern_cases)
    
    # Remove duplicates and sort
    case_ids = sorted(list(set(case_ids)))
    
    # If we have fewer than total_cases, add more evenly distributed
    if len(case_ids) < total_cases:
        all_cases = set(range(1, 101))
        remaining = sorted(list(all_cases - set(case_ids)))
        # Add evenly spaced cases from remaining
        step = len(remaining) / (total_cases - len(case_ids))
        for i in range(total_cases - len(case_ids)):
            idx = int(i * step)
            if idx < len(remaining):
                case_ids.append(remaining[idx])
    
    return sorted(case_ids[:total_cases])


def run_benchmark_phase(phase_name: str, case_ids: Optional[List[int]] = None):
    """Run a complete benchmark phase.
    
    Args:
        phase_name: "cold", "warm", or "pure_llm"
        case_ids: Optional list of case IDs to run (default: 30 diverse cases)
    """
    if case_ids is None:
        case_ids = get_diverse_case_ids(30)
    
    print(f"\n{'=' * 70}")
    print(f"Phase: {phase_name.upper()}")
    print(f"{'=' * 70}")
    
    results = []
    fixbank = None
    
    # For warm start, load Fix Bank from cold start
    if phase_name == "warm":
        fixbank_path = FIXBANK_DIR / ".celor-fixes.json"
        if fixbank_path.exists():
            fixbank = FixBank(str(fixbank_path))
            print(f"Loaded Fix Bank: {len(fixbank.entries)} entries")
        else:
            print("⚠️  Warning: Fix Bank not found, running warm start without Fix Bank")
            fixbank = FixBank(str(fixbank_path))
    
    # For cold start, create new Fix Bank
    if phase_name == "cold":
        fixbank_path = FIXBANK_DIR / ".celor-fixes.json"
        # Remove existing Fix Bank for clean cold start
        if fixbank_path.exists():
            fixbank_path.unlink()
        fixbank = FixBank(str(fixbank_path))
    
    # Create a single LLM adapter to reuse across all cases (avoids connection issues)
    llm_adapter = None
    try:
        llm_adapter = LLMAdapter()
        print(f"✓ LLM adapter initialized (will be reused across all cases)")
    except Exception as e:
        print(f"⚠️  Warning: Could not initialize LLM adapter: {e}")
        print("   Benchmark will continue but LLM calls will fail")
    
    for case_id in case_ids:
        manifest_path = MANIFESTS_DIR / f"case_{case_id:03d}.yaml"
        
        if not manifest_path.exists():
            print(f"⚠️  Warning: {manifest_path} not found, skipping")
            continue
        
        if phase_name == "cold":
            result = run_celor_cold_start(case_id, manifest_path, fixbank, llm_adapter)
            # Fix Bank is saved automatically by repair_artifact on success
        elif phase_name == "warm":
            result = run_celor_warm_start(case_id, manifest_path, fixbank, llm_adapter)
        elif phase_name == "pure_llm":
            result = run_pure_llm_baseline(case_id, manifest_path, llm_adapter)
        else:
            raise ValueError(f"Unknown phase: {phase_name}")
        
        results.append(result)
    
    # Save results
    output_file = RESULTS_DIR / f"{phase_name}_results.json"
    with open(output_file, "w") as f:
        json.dump({
            "phase": phase_name,
            "total_cases": len(results),
            "results": results
        }, f, indent=2)
    
    # Print summary
    success_count = sum(1 for r in results if r["success"])
    total_time = sum(r["time_seconds"] for r in results)
    total_llm_calls = sum(r["llm_calls"] for r in results)
    
    print(f"\nSummary:")
    print(f"  Success rate: {success_count}/{len(results)} ({100*success_count/len(results):.1f}%)")
    print(f"  Total time: {total_time:.1f}s ({total_time/len(results):.1f}s avg)")
    print(f"  Total LLM calls: {total_llm_calls}")
    print(f"  Results saved to: {output_file}")
    
    return results


def main():
    """Run complete benchmark suite."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run CeLoR vs Pure-LLM benchmark")
    parser.add_argument(
        "--pilot",
        action="store_true",
        help="Run pilot test with first 5 cases only"
    )
    parser.add_argument(
        "--phase",
        choices=["cold", "warm", "pure_llm", "all"],
        default="all",
        help="Which phase to run (default: all)"
    )
    parser.add_argument(
        "--cases",
        type=str,
        help="Comma-separated list of case IDs to run (e.g., '1,2,3')"
    )
    args = parser.parse_args()
    
    print("=" * 70)
    print("BENCHMARK: CeLoR vs Pure-LLM Comparison")
    print("=" * 70)
    print(f"Manifests: {MANIFESTS_DIR}")
    print(f"Results: {RESULTS_DIR}")
    print(f"Fix Bank: {FIXBANK_DIR}")
    
    # Check manifests exist
    manifest_files = list(MANIFESTS_DIR.glob("case_*.yaml"))
    if not manifest_files:
        print(f"\n❌ Error: No manifest files found in {MANIFESTS_DIR}")
        print("   Run: python generate_manifests.py first")
        return 1
    
    print(f"\nFound {len(manifest_files)} manifest files")
    
    # Determine case IDs to run
    if args.cases:
        case_ids = [int(x.strip()) for x in args.cases.split(",")]
        print(f"\n📋 Running {len(case_ids)} specified cases")
    elif args.pilot:
        case_ids = list(range(1, 6))  # First 5 cases
        print(f"\n🔬 PILOT MODE: Running first 5 cases only")
    else:
        case_ids = None  # Will use default 30 diverse cases
        print(f"\n📊 DEFAULT MODE: Running 30 diverse cases (selected to maintain variety across all violation patterns)")
    
    # Run phases
    print("\n" + "=" * 70)
    print("Starting benchmark execution...")
    print("=" * 70)
    
    if args.phase in ["cold", "all"]:
        cold_results = run_benchmark_phase("cold", case_ids)
    
    if args.phase in ["warm", "all"]:
        warm_results = run_benchmark_phase("warm", case_ids)
    
    if args.phase in ["pure_llm", "all"]:
        pure_llm_results = run_benchmark_phase("pure_llm", case_ids)
    
    print("\n" + "=" * 70)
    print("Benchmark Complete!")
    print("=" * 70)
    print(f"\nResults saved to: {RESULTS_DIR}")
    print(f"  - cold_results.json")
    print(f"  - warm_results.json")
    print(f"  - pure_llm_results.json")
    print(f"\nNext: Run analysis to generate comparison reports")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

