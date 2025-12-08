Problem Statement
==================

Why CeLoR?
----------

Kubernetes manifest generation with Large Language Models (LLMs) has become increasingly common, but it faces significant challenges that CeLoR addresses.

The Problem with LLM-Generated K8s Manifests
---------------------------------------------

When using LLMs to generate Kubernetes deployment manifests, several K8s-specific issues arise:

**Policy Violations**
   LLMs often generate manifests that violate organizational policies. For example, production deployments might use ``:latest`` image tags, have insufficient replicas (e.g., 2 instead of 3-5), or lack required labels like ``team`` and ``tier``.

**Security Gaps**
   Generated manifests frequently miss critical security configurations such as ``runAsNonRoot: true``, proper resource limits, or security contexts, leaving applications vulnerable.

**Manual Fixes are Time-Consuming**
   Developers must manually review and fix each violation, which is error-prone and slows down deployment workflows. This becomes especially problematic when generating many manifests or when policies change frequently.

For a discussion of general challenges with LLM-based configuration generation (token costs, determinism, privacy), see :doc:`../core_concepts/overview`.

Example Scenario
----------------

Consider a developer asking an LLM to generate a production Kubernetes deployment manifest. The LLM might produce:

.. code-block:: yaml

   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: payments-api
   spec:
     replicas: 2  # ❌ Policy violation: prod requires 3-5
     template:
       spec:
         containers:
         - name: payments-api
           image: payments-api:latest  # ❌ Policy violation: prod cannot use :latest
           resources:
             requests:
               cpu: "100m"  # ❌ Resource violation: prod needs medium/large profile
           # ❌ Missing security context

Without CeLoR, the developer would need to:
   1. Manually identify all violations
   2. Fix each one individually
   3. Re-verify after each fix
   4. Repeat if new violations are introduced

With CeLoR, the developer simply runs:

.. code-block:: bash

   celor repair deployment.yaml --out fixed/

CeLoR automatically:
   1. Detects all violations using oracles
   2. Generates a repair template (from LLM, Fix Bank, or default)
   3. Synthesizes correct values using local CEGIS loop
   4. Produces a verified, compliant manifest

The repaired manifest satisfies all policy, security, and resource requirements automatically.

Next Steps
----------

* Learn the :doc:`repair_workflow` to see CeLoR in action
* Understand :doc:`../core_concepts/oracles` for verification concepts
* Explore :doc:`k8s_oracles` for K8s-specific oracle details

