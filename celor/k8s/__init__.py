"""Kubernetes (K8s) domain adapter for CeLoR.

This module provides K8s-specific implementations for CeLoR's CEGIS-style
repair framework:
- K8sArtifact: Represents K8s YAML manifests
- K8s PatchDSL: Operations for modifying K8s manifests
- K8s Oracles: Schema, policy, security, resource validators
"""

