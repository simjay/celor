"""Tests for core synthesis primitives."""

import pytest

from celor.core.synth import CandidateGenerator, Constraint


class TestConstraint:
    """Tests for Constraint dataclass."""

    def test_forbidden_value_constraint(self):
        """Test forbidden_value constraint creation."""
        c = Constraint("forbidden_value", {"hole": "profile", "value": "small"})
        
        assert c.type == "forbidden_value"
        assert c.data["hole"] == "profile"
        assert c.data["value"] == "small"

    def test_forbidden_tuple_constraint(self):
        """Test forbidden_tuple constraint creation."""
        c = Constraint("forbidden_tuple", {
            "holes": ["env", "replicas"],
            "values": ["prod", 2]
        })
        
        assert c.type == "forbidden_tuple"
        assert c.data["holes"] == ["env", "replicas"]
        assert c.data["values"] == ["prod", 2]

    def test_constraint_serialization(self):
        """Test constraint serialization roundtrip."""
        c1 = Constraint("forbidden_value", {"hole": "x", "value": 42})
        
        # Serialize
        d = c1.to_dict()
        assert d["type"] == "forbidden_value"
        assert d["data"]["hole"] == "x"
        
        # Deserialize
        c2 = Constraint.from_dict(d)
        assert c2.type == c1.type
        assert c2.data == c1.data

    def test_constraint_repr(self):
        """Test human-readable representation."""
        c1 = Constraint("forbidden_value", {"hole": "env", "value": "staging"})
        assert "env=staging" in repr(c1)
        
        c2 = Constraint("forbidden_tuple", {
            "holes": ["env", "replicas"],
            "values": ["prod", 2]
        })
        assert "env=prod" in repr(c2)
        assert "replicas=2" in repr(c2)


class TestCandidateGenerator:
    """Tests for CandidateGenerator."""

    def test_simple_enumeration_2x2(self):
        """Test enumeration of simple 2×2 hole space."""
        hole_space = {
            "env": {"dev", "prod"},
            "replicas": {2, 3}
        }
        gen = CandidateGenerator(hole_space, [])
        
        candidates = list(gen)
        
        # Should generate all 4 combinations
        assert len(candidates) == 4
        
        # Check all combinations present
        assert {"env": "dev", "replicas": 2} in candidates
        assert {"env": "dev", "replicas": 3} in candidates
        assert {"env": "prod", "replicas": 2} in candidates
        assert {"env": "prod", "replicas": 3} in candidates

    def test_forbidden_value_constraint(self):
        """Test that forbidden_value constraint skips values."""
        hole_space = {
            "env": {"dev", "prod"},
            "replicas": {2, 3}
        }
        constraints = [
            Constraint("forbidden_value", {"hole": "env", "value": "dev"})
        ]
        gen = CandidateGenerator(hole_space, constraints)
        
        candidates = list(gen)
        
        # Should skip all candidates with env=dev
        assert len(candidates) == 2
        for c in candidates:
            assert c["env"] == "prod"

    def test_forbidden_tuple_constraint(self):
        """Test that forbidden_tuple constraint skips specific combinations."""
        hole_space = {
            "env": {"dev", "prod"},
            "replicas": {2, 3}
        }
        constraints = [
            Constraint("forbidden_tuple", {
                "holes": ["env", "replicas"],
                "values": ["prod", 2]
            })
        ]
        gen = CandidateGenerator(hole_space, constraints)
        
        candidates = list(gen)
        
        # Should skip env=prod, replicas=2
        assert len(candidates) == 3
        assert {"env": "prod", "replicas": 2} not in candidates
        assert {"env": "prod", "replicas": 3} in candidates

    def test_multiple_constraints(self):
        """Test multiple constraints together."""
        hole_space = {
            "x": {1, 2, 3},
            "y": {"a", "b"}
        }
        constraints = [
            Constraint("forbidden_value", {"hole": "x", "value": 1}),
            Constraint("forbidden_tuple", {"holes": ["x", "y"], "values": [3, "a"]})
        ]
        gen = CandidateGenerator(hole_space, constraints)
        
        candidates = list(gen)
        
        # Should have 6 total - 2 forbidden (x=1 for both y values) - 1 forbidden (x=3,y=a)
        # = 3 valid
        assert len(candidates) == 3
        
        # Check none violate constraints
        for c in candidates:
            assert c["x"] != 1
            assert not (c["x"] == 3 and c["y"] == "a")

    def test_update_constraints_restarts(self):
        """Test that update_constraints() restarts enumeration."""
        hole_space = {"x": {1, 2}}
        
        gen = CandidateGenerator(hole_space, [])
        first_candidate = next(gen)
        
        # Update constraints (should restart)
        gen.update_constraints([
            Constraint("forbidden_value", {"hole": "x", "value": first_candidate["x"]})
        ])
        
        # Should generate remaining candidates
        remaining = list(gen)
        assert len(remaining) == 1
        assert remaining[0]["x"] != first_candidate["x"]

    def test_empty_hole_space(self):
        """Test behavior with empty hole space."""
        hole_space = {}
        gen = CandidateGenerator(hole_space, [])
        
        candidates = list(gen)
        
        assert len(candidates) == 0

    def test_single_hole(self):
        """Test with single hole."""
        hole_space = {"env": {"dev", "prod", "staging"}}
        gen = CandidateGenerator(hole_space, [])
        
        candidates = list(gen)
        
        assert len(candidates) == 3
        envs = {c["env"] for c in candidates}
        assert envs == {"dev", "prod", "staging"}

    def test_estimate_size(self):
        """Test size estimation."""
        hole_space = {
            "a": {1, 2, 3},
            "b": {"x", "y"},
            "c": {True, False}
        }
        gen = CandidateGenerator(hole_space, [])
        
        # Should be 3 × 2 × 2 = 12
        assert gen.estimate_size() == 12
        
        # Verify by enumeration
        candidates = list(gen)
        assert len(candidates) == 12

    def test_large_hole_space_performance(self):
        """Test that large hole space can be enumerated efficiently."""
        # Create hole space with ~1000 candidates
        hole_space = {
            "a": set(range(10)),
            "b": set(range(10)),
            "c": set(range(10))
        }
        gen = CandidateGenerator(hole_space, [])
        
        assert gen.estimate_size() == 1000
        
        # Should be able to enumerate quickly
        count = 0
        for _ in gen:
            count += 1
            if count > 1010:  # Safety check
                break
        
        assert count == 1000

    def test_constraint_pruning_efficiency(self):
        """Test that constraints reduce enumeration."""
        hole_space = {
            "x": set(range(5)),
            "y": set(range(5))
        }
        
        # Without constraints: 25 candidates
        gen1 = CandidateGenerator(hole_space, [])
        assert len(list(gen1)) == 25
        
        # With constraint forbidding x=0: 20 candidates (5 pruned)
        constraints = [
            Constraint("forbidden_value", {"hole": "x", "value": 0})
        ]
        gen2 = CandidateGenerator(hole_space, constraints)
        candidates = list(gen2)
        assert len(candidates) == 20
        
        # Verify constraint respected
        for c in candidates:
            assert c["x"] != 0


class TestCandidateGeneratorEdgeCases:
    """Edge case tests for CandidateGenerator."""

    def test_all_candidates_forbidden(self):
        """Test when all candidates are forbidden."""
        hole_space = {"x": {1, 2}}
        constraints = [
            Constraint("forbidden_value", {"hole": "x", "value": 1}),
            Constraint("forbidden_value", {"hole": "x", "value": 2})
        ]
        gen = CandidateGenerator(hole_space, constraints)
        
        candidates = list(gen)
        
        assert len(candidates) == 0

    def test_deterministic_order(self):
        """Test that enumeration order is deterministic."""
        hole_space = {"x": {3, 1, 2}, "y": {"b", "a"}}
        
        gen1 = CandidateGenerator(hole_space, [])
        candidates1 = list(gen1)
        
        gen2 = CandidateGenerator(hole_space, [])
        candidates2 = list(gen2)
        
        # Should generate same order
        assert candidates1 == candidates2

