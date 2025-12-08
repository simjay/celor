"""Unit tests for the CEGIS loop controller.

Tests cover:
- Basic repair loop execution
- Success status when violations resolved
- Max iterations handling
- Constraint learning
"""

from typing import List

import pytest

from celor.core.cegis.loop import repair
from celor.core.cegis.synthesizer import SynthConfig
from celor.core.schema.artifact import Artifact
from celor.core.schema.oracle import Oracle
from celor.core.schema.patch_dsl import Patch, PatchOp
from celor.core.schema.violation import Violation
from celor.core.template import HoleRef, HoleSpace, PatchTemplate


class MockArtifact(Artifact):
    """Simple mock artifact for testing."""

    def __init__(self, value: int = 0):
        self.value = value

    def apply_patch(self, patch: Patch) -> "MockArtifact":
        """Apply patch by updating value."""
        # Simple mock: if patch has EnsureValue op, use it
        for op in patch.ops:
            if op.op == "EnsureValue" and "value" in op.args:
                return MockArtifact(value=op.args["value"])
        return self

    def materialize(self, path: str) -> None:
        """Mock materialization."""
        pass


def passing_oracle(artifact: Artifact) -> List[Violation]:
    """Oracle that always passes."""
    return []


def failing_oracle(artifact: Artifact) -> List[Violation]:
    """Oracle that returns a violation if value < 3."""
    if isinstance(artifact, MockArtifact) and artifact.value < 3:
        return [
            Violation(
                id="test.value_too_low",
                message="Value must be >= 3",
                path=[],
                severity="error",
                evidence={"constraint_hints": {"forbid_value": [("value", 0), ("value", 1), ("value", 2)]}}
            )
        ]
    return []


def test_repair_immediate_success():
    """Test repair with no violations (immediate success)."""
    artifact = MockArtifact(value=5)  # Already valid
    template = PatchTemplate(ops=[])  # No operations needed
    hole_space: HoleSpace = {}
    oracles = [passing_oracle]

    repaired, metadata = repair(
        artifact=artifact,
        template=template,
        hole_space=hole_space,
        oracles=oracles,
        max_iters=5
    )

    assert metadata["status"] == "success"
    assert metadata["iterations"] == 0
    assert metadata["tried_candidates"] == 0


def test_repair_with_simple_patch():
    """Test repair with a simple patch that fixes violations."""
    artifact = MockArtifact(value=0)  # Invalid (too low)
    template = PatchTemplate(ops=[
        PatchOp("EnsureValue", {"value": HoleRef("value")})
    ])
    hole_space: HoleSpace = {"value": {3, 4, 5}}
    oracles = [failing_oracle]

    config = SynthConfig(max_candidates=10, timeout_seconds=5.0)
    repaired, metadata = repair(
        artifact=artifact,
        template=template,
        hole_space=hole_space,
        oracles=oracles,
        max_iters=5,
        config=config
    )

    # Should succeed
    assert metadata["status"] == "success"
    assert metadata["iterations"] >= 1
    assert metadata["tried_candidates"] > 0
    # Repaired artifact should pass oracles
    violations = failing_oracle(repaired)
    assert len(violations) == 0


def test_repair_max_iterations():
    """Test repair when max iterations reached."""
    artifact = MockArtifact(value=0)
    template = PatchTemplate(ops=[
        PatchOp("EnsureValue", {"value": HoleRef("value")})
    ])
    hole_space: HoleSpace = {"value": {0, 1, 2}}  # All invalid values
    oracles = [failing_oracle]

    config = SynthConfig(max_candidates=10, timeout_seconds=5.0)
    repaired, metadata = repair(
        artifact=artifact,
        template=template,
        hole_space=hole_space,
        oracles=oracles,
        max_iters=2,
        config=config
    )

    # Should hit max iterations or UNSAT (if all candidates exhausted)
    assert metadata["status"] in ["max_iters", "unsat"]
    # If UNSAT, might exit early, so check iterations <= max_iters
    assert metadata["iterations"] <= 2
    assert metadata["iterations"] > 0
    assert "violations" in metadata


def test_repair_constraint_learning():
    """Test that constraints are learned during repair."""
    artifact = MockArtifact(value=0)
    template = PatchTemplate(ops=[
        PatchOp("EnsureValue", {"value": HoleRef("value")})
    ])
    hole_space: HoleSpace = {"value": {0, 1, 2, 3, 4, 5}}
    oracles = [failing_oracle]

    config = SynthConfig(max_candidates=20, timeout_seconds=5.0)
    repaired, metadata = repair(
        artifact=artifact,
        template=template,
        hole_space=hole_space,
        oracles=oracles,
        max_iters=5,
        config=config
    )

    # Should have learned constraints
    assert isinstance(metadata["constraints"], list)
    # If successful, should have found valid value
    if metadata["status"] == "success":
        assert metadata["tried_candidates"] > 0
