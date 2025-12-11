"""LLM Adapter for CeLoR template generation.

This module provides the domain-agnostic LLM adapter that orchestrates:
1. Routing to domain-specific prompt builders
2. Calling vendor-specific LLM clients
3. Parsing responses into CeLoR structures (PatchTemplate, HoleSpace)

Architecture:
- adapter.py (this file): Vendor-agnostic, domain-aware orchestration
- clients/: Vendor-specific API wrappers (OpenAI, Anthropic, etc.)
- prompts/: Domain-specific prompt engineering (k8s.py, python.py, etc.)

Layer 2 of LLM architecture: Orchestrates between vendor clients and domain prompts.
"""

import json
import logging
from typing import Dict, List, Literal, Optional, Tuple

from celor.core.schema.artifact import Artifact
from celor.core.schema.patch_dsl import Patch, PatchOp
from celor.core.schema.violation import Violation
from celor.core.template import HoleSpace, PatchTemplate, deserialize_template

logger = logging.getLogger(__name__)

ClientType = Literal["openai", "anthropic"]
DomainType = Literal["k8s", "python", "json"]


class LLMAdapter:
    """Domain-agnostic LLM adapter for PatchTemplate generation.
    
    This class orchestrates the LLM integration:
    1. Creates appropriate vendor client (OpenAI, Anthropic)
    2. Routes to domain-specific prompt builder (k8s.py, python.py)
    3. Calls LLM and parses JSON response
    4. Returns CeLoR structures (PatchTemplate, HoleSpace)
    
    Example:
        >>> from celor.llm.adapter import LLMAdapter
        >>> 
        >>> adapter = LLMAdapter(client_type="openai", api_key="sk-...")
        >>> template, hole_space = adapter.propose_template(
        ...     artifact, violations, domain="k8s"
        ... )
        >>> # template is PatchTemplate with holes
        >>> # hole_space is dict of hole → possible values
    
    Architecture:
        clients/     → "How to call vendor APIs"
        adapter.py   → "Route domain → prompt → client → parse"
        prompts/     → "What to tell LLM about each domain"
    """
    
    def __init__(
        self,
        client_type: ClientType = "openai",
        **client_config
    ):
        """Initialize LLM adapter with specified client.
        
        Args:
            client_type: Which LLM vendor to use ("openai", "anthropic")
            **client_config: Configuration for the client (api_key, model, etc.)
                           If not provided, loads from config.json automatically
        
        Example:
            >>> adapter = LLMAdapter("openai", api_key="sk-...", model="gpt-4")
            >>> adapter = LLMAdapter()  # Auto-loads from config.json
        """
        self.client_type = client_type
        self.client_config = client_config
        
        # Auto-load from config.json if not provided
        if client_type == "openai":
            from celor.core.config import get_config_value
            if "api_key" not in client_config:
                api_key = get_config_value(["openai", "api_key"])
                if api_key:
                    client_config["api_key"] = api_key
            if "model" not in client_config:
                model = get_config_value(["openai", "model"])
                if model:
                    client_config["model"] = model
        
        self.client = self._create_client(client_type, client_config)
        
        logger.info(f"Initialized LLMAdapter with {client_type} client")
    
    def _create_client(self, client_type: ClientType, config: dict):
        """Factory for creating vendor-specific clients.
        
        Args:
            client_type: Vendor identifier
            config: Client configuration
            
        Returns:
            Client instance
            
        Raises:
            ValueError: If client_type is unknown
        """
        if client_type == "openai":
            from celor.llm.clients.openai import OpenAIClient
            return OpenAIClient(**config)
        elif client_type == "anthropic":
            # Future: Anthropic/Claude client
            raise NotImplementedError("Anthropic client not yet implemented")
        else:
            raise ValueError(f"Unknown client type: {client_type}")
    
    def propose_template(
        self,
        artifact: Artifact,
        violations: List[Violation],
        domain: DomainType = "k8s",
        previous_feedback: Optional[str] = None
    ) -> Tuple[PatchTemplate, HoleSpace]:
        """Generate PatchTemplate and HoleSpace using LLM.
        
        Main entry point for LLM-based template generation.
        Orchestrates: domain prompt → LLM call → parse response.
        
        Args:
            artifact: The artifact to repair
            violations: Oracle failures to address
            domain: Which domain (determines prompt builder)
            
        Returns:
            Tuple of (PatchTemplate, HoleSpace)
            
        Raises:
            ValueError: If domain is unknown
            Exception: If LLM call or parsing fails
            
        Example:
            >>> adapter = LLMAdapter("openai", api_key="...")
            >>> template, holes = adapter.propose_template(
            ...     artifact, violations, domain="k8s"
            ... )
        """
        logger.info(f"Generating template for domain={domain}")
        
        # Step 1: Build domain-specific prompt
        prompt = self._build_prompt(artifact, violations, domain, previous_feedback)
        logger.debug(f"Built prompt ({len(prompt)} chars)")
        
        # Step 2: Call LLM (vendor-agnostic)
        try:
            # Check if model supports response_format (newer models like gpt-4-turbo, gpt-4o)
            # Older models like gpt-4 don't support it, so we'll request JSON in the prompt instead
            model_name = getattr(self.client, 'model', None) or self.client_config.get('model', 'gpt-4')
            supports_json_mode = any(x in model_name.lower() for x in ['turbo', 'gpt-4o', 'gpt-3.5-turbo', 'o1'])
            
            # Add JSON instruction to prompt if model doesn't support response_format
            if not supports_json_mode:
                prompt = prompt + "\n\nIMPORTANT: Return ONLY valid JSON (no markdown, no code blocks, no explanations)."
            
            chat_kwargs = {
                "messages": [{
                    "role": "system",
                    "content": "You are an expert in program synthesis and repair."
                }, {
                    "role": "user",
                    "content": prompt
                }]
            }
            
            # Only add response_format if model supports it
            if supports_json_mode:
                chat_kwargs["response_format"] = {"type": "json_object"}
            
            response = self.client.chat(**chat_kwargs)
            logger.debug("Received LLM response")
            
            # If model doesn't support json_object, try to extract JSON from response
            if not supports_json_mode:
                # Try to extract JSON from markdown code blocks or plain text
                import re
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    response = json_match.group(0)
                    logger.debug("Extracted JSON from response")
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise
        
        # Step 3: Parse response into CeLoR structures
        try:
            template, hole_space = self._parse_response(response)
            logger.info(f"Parsed template with {len(template.ops)} ops, {len(hole_space)} holes")
            return template, hole_space
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.debug(f"Response was: {response[:500]}...")
            raise
    
    def _build_prompt(
        self,
        artifact: Artifact,
        violations: List[Violation],
        domain: DomainType,
        previous_feedback: Optional[str] = None
    ) -> str:
        """Route to domain-specific prompt builder.
        
        This method routes to the appropriate domain module
        in celor/llm/prompts/ based on the domain parameter.
        
        Args:
            artifact: Artifact to repair
            violations: Oracle failures
            domain: Domain identifier
            previous_feedback: Optional feedback from previous repair attempts
            
        Returns:
            Prompt string for LLM
            
        Raises:
            ValueError: If domain is unknown
        """
        if domain == "k8s":
            from celor.llm.prompts.k8s import build_k8s_prompt
            return build_k8s_prompt(artifact, violations, previous_feedback)
        elif domain == "python":
            from celor.llm.prompts.python import build_python_prompt
            return build_python_prompt(artifact, violations)
        else:
            raise ValueError(f"Unknown domain: {domain}. Supported: k8s, python")
    
    def _parse_response(
        self,
        response: str
    ) -> Tuple[PatchTemplate, HoleSpace]:
        """Parse LLM JSON response into PatchTemplate + HoleSpace.
        
        Expected JSON format:
        {
          "template": {
            "ops": [
              {"op": "EnsureLabel", "args": {"key": "env", "value": {"$hole": "env"}}},
              ...
            ]
          },
          "hole_space": {
            "env": ["staging-us", "production-us"],
            "replicas": [3, 4, 5],
            ...
          }
        }
        
        Args:
            response: JSON string from LLM
            
        Returns:
            Tuple of (PatchTemplate, HoleSpace)
            
        Raises:
            json.JSONDecodeError: If response is not valid JSON
            KeyError: If required fields missing
        """
        data = json.loads(response)
        
        # Parse template using existing deserializer
        if "template" not in data:
            raise KeyError("Response missing 'template' field")
        
        template = deserialize_template(data["template"])
        
        # Parse hole space (convert lists to sets)
        if "hole_space" not in data:
            raise KeyError("Response missing 'hole_space' field")
        
        hole_space: HoleSpace = {
            hole: set(values)
            for hole, values in data["hole_space"].items()
        }
        
        return template, hole_space
    
    def propose_concrete_patch(
        self,
        artifact: Artifact,
        violations: List[Violation],
        domain: DomainType = "k8s",
        previous_feedback: Optional[str] = None
    ) -> Patch:
        """Generate a concrete Patch (no holes) using LLM for pure-LLM baseline.
        
        This is for pure-LLM approach where LLM must provide complete,
        concrete values without any synthesis.
        
        Args:
            artifact: The artifact to repair
            violations: Oracle failures to address
            domain: Which domain (determines prompt builder)
            previous_feedback: Optional feedback from previous attempts
            
        Returns:
            Concrete Patch with all values filled (no holes)
        """
        logger.info(f"Generating concrete patch for domain={domain}")
        
        # Build prompt for concrete patch
        prompt = self._build_concrete_patch_prompt(artifact, violations, domain, previous_feedback)
        logger.debug(f"Built concrete patch prompt ({len(prompt)} chars)")
        
        # Call LLM
        try:
            model_name = getattr(self.client, 'model', None) or self.client_config.get('model', 'gpt-4')
            supports_json_mode = any(x in model_name.lower() for x in ['turbo', 'gpt-4o', 'gpt-3.5-turbo', 'o1'])
            
            if not supports_json_mode:
                prompt = prompt + "\n\nIMPORTANT: Return ONLY valid JSON (no markdown, no code blocks, no explanations)."
            
            chat_kwargs = {
                "messages": [{
                    "role": "system",
                    "content": "You are an expert in program synthesis and repair."
                }, {
                    "role": "user",
                    "content": prompt
                }]
            }
            
            if supports_json_mode:
                chat_kwargs["response_format"] = {"type": "json_object"}
            
            response = self.client.chat(**chat_kwargs)
            logger.debug("Received LLM response")
            
            if not supports_json_mode:
                import re
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    response = json_match.group(0)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise
        
        # Parse response into concrete Patch
        try:
            patch = self._parse_concrete_patch_response(response)
            logger.info(f"Parsed concrete patch with {len(patch.ops)} operations")
            return patch
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.debug(f"Response was: {response[:500]}...")
            raise
    
    def _build_concrete_patch_prompt(
        self,
        artifact: Artifact,
        violations: List[Violation],
        domain: DomainType,
        previous_feedback: Optional[str] = None
    ) -> str:
        """Build prompt for concrete patch generation (no holes)."""
        if domain == "k8s":
            from celor.llm.prompts.k8s import build_k8s_concrete_patch_prompt
            return build_k8s_concrete_patch_prompt(artifact, violations, previous_feedback)
        else:
            raise ValueError(f"Concrete patch generation not supported for domain: {domain}")
    
    def _parse_concrete_patch_response(self, response: str) -> Patch:
        """Parse LLM JSON response into concrete Patch (no holes).
        
        Expected format: {"patch": {"ops": [{"op": "...", "args": {...}}, ...]}}
        """
        data = json.loads(response)
        
        if "patch" not in data:
            raise KeyError("Response missing 'patch' field")
        
        patch_data = data["patch"]
        if "ops" not in patch_data:
            raise KeyError("Patch missing 'ops' field")
        
        ops = []
        for op_data in patch_data["ops"]:
            if "op" not in op_data or "args" not in op_data:
                raise KeyError(f"Operation missing 'op' or 'args': {op_data}")
            ops.append(PatchOp(op=op_data["op"], args=op_data["args"]))
        
        return Patch(ops=ops)
