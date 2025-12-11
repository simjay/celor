"""Simplified oracles for minimal demo.

This module provides ECRPolicyOracle:
- Checks that images come from AWS ECR and env labels match

Note: Schema validation is provided by SchemaOracle in celor.k8s.oracles
"""

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from ruamel.yaml import YAML

from celor.core.schema.violation import Violation
from celor.k8s.artifact import K8sArtifact
from celor.k8s.constants import VALID_ENV_NAMES
from celor.k8s.utils import get_pod_template_label, get_containers

logger = logging.getLogger(__name__)


class ECRPolicyOracle:
    """Oracle that enforces AWS ECR image policy and environment label validation.
    
    Checks:
    1. Images must come from AWS ECR (not public Docker Hub)
    2. Environment label must exactly match company standard ("production-us", "staging-us", "dev-us")
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
            env = get_pod_template_label(manifest, "env")
            
            # Check all containers
            containers = get_containers(manifest)
            
            for i, container in enumerate(containers):
                image = container.get("image", "")
                container_name = container.get("name", f"container-{i}")
                
                if not image:
                    continue
                
                # Check 1: Image must come from ECR
                if not (f".dkr.ecr." in image and self.account_id in image):
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
                if env and f"/{env}/" not in image:
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

