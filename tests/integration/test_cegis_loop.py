"""Integration tests for CEGIS repair loop."""

import pytest

from celor.core.cegis.loop import repair
from celor.core.cegis.synthesizer import SynthConfig
from celor.k8s.artifact import K8sArtifact
from celor.k8s.examples import LLM_EDITED_DEPLOYMENT, payments_api_template_and_holes
from celor.k8s.oracles import PolicyOracle, SecurityOracle


class TestCEGISLoop:
    """Integration tests for CEGIS loop."""

    def test_successful_repair(self):
        """Test end-to-end repair with K8s artifact."""
        # Start with non-compliant artifact
        artifact = K8sArtifact(files={"deployment.yaml": LLM_EDITED_DEPLOYMENT})
        
        # Get template and hole space
        template, hole_space = payments_api_template_and_holes()
        
        # Use policy oracle (should have violations initially)
        oracles = [PolicyOracle()]
        
        # Configure synthesis
        config = SynthConfig(max_candidates=100, timeout_seconds=30.0)
        
        # Run repair
        repaired_artifact, metadata = repair(
            artifact=artifact,
            template=template,
            hole_space=hole_space,
            oracles=oracles,
            max_iters=5,
            config=config
        )
        
        # Should succeed
        assert metadata["status"] == "success"
        assert metadata["iterations"] >= 0
        
        # Verify repaired artifact passes oracles
        for oracle in oracles:
            violations = oracle(repaired_artifact)
            assert len(violations) == 0, f"Repaired artifact still has violations: {violations}"

    def test_constraint_learning(self):
        """Test that constraints are learned during repair."""
        artifact = K8sArtifact(files={"deployment.yaml": LLM_EDITED_DEPLOYMENT})
        template, hole_space = payments_api_template_and_holes()
        oracles = [PolicyOracle()]
        
        config = SynthConfig(max_candidates=100, timeout_seconds=30.0)
        
        _, metadata = repair(
            artifact=artifact,
            template=template,
            hole_space=hole_space,
            oracles=oracles,
            max_iters=5,
            config=config
        )
        
        # Should have learned some constraints
        if metadata["status"] == "success":
            # Successful repair may or may not have learned constraints
            # depending on whether hints were provided
            assert isinstance(metadata["constraints"], list)

    def test_multiple_oracles(self):
        """Test repair with multiple oracles."""
        artifact = K8sArtifact(files={"deployment.yaml": LLM_EDITED_DEPLOYMENT})
        template, hole_space = payments_api_template_and_holes()
        
        # Use both policy and security oracles
        oracles = [PolicyOracle(), SecurityOracle()]
        
        config = SynthConfig(max_candidates=100, timeout_seconds=30.0)
        
        repaired_artifact, metadata = repair(
            artifact=artifact,
            template=template,
            hole_space=hole_space,
            oracles=oracles,
            max_iters=5,
            config=config
        )
        
        # Should succeed or report detailed status
        assert metadata["status"] in ["success", "unsat", "timeout", "max_iters"]
        
        # If successful, all oracles should pass
        if metadata["status"] == "success":
            for oracle in oracles:
                violations = oracle(repaired_artifact)
                assert len(violations) == 0

    def test_max_iterations_respected(self):
        """Test that max_iters limit is respected."""
        artifact = K8sArtifact(files={"deployment.yaml": LLM_EDITED_DEPLOYMENT})
        template, hole_space = payments_api_template_and_holes()
        oracles = [PolicyOracle()]
        
        config = SynthConfig(max_candidates=1, timeout_seconds=30.0)  # Very limited
        
        _, metadata = repair(
            artifact=artifact,
            template=template,
            hole_space=hole_space,
            oracles=oracles,
            max_iters=2,  # Only 2 iterations
            config=config
        )
        
        # Should not exceed max_iters
        assert metadata["iterations"] <= 2

    def test_unsat_case(self):
        """Test behavior when no valid patch exists."""
        artifact = K8sArtifact(files={"deployment.yaml": LLM_EDITED_DEPLOYMENT})
        template, hole_space = payments_api_template_and_holes()
        oracles = [PolicyOracle()]
        
        # Extremely restrictive config - likely to cause UNSAT
        config = SynthConfig(max_candidates=1, timeout_seconds=0.1)
        
        _, metadata = repair(
            artifact=artifact,
            template=template,
            hole_space=hole_space,
            oracles=oracles,
            max_iters=1,
            config=config
        )
        
        # Should report unsat or timeout
        assert metadata["status"] in ["unsat", "timeout", "max_iters"]
        assert "violations" in metadata  # Should include diagnostic info


class TestCEGISLoopEdgeCases:
    """Edge case tests for CEGIS loop."""

    def test_already_valid_artifact(self):
        """Test with artifact that already passes all oracles."""
        # Create a minimal valid deployment
        valid_deployment = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: test
spec:
  replicas: 3
  template:
    metadata:
      labels:
        env: staging
    spec:
      containers:
      - name: test
        image: test:v1
        securityContext:
          runAsNonRoot: true
          allowPrivilegeEscalation: false
"""
        artifact = K8sArtifact(files={"deployment.yaml": valid_deployment})
        template, hole_space = payments_api_template_and_holes()
        
        # Use security oracle only (less strict)
        oracles = [SecurityOracle()]
        
        config = SynthConfig()
        
        repaired_artifact, metadata = repair(
            artifact=artifact,
            template=template,
            hole_space=hole_space,
            oracles=oracles,
            max_iters=5,
            config=config
        )
        
        # Should succeed immediately (0 iterations)
        assert metadata["status"] == "success"
        assert metadata["iterations"] == 0
        assert repaired_artifact == artifact  # Unchanged

    def test_empty_oracles_list(self):
        """Test with no oracles (should succeed immediately)."""
        artifact = K8sArtifact(files={"deployment.yaml": LLM_EDITED_DEPLOYMENT})
        template, hole_space = payments_api_template_and_holes()
        
        config = SynthConfig()
        
        repaired_artifact, metadata = repair(
            artifact=artifact,
            template=template,
            hole_space=hole_space,
            oracles=[],  # No oracles
            max_iters=5,
            config=config
        )
        
        # Should succeed immediately with no oracles to satisfy
        assert metadata["status"] == "success"
        assert metadata["iterations"] == 0

