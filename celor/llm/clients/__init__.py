"""LLM client implementations.

Contains adapters for different LLM providers (OpenAI, etc.)
"""

from . import openai

__all__ = ["openai"]
