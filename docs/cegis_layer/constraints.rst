Constraints
===========

Constraints are learned restrictions on hole values extracted from violation evidence. They prune the search space by encoding knowledge about which hole assignments always fail oracle checks.

What are Constraints?
---------------------

A **constraint** is a learned restriction on hole values that tells the synthesizer "this combination of values always fails, so skip it."

Constraints are:
1. Learned during synthesis from oracle failure hints
2. Used to prune candidate enumeration (skip invalid candidates)
3. Stored in Fix Bank for cross-run learning

Constraint Types
----------------

forbidden_value
~~~~~~~~~~~~~~~

A specific value is not allowed for a single hole.

**Example**: ``Constraint(type="forbidden_value", data={"hole": "profile", "value": "small"})``

**Meaning**: ``profile=small`` always violates (e.g., resource checks)

**Usage**: When a single hole value always fails, regardless of other hole values.

forbidden_tuple
~~~~~~~~~~~~~~~

A combination of hole values is not allowed together.

**Example**: ``Constraint(type="forbidden_tuple", data={"holes": ["env", "replicas"], "values": ["production-us", 2]})``

**Meaning**: ``env=production-us AND replicas=2`` together violate policy

**Usage**: When a specific combination of values fails, but each value individually might be valid.

Constraint Learning
-------------------

Constraints are extracted from violation evidence provided by oracles.

**Process**:
    1. Oracle detects violation and includes constraint hint in evidence
    2. Synthesizer extracts hint and creates Constraint object
    3. Constraint is added to constraint list
    4. CandidateGenerator uses constraints to prune search space

**Example**:

.. code-block:: python

   # Violation from PolicyOracle
   violation = Violation(
       id="policy.ENV_PROD_REPLICA_COUNT",
       message="env=production-us requires replicas in [3,5], got 2",
       evidence=ViolationEvidence(
           constraint_hints={"forbid_tuple": [("env", "production-us"), ("replicas", 2)]}
       )
   )
   
   # Extracted constraint
   constraint = Constraint(
       type="forbidden_tuple",
       data={
           "holes": ["env", "replicas"],
           "values": ["production-us", 2]
       }
   )

Constraint Pruning
------------------

Constraints significantly reduce the search space by skipping invalid candidates.

**How it works**:
    1. CandidateGenerator enumerates candidates lexicographically
    2. For each candidate, check if it violates any constraints
    3. If violates → skip (pruning)
    4. If valid → proceed to instantiation and verification

**Example**:

.. code-block:: python

   hole_space = {
       "env": {"staging-us", "production-us"},
       "replicas": {2, 3, 4, 5}
   }
   constraints = [
       Constraint(type="forbidden_tuple", data={"holes": ["env", "replicas"], "values": ["production-us", 2]})
   ]
   
   # Without constraints: 8 candidates (2 × 4)
   # With constraints: 7 candidates (prune {"env": "production-us", "replicas": 2})
   
   generator = CandidateGenerator(hole_space, constraints)
   # Enumerates: staging-us+2, staging-us+3, staging-us+4, staging-us+5, production-us+3, production-us+4, production-us+5
   # Skips: production-us+2 (violates constraint)

Constraint Effectiveness
------------------------

**Single Constraint Impact**:
    - Can prune 10-50% of candidates depending on hole space size
    - More effective when constraint involves frequently-enumerated values

**Multiple Constraints**:
    - 3-5 constraints can prune 50-90% of candidates
    - 10+ constraints can prune 90-99% of candidates

**Fix Bank Warm-Start**:
    - Reusing learned constraints from Fix Bank can skip many invalid candidates
    - Can provide 3-10x speedup for similar problems

Constraint Storage
------------------

Constraints are stored in Fix Bank for cross-run learning. For details on how constraints are stored and reused, see :doc:`../core_concepts/fix_bank`.

Oracle Constraint Hints
-----------------------

Oracles provide constraint hints in violation evidence to help synthesis learn faster. For details on how oracles provide constraint hints, see :doc:`../core_concepts/oracles`.

Best Practices
--------------

**Designing Constraint Hints**:
    - Include constraint hints in oracle evidence when possible
    - Use ``forbid_tuple`` for multi-hole relationships
    - Use ``forbid_value`` for single-hole restrictions

**HoleSpace Design**:
    - Keep hole spaces small to reduce search space
    - Use domain knowledge to narrow values
    - Consider constraint pruning when designing spaces

**Fix Bank Usage**:
    - Enable Fix Bank to reuse learned constraints
    - Commit Fix Bank to git for team knowledge sharing
    - Review stored constraints periodically

Next Steps
----------

* Learn about :doc:`cegis_loop` for how constraints are used in synthesis
* Understand :doc:`../core_concepts/fix_bank` for constraint storage and reuse
* Explore :doc:`../../reference/api_reference/core` for implementation details

