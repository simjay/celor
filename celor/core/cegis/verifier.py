"""Verifier for executing oracles and aggregating violations."""

from typing import Any, List

from celor.core.schema.oracle import Oracle
from celor.core.schema.violation import Violation


def verify(artifact: Any, oracles: List[Oracle]) -> List[Violation]:
    """Execute all oracles against artifact and aggregate violations.

    This function runs all provided oracles sequentially against the artifact
    and collects all violations. It handles empty oracle lists gracefully and
    continues execution even if individual oracles fail.

    Args:
        artifact: The artifact to verify (type depends on domain, e.g., PythonArtifact)
        oracles: List of verification functions to execute

    Returns:
        Aggregated list of violations from all oracles. Returns empty list if
        no oracles provided or if all oracles pass.

    Example:
        >>> from celor.adapters.python.artifact import PythonArtifact
        >>> artifact = PythonArtifact.from_source("def f(): return 42")
        >>> violations = verify(artifact, [test_oracle, style_oracle])
        >>> len(violations)
        0
    """
    # Handle empty oracle list
    if not oracles:
        return []

    violations: List[Violation] = []

    # Execute each oracle and aggregate violations
    for oracle in oracles:
        try:
            oracle_violations = oracle(artifact)
            violations.extend(oracle_violations)
        except Exception as e:
            # Convert oracle failures to violations
            # This ensures the verification process continues even if an oracle crashes
            violation = Violation(
                id=f"oracle_error:{oracle.__name__ if hasattr(oracle, '__name__') else 'unknown'}",
                message=f"Oracle execution failed: {str(e)}",
                path=["verifier", "oracle_error"],
                severity="error",
                evidence={"exception": str(e), "exception_type": type(e).__name__},
            )
            violations.append(violation)

    return violations
