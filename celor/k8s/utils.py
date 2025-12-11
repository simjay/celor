"""Shared utility functions for K8s oracles.

This module provides common helper functions used across multiple oracles
to avoid code duplication.
"""

from typing import Optional


def get_pod_template_label(manifest: dict, key: str) -> Optional[str]:
    """Extract label value from pod template.
    
    This is a shared utility function used by multiple oracles to extract
    labels from Kubernetes Deployment pod templates.
    
    Args:
        manifest: Kubernetes manifest dict
        key: Label key to extract
        
    Returns:
        Label value if found, None otherwise
    """
    return (manifest.get("spec", {})
            .get("template", {})
            .get("metadata", {})
            .get("labels", {})
            .get(key))


def get_containers(manifest: dict) -> list:
    """Extract containers list from Deployment manifest.
    
    Args:
        manifest: Kubernetes manifest dict
        
    Returns:
        List of container dicts, empty list if not found
    """
    return (manifest.get("spec", {})
            .get("template", {})
            .get("spec", {})
            .get("containers", []))
