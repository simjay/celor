"""
LLM integration for one-shot parametric patch generation.

Provides interfaces for calling LLMs to generate repair templates with holes,
minimizing token usage through single-call architecture.
"""

from .clients import openai

__all__ = ["openai"]
