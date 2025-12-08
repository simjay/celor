"""CEGIS loop controller for iterative repair.

This module implements the main CEGIS (Counterexample-Guided Inductive Synthesis)
loop using custom candidate generation instead of external synthesis tools.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from celor.core.cegis.errors import PatchApplyError, SynthesisError
from celor.core.cegis.synthesizer import SynthConfig, synthesize
from celor.core.schema.artifact import Artifact
from celor.core.schema.oracle import Oracle
from celor.core.schema.violation import Violation
from celor.core.synth import Constraint
from celor.core.template import HoleSpace, PatchTemplate

logger = logging.getLogger(__name__)


def repair(
    artifact: Artifact,
    template: PatchTemplate,
    hole_space: HoleSpace,
    oracles: List[Oracle],
    max_iters: int = 10,
    initial_constraints: Optional[List[Constraint]] = None,
    config: Optional[SynthConfig] = None
) -> Tuple[Artifact, Dict[str, Any]]:
    """CEGIS repair loop with custom synthesis.
    
    Implements the classic CEGIS algorithm:
    1. Verify current artifact against oracles
    2. If all pass → return artifact (success)
    3. Else → synthesize patch using template and hole space
    4. Apply patch and repeat
    
    This version uses custom CandidateGenerator instead of Sketch,
    making it domain-agnostic and simpler.

    Args:
        artifact: Initial artifact to repair
        template: PatchTemplate with holes to instantiate
        hole_space: Domain of possible values for each hole
        oracles: List of oracles to satisfy
        max_iters: Maximum CEGIS iterations (outer loop)
        initial_constraints: Optional pre-learned constraints (from Fix Bank)
        config: Synthesis configuration (budget, timeout)

    Returns:
        Tuple of (repaired_artifact, metadata)
        
        metadata contains:
        - status: "success" | "unsat" | "timeout" | "max_iters"
        - iterations: Number of CEGIS iterations performed
        - tried_candidates: Total candidates tried across all iterations
        - constraints: All learned constraints
        - last_assignment: The winning candidate (if success)
        - violations: Final violations (if failed)
        
    Raises:
        SynthesisError: If synthesis fails unexpectedly
        PatchApplyError: If patch application fails

    Example:
        >>> from celor.k8s.artifact import K8sArtifact
        >>> from celor.k8s.examples import payments_api_template_and_holes
        >>> from celor.k8s.oracles import PolicyOracle
        >>> 
        >>> artifact = K8sArtifact.from_file("deployment.yaml")
        >>> template, hole_space = payments_api_template_and_holes()
        >>> oracles = [PolicyOracle()]
        >>> 
        >>> repaired, metadata = repair(artifact, template, hole_space, oracles)
    """
    # Initialize configuration
    if config is None:
        config = SynthConfig()

    logger.info("Starting CEGIS repair loop")
    logger.info(f"Max iterations: {max_iters}")
    logger.info(f"Template has {len(template.ops)} operations")
    logger.info(f"Hole space has {len(hole_space)} holes")
    
    current_artifact = artifact
    total_candidates_tried = 0
    learned_constraints = list(initial_constraints) if initial_constraints else []
    all_seen_violations: List[Violation] = []  # Track violations for metadata
    last_synth_result = None  # Track last synthesis result for candidate capture

    for iteration in range(max_iters):
        logger.info(f"=== CEGIS Iteration {iteration + 1}/{max_iters} ===")
        
        # Step 1: Verify current artifact
        logger.info("Verifying current artifact...")
        all_violations = []
        for oracle in oracles:
            try:
                violations = oracle(current_artifact)
                all_violations.extend(violations)
            except Exception as e:
                logger.error(f"Oracle evaluation failed: {e}")
                raise SynthesisError(f"Oracle failed: {e}") from e
        
        # Check if verification passed
        if not all_violations:
            logger.info(f"✓ Verification PASSED after {iteration} iterations")
            # Capture the last assignment from synthesis if available
            last_assignment = None
            if last_synth_result and last_synth_result.last_assignment:
                last_assignment = last_synth_result.last_assignment
            return (current_artifact, {
                "status": "success",
                "iterations": iteration,
                "tried_candidates": total_candidates_tried,
                "constraints": learned_constraints,
                "last_assignment": last_assignment
            })
        
        # Step 2: Track violations
        logger.info(f"Verification failed with {len(all_violations)} violations")
        all_seen_violations.extend(all_violations)
        
        # Step 3: Synthesize patch
        logger.info("Synthesizing patch...")
        try:
            synth_result = synthesize(
                artifact=current_artifact,
                template=template,
                hole_space=hole_space,
                oracles=oracles,
                config=config,
                initial_constraints=learned_constraints
            )
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            raise SynthesisError(f"Synthesis failed: {e}") from e
        
        total_candidates_tried += synth_result.tried_candidates
        learned_constraints = synth_result.constraints
        
        logger.info(f"Synthesis result: {synth_result.status}")
        logger.info(f"Tried {synth_result.tried_candidates} candidates in this iteration")
        logger.info(f"Learned {len(learned_constraints)} total constraints")
        
        # Check synthesis result
        if synth_result.status == "success" and synth_result.patch is not None:
            # Step 4: Apply patch
            logger.info("Applying synthesized patch...")
            try:
                current_artifact = current_artifact.apply_patch(synth_result.patch)
            except Exception as e:
                logger.error(f"Patch application failed: {e}")
                raise PatchApplyError(f"Failed to apply patch: {e}") from e
            
            logger.info("Patch applied successfully, continuing to next iteration")
            # Continue to next iteration (will verify patched artifact)
            
        elif synth_result.status == "unsat":
            logger.warning("Synthesis returned UNSAT - no valid patch exists")
            return (current_artifact, {
                "status": "unsat",
                "iterations": iteration + 1,
                "tried_candidates": total_candidates_tried,
                "constraints": learned_constraints,
                "last_assignment": synth_result.last_assignment,
                "violations": all_violations
            })
            
        elif synth_result.status == "timeout":
            logger.warning("Synthesis timed out")
            return (current_artifact, {
                "status": "timeout",
                "iterations": iteration + 1,
                "tried_candidates": total_candidates_tried,
                "constraints": learned_constraints,
                "last_assignment": synth_result.last_assignment,
                "violations": all_violations
            })
    
    # Max iterations exceeded
    logger.warning(f"Max iterations ({max_iters}) exceeded without finding solution")
    return (current_artifact, {
        "status": "max_iters",
        "iterations": max_iters,
        "tried_candidates": total_candidates_tried,
        "constraints": learned_constraints,
        "last_assignment": None,
        "violations": all_seen_violations
    })
