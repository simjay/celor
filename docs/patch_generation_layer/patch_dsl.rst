PatchDSL
========

**PatchDSL** (Patch Domain-Specific Language) defines structured edit operations for modifying artifacts. It provides a domain-agnostic way to represent patches, with domain-specific implementations for different artifact types.

Overview
--------

PatchDSL is a tiny programming language whose programs are "patches" - sequences of operations that modify artifacts. The language is designed to be:

* **Structured**: Operations are explicit and well-defined
* **Composable**: Multiple operations can be combined sequentially
* **Domain-Agnostic Core**: Core data structures work across domains
* **Domain-Specific Operations**: Each domain implements its own operations

Core Data Structures
--------------------

The core PatchDSL is defined in ``celor.core.schema.patch_dsl``:

**PatchOp**
   A single atomic patch operation with:
   
   * ``op``: Operation name (e.g., "EnsureLabel", "EnsureReplicas")
   * ``args``: Operation-specific arguments as a dictionary

**Patch**
   A sequence of operations to be applied to an artifact:
   
   * ``ops``: List of PatchOp operations
   * ``holes``: Optional metadata about holes (for synthesis)
   * ``meta``: Optional metadata (artifact name, version, etc.)

**Example**:

.. code-block:: python

   from celor.core.schema.patch_dsl import Patch, PatchOp
   
   patch = Patch(ops=[
       PatchOp("Operation1", {"arg1": "value1"}),
       PatchOp("Operation2", {"arg2": "value2"})
   ])

Domain-Specific Operations
--------------------------

Each domain implements its own set of operations. For example:
   * **Kubernetes**: Operations like ``EnsureLabel``, ``EnsureReplicas``, ``EnsureImageVersion``, etc.
   * **Python**: Operations for code modifications (future)
   * **JSON**: Operations for JSON schema updates (future)

For K8s-specific operations, see :doc:`../example/k8s_patch_dsl`.

Example Usage
-------------

**Concrete Patch** (no holes):

.. code-block:: python

   from celor.core.schema.patch_dsl import Patch, PatchOp
   
   patch = Patch(ops=[
       PatchOp("Operation1", {"arg1": "value1"}),
       PatchOp("Operation2", {"arg2": "value2"})
   ])

**PatchTemplate** (with holes):

.. code-block:: python

   from celor.core.template import PatchTemplate, HoleRef
   from celor.core.schema.patch_dsl import PatchOp
   
   template = PatchTemplate(ops=[
       PatchOp("Operation1", {"arg1": HoleRef("hole1")}),
       PatchOp("Operation2", {"arg2": HoleRef("hole2")})
   ])

Applying Patches
----------------

Patches are applied using domain-specific executors. Each domain provides an ``apply_<domain>_patch()`` function:

.. code-block:: python

   # Example for a generic domain
   from celor.<domain>.patch_dsl import apply_<domain>_patch
   
   files = {"artifact.ext": content}
   patched_files = apply_<domain>_patch(files, patch)

The executor:
* Preserves original formatting when possible
* Applies operations sequentially
* Handles domain-specific edge cases

For K8s-specific patch application, see :doc:`../example/k8s_patch_dsl`.

JSON Transport Format
---------------------

Patches are serialized to JSON for LLM communication and storage:

.. code-block:: json

   {
     "ops": [
       {
         "op": "Operation1",
         "args": {"arg1": {"$hole": "hole1"}}
       },
       {
         "op": "Operation2",
         "args": {
           "arg2": "value2",
           "arg3": {"$hole": "hole2"}
         }
       }
     ]
   }

Holes are represented as ``{"$hole": "hole_id"}`` in JSON.

Extending PatchDSL
-------------------

To add support for a new domain:

1. **Define Operations**: Create domain-specific operation names and argument schemas
2. **Implement Executor**: Create ``apply_<domain>_patch()`` function that interprets operations
3. **Update LLM Prompts**: Add domain-specific prompt templates for template generation
4. **Add Tests**: Test each operation with various inputs

**Example Structure**:

.. code-block:: python

   # celor/<domain>/patch_dsl.py
   
   from celor.core.schema.patch_dsl import Patch, PatchOp
   
   def apply_<domain>_patch(files: dict, patch: Patch) -> dict:
       """Apply domain-specific patch operations."""
       result = dict(files)
       for op in patch.ops:
           result = apply_<domain>_op(result, op)
       return result
   
   def apply_<domain>_op(files: dict, op: PatchOp) -> dict:
       """Apply single domain-specific operation."""
       if op.op == "YourOperation":
           return _apply_your_operation(files, op.args)
       # ... other operations

Next Steps
----------

* Learn about :doc:`template_generation` for how PatchDSL is used in template generation
* Understand :doc:`../cegis_layer/index` for how patches with holes are synthesized
* Explore :doc:`../reference/api_reference/core` for API details

