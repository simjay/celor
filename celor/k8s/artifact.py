"""K8s artifact implementation for YAML manifests.

This module provides the K8sArtifact class that represents Kubernetes YAML
manifests as CeLoR artifacts. It implements the Artifact protocol for K8s domain.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from celor.core.schema.patch_dsl import Patch


@dataclass(frozen=True)
class K8sArtifact:
    """Kubernetes manifest artifact.
    
    Represents one or more K8s YAML files (typically a Deployment manifest).
    Implements the Artifact protocol for domain-agnostic repair operations.
    
    Attributes:
        files: Mapping from file path to YAML content as string.
               Example: ``{"deployment.yaml": "apiVersion: apps/v1\\n..."}``
    
    Example:
        >>> yaml_content = '''
        ... apiVersion: apps/v1
        ... kind: Deployment
        ... metadata:
        ...   name: payments-api
        ... spec:
        ...   replicas: 3
        ... '''
        >>> artifact = K8sArtifact(files={"deployment.yaml": yaml_content})
        >>> artifact.files["deployment.yaml"]
        'apiVersion: apps/v1...'
    """
    files: Dict[str, str]

    def to_serializable(self) -> Dict:
        """Convert artifact to JSON-serializable format.
        
        Implements Artifact protocol. Returns dict representation suitable
        for JSON serialization, logging, or storage.
        
        Returns:
            Dict with 'files' key containing file path -> content mapping
        """
        return {"files": self.files}

    def apply_patch(self, patch: Patch) -> "K8sArtifact":
        """Apply patch operations to create new artifact.
        
        Applies K8s-specific patch operations (EnsureLabel, EnsureReplicas, etc.)
        to the YAML manifests, producing a new K8sArtifact with modified content.
        
        Args:
            patch: Patch containing K8s-specific operations
            
        Returns:
            New K8sArtifact with patch applied (original unchanged)
        """
        from celor.k8s.patch_dsl import apply_k8s_patch
        
        patched_files = apply_k8s_patch(self.files, patch)
        return K8sArtifact(files=patched_files)

    def write_to_dir(self, dir_path: str, output_filename: Optional[str] = None) -> None:
        """Write YAML files to directory for oracle evaluation.
        
        Creates the directory if it doesn't exist and writes all manifest
        files to disk. Used by oracles that expect files (kubectl, kube-linter).
        
        Args:
            dir_path: Directory path where files should be written
            output_filename: Optional filename to use for output. If provided,
                            renames the first file to this name. If None, preserves
                            original filenames (default: None)
            
        Example:
            >>> artifact = K8sArtifact(files={"deployment.yaml": "..."})
            >>> artifact.write_to_dir("/tmp/manifests")
            # Creates /tmp/manifests/deployment.yaml
            
            >>> artifact.write_to_dir("/tmp/manifests", output_filename="fixed.yaml")
            # Creates /tmp/manifests/fixed.yaml
        """
        dir_path_obj = Path(dir_path)
        dir_path_obj.mkdir(parents=True, exist_ok=True)
        
        files_list = list(self.files.items())
        
        for i, (rel_path, content) in enumerate(files_list):
            # Use output_filename for first file if provided, otherwise use original name
            if i == 0 and output_filename is not None:
                file_path = dir_path_obj / output_filename
            else:
                file_path = dir_path_obj / rel_path
            
            # Create parent directories if path has subdirectories
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

    @classmethod
    def from_file(cls, file_path: str) -> "K8sArtifact":
        """Load K8sArtifact from a YAML file.
        
        Convenience constructor for loading a single manifest file.
        
        Args:
            file_path: Path to YAML file
            
        Returns:
            K8sArtifact with the file content
            
        Example:
            >>> artifact = K8sArtifact.from_file("deployment.yaml")
        """
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")
        filename = path.name
        return cls(files={filename: content})

    @classmethod
    def from_dir(cls, dir_path: str, pattern: str = "*.yaml") -> "K8sArtifact":
        """Load K8sArtifact from directory with YAML files.
        
        Args:
            dir_path: Directory containing YAML files
            pattern: Glob pattern for files to include (default: ``*.yaml``)
            
        Returns:
            K8sArtifact with all matching files
            
        Example:
            >>> artifact = K8sArtifact.from_dir("manifests/")
        """
        dir_path_obj = Path(dir_path)
        files = {}
        
        for file_path in dir_path_obj.glob(pattern):
            if file_path.is_file():
                rel_path = file_path.relative_to(dir_path_obj)
                content = file_path.read_text(encoding="utf-8")
                files[str(rel_path)] = content
        
        return cls(files=files)

