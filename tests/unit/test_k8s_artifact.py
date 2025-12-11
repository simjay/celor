"""Tests for K8sArtifact."""

import tempfile
from pathlib import Path

import pytest

from celor.core.schema.patch_dsl import Patch, PatchOp
from celor.k8s.artifact import K8sArtifact


SAMPLE_DEPLOYMENT = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: payments-api
  labels:
    app: payments-api
    env: prod
spec:
  replicas: 3
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
        image: payments-api:prod-1.2.3
        resources:
          requests:
            cpu: "500m"
            memory: "512Mi"
"""


class TestK8sArtifactCreation:
    """Tests for creating K8sArtifact."""

    def test_create_from_dict(self):
        """Test creating K8sArtifact from files dict."""
        artifact = K8sArtifact(files={"deployment.yaml": SAMPLE_DEPLOYMENT})
        
        assert len(artifact.files) == 1
        assert "deployment.yaml" in artifact.files
        assert "apiVersion: apps/v1" in artifact.files["deployment.yaml"]

    def test_create_multiple_files(self):
        """Test artifact with multiple YAML files."""
        artifact = K8sArtifact(files={
            "deployment.yaml": SAMPLE_DEPLOYMENT,
            "service.yaml": "apiVersion: v1\nkind: Service"
        })
        
        assert len(artifact.files) == 2

    def test_immutability(self):
        """Test that K8sArtifact is immutable (frozen)."""
        artifact = K8sArtifact(files={"deployment.yaml": SAMPLE_DEPLOYMENT})
        
        with pytest.raises(AttributeError):
            artifact.files = {}  # type: ignore


class TestArtifactProtocol:
    """Tests for Artifact protocol implementation."""

    def test_to_serializable(self):
        """Test to_serializable() method."""
        artifact = K8sArtifact(files={"deployment.yaml": SAMPLE_DEPLOYMENT})
        
        result = artifact.to_serializable()
        
        assert isinstance(result, dict)
        assert "files" in result
        assert result["files"] == artifact.files


class TestWriteToDir:
    """Tests for write_to_dir() method."""

    def test_write_single_file(self):
        """Test writing single YAML file to directory."""
        artifact = K8sArtifact(files={"deployment.yaml": SAMPLE_DEPLOYMENT})
        
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact.write_to_dir(tmpdir)
            
            written_file = Path(tmpdir) / "deployment.yaml"
            assert written_file.exists()
            assert written_file.read_text() == SAMPLE_DEPLOYMENT

    def test_write_multiple_files(self):
        """Test writing multiple YAML files."""
        artifact = K8sArtifact(files={
            "deployment.yaml": SAMPLE_DEPLOYMENT,
            "service.yaml": "apiVersion: v1\nkind: Service"
        })
        
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact.write_to_dir(tmpdir)
            
            assert (Path(tmpdir) / "deployment.yaml").exists()
            assert (Path(tmpdir) / "service.yaml").exists()

    def test_write_creates_subdirectories(self):
        """Test that write_to_dir creates subdirectories if needed."""
        artifact = K8sArtifact(files={
            "base/deployment.yaml": SAMPLE_DEPLOYMENT,
            "overlays/prod/kustomization.yaml": "resources:\n- ../../base"
        })
        
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact.write_to_dir(tmpdir)
            
            assert (Path(tmpdir) / "base" / "deployment.yaml").exists()
            assert (Path(tmpdir) / "overlays" / "prod" / "kustomization.yaml").exists()

    def test_write_creates_directory_if_not_exists(self):
        """Test that write_to_dir creates target directory."""
        artifact = K8sArtifact(files={"deployment.yaml": SAMPLE_DEPLOYMENT})
        
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "nested" / "path"
            artifact.write_to_dir(str(target))
            
            assert target.exists()
            assert (target / "deployment.yaml").exists()


class TestApplyPatch:
    """Tests for apply_patch() method."""

    def test_apply_patch_stub(self):
        """Test apply_patch() stub (full implementation in Phase 2)."""
        artifact = K8sArtifact(files={"deployment.yaml": SAMPLE_DEPLOYMENT})
        patch = Patch(ops=[
            PatchOp("EnsureLabel", {"key": "env", "value": "staging"})
        ])
        
        # Currently returns self unchanged (stub)
        result = artifact.apply_patch(patch)
        
        assert isinstance(result, K8sArtifact)


class TestFromFile:
    """Tests for from_file() class method."""

    def test_from_file(self):
        """Test loading artifact from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "deployment.yaml"
            file_path.write_text(SAMPLE_DEPLOYMENT)
            
            artifact = K8sArtifact.from_file(str(file_path))
            
            assert len(artifact.files) == 1
            assert "deployment.yaml" in artifact.files
            assert artifact.files["deployment.yaml"] == SAMPLE_DEPLOYMENT


class TestFromDir:
    """Tests for from_dir() class method."""

    def test_from_dir_single_file(self):
        """Test loading artifact from directory with single YAML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "deployment.yaml").write_text(SAMPLE_DEPLOYMENT)
            
            artifact = K8sArtifact.from_dir(tmpdir)
            
            assert len(artifact.files) == 1
            assert "deployment.yaml" in artifact.files

    def test_from_dir_multiple_files(self):
        """Test loading multiple YAML files from directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "deployment.yaml").write_text(SAMPLE_DEPLOYMENT)
            (Path(tmpdir) / "service.yaml").write_text("apiVersion: v1\nkind: Service")
            (Path(tmpdir) / "configmap.yaml").write_text("apiVersion: v1\nkind: ConfigMap")
            
            artifact = K8sArtifact.from_dir(tmpdir)
            
            assert len(artifact.files) == 3
            assert "deployment.yaml" in artifact.files
            assert "service.yaml" in artifact.files
            assert "configmap.yaml" in artifact.files

    def test_from_dir_ignores_non_yaml(self):
        """Test that from_dir only loads YAML files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "deployment.yaml").write_text(SAMPLE_DEPLOYMENT)
            (Path(tmpdir) / "README.md").write_text("# Docs")
            (Path(tmpdir) / "script.sh").write_text("#!/bin/bash")
            
            artifact = K8sArtifact.from_dir(tmpdir)
            
            assert len(artifact.files) == 1
            assert "deployment.yaml" in artifact.files

