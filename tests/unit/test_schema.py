"""Unit tests for core schema definitions.

Tests cover:
- Artifact protocol compliance (Requirement 1.1)
- Violation serialization (Requirement 1.2)
- Patch/PatchOp construction (Requirement 1.3, 1.4)
- Oracle interface (Requirement 1.5)
"""

from typing import Any, List

import pytest

from celor.core.schema.artifact import Artifact, to_serializable
from celor.core.schema.oracle import Oracle
from celor.core.schema.patch_dsl import Patch, PatchOp
from celor.core.schema.violation import Violation, ViolationEvidence

# ============================================================================
# Test Fixtures and Mock Implementations
# ============================================================================


class MockArtifact:
    """Mock artifact implementing the Artifact protocol."""

    def __init__(self, content: str = "test content"):
        self.content = content

    def to_serializable(self) -> dict:
        """Convert to JSON-serializable format."""
        return {"content": self.content, "type": "mock"}


class NonSerializableArtifact:
    """Mock artifact that doesn't implement Artifact protocol."""

    def __init__(self, data: str = "data"):
        self.data = data


def mock_oracle_passing(artifact: Any) -> List[Violation]:
    """Mock oracle that always passes."""
    return []


def mock_oracle_failing(artifact: Any) -> List[Violation]:
    """Mock oracle that returns violations."""
    return [
        Violation(id="test_violation", message="Test failed", path=["file.py", "func", "line:10"])
    ]


# ============================================================================
# Tests for Artifact Protocol (Requirement 1.1)
# ============================================================================


class TestArtifactProtocol:
    """Tests for Artifact protocol compliance."""

    def test_artifact_to_serializable_returns_dict(self):
        """Test that to_serializable returns JSON-serializable data."""
        artifact = MockArtifact("test content")
        result = artifact.to_serializable()

        assert isinstance(result, dict)
        assert result["content"] == "test content"
        assert result["type"] == "mock"

    def test_artifact_protocol_compliance(self):
        """Test that MockArtifact complies with Artifact protocol."""
        artifact = MockArtifact()

        # Should be usable as Artifact type
        def process_artifact(art: Artifact) -> dict:
            return art.to_serializable()

        result = process_artifact(artifact)
        assert isinstance(result, dict)

    def test_to_serializable_helper_with_artifact(self):
        """Test to_serializable helper with Artifact protocol object."""
        artifact = MockArtifact("helper test")
        result = to_serializable(artifact)

        assert isinstance(result, dict)
        assert result["content"] == "helper test"

    def test_to_serializable_helper_without_protocol(self):
        """Test to_serializable helper with non-Artifact object."""
        obj = NonSerializableArtifact("raw data")
        result = to_serializable(obj)

        # Should return object as-is
        assert result is obj
        assert result.data == "raw data"

    def test_to_serializable_helper_with_primitives(self):
        """Test to_serializable helper with primitive types."""
        assert to_serializable("string") == "string"
        assert to_serializable(42) == 42
        assert to_serializable(3.14) == 3.14
        assert to_serializable(True) is True
        assert to_serializable(None) is None

    def test_to_serializable_helper_with_collections(self):
        """Test to_serializable helper with collections."""
        assert to_serializable([1, 2, 3]) == [1, 2, 3]
        assert to_serializable({"key": "value"}) == {"key": "value"}
        assert to_serializable((1, 2)) == (1, 2)


# ============================================================================
# Tests for Violation Model (Requirement 1.2)
# ============================================================================


class TestViolation:
    """Tests for Violation dataclass."""

    def test_violation_creation_minimal(self):
        """Test creating violation with minimal required fields."""
        violation = Violation(id="test_id", message="Test message", path=["file.py"])

        assert violation.id == "test_id"
        assert violation.message == "Test message"
        assert violation.path == ["file.py"]
        assert violation.severity == "error"  # Default
        assert violation.evidence is None  # Default

    def test_violation_creation_complete(self):
        """Test creating violation with all fields."""
        evidence = {"input": 1, "expected": 2, "actual": 1}
        violation = Violation(
            id="test_violation",
            message="Test failed",
            path=["file.py", "func", "line:10"],
            severity="warning",
            evidence=evidence,
        )

        assert violation.id == "test_violation"
        assert violation.message == "Test failed"
        assert violation.path == ["file.py", "func", "line:10"]
        assert violation.severity == "warning"
        assert violation.evidence == evidence

    def test_violation_default_severity(self):
        """Test that default severity is 'error'."""
        violation = Violation(id="v1", message="msg", path=["path"])

        assert violation.severity == "error"

    def test_violation_default_evidence(self):
        """Test that default evidence is None."""
        violation = Violation(id="v1", message="msg", path=["path"])

        assert violation.evidence is None

    def test_violation_severity_levels(self):
        """Test different severity levels."""
        v_error = Violation(id="1", message="m", path=["p"], severity="error")
        v_warning = Violation(id="2", message="m", path=["p"], severity="warning")
        v_info = Violation(id="3", message="m", path=["p"], severity="info")

        assert v_error.severity == "error"
        assert v_warning.severity == "warning"
        assert v_info.severity == "info"

    def test_violation_path_structure(self):
        """Test violation path as list of strings."""
        violation = Violation(
            id="v1", message="msg", path=["module.py", "ClassName", "method_name", "line:42"]
        )

        assert len(violation.path) == 4
        assert violation.path[0] == "module.py"
        assert violation.path[1] == "ClassName"
        assert violation.path[2] == "method_name"
        assert violation.path[3] == "line:42"

    def test_violation_evidence_dict(self):
        """Test violation with dictionary evidence (backward compatibility)."""
        evidence = {"inputs": [10, 20], "expected": 30, "actual": 25, "locals": {"x": 10, "y": 20}}
        violation = Violation(id="v1", message="msg", path=["p"], evidence=evidence)

        # Should work with dict access (backward compatibility)
        assert violation.evidence["inputs"] == [10, 20]
        assert violation.evidence["expected"] == 30
        assert violation.evidence["actual"] == 25
        assert violation.evidence["locals"]["x"] == 10

        # Should also work with get_evidence() for standardized access
        std_evidence = violation.get_evidence()
        assert std_evidence.inputs == [10, 20]
        assert std_evidence.expected == 30
        assert std_evidence.actual == 25
        assert std_evidence.locals_snapshot["x"] == 10

    def test_violation_evidence_arbitrary_type(self):
        """Test violation with arbitrary evidence type."""
        # Evidence can be any type
        violation1 = Violation(id="1", message="m", path=["p"], evidence="string")
        violation2 = Violation(id="2", message="m", path=["p"], evidence=[1, 2, 3])
        violation3 = Violation(id="3", message="m", path=["p"], evidence=42)

        assert violation1.evidence == "string"
        assert violation2.evidence == [1, 2, 3]
        assert violation3.evidence == 42

    def test_violation_is_dataclass(self):
        """Test that Violation is a dataclass."""
        from dataclasses import is_dataclass

        assert is_dataclass(Violation)

    def test_violation_equality(self):
        """Test violation equality comparison."""
        v1 = Violation(id="1", message="m", path=["p"])
        v2 = Violation(id="1", message="m", path=["p"])
        v3 = Violation(id="2", message="m", path=["p"])

        assert v1 == v2
        assert v1 != v3


# ============================================================================
# Tests for ViolationEvidence (Task H5)
# ============================================================================


class TestViolationEvidence:
    """Tests for ViolationEvidence dataclass."""

    def test_violation_evidence_creation(self):
        """Test creating ViolationEvidence with all fields."""
        evidence = ViolationEvidence(
            inputs=[10, 20],
            expected=30,
            actual=25,
            file="test.py",
            lineno=15,
            func="test_func",
            locals_snapshot={"x": 10, "y": 20},
            executed_lines={10, 11, 12, 15},
            exception_type="AssertionError",
            exception_message="assert 25 == 30",
        )

        assert evidence.inputs == [10, 20]
        assert evidence.expected == 30
        assert evidence.actual == 25
        assert evidence.file == "test.py"
        assert evidence.lineno == 15
        assert evidence.func == "test_func"
        assert evidence.locals_snapshot == {"x": 10, "y": 20}
        assert evidence.executed_lines == {10, 11, 12, 15}
        assert evidence.exception_type == "AssertionError"
        assert evidence.exception_message == "assert 25 == 30"

    def test_violation_evidence_locals_sync(self):
        """Test that locals and locals_snapshot are synchronized."""
        # Test locals_snapshot sets locals
        evidence1 = ViolationEvidence(locals_snapshot={"a": 1})
        assert evidence1.locals == {"a": 1}
        assert evidence1.locals_snapshot == {"a": 1}

        # Test locals sets locals_snapshot
        evidence2 = ViolationEvidence(locals={"b": 2})
        assert evidence2.locals == {"b": 2}
        assert evidence2.locals_snapshot == {"b": 2}

    def test_violation_evidence_to_dict(self):
        """Test converting ViolationEvidence to dictionary."""
        evidence = ViolationEvidence(
            inputs=[1, 2], expected=3, file="test.py", lineno=10, locals_snapshot={"x": 1}
        )

        evidence_dict = evidence.to_dict()

        assert evidence_dict["inputs"] == [1, 2]
        assert evidence_dict["expected"] == 3
        assert evidence_dict["file"] == "test.py"
        assert evidence_dict["lineno"] == 10
        assert evidence_dict["locals"] == {"x": 1}
        assert evidence_dict["locals_snapshot"] == {"x": 1}
        # None values should not be in dict
        assert "actual" not in evidence_dict
        assert "func" not in evidence_dict

    def test_violation_get_evidence_from_dict(self):
        """Test get_evidence() converts dict to ViolationEvidence."""
        violation = Violation(
            id="v1",
            message="msg",
            path=["p"],
            evidence={
                "inputs": [10, 20],
                "expected": 30,
                "file": "test.py",
                "lineno": 15,
                "locals": {"x": 10},
            },
        )

        evidence = violation.get_evidence()
        assert isinstance(evidence, ViolationEvidence)
        assert evidence.inputs == [10, 20]
        assert evidence.expected == 30
        assert evidence.file == "test.py"
        assert evidence.lineno == 15
        assert evidence.locals_snapshot == {"x": 10}
        assert evidence.locals == {"x": 10}  # Should be synced

    def test_violation_get_evidence_from_violation_evidence(self):
        """Test get_evidence() returns ViolationEvidence as-is."""
        evidence_obj = ViolationEvidence(inputs=[1, 2], expected=3)
        violation = Violation(id="v1", message="msg", path=["p"], evidence=evidence_obj)

        evidence = violation.get_evidence()
        assert evidence is evidence_obj  # Should return same object
        assert isinstance(evidence, ViolationEvidence)

    def test_violation_get_evidence_none(self):
        """Test get_evidence() with no evidence returns empty ViolationEvidence."""
        violation = Violation(id="v1", message="msg", path=["p"], evidence=None)

        evidence = violation.get_evidence()
        assert isinstance(evidence, ViolationEvidence)
        assert evidence.inputs is None
        assert evidence.expected is None
        assert evidence.file is None


# ============================================================================
# Tests for PatchOp (Requirement 1.4)
# ============================================================================


class TestPatchOp:
    """Tests for PatchOp dataclass."""

    def test_patchop_creation(self):
        """Test creating a PatchOp."""
        op = PatchOp(op="replace_function_body", args={"name": "f", "body": "return x"})

        assert op.op == "replace_function_body"
        assert op.args["name"] == "f"
        assert op.args["body"] == "return x"

    def test_patchop_empty_args(self):
        """Test PatchOp with empty args."""
        op = PatchOp(op="format_black", args={})

        assert op.op == "format_black"
        assert op.args == {}

    def test_patchop_complex_args(self):
        """Test PatchOp with complex args."""
        args = {"span": (120, 135), "hole_id": "H1", "metadata": {"type": "expr", "depth": 2}}
        op = PatchOp(op="replace_span_with_hole", args=args)

        assert op.args["span"] == (120, 135)
        assert op.args["hole_id"] == "H1"
        assert op.args["metadata"]["depth"] == 2

    def test_patchop_is_dataclass(self):
        """Test that PatchOp is a dataclass."""
        from dataclasses import is_dataclass

        assert is_dataclass(PatchOp)

    def test_patchop_equality(self):
        """Test PatchOp equality."""
        op1 = PatchOp(op="test", args={"a": 1})
        op2 = PatchOp(op="test", args={"a": 1})
        op3 = PatchOp(op="test", args={"a": 2})

        assert op1 == op2
        assert op1 != op3


# ============================================================================
# Tests for Patch (Requirement 1.3)
# ============================================================================


class TestPatch:
    """Tests for Patch dataclass."""

    def test_patch_creation_minimal(self):
        """Test creating patch with minimal fields."""
        ops = [PatchOp(op="replace_function_body", args={"name": "f", "body": "return x"})]
        patch = Patch(ops=ops)

        assert len(patch.ops) == 1
        assert patch.ops[0].op == "replace_function_body"
        assert patch.holes is None
        assert patch.meta is None

    def test_patch_creation_complete(self):
        """Test creating patch with all fields."""
        ops = [
            PatchOp(op="replace_span_with_hole", args={"span": (10, 20), "hole_id": "H1"}),
            PatchOp(op="format_black", args={}),
        ]
        holes = [{"hole_id": "H1", "allowed_symbols": ["a", "b"], "type_hint": "int"}]
        meta = {"artifact": "utils.py", "version": "2.0.0"}

        patch = Patch(ops=ops, holes=holes, meta=meta)

        assert len(patch.ops) == 2
        assert len(patch.holes) == 1
        assert patch.holes[0]["hole_id"] == "H1"
        assert patch.meta["artifact"] == "utils.py"
        assert patch.meta["version"] == "2.0.0"

    def test_patch_empty_ops(self):
        """Test patch with empty ops list."""
        patch = Patch(ops=[])

        assert patch.ops == []
        assert len(patch.ops) == 0

    def test_patch_multiple_ops(self):
        """Test patch with multiple operations."""
        ops = [
            PatchOp(op="op1", args={"a": 1}),
            PatchOp(op="op2", args={"b": 2}),
            PatchOp(op="op3", args={"c": 3}),
        ]
        patch = Patch(ops=ops)

        assert len(patch.ops) == 3
        assert patch.ops[0].op == "op1"
        assert patch.ops[1].op == "op2"
        assert patch.ops[2].op == "op3"

    def test_patch_holes_metadata(self):
        """Test patch with hole metadata."""
        holes = [
            {
                "hole_id": "H1",
                "file": "utils.py",
                "lineno": 15,
                "span": (120, 135),
                "allowed_symbols": ["a", "b", "c", "d"],
                "type_hint": "float",
            },
            {
                "hole_id": "H2",
                "file": "utils.py",
                "lineno": 20,
                "span": (200, 210),
                "allowed_symbols": ["x", "y"],
                "type_hint": "int",
            },
        ]
        patch = Patch(ops=[], holes=holes)

        assert len(patch.holes) == 2
        assert patch.holes[0]["hole_id"] == "H1"
        assert patch.holes[0]["allowed_symbols"] == ["a", "b", "c", "d"]
        assert patch.holes[1]["hole_id"] == "H2"
        assert patch.holes[1]["type_hint"] == "int"

    def test_patch_meta_arbitrary_data(self):
        """Test patch with arbitrary metadata."""
        meta = {
            "artifact": "module.py",
            "version": "2.0.0",
            "timestamp": "2024-01-01T00:00:00Z",
            "author": "celor",
            "custom_field": {"nested": "data"},
        }
        patch = Patch(ops=[], meta=meta)

        assert patch.meta["artifact"] == "module.py"
        assert patch.meta["version"] == "2.0.0"
        assert patch.meta["timestamp"] == "2024-01-01T00:00:00Z"
        assert patch.meta["custom_field"]["nested"] == "data"

    def test_patch_is_dataclass(self):
        """Test that Patch is a dataclass."""
        from dataclasses import is_dataclass

        assert is_dataclass(Patch)

    def test_patch_equality(self):
        """Test patch equality."""
        ops1 = [PatchOp(op="test", args={"a": 1})]
        ops2 = [PatchOp(op="test", args={"a": 1})]
        ops3 = [PatchOp(op="test", args={"a": 2})]

        p1 = Patch(ops=ops1)
        p2 = Patch(ops=ops2)
        p3 = Patch(ops=ops3)

        assert p1 == p2
        assert p1 != p3

    def test_patch_json_transport_format(self):
        """Test that patch structure matches JSON transport format."""
        # Simulating the RFC-6902-inspired envelope format
        ops = [
            PatchOp(
                op="replace_function_body",
                args={"name": "f", "body": 'x = HOLE_EXPR("H1")\nreturn x'},
            ),
            PatchOp(op="format_black", args={}),
        ]
        holes = [{"hole_id": "H1", "allowed_symbols": ["a", "b", "c", "d"], "type_hint": "float"}]
        meta = {"artifact": "utils.py", "version": "2.0.0"}

        patch = Patch(ops=ops, holes=holes, meta=meta)

        # Verify structure matches expected format
        assert hasattr(patch, "ops")
        assert hasattr(patch, "holes")
        assert hasattr(patch, "meta")
        assert isinstance(patch.ops, list)
        assert all(isinstance(op, PatchOp) for op in patch.ops)


# ============================================================================
# Tests for Oracle Protocol (Requirement 1.5)
# ============================================================================


class TestOracleProtocol:
    """Tests for Oracle protocol compliance."""

    def test_oracle_protocol_callable(self):
        """Test that oracle is callable."""
        assert callable(mock_oracle_passing)
        assert callable(mock_oracle_failing)

    def test_oracle_returns_list_of_violations(self):
        """Test that oracle returns list of Violation objects."""
        artifact = MockArtifact()

        result_passing = mock_oracle_passing(artifact)
        result_failing = mock_oracle_failing(artifact)

        assert isinstance(result_passing, list)
        assert isinstance(result_failing, list)
        assert all(isinstance(v, Violation) for v in result_failing)

    def test_oracle_failing_returns_violations(self):
        """Test that failing oracle returns violations."""
        artifact = MockArtifact()
        violations = mock_oracle_failing(artifact)

        assert len(violations) > 0
        assert violations[0].id == "test_violation"
        assert violations[0].message == "Test failed"

    def test_oracle_accepts_any_artifact_type(self):
        """Test that oracle can accept any artifact type."""

        def flexible_oracle(artifact: Any) -> List[Violation]:
            # Should work with any artifact type
            if hasattr(artifact, "content") and artifact.content == "fail":
                return [Violation(id="1", message="Failed", path=["test"])]
            return []

        artifact1 = MockArtifact("pass")
        artifact2 = MockArtifact("fail")

        assert flexible_oracle(artifact1) == []
        assert len(flexible_oracle(artifact2)) == 1

    def test_oracle_protocol_compliance(self):
        """Test that mock oracles comply with Oracle protocol."""

        def use_oracle(oracle: Oracle, artifact: Any) -> List[Violation]:
            return oracle(artifact)

        artifact = MockArtifact()

        # Should work with both oracles
        result1 = use_oracle(mock_oracle_passing, artifact)
        result2 = use_oracle(mock_oracle_failing, artifact)

        assert isinstance(result1, list)
        assert isinstance(result2, list)

    def test_oracle_with_different_artifact_types(self):
        """Test oracle with different artifact implementations."""

        def generic_oracle(artifact: Any) -> List[Violation]:
            violations = []
            if hasattr(artifact, "content") and len(artifact.content) == 0:
                violations.append(Violation(id="empty", message="Empty content", path=["artifact"]))
            return violations

        artifact1 = MockArtifact("")
        artifact2 = MockArtifact("not empty")
        artifact3 = NonSerializableArtifact("")

        assert len(generic_oracle(artifact1)) == 1
        assert len(generic_oracle(artifact2)) == 0
        # Should work with non-Artifact protocol objects too
        assert len(generic_oracle(artifact3)) == 0  # No 'content' attribute

    def test_oracle_can_return_multiple_violations(self):
        """Test that oracle can return multiple violations."""

        def multi_violation_oracle(artifact: Any) -> List[Violation]:
            return [
                Violation(id="v1", message="Error 1", path=["p1"]),
                Violation(id="v2", message="Error 2", path=["p2"]),
                Violation(id="v3", message="Error 3", path=["p3"]),
            ]

        artifact = MockArtifact()
        violations = multi_violation_oracle(artifact)

        assert len(violations) == 3
        assert violations[0].id == "v1"
        assert violations[1].id == "v2"
        assert violations[2].id == "v3"

    def test_oracle_stateful_behavior(self):
        """Test oracle with stateful behavior."""

        class StatefulOracle:
            def __init__(self):
                self.call_count = 0

            def __call__(self, artifact: Any) -> List[Violation]:
                self.call_count += 1
                if self.call_count > 2:
                    return [Violation(id="limit", message="Too many calls", path=["oracle"])]
                return []

        oracle = StatefulOracle()
        artifact = MockArtifact()

        assert oracle(artifact) == []
        assert oracle(artifact) == []
        assert len(oracle(artifact)) == 1
        assert oracle.call_count == 3


# ============================================================================
# Integration Tests
# ============================================================================


class TestSchemaIntegration:
    """Integration tests for schema components working together."""

    def test_violation_in_oracle_return(self):
        """Test creating violations within oracle."""

        def test_oracle(artifact: Any) -> List[Violation]:
            violations = []
            if hasattr(artifact, "content"):
                if "error" in artifact.content:
                    violations.append(
                        Violation(
                            id="content_error",
                            message="Content contains error",
                            path=["artifact", "content"],
                            severity="error",
                            evidence={"content": artifact.content},
                        )
                    )
            return violations

        artifact_ok = MockArtifact("all good")
        artifact_bad = MockArtifact("has error in it")

        assert test_oracle(artifact_ok) == []
        violations = test_oracle(artifact_bad)
        assert len(violations) == 1
        assert violations[0].id == "content_error"
        assert violations[0].evidence["content"] == "has error in it"

    def test_patch_with_violation_evidence(self):
        """Test using violation evidence to create patches."""
        violation = Violation(
            id="test",
            message="Failed",
            path=["file.py", "func", "line:10"],
            evidence={"file": "file.py", "lineno": 10, "span": (100, 120)},
        )

        # Use violation evidence to create patch
        span = violation.evidence["span"]
        patch = Patch(
            ops=[PatchOp(op="replace_span_with_hole", args={"span": span, "hole_id": "H1"})]
        )

        assert patch.ops[0].args["span"] == (100, 120)

    def test_artifact_serialization_for_logging(self):
        """Test serializing artifacts for logging/transport."""
        artifact = MockArtifact("test data")
        serialized = to_serializable(artifact)

        # Should be JSON-serializable
        import json

        json_str = json.dumps(serialized)

        assert isinstance(json_str, str)
        assert "test data" in json_str

    def test_complete_verification_workflow(self):
        """Test complete workflow: artifact -> oracle -> violations."""
        # Create artifact
        artifact = MockArtifact("test content")

        # Create oracle
        def verification_oracle(art: Any) -> List[Violation]:
            violations = []
            if hasattr(art, "content") and len(art.content) < 5:
                violations.append(
                    Violation(
                        id="short_content",
                        message="Content too short",
                        path=["artifact", "content"],
                        severity="warning",
                    )
                )
            return violations

        # Run verification
        violations = verification_oracle(artifact)

        # Check results
        assert len(violations) == 0  # "test content" is long enough

        # Try with short content
        short_artifact = MockArtifact("hi")
        violations = verification_oracle(short_artifact)
        assert len(violations) == 1
        assert violations[0].severity == "warning"
