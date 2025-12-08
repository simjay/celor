Repair Workflow
===============

This tutorial walks through a complete K8s manifest repair workflow from start to finish. You'll learn how to use CeLoR to repair a non-compliant Kubernetes deployment manifest.

Prerequisites
-------------

* CeLoR installed (see :doc:`../getting_started`)
* Python 3.11+
* Optional: OpenAI API key in ``config.json`` for LLM integration

Step 1: Create a Non-Compliant Manifest
----------------------------------------

Create a file ``deployment.yaml`` with policy violations:

.. code-block:: yaml

   # deployment.yaml
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: payments-api
     labels:
       app: payments-api
   spec:
     replicas: 2  # Violation: prod requires 3-5 replicas
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
           image: docker.io/library/payments-api:latest  # Violation: not from ECR, and :latest not allowed in prod
           resources:
             requests:
               cpu: "100m"
               memory: "128Mi"  # Violation: prod requires medium/large profile

This manifest has several violations:
  - **ECR policy violation**: Image from ``docker.io`` (must be AWS ECR)
  - Replicas too low for production (needs 3-5)
  - Missing required labels (team, tier)
  - Image tag is ``:latest`` (not allowed in prod)
  - Resource profile too small (needs medium/large)
  - Missing security context
  - Missing priorityClassName

Step 2: Run Oracles to Detect Violations
----------------------------------------

Verify violations exist:

.. code-block:: python

   from celor.k8s.artifact import K8sArtifact
   from celor.k8s.oracles import (
       PolicyOracle, SecurityOracle, ResourceOracle,
       CheckovPolicyOracle, CheckovSecurityOracle, SchemaOracle
   )
   
   artifact = K8sArtifact.from_file("deployment.yaml")
   
   # Hybrid approach: Custom oracles (with constraint hints) + External oracles (comprehensive)
   custom_oracles = [PolicyOracle(), SecurityOracle(), ResourceOracle()]
   external_oracles = [
       SchemaOracle(use_kubernetes_validate=True),  # Schema validation
       CheckovPolicyOracle(),  # 200+ policy checks
       CheckovSecurityOracle()  # Security checks
   ]
   oracles = custom_oracles + external_oracles
   
   violations = []
   for oracle in oracles:
       oracle_violations = oracle(artifact)
       violations.extend(oracle_violations)
       oracle_type = "Custom" if oracle in custom_oracles else "External"
       print(f"{oracle.__class__.__name__} ({oracle_type}): {len(oracle_violations)} violations")
   
   print(f"\nTotal violations: {len(violations)}")
   print(f"  - Custom oracles: {sum(len(o(a)) for o, a in [(o, artifact) for o in custom_oracles])} violations")
   print(f"  - External oracles: {sum(len(o(a)) for o, a in [(o, artifact) for o in external_oracles])} violations")

You should see multiple violations from both custom and external oracles. The ECR policy violation will be detected by PolicyOracle.

Step 3: Repair with CeLoR
--------------------------

Using CLI
~~~~~~~~~

The simplest way to repair:

.. code-block:: bash

   celor repair deployment.yaml --out fixed/

This will:
  1. Detect violations using K8s oracles
  2. Generate a repair template (from Fix Bank, LLM, or default)
  3. Synthesize concrete values using CEGIS
  4. Write repaired manifest to ``fixed/deployment.yaml``

Using Python API
~~~~~~~~~~~~~~~~

Create a repair script ``repair.py``:

.. code-block:: python

   # repair.py
   from celor.k8s.artifact import K8sArtifact
   from celor.k8s.oracles import PolicyOracle, SecurityOracle, ResourceOracle
   from celor.core.controller import repair_artifact
   
   # 1. Load manifest
   artifact = K8sArtifact.from_file("deployment.yaml")
   
   # 2. Create oracles (hybrid approach)
   custom_oracles = [
       PolicyOracle(),      # Policy checks (including ECR validation)
       SecurityOracle(),    # Security baseline
       ResourceOracle()     # Resource validation
   ]
   external_oracles = [
       SchemaOracle(use_kubernetes_validate=True),  # Schema validation
       CheckovPolicyOracle(),  # Comprehensive policy checks
       CheckovSecurityOracle()  # Security checks
   ]
   oracles = custom_oracles + external_oracles
   
   # 3. Run repair
   print("Starting repair...")
   repaired, metadata = repair_artifact(
       artifact=artifact,
       oracles=oracles
   )
   
   # 4. Display results
   print(f"\nStatus: {metadata['status']}")
   print(f"Iterations: {metadata['iterations']}")
   print(f"Candidates tried: {metadata['tried_candidates']}")
   print(f"Constraints learned: {len(metadata['constraints'])}")
   
   if metadata['status'] == 'success':
       print("\nRepair successful!")
       repaired.write_to_dir("fixed")
   else:
       print(f"\nRepair incomplete: {metadata.get('remaining_violations', 0)} violations remain")

Run the repair:

.. code-block:: bash

   python repair.py

Step 4: Verify the Fix
----------------------

Check the repaired manifest in ``fixed/deployment.yaml``:

.. code-block:: yaml

   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: payments-api
     labels:
       app: payments-api
   spec:
     replicas: 3  # Fixed: now in valid range
     priorityClassName: critical  # Added
     selector:
       matchLabels:
         app: payments-api
     template:
       metadata:
         labels:
           app: payments-api
           env: prod
           team: payments      # Added
           tier: backend        # Added
       spec:
         containers:
         - name: payments-api
           image: 123456789012.dkr.ecr.us-east-1.amazonaws.com/prod/payments-api:prod-1.2.3  # Fixed: ECR-compliant image
           securityContext:                  # Added
             runAsNonRoot: true
             allowPrivilegeEscalation: false
           resources:                        # Fixed: medium profile
             requests:
               cpu: "500m"
               memory: "512Mi"
             limits:
               cpu: "1000m"
               memory: "1Gi"

Verify all oracles pass:

.. code-block:: python

   from celor.k8s.artifact import K8sArtifact
   from celor.k8s.oracles import (
       PolicyOracle, SecurityOracle, ResourceOracle,
       CheckovPolicyOracle, CheckovSecurityOracle, SchemaOracle
   )
   
   repaired = K8sArtifact.from_file("fixed/deployment.yaml")
   custom_oracles = [PolicyOracle(), SecurityOracle(), ResourceOracle()]
   external_oracles = [SchemaOracle(), CheckovPolicyOracle(), CheckovSecurityOracle()]
   oracles = custom_oracles + external_oracles
   
   for oracle in oracles:
       violations = oracle(repaired)
       if violations:
           print(f"{oracle.__class__.__name__}: {len(violations)} violations")
       else:
           print(f"{oracle.__class__.__name__}: ✓ All checks pass")

All oracles should pass!

Understanding the Output
------------------------

The repair script outputs:

.. code-block:: text

   Starting repair...
   Found 8+ violations (custom + external oracles)
   Search space: 3,240 combinations
   Running CEGIS synthesis...
   
   Status: success
   Iterations: 1-3
   Candidates tried: 5-15 (vs 3,240 total - 200-600x reduction!)
   Constraints learned: 3-6
   
   Repair successful!

**What happened:**

The repair completed successfully with constraint learning dramatically pruning the search space. The system tried only 5-15 candidates out of 3,240 possible combinations, demonstrating the efficiency of CEGIS synthesis. The ECR policy violation was fixed by selecting an ECR-compliant image from the hole space. For detailed explanation of the repair process, see :doc:`../core_concepts/architecture` and :doc:`../cegis_layer/cegis_loop`.

What's Next?
------------

Try More Complex Examples
~~~~~~~~~~~~~~~~~~~~~~~~~~

The tutorials walk through more complex examples demonstrating CeLoR's capabilities.

Use Fix Bank for Cross-Run Learning
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Enable Fix Bank to reuse successful repair patterns. For details, see :doc:`../core_concepts/fix_bank`.

.. code-block:: python

   from celor.core.fixbank import FixBank
   
   fixbank = FixBank(".celor-fixes.json")
   
   repaired, metadata = repair_artifact(
       artifact=artifact,
       oracles=oracles,
       fixbank=fixbank
   )

Use LLM Integration
~~~~~~~~~~~~~~~~~~~

Enable automatic template generation from LLM. For configuration details, see :doc:`../reference/usage_guide`. For how LLM template generation works, see :doc:`../patch_generation_layer/template_generation`.

.. code-block:: python

   # Add OpenAI API key to config.json, then:
   repaired, metadata = repair_artifact(
       artifact=artifact,
       oracles=oracles
       # LLM adapter auto-created from config.json
   )

Next Steps
----------

* Walk through the detailed tutorials
* Learn about :doc:`../reference/usage_guide` for configuration options
* Explore the :doc:`../cegis_layer/cegis_loop` workflow
* Read the :doc:`../reference/api_reference/core` API reference
