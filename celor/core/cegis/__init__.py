"""CEGIS (Counterexample-Guided Inductive Synthesis) implementation.

This package contains the inner CEGIS synthesis loop:
- Custom candidate generation and enumeration  
- Constraint-based search space pruning
- Oracle verification
- Synthesis errors

The outer controller loop (LLM orchestration, Fix Bank) is in celor.core.controller.
Counterexample accumulation is in celor.core.accumulator.
"""

from celor.core.cegis.errors import (
    PatchApplyError,
    SynthesisError,
)
from celor.core.cegis.loop import repair
from celor.core.cegis.verifier import verify

__all__ = [
    "repair",
    "verify",
    "PatchApplyError",
    "SynthesisError",
]
