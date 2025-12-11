Template Generation
===================

The template generation phase creates a PatchTemplate with holes. This can come from three sources (in priority order):
  1. **Fix Bank**: Reuse a previously successful template for similar violations
  2. **LLM**: Generate a new template from violations (if API key configured)
  3. **Default**: Use a domain-specific default template function

Purpose
-------

The template identifies:
  - What operations are needed (EnsureLabel, EnsureReplicas, etc.)
  - Where holes should be placed (which values are uncertain)
  - The general structure of the repair

Input
-----

* **Artifact**: The broken K8s manifest (e.g., deployment.yaml)
* **Violations**: Oracle failures (policy, security, resource, schema)
* **Domain Context**: "k8s" for Kubernetes manifests

Process
-------

Fix Bank Lookup (if enabled)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Build signature from violations (failed oracle names, error codes, artifact context)
2. Lookup in Fix Bank
3. If match found: Reuse stored template, hole space, and learned constraints

LLM Generation (if Fix Bank misses and API key configured)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The LLM receives a prompt describing the manifest and violations, then generates a PatchTemplate:

.. code-block:: json

   {
     "template": {
       "ops": [
         {"op": "EnsureLabel", "args": {"key": "env", "value": {"$hole": "env"}}},
         {"op": "EnsureReplicas", "args": {"replicas": {"$hole": "replicas"}}}
       ]
     },
     "hole_space": {
       "env": ["staging-us", "production-us"],
       "replicas": [3, 4, 5]
     }
   }

Default Template (fallback)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If no Fix Bank hit and no LLM, use domain-specific default template (e.g., `payments_api_template_and_holes()`).

Output
------

* **PatchTemplate**: A template with operations containing HoleRef markers
* **HoleSpace**: Domain of possible values for each hole

Key Properties
--------------

* **Minimal Token Usage**: Typically 1 LLM call (or 0 if Fix Bank hits)
* **Structure Focus**: LLM doesn't need to guess exact values, just operations and holes
* **Reusability**: Fix Bank enables cross-run learning

Example
-------

**Input**: Broken manifest with violations:
  - Replicas too low (needs 3-5)
  - Missing labels (team, tier)
  - Image tag is :latest (not allowed in production-us)

**Output**: PatchTemplate with holes:

.. code-block:: python

   PatchTemplate(ops=[
       PatchOp("EnsureReplicas", {"replicas": HoleRef("replicas")}),
       PatchOp("EnsureLabel", {"key": "team", "value": HoleRef("team")}),
       PatchOp("EnsureLabel", {"key": "tier", "value": HoleRef("tier")}),
       PatchOp("EnsureImageVersion", {"container": "payments-api", "version": HoleRef("version")})
   ])
   
   HoleSpace = {
       "replicas": {3, 4, 5},
       "team": {"payments"},
       "tier": {"backend"},
       "version": {"prod-1.2.3", "prod-1.2.4", "prod-1.3.0"}
   }

Next Steps
----------

* Learn about :doc:`../core_concepts/fix_bank` for Fix Bank details
* Understand :doc:`../cegis_layer/index` for how templates are used in synthesis
* Explore :doc:`../reference/api_reference/llm` for LLM integration details

