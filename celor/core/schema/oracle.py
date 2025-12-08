"""Oracle protocol for verification functions."""

from typing import Any, List, Protocol

from celor.core.schema.violation import Violation


class Oracle(Protocol):
    """Verification function interface.

    An oracle is a callable that checks an artifact for correctness and
    returns a list of violations. Oracles can represent various types of
    verification:

    - Test-based oracles: Run pytest or function-level I/O checks
    - Policy-based oracles: Style checkers (ruff), type checkers (mypy)
    - Property-based oracles: Hypothesis property tests
    - Custom oracles: Domain-specific validation logic

    Multiple oracles can be combined to verify different aspects of
    correctness (tests, style, types, etc.).

    Example:
        def my_oracle(artifact: PythonArtifact) -> List[Violation]:
            # Run tests and return violations
            violations = []
            # ... verification logic ...
            return violations
    """

    def __call__(self, artifact: Any) -> List[Violation]:
        """Check artifact and return violations.

        Args:
            artifact: The artifact to verify (type depends on domain)

        Returns:
            List of violations found during verification.
            Empty list if artifact passes all checks.
        """
        ...
