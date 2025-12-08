"""OpenAI client - Pure API wrapper.

This module provides a clean OpenAI API client with zero domain logic.
It's vendor-specific but domain-agnostic, making it reusable across projects.

Layer 1 of LLM architecture: Vendor API wrapper only.
"""

from typing import Any, Dict, List, Optional

from celor.core.config import get_config_value


class OpenAIClient:
    """Pure OpenAI API wrapper - no domain logic.
    
    This class handles only OpenAI API communication.
    It knows nothing about CeLoR, PatchDSL, or specific domains.
    
    Configuration priority: explicit parameter > config.json > ValueError
    
    Example:
        >>> client = OpenAIClient(api_key="sk-...")
        >>> response = client.chat([{"role": "user", "content": "Hello"}])
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        timeout: float = 30.0
    ):
        """Initialize OpenAI client.
        
        Args:
            api_key: OpenAI API key (loads from config.json if None)
            model: Model to use (loads from config.json if None, default: "gpt-4")
            temperature: Sampling temperature (default: 0.7)
            timeout: Request timeout in seconds (default: 30.0)
        """
        # Priority: explicit parameter > config.json > raise ValueError
        self.api_key = api_key or get_config_value(["openai", "api_key"])
        self.model = model or get_config_value(["openai", "model"], default="gpt-4")
        self.temperature = temperature
        self.timeout = timeout
        
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set in config.json: "
                "{'openai': {'api_key': 'sk-...'}}"
            )
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        response_format: Optional[Dict[str, str]] = None,
        temperature: Optional[float] = None,
        timeout: Optional[float] = None
    ) -> str:
        """Send chat messages to OpenAI API.
        
        Pure API wrapper - no domain logic, no parsing.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            response_format: Optional format spec (e.g., {"type": "json_object"})
            temperature: Override default temperature
            timeout: Override default timeout
            
        Returns:
            Response text from OpenAI
            
        Raises:
            ImportError: If openai package not installed
            Exception: On API errors (includes timeout)
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package required. Install with: pip install openai")
        
        client = OpenAI(api_key=self.api_key, timeout=timeout or self.timeout)
        
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format=response_format,
                temperature=temperature or self.temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            # Improve error messages
            error_msg = str(e)
            if "timeout" in error_msg.lower():
                raise TimeoutError(
                    f"OpenAI API request timed out after {timeout or self.timeout} seconds. "
                    f"Error: {error_msg}"
                ) from e
            elif "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
                raise ValueError(
                    f"OpenAI API authentication failed. "
                    f"Check your API key in config.json. Error: {error_msg}"
                ) from e
            else:
                raise Exception(f"OpenAI API error: {error_msg}") from e
