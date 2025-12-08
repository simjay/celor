K8s PatchDSL Operations
=========================

This page documents the Kubernetes-specific PatchDSL operations available in CeLoR. For general PatchDSL concepts, see :doc:`../patch_generation_layer/patch_dsl`.

Overview
--------

CeLoR provides six built-in PatchDSL operations for modifying Kubernetes deployment manifests:
    * ``EnsureLabel`` - Add or update labels
    * ``EnsureImageVersion`` - Set container image version
    * ``EnsureSecurityBaseline`` - Enforce security baseline
    * ``EnsureResourceProfile`` - Set resource requests/limits from profile
    * ``EnsureReplicas`` - Set replica count
    * ``EnsurePriorityClass`` - Set priorityClassName

Operations
----------

EnsureLabel
~~~~~~~~~~~

Add or update labels in deployment manifest.

**Args**:
    * ``scope``: "deployment" | "podTemplate" | "both" (default: "both")
    * ``key``: Label key (string)
    * ``value``: Label value (string or HoleRef)

**Example**:

.. code-block:: python

   from celor.core.schema.patch_dsl import PatchOp
   
   # Add label to both deployment and pod template
   op = PatchOp("EnsureLabel", {
       "scope": "both",
       "key": "env",
       "value": "prod"
   })
   
   # Add label with hole for synthesis
   from celor.core.template import HoleRef
   op = PatchOp("EnsureLabel", {
       "scope": "both",
       "key": "team",
       "value": HoleRef("team")
   })

EnsureImageVersion
~~~~~~~~~~~~~~~~~~

Set container image version.

**Args**:
    * ``container``: Container name (string)
    * ``version``: Image version/tag (string or HoleRef)

**Example**:

.. code-block:: python

   from celor.core.schema.patch_dsl import PatchOp
   
   # Set concrete version
   op = PatchOp("EnsureImageVersion", {
       "container": "payments-api",
       "version": "prod-1.2.3"
   })
   
   # Set version with hole for synthesis
   from celor.core.template import HoleRef
   op = PatchOp("EnsureImageVersion", {
       "container": "payments-api",
       "version": HoleRef("version")
   })

EnsureSecurityBaseline
~~~~~~~~~~~~~~~~~~~~~~

Enforce security baseline on container (runAsNonRoot, etc.).

**Args**:
    * ``container``: Container name (string)

**Example**:

.. code-block:: python

   from celor.core.schema.patch_dsl import PatchOp
   
   op = PatchOp("EnsureSecurityBaseline", {
       "container": "payments-api"
   })

This operation automatically adds:
    * ``runAsNonRoot: true``
    * ``allowPrivilegeEscalation: false``
    * ``readOnlyRootFilesystem: true`` (if applicable)
    * ``capabilities.drop: [ALL]``

EnsureResourceProfile
~~~~~~~~~~~~~~~~~~~~~

Set resource requests/limits from profile.

**Args**:
    * ``container``: Container name (string)
    * ``profile``: "small" | "medium" | "large" (string or HoleRef)

**Example**:

.. code-block:: python

   from celor.core.schema.patch_dsl import PatchOp
   
   # Set concrete profile
   op = PatchOp("EnsureResourceProfile", {
       "container": "payments-api",
       "profile": "medium"
   })
   
   # Set profile with hole for synthesis
   from celor.core.template import HoleRef
   op = PatchOp("EnsureResourceProfile", {
       "container": "payments-api",
       "profile": HoleRef("resource_profile")
   })

**Resource Profiles**:
    * **Small**: 100m CPU, 128Mi memory (requests) / 200m CPU, 256Mi memory (limits)
    * **Medium**: 500m CPU, 512Mi memory (requests) / 1000m CPU, 1Gi memory (limits)
    * **Large**: 2000m CPU, 2Gi memory (requests) / 4000m CPU, 4Gi memory (limits)

EnsureReplicas
~~~~~~~~~~~~~~

Set replica count.

**Args**:
    * ``replicas``: Replica count (int or HoleRef)

**Example**:

.. code-block:: python

   from celor.core.schema.patch_dsl import PatchOp
   
   # Set concrete replica count
   op = PatchOp("EnsureReplicas", {"replicas": 3})
   
   # Set replica count with hole for synthesis
   from celor.core.template import HoleRef
   op = PatchOp("EnsureReplicas", {"replicas": HoleRef("replicas")})

EnsurePriorityClass
~~~~~~~~~~~~~~~~~~~

Set priorityClassName.

**Args**:
    * ``name``: Priority class name (string, None, or HoleRef)

**Example**:

.. code-block:: python

   from celor.core.schema.patch_dsl import PatchOp
   
   # Set concrete priority class
   op = PatchOp("EnsurePriorityClass", {"name": "critical"})
   
   # Set priority class with hole for synthesis
   from celor.core.template import HoleRef
   op = PatchOp("EnsurePriorityClass", {"name": HoleRef("priority_class")})
   
   # Remove priority class
   op = PatchOp("EnsurePriorityClass", {"name": None})

Applying K8s Patches
--------------------

K8s patches are applied using the K8s-specific executor:

.. code-block:: python

   from celor.k8s.patch_dsl import apply_k8s_patch
   from celor.core.schema.patch_dsl import Patch, PatchOp
   
   # Create patch
   patch = Patch(ops=[
       PatchOp("EnsureReplicas", {"replicas": 3}),
       PatchOp("EnsureLabel", {
           "scope": "both",
           "key": "env",
           "value": "prod"
       }),
       PatchOp("EnsureImageVersion", {
           "container": "payments-api",
           "version": "prod-1.2.3"
       })
   ])
   
   # Apply patch
   files = {"deployment.yaml": yaml_content}
   patched_files = apply_k8s_patch(files, patch)

The executor:
    * Preserves YAML formatting and comments (using ruamel.yaml)
    * Applies operations sequentially
    * Handles K8s-specific edge cases (e.g., nested structures, array handling)

Example: Complete Patch
-----------------------

**Concrete Patch** (no holes):

.. code-block:: python

   from celor.core.schema.patch_dsl import Patch, PatchOp
   
   patch = Patch(ops=[
       PatchOp("EnsureReplicas", {"replicas": 3}),
       PatchOp("EnsureLabel", {
           "scope": "both",
           "key": "env",
           "value": "prod"
       }),
       PatchOp("EnsureLabel", {
           "scope": "both",
           "key": "team",
           "value": "payments"
       }),
       PatchOp("EnsureImageVersion", {
           "container": "payments-api",
           "version": "prod-1.2.3"
       }),
       PatchOp("EnsureSecurityBaseline", {
           "container": "payments-api"
       }),
       PatchOp("EnsureResourceProfile", {
           "container": "payments-api",
           "profile": "medium"
       }),
       PatchOp("EnsurePriorityClass", {"name": "critical"})
   ])

**PatchTemplate** (with holes):

.. code-block:: python

   from celor.core.template import PatchTemplate, HoleRef
   from celor.core.schema.patch_dsl import PatchOp
   
   template = PatchTemplate(ops=[
       PatchOp("EnsureReplicas", {"replicas": HoleRef("replicas")}),
       PatchOp("EnsureLabel", {
           "scope": "both",
           "key": "env",
           "value": HoleRef("env")
       }),
       PatchOp("EnsureImageVersion", {
           "container": "payments-api",
           "version": HoleRef("version")
       }),
       PatchOp("EnsureResourceProfile", {
           "container": "payments-api",
           "profile": HoleRef("resource_profile")
       }),
       PatchOp("EnsurePriorityClass", {"name": HoleRef("priority_class")})
   ])

Next Steps
----------

* Learn about :doc:`../patch_generation_layer/patch_dsl` for general PatchDSL concepts
* See :doc:`repair_workflow` for a complete repair example using these operations
* Explore :doc:`../reference/api_reference/adapters` for detailed API documentation

