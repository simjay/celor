CEGIS Loop
==========

The **CEGIS (Counterexample-Guided Inductive Synthesis) loop** is the core of CeLoR's synthesis phase. It iteratively verifies, learns constraints, and enumerates candidates until all oracles pass or a termination condition is met.

What is CEGIS?
--------------

CEGIS is a classical program synthesis technique that alternates between two phases:
   1. **Synthesis**: Generate a candidate assignment that satisfies known constraints
   2. **Verification**: Check if the candidate satisfies all specifications

If verification fails, the failure provides **constraints** that prune the next synthesis attempt. This process repeats until a correct assignment is found or synthesis becomes infeasible.

CeLoR adapts CEGIS for K8s manifest repair by:
   * Using **oracle failures** as constraint sources
   * Using **holes** to mark uncertain values in PatchTemplate
   * Using **custom synthesizer** with lexicographic enumeration
   * Supporting **multiple oracles** (policy, security, resource, schema)
   * Learning **constraints** from violation evidence

Key Concepts
------------

For definitions of key concepts (Constraint, Hole, HoleSpace, CandidateAssignments, Synthesizer, Verifier), see :doc:`holes_and_templates` and :doc:`constraints`.

Loop Workflow
-------------

The CEGIS loop executes the following steps in each iteration:

Step 1: Verify
~~~~~~~~~~~~~~

Run all oracles against the current artifact to collect violations.

**Oracles**
   * PolicyOracle (policy checks: replicas, labels, image tags)
   * SecurityOracle (security baseline: runAsNonRoot, etc.)
   * ResourceOracle (resource validation)
   * SchemaOracle (K8s schema validation)

**Output**
   * List of ``Violation`` objects with evidence and constraint hints

**Termination Check**
   * If no violations → **Success**, return repaired artifact
   * Otherwise → Continue to Step 2

**Component**: Oracle implementations in ``celor.k8s.oracles``

Step 2: Extract Constraints
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Extract constraints from violation evidence to prune the search space.

**Process**
   * Parse violation evidence for constraint hints
   * Extract ``forbid_value`` hints → create ``Constraint(type="forbidden_value", ...)``
   * Extract ``forbid_tuple`` hints → create ``Constraint(type="forbidden_tuple", ...)``
   * Combine with initial constraints (from Fix Bank if available)

**Output**
   * List of ``Constraint`` objects

**Example**

.. code-block:: python

   # Violation evidence
   evidence = ViolationEvidence(
       constraint_hints={"forbid_tuple": [("env", "prod"), ("replicas", 2)]}
   )
   
   # Extracted constraint
   constraint = Constraint(
       type="forbidden_tuple",
       holes=["env", "replicas"],
       values=("prod", 2)
   )

**Component**: ``celor.core.cegis.synthesizer.extract_constraints_from_violations()``

Step 3: Enumerate Candidates
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Systematically enumerate candidate assignments from HoleSpace.

**Process**
   * Initialize CandidateGenerator with HoleSpace and constraints
   * Enumerate candidates lexicographically (like counting: 0,0,0 → 0,0,1 → ...)
   * For each candidate:
     - Check if it violates any constraints
     - If violates → skip (pruning)
     - If valid → proceed to Step 4

**Example**

.. code-block:: python

   hole_space = {
       "env": {"staging", "prod"},
       "replicas": {2, 3, 4, 5}
   }
   constraints = [
       Constraint(type="forbidden_tuple", holes=["env", "replicas"], values=("prod", 2))
   ]
   
   generator = CandidateGenerator(hole_space, constraints)
   candidates = [
       {"env": "staging", "replicas": 2},  # Valid
       {"env": "staging", "replicas": 3},  # Valid
       {"env": "prod", "replicas": 2},     # Pruned (violates constraint)
       {"env": "prod", "replicas": 3},     # Valid
       # ... more candidates
   ]

**Component**: ``celor.core.synth.CandidateGenerator``

Step 4: Instantiate and Apply Patch
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Convert candidate assignment into concrete patch and apply to artifact.

**Process**
   * Instantiate PatchTemplate with candidate values (replace HoleRef with concrete values)
   * Apply patch to artifact using PatchDSL
   * Materialize to temporary location for verification

**Example**

.. code-block:: python

   # Template with holes
   template = PatchTemplate(ops=[
       PatchOp("EnsureReplicas", {"replicas": HoleRef("replicas")})
   ])
   
   # Candidate assignment
   candidate = {"replicas": 3}
   
   # Instantiate
   patch = instantiate(template, candidate)
   # Result: Patch(ops=[PatchOp("EnsureReplicas", {"replicas": 3})])
   
   # Apply to artifact
   repaired_artifact = artifact.apply_patch(patch)

**Component**: ``celor.core.template.instantiate()``, ``celor.k8s.patch_dsl.apply_k8s_patch()``

Step 5: Re-verify
~~~~~~~~~~~~~~~~~

Check if repaired artifact passes all oracles.

**Process**
   * Run all oracles against repaired artifact
   * Collect violations
   * If no violations → **SUCCESS**
   * If violations found → extract new constraints and update generator

**Termination Conditions**
   * **SUCCESS**: All oracles pass → Return repaired artifact
   * **UNSAT**: All candidates exhausted → No valid repair found
   * **TIMEOUT**: Time limit reached → Return best candidate so far
   * **BUDGET**: Max candidates reached → Return best candidate so far

**Component**: ``celor.core.cegis.verifier.verify()``, ``celor.core.cegis.synthesizer.synthesize()``

CEGIS Loop Diagram
------------------

.. code-block:: text

   ┌─────────────────────┐
   │  Start: Artifact    │
   │  + PatchTemplate    │
   │  + HoleSpace        │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │  1. Verify          │
   │  Run Oracles        │
   └──────────┬──────────┘
              │
              ├─ No Violations → SUCCESS
              │
              ├─ Has Violations
              │
              ▼
   ┌─────────────────────┐
   │  2. Extract         │
   │  Constraints        │
   │  (from evidence)    │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │  3. Enumerate       │
   │  Candidates         │
   │  (with pruning)     │
   └──────────┬──────────┘
              │
              ├─ All exhausted → UNSAT
              │
              ├─ Valid candidate
              │
              ▼
   ┌─────────────────────┐
   │  4. Instantiate     │
   │  & Apply Patch      │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │  5. Re-verify       │
   │  Run Oracles        │
   └──────────┬──────────┘
              │
              ├─ No Violations → SUCCESS
              │
              ├─ Has Violations
              │
              ▼
   ┌─────────────────────┐
   │  Learn New          │
   │  Constraints        │
   └──────────┬──────────┘
              │
              └─ Loop Back to Step 3

Example Iteration
-----------------

**Initial State**

.. code-block:: yaml

   # deployment.yaml (non-compliant)
   spec:
     replicas: 2  # Violation: prod requires 3-5
     template:
       metadata:
         labels:
           env: prod

**Template and HoleSpace**

.. code-block:: python

   template = PatchTemplate(ops=[
       PatchOp("EnsureReplicas", {"replicas": HoleRef("replicas")})
   ])
   hole_space = {"replicas": {2, 3, 4, 5}}

**Iteration 1**

1. **Verify**: Run PolicyOracle → violation: "prod requires 3-5 replicas"

2. **Extract Constraints**: 
   - Constraint: ``forbidden_tuple(env="prod", replicas=2)``

3. **Enumerate Candidates**:
   - Candidate 1: ``{"replicas": 2}`` → Pruned (violates constraint)
   - Candidate 2: ``{"replicas": 3}`` → Valid

4. **Instantiate & Apply**: 
   - Patch: ``EnsureReplicas(replicas=3)``
   - Apply to manifest

5. **Re-verify**: Run PolicyOracle → 0 violations

6. **Success**: Return repaired manifest

**Final State**

.. code-block:: yaml

   # deployment.yaml (repaired)
   spec:
     replicas: 3  # Fixed
     template:
       metadata:
         labels:
           env: prod

Performance Considerations
--------------------------

For performance considerations including HoleSpace size, constraint pruning, and Fix Bank warm-start, see :doc:`index`.

Next Steps
----------

* Learn about :doc:`constraints` for constraint learning details
* Understand :doc:`holes_and_templates` for holes and PatchTemplate
* Explore :doc:`../../reference/api_reference/core` for API details
* Try the :doc:`../../example/repair_workflow` tutorial

