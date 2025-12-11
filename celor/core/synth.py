"""Core synthesis primitives for CEGIS.

This module provides the constraint system and candidate generator
for custom synthesis without external tools like Sketch.
"""

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterator, Literal, Optional

from celor.core.template import CandidateAssignments, HoleSpace


@dataclass
class Constraint:
    """Learned restriction on hole values from failed candidates.
    
    Constraints prune the search space by encoding knowledge about
    which hole assignments always fail oracle checks.
    
    Types:
        - forbidden_value: A single hole value always fails
          Example: Constraint("forbidden_value", {"hole": "profile", "value": "small"})
          Meaning: profile=small always violates (e.g., resource checks)
          
        - forbidden_tuple: A combination of hole values always fails together
          Example: Constraint("forbidden_tuple", {"holes": ["env", "replicas"], "values": ["production-us", 2]})
          Meaning: env=production-us AND replicas=2 together violate policy
    
    Constraints are:
        1. Learned during synthesis from oracle failure hints
        2. Used to prune candidate enumeration (skip invalid candidates)
        3. Stored in Fix Bank for cross-run learning
    """
    type: Literal["forbidden_value", "forbidden_tuple"]
    data: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize constraint for Fix Bank storage."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Constraint":
        """Deserialize constraint from Fix Bank."""
        return cls(type=d["type"], data=d["data"])
    
    def __repr__(self) -> str:
        """Human-readable representation."""
        if self.type == "forbidden_value":
            hole = self.data.get("hole")
            value = self.data.get("value")
            return f"Constraint(forbid {hole}={value})"
        elif self.type == "forbidden_tuple":
            holes = self.data.get("holes", [])
            values = self.data.get("values", [])
            pairs = ", ".join(f"{h}={v}" for h, v in zip(holes, values))
            return f"Constraint(forbid {pairs})"
        return f"Constraint({self.type}, {self.data})"


class CandidateGenerator:
    """Enumerates candidate assignments from HoleSpace with constraint pruning.
    
    Generates all possible combinations of hole values (Cartesian product)
    in lexicographic order, skipping candidates that violate constraints.
    
    Algorithm:
    - Treat hole space as multi-dimensional counting problem
    - Enumerate like: (0,0,0), (0,0,1), (0,1,0), (0,1,1), (1,0,0), ...
    - Skip candidates that violate learned constraints
    - Complexity: O(hole1_size × hole2_size × ... × holeN_size) worst case
    
    Example:
        >>> hole_space = {"env": {"dev-us", "production-us"}, "replicas": {2, 3}}
        >>> gen = CandidateGenerator(hole_space, [])
        >>> list(gen)  # Generates all 4 combinations
        [{"env": "dev", "replicas": 2}, {"env": "dev", "replicas": 3}, ...]
    """
    
    def __init__(self, hole_space: HoleSpace, constraints: list[Constraint]):
        """Initialize candidate generator.
        
        Args:
            hole_space: Dict mapping hole names to sets of possible values
            constraints: List of constraints to respect during enumeration
        """
        self.hole_space = hole_space
        self.constraints = constraints
        self._init_state()
    
    def _init_state(self) -> None:
        """Initialize internal enumeration state."""
        # Convert hole space to ordered lists for enumeration
        self.holes = sorted(self.hole_space.keys())  # Sorted for determinism
        self.domains = [sorted(self.hole_space[h], key=str) for h in self.holes]
        
        # Current position in each domain (index vector)
        self.indices = [0] * len(self.holes)
        self.exhausted = len(self.holes) == 0 or any(len(d) == 0 for d in self.domains)
    
    def update_constraints(self, constraints: list[Constraint]) -> None:
        """Add new constraints and restart enumeration.
        
        Args:
            constraints: New constraint list (replaces old constraints)
        """
        self.constraints = constraints
        self._init_state()
    
    def __iter__(self) -> Iterator[CandidateAssignments]:
        """Return self as iterator."""
        return self
    
    def __next__(self) -> CandidateAssignments:
        """Generate next valid candidate.
        
        Returns:
            Dict mapping hole names to concrete values
            
        Raises:
            StopIteration: When all candidates have been generated
        """
        if self.exhausted:
            raise StopIteration
        
        # Search for next valid candidate
        while not self.exhausted:
            # Build candidate from current indices
            candidate = {
                hole: self.domains[i][self.indices[i]]
                for i, hole in enumerate(self.holes)
            }
            
            # Advance to next combination
            self._advance()
            
            # Check if this candidate violates any constraints
            if not self._violates_constraints(candidate):
                return candidate  # Found valid candidate!
            
            # Constraint violated, continue to next candidate
        
        raise StopIteration
    
    def _advance(self) -> None:
        """Advance to next combination (lexicographic increment).
        
        Like incrementing a multi-digit number where each digit has
        a different base (domain size).
        """
        # Increment rightmost index with carry
        for i in reversed(range(len(self.indices))):
            self.indices[i] += 1
            if self.indices[i] < len(self.domains[i]):
                return  # Successfully incremented
            # Overflow: reset this index and carry to next
            self.indices[i] = 0
        
        # All indices overflowed - exhausted all combinations
        self.exhausted = True
    
    def _violates_constraints(self, candidate: CandidateAssignments) -> bool:
        """Check if candidate violates any learned constraints.
        
        Args:
            candidate: Hole assignment to check
            
        Returns:
            True if candidate violates at least one constraint
        """
        for constraint in self.constraints:
            if constraint.type == "forbidden_value":
                # Check if specific hole has forbidden value
                hole = constraint.data.get("hole")
                forbidden_val = constraint.data.get("value")
                if candidate.get(hole) == forbidden_val:
                    return True
                    
            elif constraint.type == "forbidden_tuple":
                # Check if all holes match forbidden combination
                holes = constraint.data.get("holes", [])
                forbidden_vals = constraint.data.get("values", [])
                if all(candidate.get(h) == v for h, v in zip(holes, forbidden_vals)):
                    return True
        
        return False  # No constraints violated
    
    def estimate_size(self) -> int:
        """Estimate total number of candidates (before constraint pruning).
        
        Returns:
            Product of all domain sizes
        """
        size = 1
        for domain in self.domains:
            size *= len(domain)
        return size

