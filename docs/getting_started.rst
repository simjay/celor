Getting Started
===============

This guide will help you get CeLoR running quickly for Kubernetes manifest repair.

Installation
-------------

Install CeLoR from source:

.. code-block:: bash

   pip install -e .

This installs CeLoR and required dependencies (``ruamel.yaml``, ``openai``).

**Optional**: For enhanced oracle support:

.. code-block:: bash

   pip install celor[oracles]

This adds ``kubernetes-validate`` and ``checkov`` for comprehensive validation.

Configuration
-------------

Create a ``config.json`` file in your project root:

.. code-block:: json

   {
     "openai": {
       "api_key": "sk-...",
       "model": "gpt-4"
     }
   }

**Note**: The API key is optional. Without it, CeLoR uses default templates (no LLM calls).

For detailed configuration options, see :doc:`reference/usage_guide`.

Quick Example
-------------

Repair a Kubernetes deployment manifest:

.. code-block:: python

   from celor.k8s.artifact import K8sArtifact
   from celor.k8s.oracles import PolicyOracle, SecurityOracle
   from celor.core.controller import repair_artifact
   
   # Load manifest
   artifact = K8sArtifact.from_file("deployment.yaml")
   
   # Create oracles
   oracles = [PolicyOracle(), SecurityOracle()]
   
   # Run repair
   repaired, metadata = repair_artifact(
       artifact=artifact,
       oracles=oracles
   )
   
   # Save result
   if metadata["status"] == "success":
       repaired.write_to_dir("fixed/")
       print(f"Repaired in {metadata['tried_candidates']} candidates")

Or using the CLI:

.. code-block:: bash

   celor repair deployment.yaml --out fixed/

What Happens
------------

CeLoR detects violations, generates repair templates, synthesizes values, and verifies results. For detailed explanations, see :doc:`core_concepts/architecture`.

Next Steps
----------

* Learn about the :doc:`core_concepts/architecture` to understand how CeLoR works
* Explore :doc:`example/repair_workflow` for a detailed walkthrough
* Read :doc:`reference/usage_guide` for configuration and CLI options

