"""Example K8s manifests, templates, and hole spaces for testing and demos.

This module provides sample deployments and default PatchTemplate/HoleSpace
configurations for the K8s domain.
"""

from typing import Any, Dict, Optional

from celor.core.schema.patch_dsl import PatchOp
from celor.core.template import HoleRef, HoleSpace, PatchTemplate

# Sample baseline deployment (compliant with all policies)
BASELINE_DEPLOYMENT = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: payments-api
  labels:
    app: payments-api
    env: prod
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
        env: prod
        team: payments
        tier: backend
    spec:
      containers:
      - name: payments-api
        image: payments-api:prod-1.2.3
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
    context: Optional[Dict[str, Any]] = None
) -> tuple[PatchTemplate, HoleSpace]:
    """Get PatchTemplate and HoleSpace for K8s deployment repair.
    
    Returns a comprehensive template that can fix common policy violations
    including labels, image versions, security, resources, replicas, and priority class.
    
    Args:
        context: Optional context dict to narrow hole space:
            - "env": Override env values (default: {"staging", "prod"})
            - "team": Override team values (default: {"payments", "platform", "data"})
            - "tier": Override tier values (default: {"frontend", "backend", "data"})
            - "container": Container name (default: "payments-api")
            - "narrow": If True, use narrower production-focused spaces
    
    Returns:
        Tuple of (PatchTemplate, HoleSpace)
        
    Example:
        >>> # Default (broad search space)
        >>> template, holes = get_k8s_template_and_holes()
        
        >>> # Narrowed for payments-api in prod
        >>> template, holes = get_k8s_template_and_holes({
        ...     "env": {"prod"},
        ...     "team": {"payments"},
        ...     "tier": {"backend"},
        ...     "narrow": True
        ... })
    """
    if context is None:
        context = {}
    
    container = context.get("container", "payments-api")
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
    if narrow:
        # Narrower production-focused space
        hole_space: HoleSpace = {
            "env": context.get("env", {"prod"}),
            "team": context.get("team", {"payments"}),
            "tier": context.get("tier", {"backend"}),
            "version": {"prod-1.2.3", "prod-1.2.4", "prod-1.3.0"},
            "profile": {"medium", "large"},  # prod doesn't allow small
            "replicas": {3, 4, 5},  # prod requires 3-5
            "priority_class": {"critical", "high-priority"}
        }
    else:
        # Broad default space
        hole_space: HoleSpace = {
            "env": context.get("env", {"staging", "prod"}),
            "team": context.get("team", {"payments", "platform", "data"}),
            "tier": context.get("tier", {"frontend", "backend", "data"}),
            "version": {"prod-1.2.3", "prod-1.2.4", "prod-1.3.0"},
            "profile": {"small", "medium", "large"},
            "replicas": {2, 3, 4, 5},
            "priority_class": {None, "critical", "high-priority"}
        }
    
    return template, hole_space


# Backward compatibility aliases
def default_k8s_template() -> PatchTemplate:
    """DEPRECATED: Use get_k8s_template_and_holes() instead."""
    template, _ = get_k8s_template_and_holes()
    return template


def default_k8s_hole_space() -> HoleSpace:
    """DEPRECATED: Use get_k8s_template_and_holes() instead."""
    _, hole_space = get_k8s_template_and_holes()
    return hole_space


def payments_api_template_and_holes() -> tuple[PatchTemplate, HoleSpace]:
    """DEPRECATED: Use get_k8s_template_and_holes({"narrow": True}) instead."""
    return get_k8s_template_and_holes({
        "env": {"prod"},
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
    # Note: Order matters - put valid prod values first so they're tried early
    hole_space: HoleSpace = {
        "env": {"prod", "staging"},  # 2 values (staging invalid for prod, but we'll try it)
        "team": {"payments", "platform", "invalid-team"},  # 3 values (invalid-team will fail)
        "tier": {"backend", "frontend"},  # 2 values (both valid)
        "version": [
            # Valid production ECR nginx images (the solution)
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/prod/nginx:prod-1.25.0",
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/prod/nginx:prod-1.25.1",
            # Invalid: Public Docker Hub images (not ECR) - the original problem
            "nginx:latest",
            "docker.io/library/nginx:latest",
            # Invalid: Wrong environment (staging ECR for prod deployment)
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/staging/nginx:staging-1.25.0",
        ],  # 5 values (2 valid, 3 invalid - enough to show constraint learning)
        "profile": {"medium", "large", "small"},  # 3 values (small invalid for prod)
        "replicas": [3, 4, 5, 1, 2],  # 5 values (1,2 invalid for prod)
        "priority_class": {"critical", "high-priority", None},  # 3 values (None invalid for prod)
    }
    
    # Total: 2 × 3 × 2 × 5 × 3 × 5 × 3 = 2,700 combinations
    # Valid prod: 1 × 2 × 2 × 2 × 2 × 3 × 2 = 96 combinations
    # Still demonstrates constraint learning while ensuring solution is found
    # Only a small fraction are valid for prod, demonstrating:
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

