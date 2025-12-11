"""Tests for synthesis orchestration."""

from dataclasses import dataclass
from typing import List

import pytest

from celor.core.cegis.synthesizer import (
    SynthConfig,
    SynthResult,
    extract_constraints_from_violations,
    synthesize,
)
from celor.core.schema.artifact import Artifact
from celor.core.schema.patch_dsl import Patch, PatchOp
from celor.core.schema.violation import Violation
from celor.core.synth import Constraint
from celor.core.template import HoleRef, HoleSpace, PatchTemplate


# Mock artifact for testing
@dataclass(frozen=True)
class MockArtifact(Artifact):
    """Simple mock artifact for testing."""
    data: dict
    
    def to_serializable(self):
        return self.data
    
    def apply_patch(self, patch: Patch) -> "MockArtifact":
        # Apply patch ops to data
        new_data = dict(self.data)
        for op in patch.ops:
            if op.op == "SetField":
                new_data.update(op.args)
        return MockArtifact(data=new_data)


class TestExtractConstraints:
    """Tests for extract_constraints_from_violations."""

    def test_extract_forbid_value(self):
        """Test extracting forbidden_value constraint."""
        candidate = {"x": 1}
        violations = [
            Violation(
                id="test",
                message="x=1 is forbidden",
                path=[],
                severity="error",
                evidence={"forbid_value": {"hole": "x", "value": 1}}
            )
        ]
        
        constraints = extract_constraints_from_violations(candidate, violations)
        
        assert len(constraints) == 1
        assert constraints[0].type == "forbidden_value"
        assert constraints[0].data["hole"] == "x"
        assert constraints[0].data["value"] == 1

    def test_extract_forbid_tuple(self):
        """Test extracting forbidden_tuple constraint."""
        candidate = {"env": "production-us", "replicas": 2}
        violations = [
            Violation(
                id="test",
                message="production-us + 2 replicas forbidden",
                path=[],
                severity="error",
                evidence={
                    "forbid_tuple": {
                        "holes": ["env", "replicas"],
                        "values": ["production-us", 2]
                    }
                }
            )
        ]
        
        constraints = extract_constraints_from_violations(candidate, violations)
        
        assert len(constraints) == 1
        assert constraints[0].type == "forbidden_tuple"
        assert constraints[0].data["holes"] == ["env", "replicas"]
        assert constraints[0].data["values"] == ["production-us", 2]

    def test_extract_multiple_constraints(self):
        """Test extracting multiple constraints from multiple violations."""
        candidate = {"x": 1, "y": 2}
        violations = [
            Violation(
                id="v1",
                message="x forbidden",
                path=[],
                severity="error",
                evidence={"forbid_value": {"hole": "x", "value": 1}}
            ),
            Violation(
                id="v2",
                message="tuple forbidden",
                path=[],
                severity="error",
                evidence={"forbid_tuple": {"holes": ["x", "y"], "values": [1, 2]}}
            )
        ]
        
        constraints = extract_constraints_from_violations(candidate, violations)
        
        assert len(constraints) == 2

    def test_extract_no_hints(self):
        """Test with violations that have no constraint hints."""
        candidate = {"x": 1}
        violations = [
            Violation(
                id="test",
                message="generic failure",
                path=[],
                severity="error",
                evidence={}  # No hints
            )
        ]
        
        constraints = extract_constraints_from_violations(candidate, violations)
        
        assert len(constraints) == 0


class TestSynthesize:
    """Tests for synthesize() function."""

    def test_simple_success(self):
        """Test successful synthesis with one valid candidate."""
        # Artifact that needs x=2 to pass
        artifact = MockArtifact(data={"x": 0})
        
        # Template with one hole
        template = PatchTemplate(ops=[
            PatchOp("SetField", {"x": HoleRef("x")})
        ])
        
        # Hole space with x in {1, 2}
        hole_space: HoleSpace = {"x": {1, 2}}
        
        # Oracle that only passes when x=2
        def oracle(art: Artifact) -> List[Violation]:
            if art.to_serializable().get("x") == 2:
                return []  # Pass
            return [Violation("test", "x must be 2", [], "error")]
        
        config = SynthConfig(max_candidates=10, timeout_seconds=10.0)
        result = synthesize(artifact, template, hole_space, [oracle], config)
        
        assert result.status == "success"
        assert result.patch is not None
        assert result.tried_candidates <= 2

    def test_unsat_case(self):
        """Test UNSAT when no valid candidate exists."""
        artifact = MockArtifact(data={"x": 0})
        
        template = PatchTemplate(ops=[
            PatchOp("SetField", {"x": HoleRef("x")})
        ])
        
        hole_space: HoleSpace = {"x": {1, 2}}
        
        # Oracle that never passes
        def oracle(art: Artifact) -> List[Violation]:
            return [Violation("test", "always fails", [], "error")]
        
        config = SynthConfig(max_candidates=10, timeout_seconds=10.0)
        result = synthesize(artifact, template, hole_space, [oracle], config)
        
        assert result.status == "unsat"
        assert result.patch is None
        assert result.tried_candidates == 2  # Tried both candidates

    def test_max_candidates_enforced(self):
        """Test that max_candidates budget is enforced."""
        artifact = MockArtifact(data={"x": 0})
        
        template = PatchTemplate(ops=[
            PatchOp("SetField", {"x": HoleRef("x")})
        ])
        
        # Large hole space
        hole_space: HoleSpace = {"x": set(range(100))}
        
        # Oracle that never passes
        def oracle(art: Artifact) -> List[Violation]:
            return [Violation("test", "always fails", [], "error")]
        
        config = SynthConfig(max_candidates=5, timeout_seconds=10.0)
        result = synthesize(artifact, template, hole_space, [oracle], config)
        
        assert result.status == "unsat"
        # Allow for off-by-one: might try one more before checking limit
        assert result.tried_candidates <= 6

    def test_initial_constraints_warm_start(self):
        """Test that initial_constraints are used for warm-start."""
        artifact = MockArtifact(data={"x": 0})
        
        template = PatchTemplate(ops=[
            PatchOp("SetField", {"x": HoleRef("x")})
        ])
        
        hole_space: HoleSpace = {"x": {1, 2, 3}}
        
        # Oracle that only passes when x=3
        def oracle(art: Artifact) -> List[Violation]:
            if art.to_serializable().get("x") == 3:
                return []
            return [Violation("test", "must be 3", [], "error")]
        
        # Provide initial constraints that forbid x=1
        initial_constraints = [
            Constraint("forbidden_value", {"hole": "x", "value": 1})
        ]
        
        config = SynthConfig(max_candidates=10, timeout_seconds=10.0)
        result = synthesize(
            artifact, template, hole_space, [oracle], config,
            initial_constraints=initial_constraints
        )
        
        assert result.status == "success"
        # Should have tried only 2 candidates (2 and 3), skipping 1
        assert result.tried_candidates == 2
        # Returned constraints should include initial ones
        assert len(result.constraints) >= 1

    def test_constraint_learning(self):
        """Test that constraints are learned from oracle hints."""
        artifact = MockArtifact(data={"x": 0, "y": 0})
        
        template = PatchTemplate(ops=[
            PatchOp("SetField", {"x": HoleRef("x"), "y": HoleRef("y")})
        ])
        
        hole_space: HoleSpace = {"x": {1, 2}, "y": {1, 2}}
        
        # Oracle that provides constraint hints
        def oracle(art: Artifact) -> List[Violation]:
            data = art.to_serializable()
            if data.get("x") == 2 and data.get("y") == 2:
                return []  # Only this passes
            
            # Provide hint for x=1
            if data.get("x") == 1:
                return [Violation(
                    "test", "x=1 forbidden", [], "error",
                    evidence={"forbid_value": {"hole": "x", "value": 1}}
                )]
            
            return [Violation("test", "fails", [], "error")]
        
        config = SynthConfig(max_candidates=10, timeout_seconds=10.0)
        result = synthesize(artifact, template, hole_space, [oracle], config)
        
        assert result.status == "success"
        # Should have learned constraint about x=1
        assert len(result.constraints) > 0

    def test_multiple_oracles(self):
        """Test with multiple oracles."""
        artifact = MockArtifact(data={"x": 0})
        
        template = PatchTemplate(ops=[
            PatchOp("SetField", {"x": HoleRef("x")})
        ])
        
        hole_space: HoleSpace = {"x": {1, 2, 3}}
        
        # Oracle 1: x must be >= 2
        def oracle1(art: Artifact) -> List[Violation]:
            if art.to_serializable().get("x") >= 2:
                return []
            return [Violation("o1", "x must be >= 2", [], "error")]
        
        # Oracle 2: x must be <= 2
        def oracle2(art: Artifact) -> List[Violation]:
            if art.to_serializable().get("x") <= 2:
                return []
            return [Violation("o2", "x must be <= 2", [], "error")]
        
        config = SynthConfig(max_candidates=10, timeout_seconds=10.0)
        result = synthesize(artifact, template, hole_space, [oracle1, oracle2], config)
        
        assert result.status == "success"
        # Only x=2 satisfies both oracles
        patched = artifact.apply_patch(result.patch)
        assert patched.to_serializable()["x"] == 2


class TestSynthConfig:
    """Tests for SynthConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = SynthConfig()
        
        assert config.max_candidates == 1000
        assert config.timeout_seconds == 60.0

    def test_custom_config(self):
        """Test custom configuration."""
        config = SynthConfig(max_candidates=50, timeout_seconds=5.0)
        
        assert config.max_candidates == 50
        assert config.timeout_seconds == 5.0

