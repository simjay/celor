"""Patch DSL for structured edit programs.

This module defines the core patch data structures used throughout CeLoR.
Patches are structured edit programs that can contain holes (uncertain logic)
to be filled by synthesis.

JSON Transport Format
---------------------

Patches are serialized to JSON using an RFC-6902-inspired envelope format:

Example::

    {
      "ops": [
        {
          "op": "replace_function_body",
          "args": { "name": "f", "body": "x = HOLE_EXPR(\\"H1\\")\\nreturn x" }
        },
        { "op": "format_black", "args": {} }
      ],
      "holes": [
        {
          "hole_id": "H1",
          "allowed_symbols": ["a", "b", "c", "d"],
          "type_hint": "float"
        }
      ],
      "meta": { "artifact": "utils.py", "version": "2.0.0" }
    }

The envelope contains:

- ops: List of patch operations to apply sequentially
- holes: Metadata about holes in the patch (for synthesis)
- meta: Optional metadata (artifact name, version, etc.)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PatchOp:
    """Single atomic patch operation.

    A patch operation represents a single edit to be applied to an artifact.
    The specific operations available depend on the artifact type (domain).

    Common operations for Python artifacts:
    - replace_function_body: Replace entire function body
    - replace_span_with_hole: Insert HOLE_EXPR marker at specific span
    - set_constant: Replace constant value
    - format_black: Apply Black formatter

    Attributes:
        op: Operation name (e.g., "replace_function_body")
        args: Operation-specific arguments as a dictionary
    """

    op: str
    args: Dict[str, Any]


@dataclass
class Patch:
    """Structured edit program.

    A patch is a sequence of operations to be applied to an artifact.
    Patches can contain holes (HOLE_EXPR markers) representing uncertain
    logic that will be filled by synthesis during the CEGIS loop.

    Attributes:
        ops: List of patch operations to apply sequentially
        holes: Optional list of hole metadata for synthesis
               Each hole dict contains: hole_id, allowed_symbols, type_hint, etc.
        meta: Optional metadata dictionary (artifact name, version, etc.)
    """

    ops: List[PatchOp]
    holes: Optional[List[Dict[str, Any]]] = None
    meta: Optional[Dict[str, Any]] = None
