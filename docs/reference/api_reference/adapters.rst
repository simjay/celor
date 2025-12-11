K8s Adapters API
================

The K8s adapters API provides domain-specific implementations for Kubernetes manifest repair.

K8s Artifact
------------

K8sArtifact represents a Kubernetes manifest collection.

celor.k8s.artifact
~~~~~~~~~~~~~~~~~~

.. automodule:: celor.k8s.artifact
   :members:
   :exclude-members: files
   :show-inheritance:
   :no-index:

**Key Methods**:

* ``from_file(path)``: Load manifest from file
* ``from_dir(dir_path)``: Load all YAML files from directory
* ``write_to_dir(dir_path)``: Write manifests to directory
* ``apply_patch(patch)``: Apply patch to manifest
* ``to_serializable()``: Convert to serializable format

**Example**:

.. code-block:: python

   from celor.k8s.artifact import K8sArtifact
   
   artifact = K8sArtifact.from_file("deployment.yaml")
   repaired = artifact.apply_patch(patch)
   repaired.write_to_dir("fixed")

K8s PatchDSL
------------

PatchDSL defines structured edit operations for K8s manifests.

celor.k8s.patch_dsl
~~~~~~~~~~~~~~~~~~~~

.. automodule:: celor.k8s.patch_dsl
   :members:
   
   :show-inheritance:

**Operations**: See :doc:`../../patch_generation_layer/patch_dsl` for detailed operation descriptions.

* ``EnsureLabel``: Add/update label
* ``EnsureImageVersion``: Set container image version
* ``EnsureSecurityBaseline``: Add security context
* ``EnsureResourceProfile``: Set resource requests/limits
* ``EnsureReplicas``: Set replica count
* ``EnsurePriorityClass``: Set priority class

**Example**:

.. code-block:: python

   from celor.k8s.patch_dsl import apply_k8s_patch, Patch, PatchOp
   
   patch = Patch(ops=[
       PatchOp("EnsureReplicas", {"replicas": 3}),
       PatchOp("EnsureLabel", {"key": "env", "value": "production-us"})
   ])
   
   repaired_files = apply_k8s_patch(original_files, patch)

K8s Oracles
-----------

K8s-specific oracles for manifest validation.

celor.k8s.oracles
~~~~~~~~~~~~~~~~~~

.. automodule:: celor.k8s.oracles
   :members:
   
   :show-inheritance:

**Oracles**:

* ``PolicyOracle``: Policy checks (replicas, labels, image tags)
* ``SecurityOracle``: Security baseline (runAsNonRoot, etc.)
* ``ResourceOracle``: Resource validation
* ``SchemaOracle``: K8s schema validation

**Example**:

.. code-block:: python

   from celor.k8s.oracles import PolicyOracle, SecurityOracle
   
   oracle = PolicyOracle()
   violations = oracle(artifact)

K8s Examples
------------

Example manifests and templates for testing and demos.

celor.k8s.examples
~~~~~~~~~~~~~~~~~~

.. automodule:: celor.k8s.examples
   :members:
   
   :show-inheritance:

**Examples**:

* ``BASELINE_DEPLOYMENT``: Compliant manifest
* ``LLM_EDITED_DEPLOYMENT``: Non-compliant manifest with violations
* ``default_k8s_template()``: Default PatchTemplate
* ``default_k8s_hole_space()``: Default HoleSpace
* ``payments_api_template_and_holes()``: Specific template for payments-api

**Example**:

.. code-block:: python

   from celor.k8s.examples import (
       LLM_EDITED_DEPLOYMENT,
       payments_api_template_and_holes
   )
   
   artifact = K8sArtifact(files={"deployment.yaml": LLM_EDITED_DEPLOYMENT})
   template, hole_space = payments_api_template_and_holes()

Example Usage
-------------

Complete K8s Repair Workflow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from celor.k8s.artifact import K8sArtifact
   from celor.k8s.oracles import PolicyOracle, SecurityOracle, ResourceOracle
   from celor.k8s.patch_dsl import apply_k8s_patch
   from celor.core.controller import repair_artifact
   
   # 1. Load manifest
   artifact = K8sArtifact.from_file("deployment.yaml")
   
   # 2. Create oracles
   oracles = [
       PolicyOracle(),
       SecurityOracle(),
       ResourceOracle()
   ]
   
   # 3. Repair
   repaired, metadata = repair_artifact(
       artifact=artifact,
       oracles=oracles
   )
   
   # 4. Write result
   repaired.write_to_dir("fixed")

Using PatchDSL Directly
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from celor.k8s.patch_dsl import Patch, PatchOp, apply_k8s_patch
   
   patch = Patch(ops=[
       PatchOp("EnsureReplicas", {"replicas": 3}),
       PatchOp("EnsureLabel", {
           "scope": "podTemplate",
           "key": "env",
           "value": "production-us"
       })
   ])
   
   files = {"deployment.yaml": yaml_content}
   repaired_files = apply_k8s_patch(files, patch)

Next Steps
----------

* See :doc:`../../core_concepts/key_concepts` for understanding artifacts and patches
* Explore :doc:`core` for core API details
* Try the :doc:`../../example/repair_workflow` tutorial
