"""Tests for LLM adapter."""

import json
from unittest.mock import MagicMock, patch

import pytest

from celor.core.schema.patch_dsl import PatchOp
from celor.core.schema.violation import Violation
from celor.core.template import HoleRef, PatchTemplate
from celor.k8s.artifact import K8sArtifact
from celor.llm.adapter import LLMAdapter


class TestLLMAdapter:
    """Tests for LLMAdapter class."""

    @patch('openai.OpenAI')
    @patch('celor.core.config.get_config_value')
    def test_create_with_openai_client(self, mock_get_config, mock_openai_class):
        """Test creating adapter with OpenAI client."""
        # Mock config to return API key
        def config_side_effect(keys, default=None):
            key_tuple = tuple(keys) if isinstance(keys, list) else keys
            return {
                ("openai", "api_key"): "sk-test-key",
                ("openai", "model"): "gpt-4"
            }.get(key_tuple, default)
        
        mock_get_config.side_effect = config_side_effect
        
        # Mock OpenAI client
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        adapter = LLMAdapter()
        
        assert adapter.client_type == "openai"
        assert adapter.client is not None

    @patch('openai.OpenAI')
    @patch('celor.core.config.get_config_value')
    def test_routing_to_k8s_prompts(self, mock_get_config, mock_openai_class):
        """Test that k8s domain routes to k8s prompt builder."""
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
        
        adapter = LLMAdapter()
        
        artifact = K8sArtifact(files={"deployment.yaml": "apiVersion: apps/v1\nkind: Deployment"})
        violations = [
            Violation("policy.TEST", "test violation", [], "error")
        ]
        
        # Should route to k8s prompts
        prompt = adapter._build_prompt(artifact, violations, domain="k8s")
        
        # Verify prompt contains K8s-specific content
        assert "K8s PatchDSL" in prompt or "Kubernetes" in prompt
        assert "EnsureLabel" in prompt  # K8s operation

    @patch('openai.OpenAI')
    @patch('celor.core.config.get_config_value')
    def test_parse_valid_response(self, mock_get_config, mock_openai_class):
        """Test parsing valid LLM JSON response."""
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
        
        adapter = LLMAdapter()
        
        # Valid response JSON
        response = json.dumps({
            "template": {
                "ops": [
                    {
                        "op": "EnsureLabel",
                        "args": {"scope": "podTemplate", "key": "env", "value": {"$hole": "env"}}
                    },
                    {
                        "op": "EnsureReplicas",
                        "args": {"replicas": {"$hole": "replicas"}}
                    }
                ]
            },
            "hole_space": {
                "env": ["staging-us", "production-us"],
                "replicas": [3, 4, 5]
            }
        })
        
        template, hole_space = adapter._parse_response(response)
        
        # Verify template
        assert len(template.ops) == 2
        assert template.ops[0].op == "EnsureLabel"
        
        # Verify hole space
        assert "env" in hole_space
        assert hole_space["env"] == {"staging-us", "production-us"}
        assert hole_space["replicas"] == {3, 4, 5}

    @patch('openai.OpenAI')
    @patch('celor.core.config.get_config_value')
    def test_parse_invalid_json_raises_error(self, mock_get_config, mock_openai_class):
        """Test that invalid JSON raises error."""
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
        
        adapter = LLMAdapter()
        
        with pytest.raises(json.JSONDecodeError):
            adapter._parse_response("not valid json")

    @patch('openai.OpenAI')
    @patch('celor.core.config.get_config_value')
    def test_parse_missing_template_raises_error(self, mock_get_config, mock_openai_class):
        """Test that missing template field raises error."""
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
        
        adapter = LLMAdapter()
        
        response = json.dumps({
            "hole_space": {"x": [1, 2]}
            # Missing "template"
        })
        
        with pytest.raises(KeyError, match="template"):
            adapter._parse_response(response)

    @patch('openai.OpenAI')
    @patch('celor.core.config.get_config_value')
    def test_parse_missing_hole_space_raises_error(self, mock_get_config, mock_openai_class):
        """Test that missing hole_space field raises error."""
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
        
        adapter = LLMAdapter()
        
        response = json.dumps({
            "template": {"ops": []}
            # Missing "hole_space"
        })
        
        with pytest.raises(KeyError, match="hole_space"):
            adapter._parse_response(response)

    @patch('openai.OpenAI')
    @patch('celor.core.config.get_config_value')
    def test_unknown_domain_raises_error(self, mock_get_config, mock_openai_class):
        """Test that unknown domain raises error."""
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
        
        adapter = LLMAdapter()
        
        artifact = K8sArtifact(files={})
        violations = []
        
        with pytest.raises(ValueError, match="Unknown domain"):
            adapter._build_prompt(artifact, violations, domain="invalid")

    def test_unknown_client_type_raises_error(self):
        """Test that unknown client type raises error."""
        # This test doesn't need mocking - it just tests error handling
        # The error happens before any client creation
        with pytest.raises(ValueError, match="Unknown client type"):
            LLMAdapter(client_type="invalid")


class TestLLMAdapterIntegration:
    """Integration tests with mocked OpenAI."""

    @patch('openai.OpenAI')
    @patch('celor.core.config.get_config_value')
    def test_end_to_end_with_mock(self, mock_get_config, mock_openai_class):
        """Test complete workflow with mocked OpenAI."""
        # Mock config
        def config_side_effect(keys, default=None):
            key_tuple = tuple(keys) if isinstance(keys, list) else keys
            return {
                ("openai", "api_key"): "sk-test-key",
                ("openai", "model"): "gpt-4"
            }.get(key_tuple, default)
        
        mock_get_config.side_effect = config_side_effect
        
        # Mock OpenAI API response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "template": {
                "ops": [
                    {
                        "op": "EnsureLabel",
                        "args": {"scope": "podTemplate", "key": "env", "value": {"$hole": "env"}}
                    },
                    {
                        "op": "EnsureReplicas",
                        "args": {"replicas": {"$hole": "replicas"}}
                    }
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
        
        artifact = K8sArtifact(files={"deployment.yaml": "apiVersion: apps/v1\nkind: Deployment"})
        violations = [
            Violation("policy.TEST", "test", [], "error")
        ]
        
        # This will call mocked OpenAI which should return valid template
        template, hole_space = adapter.propose_template(
            artifact, violations, domain="k8s"
        )
        
        # Verify we got valid structures
        assert isinstance(template, PatchTemplate)
        assert isinstance(hole_space, dict)
        assert len(template.ops) > 0
