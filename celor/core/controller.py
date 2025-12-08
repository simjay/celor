"""Controller for orchestrating LLM, Fix Bank, and CEGIS synthesis.

This module provides the main entry point for CeLoR's repair workflow:
- repair_artifact: Main API with Fix Bank and LLM integration
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from celor.core.cegis.loop import repair
from celor.core.cegis.synthesizer import SynthConfig
from celor.core.config import get_config_value
from celor.core.fixbank import FixBank, FixEntry, build_signature
from celor.core.schema.artifact import Artifact
from celor.core.schema.oracle import Oracle
from celor.core.schema.violation import Violation
from celor.core.synth import Constraint
from celor.core.template import HoleSpace, PatchTemplate
from celor.llm.adapter import LLMAdapter

logger = logging.getLogger(__name__)


def _determine_template_source(
    artifact: Artifact,
    violations: List[Violation],
    fixbank: Optional[FixBank],
    llm_adapter: Optional[LLMAdapter],
    default_template_fn: Optional[Callable[[], Tuple[PatchTemplate, HoleSpace]]],
    provided_template: Optional[PatchTemplate],
    provided_hole_space: Optional[HoleSpace]
) -> Tuple[PatchTemplate, HoleSpace, Optional[List[Constraint]], bool, int]:
    """Determine template and hole space source based on priority.
    
    Priority: Fix Bank > LLM > default_template_fn > provided parameters
    
    Args:
        artifact: Artifact being repaired
        violations: Current violations
        fixbank: Optional Fix Bank instance
        llm_adapter: Optional LLM adapter
        default_template_fn: Optional default template function
        provided_template: Optional template from caller
        provided_hole_space: Optional hole space from caller
        
    Returns:
        Tuple of (template, hole_space, initial_constraints, fixbank_hit, llm_calls)
    """
    fixbank_hit = False
    llm_calls = 0
    initial_constraints: Optional[List[Constraint]] = None
    template: Optional[PatchTemplate] = None
    hole_space: Optional[HoleSpace] = None
    
    # Priority 1: Check Fix Bank
    if fixbank is not None:
        signature = build_signature(artifact, violations)
        entry = fixbank.lookup(signature)
        if entry is not None:
            template = entry.template
            hole_space = entry.hole_space
            initial_constraints = entry.learned_constraints
            fixbank_hit = True
            logger.info(f"Fix Bank HIT! Reusing template with {len(initial_constraints)} constraints")
    
    # Priority 2: Try LLM if no Fix Bank hit
    if not fixbank_hit and (template is None or hole_space is None):
        if llm_adapter is None:
            # Try to auto-create from config.json
            api_key = get_config_value(["openai", "api_key"])
            if api_key:
                llm_adapter = LLMAdapter()
                logger.info("Auto-created LLMAdapter from config.json")
        
        if llm_adapter is not None:
            logger.info("Calling LLM to generate template...")
            try:
                template, hole_space = llm_adapter.propose_template(
                    artifact, violations, domain="k8s"
                )
                llm_calls = 1
                logger.info(f"LLM generated template with {len(template.ops)} operations")
            except Exception as e:
                logger.warning(f"LLM call failed: {e}")
                template = None
                hole_space = None
    
    # Priority 3: Use default_template_fn
    if template is None or hole_space is None:
        if default_template_fn:
            logger.info("Using default template function")
            template, hole_space = default_template_fn()
        elif provided_template is not None and provided_hole_space is not None:
            template = provided_template
            hole_space = provided_hole_space
        else:
            raise ValueError(
                "No template/hole_space available. Need one of: "
                "Fix Bank entry, LLM adapter, default_template_fn, or provided template/hole_space"
            )
    
    return template, hole_space, initial_constraints, fixbank_hit, llm_calls


def repair_artifact(
    artifact: Artifact,
    template: Optional[PatchTemplate] = None,
    hole_space: Optional[HoleSpace] = None,
    oracles: Optional[List[Oracle]] = None,
    max_iters: int = 10,
    initial_constraints: Optional[List[Constraint]] = None,
    config: Optional[SynthConfig] = None,
    fixbank: Optional[FixBank] = None,
    llm_adapter: Optional[LLMAdapter] = None,
    default_template_fn: Optional[Callable[[], Tuple[PatchTemplate, HoleSpace]]] = None
) -> Tuple[Artifact, Dict[str, Any]]:
    """High-level repair orchestration with Fix Bank and LLM integration.
    
    Main entry point for CeLoR repair using custom synthesis.
    Orchestrates: Fix Bank lookup → LLM template generation → CEGIS repair → Fix Bank update.
    
    Template Priority:
    1. Fix Bank entry (if found)
    2. LLM generation (if adapter provided and no Fix Bank hit)
    3. default_template_fn (if provided)
    4. Provided template/hole_space parameters
    
    Args:
        artifact: Artifact to repair
        template: PatchTemplate with holes (optional)
        hole_space: Domain of possible values for each hole (optional)
        oracles: List of oracle functions (required)
        max_iters: Maximum CEGIS outer loop iterations
        initial_constraints: Optional pre-learned constraints (overrides Fix Bank)
        config: Synthesis configuration (budget, timeout)
        fixbank: Optional Fix Bank for constraint storage
        llm_adapter: Optional LLM adapter for template generation
        default_template_fn: Function to get default template as fallback
        
    Returns:
        Tuple of (repaired_artifact, metadata)
        
        metadata includes:
        - status: "success" | "unsat" | "timeout" | "max_iters"
        - iterations: Number of CEGIS iterations
        - tried_candidates: Total candidates tried
        - constraints: Learned constraints
        - fixbank_hit: Whether Fix Bank was used
        - llm_calls: Number of LLM calls made
    """
    logger.info("Starting repair_artifact orchestration")
    
    if oracles is None:
        oracles = []
    
    # Step 1: Run oracles to check initial state and build signature
    all_violations = []
    for oracle in oracles:
        violations = oracle(artifact)
        all_violations.extend(violations)
    
    if not all_violations:
        logger.info("Artifact already passes all oracles")
        return artifact, {
            "status": "success",
            "iterations": 0,
            "tried_candidates": 0,
            "constraints": [],
            "fixbank_hit": False,
            "llm_calls": 0
        }
    
    # Step 2: Build signature and determine template source
    signature = build_signature(artifact, all_violations)
    logger.info(f"Built signature: {signature}")
    
    template, hole_space, fixbank_constraints, fixbank_hit, llm_calls = _determine_template_source(
        artifact=artifact,
        violations=all_violations,
        fixbank=fixbank,
        llm_adapter=llm_adapter,
        default_template_fn=default_template_fn,
        provided_template=template,
        provided_hole_space=hole_space
    )
    
    # Use Fix Bank constraints unless overridden
    if initial_constraints is None:
        initial_constraints = fixbank_constraints
    
    # Step 3: Call CEGIS repair loop
    logger.info("Calling CEGIS repair loop")
    repaired_artifact, repair_metadata = repair(
        artifact=artifact,
        template=template,
        hole_space=hole_space,
        oracles=oracles,
        max_iters=max_iters,
        initial_constraints=initial_constraints,
        config=config
    )
    
    # Step 4: Update Fix Bank on success
    if fixbank is not None and repair_metadata["status"] == "success":
        from celor.core.fixbank import FixEntry
        
        if not fixbank_hit:
            # New signature - add to Fix Bank
            logger.info("Adding new entry to Fix Bank")
            fixbank.add(FixEntry(
                signature=signature,
                template=template,
                hole_space=hole_space,
                learned_constraints=repair_metadata["constraints"],
                successful_assignment=repair_metadata.get("last_assignment"),
                metadata={
                    "candidates_tried": repair_metadata["tried_candidates"]
                }
            ))
        else:
            # Existing signature - update metadata
            logger.info("Updating existing Fix Bank entry")
            fixbank.add(FixEntry(
                signature=signature,
                template=template,
                hole_space=hole_space,
                learned_constraints=repair_metadata["constraints"]
            ))
    
    # Add controller-level metadata
    repair_metadata["fixbank_hit"] = fixbank_hit
    repair_metadata["llm_calls"] = llm_calls
    
    return repaired_artifact, repair_metadata
