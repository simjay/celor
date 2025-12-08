"""Fix Bank for storing and reusing successful repair patterns.

The Fix Bank enables cross-run learning by persisting:
- Repair signatures (fingerprints of oracle failures)
- Successful templates and hole spaces
- Learned constraints for warm-starting synthesis
- Metadata for tracking reuse and success rates

This allows team knowledge sharing via git-committable .celor-fixes.json files.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from celor.core.schema.artifact import Artifact
from celor.core.schema.violation import Violation
from celor.core.synth import Constraint
from celor.core.template import HoleSpace, PatchTemplate, deserialize_template, serialize_template

logger = logging.getLogger(__name__)


@dataclass
class FixEntry:
    """Entry in the Fix Bank storing a successful repair pattern.
    
    Attributes:
        signature: Fingerprint identifying this type of regression
        template: The PatchTemplate that successfully repaired it
        hole_space: The HoleSpace used for synthesis
        learned_constraints: Constraints learned during synthesis (for warm-start)
        successful_assignment: The winning candidate assignment
        metadata: Additional info (timestamps, success count, etc.)
    """
    signature: Dict[str, Any]
    template: PatchTemplate
    hole_space: HoleSpace
    learned_constraints: List[Constraint] = field(default_factory=list)
    successful_assignment: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class FixBank:
    """Persistent storage for successful repair patterns.
    
    The Fix Bank stores repair recipes indexed by signature, enabling:
    - Fast lookup of known regressions
    - Reuse of successful templates
    - Warm-starting synthesis with learned constraints
    - Team knowledge sharing via git
    
    Example:
        >>> fixbank = FixBank(".celor-fixes.json")
        >>> entry = fixbank.lookup(signature)
        >>> if entry:
        >>>     # Reuse stored template and constraints
        >>>     template = entry.template
        >>>     constraints = entry.learned_constraints
    """
    
    def __init__(self, file_path: Optional[str] = None):
        """Initialize Fix Bank.
        
        Args:
            file_path: Path to JSON file for persistence (None disables persistence)
        """
        self.file_path = file_path
        self.entries: List[FixEntry] = []
        
        if file_path and Path(file_path).exists():
            self.load()
            logger.info(f"Loaded Fix Bank from {file_path} with {len(self.entries)} entries")
    
    def lookup(self, signature: Dict[str, Any]) -> Optional[FixEntry]:
        """Find matching entry for signature.
        
        Args:
            signature: Signature to look up
            
        Returns:
            FixEntry if match found, None otherwise
        """
        for entry in self.entries:
            if signatures_match(entry.signature, signature):
                logger.debug(f"Fix Bank HIT for signature: {signature}")
                return entry
        
        logger.debug(f"Fix Bank MISS for signature: {signature}")
        return None
    
    def add(self, entry: FixEntry) -> None:
        """Add new entry or update existing.
        
        Args:
            entry: FixEntry to add
        """
        existing = self.lookup(entry.signature)
        
        if existing:
            # Update existing entry
            existing.metadata["success_count"] = existing.metadata.get("success_count", 0) + 1
            existing.metadata["last_used"] = datetime.now().isoformat()
            
            # Optionally merge constraints (union of learned constraints)
            existing_constraint_set = {
                (c.type, json.dumps(c.data, sort_keys=True))
                for c in existing.learned_constraints
            }
            new_constraint_set = {
                (c.type, json.dumps(c.data, sort_keys=True))
                for c in entry.learned_constraints
            }
            
            if new_constraint_set - existing_constraint_set:
                logger.info("Merging newly learned constraints into existing entry")
                # Add new constraints
                for c in entry.learned_constraints:
                    c_key = (c.type, json.dumps(c.data, sort_keys=True))
                    if c_key not in existing_constraint_set:
                        existing.learned_constraints.append(c)
            
            logger.info(f"Updated existing Fix Bank entry (success_count={existing.metadata.get('success_count')})")
        else:
            # Add new entry
            if "created_at" not in entry.metadata:
                entry.metadata["created_at"] = datetime.now().isoformat()
            entry.metadata["success_count"] = 1
            entry.metadata["last_used"] = datetime.now().isoformat()
            
            self.entries.append(entry)
            logger.info(f"Added new Fix Bank entry with {len(entry.learned_constraints)} constraints")
        
        self.save()
    
    def save(self) -> None:
        """Persist Fix Bank to JSON file."""
        if not self.file_path:
            return
        
        data = {
            "version": "1.0",
            "entries": [self._entry_to_dict(e) for e in self.entries]
        }
        
        # Pretty-print for git-friendly diffs
        json_str = json.dumps(data, indent=2, sort_keys=True)
        Path(self.file_path).write_text(json_str)
        
        logger.debug(f"Saved Fix Bank to {self.file_path}")
    
    def load(self) -> None:
        """Load Fix Bank from JSON file."""
        if not self.file_path:
            return
        
        try:
            data = json.loads(Path(self.file_path).read_text())
            self.entries = [self._dict_to_entry(e) for e in data.get("entries", [])]
            logger.info(f"Loaded {len(self.entries)} entries from Fix Bank")
        except Exception as e:
            logger.error(f"Failed to load Fix Bank: {e}")
            self.entries = []
    
    def _entry_to_dict(self, entry: FixEntry) -> Dict[str, Any]:
        """Serialize FixEntry to dict for JSON storage."""
        return {
            "signature": entry.signature,
            "template": serialize_template(entry.template),
            "hole_space": serialize_hole_space(entry.hole_space),
            "learned_constraints": [c.to_dict() for c in entry.learned_constraints],
            "successful_assignment": entry.successful_assignment,
            "metadata": entry.metadata
        }
    
    def _dict_to_entry(self, d: Dict[str, Any]) -> FixEntry:
        """Deserialize FixEntry from dict."""
        return FixEntry(
            signature=d["signature"],
            template=deserialize_template(d["template"]),
            hole_space=deserialize_hole_space(d["hole_space"]),
            learned_constraints=[
                Constraint.from_dict(c) for c in d.get("learned_constraints", [])
            ],
            successful_assignment=d.get("successful_assignment"),
            metadata=d.get("metadata", {})
        )


def build_signature(artifact: Artifact, violations: List[Violation]) -> Dict[str, Any]:
    """Build regression signature from oracle violations.
    
    Creates a fingerprint of the failure pattern for matching against
    Fix Bank entries. Signatures are based on:
    - Which oracles failed
    - Specific error codes
    - Artifact context (env, app name)
    
    Args:
        artifact: The failing artifact
        violations: List of oracle violations
        
    Returns:
        Signature dict for Fix Bank lookup
        
    Example:
        >>> signature = build_signature(artifact, violations)
        >>> signature
        {
            "failed_oracles": ["policy", "security"],
            "error_codes": ["ENV_PROD_REPLICA_COUNT", "MISSING_LABEL_TEAM"],
            "context": {"env": "prod", "app": "payments-api"}
        }
    """
    # Extract unique oracle names from violation IDs
    # E.g., "policy.ENV_PROD_REPLICA_COUNT" → "policy"
    failed_oracles = sorted(list(set(
        v.id.split(".")[0] for v in violations
    )))
    
    # Extract error codes from violation evidence
    error_codes = []
    for v in violations:
        if v.evidence and isinstance(v.evidence, dict):
            if "error_code" in v.evidence:
                error_codes.append(v.evidence["error_code"])
    error_codes = sorted(list(set(error_codes)))
    
    # Extract context from artifact (for K8s)
    context = {}
    try:
        serialized = artifact.to_serializable()
        if "files" in serialized:
            # Try to extract from K8s manifest
            from ruamel.yaml import YAML
            yaml = YAML()
            
            for filepath, content in serialized["files"].items():
                if "deployment" in filepath.lower():
                    manifest = yaml.load(content)
                    
                    # Extract app name
                    context["app"] = manifest.get("metadata", {}).get("name", "")
                    
                    # Extract env label if present
                    env = (manifest.get("spec", {})
                          .get("template", {})
                          .get("metadata", {})
                          .get("labels", {})
                          .get("env", ""))
                    if env:
                        context["env"] = env
                    break
    except Exception:
        # Context extraction is best-effort
        pass
    
    return {
        "failed_oracles": failed_oracles,
        "error_codes": error_codes,
        "context": context
    }


def signatures_match(sig_a: Dict[str, Any], sig_b: Dict[str, Any]) -> bool:
    """Check if two signatures match.
    
    V1 implementation uses exact matching on oracle names and error codes.
    Future versions could use fuzzy matching or similarity metrics.
    
    Args:
        sig_a: First signature
        sig_b: Second signature
        
    Returns:
        True if signatures match (represent same type of regression)
    """
    # Exact match on failed oracles
    if sig_a.get("failed_oracles") != sig_b.get("failed_oracles"):
        return False
    
    # Exact match on error codes
    if sig_a.get("error_codes") != sig_b.get("error_codes"):
        return False
    
    # Optional: match on context (env, app)
    # For now, consider context optional (don't require exact match)
    
    return True


def serialize_hole_space(hole_space: HoleSpace) -> Dict[str, List[Any]]:
    """Serialize HoleSpace to JSON-compatible format.
    
    Converts sets to sorted lists for JSON serialization.
    
    Args:
        hole_space: HoleSpace to serialize
        
    Returns:
        Dict with lists instead of sets
    """
    return {
        hole: sorted(list(values), key=str)
        for hole, values in hole_space.items()
    }


def deserialize_hole_space(data: Dict[str, List[Any]]) -> HoleSpace:
    """Deserialize HoleSpace from JSON.
    
    Converts lists back to sets.
    
    Args:
        data: Serialized hole space
        
    Returns:
        HoleSpace with sets
    """
    return {
        hole: set(values)
        for hole, values in data.items()
    }

