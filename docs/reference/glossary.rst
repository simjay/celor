Glossary
========

This glossary defines key terms used in CeLoR documentation for K8s manifest repair.

Artifact
--------

A domain-specific code or configuration object that can be repaired. For K8s, this is a ``K8sArtifact`` containing YAML manifest files.

CEGIS
-----

**Counterexample-Guided Inductive Synthesis**. A program synthesis technique that alternates between:
    1. **Synthesis**: Generate candidate assignment satisfying known constraints
    2. **Verification**: Check if candidate satisfies all specifications

If verification fails, the failure provides constraints that prune the next synthesis attempt.

Constraint
----------

A learned restriction on hole values extracted from violation evidence. Types:
    - ``forbidden_value``: A specific value is not allowed for a hole
    - ``forbidden_tuple``: A combination of values is not allowed

For detailed explanation, see :doc:`../core_concepts/key_concepts`.

Hole
----

A placeholder in PatchTemplate marked with ``HoleRef("name")`` that represents an uncertain value to be synthesized. Holes are filled by the synthesizer with concrete values from HoleSpace.

HoleRef
-------

A reference to a hole in PatchTemplate. Example: ``HoleRef("replicas")`` in ``PatchOp("EnsureReplicas", {"replicas": HoleRef("replicas")})``.

HoleSpace
---------

The domain of possible values for each hole. Example: ``{"replicas": {3, 4, 5}, "env": {"production-us"}}``.

CandidateAssignments
---------------------

A specific choice of values for all holes. Example: ``{"replicas": 3, "env": "production-us"}``.

PatchTemplate
-------------

A partially specified patch containing operations with holes. The template defines the structure of the repair without specifying exact values.

Patch
-----

A concrete patch containing operations with concrete values (no holes). Patches are applied to artifacts using PatchDSL.

PatchDSL
--------

**Patch Domain-Specific Language**. A language defining structured edit operations for K8s manifests. Operations include EnsureLabel, EnsureReplicas, EnsureImageVersion, etc.

Oracle
------

A verification function that checks an artifact and returns violations. K8s oracles include PolicyOracle, SecurityOracle, ResourceOracle, and SchemaOracle.

Violation
---------

A representation of a policy failure, security issue, or error detected by an oracle. Contains evidence with constraint hints for synthesis.

Fix Bank
--------

Persistent storage (JSON file) for successful repair patterns. Enables cross-run learning and team knowledge sharing.

FixEntry
--------

A single entry in Fix Bank containing:
    - Signature (violation fingerprint)
    - PatchTemplate used
    - HoleSpace used
    - Learned constraints
    - Successful candidate assignment
    - Metadata (success count, timestamps)

Synthesizer
-----------

The component that enumerates candidates from HoleSpace and fills holes. Uses lexicographic enumeration with constraint pruning.

CandidateGenerator
------------------

The component that enumerates candidates from HoleSpace while respecting constraints. Prunes invalid candidates to reduce search space.

For detailed explanation, see :doc:`../core_concepts/key_concepts`.

Next Steps
----------

* See :doc:`../core_concepts/key_concepts` for detailed explanations
* Explore :doc:`../core_concepts/architecture` to understand the complete workflow
* Try the :doc:`../example/repair_workflow` tutorial
