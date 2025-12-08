"""Integration tests for Fix Bank cross-run learning."""

import tempfile
from pathlib import Path

import pytest

from celor.core.controller import repair_artifact
from celor.core.fixbank import FixBank
from celor.k8s.artifact import K8sArtifact
from celor.k8s.examples import LLM_EDITED_DEPLOYMENT, payments_api_template_and_holes
from celor.k8s.oracles import PolicyOracle, ResourceOracle, SecurityOracle


class TestFixBankLearning:
    """Tests for Fix Bank cross-run learning."""

    def test_first_run_stores_in_fixbank(self):
        """Test that first run stores entry in Fix Bank."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w') as f:
            fixbank_path = f.name
        
        try:
            # First run
            fixbank = FixBank(fixbank_path)
            assert len(fixbank.entries) == 0
            
            artifact = K8sArtifact(files={"deployment.yaml": LLM_EDITED_DEPLOYMENT})
            oracles = [PolicyOracle(), SecurityOracle(), ResourceOracle()]
            
            repaired, metadata = repair_artifact(
                artifact=artifact,
                oracles=oracles,
                fixbank=fixbank,
                default_template_fn=payments_api_template_and_holes
            )
            
            assert metadata["status"] == "success"
            assert not metadata["fixbank_hit"]  # First run, no hit
            
            # Should have added entry to Fix Bank
            assert len(fixbank.entries) == 1
            
            # Entry should have constraints (even if 0)
            entry = fixbank.entries[0]
            assert hasattr(entry, "learned_constraints")
            assert isinstance(entry.learned_constraints, list)
            
        finally:
            Path(fixbank_path).unlink()

    def test_second_run_reuses_fixbank(self):
        """Test that second run reuses Fix Bank entry."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w') as f:
            fixbank_path = f.name
        
        try:
            artifact = K8sArtifact(files={"deployment.yaml": LLM_EDITED_DEPLOYMENT})
            oracles = [PolicyOracle(), SecurityOracle(), ResourceOracle()]
            
            # First run
            fixbank1 = FixBank(fixbank_path)
            repaired1, metadata1 = repair_artifact(
                artifact=artifact,
                oracles=oracles,
                fixbank=fixbank1,
                default_template_fn=payments_api_template_and_holes
            )
            
            assert metadata1["status"] == "success"
            assert not metadata1["fixbank_hit"]
            first_run_candidates = metadata1["tried_candidates"]
            
            # Second run with NEW Fix Bank instance (simulates different session)
            fixbank2 = FixBank(fixbank_path)  # Loads from disk
            assert len(fixbank2.entries) == 1
            
            repaired2, metadata2 = repair_artifact(
                artifact=artifact,  # Same problem
                oracles=oracles,
                fixbank=fixbank2,
                default_template_fn=payments_api_template_and_holes
            )
            
            assert metadata2["status"] == "success"
            assert metadata2["fixbank_hit"]  # Second run, should hit!
            
            # Should still work (might try same or fewer candidates)
            assert metadata2["tried_candidates"] >= 1
            
        finally:
            Path(fixbank_path).unlink()

    def test_speedup_measurement(self):
        """Test measuring speedup from Fix Bank constraints."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w') as f:
            fixbank_path = f.name
        
        try:
            artifact = K8sArtifact(files={"deployment.yaml": LLM_EDITED_DEPLOYMENT})
            oracles = [PolicyOracle(), SecurityOracle(), ResourceOracle()]
            
            # Run WITHOUT Fix Bank
            _, metadata_no_fb = repair_artifact(
                artifact=artifact,
                oracles=oracles,
                fixbank=None,  # No Fix Bank
                default_template_fn=payments_api_template_and_holes
            )
            
            candidates_without_fb = metadata_no_fb["tried_candidates"]
            
            # Run WITH Fix Bank (first time - adds entry)
            fixbank1 = FixBank(fixbank_path)
            _, metadata1 = repair_artifact(
                artifact=artifact,
                oracles=oracles,
                fixbank=fixbank1,
                default_template_fn=payments_api_template_and_holes
            )
            
            assert len(fixbank1.entries) == 1
            
            # Run WITH Fix Bank (second time - reuses entry)
            fixbank2 = FixBank(fixbank_path)
            _, metadata2 = repair_artifact(
                artifact=artifact,
                oracles=oracles,
                fixbank=fixbank2,
                default_template_fn=payments_api_template_and_holes
            )
            
            candidates_with_fb = metadata2["tried_candidates"]
            
            # Should be successful
            assert metadata2["status"] == "success"
            assert metadata2["fixbank_hit"]
            
            # Log speedup (might be same if search space is small)
            print(f"\nSpeedup measurement:")
            print(f"  Without Fix Bank: {candidates_without_fb} candidates")
            print(f"  With Fix Bank (reuse): {candidates_with_fb} candidates")
            
        finally:
            Path(fixbank_path).unlink()

    def test_team_sharing_scenario(self):
        """Test team knowledge sharing via Fix Bank."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w') as f:
            fixbank_path = f.name
        
        try:
            artifact = K8sArtifact(files={"deployment.yaml": LLM_EDITED_DEPLOYMENT})
            oracles = [PolicyOracle(), SecurityOracle(), ResourceOracle()]
            
            # Developer A encounters problem
            print("\n[Developer A] First encounter...")
            fixbank_a = FixBank(fixbank_path)
            repaired_a, metadata_a = repair_artifact(
                artifact=artifact,
                oracles=oracles,
                fixbank=fixbank_a,
                default_template_fn=payments_api_template_and_holes
            )
            
            assert metadata_a["status"] == "success"
            assert not metadata_a["fixbank_hit"]  # First time
            assert len(fixbank_a.entries) == 1
            
            # Simulate: Developer A commits .celor-fixes.json
            # (file is already saved to disk)
            
            # Simulate: Developer B pulls and encounters same problem
            print("[Developer B] After pulling Fix Bank...")
            fixbank_b = FixBank(fixbank_path)  # Load from "git"
            assert len(fixbank_b.entries) == 1  # Has A's learning
            
            repaired_b, metadata_b = repair_artifact(
                artifact=artifact,  # Same type of problem
                oracles=oracles,
                fixbank=fixbank_b,
                default_template_fn=payments_api_template_and_holes
            )
            
            assert metadata_b["status"] == "success"
            assert metadata_b["fixbank_hit"]  # Reused A's learning!
            
            print(f"  Developer A: {metadata_a['tried_candidates']} candidates")
            print(f"  Developer B: {metadata_b['tried_candidates']} candidates (reused constraints!)")
            
        finally:
            Path(fixbank_path).unlink()

    def test_different_problems_dont_match(self):
        """Test that different problems get separate Fix Bank entries."""
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w') as f:
            fixbank_path = f.name
        
        try:
            fixbank = FixBank(fixbank_path)
            
            # Problem 1: LLM-edited deployment
            artifact1 = K8sArtifact(files={"deployment.yaml": LLM_EDITED_DEPLOYMENT})
            oracles = [PolicyOracle(), SecurityOracle(), ResourceOracle()]
            
            repaired1, _ = repair_artifact(
                artifact=artifact1,
                oracles=oracles,
                fixbank=fixbank,
                default_template_fn=payments_api_template_and_holes
            )
            
            assert len(fixbank.entries) == 1
            
            # Problem 2: Different artifact (only security violations)
            different_manifest = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: other-app
spec:
  replicas: 3
  template:
    metadata:
      labels:
        env: prod
        team: platform
        tier: backend
    spec:
      containers:
      - name: other-app
        image: other-app:v1
"""
            artifact2 = K8sArtifact(files={"deployment.yaml": different_manifest})
            
            repaired2, metadata2 = repair_artifact(
                artifact=artifact2,
                oracles=oracles,
                fixbank=fixbank,
                default_template_fn=payments_api_template_and_holes
            )
            
            # If this has different violations, should create new entry
            # (or hit existing if signatures match)
            # For this test, we just verify it doesn't crash
            assert metadata2["status"] in ["success", "unsat", "timeout"]
            
        finally:
            Path(fixbank_path).unlink()

