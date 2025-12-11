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
    violations: List[Violation],
    hole_space: Optional[HoleSpace] = None
) -> list[Constraint]:
    """Extract constraints from oracle failure details.
    
    Looks for constraint hints in violation.evidence field:
    - {"forbid_value": {"hole": "x", "value": v}}
    - {"forbid_tuple": {"holes": [...], "values": [...]}}
    
    These hints are provided by oracles (e.g., PolicyOracle) to help
    the synthesizer learn which hole assignments always fail.
    
    IMPORTANT: Only creates constraints for holes that exist in the template's hole_space.
    This prevents creating constraints for holes that don't exist (e.g., oracle says "env"
    but template only has "ecr_image_version").
    
    Args:
        candidate: The candidate assignment that failed
        violations: List of violations from oracles
        hole_space: Optional hole space to validate constraint holes exist
    
    Returns:
        List of newly learned Constraint objects
        
    Example:
        >>> candidate = {"env": "production-us", "replicas": 2}
        >>> violations = [Violation(..., evidence={"forbid_tuple": {...}})]
        >>> constraints = extract_constraints_from_violations(candidate, violations, hole_space)
    """
    constraints = []
    
    # Get set of valid hole names if hole_space provided
    valid_holes = set(hole_space.keys()) if hole_space else None
    
    for violation in violations:
        if not violation.evidence or not isinstance(violation.evidence, dict):
                continue
        
        evidence = violation.evidence
        
        # Check for forbid_value hint
        if "forbid_value" in evidence:
            hint = evidence["forbid_value"]
            if isinstance(hint, dict) and "hole" in hint and "value" in hint:
                hole_name = hint["hole"]
                # Only create constraint if hole exists in template
                if valid_holes is None or hole_name in valid_holes:
                    constraint = Constraint(
                        type="forbidden_value",
                        data={"hole": hole_name, "value": hint["value"]}
                    )
                    constraints.append(constraint)
                    logger.debug(f"Learned constraint from oracle: {constraint}")
                else:
                    logger.debug(f"Skipping constraint for non-existent hole: {hole_name}")
        
        # Check for forbid_tuple hint
        if "forbid_tuple" in evidence:
            hint = evidence["forbid_tuple"]
            if isinstance(hint, dict) and "holes" in hint and "values" in hint:
                holes = hint["holes"]
                values = hint["values"]
                
                # Filter to only holes that exist in template
                if valid_holes is not None:
                    filtered_holes = []
                    filtered_values = []
                    for h, v in zip(holes, values):
                        if h in valid_holes:
                            filtered_holes.append(h)
                            filtered_values.append(v)
                    
                    # Only create constraint if at least one hole exists
                    if filtered_holes:
                        # If all holes filtered out, convert to forbid_value for the first matching hole
                        if len(filtered_holes) == 1:
                            constraint = Constraint(
                                type="forbidden_value",
                                data={"hole": filtered_holes[0], "value": filtered_values[0]}
                            )
                        else:
                            constraint = Constraint(
                                type="forbidden_tuple",
                                data={"holes": filtered_holes, "values": filtered_values}
                            )
                        constraints.append(constraint)
                        logger.debug(f"Learned constraint from oracle: {constraint}")
                    else:
                        logger.debug(f"Skipping constraint - no matching holes in template: {holes}")
                else:
                    # No hole_space provided - create constraint as-is (backward compatibility)
                    constraint = Constraint(
                        type="forbidden_tuple",
                        data={"holes": holes, "values": values}
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
    logger.info(f"Hole space: {len(hole_space)} holes")
    for hole, values in hole_space.items():
        logger.info(f"  - {hole}: {len(values)} values")
    
    # Create candidate generator
    generator = CandidateGenerator(hole_space, all_constraints)
    estimated_size = generator.estimate_size()
    logger.info(f"Estimated candidates (before constraint pruning): {estimated_size}")
    if estimated_size > config.max_candidates:
        logger.warning(f"⚠️  Search space ({estimated_size}) exceeds max_candidates ({config.max_candidates})")
    
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
            if tried_candidates <= 5 or tried_candidates % 100 == 0:
                logger.info(f"Trying candidate #{tried_candidates}: {candidate}")
            else:
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
            new_constraints = extract_constraints_from_violations(candidate, all_violations, hole_space)
            
            if new_constraints:
                # Deduplicate constraints (avoid adding the same constraint multiple times)
                # Convert lists to tuples for hashability
                def _make_hashable(data):
                    """Convert constraint data to hashable form (lists -> tuples)."""
                    if isinstance(data, dict):
                        return tuple(sorted(
                            (k, _make_hashable(v)) for k, v in data.items()
                        ))
                    elif isinstance(data, list):
                        return tuple(_make_hashable(item) for item in data)
                    else:
                        return data
                
                existing_constraint_set = {
                    (c.type, _make_hashable(c.data))
                    for c in all_constraints
                }
                
                unique_new_constraints = []
                for constraint in new_constraints:
                    constraint_key = (constraint.type, _make_hashable(constraint.data))
                    if constraint_key not in existing_constraint_set:
                        unique_new_constraints.append(constraint)
                        existing_constraint_set.add(constraint_key)
                
                if unique_new_constraints:
                    logger.info(f"❌ Candidate #{tried_candidates} failed. Learned {len(unique_new_constraints)} new constraints:")
                    for constraint in unique_new_constraints:
                        logger.info(f"   {constraint}")
                    all_constraints.extend(unique_new_constraints)
                    
                    # Update generator with new constraints (restarts search with pruning)
                    generator.update_constraints(all_constraints)
                    new_estimated_size = generator.estimate_size()
                    logger.info(f"   Updated search space (after pruning): {new_estimated_size} candidates")
                else:
                    logger.debug(f"❌ Candidate #{tried_candidates} failed. All constraints already known (duplicate).")
            else:
                if tried_candidates <= 5:
                    logger.info(f"❌ Candidate #{tried_candidates} failed. No constraints learned from violations:")
                    for v in all_violations:
                        logger.info(f"   - {v.id}: {v.message}")
        
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
