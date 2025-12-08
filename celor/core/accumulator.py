"""Counterexample accumulator for tracking violations across iterations.

This module provides functionality to accumulate counterexamples (violations)
across repair iterations, preventing the system from reintroducing bugs that
were previously fixed.

Used by the outer controller loop to track failures across LLM re-prompting iterations.
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import List, Set

from celor.core.schema.violation import Violation


@dataclass
class AccumulatedCounterexample:
    """Counterexample with metadata for accumulation."""

    violation: Violation
    iteration: int  # When it was first seen
    satisfied: bool = False  # Whether current patch satisfies it


class CounterexampleAccumulator:
    """Manages accumulated counterexamples across iterations.

    This class tracks violations (counterexamples) across CEGIS iterations
    to ensure that once a bug is fixed, it doesn't get reintroduced in
    subsequent iterations.

    Example:
        >>> accumulator = CounterexampleAccumulator()
        >>> violation = Violation(id="test", message="assert failed", ...)
        >>> accumulator.add(violation, iteration=0)
        >>> all_cex = accumulator.get_all()
        >>> len(all_cex)
        1
        >>> accumulator.mark_satisfied(violation)
        >>> all_cex = accumulator.get_all()
        >>> len(all_cex)
        0
    """

    def __init__(self):
        """Initialize an empty accumulator."""
        self.accumulated: List[AccumulatedCounterexample] = []
        self._seen_hashes: Set[str] = set()

    def add(self, violation: Violation, iteration: int) -> bool:
        """Add a new counterexample if not already seen.

        Args:
            violation: Violation to add as counterexample
            iteration: Current iteration number

        Returns:
            True if violation was added, False if it was already seen
        """
        # Create hash from violation evidence
        cex_hash = self._hash_violation(violation)

        if cex_hash not in self._seen_hashes:
            self.accumulated.append(
                AccumulatedCounterexample(violation=violation, iteration=iteration)
            )
            self._seen_hashes.add(cex_hash)
            return True
        return False

    def add_all(self, violations: List[Violation], iteration: int) -> int:
        """Add multiple counterexamples.

        Args:
            violations: List of violations to add
            iteration: Current iteration number

        Returns:
            Number of new violations added (excluding duplicates)
        """
        added_count = 0
        for v in violations:
            if self.add(v, iteration):
                added_count += 1
        return added_count

    def get_all(self) -> List[Violation]:
        """Get all accumulated counterexamples that are not yet satisfied.

        Returns:
            List of violations that are still unsatisfied
        """
        return [acc.violation for acc in self.accumulated if not acc.satisfied]

    def get_all_with_metadata(self) -> List[AccumulatedCounterexample]:
        """Get all accumulated counterexamples with metadata.

        Returns:
            List of AccumulatedCounterexample objects (including satisfied ones)
        """
        return self.accumulated.copy()

    def mark_satisfied(self, violation: Violation) -> bool:
        """Mark a counterexample as satisfied by current patch.

        Args:
            violation: Violation that is now satisfied

        Returns:
            True if violation was found and marked, False otherwise
        """
        cex_hash = self._hash_violation(violation)
        for acc in self.accumulated:
            if self._hash_violation(acc.violation) == cex_hash:
                acc.satisfied = True
                return True
        return False

    def mark_all_satisfied(self, violations: List[Violation]) -> int:
        """Mark multiple counterexamples as satisfied.

        Args:
            violations: List of violations that are now satisfied

        Returns:
            Number of violations that were found and marked
        """
        marked_count = 0
        for v in violations:
            if self.mark_satisfied(v):
                marked_count += 1
        return marked_count

    def _hash_violation(self, violation: Violation) -> str:
        """Create hash from violation evidence for deduplication.

        Uses the module-level hash_violation function.
        """
        return hash_violation(violation)

    def count(self) -> int:
        """Get count of accumulated counterexamples (including satisfied ones).

        Returns:
            Total number of accumulated counterexamples
        """
        return len(self.accumulated)

    def count_unsatisfied(self) -> int:
        """Get count of unsatisfied counterexamples.

        Returns:
            Number of counterexamples that are not yet satisfied
        """
        return len(self.get_all())

    def clear(self):
        """Clear all accumulated counterexamples."""
        self.accumulated.clear()
        self._seen_hashes.clear()


def hash_violation(violation: Violation) -> str:
    """Create hash from violation evidence for deduplication.

    The hash is based on the constraint (inputs and expected output),
    not on the violation message or other metadata. This ensures that
    the same test case is only accumulated once, even if the violation
    message changes.

    Args:
        violation: Violation to hash

    Returns:
        MD5 hash as hexadecimal string
    """
    # Get evidence (use get_evidence() for standardized access)
    evidence = violation.get_evidence()

    # Hash based on inputs and expected (the actual constraint)
    # Also include file and function to distinguish different functions
    key_data = {
        "inputs": getattr(evidence, "inputs", None) or [],
        "expected": getattr(evidence, "expected", None),
        "file": violation.path[0] if violation.path else "",
        "func": violation.path[1] if len(violation.path) > 1 else "",
    }

    # Convert to JSON string and hash
    json_str = json.dumps(key_data, sort_keys=True)
    return hashlib.md5(json_str.encode()).hexdigest()
