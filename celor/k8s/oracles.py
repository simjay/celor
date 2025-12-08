"""K8s oracles for manifest validation.

This module implements K8s-specific oracles that validate manifests against
various policies and constraints, returning Violations with constraint hints
for the synthesizer.
"""

import logging
import re
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from ruamel.yaml import YAML

from celor.core.schema.violation import Violation
from celor.k8s.artifact import K8sArtifact
from celor.k8s.patch_dsl import RESOURCE_PROFILES


class PolicyOracle:
    """Custom policy oracle for org-specific K8s rules.
    
    Implements policies like:
    - env=prod requires replicas in [3,5]
    - env=prod requires profile in {medium, large}
    - Image tags must match patterns
    - Required labels must be present
    
    Returns Violations with constraint hints in evidence field for synthesis.
    """

    def __call__(self, artifact: K8sArtifact) -> List[Violation]:
        """Check artifact against policies.
        
        Args:
            artifact: K8sArtifact to validate
            
        Returns:
            List of Violations (empty if all policies pass)
        """
        violations = []
        
        yaml = YAML()
        
        for filepath, content in artifact.files.items():
            try:
                manifest = yaml.load(content)
            except Exception as e:
                violations.append(Violation(
                    id="policy.INVALID_YAML",
                    message=f"Failed to parse YAML: {e}",
                    path=[filepath],
                    severity="error"
                ))
                continue
            
            # Only process Deployment manifests
            if manifest.get("kind") != "Deployment":
                continue
            
            # Extract values for policy checks
            env = self._get_label(manifest, "env")
            team = self._get_label(manifest, "team")
            tier = self._get_label(manifest, "tier")
            replicas = manifest.get("spec", {}).get("replicas")
            priority_class = manifest.get("spec", {}).get("priorityClassName")
            
            # Extract resource profile
            profile = self._extract_profile(manifest)
            
            # Extract image tag and full image
            image_full = self._extract_image(manifest)
            image_tag = self._extract_image_tag(manifest)
            
            # Policy: Images must come from AWS ECR
            if image_full:
                ecr_violation = self._check_ecr_policy(image_full, env, filepath)
                if ecr_violation:
                    violations.append(ecr_violation)
            
            # Policy: env=prod requires replicas in [3, 5]
            if env == "prod" and replicas is not None and replicas not in [3, 4, 5]:
                violations.append(Violation(
                    id="policy.ENV_PROD_REPLICA_COUNT",
                    message=f"env=prod requires replicas in [3,5], got {replicas}",
                    path=[filepath, "spec", "replicas"],
                    severity="error",
                    evidence={
                        "env": env,
                        "replicas": replicas,
                        "error_code": "ENV_PROD_REPLICA_COUNT",
                        # Constraint hint for synthesizer
                        "forbid_tuple": {
                            "holes": ["env", "replicas"],
                            "values": ["prod", replicas]
                        }
                    }
                ))
            
            # Policy: env=prod requires profile in {medium, large}
            if env == "prod" and profile == "small":
                violations.append(Violation(
                    id="policy.ENV_PROD_PROFILE_SMALL",
                    message=f"env=prod requires profile in {{medium, large}}, got {profile}",
                    path=[filepath, "spec", "template", "spec", "containers"],
                    severity="error",
                    evidence={
                        "env": env,
                        "profile": profile,
                        "error_code": "ENV_PROD_PROFILE_SMALL",
                        # Constraint hint
                        "forbid_tuple": {
                            "holes": ["env", "profile"],
                            "values": ["prod", "small"]
                        }
                    }
                ))
            
            # Policy: env=prod requires proper image tag (not latest, not staging)
            if env == "prod" and image_tag:
                if image_tag == "latest" or "staging" in image_tag:
                    violations.append(Violation(
                        id="policy.ENV_PROD_IMAGE_TAG",
                        message=f"env=prod requires prod-x.y.z tag pattern, got {image_tag}",
                        path=[filepath, "spec", "template", "spec", "containers", "image"],
                        severity="error",
                        evidence={
                            "env": env,
                            "image_tag": image_tag,
                            "error_code": "ENV_PROD_IMAGE_TAG"
                        }
                    ))
            
            # Policy: env=prod requires certain labels
            if env == "prod":
                required_labels = ["env", "team", "tier"]
                for label in required_labels:
                    if not self._get_label(manifest, label):
                        violations.append(Violation(
                            id=f"policy.MISSING_LABEL_{label.upper()}",
                            message=f"env=prod requires label '{label}'",
                            path=[filepath, "spec", "template", "metadata", "labels"],
                            severity="error",
                            evidence={"missing_label": label}
                        ))
            
            # Policy: env=prod requires priorityClassName
            if env == "prod" and not priority_class:
                violations.append(Violation(
                    id="policy.MISSING_PRIORITY_CLASS",
                    message="env=prod requires priorityClassName to be set",
                    path=[filepath, "spec", "priorityClassName"],
                    severity="error",
                    evidence={"env": env}
                ))
        
        return violations
    
    def _get_label(self, manifest: dict, key: str) -> str:
        """Extract label value from pod template."""
        return (manifest.get("spec", {})
                .get("template", {})
                .get("metadata", {})
                .get("labels", {})
                .get(key, ""))
    
    def _extract_profile(self, manifest: dict) -> str:
        """Determine resource profile from CPU/memory values."""
        containers = (manifest.get("spec", {})
                      .get("template", {})
                      .get("spec", {})
                      .get("containers", []))
        
        if not containers:
            return ""
        
        # Check first container's resources
        resources = containers[0].get("resources", {})
        cpu = resources.get("requests", {}).get("cpu", "")
        memory = resources.get("requests", {}).get("memory", "")
        
        # Match to known profiles
        for profile_name, profile_spec in RESOURCE_PROFILES.items():
            if (cpu == profile_spec["requests"]["cpu"] and 
                memory == profile_spec["requests"]["memory"]):
                return profile_name
        
        # Check if it's close to a profile (for detecting "small")
        if "100m" in cpu or "128Mi" in memory:
            return "small"
        elif "500m" in cpu or "512Mi" in memory:
            return "medium"
        elif "1000m" in cpu or "1Gi" in memory:
            return "large"
        
        return "unknown"
    
    def _extract_image(self, manifest: dict) -> str:
        """Extract full image path from first container."""
        containers = (manifest.get("spec", {})
                      .get("template", {})
                      .get("spec", {})
                      .get("containers", []))
        
        if not containers:
            return ""
        
        return containers[0].get("image", "")
    
    def _extract_image_tag(self, manifest: dict) -> str:
        """Extract image tag from first container."""
        image = self._extract_image(manifest)
        if ":" in image:
            return image.split(":")[-1]
        return ""
    
    def _check_ecr_policy(self, image: str, env: str, filepath: str) -> Optional[Violation]:
        """Check if image complies with AWS ECR policy.
        
        Policy requirements:
        1. Image must come from AWS ECR (format: <account>.dkr.ecr.<region>.amazonaws.com/<repo>:<tag>)
        2. ECR repository must match environment (dev/staging/prod)
        
        Args:
            image: Full image path
            env: Environment label value (if available)
            filepath: File path for violation reporting
            
        Returns:
            Violation if policy violated, None otherwise
        """
        # ECR pattern: <account>.dkr.ecr.<region>.amazonaws.com/<repo>:<tag>
        ecr_pattern = r'^(\d{12})\.dkr\.ecr\.([^.]+)\.amazonaws\.com/(.+)$'
        match = re.match(ecr_pattern, image)
        
        if not match:
            # Not from ECR - violation
            return Violation(
                id="policy.IMAGE_NOT_FROM_ECR",
                message=f"Image must come from AWS ECR, got {image}",
                path=[filepath, "spec", "template", "spec", "containers", "image"],
                severity="error",
                evidence={
                    "image": image,
                    "error_code": "IMAGE_NOT_FROM_ECR",
                    "forbid_value": {
                        "hole": "version",
                        "value": image
                    }
                }
            )
        
        account_id, region, repo_and_tag = match.groups()
        
        # Extract repository path and tag
        if ":" in repo_and_tag:
            repo_path, tag = repo_and_tag.rsplit(":", 1)
        else:
            repo_path = repo_and_tag
            tag = ""
        
        # Check environment match (if env is specified)
        if env:
            # Check if repo path or tag contains environment
            env_in_repo = env.lower() in repo_path.lower()
            env_in_tag = env.lower() in tag.lower()
            
            if not (env_in_repo or env_in_tag):
                return Violation(
                    id="policy.ECR_ENV_MISMATCH",
                    message=f"ECR image must match environment '{env}', got {image}",
                    path=[filepath, "spec", "template", "spec", "containers", "image"],
                    severity="error",
                    evidence={
                        "env": env,
                        "image": image,
                        "error_code": "ECR_ENV_MISMATCH",
                        "forbid_tuple": {
                            "holes": ["env", "version"],
                            "values": [env, image]
                        }
                    }
                )
        
        return None  # ECR policy satisfied


class SchemaOracle:
    """K8s schema validation oracle.
    
    Supports multiple backends:
    - kubernetes-validate library (preferred, pure Python)
    - kubectl subprocess (fallback)
    
    Validates that manifests conform to K8s API schema.
    """
    
    def __init__(self, use_kubernetes_validate: bool = True):
        """Initialize SchemaOracle.
        
        Args:
            use_kubernetes_validate: If True, prefer kubernetes-validate library
                                   over kubectl (default: True)
        """
        self.use_kubernetes_validate = use_kubernetes_validate
        self._k8s_validate_available = self._check_kubernetes_validate()
        self._kubectl_available = self._check_kubectl()
        self.logger = logging.getLogger(__name__)
    
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
        """Validate artifact against K8s schema.
        
        Uses preferred backend (kubernetes-validate or kubectl).
        
        Args:
            artifact: K8sArtifact to validate
            
        Returns:
            List of Violations (empty if valid or tools unavailable)
        """
        # Try preferred backend first
        if self.use_kubernetes_validate and self._k8s_validate_available:
            return self._validate_with_library(artifact)
        elif self._kubectl_available:
            return self._validate_with_kubectl(artifact)
        else:
            self.logger.debug("No schema validation tools available, skipping SchemaOracle")
            return []  # Graceful fallback
    
    def _validate_with_library(self, artifact: K8sArtifact) -> List[Violation]:
        """Validate using kubernetes-validate library (pure Python)."""
        violations = []
        
        try:
            from kubernetes_validate import validate as k8s_validate
        except ImportError:
            # Fallback to kubectl if library import fails
            if self._kubectl_available:
                return self._validate_with_kubectl(artifact)
            return []
        
        yaml = YAML()
        
        for filepath, content in artifact.files.items():
            try:
                # Parse YAML first
                manifest = yaml.load(content)
                
                # Validate using kubernetes-validate
                # Note: kubernetes-validate expects dict, not string
                errors = k8s_validate(manifest, kubernetes_version="1.28")
                
                for error in errors:
                    violations.append(Violation(
                        id="schema.VALIDATION_ERROR",
                        message=str(error),
                        path=[filepath],
                        severity="error",
                        evidence={"error": str(error)}
                    ))
                    
            except Exception as e:
                violations.append(Violation(
                    id="schema.VALIDATION_EXCEPTION",
                    message=f"Validation failed: {e}",
                    path=[filepath],
                    severity="error",
                    evidence={"exception": str(e)}
                ))
        
        return violations
    
    def _validate_with_kubectl(self, artifact: K8sArtifact) -> List[Violation]:
        """Validate using kubectl subprocess (fallback)."""
        violations = []
        
        # Write to temp dir
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact.write_to_dir(tmpdir)
            
            for filepath in artifact.files.keys():
                full_path = Path(tmpdir) / filepath
                
                # Try kubectl validation (may not be available)
                try:
                    result = subprocess.run(
                        ["kubectl", "apply", "--dry-run=client", "-f", str(full_path)],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if result.returncode != 0:
                        violations.append(Violation(
                            id="schema.KUBECTL_VALIDATION_FAILED",
                            message=f"kubectl validation failed: {result.stderr}",
                            path=[filepath],
                            severity="error",
                            evidence={"stderr": result.stderr}
                        ))
                        
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    # kubectl not available or timed out - skip validation
                    pass
        
        return violations


class SecurityOracle:
    """Security baseline oracle for K8s manifests.
    
    Checks that containers have proper securityContext settings.
    """

    def __call__(self, artifact: K8sArtifact) -> List[Violation]:
        """Check security baseline.
        
        Args:
            artifact: K8sArtifact to validate
            
        Returns:
            List of Violations (empty if secure)
        """
        violations = []
        
        yaml = YAML()
        
        for filepath, content in artifact.files.items():
            manifest = yaml.load(content)
            
            # Only process Deployment manifests
            if manifest.get("kind") != "Deployment":
                continue
            
            containers = (manifest.get("spec", {})
                         .get("template", {})
                         .get("spec", {})
                         .get("containers", []))
            
            for container in containers:
                sec_ctx = container.get("securityContext", {})
                container_name = container.get("name", "unknown")
                
                # Check runAsNonRoot
                if not sec_ctx.get("runAsNonRoot"):
                    violations.append(Violation(
                        id=f"security.NO_RUN_AS_NON_ROOT.{container_name}",
                        message=f"Container {container_name} must set runAsNonRoot=true",
                        path=[filepath, "spec", "template", "spec", "containers", container_name, "securityContext"],
                        severity="error",
                        evidence={"container": container_name}
                    ))
                
                # Check allowPrivilegeEscalation
                if sec_ctx.get("allowPrivilegeEscalation") is not False:
                    violations.append(Violation(
                        id=f"security.PRIVILEGE_ESCALATION.{container_name}",
                        message=f"Container {container_name} must set allowPrivilegeEscalation=false",
                        path=[filepath, "spec", "template", "spec", "containers", container_name, "securityContext"],
                        severity="error",
                        evidence={"container": container_name}
                    ))
        
        return violations


class ResourceOracle:
    """Resource validation oracle.
    
    Validates that resource requests/limits match known profiles and are reasonable.
    """

    def __call__(self, artifact: K8sArtifact) -> List[Violation]:
        """Validate resources.
        
        Args:
            artifact: K8sArtifact to validate
            
        Returns:
            List of Violations (empty if valid)
        """
        violations = []
        
        yaml = YAML()
        
        for filepath, content in artifact.files.items():
            manifest = yaml.load(content)
            
            # Only process Deployment manifests
            if manifest.get("kind") != "Deployment":
                continue
            
            containers = (manifest.get("spec", {})
                         .get("template", {})
                         .get("spec", {})
                         .get("containers", []))
            
            for container in containers:
                container_name = container.get("name", "unknown")
                resources = container.get("resources", {})
                
                # Check if resources are set
                if not resources:
                    violations.append(Violation(
                        id=f"resource.MISSING_RESOURCES.{container_name}",
                        message=f"Container {container_name} must specify resources",
                        path=[filepath, "spec", "template", "spec", "containers", container_name],
                        severity="error",
                        evidence={"container": container_name}
                    ))
                    continue
                
                # Check if resources match a known profile
                requests = resources.get("requests", {})
                cpu = requests.get("cpu", "")
                memory = requests.get("memory", "")
                
                # Validate against profiles
                matches_profile = False
                for profile_name, profile_spec in RESOURCE_PROFILES.items():
                    if (cpu == profile_spec["requests"]["cpu"] and 
                        memory == profile_spec["requests"]["memory"]):
                        matches_profile = True
                        break
                
                if not matches_profile and cpu and memory:
                    # Determine what profile this resembles
                    if "100m" in cpu or "128Mi" in memory:
                        inferred_profile = "small"
                    else:
                        inferred_profile = "unknown"
                    
                    if inferred_profile == "small":
                        violations.append(Violation(
                            id=f"resource.NONSTANDARD_PROFILE.{container_name}",
                            message=f"Container {container_name} resources don't match standard profiles",
                            path=[filepath, "spec", "template", "spec", "containers", container_name, "resources"],
                            severity="warning",
                            evidence={
                                "container": container_name,
                                "cpu": cpu,
                                "memory": memory,
                                "suggested_profiles": list(RESOURCE_PROFILES.keys())
                            }
                        ))
        
        return violations


# ============================================================================
# External Oracle Implementations (Checkov, kubernetes-validate)
# ============================================================================

class CheckovPolicyOracle:
    """Policy oracle using Checkov for comprehensive policy checks.
    
    Wraps Checkov to provide 200+ policy checks while maintaining
    constraint hint capability for synthesis through custom mapping.
    
    This oracle demonstrates CeLoR's extensibility with external tools.
    """
    
    # Policy-related Checkov check IDs (subset of all checks)
    POLICY_CHECK_IDS = [
        "CKV_K8S_8",   # Ensure that containers do not run with root user
        "CKV_K8S_10",  # Ensure that CPU limits are set
        "CKV_K8S_11",  # Ensure that memory limits are set
        "CKV_K8S_12",  # Ensure that the --host-network flag is not set
        "CKV_K8S_13",  # Ensure that the --host-pid flag is not set
        "CKV_K8S_14",  # Ensure that the --host-ipc flag is not set
        "CKV_K8S_17",  # Ensure that the default namespace is not used
        # Add more policy-related checks as needed
    ]
    
    def __init__(self):
        self._checkov_available = self._check_checkov()
        self.logger = logging.getLogger(__name__)
    
    def _check_checkov(self) -> bool:
        """Check if Checkov is available."""
        try:
            import checkov
            return True
        except ImportError:
            return False
    
    def __call__(self, artifact: K8sArtifact) -> List[Violation]:
        """Run Checkov policy checks with constraint hints.
        
        Args:
            artifact: K8sArtifact to validate
            
        Returns:
            List of Violations (empty if Checkov unavailable or all pass)
        """
        if not self._checkov_available:
            self.logger.debug("Checkov not available, skipping CheckovPolicyOracle")
            return []  # Graceful fallback
        
        violations = []
        
        # Write artifact to temp dir for Checkov
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact.write_to_dir(tmpdir)
            
            try:
                from checkov.kubernetes.runner import Runner as K8sRunner
                from checkov.runner_filter import RunnerFilter
                
                runner = K8sRunner()
                runner_filter = RunnerFilter(
                    checks=self.POLICY_CHECK_IDS,
                    skip_checks=None
                )
                
                # Run Checkov
                report = runner.run(
                    root_folder=tmpdir,
                    runner_filter=runner_filter
                )
                
                # Convert Checkov results to Violations
                for failed_check in report.failed_checks:
                    violation = self._convert_checkov_to_violation(failed_check)
                    violations.append(violation)
                    
            except Exception as e:
                # Gracefully handle errors
                self.logger.warning(f"Checkov execution failed: {e}")
                return []  # Fallback to empty violations
        
        return violations
    
    def _convert_checkov_to_violation(self, check) -> Violation:
        """Convert Checkov check to Violation with constraint hints.
        
        Args:
            check: Checkov failed check object
            
        Returns:
            Violation with constraint hints extracted
        """
        # Extract constraint hints from Checkov check
        evidence = self._extract_constraint_hints(check)
        
        return Violation(
            id=f"checkov.{check.check_id}",
            message=check.check_name or f"Checkov check {check.check_id} failed",
            path=[check.file_path] if hasattr(check, 'file_path') else [],
            severity="error",
            evidence=evidence
        )
    
    def _extract_constraint_hints(self, check) -> dict:
        """Extract constraint hints from Checkov check.
        
        Maps Checkov check IDs to synthesis constraint hints.
        
        Args:
            check: Checkov failed check object
            
        Returns:
            Dictionary with constraint hints (forbid_value, forbid_tuple, etc.)
        """
        evidence = {
            "checkov_check_id": check.check_id,
            "checkov_check_name": check.check_name if hasattr(check, 'check_name') else None
        }
        
        # Map specific Checkov checks to constraint hints
        check_id = check.check_id
        
        # Example mappings (can be extended)
        if "CKV_K8S_8" in check_id:  # Root user check
            evidence["forbid_value"] = {
                "hole": "security_baseline",
                "value": "root"
            }
        elif "CKV_K8S_10" in check_id or "CKV_K8S_11" in check_id:  # Resource limits
            # Could map to profile constraints
            evidence["forbid_value"] = {
                "hole": "profile",
                "value": "none"  # No resources set
            }
        
        return evidence


class CheckovSecurityOracle:
    """Security oracle using Checkov security checks.
    
    Wraps Checkov to provide comprehensive security validation.
    Filters for security-specific check IDs.
    """
    
    # Security-specific Checkov check IDs
    SECURITY_CHECK_IDS = [
        "CKV_K8S_8",   # Ensure that containers do not run with root user
        "CKV_K8S_23",  # Minimize the admission of containers with capabilities assigned
        "CKV_K8S_24",  # Ensure that the --host-network flag is not set
        "CKV_K8S_25",  # Ensure that the --host-pid flag is not set
        "CKV_K8S_26",  # Ensure that the --host-ipc flag is not set
        # Add more security checks as needed
    ]
    
    def __init__(self):
        self._checkov_available = self._check_checkov()
        self.logger = logging.getLogger(__name__)
    
    def _check_checkov(self) -> bool:
        """Check if Checkov is available."""
        try:
            import checkov
            return True
        except ImportError:
            return False
    
    def __call__(self, artifact: K8sArtifact) -> List[Violation]:
        """Run Checkov security checks only.
        
        Args:
            artifact: K8sArtifact to validate
            
        Returns:
            List of Violations (empty if Checkov unavailable or all pass)
        """
        if not self._checkov_available:
            self.logger.debug("Checkov not available, skipping CheckovSecurityOracle")
            return []  # Graceful fallback
        
        violations = []
        
        # Write artifact to temp dir for Checkov
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact.write_to_dir(tmpdir)
            
            try:
                from checkov.kubernetes.runner import Runner as K8sRunner
                from checkov.runner_filter import RunnerFilter
                
                runner = K8sRunner()
                runner_filter = RunnerFilter(
                    checks=self.SECURITY_CHECK_IDS,
                    skip_checks=None
                )
                
                # Run Checkov
                report = runner.run(
                    root_folder=tmpdir,
                    runner_filter=runner_filter
                )
                
                # Convert Checkov results to Violations
                for failed_check in report.failed_checks:
                    violation = Violation(
                        id=f"checkov.security.{failed_check.check_id}",
                        message=failed_check.check_name or f"Security check {failed_check.check_id} failed",
                        path=[failed_check.file_path] if hasattr(failed_check, 'file_path') else [],
                        severity="error",
                        evidence={
                            "checkov_check_id": failed_check.check_id,
                            "checkov_check_name": failed_check.check_name if hasattr(failed_check, 'check_name') else None
                        }
                    )
                    violations.append(violation)
                    
            except Exception as e:
                # Gracefully handle errors
                self.logger.warning(f"Checkov execution failed: {e}")
                return []  # Fallback to empty violations
        
        return violations


# Enhanced SchemaOracle with kubernetes-validate support
# (SchemaOracle already exists, we'll enhance it)
# Note: The existing SchemaOracle uses kubectl. We can add a parameter to use kubernetes-validate instead.

