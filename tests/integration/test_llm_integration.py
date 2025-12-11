"""Integration tests for LLM + Fix Bank interaction."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from celor.core.controller import repair_artifact
from celor.core.fixbank import FixBank
from celor.core.schema.violation import Violation
from celor.k8s.artifact import K8sArtifact
from celor.k8s.examples import LLM_EDITED_DEPLOYMENT, payments_api_template_and_holes
from celor.k8s.oracles import PolicyOracle, ResourceOracle, SecurityOracle
from celor.llm.adapter import LLMAdapter


class TestLLMIntegration:
    """Tests for LLM adapter integration."""

    @patch('openai.OpenAI')
    @patch('celor.core.config.get_config_value')
    def test_llm_with_openai_client(self, mock_get_config, mock_openai_class):
        """Test LLM integration with mocked OpenAI client."""
        # Mock config
        def config_side_effect(keys, default=None):
            key_tuple = tuple(keys) if isinstance(keys, list) else keys
            return {
                ("openai", "api_key"): "sk-test-key",
                ("openai", "model"): "gpt-4"
            }.get(key_tuple, default)
        
        mock_get_config.side_effect = config_side_effect
        
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "template": {
                "ops": [
                    {"op": "EnsureLabel", "args": {"scope": "podTemplate", "key": "env", "value": {"$hole": "env"}}},
                    {"op": "EnsureLabel", "args": {"scope": "podTemplate", "key": "team", "value": {"$hole": "team"}}},
                    {"op": "EnsureLabel", "args": {"scope": "podTemplate", "key": "tier", "value": {"$hole": "tier"}}},
                    {"op": "EnsureImageVersion", "args": {"container": "payments-api", "version": {"$hole": "version"}}},
                    {"op": "EnsureSecurityBaseline", "args": {"container": "payments-api"}},
                    {"op": "EnsureResourceProfile", "args": {"container": "payments-api", "profile": {"$hole": "profile"}}},
                    {"op": "EnsureReplicas", "args": {"replicas": {"$hole": "replicas"}}},
                    {"op": "EnsurePriorityClass", "args": {"name": {"$hole": "priority_class"}}}
                ]
            },
            "hole_space": {
                "env": ["production-us"],
                "team": ["payments"],
                "tier": ["backend"],
                "version": [
                    "123456789012.dkr.ecr.us-east-1.amazonaws.com/production-us/payments-api:prod-1.2.3",
                    "123456789012.dkr.ecr.us-east-1.amazonaws.com/production-us/payments-api:prod-1.2.4",
                    "123456789012.dkr.ecr.us-east-1.amazonaws.com/production-us/payments-api:prod-1.3.0"
                ],
                "profile": ["medium", "large"],
                "replicas": [3, 4, 5],
                "priority_class": ["critical", "high-priority"]
            }
        })
        
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        adapter = LLMAdapter()
        
        artifact = K8sArtifact(files={"deployment.yaml": LLM_EDITED_DEPLOYMENT})
        oracles = [PolicyOracle(), SecurityOracle(), ResourceOracle()]
        
        # Repair with LLM adapter but NO default_template_fn (forces LLM use)
        repaired, metadata = repair_artifact(
            artifact=artifact,
            template=None,  # No template provided
            hole_space=None,  # No hole space provided
            oracles=oracles,
            llm_adapter=adapter,
            default_template_fn=None  # No fallback - must use LLM
        )
        
        # Should succeed (mocked OpenAI returns valid template)
        assert metadata["status"] == "success"
        assert metadata["llm_calls"] == 1  # Should have called LLM

    @patch('openai.OpenAI')
    @patch('celor.core.config.get_config_value')
    def test_llm_only_called_on_fixbank_miss(self, mock_get_config, mock_openai_class):
        """Test that LLM is only called when Fix Bank misses."""
        # Mock config
        def config_side_effect(keys, default=None):
            key_tuple = tuple(keys) if isinstance(keys, list) else keys
            return {
                ("openai", "api_key"): "sk-test-key",
                ("openai", "model"): "gpt-4"
            }.get(key_tuple, default)
        
        mock_get_config.side_effect = config_side_effect
        
        # Mock OpenAI response with full template
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "template": {
                "ops": [
                    {"op": "EnsureLabel", "args": {"scope": "podTemplate", "key": "env", "value": {"$hole": "env"}}},
                    {"op": "EnsureLabel", "args": {"scope": "podTemplate", "key": "team", "value": {"$hole": "team"}}},
                    {"op": "EnsureLabel", "args": {"scope": "podTemplate", "key": "tier", "value": {"$hole": "tier"}}},
                    {"op": "EnsureImageVersion", "args": {"container": "payments-api", "version": {"$hole": "version"}}},
                    {"op": "EnsureSecurityBaseline", "args": {"container": "payments-api"}},
                    {"op": "EnsureResourceProfile", "args": {"container": "payments-api", "profile": {"$hole": "profile"}}},
                    {"op": "EnsureReplicas", "args": {"replicas": {"$hole": "replicas"}}},
                    {"op": "EnsurePriorityClass", "args": {"name": {"$hole": "priority_class"}}}
                ]
            },
            "hole_space": {
                "env": ["production-us"],
                "team": ["payments"],
                "tier": ["backend"],
                "version": [
                    "123456789012.dkr.ecr.us-east-1.amazonaws.com/production-us/payments-api:prod-1.2.3",
                    "123456789012.dkr.ecr.us-east-1.amazonaws.com/production-us/payments-api:prod-1.2.4",
                    "123456789012.dkr.ecr.us-east-1.amazonaws.com/production-us/payments-api:prod-1.3.0"
                ],
                "profile": ["medium", "large"],
                "replicas": [3, 4, 5],
                "priority_class": ["critical", "high-priority"]
            }
        })
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w') as f:
            fixbank_path = f.name
        
        try:
            adapter = LLMAdapter()
            artifact = K8sArtifact(files={"deployment.yaml": LLM_EDITED_DEPLOYMENT})
            oracles = [PolicyOracle(), SecurityOracle(), ResourceOracle()]
            
            # First run - Fix Bank empty, should call LLM
            fixbank1 = FixBank(fixbank_path)
            _, metadata1 = repair_artifact(
                artifact=artifact,
                oracles=oracles,
                fixbank=fixbank1,
                llm_adapter=adapter,
                default_template_fn=payments_api_template_and_holes
            )
            
            assert metadata1["status"] == "success"
            assert not metadata1["fixbank_hit"]  # MISS
            
            # Second run - Fix Bank has entry, should NOT call LLM
            fixbank2 = FixBank(fixbank_path)
            _, metadata2 = repair_artifact(
                artifact=artifact,
                oracles=oracles,
                fixbank=fixbank2,
                llm_adapter=adapter,
                default_template_fn=payments_api_template_and_holes
            )
            
            assert metadata2["status"] == "success"
            assert metadata2["fixbank_hit"]  # HIT
            assert metadata2["llm_calls"] == 0  # No LLM call (reused Fix Bank)
            
        finally:
            Path(fixbank_path).unlink()

    def test_llm_fallback_on_error(self):
        """Test that errors fallback to default template."""
        # Create adapter that will fail
        class FailingAdapter:
            def propose_template(self, *args, **kwargs):
                raise Exception("Mock LLM failure")
        
        adapter = FailingAdapter()
        artifact = K8sArtifact(files={"deployment.yaml": LLM_EDITED_DEPLOYMENT})
        oracles = [PolicyOracle(), SecurityOracle(), ResourceOracle()]
        
        # Should fallback to default template
        repaired, metadata = repair_artifact(
            artifact=artifact,
            oracles=oracles,
            llm_adapter=adapter,
            default_template_fn=payments_api_template_and_holes
        )
        
        # Should still succeed using fallback
        assert metadata["status"] == "success"

    @patch('openai.OpenAI')
    @patch('celor.core.config.get_config_value')
    def test_openai_generated_template_works_for_synthesis(self, mock_get_config, mock_openai_class):
        """Test that OpenAI-generated template actually works for synthesis."""
        # Mock config
        def config_side_effect(keys, default=None):
            key_tuple = tuple(keys) if isinstance(keys, list) else keys
            return {
                ("openai", "api_key"): "sk-test-key",
                ("openai", "model"): "gpt-4"
            }.get(key_tuple, default)
        
        mock_get_config.side_effect = config_side_effect
        
        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "template": {
                "ops": [
                    {"op": "EnsureLabel", "args": {"scope": "podTemplate", "key": "env", "value": {"$hole": "env"}}},
                    {"op": "EnsureReplicas", "args": {"replicas": {"$hole": "replicas"}}}
                ]
            },
            "hole_space": {
                "env": ["staging-us", "production-us"],
                "replicas": [3, 4, 5]
            }
        })
        
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        adapter = LLMAdapter()
        
        artifact = K8sArtifact(files={"deployment.yaml": LLM_EDITED_DEPLOYMENT})
        violations = [
            Violation("policy.TEST", "test", [], "error")
        ]
        
        # Get template from mocked OpenAI
        template, hole_space = adapter.propose_template(artifact, violations, domain="k8s")
        
        # Verify it's a valid template
        assert len(template.ops) > 0
        assert len(hole_space) > 0
        
        # Verify hole space has sets (not lists)
        for hole, values in hole_space.items():
            assert isinstance(values, set), f"hole_space[{hole}] should be set, got {type(values)}"


class TestLLMPrompts:
    """Tests for prompt building."""

    @patch('openai.OpenAI')
    @patch('celor.core.config.get_config_value')
    def test_k8s_prompt_includes_violations(self, mock_get_config, mock_openai_class):
        """Test that K8s prompt includes violation information."""
        # Mock config
        def config_side_effect(keys, default=None):
            key_tuple = tuple(keys) if isinstance(keys, list) else keys
            return {
                ("openai", "api_key"): "sk-test-key",
                ("openai", "model"): "gpt-4"
            }.get(key_tuple, default)
        
        mock_get_config.side_effect = config_side_effect
        
        # Mock OpenAI
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        from celor.llm.prompts.k8s import build_k8s_prompt
        
        artifact = K8sArtifact(files={"deployment.yaml": LLM_EDITED_DEPLOYMENT})
        violations = [
            Violation("policy.ENV_PROD_REPLICA_COUNT", "replicas too low", [], "error"),
            Violation("security.NO_RUN_AS_NON_ROOT", "must run as non-root", [], "error")
        ]
        
        prompt = build_k8s_prompt(artifact, violations)
        
        # Should mention the violations
        assert "ENV_PROD_REPLICA_COUNT" in prompt or "replicas" in prompt.lower()
        assert "RUN_AS_NON_ROOT" in prompt or "non-root" in prompt.lower()

    def test_k8s_prompt_includes_patchdsl_docs(self):
        """Test that K8s prompt includes PatchDSL documentation."""
        from celor.llm.prompts.k8s import build_k8s_prompt
        
        artifact = K8sArtifact(files={"deployment.yaml": "apiVersion: apps/v1\nkind: Deployment"})
        violations = []
        
        prompt = build_k8s_prompt(artifact, violations)
        
        # Should document K8s operations
        operations = ["EnsureLabel", "EnsureImageVersion", "EnsureSecurityBaseline",
                     "EnsureResourceProfile", "EnsureReplicas", "EnsurePriorityClass"]
        
        for op in operations:
            assert op in prompt, f"Prompt should document {op} operation"
