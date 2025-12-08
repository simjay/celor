"""
CeLoR: CEGIS-in-the-Loop Reasoning

An inference-time verification and repair system for LLM-generated artifacts.
Uses iterative LLM calls to generate parametric patches with holes, then executes
a local CEGIS loop to fill holes using program synthesis without additional LLM calls.
"""

__version__ = "1.0.0"

# Public API exports will be added as components are implemented
__all__ = ["__version__"]
