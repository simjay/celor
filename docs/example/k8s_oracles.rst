K8S Oracles
===========

This page documents the built-in Kubernetes oracles available in CeLoR. For general oracle concepts, see :doc:`../core_concepts/oracles`.

Built-in K8s Oracles
--------------------

CeLoR provides four built-in oracles for Kubernetes manifest validation:

PolicyOracle
~~~~~~~~~~~~

Checks custom policy rules for production deployments.

**Checks**:
    * **AWS ECR policy**: Images must come from AWS ECR repositories
    * Production replicas must be 3-5
    * Production requires labels: ``env``, ``team``, ``tier``
    * Production cannot use ``:latest`` or ``:staging`` image tags
    * Production requires ``priorityClassName``
    * Production resource profile must be medium or large

**Usage**:

.. code-block:: python

   from celor.k8s.oracles import PolicyOracle
   
   oracle = PolicyOracle()
   violations = oracle(artifact)

**Constraint Hints**:
    * Provides ``forbid_tuple`` hints for policy violations
    * Example: ``forbid_tuple(env="prod", replicas=2)``

**Example Violations**:

.. code-block:: python

   [
       Violation(
           id="policy.IMAGE_NOT_FROM_ECR",
           message="Image must come from AWS ECR, got docker.io/library/payments-api:latest",
           evidence={
               "forbid_value": {
                   "hole": "version",
                   "value": "docker.io/library/payments-api:latest"
               }
           }
       ),
       Violation(
           id="policy.ENV_PROD_REPLICA_COUNT",
           message="env=prod requires replicas in [3,5], got 2",
           evidence={
               "forbid_tuple": {
                   "holes": ["env", "replicas"],
                   "values": ["prod", 2]
               }
           }
       )
   ]

SecurityOracle
~~~~~~~~~~~~~~

Checks security baseline requirements.

**Checks**:
    * ``runAsNonRoot: true``
    * ``allowPrivilegeEscalation: false``
    * ``readOnlyRootFilesystem: true`` (if applicable)
    * ``capabilities.drop: [ALL]``

**Usage**:

.. code-block:: python

   from celor.k8s.oracles import SecurityOracle
   
   oracle = SecurityOracle()
   violations = oracle(artifact)

**Example Violations**:

.. code-block:: python

   [
       Violation(
           id="security.MISSING_RUN_AS_NON_ROOT",
           message="Container must run as non-root user",
           evidence={}
       )
   ]

ResourceOracle
~~~~~~~~~~~~~~

Validates resource requests and limits.

**Checks**:
    * Resources are set (requests and limits)
    * Resources match known profiles (small, medium, large)
    * Warnings for non-standard profiles

**Usage**:

.. code-block:: python

   from celor.k8s.oracles import ResourceOracle
   
   oracle = ResourceOracle()
   violations = oracle(artifact)

**Resource Profiles**:
    * **Small**: 100m CPU, 128Mi memory (requests) / 200m CPU, 256Mi memory (limits)
    * **Medium**: 500m CPU, 512Mi memory (requests) / 1000m CPU, 1Gi memory (limits)
    * **Large**: 2000m CPU, 2Gi memory (requests) / 4000m CPU, 4Gi memory (limits)

SchemaOracle
~~~~~~~~~~~~

Validates K8s schema (optional, requires kubectl or kubernetes-validate).

**Checks**:
    * Valid K8s API version
    * Required fields present
    * Field types correct
    * Valid enum values

**Usage**:

.. code-block:: python

   from celor.k8s.oracles import SchemaOracle
   
   oracle = SchemaOracle()
   violations = oracle(artifact)

**Note**: This oracle gracefully handles missing tools. If neither kubernetes-validate nor kubectl is available, it returns no violations.

External Oracle Integration
----------------------------

CeLoR supports integration with external validation tools for comprehensive checks. These oracles wrap industry-standard tools while maintaining constraint hint capability.

CheckovPolicyOracle
~~~~~~~~~~~~~~~~~~~

Wraps `Checkov <https://www.checkov.io/>`_ for comprehensive policy checks (200+ rules).

**Features**:
    * 200+ built-in Kubernetes policy checks
    * Constraint hint extraction from Checkov results
    * Graceful fallback when Checkov unavailable

**Installation**:

.. code-block:: bash

   pip install celor[oracles]

**Usage**:

.. code-block:: python

   from celor.k8s.oracles import CheckovPolicyOracle
   
   oracle = CheckovPolicyOracle()
   violations = oracle(artifact)
   
   # If Checkov not available, returns empty list (graceful fallback)

**Checks**: Includes checks for replicas, labels, image tags, resource limits, and more.

CheckovSecurityOracle
~~~~~~~~~~~~~~~~~~~~~

Wraps Checkov for security-specific checks.

**Features**:
    * Security-focused subset of Checkov checks
    * Filters for security-specific check IDs (CKV_K8S_8, CKV_K8S_23, etc.)
    * Graceful fallback when Checkov unavailable

**Usage**:

.. code-block:: python

   from celor.k8s.oracles import CheckovSecurityOracle
   
   oracle = CheckovSecurityOracle()
   violations = oracle(artifact)

Hybrid Approach
~~~~~~~~~~~~~~~

Use both custom and external oracles for comprehensive validation:

.. code-block:: python

   from celor.k8s.oracles import (
       PolicyOracle, SecurityOracle, ResourceOracle,
       CheckovPolicyOracle, CheckovSecurityOracle, SchemaOracle
   )
   
   # Custom oracles (provide constraint hints)
   custom_oracles = [
       PolicyOracle(),      # ECR policy, replicas, labels
       SecurityOracle(),    # Security baseline
       ResourceOracle()     # Resource validation
   ]
   
   # External oracles (comprehensive checks)
   external_oracles = [
       SchemaOracle(use_kubernetes_validate=True),  # Schema validation
       CheckovPolicyOracle(),  # 200+ policy checks
       CheckovSecurityOracle()  # Security checks
   ]
   
   oracles = custom_oracles + external_oracles
   
   # Run all oracles
   violations = []
   for oracle in oracles:
       violations.extend(oracle(artifact))
   
   print(f"Total violations: {len(violations)}")
   print(f"  - Custom: {sum(len(o(artifact)) for o in custom_oracles)}")
   print(f"  - External: {sum(len(o(artifact)) for o in external_oracles)}")

**Benefits**:
    * Custom oracles provide constraint hints for efficient synthesis
    * External oracles provide comprehensive validation (200+ checks)
    * Best of both worlds: precision + coverage

Combining K8s Oracles
----------------------

You can combine multiple oracles to enforce comprehensive checks:

.. code-block:: python

   from celor.k8s.artifact import K8sArtifact
   from celor.k8s.oracles import (
       PolicyOracle,
       SecurityOracle,
       ResourceOracle,
       SchemaOracle
   )
   from celor.core.controller import repair_artifact
   
   # Load artifact
   artifact = K8sArtifact.from_file("deployment.yaml")
   
   # Create multiple oracles
   oracles = [
       PolicyOracle(),      # Production policies
       SecurityOracle(),    # Security baseline
       ResourceOracle(),    # Resource validation
       SchemaOracle()       # Schema validation (optional)
   ]
   
   # Run repair
   repaired, metadata = repair_artifact(
       artifact=artifact,
       oracles=oracles
   )
   
   print(f"Status: {metadata['status']}")
   print(f"Violations fixed: {len(metadata.get('initial_violations', []))}")

**Oracle Execution Order**:
    * Oracles run in the order specified
    * All violations are collected
    * Synthesis must satisfy all oracles

Example: Multiple Oracle Violations
-------------------------------------

Consider a manifest with violations across multiple oracles:

.. code-block:: yaml

   # deployment.yaml
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: payments-api
   spec:
     replicas: 2  # Policy violation
     template:
       spec:
         containers:
         - name: payments-api
           image: payments-api:latest  # Policy violation
           # Missing security context (Security violation)
           resources:
             requests:
               cpu: "100m"  # Resource violation
               memory: "128Mi"

Running all oracles:

.. code-block:: python

   from celor.k8s.artifact import K8sArtifact
   from celor.k8s.oracles import PolicyOracle, SecurityOracle, ResourceOracle
   
   artifact = K8sArtifact.from_file("deployment.yaml")
   oracles = [PolicyOracle(), SecurityOracle(), ResourceOracle()]
   
   violations = []
   for oracle in oracles:
       oracle_violations = oracle(artifact)
       violations.extend(oracle_violations)
       print(f"{oracle.__class__.__name__}: {len(oracle_violations)} violations")
   
   print(f"\nTotal violations: {len(violations)}")

Output:

.. code-block:: text

   PolicyOracle: 3 violations
   SecurityOracle: 2 violations
   ResourceOracle: 1 violations
   
   Total violations: 6

The repair loop will ensure the final manifest satisfies all oracles.

Next Steps
----------

* Learn about :doc:`../core_concepts/oracles` for general oracle concepts
* See :doc:`repair_workflow` for a complete repair example
* Explore :doc:`../reference/oracle_system` for detailed oracle API documentation

