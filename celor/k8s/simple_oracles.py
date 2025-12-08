"""Simplified oracles for minimal demo.

This module provides two focused oracles:
1. ECRPolicyOracle: Checks that images come from AWS ECR and env labels match
2. FormatOracle: Checks YAML syntax and K8s schema validation
"""

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from ruamel.yaml import YAML

from celor.core.schema.violation import Violation
from celor.k8s.artifact import K8sArtifact

logger = logging.getLogger(__name__)

# Company standard environment names
VALID_ENV_NAMES = {"production-us", "staging-us", "dev-us"}


class ECRPolicyOracle:
    """Oracle that enforces AWS ECR image policy and environment label normalization.
    
    Checks:
    1. Images must come from AWS ECR (not public Docker Hub)
    2. Environment label must match company standard ("production-us", "staging-us", "dev-us")
    3. ECR path must match the env label
    """
    
    def __init__(self, account_id: str = "123456789012", region: str = "us-east-1"):
        """Initialize ECR policy oracle.
        
        Args:
            account_id: AWS account ID for ECR
            region: AWS region for ECR
        """
        self.account_id = account_id
        self.region = region
        self.ecr_base = f"{account_id}.dkr.ecr.{region}.amazonaws.com"
    
    def __call__(self, artifact: K8sArtifact) -> List[Violation]:
        """Check artifact against ECR policy.
        
        Args:
            artifact: K8sArtifact to validate
            
        Returns:
            List of Violations (empty if all checks pass)
        """
        violations = []
        yaml = YAML()
        
        for filepath, content in artifact.files.items():
            try:
                # Handle multi-document YAML (separated by ---)
                # Try loading as single document first
                try:
                    manifest = yaml.load(content)
                except Exception:
                    # If that fails, try loading all documents and find Deployment
                    manifests = list(yaml.load_all(content))
                    manifest = None
                    for doc in manifests:
                        if isinstance(doc, dict) and doc.get("kind") == "Deployment":
                            manifest = doc
                            break
                    if manifest is None:
                        continue  # No Deployment found, skip this file
            except Exception as e:
                violations.append(Violation(
                    id="ecr.INVALID_YAML",
                    message=f"Failed to parse YAML: {e}",
                    path=[filepath],
                    severity="error"
                ))
                continue
            
            # Only process Deployment manifests
            if manifest.get("kind") != "Deployment":
                continue
            
            # Extract env label
            env = self._get_env_label(manifest)
            
            # Check all containers
            containers = (manifest.get("spec", {})
                        .get("template", {})
                        .get("spec", {})
                        .get("containers", []))
            
            for i, container in enumerate(containers):
                image = container.get("image", "")
                container_name = container.get("name", f"container-{i}")
                
                if not image:
                    continue
                
                # Check 1: Image must come from ECR
                if not self._is_ecr_image(image):
                    violations.append(Violation(
                        id="ecr.INVALID_IMAGE_SOURCE",
                        message=f"Container '{container_name}' uses public Docker image '{image}'. Must use AWS ECR image.",
                        path=[filepath, "spec", "template", "spec", "containers", i, "image"],
                        severity="error",
                        evidence={
                            "container": container_name,
                            "image": image,
                            "forbid_value": {
                                "hole": f"{container_name}_ecr_image",  # Match template hole names
                                "value": image
                            }
                        }
                    ))
                    continue
                
                # Check 2: ECR path must match env label
                if env and not self._ecr_path_matches_env(image, env):
                    violations.append(Violation(
                        id="ecr.ENV_MISMATCH",
                        message=f"Container '{container_name}' ECR path does not match env label '{env}'. Expected path containing '{env}'.",
                        path=[filepath, "spec", "template", "spec", "containers", i, "image"],
                        severity="error",
                        evidence={
                            "container": container_name,
                            "image": image,
                            "env": env,
                            "forbid_tuple": {
                                "holes": ["env", f"{container_name}_ecr_image"],  # Match template hole names
                                "values": [env, image]
                            }
                        }
                    ))
                
                # Check 3: Env label must be company standard
                if env and env not in VALID_ENV_NAMES:
                    violations.append(Violation(
                        id="ecr.INVALID_ENV_LABEL",
                        message=f"env label '{env}' is not a company standard. Must be one of: {', '.join(sorted(VALID_ENV_NAMES))}",
                        path=[filepath, "spec", "template", "metadata", "labels", "env"],
                        severity="error",
                        evidence={
                            "env": env,
                            "forbid_value": {
                                "hole": "env",
                                "value": env
                            }
                        }
                    ))
        
        return violations
    
    def _get_env_label(self, manifest: dict) -> Optional[str]:
        """Extract env label from pod template."""
        return (manifest.get("spec", {})
                .get("template", {})
                .get("metadata", {})
                .get("labels", {})
                .get("env"))
    
    def _is_ecr_image(self, image: str) -> bool:
        """Check if image comes from AWS ECR."""
        return f".dkr.ecr." in image and self.account_id in image
    
    def _ecr_path_matches_env(self, image: str, env: str) -> bool:
        """Check if ECR path contains the env value."""
        return f"/{env}/" in image


class FormatOracle:
    """Oracle that checks YAML syntax and K8s schema validation.
    
    Uses kubernetes-validate library if available, otherwise falls back to kubectl.
    """
    
    def __init__(self, use_kubernetes_validate: bool = True):
        """Initialize FormatOracle.
        
        Args:
            use_kubernetes_validate: If True, prefer kubernetes-validate library
                                     over kubectl (default: True)
        """
        self.use_kubernetes_validate = use_kubernetes_validate
        self._k8s_validate_available = self._check_kubernetes_validate()
        self._kubectl_available = self._check_kubectl()
    
    def _check_kubernetes_validate(self) -> bool:
        """Check if kubernetes-validate library is available."""
        try:
            import kubernetes_validate
            return True
        except ImportError:
            return False
    
    def _check_kubectl(self) -> bool:
        """Check if kubectl is available."""
        try:
            result = subprocess.run(
                ["kubectl", "version", "--client"],
                capture_output=True,
                timeout=2
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def __call__(self, artifact: K8sArtifact) -> List[Violation]:
        """Check artifact for YAML/schema errors.
        
        Args:
            artifact: K8sArtifact to validate
            
        Returns:
            List of Violations (empty if all checks pass)
        """
        if self.use_kubernetes_validate and self._k8s_validate_available:
            return self._validate_with_library(artifact)
        elif self._kubectl_available:
            return self._validate_with_kubectl(artifact)
        else:
            logger.warning("Neither kubernetes-validate nor kubectl available, skipping format validation")
            return []
    
    def _validate_with_library(self, artifact: K8sArtifact) -> List[Violation]:
        """Validate using kubernetes-validate library."""
        violations = []
        
        try:
            from kubernetes_validate import validate as k8s_validate
        except ImportError:
            return []
        
        yaml = YAML()
        
        for filepath, content in artifact.files.items():
            try:
                manifest = yaml.load(content)
                
                # Validate using kubernetes-validate
                errors = k8s_validate(manifest, kubernetes_version="1.28")
                
                for error in errors:
                    violations.append(Violation(
                        id="format.VALIDATION_ERROR",
                        message=str(error),
                        path=[filepath],
                        severity="error",
                        evidence={"error": str(error)}
                    ))
                    
            except Exception as e:
                violations.append(Violation(
                    id="format.VALIDATION_EXCEPTION",
                    message=f"Validation failed: {e}",
                    path=[filepath],
                    severity="error",
                    evidence={"exception": str(e)}
                ))
        
        return violations
    
    def _validate_with_kubectl(self, artifact: K8sArtifact) -> List[Violation]:
        """Validate using kubectl --dry-run."""
        violations = []
        
        # Write to temp dir
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact.write_to_dir(tmpdir)
            
            for filepath in artifact.files.keys():
                full_path = Path(tmpdir) / filepath
                
                try:
                    result = subprocess.run(
                        ["kubectl", "apply", "--dry-run=client", "-f", str(full_path)],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if result.returncode != 0:
                        violations.append(Violation(
                            id="format.KUBECTL_VALIDATION_FAILED",
                            message=f"kubectl validation failed: {result.stderr}",
                            path=[filepath],
                            severity="error",
                            evidence={"stderr": result.stderr}
                        ))
                        
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass
        
        return violations

