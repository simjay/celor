Oracles
=======

Oracles are verification functions that check whether an artifact satisfies correctness criteria. This page explains the general oracle concept and protocol. For K8s-specific oracle details, see :doc:`../example/k8s_oracles`.

What is an Oracle?
------------------

An **oracle** is a function that:

1. Takes an artifact as input
2. Executes some verification (policy checks, security validation, schema checks, etc.)
3. Returns a list of ``Violation`` objects representing failures

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

Oracle Protocol
---------------

The oracle protocol is simple: any callable that takes an artifact and returns a list of violations is an oracle.

**Signature**:
   ``oracle(artifact: Artifact) -> List[Violation]``

**Return Value**:
   * Empty list ``[]``: Artifact passes all checks
   * Non-empty list: Contains all violations found

**Example**:

.. code-block:: python

   from celor.k8s.artifact import K8sArtifact
   from celor.k8s.oracles import PolicyOracle
   
   artifact = K8sArtifact.from_file("deployment.yaml")
   oracle = PolicyOracle()
   
   violations = oracle(artifact)
   if not violations:
       print("All checks pass!")
   else:
       print(f"Found {len(violations)} violations")

How Oracles Work in CEGIS
--------------------------

Oracles play a critical role in the CEGIS (Counterexample-Guided Inductive Synthesis) loop:

1. **Initial Verification**: Oracles check the initial artifact and report violations
2. **Constraint Extraction**: Violations contain constraint hints that guide synthesis
3. **Iterative Verification**: After each candidate is applied, oracles verify the result
4. **Termination**: The loop terminates when all oracles pass (no violations)

.. code-block:: python

   # Simplified CEGIS loop with oracles
   for iteration in range(max_iters):
       # Step 1: Verify current artifact
       all_violations = []
       for oracle in oracles:
           violations = oracle(current_artifact)
           all_violations.extend(violations)
       
       # Step 2: If all pass, we're done
       if not all_violations:
           return current_artifact  # Success!
       
       # Step 3: Extract constraints from violations
       constraints = extract_constraints(all_violations)
       
       # Step 4: Synthesize next candidate (avoiding constraints)
       candidate = synthesize_next(constraints)
       
       # Step 5: Apply candidate and repeat
       current_artifact = apply_patch(current_artifact, candidate)

Constraint Hints
----------------

Oracles provide **constraint hints** in violation evidence to guide synthesis. These hints help the synthesizer prune invalid candidates early.

**Common Constraint Hint Types**:
    * ``forbid_tuple``: Forbids specific combinations of values
    * ``forbid_value``: Forbids specific values for a field
    * ``require_value``: Requires specific values for a field

**Example**:

.. code-block:: python

   from celor.core.schema.violation import Violation, ViolationEvidence
   
   violation = Violation(
       id="policy.ENV_PROD_REPLICA_COUNT",
       message="env=production-us requires replicas in [3,5], got 2",
       evidence=ViolationEvidence(
           constraint_hints={
               "forbid_tuple": {
                   "holes": ["env", "replicas"],
                   "values": ["production-us", 2]
               }
           }
       )
   )

The synthesizer extracts these hints and uses them to prune the search space, avoiding invalid combinations.

Multiple Oracles
----------------

You can use multiple oracles to check different aspects of an artifact:

.. code-block:: python

   oracles = [
       PolicyOracle(),      # Policy checks
       SecurityOracle(),    # Security baseline
       ResourceOracle(),    # Resource validation
       SchemaOracle()       # Schema validation
   ]
   
   # All oracles must pass for repair to succeed
   repaired, metadata = repair_artifact(
       artifact=artifact,
       oracles=oracles
   )

**Oracle Execution**:
    * Oracles run in the order specified
    * All violations from all oracles are collected
    * The repair must satisfy **all** oracles to succeed

Creating Custom Oracles
-----------------------

You can create custom oracles for domain-specific verification:

.. code-block:: python

   from typing import List
   from celor.core.schema.violation import Violation, ViolationEvidence
   from celor.core.schema.artifact import Artifact
   
   def custom_policy_oracle(artifact: Artifact) -> List[Violation]:
       """Custom oracle that checks business rules."""
       violations = []
       
       # Check custom policy
       if violates_custom_policy(artifact):
           violations.append(Violation(
               id="custom.policy.violation",
               message="Custom policy violation",
               evidence=ViolationEvidence(
                   constraint_hints={
                       "forbid_value": [("field", "invalid_value")]
                   }
               )
           ))
       
       return violations

**Best Practices**:
    * Return empty list when artifact passes all checks
    * Include constraint hints in violation evidence when possible
    * Use descriptive violation IDs and messages
    * Make oracles deterministic (same input → same output)

Oracle vs. Synthesizer
-----------------------

It's important to understand the distinction:
    * **Oracle**: Verifies an artifact and reports violations
    * **Synthesizer**: Generates candidate values to fill holes in templates

The oracle doesn't know how to fix violations—it only reports them. The synthesizer uses oracle feedback (violations and constraint hints) to generate better candidates.

Next Steps
----------

* See :doc:`../example/k8s_oracles` for K8s-specific oracle details
* Learn about :doc:`../cegis_layer/cegis_loop` to understand how oracles are used in synthesis
* Explore :doc:`../reference/oracle_system` for complete oracle API documentation
* Read :doc:`key_concepts` for more on violations and constraint hints

