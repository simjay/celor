"""Example K8s manifests, templates, and hole spaces for testing and demos.

This module provides sample deployments and default PatchTemplate/HoleSpace
configurations for the K8s domain.
"""

from typing import Any, Dict, Optional

from celor.core.schema.artifact import Artifact
from celor.core.schema.patch_dsl import PatchOp
from celor.core.template import HoleRef, HoleSpace, PatchTemplate

# Sample baseline deployment (compliant with all policies)
BASELINE_DEPLOYMENT = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: payments-api
  labels:
    app: payments-api
    env: production-us
    team: payments
    tier: backend
spec:
  replicas: 3
  priorityClassName: critical
  selector:
    matchLabels:
      app: payments-api
  template:
    metadata:
      labels:
        app: payments-api
        env: production-us
        team: payments
        tier: backend
    spec:
      containers:
      - name: payments-api
        image: 123456789012.dkr.ecr.us-east-1.amazonaws.com/production-us/payments-api:prod-1.2.3
        securityContext:
          runAsNonRoot: true
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop: [ALL]
        resources:
          requests:
            cpu: "500m"
            memory: "512Mi"
          limits:
            cpu: "1000m"
            memory: "1Gi"
"""

# Simulated LLM edit (breaks policies)
LLM_EDITED_DEPLOYMENT = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: payments-api
  labels:
    app: payments-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: payments-api
  template:
    metadata:
      labels:
        app: payments-api
        env: prod
    spec:
      containers:
      - name: payments-api
        image: payments-api:latest
        resources:
          requests:
            cpu: "100m"
            memory: "128Mi"
"""


def get_k8s_template_and_holes(
    context: Optional[Dict[str, Any]] = None,
    artifact: Optional[Artifact] = None
) -> tuple[PatchTemplate, HoleSpace]:
    """Get PatchTemplate and HoleSpace for K8s deployment repair.
    
    Returns a comprehensive template that can fix common policy violations
    including labels, image versions, security, resources, replicas, and priority class.
    
    Extracts container name, env, team, and tier from artifact if available.
    Falls back to context or defaults only if not found in artifact.
    
    Args:
        context: Optional context dict to narrow hole space or override extracted values:
            - "env": Override env values (if not extracted from artifact)
            - "team": Override team values (if not extracted from artifact)
            - "tier": Override tier values (if not extracted from artifact)
            - "container": Override container name (if not extracted from artifact)
            - "narrow": If True, use narrower production-focused spaces
        artifact: Optional artifact to extract container name, env, team, tier from
    
    Returns:
        Tuple of (PatchTemplate, HoleSpace)
        
    Example:
        >>> # Extract from artifact
        >>> template, holes = get_k8s_template_and_holes(artifact=artifact)
        
        >>> # Override with context
        >>> template, holes = get_k8s_template_and_holes({
        ...     "env": {"production-us"},
        ...     "narrow": True
        ... }, artifact=artifact)
    """
    if context is None:
        context = {}
    
    # Extract values from artifact if available
    extracted_container = None
    extracted_env = None
    extracted_team = None
    extracted_tier = None
    
    if artifact is not None:
        from ruamel.yaml import YAML
        from celor.k8s.utils import get_containers, get_pod_template_label
        
        yaml = YAML()
        for filepath, content in artifact.files.items():
            try:
                manifest = yaml.load(content)
                if manifest.get("kind") == "Deployment":
                    # Extract container name
                    containers = get_containers(manifest)
                    if containers and not extracted_container:
                        extracted_container = containers[0].get("name")
                    
                    # Extract labels
                    if not extracted_env:
                        extracted_env = get_pod_template_label(manifest, "env")
                    if not extracted_team:
                        extracted_team = get_pod_template_label(manifest, "team")
                    if not extracted_tier:
                        extracted_tier = get_pod_template_label(manifest, "tier")
                    
                    # Only need first Deployment
                    break
            except Exception:
                continue
    
    # Use extracted values, fallback to context, then raise error if still None
    container = context.get("container") or extracted_container
    if container is None:
        raise ValueError(
            "Container name not found. Provide via context['container'] or ensure artifact has containers."
        )
    
    # For env, team, tier: use extracted if available, otherwise use context defaults
    # These are used for hole space, so we can have defaults
    env_from_artifact = extracted_env
    team_from_artifact = extracted_team
    tier_from_artifact = extracted_tier
    
    narrow = context.get("narrow", False)
    
    # Build template (same for all contexts)
    template = PatchTemplate(ops=[
        # Labels
        PatchOp("EnsureLabel", {
            "scope": "podTemplate",
            "key": "env",
            "value": HoleRef("env")
        }),
        PatchOp("EnsureLabel", {
            "scope": "podTemplate",
            "key": "team",
            "value": HoleRef("team")
        }),
        PatchOp("EnsureLabel", {
            "scope": "podTemplate",
            "key": "tier",
            "value": HoleRef("tier")
        }),
        
        # Image
        PatchOp("EnsureImageVersion", {
            "container": container,
            "version": HoleRef("version")
        }),
        
        # Security
        PatchOp("EnsureSecurityBaseline", {
            "container": container
        }),
        
        # Resources
        PatchOp("EnsureResourceProfile", {
            "container": container,
            "profile": HoleRef("profile")
        }),
        
        # Replicas
        PatchOp("EnsureReplicas", {
            "replicas": HoleRef("replicas")
        }),
        
        # Priority
        PatchOp("EnsurePriorityClass", {
            "name": HoleRef("priority_class")
        }),
    ])
    
    # Build hole space (context-dependent)
    # Determine env values: use extracted, context override, or defaults
    if "env" in context:
        env_values = context["env"] if isinstance(context["env"], set) else {context["env"]}
    elif env_from_artifact:
        # Use extracted env, but include common alternatives for search space
        if env_from_artifact == "production-us":
            env_values = {"production-us", "staging-us"}  # Include staging for search
        elif env_from_artifact == "staging-us":
            env_values = {"staging-us", "production-us", "dev-us"}
        elif env_from_artifact == "dev-us":
            env_values = {"dev-us", "staging-us"}
        else:
            env_values = {env_from_artifact, "production-us", "staging-us", "dev-us"}
    else:
        env_values = {"production-us"} if narrow else {"staging-us", "production-us", "dev-us"}
    
    primary_env = env_from_artifact or next(iter(env_values)) if env_values else "production-us"
    
    # Determine team values: use extracted, context override, or defaults
    if "team" in context:
        team_values = context["team"] if isinstance(context["team"], set) else {context["team"]}
    elif team_from_artifact:
        team_values = {team_from_artifact, "payments", "platform", "data"}  # Include common alternatives
    else:
        team_values = {"payments"} if narrow else {"payments", "platform", "data"}
    
    # Determine tier values: use extracted, context override, or defaults
    if "tier" in context:
        tier_values = context["tier"] if isinstance(context["tier"], set) else {context["tier"]}
    elif tier_from_artifact:
        tier_values = {tier_from_artifact, "frontend", "backend", "data"}  # Include common alternatives
    else:
        tier_values = {"backend"} if narrow else {"frontend", "backend", "data"}
    
    if narrow:
        # Narrower production-focused space
        # Version must be full ECR paths (PolicyOracle requires ECR images)
        version_values = {
            f"123456789012.dkr.ecr.us-east-1.amazonaws.com/{primary_env}/{container}:prod-1.2.3",
            f"123456789012.dkr.ecr.us-east-1.amazonaws.com/{primary_env}/{container}:prod-1.2.4",
            f"123456789012.dkr.ecr.us-east-1.amazonaws.com/{primary_env}/{container}:prod-1.3.0",
        }
        hole_space: HoleSpace = {
            "env": env_values,
            "team": team_values,
            "tier": tier_values,
            "version": version_values,
            "profile": {"medium", "large"},  # production-us doesn't allow small
            "replicas": {3, 4, 5},  # production-us requires 3-5
            "priority_class": {"critical", "high-priority"}
        }
    else:
        # Broad default space
        # Include ECR paths for all envs in env_values
        version_values = set()
        for env in env_values:
            version_values.update({
                f"123456789012.dkr.ecr.us-east-1.amazonaws.com/{env}/{container}:prod-1.2.3",
                f"123456789012.dkr.ecr.us-east-1.amazonaws.com/{env}/{container}:prod-1.2.4",
                f"123456789012.dkr.ecr.us-east-1.amazonaws.com/{env}/{container}:prod-1.3.0",
            })
        hole_space: HoleSpace = {
            "env": env_values,
            "team": team_values,
            "tier": tier_values,
            "version": version_values,
            "profile": {"small", "medium", "large"},
            "replicas": {2, 3, 4, 5},
            "priority_class": {None, "critical", "high-priority"}
        }
    
    return template, hole_space


# Backward compatibility aliases
def default_k8s_template() -> PatchTemplate:
    """DEPRECATED: Use get_k8s_template_and_holes() instead."""
    template, _ = get_k8s_template_and_holes(context={"container": "payments-api"})
    return template


def default_k8s_hole_space() -> HoleSpace:
    """DEPRECATED: Use get_k8s_template_and_holes() instead."""
    _, hole_space = get_k8s_template_and_holes(context={"container": "payments-api"})
    return hole_space


def payments_api_template_and_holes() -> tuple[PatchTemplate, HoleSpace]:
    """DEPRECATED: Use get_k8s_template_and_holes({"narrow": True}) instead."""
    return get_k8s_template_and_holes({
        "container": "payments-api",  # Explicitly provide container for backward compatibility
        "env": {"production-us"},
        "team": {"payments"},
        "tier": {"backend"},
        "narrow": True
    })


def demo_template_and_holes() -> tuple[PatchTemplate, HoleSpace]:
    """Demo template with expanded hole space to show synthesis value.
    
    Search space: 2 × 3 × 3 × 4 × 3 × 5 × 3 = 3,240 combinations
    
    This demonstrates:
    - Why enumeration is impractical (3,240 combinations)
    - How constraint learning prunes the space
    - Efficiency of CEGIS synthesis (tries only 5-15 candidates)
    - AWS ECR repository requirements (ECR paths in version hole)
    
    Returns:
        Tuple of (PatchTemplate, HoleSpace)
        
    Example:
        >>> template, hole_space = demo_template_and_holes()
        >>> from celor.k8s.examples import calculate_search_space_size
        >>> print(f"Search space: {calculate_search_space_size(hole_space)} combinations")
        Search space: 3240 combinations
    """
    template = PatchTemplate(ops=[
        # Labels
        PatchOp("EnsureLabel", {
            "scope": "podTemplate",
            "key": "env",
            "value": HoleRef("env")
        }),
        PatchOp("EnsureLabel", {
            "scope": "podTemplate",
            "key": "team",
            "value": HoleRef("team")
        }),
        PatchOp("EnsureLabel", {
            "scope": "podTemplate",
            "key": "tier",
            "value": HoleRef("tier")
        }),
        
        # Image version (with ECR paths)
        # Note: Container name is dynamic - could be "nginx", "payments-api", etc.
        PatchOp("EnsureImageVersion", {
            "container": "nginx",  # Updated for nginx demo
            "version": HoleRef("version")
        }),
        
        # Security baseline
        PatchOp("EnsureSecurityBaseline", {
            "container": "nginx"  # Updated for nginx demo
        }),
        
        # Resource profile
        PatchOp("EnsureResourceProfile", {
            "container": "nginx",  # Updated for nginx demo
            "profile": HoleRef("profile")
        }),
        
        # Replicas
        PatchOp("EnsureReplicas", {
            "replicas": HoleRef("replicas")
        }),
        
        # Priority class
        PatchOp("EnsurePriorityClass", {
            "name": HoleRef("priority_class")
        }),
    ])
    
    # Expanded hole space with invalid values to demonstrate constraint learning
    # Problem: LLM gave us nginx:latest, but we need ECR nginx image
    # This creates a harder problem where synthesis must:
    # 1. Try invalid public images first (will fail ECR policy)
    # 2. Learn constraints from failures
    # 3. Prune invalid candidates
    # 4. Find valid ECR nginx image
    # Format: <account>.dkr.ecr.<region>.amazonaws.com/<env>/<repo>:<tag>
    # Note: Order matters - put valid production-us values first so they're tried early
    hole_space: HoleSpace = {
        "env": {"production-us", "prod"},  # 2 values (prod is invalid - LLM might give this, but we'll try it)
        "team": {"payments", "platform", "invalid-team"},  # 3 values (invalid-team will fail)
        "tier": {"backend", "frontend"},  # 2 values (both valid)
        "version": [
            # Valid production-us ECR nginx images (the solution)
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/production-us/nginx:prod-1.25.0",
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/production-us/nginx:prod-1.25.1",
            # Invalid: Public Docker Hub images (not ECR) - the original problem
            "nginx:latest",
            "docker.io/library/nginx:latest",
            # Invalid: Wrong environment (staging-us ECR for production-us deployment)
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/staging-us/nginx:staging-1.25.0",
        ],  # 5 values (2 valid, 3 invalid - enough to show constraint learning)
        "profile": {"medium", "large", "small"},  # 3 values (small invalid for production-us)
        "replicas": [3, 4, 5, 1, 2],  # 5 values (1,2 invalid for production-us)
        "priority_class": {"critical", "high-priority", None},  # 3 values (None invalid for production-us)
    }
    
    # Total: 2 × 3 × 2 × 5 × 3 × 5 × 3 = 2,700 combinations
    # Valid production-us: 1 × 2 × 2 × 2 × 2 × 3 × 2 = 96 combinations
    # Still demonstrates constraint learning while ensuring solution is found
    # Only a small fraction are valid for production-us, demonstrating:
    # - Why synthesis is needed (can't try all manually)
    # - How constraints prune invalid candidates
    # - Efficiency of CEGIS (tries only valid candidates after learning)
    
    return template, hole_space


def calculate_search_space_size(hole_space: HoleSpace) -> int:
    """Calculate total number of combinations in hole space.
    
    Args:
        hole_space: Dictionary mapping hole names to sets of values
        
    Returns:
        Total number of possible combinations
    """
    total = 1
    for values in hole_space.values():
        total *= len(values)
    return total

