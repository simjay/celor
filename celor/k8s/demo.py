"""K8s repair demo - End-to-end demonstration of CeLoR.

This module provides a simple demo function showing the complete
CeLoR workflow: loading a manifest, detecting violations, synthesizing
a repair, and verifying the result.
"""

import logging
from pathlib import Path
from typing import Optional

from celor.core.cegis.loop import repair
from celor.core.cegis.synthesizer import SynthConfig
from celor.k8s.artifact import K8sArtifact
from celor.k8s.examples import LLM_EDITED_DEPLOYMENT, payments_api_template_and_holes
from celor.k8s.oracles import PolicyOracle, ResourceOracle, SecurityOracle

logger = logging.getLogger(__name__)


def demo_repair(
    input_file: Optional[str] = None,
    output_dir: Optional[str] = None,
    verbose: bool = True,
    fixbank_path: Optional[str] = None
) -> tuple[K8sArtifact, dict]:
    """Demonstrate K8s manifest repair using CeLoR.
    
    This function shows the complete CeLoR workflow:
    1. Load non-compliant manifest (or use example)
    2. Run oracles to detect violations
    3. Synthesize repair using CEGIS
    4. Verify repaired manifest passes all oracles
    5. Optionally write output
    
    Args:
        input_file: Path to input deployment.yaml (uses example if None)
        output_dir: Directory to write repaired manifest (skips if None)
        verbose: Print detailed progress information
        
    Returns:
        Tuple of (repaired_artifact, metadata)
        
    Example:
        >>> repaired, meta = demo_repair()
        >>> print(f"Repaired in {meta['tried_candidates']} candidates")
    """
    if verbose:
        logging.basicConfig(level=logging.INFO)
        print("=" * 60)
        print("CeLoR K8s Repair Demo")
        print("=" * 60)
    
    # Step 1: Load artifact
    if input_file is None:
        if verbose:
            print("\n[1] Using example LLM-edited manifest...")
        artifact = K8sArtifact(files={"deployment.yaml": LLM_EDITED_DEPLOYMENT})
    else:
        if verbose:
            print(f"\n[1] Loading manifest from {input_file}...")
        artifact = K8sArtifact.from_file(input_file)
    
    # Step 2: Setup oracles and Fix Bank
    if verbose:
        print("[2] Setting up oracles and Fix Bank...")
    
    oracles = [PolicyOracle(), SecurityOracle(), ResourceOracle()]
    
    # Setup Fix Bank if path provided
    fixbank = None
    if fixbank_path:
        from celor.core.fixbank import FixBank
        fixbank = FixBank(fixbank_path)
        if verbose:
            print(f"    Fix Bank loaded: {fixbank_path} ({len(fixbank.entries)} entries)")
    
    # Template will be determined by controller (Fix Bank or default)
    if verbose and not fixbank:
        print("    No Fix Bank - using default template")
    
    # Step 3: Check initial violations
    if verbose:
        print("\n[3] Checking initial violations...")
    
    initial_violations = []
    for oracle in oracles:
        violations = oracle(artifact)
        initial_violations.extend(violations)
        if verbose and violations:
            print(f"    {oracle.__class__.__name__}: {len(violations)} violations")
            for v in violations[:2]:  # Show first 2
                print(f"      - {v.id}: {v.message}")
            if len(violations) > 2:
                print(f"      ... and {len(violations) - 2} more")
    
    if verbose:
        print(f"\n    Total initial violations: {len(initial_violations)}")
    
    # Step 4: Run CEGIS repair (with Fix Bank integration)
    if verbose:
        print("\n[4] Running CEGIS repair...")
    
    config = SynthConfig(max_candidates=100, timeout_seconds=30.0)
    
    from celor.core.controller import repair_artifact
    
    repaired_artifact, metadata = repair_artifact(
        artifact=artifact,
        template=None,  # Let controller decide (Fix Bank or default)
        hole_space=None,
        oracles=oracles,
        max_iters=5,
        config=config,
        fixbank=fixbank,
        default_template_fn=payments_api_template_and_holes
    )
    
    # Step 5: Show results
    if verbose:
        print(f"\n[5] Repair completed!")
        print(f"    Status: {metadata['status']}")
        print(f"    Fix Bank: {'HIT' if metadata.get('fixbank_hit') else 'MISS'}")
        print(f"    Iterations: {metadata['iterations']}")
        print(f"    Candidates tried: {metadata['tried_candidates']}")
        print(f"    Constraints learned: {len(metadata['constraints'])}")
        if metadata.get('fixbank_hit') and fixbank:
            print(f"    Fix Bank entries: {len(fixbank.entries)}")
    
    # Step 6: Verify final state
    if metadata['status'] == 'success':
        if verbose:
            print("\n[6] Verifying repaired manifest...")
        
        final_violations = []
        for oracle in oracles:
            violations = oracle(repaired_artifact)
            final_violations.extend(violations)
        
        if verbose:
            print(f"    Final violations: {len(final_violations)}")
        
        if len(final_violations) == 0:
            if verbose:
                print("    ✅ All oracles PASS!")
        else:
            if verbose:
                print("    ⚠ Some violations remain:")
                for v in final_violations:
                    print(f"      - {v.id}: {v.message}")
        
        # Write output
        if output_dir:
            if verbose:
                print(f"\n[7] Writing repaired manifest to {output_dir}...")
            repaired_artifact.write_to_dir(output_dir)
            if verbose:
                print(f"    ✓ Wrote deployment.yaml")
    else:
        if verbose:
            print(f"\n[6] ⚠ Repair failed with status: {metadata['status']}")
            if 'violations' in metadata:
                print(f"    Remaining violations: {len(metadata['violations'])}")
    
    if verbose:
        print("\n" + "=" * 60)
    
    return repaired_artifact, metadata


def main():
    """CLI entry point for demo."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="CeLoR K8s Repair Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with example manifest
  python -m celor.k8s.demo
  
  # Repair custom manifest
  python -m celor.k8s.demo --input deployment.yaml --output ./fixed/
  
  # Quiet mode
  python -m celor.k8s.demo --quiet
"""
    )
    
    parser.add_argument(
        "--input",
        help="Input deployment.yaml (uses example if not provided)"
    )
    parser.add_argument(
        "--output",
        help="Output directory for repaired manifest"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress verbose output"
    )
    parser.add_argument(
        "--fixbank",
        help="Path to Fix Bank file (enables cross-run learning)"
    )
    
    args = parser.parse_args()
    
    try:
        repaired, metadata = demo_repair(
            input_file=args.input,
            output_dir=args.output,
            verbose=not args.quiet,
            fixbank_path=args.fixbank
        )
        
        # Exit code based on status
        if metadata['status'] == 'success':
            exit(0)
        else:
            exit(1)
            
    except Exception as e:
        print(f"Error: {e}")
        if args.quiet:
            logger.exception("Demo failed")
        raise


if __name__ == "__main__":
    main()

