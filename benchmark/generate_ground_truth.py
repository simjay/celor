#!/usr/bin/env python3
"""
Generate ground truth data for all benchmark cases.

For each broken manifest, creates:
- case_XXX_fixed.yaml: Expected repaired manifest
- case_XXX_violations.json: Complete violation list
- case_XXX_metadata.json: Case metadata (complexity, search space, expected fixes)
"""

import json
from pathlib import Path
from typing import Dict, List

from ruamel.yaml import YAML
from celor.k8s.artifact import K8sArtifact
from celor.k8s.oracle_config import get_oracles_for_scenario

# Configuration
BENCHMARK_DIR = Path(__file__).parent
MANIFESTS_DIR = BENCHMARK_DIR / "manifests"
GROUND_TRUTH_DIR = BENCHMARK_DIR / "ground_truth"
GROUND_TRUTH_DIR.mkdir(exist_ok=True)

# ECR base for valid images
ECR_BASE = "123456789012.dkr.ecr.us-east-1.amazonaws.com"

# Resource profiles
RESOURCE_PROFILES = {
    "small": {"cpu": "100m", "memory": "128Mi"},
    "medium": {"cpu": "500m", "memory": "512Mi"},
    "large": {"cpu": "1000m", "memory": "1Gi"},
}


def fix_manifest(manifest: Dict) -> Dict:
    """Fix a broken manifest by applying all necessary corrections.
    
    Args:
        manifest: Broken manifest dictionary
        
    Returns:
        Fixed manifest dictionary
    """
    fixed = manifest.copy()
    
    # Deep copy to avoid modifying original
    import copy
    fixed = copy.deepcopy(manifest)
    
    # Get container and labels
    container = fixed["spec"]["template"]["spec"]["containers"][0]
    labels = fixed["spec"]["template"]["metadata"]["labels"]
    env = labels.get("env", "")
    
    # Fix 1: ECR image policy
    image = container.get("image", "")
    if image and not image.startswith(ECR_BASE):
        # Extract image name
        if ":" in image:
            image_name = image.split(":")[0].split("/")[-1]
        else:
            image_name = image.split("/")[-1]
        
        # Use appropriate ECR path based on env
        if env == "production-us":
            fixed_image = f"{ECR_BASE}/production-us/{image_name}:1.25.0"
        elif env == "staging-us":
            fixed_image = f"{ECR_BASE}/staging-us/{image_name}:1.25.0"
        elif env == "dev-us":
            fixed_image = f"{ECR_BASE}/dev-us/{image_name}:1.25.0"
        else:
            fixed_image = f"{ECR_BASE}/production-us/{image_name}:1.25.0"
        
        container["image"] = fixed_image
    
    # Fix 2: Missing labels
    if "env" not in labels:
        labels["env"] = env or "production-us"
    if "team" not in labels:
        labels["team"] = "platform"
    if "tier" not in labels:
        labels["tier"] = "backend"
    
    # Fix 3: Wrong replicas for prod
    if env == "production-us":
        replicas = fixed["spec"].get("replicas", 3)
        if replicas < 3 or replicas > 5:
            fixed["spec"]["replicas"] = 3
    
    # Fix 4: Missing security context
    if "securityContext" not in container:
        container["securityContext"] = {
            "runAsNonRoot": True,
            "allowPrivilegeEscalation": False,
            "readOnlyRootFilesystem": True,
            "capabilities": {
                "drop": ["ALL"]
            }
        }
    
    # Fix 5: Missing resources
    if "resources" not in container:
        container["resources"] = {
            "requests": {
                "cpu": RESOURCE_PROFILES["medium"]["cpu"],
                "memory": RESOURCE_PROFILES["medium"]["memory"]
            },
            "limits": {
                "cpu": RESOURCE_PROFILES["medium"]["cpu"],
                "memory": RESOURCE_PROFILES["medium"]["memory"]
            }
        }
    else:
        # Ensure both requests and limits exist
        resources = container["resources"]
        if "requests" not in resources:
            resources["requests"] = {
                "cpu": RESOURCE_PROFILES["medium"]["cpu"],
                "memory": RESOURCE_PROFILES["medium"]["memory"]
            }
        if "limits" not in resources:
            resources["limits"] = {
                "cpu": RESOURCE_PROFILES["medium"]["cpu"],
                "memory": RESOURCE_PROFILES["medium"]["memory"]
            }
    
    # Fix 6: Wrong profile for prod (can't use small)
    if env == "production-us" and "resources" in container:
        resources = container["resources"]
        cpu = resources.get("requests", {}).get("cpu", "")
        memory = resources.get("requests", {}).get("memory", "")
        
        if "100m" in cpu or "128Mi" in memory:
            # Upgrade to medium
            resources["requests"] = {
                "cpu": RESOURCE_PROFILES["medium"]["cpu"],
                "memory": RESOURCE_PROFILES["medium"]["memory"]
            }
            resources["limits"] = {
                "cpu": RESOURCE_PROFILES["medium"]["cpu"],
                "memory": RESOURCE_PROFILES["medium"]["memory"]
            }
    
    # Fix 7: Missing priority class for prod
    if env == "production-us" and "priorityClassName" not in fixed["spec"]:
        fixed["spec"]["priorityClassName"] = "critical"
    
    return fixed


def get_violations(manifest_path: Path) -> List[Dict]:
    """Get violations for a manifest.
    
    Args:
        manifest_path: Path to manifest file
        
    Returns:
        List of violation dictionaries
    """
    artifact = K8sArtifact.from_file(str(manifest_path))
    # Use unified benchmark oracle configuration
    oracles = get_oracles_for_scenario("benchmark", include_external=False)
    
    all_violations = []
    for oracle in oracles:
        violations = oracle(artifact)
        all_violations.extend(violations)
    
    return [
        {
            "id": v.id,
            "message": v.message,
            "severity": v.severity,
            "path": v.path,
        }
        for v in all_violations
    ]


def calculate_search_space_size(violation_types: List[str]) -> int:
    """Estimate search space size based on violation types.
    
    This is a simplified estimation. Actual search space depends on
    the specific hole space used during repair.
    
    Args:
        violation_types: List of violation type strings
        
    Returns:
        Estimated search space size
    """
    # Base estimation: each violation type adds complexity
    base = 1
    
    if "ecr_policy" in violation_types:
        base *= 6  # ~6 ECR image options
    if "missing_label_env" in violation_types or "missing_label_team" in violation_types or "missing_label_tier" in violation_types:
        base *= 3  # ~3 label value options
    if "wrong_replicas" in violation_types:
        base *= 3  # 3-5 replicas for prod
    if "missing_security" in violation_types:
        base *= 1  # Security context is binary (add or not)
    if "missing_resources" in violation_types or "wrong_profile" in violation_types:
        base *= 3  # 3 resource profiles
    
    return base


def generate_metadata(
    case_id: int,
    violation_types: List[str],
    violations: List[Dict],
    fixed_manifest: Dict,
) -> Dict:
    """Generate metadata for a case.
    
    Args:
        case_id: Case number
        violation_types: List of violation types
        violations: List of violation dictionaries
        fixed_manifest: Fixed manifest
        
    Returns:
        Metadata dictionary
    """
    # Determine complexity
    violation_count = len(violations)
    if violation_count == 1:
        complexity = "easy"
    elif violation_count == 2:
        complexity = "medium"
    elif violation_count == 3:
        complexity = "hard"
    else:
        complexity = "very_hard"
    
    # Estimate search space
    search_space_size = calculate_search_space_size(violation_types)
    
    # Determine expected fixes
    expected_fixes = []
    if "ecr_policy" in violation_types:
        expected_fixes.append({"type": "EnsureImageVersion", "container": "web"})
    if "missing_label_env" in violation_types:
        expected_fixes.append({"type": "EnsureLabel", "key": "env", "value": "production-us"})
    if "missing_label_team" in violation_types:
        expected_fixes.append({"type": "EnsureLabel", "key": "team", "value": "platform"})
    if "missing_label_tier" in violation_types:
        expected_fixes.append({"type": "EnsureLabel", "key": "tier", "value": "backend"})
    if "missing_security" in violation_types:
        expected_fixes.append({"type": "EnsureSecurityBaseline", "container": "web"})
    if "missing_resources" in violation_types or "wrong_profile" in violation_types:
        expected_fixes.append({"type": "EnsureResourceProfile", "container": "web", "profile": "medium"})
    if "wrong_replicas" in violation_types:
        expected_fixes.append({"type": "EnsureReplicas", "replicas": 3})
    if "missing_priority_class" in violation_types:
        expected_fixes.append({"type": "EnsurePriorityClass", "name": "critical"})
    
    return {
        "case_id": f"{case_id:03d}",
        "violation_types": violation_types,
        "violation_count": violation_count,
        "complexity": complexity,
        "expected_fixes": expected_fixes,
        "search_space_size": search_space_size,
        "difficulty": complexity,
    }


def process_case(case_id: int) -> bool:
    """Process a single case and generate ground truth.
    
    Args:
        case_id: Case number
        
    Returns:
        True if successful, False otherwise
    """
    try:
        manifest_path = MANIFESTS_DIR / f"case_{case_id:03d}.yaml"
        
        if not manifest_path.exists():
            print(f"  ⚠️  Case {case_id:03d}: Manifest not found")
            return False
        
        # Load broken manifest
        yaml = YAML()
        with open(manifest_path) as f:
            broken_manifest = yaml.load(f)
        
        # Get violations
        violations = get_violations(manifest_path)
        
        # Extract violation types from violations
        violation_types = sorted(list(set(v.id.split(".")[0] for v in [type('obj', (object,), v) for v in violations])))
        # Better approach: extract from violation IDs
        violation_type_set = set()
        for v in violations:
            vtype = v["id"].split(".")[0]
            violation_type_set.add(vtype)
            # Also check for specific violation patterns
            if "IMAGE_NOT_FROM_ECR" in v["id"]:
                violation_type_set.add("ecr_policy")
            if "MISSING_LABEL" in v["id"] or "missing_label" in v["id"].lower():
                if "ENV" in v["id"]:
                    violation_type_set.add("missing_label_env")
                elif "TEAM" in v["id"]:
                    violation_type_set.add("missing_label_team")
                elif "TIER" in v["id"]:
                    violation_type_set.add("missing_label_tier")
            if "NO_RUN_AS_NON_ROOT" in v["id"] or "PRIVILEGE" in v["id"]:
                violation_type_set.add("missing_security")
            if "RESOURCE" in v["id"]:
                violation_type_set.add("missing_resources")
            if "REPLICA" in v["id"]:
                violation_type_set.add("wrong_replicas")
        
        violation_types = sorted(list(violation_type_set))
        
        # Fix manifest
        fixed_manifest = fix_manifest(broken_manifest)
        
        # Generate metadata
        metadata = generate_metadata(case_id, violation_types, violations, fixed_manifest)
        
        # Save fixed manifest
        fixed_path = GROUND_TRUTH_DIR / f"case_{case_id:03d}_fixed.yaml"
        yaml = YAML()
        yaml.preserve_quotes = True
        yaml.width = 120
        with open(fixed_path, "w") as f:
            yaml.dump(fixed_manifest, f)
        
        # Save violations
        violations_path = GROUND_TRUTH_DIR / f"case_{case_id:03d}_violations.json"
        violations_path.write_text(json.dumps(violations, indent=2))
        
        # Save metadata
        metadata_path = GROUND_TRUTH_DIR / f"case_{case_id:03d}_metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2))
        
        return True
        
    except Exception as e:
        print(f"  ❌ Case {case_id:03d}: Error - {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Generate ground truth for all cases."""
    print("Generating ground truth for all benchmark cases...")
    print(f"Manifests directory: {MANIFESTS_DIR}")
    print(f"Ground truth directory: {GROUND_TRUTH_DIR}\n")
    
    manifest_files = sorted(MANIFESTS_DIR.glob("case_*.yaml"))
    
    if not manifest_files:
        print(f"❌ Error: No manifest files found in {MANIFESTS_DIR}")
        print("   Run generate_manifests.py first")
        return
    
    print(f"Processing {len(manifest_files)} cases...\n")
    
    success_count = 0
    for manifest_file in manifest_files:
        case_id = int(manifest_file.stem.split("_")[1])
        print(f"Processing case {case_id:03d}...", end=" ")
        
        if process_case(case_id):
            print("✅")
            success_count += 1
        else:
            print("❌")
    
    print(f"\n✅ Generated ground truth for {success_count}/{len(manifest_files)} cases")
    print(f"   Fixed manifests: {GROUND_TRUTH_DIR}/*_fixed.yaml")
    print(f"   Violation lists: {GROUND_TRUTH_DIR}/*_violations.json")
    print(f"   Metadata: {GROUND_TRUTH_DIR}/*_metadata.json")


if __name__ == "__main__":
    main()
