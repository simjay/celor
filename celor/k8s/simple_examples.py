"""Simplified examples for minimal demo.

This module provides simple template generators for the two-prompt demo:
1. prompt1_initial: Fix nginx image and add env label
2. prompt2_regression: Fix promtail image (regression test)
"""

from celor.core.schema.patch_dsl import PatchOp
from celor.core.template import HoleRef, HoleSpace, PatchTemplate


def prompt1_template_and_holes() -> tuple[PatchTemplate, HoleSpace]:
    """Template for Prompt 1: Fix nginx image and add env label.
    
    Problem: LLM gave us nginx:latest (public Docker Hub) and missing env label.
    Solution: Replace with ECR image and add env label matching company standard.
    
    Returns:
        Tuple of (PatchTemplate, HoleSpace)
    """
    template = PatchTemplate(ops=[
        # Add env label
        PatchOp("EnsureLabel", {
            "scope": "podTemplate",
            "key": "env",
            "value": HoleRef("env")
        }),
        # Replace nginx image with ECR image
        PatchOp("EnsureImageVersion", {
            "container": "nginx",
            "version": HoleRef("nginx_ecr_image")
        }),
    ])
    
    hole_space: HoleSpace = {
        "env": {
            "production-us",      # ✅ Valid (company standard)
            "staging-us",         # ✅ Valid
            "dev-us",             # ✅ Valid
            "prod",               # ❌ Invalid (LLM might give this)
            "production",         # ❌ Invalid (LLM might give this)
            "staging",            # ❌ Invalid
            "dev"                 # ❌ Invalid
        },  # 7 values (3 valid, 4 invalid)
        "nginx_ecr_image": {
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/production-us/nginx:1.25.0",
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/staging-us/nginx:1.25.0",
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/dev-us/nginx:1.25.0",
            "nginx:latest",                                    # ❌ Invalid
            "docker.io/library/nginx:latest",                  # ❌ Invalid
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/prod/nginx:1.25.0",  # ❌ Wrong env
        }  # 6 values (3 valid, 3 invalid)
    }
    
    # Total: 7 × 6 = 42 combinations (9 valid)
    
    return template, hole_space


def prompt2_template_and_holes() -> tuple[PatchTemplate, HoleSpace]:
    """Template for Prompt 2: Fix promtail image (regression test).
    
    Problem: LLM added Promtail sidecar with grafana/promtail:latest (public Docker Hub).
    Solution: Replace with ECR image. Env label should already be correct from prompt 1.
    
    Returns:
        Tuple of (PatchTemplate, HoleSpace)
    """
    template = PatchTemplate(ops=[
        # Replace promtail image with ECR image
        # Note: env label should already be set from prompt 1, so we only fix the image
        PatchOp("EnsureImageVersion", {
            "container": "promtail",
            "version": HoleRef("promtail_ecr_image")
        }),
    ])
    
    # Simplified hole space - only need to fix the promtail image
    # The env label is already set from prompt 1 (could be production-us, staging-us, or dev-us)
    # So we need to try promtail images for all possible envs
    # The oracle will check env mismatch and prune invalid ones
    hole_space: HoleSpace = {
        "promtail_ecr_image": {
            # Valid ECR images for all possible envs (one will match the existing env label)
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/production-us/promtail:2.9.0",
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/staging-us/promtail:2.9.0",
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/dev-us/promtail:2.9.0",
            # Invalid: Public Docker images (what LLM gave) - will be pruned by constraints
            "grafana/promtail:latest",  # ❌ Invalid
            "docker.io/grafana/promtail:latest",  # ❌ Invalid
        }  # 5 values (3 valid for different envs, 2 invalid)
    }
    
    # Total: 5 combinations (1 valid)
    # Small search space, but demonstrates constraint learning from invalid values
    
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

