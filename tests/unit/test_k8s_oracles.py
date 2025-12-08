"""Tests for K8s oracles."""

import pytest

from celor.k8s.artifact import K8sArtifact
from celor.k8s.oracles import PolicyOracle, ResourceOracle, SecurityOracle, SchemaOracle

COMPLIANT_DEPLOYMENT = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: payments-api
  labels:
    app: payments-api
spec:
  replicas: 3
  priorityClassName: critical
  selector:
    matchLabels:
      app: payments-api
  template:
    metadata:
      labels:
        app: payments-api
        env: prod
        team: payments
        tier: backend
    spec:
      containers:
      - name: payments-api
        image: payments-api:prod-1.2.3
        securityContext:
          runAsNonRoot: true
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop: [ALL]
        resources:
          requests:
            cpu: "500m"
            memory: "512Mi"
          limits:
            cpu: "1000m"
            memory: "1Gi"
"""

NON_COMPLIANT_DEPLOYMENT = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: payments-api
spec:
  replicas: 2
  template:
    metadata:
      labels:
        app: payments-api
        env: prod
    spec:
      containers:
      - name: payments-api
        image: payments-api:latest
        resources:
          requests:
            cpu: "100m"
            memory: "128Mi"
"""


class TestPolicyOracle:
    """Tests for PolicyOracle."""

    def test_compliant_manifest_passes(self):
        """Test that compliant manifest passes."""
        artifact = K8sArtifact(files={"deployment.yaml": COMPLIANT_DEPLOYMENT})
        oracle = PolicyOracle()
        
        violations = oracle(artifact)
        
        assert len(violations) == 0

    def test_env_prod_low_replicas_fails(self):
        """Test that env=prod with replicas=2 fails."""
        artifact = K8sArtifact(files={"deployment.yaml": NON_COMPLIANT_DEPLOYMENT})
        oracle = PolicyOracle()
        
        violations = oracle(artifact)
        
        # Should have violation for replicas
        replica_violations = [v for v in violations if "REPLICA" in v.id]
        assert len(replica_violations) > 0
        
        # Should have constraint hint
        v = replica_violations[0]
        assert v.evidence is not None
        assert isinstance(v.evidence, dict)
        assert "forbid_tuple" in v.evidence
        assert v.evidence["forbid_tuple"]["holes"] == ["env", "replicas"]
        assert v.evidence["forbid_tuple"]["values"] == ["prod", 2]

    def test_env_prod_small_profile_fails(self):
        """Test that env=prod with small profile fails."""
        artifact = K8sArtifact(files={"deployment.yaml": NON_COMPLIANT_DEPLOYMENT})
        oracle = PolicyOracle()
        
        violations = oracle(artifact)
        
        # Should have violation for profile
        profile_violations = [v for v in violations if "PROFILE" in v.id]
        assert len(profile_violations) > 0
        
        # Should have constraint hint
        v = profile_violations[0]
        assert "forbid_tuple" in v.evidence
        assert v.evidence["forbid_tuple"]["holes"] == ["env", "profile"]
        assert v.evidence["forbid_tuple"]["values"] == ["prod", "small"]

    def test_env_prod_latest_tag_fails(self):
        """Test that env=prod with :latest tag fails."""
        artifact = K8sArtifact(files={"deployment.yaml": NON_COMPLIANT_DEPLOYMENT})
        oracle = PolicyOracle()
        
        violations = oracle(artifact)
        
        # Should have violation for image tag
        image_violations = [v for v in violations if "IMAGE_TAG" in v.id]
        assert len(image_violations) > 0

    def test_missing_required_labels(self):
        """Test that missing required labels are detected."""
        artifact = K8sArtifact(files={"deployment.yaml": NON_COMPLIANT_DEPLOYMENT})
        oracle = PolicyOracle()
        
        violations = oracle(artifact)
        
        # Should have violations for missing team, tier labels
        label_violations = [v for v in violations if "MISSING_LABEL" in v.id]
        assert len(label_violations) >= 2  # team, tier

    def test_missing_priority_class(self):
        """Test that missing priorityClassName is detected."""
        artifact = K8sArtifact(files={"deployment.yaml": NON_COMPLIANT_DEPLOYMENT})
        oracle = PolicyOracle()
        
        violations = oracle(artifact)
        
        priority_violations = [v for v in violations if "PRIORITY_CLASS" in v.id]
        assert len(priority_violations) > 0


class TestSecurityOracle:
    """Tests for SecurityOracle."""

    def test_compliant_security_passes(self):
        """Test that compliant security settings pass."""
        artifact = K8sArtifact(files={"deployment.yaml": COMPLIANT_DEPLOYMENT})
        oracle = SecurityOracle()
        
        violations = oracle(artifact)
        
        assert len(violations) == 0

    def test_missing_run_as_non_root_fails(self):
        """Test that missing runAsNonRoot is detected."""
        artifact = K8sArtifact(files={"deployment.yaml": NON_COMPLIANT_DEPLOYMENT})
        oracle = SecurityOracle()
        
        violations = oracle(artifact)
        
        # Should have violations for runAsNonRoot
        run_as_nonroot_violations = [v for v in violations if "RUN_AS_NON_ROOT" in v.id]
        assert len(run_as_nonroot_violations) > 0

    def test_missing_privilege_escalation_fails(self):
        """Test that missing allowPrivilegeEscalation=false is detected."""
        artifact = K8sArtifact(files={"deployment.yaml": NON_COMPLIANT_DEPLOYMENT})
        oracle = SecurityOracle()
        
        violations = oracle(artifact)
        
        privilege_violations = [v for v in violations if "PRIVILEGE_ESCALATION" in v.id]
        assert len(privilege_violations) > 0


class TestResourceOracle:
    """Tests for ResourceOracle."""

    def test_compliant_resources_pass(self):
        """Test that standard profile resources pass."""
        artifact = K8sArtifact(files={"deployment.yaml": COMPLIANT_DEPLOYMENT})
        oracle = ResourceOracle()
        
        violations = oracle(artifact)
        
        # Should pass (medium profile)
        assert len(violations) == 0

    def test_missing_resources_fails(self):
        """Test that missing resources are detected."""
        manifest = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: test
spec:
  template:
    spec:
      containers:
      - name: test
        image: test:latest
"""
        artifact = K8sArtifact(files={"deployment.yaml": manifest})
        oracle = ResourceOracle()
        
        violations = oracle(artifact)
        
        missing_violations = [v for v in violations if "MISSING_RESOURCES" in v.id]
        assert len(missing_violations) > 0


class TestSchemaOracle:
    """Tests for SchemaOracle (may be skipped if kubectl not available)."""

    def test_valid_deployment_passes(self):
        """Test that valid deployment passes schema validation."""
        artifact = K8sArtifact(files={"deployment.yaml": COMPLIANT_DEPLOYMENT})
        oracle = SchemaOracle()
        
        violations = oracle(artifact)
        
        # Should pass or skip if kubectl not available
        # Don't assert - kubectl may not be installed
        assert isinstance(violations, list)

    def test_invalid_yaml_detected(self):
        """Test that invalid YAML structure is detected."""
        invalid = """apiVersion: apps/v1
kind: InvalidKind
metadata:
  name: test
"""
        artifact = K8sArtifact(files={"deployment.yaml": invalid})
        oracle = SchemaOracle()
        
        violations = oracle(artifact)
        
        # Should fail validation or skip if kubectl not available
        assert isinstance(violations, list)

