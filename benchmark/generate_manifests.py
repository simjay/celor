#!/usr/bin/env python3
"""
Generate 100 broken Kubernetes manifests for benchmark evaluation.

This script generates Kubernetes deployment manifests with known violations
to serve as benchmark targets for comparing Pure-LLM vs CeLoR repair approaches.
"""

import json
import random
from pathlib import Path
from typing import Dict, List, Tuple

from ruamel.yaml import YAML

# Configuration
BENCHMARK_DIR = Path(__file__).parent
MANIFESTS_DIR = BENCHMARK_DIR / "manifests"
MANIFESTS_DIR.mkdir(exist_ok=True)

# Application names for variation
APP_NAMES = [
    "web-app", "api-service", "worker-pool", "frontend", "backend",
    "payments-api", "user-service", "data-processor", "cache-service", "queue-worker"
]

# Container images
CONTAINER_IMAGES = {
    "nginx": ["nginx:latest", "nginx:1.25.0", "nginx:1.24.0"],
    "redis": ["redis:latest", "redis:7.0", "redis:6.2"],
    "postgres": ["postgres:latest", "postgres:15", "postgres:14"],
    "node": ["node:latest", "node:18", "node:20"],
    "python": ["python:latest", "python:3.11", "python:3.10"],
}

# Environments
ENVIRONMENTS = ["production-us", "staging-us", "dev-us"]
TEAMS = ["payments", "platform", "data", "frontend", "backend"]
TIERS = ["frontend", "backend", "data"]

# ECR base (for valid images)
ECR_BASE = "123456789012.dkr.ecr.us-east-1.amazonaws.com"

# Resource profiles
RESOURCE_PROFILES = {
    "small": {"cpu": "100m", "memory": "128Mi"},
    "medium": {"cpu": "500m", "memory": "512Mi"},
    "large": {"cpu": "1000m", "memory": "1Gi"},
}


def generate_base_manifest(
    app_name: str,
    container_name: str,
    image: str,
    env: str,
    team: str,
    tier: str,
    replicas: int,
    profile: str = "medium",
    include_security: bool = True,
    include_resources: bool = True,
) -> Dict:
    """Generate a base Kubernetes deployment manifest.
    
    Args:
        app_name: Application name
        container_name: Container name
        image: Container image
        env: Environment label value
        team: Team label value
        tier: Tier label value
        replicas: Number of replicas
        profile: Resource profile (small, medium, large)
        include_security: Whether to include security context
        include_resources: Whether to include resource limits
        
    Returns:
        Dictionary representing the Kubernetes manifest
    """
    resources = RESOURCE_PROFILES.get(profile, RESOURCE_PROFILES["medium"])
    
    manifest = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": app_name,
            "labels": {
                "app": app_name,
            }
        },
        "spec": {
            "replicas": replicas,
            "selector": {
                "matchLabels": {
                    "app": app_name
                }
            },
            "template": {
                "metadata": {
                    "labels": {
                        "app": app_name,
                    }
                },
                "spec": {
                    "containers": [
                        {
                            "name": container_name,
                            "image": image,
                        }
                    ]
                }
            }
        }
    }
    
    # Add labels if provided
    if env:
        manifest["spec"]["template"]["metadata"]["labels"]["env"] = env
    if team:
        manifest["spec"]["template"]["metadata"]["labels"]["team"] = team
    if tier:
        manifest["spec"]["template"]["metadata"]["labels"]["tier"] = tier
    
    # Add resources
    if include_resources:
        manifest["spec"]["template"]["spec"]["containers"][0]["resources"] = {
            "requests": {
                "cpu": resources["cpu"],
                "memory": resources["memory"]
            },
            "limits": {
                "cpu": resources["cpu"],
                "memory": resources["memory"]
            }
        }
    
    # Add security context
    if include_security:
        manifest["spec"]["template"]["spec"]["containers"][0]["securityContext"] = {
            "runAsNonRoot": True,
            "allowPrivilegeEscalation": False,
            "readOnlyRootFilesystem": True,
            "capabilities": {
                "drop": ["ALL"]
            }
        }
    
    # Add priority class for prod
    if env == "production-us":
        manifest["spec"]["priorityClassName"] = "critical"
    
    return manifest


def apply_violation_ecr_policy(manifest: Dict, use_public_image: bool = True) -> Dict:
    """Apply ECR policy violation: use public Docker Hub image instead of ECR.
    
    Args:
        manifest: Manifest to modify
        use_public_image: If True, use public image; if False, use wrong ECR env
        
    Returns:
        Modified manifest
    """
    container = manifest["spec"]["template"]["spec"]["containers"][0]
    original_image = container["image"]
    
    if use_public_image:
        # Extract image name (e.g., "nginx" from "nginx:latest" or ECR path)
        if ":" in original_image:
            image_name = original_image.split(":")[0].split("/")[-1]
        else:
            image_name = original_image.split("/")[-1]
        
        # Use public Docker Hub image
        container["image"] = f"{image_name}:latest"
    else:
        # Use ECR image but with wrong environment
        env = manifest["spec"]["template"]["metadata"]["labels"].get("env", "production-us")
        wrong_env = "staging-us" if env == "production-us" else "production-us"
        image_name = "nginx"  # Default
        container["image"] = f"{ECR_BASE}/{wrong_env}/{image_name}:latest"
    
    return manifest


def apply_violation_missing_label(manifest: Dict, label: str) -> Dict:
    """Apply missing label violation.
    
    Args:
        manifest: Manifest to modify
        label: Label to remove (env, team, or tier)
        
    Returns:
        Modified manifest
    """
    labels = manifest["spec"]["template"]["metadata"]["labels"]
    if label in labels:
        del labels[label]
    return manifest


def apply_violation_wrong_replicas(manifest: Dict, env: str) -> Dict:
    """Apply wrong replica count violation for prod.
    
    Args:
        manifest: Manifest to modify
        env: Environment (prod requires 3-5 replicas)
        
    Returns:
        Modified manifest
    """
    if env == "production-us":
        # Set replicas to invalid value (too low or too high)
        manifest["spec"]["replicas"] = random.choice([1, 2, 6, 10])
    return manifest


def apply_violation_missing_security(manifest: Dict) -> Dict:
    """Apply missing security context violation.
    
    Args:
        manifest: Manifest to modify
        
    Returns:
        Modified manifest
    """
    container = manifest["spec"]["template"]["spec"]["containers"][0]
    if "securityContext" in container:
        del container["securityContext"]
    return manifest


def apply_violation_missing_resources(manifest: Dict) -> Dict:
    """Apply missing resource limits violation.
    
    Args:
        manifest: Manifest to modify
        
    Returns:
        Modified manifest
    """
    container = manifest["spec"]["template"]["spec"]["containers"][0]
    if "resources" in container:
        del container["resources"]
    return manifest


def apply_violation_wrong_profile(manifest: Dict, env: str) -> Dict:
    """Apply wrong resource profile violation (prod can't use small).
    
    Args:
        manifest: Manifest to modify
        env: Environment
        
    Returns:
        Modified manifest
    """
    if env == "production-us":
        container = manifest["spec"]["template"]["spec"]["containers"][0]
        container["resources"] = {
            "requests": {
                "cpu": RESOURCE_PROFILES["small"]["cpu"],
                "memory": RESOURCE_PROFILES["small"]["memory"]
            },
            "limits": {
                "cpu": RESOURCE_PROFILES["small"]["cpu"],
                "memory": RESOURCE_PROFILES["small"]["memory"]
            }
        }
    return manifest


def apply_violation_missing_priority_class(manifest: Dict, env: str) -> Dict:
    """Apply missing priority class violation for prod.
    
    Args:
        manifest: Manifest to modify
        env: Environment
        
    Returns:
        Modified manifest
    """
    if env == "production-us" and "priorityClassName" in manifest["spec"]:
        del manifest["spec"]["priorityClassName"]
    return manifest


def generate_case(
    case_id: int,
    violation_types: List[str],
    app_name: str = None,
    container_name: str = None,
    image: str = None,
    env: str = None,
    team: str = None,
    tier: str = None,
    replicas: int = None,
    profile: str = None,
) -> Tuple[Dict, List[str]]:
    """Generate a single benchmark case with specified violations.
    
    Args:
        case_id: Case number (001-100)
        violation_types: List of violation types to apply
        app_name: Optional app name (random if not provided)
        container_name: Optional container name (random if not provided)
        image: Optional image (random if not provided)
        env: Optional environment (random if not provided)
        team: Optional team (random if not provided)
        tier: Optional tier (random if not provided)
        replicas: Optional replicas (random if not provided)
        profile: Optional profile (random if not provided)
        
    Returns:
        Tuple of (manifest dict, violation_types list)
    """
    # Randomize if not provided
    if app_name is None:
        app_name = random.choice(APP_NAMES)
    if container_name is None:
        container_name = random.choice(["web", "api", "worker", "app", "service"])
    if image is None:
        image_type = random.choice(list(CONTAINER_IMAGES.keys()))
        image = random.choice(CONTAINER_IMAGES[image_type])
    if env is None:
        env = random.choice(ENVIRONMENTS)
    if team is None:
        team = random.choice(TEAMS)
    if tier is None:
        tier = random.choice(TIERS)
    if replicas is None:
        replicas = random.choice([1, 2, 3, 4, 5, 6])
    if profile is None:
        profile = random.choice(["small", "medium", "large"])
    
    # Generate base manifest
    include_security = "missing_security" not in violation_types
    include_resources = "missing_resources" not in violation_types and "wrong_profile" not in violation_types
    
    manifest = generate_base_manifest(
        app_name=app_name,
        container_name=container_name,
        image=image,
        env=env,
        team=team,
        tier=tier,
        replicas=replicas,
        profile=profile,
        include_security=include_security,
        include_resources=include_resources,
    )
    
    # Apply violations
    for violation in violation_types:
        if violation == "ecr_policy":
            manifest = apply_violation_ecr_policy(manifest, use_public_image=True)
        elif violation == "ecr_wrong_env":
            manifest = apply_violation_ecr_policy(manifest, use_public_image=False)
        elif violation == "missing_label_env":
            manifest = apply_violation_missing_label(manifest, "env")
        elif violation == "missing_label_team":
            manifest = apply_violation_missing_label(manifest, "team")
        elif violation == "missing_label_tier":
            manifest = apply_violation_missing_label(manifest, "tier")
        elif violation == "wrong_replicas":
            manifest = apply_violation_wrong_replicas(manifest, env)
        elif violation == "missing_security":
            manifest = apply_violation_missing_security(manifest)
        elif violation == "missing_resources":
            manifest = apply_violation_missing_resources(manifest)
        elif violation == "wrong_profile":
            manifest = apply_violation_wrong_profile(manifest, env)
        elif violation == "missing_priority_class":
            manifest = apply_violation_missing_priority_class(manifest, env)
    
    return manifest, violation_types


def generate_all_cases() -> List[Tuple[int, Dict, List[str]]]:
    """Generate all 100 benchmark cases with diverse violation patterns.
    
    Strategy: Create 20-30 unique violation patterns by:
    - Mixing production-us and non-production environments
    - Combining different violation types
    - Ensuring each pattern appears 2-5 times for Fix Bank evaluation
    
    Returns:
        List of tuples: (case_id, manifest, violation_types)
    """
    cases = []
    case_id = 1
    
    # Pattern 1: Single ECR violation (non-prod) - 6 cases
    for i in range(6):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy"], env=random.choice(["staging-us", "dev-us"]))))
        case_id += 1
    
    # Pattern 2: Single ECR violation (prod) - 4 cases (triggers image tag violation too)
    for i in range(4):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy"], env="production-us")))
        case_id += 1
    
    # Pattern 3: Single security violation - 5 cases
    for i in range(5):
        cases.append((case_id, *generate_case(case_id, ["missing_security"])))
        case_id += 1
    
    # Pattern 4: Single resource violation - 3 cases
    for i in range(3):
        cases.append((case_id, *generate_case(case_id, ["missing_resources"])))
        case_id += 1
    
    # Pattern 5: ECR + Security (non-prod) - 4 cases
    for i in range(4):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy", "missing_security"], env=random.choice(["staging-us", "dev-us"]))))
        case_id += 1
    
    # Pattern 6: ECR + Security (prod) - 3 cases
    for i in range(3):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy", "missing_security"], env="production-us")))
        case_id += 1
    
    # Pattern 7: ECR + Resource (non-prod) - 4 cases
    for i in range(4):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy", "missing_resources"], env=random.choice(["staging-us", "dev-us"]))))
        case_id += 1
    
    # Pattern 8: ECR + Resource (prod) - 3 cases
    for i in range(3):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy", "missing_resources"], env="production-us")))
        case_id += 1
    
    # Pattern 9: Security + Resource - 4 cases
    for i in range(4):
        cases.append((case_id, *generate_case(case_id, ["missing_security", "missing_resources"])))
        case_id += 1
    
    # Pattern 10: ECR + Missing Label (prod) - 4 cases
    for i in range(4):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy", "missing_label_env"], env="production-us")))
        case_id += 1
    
    # Pattern 11: ECR + Missing Label (non-prod) - 3 cases
    for i in range(3):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy", "missing_label_team"], env=random.choice(["staging-us", "dev-us"]))))
        case_id += 1
    
    # Pattern 12: ECR + Wrong Replicas (prod) - 4 cases
    for i in range(4):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy", "wrong_replicas"], env="production-us")))
        case_id += 1
    
    # Pattern 13: ECR + Wrong Profile (prod) - 4 cases
    for i in range(4):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy", "wrong_profile"], env="production-us")))
        case_id += 1
    
    # Pattern 14: ECR + Missing Priority (prod) - 3 cases
    for i in range(3):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy", "missing_priority_class"], env="production-us")))
        case_id += 1
    
    # Pattern 15: ECR + Security + Resource (non-prod) - 4 cases
    for i in range(4):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy", "missing_security", "missing_resources"], env=random.choice(["staging-us", "dev-us"]))))
        case_id += 1
    
    # Pattern 16: ECR + Security + Resource (prod) - 4 cases
    for i in range(4):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy", "missing_security", "missing_resources"], env="production-us")))
        case_id += 1
    
    # Pattern 17: ECR + Security + Missing Label (prod) - 3 cases
    for i in range(3):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy", "missing_security", "missing_label_env"], env="production-us")))
        case_id += 1
    
    # Pattern 18: ECR + Resource + Missing Label (prod) - 3 cases
    for i in range(3):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy", "missing_resources", "missing_label_team"], env="production-us")))
        case_id += 1
    
    # Pattern 19: ECR + Wrong Replicas + Wrong Profile (prod) - 3 cases
    for i in range(3):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy", "wrong_replicas", "wrong_profile"], env="production-us")))
        case_id += 1
    
    # Pattern 20: ECR + Security + Resource + Missing Label (non-prod) - 3 cases
    for i in range(3):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy", "missing_security", "missing_resources", "missing_label_tier"], env=random.choice(["staging-us", "dev-us"]))))
        case_id += 1
    
    # Pattern 21: ECR + Security + Resource + Missing Label (prod) - 4 cases
    for i in range(4):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy", "missing_security", "missing_resources", "missing_label_env"], env="production-us")))
        case_id += 1
    
    # Pattern 22: ECR + Security + Wrong Replicas (prod) - 3 cases
    for i in range(3):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy", "missing_security", "wrong_replicas"], env="production-us")))
        case_id += 1
    
    # Pattern 23: ECR + Resource + Wrong Replicas (prod) - 3 cases
    for i in range(3):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy", "missing_resources", "wrong_replicas"], env="production-us")))
        case_id += 1
    
    # Pattern 24: ECR + Security + Resource + Wrong Replicas (prod) - 3 cases
    for i in range(3):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy", "missing_security", "missing_resources", "wrong_replicas"], env="production-us")))
        case_id += 1
    
    # Pattern 25: ECR + Security + Resource + Missing Label + Wrong Replicas (prod) - 3 cases
    for i in range(3):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy", "missing_security", "missing_resources", "missing_label_env", "wrong_replicas"], env="production-us")))
        case_id += 1
    
    # Pattern 26: ECR + Security + Resource + Wrong Profile (prod) - 2 cases
    for i in range(2):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy", "missing_security", "missing_resources", "wrong_profile"], env="production-us")))
        case_id += 1
    
    # Pattern 27: ECR + Security + Resource + Missing Priority (prod) - 2 cases
    for i in range(2):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy", "missing_security", "missing_resources", "missing_priority_class"], env="production-us")))
        case_id += 1
    
    # Pattern 28: ECR + Security + Resource + Missing Label + Wrong Profile (prod) - 2 cases
    for i in range(2):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy", "missing_security", "missing_resources", "missing_label_env", "wrong_profile"], env="production-us")))
        case_id += 1
    
    # Pattern 29: ECR + Security + Resource + Missing Label + Missing Priority (prod) - 2 cases
    for i in range(2):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy", "missing_security", "missing_resources", "missing_label_env", "missing_priority_class"], env="production-us")))
        case_id += 1
    
    # Pattern 30: Complex - All violations (prod) - 2 cases
    for i in range(2):
        cases.append((case_id, *generate_case(case_id, ["ecr_policy", "missing_security", "missing_resources", "missing_label_env", "wrong_replicas", "wrong_profile", "missing_priority_class"], env="production-us")))
        case_id += 1
    
    return cases


def save_manifest(case_id: int, manifest: Dict) -> Path:
    """Save manifest to YAML file.
    
    Args:
        case_id: Case number
        manifest: Manifest dictionary
        
    Returns:
        Path to saved file
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 120
    
    filename = f"case_{case_id:03d}.yaml"
    filepath = MANIFESTS_DIR / filename
    
    with open(filepath, "w") as f:
        yaml.dump(manifest, f)
    
    return filepath


def main():
    """Generate all benchmark manifests."""
    print("Generating 100 benchmark manifests...")
    print(f"Output directory: {MANIFESTS_DIR}")
    
    cases = generate_all_cases()
    
    print(f"\nGenerated {len(cases)} cases:")
    for case_id, manifest, violations in cases:
        filepath = save_manifest(case_id, manifest)
        print(f"  Case {case_id:03d}: {filepath.name} - Violations: {', '.join(violations)}")
    
    print(f"\n✅ Generated {len(cases)} manifests in {MANIFESTS_DIR}")
    print(f"\nNext steps:")
    print(f"  1. Run: python validate_manifests.py")
    print(f"  2. Review generated manifests")


if __name__ == "__main__":
    main()
