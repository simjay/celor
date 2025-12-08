"""Violation model for representing test failures, policy violations, or errors."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Union


@dataclass
class ViolationEvidence:
    """Standardized evidence structure for violations.

    This dataclass provides a type-safe, well-documented structure for
    violation evidence across all tools in CeLoR. It consolidates evidence
    from test failures, runtime exceptions, and static analysis.

    Attributes:
        # Test failure fields
        inputs: Input arguments that triggered the failure
        expected: Expected output value (if known)
        actual: Actual output value (if computed before failure)

        # Location fields
        file: Source file path where the failure occurred
        lineno: Line number where the failure occurred
        func: Function name where the failure occurred

        # Dynamic analysis fields (from stack_data)
        locals: Local variables at failure point (alias for locals_snapshot)
        locals_snapshot: Local variables at failure point (preferred name)
        executing_node: AST node being executed at failure (from stack_data)

        # Coverage fields
        executed_lines: Set of line numbers executed during test

        # Exception fields
        exception_type: Type of exception raised (if any)
        exception_message: Exception message (if any)
    """

    # Test failure fields
    inputs: Optional[List[Any]] = None
    expected: Optional[Any] = None
    actual: Optional[Any] = None

    # Location fields
    file: Optional[str] = None
    lineno: Optional[int] = None
    func: Optional[str] = None

    # Dynamic analysis fields (from stack_data)
    locals: Optional[Dict[str, Any]] = None  # Alias for locals_snapshot
    locals_snapshot: Optional[Dict[str, Any]] = None  # Preferred name
    executing_node: Optional[Any] = None  # AST node from stack_data

    # Coverage fields
    executed_lines: Optional[Set[int]] = None

    # Exception fields
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None

    def __post_init__(self):
        """Ensure locals and locals_snapshot are synchronized."""
        # If locals_snapshot is set but locals is not, copy it
        if self.locals_snapshot is not None and self.locals is None:
            self.locals = self.locals_snapshot
        # If locals is set but locals_snapshot is not, copy it
        elif self.locals is not None and self.locals_snapshot is None:
            self.locals_snapshot = self.locals

    def to_dict(self) -> Dict[str, Any]:
        """Convert evidence to dictionary format.

        Returns:
            Dictionary representation of evidence
        """
        result = {}
        if self.inputs is not None:
            result["inputs"] = self.inputs
        if self.expected is not None:
            result["expected"] = self.expected
        if self.actual is not None:
            result["actual"] = self.actual
        if self.file is not None:
            result["file"] = self.file
        if self.lineno is not None:
            result["lineno"] = self.lineno
        if self.func is not None:
            result["func"] = self.func
        if self.locals_snapshot is not None:
            result["locals"] = self.locals_snapshot
            result["locals_snapshot"] = self.locals_snapshot
        if self.executing_node is not None:
            result["executing_node"] = self.executing_node
        if self.executed_lines is not None:
            result["executed_lines"] = self.executed_lines
        if self.exception_type is not None:
            result["exception_type"] = self.exception_type
        if self.exception_message is not None:
            result["exception_message"] = self.exception_message
        return result


@dataclass
class Violation:
    """Represents a test failure, policy violation, or error.

    Violations are returned by oracles during verification and contain
    information about what went wrong, where it occurred, and evidence
    for debugging and repair.

    Attributes:
        id: Unique identifier for the violation (e.g., "file.py:10:func_name")
        message: Human-readable description of the violation
        path: Location path as list of strings (e.g., ["file.py", "func", "line:10"])
        severity: Severity level - "error", "warning", or "info"
        evidence: Domain-specific data such as inputs, expected/actual values,
                 locals snapshot, stack traces, etc. Can be a dict or ViolationEvidence
                 object for backward compatibility.
    """

    id: str
    message: str
    path: List[str]
    severity: str = "error"
    evidence: Union[Dict[str, Any], ViolationEvidence, None] = None

    def get_evidence(self) -> ViolationEvidence:
        """Get evidence as standardized ViolationEvidence object.

        Converts dict-based evidence to ViolationEvidence if needed.
        This ensures consistent access to evidence fields across the codebase.

        Returns:
            ViolationEvidence object (empty if no evidence)
        """
        if isinstance(self.evidence, ViolationEvidence):
            return self.evidence

        if isinstance(self.evidence, dict):
            # Convert dict to ViolationEvidence
            # Handle both 'locals' and 'locals_snapshot' keys
            evidence_dict = dict(self.evidence)

            # Ensure locals_snapshot is set if locals is present
            if "locals" in evidence_dict and "locals_snapshot" not in evidence_dict:
                evidence_dict["locals_snapshot"] = evidence_dict["locals"]
            elif "locals_snapshot" in evidence_dict and "locals" not in evidence_dict:
                evidence_dict["locals"] = evidence_dict["locals_snapshot"]

            # Filter to only include valid ViolationEvidence fields
            valid_fields = {
                "inputs",
                "expected",
                "actual",
                "file",
                "lineno",
                "func",
                "locals",
                "locals_snapshot",
                "executing_node",
                "executed_lines",
                "exception_type",
                "exception_message",
            }
            filtered_dict = {k: v for k, v in evidence_dict.items() if k in valid_fields}

            return ViolationEvidence(**filtered_dict)

        # No evidence or unknown type
        return ViolationEvidence()
