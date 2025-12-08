"""Unit tests for the CEGIS verifier module.

Tests cover:
- Multiple oracle execution (Requirement 4.1)
- Violation aggregation (Requirement 4.2)
- Empty oracle list handling (Requirement 4.3)
"""

from typing import Any, List

import pytest

from celor.core.cegis.verifier import verify
from celor.core.schema.oracle import Oracle
from celor.core.schema.violation import Violation

# Test fixtures and mock oracles


class MockArtifact:
    """Simple mock artifact for testing."""

    def __init__(self, content: str = "test"):
        self.content = content


def passing_oracle(artifact: Any) -> List[Violation]:
    """Oracle that always passes (returns no violations)."""
    return []


def failing_oracle_one(artifact: Any) -> List[Violation]:
    """Oracle that returns one violation."""
    return [
        Violation(
            id="test1",
            message="Test failure 1",
            path=["file.py", "func1", "line:10"],
            severity="error",
            evidence={"input": 1, "expected": 2, "actual": 1},
        )
    ]


def failing_oracle_two(artifact: Any) -> List[Violation]:
    """Oracle that returns two violations."""
    return [
        Violation(
            id="test2",
            message="Test failure 2",
            path=["file.py", "func2", "line:20"],
            severity="error",
        ),
        Violation(
            id="test3",
            message="Test failure 3",
            path=["file.py", "func3", "line:30"],
            severity="warning",
        ),
    ]


def crashing_oracle(artifact: Any) -> List[Violation]:
    """Oracle that raises an exception."""
    raise RuntimeError("Oracle crashed unexpectedly")


# Test cases


def test_verify_empty_oracle_list():
    """Test that verify handles empty oracle list gracefully (Requirement 4.3)."""
    artifact = MockArtifact()
    violations = verify(artifact, [])

    assert violations == []
    assert isinstance(violations, list)


def test_verify_single_passing_oracle():
    """Test verify with a single oracle that passes."""
    artifact = MockArtifact()
    violations = verify(artifact, [passing_oracle])

    assert violations == []


def test_verify_single_failing_oracle():
    """Test verify with a single oracle that returns violations."""
    artifact = MockArtifact()
    violations = verify(artifact, [failing_oracle_one])

    assert len(violations) == 1
    assert violations[0].id == "test1"
    assert violations[0].message == "Test failure 1"
    assert violations[0].severity == "error"


def test_verify_multiple_oracles_all_passing():
    """Test multiple oracle execution when all pass (Requirement 4.1)."""
    artifact = MockArtifact()
    violations = verify(artifact, [passing_oracle, passing_oracle, passing_oracle])

    assert violations == []


def test_verify_multiple_oracles_mixed():
    """Test multiple oracle execution with mixed results (Requirement 4.1)."""
    artifact = MockArtifact()
    oracles = [passing_oracle, failing_oracle_one, passing_oracle]
    violations = verify(artifact, oracles)

    assert len(violations) == 1
    assert violations[0].id == "test1"


def test_verify_violation_aggregation():
    """Test that violations from multiple oracles are aggregated (Requirement 4.2)."""
    artifact = MockArtifact()
    oracles = [failing_oracle_one, failing_oracle_two]
    violations = verify(artifact, oracles)

    # Should have 1 violation from first oracle + 2 from second oracle
    assert len(violations) == 3

    # Verify all violations are present
    violation_ids = [v.id for v in violations]
    assert "test1" in violation_ids
    assert "test2" in violation_ids
    assert "test3" in violation_ids

    # Verify order is preserved (first oracle's violations come first)
    assert violations[0].id == "test1"
    assert violations[1].id == "test2"
    assert violations[2].id == "test3"


def test_verify_aggregation_preserves_severity():
    """Test that violation aggregation preserves severity levels."""
    artifact = MockArtifact()
    violations = verify(artifact, [failing_oracle_two])

    assert len(violations) == 2
    assert violations[0].severity == "error"
    assert violations[1].severity == "warning"


def test_verify_aggregation_preserves_evidence():
    """Test that violation aggregation preserves evidence data."""
    artifact = MockArtifact()
    violations = verify(artifact, [failing_oracle_one])

    assert len(violations) == 1
    assert violations[0].evidence is not None
    assert violations[0].evidence["input"] == 1
    assert violations[0].evidence["expected"] == 2
    assert violations[0].evidence["actual"] == 1


def test_verify_oracle_execution_order():
    """Test that oracles are executed in the order provided (Requirement 4.1)."""
    artifact = MockArtifact()

    # Create oracles that track execution order
    execution_order = []

    def oracle_a(artifact: Any) -> List[Violation]:
        execution_order.append("A")
        return []

    def oracle_b(artifact: Any) -> List[Violation]:
        execution_order.append("B")
        return []

    def oracle_c(artifact: Any) -> List[Violation]:
        execution_order.append("C")
        return []

    verify(artifact, [oracle_a, oracle_b, oracle_c])

    assert execution_order == ["A", "B", "C"]


def test_verify_handles_crashing_oracle():
    """Test that verify continues execution even if an oracle crashes."""
    artifact = MockArtifact()
    oracles = [failing_oracle_one, crashing_oracle, failing_oracle_two]
    violations = verify(artifact, oracles)

    # Should have violations from first oracle, error from crashing oracle,
    # and violations from third oracle
    assert len(violations) >= 4  # At least 1 + 1 (error) + 2

    # Check that we got violations from the non-crashing oracles
    violation_ids = [v.id for v in violations]
    assert "test1" in violation_ids
    assert "test2" in violation_ids
    assert "test3" in violation_ids

    # Check that the crash was converted to a violation
    oracle_error_violations = [v for v in violations if "oracle_error" in v.id]
    assert len(oracle_error_violations) == 1
    assert "Oracle execution failed" in oracle_error_violations[0].message
    assert "RuntimeError" in oracle_error_violations[0].evidence["exception_type"]


def test_verify_artifact_passed_to_all_oracles():
    """Test that the same artifact is passed to all oracles."""
    artifact = MockArtifact(content="specific_content")

    received_artifacts = []

    def capturing_oracle(artifact: Any) -> List[Violation]:
        received_artifacts.append(artifact)
        return []

    verify(artifact, [capturing_oracle, capturing_oracle, capturing_oracle])

    assert len(received_artifacts) == 3
    assert all(a.content == "specific_content" for a in received_artifacts)
    assert all(a is artifact for a in received_artifacts)


def test_verify_returns_list_type():
    """Test that verify always returns a list, never None."""
    artifact = MockArtifact()

    # Empty oracles
    result = verify(artifact, [])
    assert isinstance(result, list)

    # Passing oracles
    result = verify(artifact, [passing_oracle])
    assert isinstance(result, list)

    # Failing oracles
    result = verify(artifact, [failing_oracle_one])
    assert isinstance(result, list)
