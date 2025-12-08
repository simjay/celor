Oracle System API Reference
============================

This page provides API reference documentation for the oracle system. For general oracle concepts, see :doc:`../core_concepts/oracles`. For K8s-specific oracle details and examples, see :doc:`../example/k8s_oracles`.

Oracle Protocol
----------------

All oracles follow the ``Oracle`` protocol:

.. code-block:: python

   from typing import List
   from celor.core.schema.oracle import Oracle
   from celor.core.schema.violation import Violation
   from celor.core.schema.artifact import Artifact
   
   def my_oracle(artifact: Artifact) -> List[Violation]:
       """Oracle function that verifies artifact."""
       violations = []
       # ... perform verification ...
       return violations

**Signature**: ``oracle(artifact: Artifact) -> List[Violation]``

**Return Value**:
* Empty list ``[]``: Artifact passes all checks
* Non-empty list: Contains all violations found

Built-in K8s Oracles
--------------------

CeLoR provides four built-in oracles for K8s. For detailed descriptions, usage examples, and constraint hints, see :doc:`../example/k8s_oracles`.

* **PolicyOracle**: Policy checks (replicas, labels, image tags)
* **SecurityOracle**: Security baseline (runAsNonRoot, etc.)
* **ResourceOracle**: Resource validation
* **SchemaOracle**: K8s schema validation (optional)

Creating Custom Oracles
-----------------------

You can create custom oracles for domain-specific verification. For examples and best practices, see :doc:`../core_concepts/oracles`.

Oracle Evidence Structure
-------------------------

Each violation returned by an oracle should include rich evidence:

- **Constraint Hints**: ``forbid_value``, ``forbid_tuple`` for synthesis (see :doc:`../core_concepts/oracles` for details)
- **Location**: File path, field path
- **Context**: Current values that caused violation
- **Error Code**: Unique identifier for the violation type

This evidence is used by:

- **Synthesizer**: To extract constraints and prune search space
- **Fix Bank**: To build signatures for pattern matching
- **Debugging**: To understand why violations occurred

Next Steps
----------

* Learn about :doc:`../core_concepts/oracles` for general oracle concepts and constraint hints
* See :doc:`../example/k8s_oracles` for K8s-specific oracle details and examples
* Explore :doc:`api_reference/core` for complete Oracle protocol API documentation
