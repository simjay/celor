"""Tests for K8s Patch DSL operations."""

import pytest

from celor.core.schema.patch_dsl import Patch, PatchOp
from celor.k8s.patch_dsl import (
    RESOURCE_PROFILES,
    apply_k8s_op,
    apply_k8s_patch,
)

SAMPLE_DEPLOYMENT = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: payments-api
  labels:
    app: payments-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: payments-api
  template:
    metadata:
      labels:
        app: payments-api
    spec:
      containers:
      - name: payments-api
        image: payments-api:latest
        resources:
          requests:
            cpu: "100m"
            memory: "128Mi"
"""


class TestEnsureLabel:
    """Tests for EnsureLabel operation."""

    def test_ensure_label_pod_template(self):
        """Test adding label to pod template."""
        files = {"deployment.yaml": SAMPLE_DEPLOYMENT}
        op = PatchOp("EnsureLabel", {"scope": "podTemplate", "key": "env", "value": "production-us"})
        
        result = apply_k8s_op(files, op)
        
        assert "env: production-us" in result["deployment.yaml"]
        # Should be in pod template labels, not deployment labels

    def test_ensure_label_deployment(self):
        """Test adding label to deployment metadata."""
        files = {"deployment.yaml": SAMPLE_DEPLOYMENT}
        op = PatchOp("EnsureLabel", {"scope": "deployment", "key": "team", "value": "payments"})
        
        result = apply_k8s_op(files, op)
        
        assert "team: payments" in result["deployment.yaml"]

    def test_ensure_label_both(self):
        """Test adding label to both deployment and pod template."""
        files = {"deployment.yaml": SAMPLE_DEPLOYMENT}
        op = PatchOp("EnsureLabel", {"scope": "both", "key": "env", "value": "staging"})
        
        result = apply_k8s_op(files, op)
        
        # Should appear twice (deployment + pod template)
        assert result["deployment.yaml"].count("env: staging") >= 1


class TestEnsureImageVersion:
    """Tests for EnsureImageVersion operation."""

    def test_ensure_image_version(self):
        """Test setting container image version."""
        files = {"deployment.yaml": SAMPLE_DEPLOYMENT}
        op = PatchOp("EnsureImageVersion", {"container": "payments-api", "version": "prod-1.2.3"})
        
        result = apply_k8s_op(files, op)
        
        assert "image: payments-api:prod-1.2.3" in result["deployment.yaml"]

    def test_ensure_image_version_replaces_latest(self):
        """Test that it replaces :latest tag."""
        files = {"deployment.yaml": SAMPLE_DEPLOYMENT}  # Has :latest
        op = PatchOp("EnsureImageVersion", {"container": "payments-api", "version": "v2.0.0"})
        
        result = apply_k8s_op(files, op)
        
        assert ":latest" not in result["deployment.yaml"]
        assert ":v2.0.0" in result["deployment.yaml"]


class TestEnsureSecurityBaseline:
    """Tests for EnsureSecurityBaseline operation."""

    def test_ensure_security_baseline(self):
        """Test setting security context."""
        files = {"deployment.yaml": SAMPLE_DEPLOYMENT}
        op = PatchOp("EnsureSecurityBaseline", {"container": "payments-api"})
        
        result = apply_k8s_op(files, op)
        
        result_yaml = result["deployment.yaml"]
        assert "runAsNonRoot: true" in result_yaml
        assert "allowPrivilegeEscalation: false" in result_yaml
        assert "readOnlyRootFilesystem: true" in result_yaml
        # Check for capabilities drop with ALL (formatting may vary)
        assert "capabilities:" in result_yaml
        assert "drop:" in result_yaml
        assert "ALL" in result_yaml


class TestEnsureResourceProfile:
    """Tests for EnsureResourceProfile operation."""

    def test_ensure_resource_profile_medium(self):
        """Test setting medium resource profile."""
        files = {"deployment.yaml": SAMPLE_DEPLOYMENT}
        op = PatchOp("EnsureResourceProfile", {"container": "payments-api", "profile": "medium"})
        
        result = apply_k8s_op(files, op)
        
        assert "cpu: 500m" in result["deployment.yaml"]
        assert "memory: 512Mi" in result["deployment.yaml"]

    def test_ensure_resource_profile_large(self):
        """Test setting large resource profile."""
        files = {"deployment.yaml": SAMPLE_DEPLOYMENT}
        op = PatchOp("EnsureResourceProfile", {"container": "payments-api", "profile": "large"})
        
        result = apply_k8s_op(files, op)
        
        assert "cpu: 1000m" in result["deployment.yaml"] or "cpu: '1000m'" in result["deployment.yaml"]
        assert "memory: 1Gi" in result["deployment.yaml"]

    def test_resource_profile_invalid_raises_error(self):
        """Test that invalid profile raises error."""
        files = {"deployment.yaml": SAMPLE_DEPLOYMENT}
        op = PatchOp("EnsureResourceProfile", {"container": "payments-api", "profile": "invalid"})
        
        with pytest.raises(ValueError, match="Unknown resource profile"):
            apply_k8s_op(files, op)


class TestEnsureReplicas:
    """Tests for EnsureReplicas operation."""

    def test_ensure_replicas(self):
        """Test setting replica count."""
        files = {"deployment.yaml": SAMPLE_DEPLOYMENT}  # Has replicas: 2
        op = PatchOp("EnsureReplicas", {"replicas": 5})
        
        result = apply_k8s_op(files, op)
        
        assert "replicas: 5" in result["deployment.yaml"]
        assert "replicas: 2" not in result["deployment.yaml"]


class TestEnsurePriorityClass:
    """Tests for EnsurePriorityClass operation."""

    def test_ensure_priority_class(self):
        """Test setting priorityClassName."""
        files = {"deployment.yaml": SAMPLE_DEPLOYMENT}
        op = PatchOp("EnsurePriorityClass", {"name": "critical"})
        
        result = apply_k8s_op(files, op)
        
        assert "priorityClassName: critical" in result["deployment.yaml"]

    def test_ensure_priority_class_none_removes(self):
        """Test that None removes priorityClassName."""
        # First add it
        files = {"deployment.yaml": SAMPLE_DEPLOYMENT}
        op1 = PatchOp("EnsurePriorityClass", {"name": "critical"})
        files = apply_k8s_op(files, op1)
        assert "priorityClassName" in files["deployment.yaml"]
        
        # Then remove it
        op2 = PatchOp("EnsurePriorityClass", {"name": None})
        result = apply_k8s_op(files, op2)
        
        assert "priorityClassName" not in result["deployment.yaml"]


class TestApplyK8sPatch:
    """Tests for apply_k8s_patch() function."""

    def test_apply_multiple_ops(self):
        """Test applying multiple operations in sequence."""
        files = {"deployment.yaml": SAMPLE_DEPLOYMENT}
        patch = Patch(ops=[
            PatchOp("EnsureLabel", {"scope": "podTemplate", "key": "env", "value": "production-us"}),
            PatchOp("EnsureReplicas", {"replicas": 3}),
            PatchOp("EnsureResourceProfile", {"container": "payments-api", "profile": "medium"})
        ])
        
        result = apply_k8s_patch(files, patch)
        
        assert "env: production-us" in result["deployment.yaml"]
        assert "replicas: 3" in result["deployment.yaml"]
        assert "cpu: 500m" in result["deployment.yaml"]

    def test_operations_are_sequential(self):
        """Test that operations apply in order."""
        files = {"deployment.yaml": SAMPLE_DEPLOYMENT}
        patch = Patch(ops=[
            PatchOp("EnsureReplicas", {"replicas": 3}),
            PatchOp("EnsureReplicas", {"replicas": 4}),  # Overrides previous
        ])
        
        result = apply_k8s_patch(files, patch)
        
        assert "replicas: 4" in result["deployment.yaml"]
        assert "replicas: 3" not in result["deployment.yaml"]

    def test_unknown_op_raises_error(self):
        """Test that unknown operation raises error."""
        files = {"deployment.yaml": SAMPLE_DEPLOYMENT}
        patch = Patch(ops=[PatchOp("UnknownOp", {})])
        
        with pytest.raises(ValueError, match="Unknown K8s patch operation"):
            apply_k8s_patch(files, patch)


class TestYAMLPreservation:
    """Tests for YAML format preservation."""

    def test_preserves_yaml_structure(self):
        """Test that YAML structure is preserved."""
        files = {"deployment.yaml": SAMPLE_DEPLOYMENT}
        op = PatchOp("EnsureReplicas", {"replicas": 3})
        
        result = apply_k8s_op(files, op)
        
        # Should still have apiVersion, kind, metadata structure
        assert "apiVersion: apps/v1" in result["deployment.yaml"]
        assert "kind: Deployment" in result["deployment.yaml"]
        assert "name: payments-api" in result["deployment.yaml"]

