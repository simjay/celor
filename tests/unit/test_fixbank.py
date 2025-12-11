"""Tests for Fix Bank implementation."""

import json
import tempfile
from pathlib import Path

import pytest

from celor.core.fixbank import (
    FixBank,
    FixEntry,
    build_signature,
    deserialize_hole_space,
    serialize_hole_space,
    signatures_match,
)
from celor.core.schema.patch_dsl import PatchOp
from celor.core.schema.violation import Violation
from celor.core.synth import Constraint
from celor.core.template import HoleRef, HoleSpace, PatchTemplate
from celor.k8s.artifact import K8sArtifact


class TestSignatureBuilding:
    """Tests for signature building and matching."""

    def test_build_signature_from_violations(self):
        """Test building signature from violations."""
        violations = [
            Violation(
                "policy.ENV_PROD_REPLICA_COUNT",
                "replicas too low",
                [],
                "error",
                evidence={"error_code": "ENV_PROD_REPLICA_COUNT"}
            ),
            Violation(
                "policy.MISSING_LABEL_TEAM",
                "team label missing",
                [],
                "error",
                evidence={"error_code": "MISSING_LABEL_TEAM"}
            ),
            Violation(
                "security.NO_RUN_AS_NON_ROOT",
                "security issue",
                [],
                "error"
            )
        ]
        
        artifact = K8sArtifact(files={"deployment.yaml": "apiVersion: apps/v1\nkind: Deployment\n"})
        signature = build_signature(artifact, violations)
        
        assert "failed_oracles" in signature
        assert set(signature["failed_oracles"]) == {"policy", "security"}
        assert "error_codes" in signature
        assert set(signature["error_codes"]) == {"ENV_PROD_REPLICA_COUNT", "MISSING_LABEL_TEAM"}

    def test_signatures_match_exact(self):
        """Test exact signature matching."""
        sig_a = {
            "failed_oracles": ["policy", "security"],
            "error_codes": ["ENV_PROD_REPLICA_COUNT"],
            "context": {"env": "production-us"}
        }
        sig_b = {
            "failed_oracles": ["policy", "security"],
            "error_codes": ["ENV_PROD_REPLICA_COUNT"],
            "context": {"env": "production-us", "app": "different"}  # Different context
        }
        
        assert signatures_match(sig_a, sig_b)  # Context is optional

    def test_signatures_dont_match_different_oracles(self):
        """Test that different oracle failures don't match."""
        sig_a = {
            "failed_oracles": ["policy"],
            "error_codes": [],
            "context": {}
        }
        sig_b = {
            "failed_oracles": ["security"],
            "error_codes": [],
            "context": {}
        }
        
        assert not signatures_match(sig_a, sig_b)

    def test_signatures_dont_match_different_errors(self):
        """Test that different error codes don't match."""
        sig_a = {
            "failed_oracles": ["policy"],
            "error_codes": ["ERROR_A"],
            "context": {}
        }
        sig_b = {
            "failed_oracles": ["policy"],
            "error_codes": ["ERROR_B"],
            "context": {}
        }
        
        assert not signatures_match(sig_a, sig_b)
    
    def test_signatures_require_container_match(self):
        """Test that signatures with different container names don't match."""
        sig_a = {
            "failed_oracles": ["policy"],
            "error_codes": ["IMAGE_NOT_FROM_ECR"],
            "context": {"container": "web"}
        }
        sig_b = {
            "failed_oracles": ["policy"],
            "error_codes": ["IMAGE_NOT_FROM_ECR"],
            "context": {"container": "api"}  # Different container
        }
        
        assert not signatures_match(sig_a, sig_b)
    
    def test_signatures_match_same_container(self):
        """Test that signatures with same container name match."""
        sig_a = {
            "failed_oracles": ["policy"],
            "error_codes": ["IMAGE_NOT_FROM_ECR"],
            "context": {"container": "web", "env": "production-us"}
        }
        sig_b = {
            "failed_oracles": ["policy"],
            "error_codes": ["IMAGE_NOT_FROM_ECR"],
            "context": {"container": "web", "env": "staging-us"}  # Different env, same container
        }
        
        assert signatures_match(sig_a, sig_b)  # Should match (same container)


class TestHoleSpaceSerialization:
    """Tests for HoleSpace serialization."""

    def test_serialize_hole_space(self):
        """Test serializing hole space to JSON-compatible format."""
        hole_space: HoleSpace = {
            "env": {"staging-us", "production-us"},
            "replicas": {2, 3, 4}
        }
        
        serialized = serialize_hole_space(hole_space)
        
        # Should be lists, not sets
        assert isinstance(serialized["env"], list)
        assert isinstance(serialized["replicas"], list)
        
        # Should be sorted for determinism
        assert serialized["env"] == ["production-us", "staging-us"]
        assert serialized["replicas"] == [2, 3, 4]

    def test_deserialize_hole_space(self):
        """Test deserializing hole space from JSON."""
        data = {
            "env": ["staging-us", "production-us"],
            "replicas": [2, 3, 4]
        }
        
        hole_space = deserialize_hole_space(data)
        
        # Should be sets
        assert isinstance(hole_space["env"], set)
        assert hole_space["env"] == {"staging-us", "production-us"}
        assert hole_space["replicas"] == {2, 3, 4}

    def test_roundtrip(self):
        """Test serialize → deserialize roundtrip."""
        original: HoleSpace = {
            "x": {1, 2, 3},
            "y": {"a", "b"}
        }
        
        serialized = serialize_hole_space(original)
        deserialized = deserialize_hole_space(serialized)
        
        assert deserialized == original


class TestFixBank:
    """Tests for FixBank class."""

    def test_empty_fixbank(self):
        """Test creating empty Fix Bank."""
        fixbank = FixBank()
        
        assert len(fixbank.entries) == 0
        
        signature = {"failed_oracles": ["policy"], "error_codes": [], "context": {}}
        assert fixbank.lookup(signature) is None

    def test_add_and_lookup(self):
        """Test adding and looking up entries."""
        fixbank = FixBank()
        
        template = PatchTemplate(ops=[
            PatchOp("EnsureReplicas", {"replicas": HoleRef("replicas")})
        ])
        hole_space: HoleSpace = {"replicas": {3, 4, 5}}
        signature = {"failed_oracles": ["policy"], "error_codes": ["REPLICA_COUNT"], "context": {}}
        
        entry = FixEntry(
            signature=signature,
            template=template,
            hole_space=hole_space,
            learned_constraints=[],
            successful_assignment={"replicas": 3}
        )
        
        fixbank.add(entry)
        
        # Should be able to look up
        found = fixbank.lookup(signature)
        assert found is not None
        assert found.signature == signature

    def test_duplicate_signature_updates(self):
        """Test that adding duplicate signature updates existing entry."""
        fixbank = FixBank()
        
        template = PatchTemplate(ops=[PatchOp("EnsureReplicas", {"replicas": HoleRef("r")})])
        hole_space: HoleSpace = {"r": {3}}
        signature = {"failed_oracles": ["policy"], "error_codes": [], "context": {}}
        
        # Add first entry
        entry1 = FixEntry(
            signature=signature,
            template=template,
            hole_space=hole_space
        )
        fixbank.add(entry1)
        
        assert len(fixbank.entries) == 1
        assert fixbank.entries[0].metadata["success_count"] == 1
        
        # Add same signature again
        entry2 = FixEntry(
            signature=signature,
            template=template,
            hole_space=hole_space
        )
        fixbank.add(entry2)
        
        # Should still be 1 entry, but updated
        assert len(fixbank.entries) == 1
        assert fixbank.entries[0].metadata["success_count"] == 2

    def test_save_and_load(self):
        """Test saving to and loading from JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # Create and save
            fixbank = FixBank(temp_path)
            
            template = PatchTemplate(ops=[
                PatchOp("EnsureLabel", {"key": "env", "value": HoleRef("env")})
            ])
            hole_space: HoleSpace = {"env": {"production-us", "staging-us"}}
            constraints = [
                Constraint("forbidden_value", {"hole": "env", "value": "dev-us"})
            ]
            
            entry = FixEntry(
                signature={"failed_oracles": ["policy"], "error_codes": [], "context": {}},
                template=template,
                hole_space=hole_space,
                learned_constraints=constraints,
                successful_assignment={"env": "production-us"}
            )
            
            fixbank.add(entry)
            
            # Load in new instance
            fixbank2 = FixBank(temp_path)
            
            assert len(fixbank2.entries) == 1
            loaded_entry = fixbank2.entries[0]
            
            # Verify fields preserved
            assert loaded_entry.signature == entry.signature
            assert len(loaded_entry.template.ops) == 1
            assert "env" in loaded_entry.hole_space
            assert len(loaded_entry.learned_constraints) == 1
            assert loaded_entry.successful_assignment == {"env": "production-us"}
            
        finally:
            Path(temp_path).unlink()

    def test_json_is_pretty_printed(self):
        """Test that saved JSON is git-friendly."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            fixbank = FixBank(temp_path)
            
            entry = FixEntry(
                signature={"failed_oracles": ["policy"], "error_codes": [], "context": {}},
                template=PatchTemplate(ops=[]),
                hole_space={}
            )
            fixbank.add(entry)
            
            # Read raw JSON
            content = Path(temp_path).read_text()
            
            # Should be indented
            assert "  " in content  # Has indentation
            assert "\n" in content  # Has newlines
            
            # Should be valid JSON
            data = json.loads(content)
            assert "version" in data
            assert "entries" in data
            
        finally:
            Path(temp_path).unlink()


class TestConstraintMerging:
    """Tests for constraint merging when updating entries."""

    def test_new_constraints_are_merged(self):
        """Test that newly learned constraints are added to existing entry."""
        fixbank = FixBank()
        
        template = PatchTemplate(ops=[])
        hole_space: HoleSpace = {"x": {1, 2}}
        signature = {"failed_oracles": ["policy"], "error_codes": [], "context": {}}
        
        # First entry with 1 constraint
        entry1 = FixEntry(
            signature=signature,
            template=template,
            hole_space=hole_space,
            learned_constraints=[
                Constraint("forbidden_value", {"hole": "x", "value": 1})
            ]
        )
        fixbank.add(entry1)
        
        # Second entry with different constraint
        entry2 = FixEntry(
            signature=signature,
            template=template,
            hole_space=hole_space,
            learned_constraints=[
                Constraint("forbidden_value", {"hole": "x", "value": 2})
            ]
        )
        fixbank.add(entry2)
        
        # Should have merged constraints
        assert len(fixbank.entries) == 1
        assert len(fixbank.entries[0].learned_constraints) == 2

