"""Synthesizer for CEGIS loop - custom candidate generation.

This module contains the main synthesis orchestration:
- SynthConfig: Configuration for synthesis runs
- SynthResult: Results from synthesis attempts
- extract_constraints_from_violations: Learn constraints from oracle failures
- synthesize: Main synthesis function using CandidateGenerator
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, List, Literal, Optional

from celor.core.cegis.errors import SynthesisError
from celor.core.schema.artifact import Artifact
from celor.core.schema.oracle import Oracle
from celor.core.schema.patch_dsl import Patch
from celor.core.schema.violation import Violation
from celor.core.synth import CandidateGenerator, Constraint
from celor.core.template import (
    CandidateAssignments,
    HoleSpace,
    PatchTemplate,
    instantiate,
)

logger = logging.getLogger(__name__)


@dataclass
class SynthConfig:
    """Configuration for synthesis runs.
    
    Attributes:
        max_candidates: Maximum number of candidates to try before giving up
        timeout_seconds: Maximum time to spend in synthesis (seconds)
    """
    max_candidates: int = 1000
    timeout_seconds: float = 60.0


@dataclass
class SynthResult:
    """Result from a synthesis attempt.
    
    Attributes:
        status: Outcome of synthesis ("success", "unsat", "timeout")
        patch: The successful patch (if status == "success"), None otherwise
        tried_candidates: Number of candidates evaluated
        constraints: All constraints learned (initial + new)
        last_assignment: The last candidate tried (for debugging)
    """
    status: Literal["success", "unsat", "timeout"]
    patch: Optional[Patch]
    tried_candidates: int
    constraints: list[Constraint]
    last_assignment: Optional[CandidateAssignments]


def extract_constraints_from_violations(
    candidate: CandidateAssignments,
    violations: List[Violation]
) -> list[Constraint]:
    """Extract constraints from oracle failure details.
    
    Looks for constraint hints in violation.evidence field:
    - {"forbid_value": {"hole": "x", "value": v}}
    - {"forbid_tuple": {"holes": [...], "values": [...]}}
    
    These hints are provided by oracles (e.g., PolicyOracle) to help
    the synthesizer learn which hole assignments always fail.

    Args:
        candidate: The candidate assignment that failed
        violations: List of violations from oracles

    Returns:
        List of newly learned Constraint objects
        
    Example:
        >>> candidate = {"env": "prod", "replicas": 2}
        >>> violations = [Violation(..., evidence={"forbid_tuple": {...}})]
        >>> constraints = extract_constraints_from_violations(candidate, violations)
    """
    constraints = []

    for violation in violations:
        if not violation.evidence or not isinstance(violation.evidence, dict):
                continue

        evidence = violation.evidence
        
        # Check for forbid_value hint
        if "forbid_value" in evidence:
            hint = evidence["forbid_value"]
            if isinstance(hint, dict) and "hole" in hint and "value" in hint:
                constraint = Constraint(
                    type="forbidden_value",
                    data={"hole": hint["hole"], "value": hint["value"]}
                )
                constraints.append(constraint)
                logger.debug(f"Learned constraint from oracle: {constraint}")
        
        # Check for forbid_tuple hint
        if "forbid_tuple" in evidence:
            hint = evidence["forbid_tuple"]
            if isinstance(hint, dict) and "holes" in hint and "values" in hint:
                constraint = Constraint(
                    type="forbidden_tuple",
                    data={"holes": hint["holes"], "values": hint["values"]}
                )
                constraints.append(constraint)
                logger.debug(f"Learned constraint from oracle: {constraint}")
    
    return constraints


def synthesize(
    artifact: Artifact,
    template: PatchTemplate,
    hole_space: HoleSpace,
    oracles: List[Oracle],
    config: SynthConfig,
    initial_constraints: Optional[list[Constraint]] = None
) -> SynthResult:
    """Run synthesis using CandidateGenerator with constraint learning.
    
    This is the core synthesis algorithm:
        1. Initialize constraints (start with initial_constraints if provided)
        2. Create CandidateGenerator to enumerate candidates
        3. For each candidate (respecting budget & timeout):
           a. Instantiate template with candidate → Patch
           b. Apply patch to artifact
           c. Evaluate all oracles
           d. If all PASS → SUCCESS (return patch + all constraints)
           e. Else → extract NEW constraints from failures, continue
        4. If all candidates exhausted → UNSAT (return learned constraints)
        5. If timeout → TIMEOUT

    Args:
        artifact: The artifact to repair
        template: PatchTemplate with holes
        hole_space: Domain of possible values for each hole
        oracles: List of oracles to satisfy
        config: Synthesis configuration (budget, timeout)
        initial_constraints: Optional pre-learned constraints (from Fix Bank)

    Returns:
        SynthResult with status, patch (if found), and learned constraints
        
    Note:
        The returned constraints include both initial_constraints AND
        newly learned constraints, making them suitable for Fix Bank storage.
    """
    # Initialize constraints
    all_constraints = list(initial_constraints) if initial_constraints else []
    
    logger.info(f"Starting synthesis with {len(all_constraints)} initial constraints")
    logger.info(f"Hole space size: {len(hole_space)} holes")
    
    # Create candidate generator
    generator = CandidateGenerator(hole_space, all_constraints)
    estimated_size = generator.estimate_size()
    logger.info(f"Estimated candidates (before pruning): {estimated_size}")
    
    tried_candidates = 0
    start_time = time.time()
    last_assignment = None
    
    try:
        for candidate in generator:
            last_assignment = candidate
            tried_candidates += 1
            
            # Check budget
            if tried_candidates > config.max_candidates:
                logger.info(f"Max candidates ({config.max_candidates}) exceeded")
                return SynthResult(
                    status="unsat",
                    patch=None,
                    tried_candidates=tried_candidates,
                    constraints=all_constraints,
                    last_assignment=last_assignment
                )
            
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > config.timeout_seconds:
                logger.info(f"Timeout ({config.timeout_seconds}s) exceeded")
                return SynthResult(
                    status="timeout",
                    patch=None,
                    tried_candidates=tried_candidates,
                    constraints=all_constraints,
                    last_assignment=last_assignment
                )
            
            # Try this candidate
            logger.debug(f"Trying candidate #{tried_candidates}: {candidate}")
            
            # Instantiate template → concrete patch
            try:
                patch = instantiate(template, candidate)
            except Exception as e:
                logger.warning(f"Failed to instantiate template: {e}")
                continue
            
            # Apply patch to artifact
            try:
                patched_artifact = artifact.apply_patch(patch)
            except Exception as e:
                logger.warning(f"Failed to apply patch: {e}")
                continue
            
            # Evaluate all oracles
            all_violations = []
            for oracle in oracles:
                try:
                    violations = oracle(patched_artifact)
                    all_violations.extend(violations)
                except Exception as e:
                    logger.error(f"Oracle evaluation failed: {e}")
                    # Treat oracle failure as violation
                    continue
            
            # Check if all oracles passed
            if not all_violations:
                # SUCCESS!
                logger.info(f"Found solution after {tried_candidates} candidates")
                return SynthResult(
                    status="success",
                    patch=patch,
                    tried_candidates=tried_candidates,
                    constraints=all_constraints,
                    last_assignment=candidate
                )
            
            # Oracles failed - extract constraints
            new_constraints = extract_constraints_from_violations(candidate, all_violations)
            
            if new_constraints:
                logger.debug(f"Learned {len(new_constraints)} new constraints")
                all_constraints.extend(new_constraints)
                
                # Update generator with new constraints (restarts search with pruning)
                generator.update_constraints(all_constraints)
        
        # Exhausted all candidates without finding solution
        logger.info(f"UNSAT: Exhausted all candidates ({tried_candidates} tried)")
        return SynthResult(
            status="unsat",
            patch=None,
            tried_candidates=tried_candidates,
            constraints=all_constraints,
            last_assignment=last_assignment
        )
        
    except Exception as e:
        logger.error(f"Synthesis failed with exception: {e}")
        raise SynthesisError(f"Synthesis failed: {e}") from e
