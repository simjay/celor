"""Tests for K8s prompt engineering."""

import pytest

from celor.core.schema.violation import Violation
from celor.k8s.artifact import K8sArtifact
from celor.k8s.examples import LLM_EDITED_DEPLOYMENT
from celor.llm.prompts.k8s import (
    build_k8s_prompt,
    extract_manifest_snippet,
    format_violations,
    get_example_templates,
    get_patchdsl_docs,
)


class TestK8sPromptBuilding:
    """Tests for K8s prompt building."""

    def test_build_k8s_prompt_structure(self):
        """Test that K8s prompt has expected structure."""
        artifact = K8sArtifact(files={"deployment.yaml": LLM_EDITED_DEPLOYMENT})
        violations = [
            Violation("policy.REPLICA_COUNT", "replicas too low", [], "error"),
            Violation("security.NO_RUN_AS_NON_ROOT", "must run as non-root", [], "error")
        ]
        
        prompt = build_k8s_prompt(artifact, violations)
        
        # Should contain key sections
        assert "Kubernetes" in prompt or "K8s" in prompt
        assert "PatchDSL" in prompt
        assert "violations" in prompt.lower() or "failures" in prompt.lower()
        assert "EnsureLabel" in prompt  # Should document operations
        assert "EnsureReplicas" in prompt
        assert "$hole" in prompt  # Should explain hole syntax
        assert "json" in prompt.lower()  # Should request JSON

    def test_extract_manifest_snippet(self):
        """Test manifest snippet extraction."""
        artifact = K8sArtifact(files={"deployment.yaml": LLM_EDITED_DEPLOYMENT})
        
        snippet = extract_manifest_snippet(artifact)
        
        # Should include key info
        assert "metadata" in snippet or "name" in snippet
        assert "replicas" in snippet
        assert "image" in snippet

    def test_format_violations(self):
        """Test violation formatting."""
        violations = [
            Violation("policy.ERROR1", "message 1", [], "error"),
            Violation("policy.ERROR2", "message 2", [], "error", 
                     evidence={"error_code": "ERR2"}),
            Violation("security.ERROR3", "message 3", [], "error")
        ]
        
        formatted = format_violations(violations)
        
        # Should list all violations
        assert "ERROR1" in formatted
        assert "ERROR2" in formatted
        assert "ERROR3" in formatted
        
        # Should group by oracle
        assert "POLICY" in formatted
        assert "SECURITY" in formatted
        
        # Should include error codes
        assert "ERR2" in formatted

    def test_format_empty_violations(self):
        """Test formatting with no violations."""
        formatted = format_violations([])
        
        assert "compliant" in formatted.lower() or "no violations" in formatted.lower()

    def test_get_patchdsl_docs(self):
        """Test getting PatchDSL documentation."""
        docs = get_patchdsl_docs()
        
        # Should document all K8s operations
        assert "EnsureLabel" in docs
        assert "EnsureImageVersion" in docs
        assert "EnsureSecurityBaseline" in docs
        assert "EnsureResourceProfile" in docs
        assert "EnsureReplicas" in docs
        assert "EnsurePriorityClass" in docs
        
        # Should explain hole syntax
        assert "$hole" in docs

    def test_get_example_templates(self):
        """Test getting example templates."""
        examples = get_example_templates()
        
        # Should be valid JSON
        assert "{" in examples
        assert "template" in examples
        assert "hole_space" in examples


