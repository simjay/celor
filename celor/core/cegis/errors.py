"""CEGIS-specific exceptions for error handling."""

from typing import Any, List, Optional


class PatchApplyError(Exception):
    """Raised when patch application fails.

    This exception is raised when applying a patch to an artifact fails due to:
    - Invalid patch operations
    - Syntax errors in generated code
    - Unknown operation types

    The error includes information about which operation failed and why,
    allowing for graceful degradation and logging.

    Attributes:
        message: Description of the failure
        patch_op: The PatchOp that failed (optional)
        artifact: The artifact being patched (optional)
    """

    def __init__(
        self, message: str, patch_op: Optional[Any] = None, artifact: Optional[Any] = None
    ) -> None:
        """Initialize PatchApplyError exception.

        Args:
            message: Error message describing the failure
            patch_op: The PatchOp that failed (optional)
            artifact: The artifact being patched (optional)
        """
        super().__init__(message)
        self.patch_op = patch_op
        self.artifact = artifact


class SynthesisError(Exception):
    """Raised when synthesis fails.

    This exception covers synthesis failures such as:
    - No satisfying candidate found
    - Invalid template or hole space
    - Unsatisfiable constraints
    - Search exhausted without solution

    Attributes:
        message: Description of the synthesis failure
        details: Additional debugging information (optional)
    """

    def __init__(self, message: str, details: Optional[str] = None) -> None:
        """Initialize SynthesisError exception.

        Args:
            message: Error message describing the failure
            details: Additional details for debugging (optional)
        """
        super().__init__(message)
        self.details = details
