"""Artifact protocol for domain-agnostic artifact interface."""

from typing import Any, Protocol


class Artifact(Protocol):
    """Domain-agnostic artifact interface.

    An artifact represents a code or configuration object that can be
    verified and repaired. Examples include Python source code, JSON
    configurations, or Kubernetes manifests.
    """

    def to_serializable(self) -> Any:
        """Convert artifact to JSON-serializable format.

        Returns:
            JSON-serializable representation of the artifact (dict, list, str, etc.)
        """
        ...


def to_serializable(artifact: Any) -> Any:
    """Helper to serialize any artifact.

    If the artifact implements the Artifact protocol (has to_serializable method),
    uses that method. Otherwise, returns the artifact as-is.

    Args:
        artifact: The artifact to serialize

    Returns:
        JSON-serializable representation of the artifact
    """
    if hasattr(artifact, "to_serializable"):
        return artifact.to_serializable()
    return artifact
