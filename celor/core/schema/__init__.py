"""
Core schema definitions for artifacts, violations, patches, and oracles.

These domain-agnostic protocols and dataclasses form the foundation
of the CeLoR system.
"""

from celor.core.schema.artifact import Artifact, to_serializable
from celor.core.schema.oracle import Oracle
from celor.core.schema.patch_dsl import Patch, PatchOp
from celor.core.schema.violation import Violation

__all__ = [
    "Artifact",
    "to_serializable",
    "Oracle",
    "Patch",
    "PatchOp",
    "Violation",
]
