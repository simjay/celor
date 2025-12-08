Core API
========

The core API provides domain-agnostic interfaces and implementations for the CEGIS repair loop.

Schema Module
-------------

Core data models and protocols.

celor.core.schema.artifact
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: celor.core.schema.artifact
   :members:
   :show-inheritance:

celor.core.schema.violation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: celor.core.schema.violation
   :members:
   :show-inheritance:
   :no-index:

celor.core.schema.patch_dsl
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: celor.core.schema.patch_dsl
   :members:
   :show-inheritance:
   :no-index:

celor.core.schema.oracle
~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: celor.core.schema.oracle
   :members:
   :show-inheritance:

Template Module
---------------

Template system for patches with holes.

celor.core.template
~~~~~~~~~~~~~~~~~~~

.. automodule:: celor.core.template
   :members:
   :show-inheritance:
   :no-index:

**Key Components**: See :doc:`../../cegis_layer/holes_and_templates` for detailed explanations.

* ``HoleRef``: Placeholder for uncertain values
* ``PatchTemplate``: Partially specified patch with holes
* ``HoleSpace``: Domain of possible values for each hole
* ``CandidateAssignments``: Specific choice of values
* ``instantiate()``: Convert template + assignment to concrete patch

Synthesis Module
----------------

Custom synthesizer with constraint learning.

celor.core.synth
~~~~~~~~~~~~~~~~

.. automodule:: celor.core.synth
   :members:
   :show-inheritance:

**Key Components**: See :doc:`../../cegis_layer/constraints` and :doc:`../../cegis_layer/holes_and_templates` for detailed explanations.

* ``Constraint``: Learned restriction on hole values
* ``CandidateGenerator``: Enumerates candidates with constraint pruning

CEGIS Module
------------

CEGIS loop implementation.

celor.core.cegis.loop
~~~~~~~~~~~~~~~~~~~~~

.. automodule:: celor.core.cegis.loop
   :members:
   :show-inheritance:

**Key Functions**:

* ``repair()``: Main CEGIS repair loop

celor.core.cegis.verifier
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: celor.core.cegis.verifier
   :members:
   :show-inheritance:

celor.core.cegis.synthesizer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: celor.core.cegis.synthesizer
   :members:
   :show-inheritance:
   :no-index:

**Key Functions**:

* ``synthesize()``: Custom synthesis with candidate enumeration
* ``extract_constraints_from_violations()``: Extract constraints from violation evidence

celor.core.cegis.errors
~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: celor.core.cegis.errors
   :members:
   :show-inheritance:

Controller Module
-----------------

High-level repair orchestration.

celor.core.controller
~~~~~~~~~~~~~~~~~~~~~

.. automodule:: celor.core.controller
   :members:
   :show-inheritance:

**Key Functions**:

* ``repair_artifact()``: Main entry point for artifact repair
  - Fix Bank lookup
  - LLM template generation
  - CEGIS loop execution
  - Fix Bank storage

Fix Bank Module
---------------

Persistent storage for repair patterns.

celor.core.fixbank
~~~~~~~~~~~~~~~~~~

.. automodule:: celor.core.fixbank
   :members:
   :show-inheritance:
   :no-index:

**Key Components**:

* ``FixEntry``: Storage for successful repair patterns
* ``FixBank``: Persistent storage and lookup

Accumulator Module
------------------

Counterexample accumulation.

celor.core.accumulator
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: celor.core.accumulator
   :members:
   :show-inheritance:

Example Usage
-------------

Basic Repair Loop
~~~~~~~~~~~~~~~~~

.. code-block:: python

   from celor.k8s.artifact import K8sArtifact
   from celor.k8s.oracles import PolicyOracle, SecurityOracle
   from celor.core.controller import repair_artifact
   
   artifact = K8sArtifact.from_file("deployment.yaml")
   oracles = [PolicyOracle(), SecurityOracle()]
   
   repaired, metadata = repair_artifact(
       artifact=artifact,
       oracles=oracles
   )

Using Templates and Synthesis
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from celor.core.template import PatchTemplate, HoleRef, instantiate
   from celor.core.synth import CandidateGenerator, Constraint
   from celor.core.cegis.synthesizer import synthesize
   
   template = PatchTemplate(ops=[...])
   hole_space = {"replicas": {3, 4, 5}}
   constraints = [Constraint(...)]
   
   result = synthesize(
       template=template,
       hole_space=hole_space,
       artifact=artifact,
       oracles=oracles,
       initial_constraints=constraints
   )

Using Fix Bank
~~~~~~~~~~~~~~~

.. code-block:: python

   from celor.core.fixbank import FixBank, build_signature
   
   fixbank = FixBank(".celor-fixes.json")
   signature = build_signature(artifact, violations)
   entry = fixbank.lookup(signature)
   
   if entry:
       # Reuse template and constraints
       template = entry.template
       constraints = entry.learned_constraints

Next Steps
----------

* See :doc:`../../core_concepts/key_concepts` for understanding core concepts
* Explore :doc:`adapters` for K8s-specific APIs
* Try the :doc:`../../example/repair_workflow` tutorial
