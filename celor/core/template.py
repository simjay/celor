"""Template system for patches with holes.

This module provides the template abstraction for representing partially-specified
patches. Templates contain holes (unknowns) that the synthesizer fills through
candidate enumeration and constraint-based search.

Key concepts:
- HoleRef: Reference to a hole (unknown value) in a template
- PatchTemplate: Patch with holes (partially specified)
- HoleSpace: Domain of possible values for each hole (search space)
- CandidateAssignments: Specific choice of values for all holes
- instantiate(): Fill holes to create concrete Patch
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Set

from celor.core.schema.patch_dsl import Patch, PatchOp


@dataclass(frozen=True)
class HoleRef:
    """Reference to a hole (unknown value) in a patch template.
    
    A hole represents a value that the synthesizer must determine through
    search. Holes are placeholders in PatchOp arguments that get filled
    with concrete values during instantiation.
    
    Example:
        HoleRef("env") represents the ?env hole that could be "staging-us" or "production-us"
        HoleRef("replicas") represents the ?replicas hole that could be 2, 3, 4, or 5
    
    Attributes:
        name: Unique identifier for the hole (e.g., "env", "version", "profile")
    """
    name: str


@dataclass
class PatchTemplate:
    """Patch template with holes (partially specified PatchDSL program).
    
    A PatchTemplate is a patch where some operation arguments are HoleRef objects
    instead of concrete values. The synthesizer enumerates candidate assignments
    from the HoleSpace and instantiates the template to create concrete patches
    for testing.
    
    Example::
    
        PatchTemplate(ops=[
            PatchOp("EnsureLabel", {"key": "env", "value": HoleRef("env")}),
            PatchOp("EnsureReplicas", {"replicas": HoleRef("replicas")})
        ])
    
    Attributes:
        ops: List of patch operations, some args may contain HoleRef.
    """
    ops: List[PatchOp]


# Type aliases for synthesis
HoleSpace = Dict[str, Set[Any]]
"""Mapping from hole name to set of allowed values (search space).

Example::

    {
        "env": {"staging-us", "production-us"},
        "version": {"v1", "v2", "v3"},
        "profile": {"small", "medium", "large"}
    }
"""

CandidateAssignments = Dict[str, Any]
"""Mapping from hole name to chosen value (one point in search space).

Example::

    {"env": "production-us", "version": "v2", "profile": "medium"}
"""


def instantiate(template: PatchTemplate, assignment: CandidateAssignments) -> Patch:
    """Fill holes in template to create concrete patch.
    
    Replaces all HoleRef objects in the template's operation arguments with
    concrete values from the assignment, producing a fully instantiated Patch
    that's ready to apply to an artifact.
    
    Args:
        template: PatchTemplate with HoleRef placeholders
        assignment: Mapping from hole names to concrete values
        
    Returns:
        Patch with all holes filled (ConcretePatch)
        
    Example:
        >>> template = PatchTemplate(ops=[
        ...     PatchOp("EnsureLabel", {"key": "env", "value": HoleRef("env")}),
        ...     PatchOp("EnsureReplicas", {"replicas": HoleRef("replicas")})
        ... ])
        >>> assignment = {"env": "production-us", "replicas": 3}
        >>> patch = instantiate(template, assignment)
        >>> patch.ops[0].args["value"]
        'production-us'
        >>> patch.ops[1].args["replicas"]
        3
    """
    concrete_ops: List[PatchOp] = []
    
    for op in template.ops:
        # Replace HoleRef in args with concrete values
        new_args = {}
        for key, value in op.args.items():
            if isinstance(value, HoleRef):
                # Replace hole with concrete value from assignment
                if value.name not in assignment:
                    raise ValueError(
                        f"Hole '{value.name}' not found in assignment. "
                        f"Available: {list(assignment.keys())}"
                    )
                new_args[key] = assignment[value.name]
            else:
                # Keep non-hole values as-is
                new_args[key] = value
        
        concrete_ops.append(PatchOp(op=op.op, args=new_args))
    
    return Patch(ops=concrete_ops)


def serialize_value(value: Any) -> Any:
    """Serialize a value for JSON storage, converting HoleRef to dict.
    
    Converts HoleRef objects to {"$hole": "name"} format for JSON serialization.
    Other values are returned as-is.
    
    Args:
        value: Value to serialize (may be HoleRef or regular value)
        
    Returns:
        Serialized value (dict for HoleRef, unchanged otherwise)
        
    Example:
        >>> serialize_value(HoleRef("env"))
        {'$hole': 'env'}
        >>> serialize_value("production-us")
        'production-us'
        >>> serialize_value(3)
        3
    """
    if isinstance(value, HoleRef):
        return {"$hole": value.name}
    return value


def deserialize_value(value: Any) -> Any:
    """Deserialize a value from JSON storage, converting dict to HoleRef.
    
    Converts {"$hole": "name"} format back to HoleRef objects.
    Other values are returned as-is.
    
    Args:
        value: Value to deserialize (may be dict with $hole or regular value)
        
    Returns:
        Deserialized value (HoleRef if dict with $hole, unchanged otherwise)
        
    Example:
        >>> deserialize_value({'$hole': 'env'})
        HoleRef(name='env')
        >>> deserialize_value("production-us")
        'production-us'
        >>> deserialize_value(3)
        3
    """
    if isinstance(value, dict) and "$hole" in value:
        return HoleRef(value["$hole"])
    return value


def serialize_template(template: PatchTemplate) -> Dict[str, Any]:
    """Serialize PatchTemplate to JSON-compatible dict.
    
    Args:
        template: PatchTemplate to serialize
        
    Returns:
        Dict representation with HoleRefs serialized as {"$hole": "name"}
    """
    return {
        "ops": [
            {
                "op": op.op,
                "args": {k: serialize_value(v) for k, v in op.args.items()}
            }
            for op in template.ops
        ]
    }


def deserialize_template(data: Dict[str, Any]) -> PatchTemplate:
    """Deserialize PatchTemplate from JSON-compatible dict.
    
    Args:
        data: Dict representation from serialize_template()
        
    Returns:
        PatchTemplate with HoleRefs restored
    """
    ops = [
        PatchOp(
            op=op_data["op"],
            args={k: deserialize_value(v) for k, v in op_data["args"].items()}
        )
        for op_data in data["ops"]
    ]
    return PatchTemplate(ops=ops)

