"""End-to-end integration tests for K8s repair workflow."""

import tempfile
from pathlib import Path

import pytest

from celor.core.cegis.loop import repair
from celor.core.cegis.synthesizer import SynthConfig
from celor.k8s.artifact import K8sArtifact
from celor.k8s.examples import (
    BASELINE_DEPLOYMENT,
    LLM_EDITED_DEPLOYMENT,
    payments_api_template_and_holes,
)
from celor.k8s.oracles import PolicyOracle, ResourceOracle, SecurityOracle


class TestEndToEndRepair:
    """End-to-end tests for complete repair workflow."""

    def test_baseline_already_compliant(self):
        """Test that baseline deployment already passes all oracles."""
        artifact = K8sArtifact(files={"deployment.yaml": BASELINE_DEPLOYMENT})
        oracles = [PolicyOracle(), SecurityOracle(), ResourceOracle()]
        
        # Check all oracles
        all_violations = []
        for oracle in oracles:
            violations = oracle(artifact)
            all_violations.extend(violations)
        
        # Baseline should pass
        assert len(all_violations) == 0, \
            f"Baseline should pass all oracles, got {len(all_violations)} violations"

    def test_llm_edit_has_violations(self):
        """Test that LLM-edited manifest fails oracles."""
        artifact = K8sArtifact(files={"deployment.yaml": LLM_EDITED_DEPLOYMENT})
        oracles = [PolicyOracle(), SecurityOracle(), ResourceOracle()]
        
        # Check all oracles
        all_violations = []
        for oracle in oracles:
            violations = oracle(artifact)
            all_violations.extend(violations)
        
        # LLM edit should have violations
        assert len(all_violations) > 0, \
            "LLM-edited manifest should have violations"
        
        # Should include expected violation types
        violation_ids = [v.id for v in all_violations]
        
        # At minimum, should have policy violations
        policy_violations = [v for v in all_violations if "policy" in v.id.lower()]
        assert len(policy_violations) > 0, "Should have policy violations"

    def test_end_to_end_repair_succeeds(self):
        """Test that repair workflow successfully fixes violations."""
        # Start with non-compliant artifact
        artifact = K8sArtifact(files={"deployment.yaml": LLM_EDITED_DEPLOYMENT})
        
        # Setup
        template, hole_space = payments_api_template_and_holes()
        oracles = [PolicyOracle(), SecurityOracle(), ResourceOracle()]
        config = SynthConfig(max_candidates=100, timeout_seconds=30.0)
        
        # Verify initial violations exist
        initial_violations = []
        for oracle in oracles:
            initial_violations.extend(oracle(artifact))
        assert len(initial_violations) > 0, "Should start with violations"
        
        # Run repair
        repaired_artifact, metadata = repair(
            artifact=artifact,
            template=template,
            hole_space=hole_space,
            oracles=oracles,
            max_iters=5,
            config=config
        )
        
        # Verify success
        assert metadata["status"] == "success", \
            f"Repair should succeed, got {metadata['status']}"
        
        # Verify all oracles now pass
        final_violations = []
        for oracle in oracles:
            violations = oracle(repaired_artifact)
            final_violations.extend(violations)
        
        assert len(final_violations) == 0, \
            f"Repaired artifact should pass all oracles, got {len(final_violations)} violations: {final_violations}"
        
        # Verify artifact changed
        assert repaired_artifact != artifact, "Artifact should be modified"
        
        # Verify metadata
        assert metadata["iterations"] >= 0
        assert metadata["tried_candidates"] > 0
        assert isinstance(metadata["constraints"], list)

    def test_repaired_manifest_writes_correctly(self):
        """Test that repaired manifest can be written to disk."""
        artifact = K8sArtifact(files={"deployment.yaml": LLM_EDITED_DEPLOYMENT})
        template, hole_space = payments_api_template_and_holes()
        oracles = [PolicyOracle(), SecurityOracle(), ResourceOracle()]
        
        # Repair
        config = SynthConfig(max_candidates=100, timeout_seconds=30.0)
        repaired_artifact, metadata = repair(
            artifact, template, hole_space, oracles,
            max_iters=5, config=config
        )
        
        assert metadata["status"] == "success"
        
        # Write to temp dir
        with tempfile.TemporaryDirectory() as tmpdir:
            repaired_artifact.write_to_dir(tmpdir)
            
            # Verify file exists
            output_file = Path(tmpdir) / "deployment.yaml"
            assert output_file.exists()
            
            # Verify content is valid YAML
            content = output_file.read_text()
            assert "apiVersion:" in content
            assert "kind: Deployment" in content
            
            # Reload and verify still passes
            reloaded = K8sArtifact.from_file(str(output_file))
            all_violations = []
            for oracle in oracles:
                all_violations.extend(oracle(reloaded))
            assert len(all_violations) == 0

    def test_user_intent_preserved(self):
        """Test that repair preserves user intent (env=prod context)."""
        artifact = K8sArtifact(files={"deployment.yaml": LLM_EDITED_DEPLOYMENT})
        template, hole_space = payments_api_template_and_holes()
        oracles = [PolicyOracle(), SecurityOracle(), ResourceOracle()]
        
        config = SynthConfig(max_candidates=100, timeout_seconds=30.0)
        repaired_artifact, metadata = repair(
            artifact, template, hole_space, oracles,
            max_iters=5, config=config
        )
        
        assert metadata["status"] == "success"
        
        # Check that env=prod is preserved (user intent)
        from ruamel.yaml import YAML
        yaml = YAML()
        manifest = yaml.load(repaired_artifact.files["deployment.yaml"])
        
        env_label = (manifest.get("spec", {})
                    .get("template", {})
                    .get("metadata", {})
                    .get("labels", {})
                    .get("env"))
        
        assert env_label == "production-us", "Should preserve env=production-us from user intent"


class TestDemoFunction:
    """Tests for demo_repair function."""

    def test_demo_runs_successfully(self):
        """Test that demo function runs without errors."""
        from celor.k8s.demo import demo_repair
        
        repaired, metadata = demo_repair(
            input_file=None,  # Use example
            output_dir=None,  # Don't write
            verbose=False
        )
        
        assert metadata["status"] == "success"
        assert repaired is not None

    def test_demo_writes_output(self):
        """Test that demo can write output files."""
        from celor.k8s.demo import demo_repair
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repaired, metadata = demo_repair(
                input_file=None,
                output_dir=tmpdir,
                verbose=False
            )
            
            assert metadata["status"] == "success"
            
            # Check file was written
            output_file = Path(tmpdir) / "deployment.yaml"
            assert output_file.exists()

