"""OpenAI client - Pure API wrapper.

This module provides a clean OpenAI API client with zero domain logic.
It's vendor-specific but domain-agnostic, making it reusable across projects.

Layer 1 of LLM architecture: Vendor API wrapper only.
"""

import logging
import time
from typing import Any, Dict, List, Optional
from openai import APIConnectionError, APITimeoutError, RateLimitError, APIError
from openai import OpenAI
from celor.core.config import get_config_value

logger = logging.getLogger(__name__)


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
        
        self._client = OpenAI(
            api_key=self.api_key,
            timeout=self.timeout,
            max_retries=0  # We handle retries ourselves with better error logging
        )
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        response_format: Optional[Dict[str, str]] = None,
        temperature: Optional[float] = None,
        timeout: Optional[float] = None,
        max_retries: int = 3
    ) -> str:
        """Send chat messages to OpenAI API with retry logic.
        
        Pure API wrapper - no domain logic, no parsing.
        Retries on connection errors with exponential backoff.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            response_format: Optional format spec (e.g., {"type": "json_object"})
            temperature: Override default temperature
            timeout: Override default timeout
            max_retries: Maximum number of retry attempts (default: 3)
            
        Returns:
            Response text from OpenAI
            
        Raises:
            ImportError: If openai package not installed
            Exception: On API errors (includes timeout)
        """
        def _create_fresh_client():
            """Create a fresh OpenAI client instance."""
            return OpenAI(
                api_key=self.api_key,
                timeout=timeout or self.timeout,
                max_retries=0
            )
        
        # Start with the client from __init__, only recreate on APIConnectionError
        client = self._client
        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_format=response_format,
                    temperature=temperature or self.temperature
                )
                return response.choices[0].message.content
            except APIConnectionError as e:
                # Connection errors - recreate client and retry with longer delays
                last_exception = e
                error_cause = str(e.__cause__) if e.__cause__ else "None"
                logger.error(
                    f"OpenAI APIConnectionError (attempt {attempt + 1}/{max_retries + 1}): "
                    f"Type: {type(e).__name__}, Message: {str(e)}, "
                    f"Cause: {error_cause}"
                )
                if attempt < max_retries:
                    # Longer wait times for DNS/connection issues
                    wait_time = 2 + (2 ** attempt) + (attempt * 1.0)
                    logger.warning(f"Recreating client and retrying in {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    # Recreate client for next attempt
                    client = _create_fresh_client()
                    logger.debug(f"Created fresh client after APIConnectionError (attempt {attempt + 2})")
                    continue
                break
            except (APITimeoutError, TimeoutError) as e:
                last_exception = e
                logger.error(
                    f"OpenAI timeout (attempt {attempt + 1}/{max_retries + 1}): "
                    f"Type: {type(e).__name__}, Message: {str(e)}"
                )
                if attempt < max_retries:
                    wait_time = (2 ** attempt) + (attempt * 0.5)
                    logger.warning(f"Retrying in {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    continue
                break
            except RateLimitError as e:
                last_exception = e
                logger.error(
                    f"OpenAI rate limit (attempt {attempt + 1}/{max_retries + 1}): "
                    f"Type: {type(e).__name__}, Message: {str(e)}"
                )
                if attempt < max_retries:
                    wait_time = 10 + (attempt * 5)
                    logger.warning(f"Waiting {wait_time:.1f}s for rate limit...")
                    time.sleep(wait_time)
                    continue
                break
            except APIError as e:
                last_exception = e
                error_msg = str(e).lower()
                status_code = getattr(e, 'status_code', 'unknown')
                logger.error(
                    f"OpenAI APIError (attempt {attempt + 1}/{max_retries + 1}): "
                    f"Type: {type(e).__name__}, Status: {status_code}, "
                    f"Message: {str(e)}"
                )
                # Don't retry on authentication errors
                if "api_key" in error_msg or "authentication" in error_msg or str(status_code) == "401":
                    raise ValueError(
                        f"OpenAI API authentication failed. "
                        f"Check your API key in config.json. Error: {type(e).__name__}: {str(e)}"
                    ) from e
                # Don't retry on other API errors
                break
            except Exception as e:
                last_exception = e
                error_msg = str(e).lower()
                logger.error(
                    f"OpenAI unexpected error (attempt {attempt + 1}/{max_retries + 1}): "
                    f"Type: {type(e).__name__}, Message: {str(e)}, "
                    f"Cause: {e.__cause__ if e.__cause__ else 'None'}"
                )
                # Don't retry on authentication errors
                if "api_key" in error_msg or "authentication" in error_msg or "401" in str(e):
                    raise ValueError(
                        f"OpenAI API authentication failed. "
                        f"Check your API key in config.json. Error: {type(e).__name__}: {str(e)}"
                    ) from e
                # Retry on connection/timeout errors
                if attempt < max_retries and ("connection" in error_msg or "timeout" in error_msg):
                    wait_time = (2 ** attempt) + (attempt * 0.5)
                    logger.warning(f"Retrying in {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    continue
                break
        
        # All retries exhausted - raise with full details
        error_type = type(last_exception).__name__
        error_msg = str(last_exception)
        raise Exception(
            f"OpenAI API error after {max_retries + 1} attempts: "
            f"{error_type}: {error_msg}"
        ) from last_exception
