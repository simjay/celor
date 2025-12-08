"""Unit tests for counterexample accumulator.

Tests cover:
- Adding counterexamples (deduplication)
- Marking counterexamples as satisfied
- Getting all unsatisfied counterexamples
- Hash-based matching
"""

import pytest

from celor.core.accumulator import (
    AccumulatedCounterexample,
    CounterexampleAccumulator,
)
from celor.core.schema.violation import Violation


def test_accumulator_add_single():
    """Test adding a single counterexample."""
    accumulator = CounterexampleAccumulator()
    violation = Violation(
        id="test1",
        message="Test failure",
        path=["file.py", "f"],
        evidence={"inputs": [10, 2], "expected": 20},
    )

    result = accumulator.add(violation, iteration=0)

    assert result is True
    assert accumulator.count() == 1
    assert accumulator.count_unsatisfied() == 1


def test_accumulator_deduplication():
    """Test that duplicate counterexamples are not added."""
    accumulator = CounterexampleAccumulator()
    violation1 = Violation(
        id="test1",
        message="Test failure",
        path=["file.py", "f"],
        evidence={"inputs": [10, 2], "expected": 20},
    )
    violation2 = Violation(
        id="test2",  # Different ID but same constraint
        message="Different message",
        path=["file.py", "f"],
        evidence={"inputs": [10, 2], "expected": 20},  # Same inputs/expected
    )

    accumulator.add(violation1, iteration=0)
    result = accumulator.add(violation2, iteration=1)

    assert result is False  # Duplicate, not added
    assert accumulator.count() == 1
    assert accumulator.count_unsatisfied() == 1


def test_accumulator_add_all():
    """Test adding multiple counterexamples."""
    accumulator = CounterexampleAccumulator()
    violations = [
        Violation(
            id=f"test{i}",
            message=f"Test {i}",
            path=["file.py", "f"],
            evidence={"inputs": [i, i + 1], "expected": i * 2},
        )
        for i in range(3)
    ]

    added_count = accumulator.add_all(violations, iteration=0)

    assert added_count == 3
    assert accumulator.count() == 3
    assert accumulator.count_unsatisfied() == 3


def test_accumulator_mark_satisfied():
    """Test marking a counterexample as satisfied."""
    accumulator = CounterexampleAccumulator()
    violation = Violation(
        id="test1",
        message="Test failure",
        path=["file.py", "f"],
        evidence={"inputs": [10, 2], "expected": 20},
    )

    accumulator.add(violation, iteration=0)
    assert accumulator.count_unsatisfied() == 1

    result = accumulator.mark_satisfied(violation)

    assert result is True
    assert accumulator.count() == 1  # Still counted
    assert accumulator.count_unsatisfied() == 0  # But satisfied


def test_accumulator_get_all():
    """Test getting all unsatisfied counterexamples."""
    accumulator = CounterexampleAccumulator()
    violations = [
        Violation(
            id=f"test{i}",
            message=f"Test {i}",
            path=["file.py", "f"],
            evidence={"inputs": [i, i + 1], "expected": i * 2},
        )
        for i in range(3)
    ]

    accumulator.add_all(violations, iteration=0)

    all_cex = accumulator.get_all()
    assert len(all_cex) == 3

    # Mark one as satisfied
    accumulator.mark_satisfied(violations[0])

    all_cex = accumulator.get_all()
    assert len(all_cex) == 2  # Only unsatisfied ones


def test_accumulator_hash_based_matching():
    """Test that hash-based matching works correctly."""
    accumulator = CounterexampleAccumulator()

    # Same constraint, different metadata
    violation1 = Violation(
        id="test1",
        message="First failure",
        path=["file.py", "f"],
        evidence={"inputs": [10, 2], "expected": 20},
    )
    violation2 = Violation(
        id="test2",
        message="Second failure",  # Different message
        path=["file.py", "f"],
        evidence={"inputs": [10, 2], "expected": 20},  # Same constraint
    )

    accumulator.add(violation1, iteration=0)
    result = accumulator.add(violation2, iteration=1)

    # Should be treated as duplicate (same constraint)
    assert result is False
    assert accumulator.count() == 1


def test_accumulator_different_constraints():
    """Test that different constraints are treated as separate."""
    accumulator = CounterexampleAccumulator()

    violation1 = Violation(
        id="test1",
        message="Test 1",
        path=["file.py", "f"],
        evidence={"inputs": [10, 2], "expected": 20},
    )
    violation2 = Violation(
        id="test2",
        message="Test 2",
        path=["file.py", "f"],
        evidence={"inputs": [5, 3], "expected": 15},  # Different constraint
    )

    accumulator.add(violation1, iteration=0)
    result = accumulator.add(violation2, iteration=1)

    # Should be treated as different
    assert result is True
    assert accumulator.count() == 2


def test_accumulator_clear():
    """Test clearing all accumulated counterexamples."""
    accumulator = CounterexampleAccumulator()
    violations = [
        Violation(
            id=f"test{i}",
            message=f"Test {i}",
            path=["file.py", "f"],
            evidence={"inputs": [i, i + 1], "expected": i * 2},
        )
        for i in range(3)
    ]

    accumulator.add_all(violations, iteration=0)
    assert accumulator.count() == 3

    accumulator.clear()

    assert accumulator.count() == 0
    assert accumulator.count_unsatisfied() == 0


def test_accumulator_mark_all_satisfied():
    """Test marking multiple counterexamples as satisfied."""
    accumulator = CounterexampleAccumulator()
    violations = [
        Violation(
            id=f"test{i}",
            message=f"Test {i}",
            path=["file.py", "f"],
            evidence={"inputs": [i, i + 1], "expected": i * 2},
        )
        for i in range(3)
    ]

    accumulator.add_all(violations, iteration=0)
    assert accumulator.count_unsatisfied() == 3

    marked_count = accumulator.mark_all_satisfied(violations[:2])

    assert marked_count == 2
    assert accumulator.count_unsatisfied() == 1
