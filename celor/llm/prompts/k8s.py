"""K8s-specific prompt engineering for LLM adapter.

This module contains all K8s domain knowledge for LLM template generation:
- K8s PatchDSL operation documentation
- Manifest snippet extraction
- Violation formatting
- Example templates

Layer 3 of LLM architecture: Domain-specific prompt logic.
"""

import logging
from typing import Dict, List

from celor.core.schema.artifact import Artifact
from celor.core.schema.violation import Violation

logger = logging.getLogger(__name__)


# K8s PatchDSL documentation for LLM
PATCHDSL_DOCS = """
Available K8s PatchDSL Operations:

1. EnsureLabel(scope, key, value)
   - Adds or updates labels on deployment or pod template
   - scope: "deployment" | "podTemplate" | "both"
   - key: label key (string)
   - value: label value (string or {"$hole": "name"} for uncertain values)
   
2. EnsureImageVersion(container, version)
   - Sets container image tag
   - container: container name (string)
   - version: image tag (string or {"$hole": "name"})
   
3. EnsureSecurityBaseline(container)
   - Enforces security best practices on container
   - Sets: runAsNonRoot=true, allowPrivilegeEscalation=false, etc.
   - container: container name (string)
   
4. EnsureResourceProfile(container, profile)
   - Sets CPU/memory from predefined profiles
   - container: container name (string)
   - profile: "small" | "medium" | "large" (or {"$hole": "name"})
   
5. EnsureReplicas(replicas)
   - Sets replica count
   - replicas: integer (or {"$hole": "name"} for uncertain count)
   
6. EnsurePriorityClass(name)
   - Sets priorityClassName
   - name: priority class name (string or {"$hole": "name"})

Use {"$hole": "name"} for values that should be searched by synthesis.
"""

# Example template for LLM reference
EXAMPLE_TEMPLATE = """
Example PatchTemplate:
{
  "template": {
    "ops": [
      {"op": "EnsureLabel", "args": {"scope": "podTemplate", "key": "env", "value": {"$hole": "env"}}},
      {"op": "EnsureLabel", "args": {"scope": "podTemplate", "key": "team", "value": {"$hole": "team"}}},
      {"op": "EnsureImageVersion", "args": {"container": "payments-api", "version": {"$hole": "version"}}},
      {"op": "EnsureSecurityBaseline", "args": {"container": "payments-api"}},
      {"op": "EnsureResourceProfile", "args": {"container": "payments-api", "profile": {"$hole": "profile"}}},
      {"op": "EnsureReplicas", "args": {"replicas": {"$hole": "replicas"}}},
      {"op": "EnsurePriorityClass", "args": {"name": {"$hole": "priority_class"}}}
    ]
  },
  "hole_space": {
    "env": ["staging", "prod"],
    "team": ["payments", "platform"],
    "version": ["prod-1.2.3", "prod-1.2.4"],
    "profile": ["medium", "large"],
    "replicas": [3, 4, 5],
    "priority_class": ["critical", "high-priority"]
  }
}
"""


def build_k8s_prompt(
    artifact: Artifact,
    violations: List[Violation]
) -> str:
    """Build K8s-specific prompt for PatchTemplate generation.
    
    Constructs a comprehensive prompt that includes:
    - K8s PatchDSL operation documentation
    - Current manifest snippet
    - Oracle violations to fix
    - Expected JSON format
    - Example templates
    
    Args:
        artifact: K8s artifact to repair
        violations: Oracle failures to address
        
    Returns:
        Prompt string for LLM
    """
    # Extract manifest snippet
    manifest_snippet = extract_manifest_snippet(artifact)
    
    # Format violations
    violation_text = format_violations(violations)
    
    # Build comprehensive prompt
    prompt = f"""You are a Kubernetes expert helping to generate repair templates using CeLoR's PatchDSL.

## Current Deployment Manifest

```yaml
{manifest_snippet}
```

## Oracle Failures

The manifest has the following validation failures:

{violation_text}

## Important Context

**ECR Image Format**: All images must use AWS ECR with this exact format:
- Account ID: 123456789012
- Region: us-east-1
- Format: `123456789012.dkr.ecr.us-east-1.amazonaws.com/{{env}}/{{image_name}}:{{tag}}`
- Example: `123456789012.dkr.ecr.us-east-1.amazonaws.com/production-us/nginx:1.25.0`

**Environment Labels**: Must be one of: "production-us", "staging-us", "dev-us"
- If manifest has "production", it should be "production-us"
- If manifest has "staging", it should be "staging-us"
- If manifest has "dev", it should be "dev-us"

## Your Task

Generate a PatchTemplate that fixes these violations using the K8s PatchDSL operations.

{PATCHDSL_DOCS}

## Important Guidelines

1. **CRITICAL: Use {{"$hole": "name"}} for ANY value that is WRONG or needs to be fixed**
   - If the oracle says a value is wrong (e.g., wrong env label, wrong image), use a hole
   - Example: If current manifest has `env: production` but oracle says it's wrong, use {{"value": {{"$hole": "env"}}}}
   - Example: If current manifest has `image: nginx:latest` but oracle says it's wrong, use {{"version": {{"$hole": "nginx_ecr_image"}}}}
   
2. Use concrete values ONLY for things that are definitely correct and don't need fixing
   - Example: {{"container": "web"}} is concrete (container name is correct)
   
3. **For each violation, create a hole so the synthesizer can search for the correct value**

4. Define a reasonable hole_space with valid options for each hole
   - Include both valid and invalid values (synthesizer will learn constraints)
   - Keep domains small (2-10 values per hole)
   - Example: If fixing env label, hole_space might be: {{"env": ["production-us", "staging-us", "dev-us", "prod", "production"]}}

## Output Format

Return ONLY valid JSON (no markdown, no explanations) in this format:

{EXAMPLE_TEMPLATE}

Remember: The synthesizer will search through the hole_space to find values that satisfy all oracles.
"""
    
    return prompt


def extract_manifest_snippet(artifact: Artifact) -> str:
    """Extract relevant parts of K8s manifest for LLM context.
    
    Shows key sections: metadata, labels, spec.replicas, containers, etc.
    Limits size to avoid excessive tokens.
    
    Args:
        artifact: K8s artifact
        
    Returns:
        YAML snippet string
    """
    try:
        from ruamel.yaml import YAML
        
        serialized = artifact.to_serializable()
        if "files" not in serialized:
            return "# No files in artifact"
        
        yaml = YAML()
        
        for filepath, content in serialized["files"].items():
            # Handle multi-document YAML (separated by ---)
            # Load all documents and find the Deployment
            try:
                # Try loading as single document first
                manifest = yaml.load(content)
                if not isinstance(manifest, dict):
                    continue
            except Exception:
                # If that fails, try loading all documents
                try:
                    documents = list(yaml.load_all(content))
                    manifest = None
                    for doc in documents:
                        if isinstance(doc, dict) and doc.get("kind") == "Deployment":
                            manifest = doc
                            break
                    if manifest is None:
                        continue
                except Exception:
                    continue
            
            # Check if this is a Deployment
            if manifest.get("kind") != "Deployment":
                continue
            
            # Build snippet with key fields
            snippet_parts = []
            
            # Metadata
            if "metadata" in manifest:
                snippet_parts.append(f"metadata:")
                snippet_parts.append(f"  name: {manifest['metadata'].get('name', 'unknown')}")
                if "labels" in manifest.get("metadata", {}):
                    snippet_parts.append(f"  labels: {manifest['metadata']['labels']}")
            
            # Spec basics
            if "spec" in manifest:
                spec = manifest["spec"]
                snippet_parts.append(f"spec:")
                snippet_parts.append(f"  replicas: {spec.get('replicas', 'N/A')}")
                if "priorityClassName" in spec:
                    snippet_parts.append(f"  priorityClassName: {spec['priorityClassName']}")
                
                # Pod template labels
                if "template" in spec:
                    template = spec["template"]
                    if "metadata" in template and "labels" in template["metadata"]:
                        snippet_parts.append(f"  template.metadata.labels: {template['metadata']['labels']}")
                    
                    # Container info
                    if "spec" in template and "containers" in template["spec"]:
                        containers = template["spec"]["containers"]
                        for c in containers[:2]:  # First 2 containers
                            snippet_parts.append(f"  container: {c.get('name', 'unknown')}")
                            snippet_parts.append(f"    image: {c.get('image', 'N/A')}")
                            if "resources" in c:
                                res = c["resources"]
                                if "requests" in res:
                                    snippet_parts.append(f"    resources.requests: {res['requests']}")
            
            return "\n".join(snippet_parts)
        
        return "# No deployment found"
        
    except Exception as e:
        logger.warning(f"Failed to extract manifest snippet: {e}")
        return f"# Error extracting manifest: {e}"


def format_violations(violations: List[Violation]) -> str:
    """Format violations for LLM readability.
    
    Args:
        violations: List of oracle violations
        
    Returns:
        Formatted string listing violations
    """
    if not violations:
        return "No violations (manifest already compliant)"
    
    lines = []
    
    # Group by oracle
    by_oracle: Dict[str, List[Violation]] = {}
    for v in violations:
        oracle_name = v.id.split(".")[0] if "." in v.id else "unknown"
        if oracle_name not in by_oracle:
            by_oracle[oracle_name] = []
        by_oracle[oracle_name].append(v)
    
    # Format each oracle's violations
    for oracle_name, oracle_violations in sorted(by_oracle.items()):
        lines.append(f"\n{oracle_name.upper()} ORACLE:")
        for v in oracle_violations:
            lines.append(f"  - {v.id}: {v.message}")
            if v.evidence and isinstance(v.evidence, dict):
                # Include relevant evidence
                if "error_code" in v.evidence:
                    lines.append(f"    Error code: {v.evidence['error_code']}")
    
    return "\n".join(lines)


def get_patchdsl_docs() -> str:
    """Get K8s PatchDSL operation documentation.
    
    Returns documentation of available K8s PatchDSL operations
    for inclusion in LLM prompt.
    
    Returns:
        Documentation string
    """
    return PATCHDSL_DOCS


def get_example_templates() -> str:
    """Get example PatchTemplate for LLM reference.
    
    Returns:
        Example template JSON
    """
    return EXAMPLE_TEMPLATE
