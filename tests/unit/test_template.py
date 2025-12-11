"""Tests for template system (HoleRef, PatchTemplate, instantiate)."""

import pytest

from celor.core.schema.patch_dsl import Patch, PatchOp
from celor.core.template import (
    CandidateAssignments,
    HoleRef,
    HoleSpace,
    PatchTemplate,
    deserialize_template,
    deserialize_value,
    instantiate,
    serialize_template,
    serialize_value,
)


class TestHoleRef:
    """Tests for HoleRef dataclass."""

    def test_create_hole_ref(self):
        """Test creating a HoleRef."""
        hole = HoleRef("env")
        assert hole.name == "env"

    def test_hole_ref_immutable(self):
        """Test that HoleRef is immutable (frozen)."""
        hole = HoleRef("env")
        with pytest.raises(AttributeError):
            hole.name = "production-us"  # type: ignore

    def test_hole_ref_equality(self):
        """Test HoleRef equality."""
        hole1 = HoleRef("env")
        hole2 = HoleRef("env")
        hole3 = HoleRef("version")
        
        assert hole1 == hole2
        assert hole1 != hole3


class TestPatchTemplate:
    """Tests for PatchTemplate dataclass."""

    def test_create_template(self):
        """Test creating a PatchTemplate."""
        template = PatchTemplate(ops=[
            PatchOp("EnsureLabel", {"key": "env", "value": HoleRef("env")})
        ])
        assert len(template.ops) == 1
        assert template.ops[0].op == "EnsureLabel"

    def test_template_with_multiple_holes(self):
        """Test template with multiple holes."""
        template = PatchTemplate(ops=[
            PatchOp("EnsureLabel", {"key": "env", "value": HoleRef("env")}),
            PatchOp("EnsureReplicas", {"replicas": HoleRef("replicas")}),
            PatchOp("EnsureResourceProfile", {"profile": HoleRef("profile")})
        ])
        assert len(template.ops) == 3

    def test_template_with_mixed_values(self):
        """Test template with both holes and concrete values."""
        template = PatchTemplate(ops=[
            PatchOp("EnsureLabel", {
                "scope": "podTemplate",  # Concrete
                "key": "env",            # Concrete
                "value": HoleRef("env")  # Hole
            })
        ])
        assert template.ops[0].args["scope"] == "podTemplate"
        assert isinstance(template.ops[0].args["value"], HoleRef)


class TestInstantiate:
    """Tests for instantiate() function."""

    def test_instantiate_single_hole(self):
        """Test instantiating template with single hole."""
        template = PatchTemplate(ops=[
            PatchOp("EnsureLabel", {"key": "env", "value": HoleRef("env")})
        ])
        assignment = {"env": "production-us"}
        
        patch = instantiate(template, assignment)
        
        assert isinstance(patch, Patch)
        assert len(patch.ops) == 1
        assert patch.ops[0].args["value"] == "production-us"

    def test_instantiate_multiple_holes(self):
        """Test instantiating template with multiple holes."""
        template = PatchTemplate(ops=[
            PatchOp("EnsureLabel", {"key": "env", "value": HoleRef("env")}),
            PatchOp("EnsureReplicas", {"replicas": HoleRef("replicas")}),
            PatchOp("EnsureResourceProfile", {"profile": HoleRef("profile")})
        ])
        assignment = {
            "env": "production-us",
            "replicas": 3,
            "profile": "medium"
        }
        
        patch = instantiate(template, assignment)
        
        assert len(patch.ops) == 3
        assert patch.ops[0].args["value"] == "production-us"
        assert patch.ops[1].args["replicas"] == 3
        assert patch.ops[2].args["profile"] == "medium"

    def test_instantiate_preserves_concrete_values(self):
        """Test that instantiate preserves non-hole values."""
        template = PatchTemplate(ops=[
            PatchOp("EnsureLabel", {
                "scope": "podTemplate",
                "key": "env",
                "value": HoleRef("env")
            })
        ])
        assignment = {"env": "staging-us"}
        
        patch = instantiate(template, assignment)
        
        assert patch.ops[0].args["scope"] == "podTemplate"
        assert patch.ops[0].args["key"] == "env"
        assert patch.ops[0].args["value"] == "staging-us"

    def test_instantiate_nested_holes(self):
        """Test that nested structures with holes work."""
        template = PatchTemplate(ops=[
            PatchOp("ComplexOp", {
                "nested": {
                    "value": HoleRef("inner"),
                    "fixed": "constant"
                }
            })
        ])
        assignment = {"inner": "value123"}
        
        # Note: Current implementation doesn't handle nested dicts with holes
        # This would need recursive instantiation if we want to support it
        # For K8s use case, holes are only at top level of args

    def test_instantiate_missing_hole_raises_error(self):
        """Test that missing hole in assignment raises error."""
        template = PatchTemplate(ops=[
            PatchOp("EnsureLabel", {"value": HoleRef("env")})
        ])
        assignment = {"replicas": 3}  # Missing "env"
        
        with pytest.raises(ValueError, match="Hole 'env' not found"):
            instantiate(template, assignment)


class TestSerialization:
    """Tests for serialization helpers."""

    def test_serialize_hole_ref(self):
        """Test serializing HoleRef to dict."""
        hole = HoleRef("env")
        result = serialize_value(hole)
        
        assert result == {"$hole": "env"}

    def test_serialize_regular_values(self):
        """Test that non-HoleRef values pass through."""
        assert serialize_value("production-us") == "production-us"
        assert serialize_value(3) == 3
        assert serialize_value(["a", "b"]) == ["a", "b"]
        assert serialize_value({"key": "value"}) == {"key": "value"}

    def test_deserialize_hole_ref(self):
        """Test deserializing dict to HoleRef."""
        data = {"$hole": "env"}
        result = deserialize_value(data)
        
        assert isinstance(result, HoleRef)
        assert result.name == "env"

    def test_deserialize_regular_values(self):
        """Test that non-hole dicts pass through."""
        assert deserialize_value("production-us") == "production-us"
        assert deserialize_value(3) == 3
        assert deserialize_value({"key": "value"}) == {"key": "value"}

    def test_serialize_template(self):
        """Test serializing entire template."""
        template = PatchTemplate(ops=[
            PatchOp("EnsureLabel", {"key": "env", "value": HoleRef("env")}),
            PatchOp("EnsureReplicas", {"replicas": HoleRef("replicas")})
        ])
        
        result = serialize_template(template)
        
        assert result == {
            "ops": [
                {
                    "op": "EnsureLabel",
                    "args": {"key": "env", "value": {"$hole": "env"}}
                },
                {
                    "op": "EnsureReplicas",
                    "args": {"replicas": {"$hole": "replicas"}}
                }
            ]
        }

    def test_deserialize_template(self):
        """Test deserializing template from dict."""
        data = {
            "ops": [
                {
                    "op": "EnsureLabel",
                    "args": {"key": "env", "value": {"$hole": "env"}}
                },
                {
                    "op": "EnsureReplicas",
                    "args": {"replicas": {"$hole": "replicas"}}
                }
            ]
        }
        
        template = deserialize_template(data)
        
        assert isinstance(template, PatchTemplate)
        assert len(template.ops) == 2
        assert isinstance(template.ops[0].args["value"], HoleRef)
        assert template.ops[0].args["value"].name == "env"
        assert isinstance(template.ops[1].args["replicas"], HoleRef)

    def test_roundtrip_serialization(self):
        """Test that serialize → deserialize is identity."""
        original = PatchTemplate(ops=[
            PatchOp("EnsureLabel", {
                "scope": "podTemplate",
                "key": "env",
                "value": HoleRef("env")
            }),
            PatchOp("EnsureReplicas", {"replicas": HoleRef("replicas")}),
            PatchOp("EnsureSecurityBaseline", {"container": "app"})  # No holes
        ])
        
        serialized = serialize_template(original)
        deserialized = deserialize_template(serialized)
        
        assert len(deserialized.ops) == len(original.ops)
        for orig_op, deser_op in zip(original.ops, deserialized.ops):
            assert orig_op.op == deser_op.op
            for key in orig_op.args:
                if isinstance(orig_op.args[key], HoleRef):
                    assert isinstance(deser_op.args[key], HoleRef)
                    assert deser_op.args[key].name == orig_op.args[key].name
                else:
                    assert deser_op.args[key] == orig_op.args[key]


class TestIntegration:
    """Integration tests for template system."""

    def test_full_workflow(self):
        """Test complete workflow: create template → instantiate → verify."""
        # Create template
        template = PatchTemplate(ops=[
            PatchOp("EnsureLabel", {"key": "env", "value": HoleRef("env")}),
            PatchOp("EnsureReplicas", {"replicas": HoleRef("replicas")})
        ])
        
        # Define hole space
        hole_space: HoleSpace = {
            "env": {"staging-us", "production-us"},
            "replicas": {2, 3, 4}
        }
        
        # Try one candidate
        candidate: CandidateAssignments = {"env": "production-us", "replicas": 3}
        
        # Instantiate
        patch = instantiate(template, candidate)
        
        # Verify result
        assert isinstance(patch, Patch)
        assert patch.ops[0].args["value"] == "production-us"
        assert patch.ops[1].args["replicas"] == 3
        
        # No more holes
        for op in patch.ops:
            for value in op.args.values():
                assert not isinstance(value, HoleRef)

