"""K8s Patch DSL operations for modifying YAML manifests.

This module implements K8s-specific patch operations that modify Deployment
manifests using ruamel.yaml for format-preserving transformations.
"""

from typing import Dict, List, Optional

from ruamel.yaml import YAML

from celor.core.schema.patch_dsl import Patch, PatchOp
from celor.k8s.utils import get_containers


def _create_yaml_instance() -> YAML:
    """Create configured ruamel.yaml instance for K8s manifest editing.
    
    Returns:
        YAML instance configured to:
        - Preserve quotes and formatting
        - Not wrap long strings (prevents image field splitting)
        - Use block style (not flow style)
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096  # Very wide to prevent wrapping long strings like ECR paths
    yaml.default_flow_style = False  # Use block style, not flow style
    yaml.allow_unicode = True
    return yaml

# Resource profile mappings
RESOURCE_PROFILES = {
    "small": {
        "requests": {"cpu": "100m", "memory": "128Mi"},
        "limits": {"cpu": "200m", "memory": "256Mi"}
    },
    "medium": {
        "requests": {"cpu": "500m", "memory": "512Mi"},
        "limits": {"cpu": "1000m", "memory": "1Gi"}
    },
    "large": {
        "requests": {"cpu": "1000m", "memory": "1Gi"},
        "limits": {"cpu": "2000m", "memory": "2Gi"}
    }
}


def apply_k8s_patch(files: Dict[str, str], patch: Patch) -> Dict[str, str]:
    """Apply K8s patch operations to YAML files.
    
    Applies all patch operations sequentially to the files, preserving
    YAML formatting and comments.
    
    Args:
        files: Dict mapping file paths to YAML content strings
        patch: Patch containing K8s-specific operations
        
    Returns:
        Dict with patched YAML content
        
    Example:
        >>> files = {"deployment.yaml": "..."}
        >>> patch = Patch(ops=[PatchOp("EnsureReplicas", {"replicas": 5})])
        >>> patched_files = apply_k8s_patch(files, patch)
    """
    result_files = dict(files)
    
    for op in patch.ops:
        result_files = apply_k8s_op(result_files, op)
    
    return result_files


def apply_k8s_op(files: Dict[str, str], op: PatchOp) -> Dict[str, str]:
    """Apply single K8s patch operation.
    
    Args:
        files: Dict mapping file paths to YAML content
        op: Single patch operation to apply
        
    Returns:
        Dict with operation applied
        
    Raises:
        ValueError: If operation kind is unknown
    """
    if op.op == "EnsureLabel":
        return _apply_ensure_label(files, op.args)
    elif op.op == "EnsureImageVersion":
        return _apply_ensure_image_version(files, op.args)
    elif op.op == "EnsureSecurityBaseline":
        return _apply_ensure_security_baseline(files, op.args)
    elif op.op == "EnsureResourceProfile":
        return _apply_ensure_resource_profile(files, op.args)
    elif op.op == "EnsureReplicas":
        return _apply_ensure_replicas(files, op.args)
    elif op.op == "EnsurePriorityClass":
        return _apply_ensure_priority_class(files, op.args)
    else:
        raise ValueError(f"Unknown K8s patch operation: {op.op}")


def _apply_ensure_label(files: Dict[str, str], args: dict) -> Dict[str, str]:
    """Add or update labels in deployment manifest.
    
    Args:
        files: File dict
        args: {scope: str, key: str, value: str}
              scope: "deployment" | "podTemplate" | "both"
    """
    scope = args.get("scope", "both")
    key = args["key"]
    value = args["value"]
    
    result = dict(files)
    yaml = _create_yaml_instance()
    
    for filepath, content in files.items():
        manifest = yaml.load(content)
        
        # Only process Deployment manifests
        if manifest.get("kind") != "Deployment":
            continue
        
        # Ensure deployment metadata.labels exists
        if scope in ["deployment", "both"]:
            if "metadata" not in manifest:
                manifest["metadata"] = {}
            if "labels" not in manifest["metadata"]:
                manifest["metadata"]["labels"] = {}
            manifest["metadata"]["labels"][key] = value
        
        # Ensure pod template metadata.labels exists
        if scope in ["podTemplate", "both"]:
            if "spec" not in manifest:
                manifest["spec"] = {}
            if "template" not in manifest["spec"]:
                manifest["spec"]["template"] = {}
            if "metadata" not in manifest["spec"]["template"]:
                manifest["spec"]["template"]["metadata"] = {}
            if "labels" not in manifest["spec"]["template"]["metadata"]:
                manifest["spec"]["template"]["metadata"]["labels"] = {}
            manifest["spec"]["template"]["metadata"]["labels"][key] = value
        
        # Write back
        from io import StringIO
        stream = StringIO()
        yaml.dump(manifest, stream)
        result[filepath] = stream.getvalue()
    
    return result


def _apply_ensure_image_version(files: Dict[str, str], args: dict) -> Dict[str, str]:
    """Set container image version.
    
    Args:
        files: File dict
        args: {container: str, version: str}
    """
    container_name = args["container"]
    version = args["version"]
    
    result = dict(files)
    yaml = _create_yaml_instance()
    
    for filepath, content in files.items():
        manifest = yaml.load(content)
        
        # Only process Deployment manifests
        if manifest.get("kind") != "Deployment":
            continue
        
        # Find and update container image
        containers = get_containers(manifest)
        
        for container in containers:
            if container.get("name") == container_name:
                # Handle version: could be just tag or full ECR path
                current_image = container.get("image", "")
                
                # If version is a full ECR path, use it directly
                # ECR format: <account>.dkr.ecr.<region>.amazonaws.com/<repo>:<tag>
                if ".dkr.ecr." in version or version.startswith(("http://", "https://")):
                    # Full image path provided (e.g., ECR path)
                    container["image"] = version
                else:
                    # Just a tag/version provided
                    if ":" in current_image:
                        image_base = current_image.split(":")[0]
                    else:
                        image_base = current_image or container_name
                    
                    # Set new image with version
                    container["image"] = f"{image_base}:{version}"
        
        # Write back
        from io import StringIO
        stream = StringIO()
        yaml.dump(manifest, stream)
        result[filepath] = stream.getvalue()
    
    return result


def _apply_ensure_security_baseline(files: Dict[str, str], args: dict) -> Dict[str, str]:
    """Enforce security baseline on container.
    
    Args:
        files: File dict
        args: {container: str}
    """
    container_name = args["container"]
    
    result = dict(files)
    yaml = _create_yaml_instance()
    
    for filepath, content in files.items():
        manifest = yaml.load(content)
        
        # Only process Deployment manifests
        if manifest.get("kind") != "Deployment":
            continue
        
        # Find and update container securityContext
        containers = get_containers(manifest)
        
        for container in containers:
            if container.get("name") == container_name:
                if "securityContext" not in container:
                    container["securityContext"] = {}
                
                # Set security baseline
                container["securityContext"]["runAsNonRoot"] = True
                container["securityContext"]["allowPrivilegeEscalation"] = False
                container["securityContext"]["readOnlyRootFilesystem"] = True
                
                if "capabilities" not in container["securityContext"]:
                    container["securityContext"]["capabilities"] = {}
                container["securityContext"]["capabilities"]["drop"] = ["ALL"]
        
        # Write back
        from io import StringIO
        stream = StringIO()
        yaml.dump(manifest, stream)
        result[filepath] = stream.getvalue()
    
    return result


def _apply_ensure_resource_profile(files: Dict[str, str], args: dict) -> Dict[str, str]:
    """Set resource requests/limits from profile.
    
    Args:
        files: File dict
        args: {container: str, profile: str}
              profile: "small" | "medium" | "large"
    """
    container_name = args["container"]
    profile = args["profile"]
    
    if profile not in RESOURCE_PROFILES:
        raise ValueError(f"Unknown resource profile: {profile}. Valid: {list(RESOURCE_PROFILES.keys())}")
    
    profile_spec = RESOURCE_PROFILES[profile]
    
    result = dict(files)
    yaml = _create_yaml_instance()
    
    for filepath, content in files.items():
        manifest = yaml.load(content)
        
        # Only process Deployment manifests
        if manifest.get("kind") != "Deployment":
            continue
        
        # Find and update container resources
        containers = get_containers(manifest)
        
        for container in containers:
            if container.get("name") == container_name:
                container["resources"] = {
                    "requests": dict(profile_spec["requests"]),
                    "limits": dict(profile_spec["limits"])
                }
        
        # Write back
        from io import StringIO
        stream = StringIO()
        yaml.dump(manifest, stream)
        result[filepath] = stream.getvalue()
    
    return result


def _apply_ensure_replicas(files: Dict[str, str], args: dict) -> Dict[str, str]:
    """Set replica count.
    
    Args:
        files: File dict
        args: {replicas: int}
    """
    replicas = args["replicas"]
    
    result = dict(files)
    yaml = _create_yaml_instance()
    
    for filepath, content in files.items():
        manifest = yaml.load(content)
        
        # Only process Deployment manifests
        if manifest.get("kind") != "Deployment":
            continue
        
        # Set replicas
        if "spec" not in manifest:
            manifest["spec"] = {}
        manifest["spec"]["replicas"] = replicas
        
        # Write back
        from io import StringIO
        stream = StringIO()
        yaml.dump(manifest, stream)
        result[filepath] = stream.getvalue()
    
    return result


def _apply_ensure_priority_class(files: Dict[str, str], args: dict) -> Dict[str, str]:
    """Set priorityClassName.
    
    Args:
        files: File dict
        args: {name: str} - priority class name (or None to remove)
    """
    priority_class = args["name"]
    
    result = dict(files)
    yaml = _create_yaml_instance()
    
    for filepath, content in files.items():
        manifest = yaml.load(content)
        
        # Only process Deployment manifests
        if manifest.get("kind") != "Deployment":
            continue
        
        # Set priorityClassName
        if "spec" not in manifest:
            manifest["spec"] = {}
        
        if priority_class is None:
            # Remove priorityClassName if exists
            manifest["spec"].pop("priorityClassName", None)
        else:
            manifest["spec"]["priorityClassName"] = priority_class
        
        # Write back
        from io import StringIO
        stream = StringIO()
        yaml.dump(manifest, stream)
        result[filepath] = stream.getvalue()
    
    return result

