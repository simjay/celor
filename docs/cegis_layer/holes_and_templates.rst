Holes and Synthesis
===================

**Holes** are placeholders in PatchTemplate that mark uncertain values. **Synthesis** is the process of filling those holes with concrete values from HoleSpace that satisfy all constraints. This separation allows CeLoR to minimize LLM token usage while providing formal correctness guarantees.

What are Holes?
---------------

A **hole** is a placeholder in a PatchTemplate that indicates "a value goes here, but we're not sure which one yet."

Example Without Holes
~~~~~~~~~~~~~~~~~~~~~~

Traditional LLM repair might generate:

.. code-block:: yaml

   spec:
     replicas: 3  # LLM guesses exact value
     template:
       metadata:
         labels:
           env: production-us

**Problems**
   * LLM might guess wrong value
   * No guarantee the value satisfies all policies
   * Requires multiple LLM calls to iterate

Example With Holes
~~~~~~~~~~~~~~~~~~

CeLoR generates a parametric template:

.. code-block:: python

   template = PatchTemplate(ops=[
       PatchOp("EnsureReplicas", {"replicas": HoleRef("replicas")})
   ])
   hole_space = {"replicas": {3, 4, 5}}

**Benefits**
   * LLM focuses on structure (what operations), not exact values
   * Synthesis fills holes with provably correct values
   * Minimal LLM calls (typically 1)

Hole Syntax
-----------

Holes are represented using the ``HoleRef`` marker in PatchTemplate:

.. code-block:: python

   HoleRef("replicas")  # Simple hole reference
   HoleRef("env")        # Another hole

**Hole Metadata**

Each hole has:
   * ``name``: Unique identifier (e.g., "replicas", "env", "version")
   * ``HoleSpace``: Domain of possible values (e.g., ``{"replicas": {3, 4, 5}}``)

Hole Sources
------------

Holes come from three sources (Fix Bank, LLM, or Default). For details on how templates and holes are generated, see :doc:`../patch_generation_layer/template_generation`.

HoleSpace
---------

**HoleSpace** defines the domain of possible values for each hole.

Example
~~~~~~~

.. code-block:: python

   hole_space = {
       "env": {"production-us"},
       "team": {"payments"},
       "tier": {"backend"},
       "replicas": {3, 4, 5},
       "version": {"prod-1.2.3", "prod-1.2.4", "prod-1.3.0"},
       "profile": {"medium", "large"},
       "priority_class": {"critical", "high-priority"}
   }

**Search Space Size**

Total candidates = ``len(hole1) * len(hole2) * ... * len(holeN)``

Example: 3 holes with 5, 3, 2 values = 5 × 3 × 2 = 30 candidates

**Designing HoleSpace**

* Keep spaces small (3-10 values per hole)
* Use domain knowledge (e.g., prod replicas: 3-5)
* Consider constraint pruning (constraints reduce effective space)

Synthesis
---------

**Synthesis** is the process of enumerating candidates from HoleSpace and finding one that satisfies all constraints.

Custom Synthesizer
~~~~~~~~~~~~~~~~~~

CeLoR uses a **custom synthesizer** (not Sketch) that:
   * Enumerates candidates lexicographically (like counting)
   * Prunes candidates that violate constraints
   * Learns constraints from oracle failures

**Enumeration Order**

Candidates are enumerated like counting:

.. code-block:: python

   # HoleSpace: {"env": {0, 1}, "replicas": {0, 1, 2}}
   # Enumeration order:
   # 0. {"env": 0, "replicas": 0}
   # 1. {"env": 0, "replicas": 1}
   # 2. {"env": 0, "replicas": 2}
   # 3. {"env": 1, "replicas": 0}
   # 4. {"env": 1, "replicas": 1}
   # 5. {"env": 1, "replicas": 2}

**Constraint Pruning**

Constraints skip invalid candidates:

.. code-block:: python

   # Constraint: forbid_tuple(env=production-us, replicas=2)
   # Candidates:
   # {"env": "production-us", "replicas": 2} → Pruned (violates constraint)
   # {"env": "production-us", "replicas": 3} → Valid (proceed)

**Constraint Learning**

Constraints are learned from violation evidence. For details, see :doc:`constraints`.

Synthesis Workflow
------------------

The synthesis workflow involves enumerating candidates, instantiating patches, and verifying results. For the complete CEGIS loop workflow, see :doc:`cegis_loop`.

Example: Complete Synthesis
----------------------------

**Initial Manifest**

.. code-block:: yaml

   spec:
     replicas: 2  # Violation: production-us requires 3-5
     template:
       metadata:
         labels:
           env: production-usuction-us

**Template and HoleSpace**

.. code-block:: python

   template = PatchTemplate(ops=[
       PatchOp("EnsureReplicas", {"replicas": HoleRef("replicas")})
   ])
   hole_space = {"replicas": {2, 3, 4, 5}}

**Initial Verification**

.. code-block:: python

   violations = [
       Violation(
           id="policy.ENV_PROD_REPLICA_COUNT",
           evidence=ViolationEvidence(
               constraint_hints={"forbid_tuple": [("env", "production-us"), ("replicas", 2)]}
           )
       )
   ]

**Constraint Extraction**

.. code-block:: python

   constraints = [
       Constraint(
           type="forbidden_tuple",
           holes=["env", "replicas"],
           values=("production-us", 2)
       )
   ]

**Candidate Enumeration**

.. code-block:: python

   generator = CandidateGenerator(hole_space, constraints)
   
   # Candidate 1: {"replicas": 2}
   # → Pruned (violates constraint: production-us + replicas=2)
   
   # Candidate 2: {"replicas": 3}
   # → Valid, proceed

**Instantiate and Apply**

.. code-block:: python

   patch = instantiate(template, {"replicas": 3})
   # Result: Patch(ops=[PatchOp("EnsureReplicas", {"replicas": 3})])
   
   repaired_artifact = artifact.apply_patch(patch)

**Re-verify**

.. code-block:: python

   violations = oracle(repaired_artifact)
   # Result: [] (empty, all pass)

**Success**

Repaired manifest:

.. code-block:: yaml

   spec:
     replicas: 3  # Fixed
     template:
       metadata:
         labels:
           env: production-us

Advantages of Holes + Synthesis
--------------------------------

**Minimal Token Usage**
   LLM generates structure (operations), synthesis fills values locally

**Formal Correctness**
   Synthesized values are **guaranteed** to satisfy all constraints

**Determinism**
   Same inputs always produce same patches (unlike LLM sampling)

**Privacy**
   Synthesis happens locally, no manifest sent to external APIs during enumeration

**Composability**
   Multiple holes can be filled jointly (constraints can relate multiple holes)

**Debuggability**
   Clear separation between structural reasoning (LLM) and value synthesis (custom enumerator)

**Cross-Run Learning**
   Fix Bank stores successful patterns for reuse

Performance Considerations
---------------------------

For performance considerations including HoleSpace size, constraint pruning, and Fix Bank warm-start, see :doc:`index`.

Next Steps
----------

* Understand the :doc:`cegis_loop` workflow
* See the :doc:`../../example/repair_workflow` for hands-on walkthroughs
* Read the :doc:`../../reference/api_reference/core` for implementation details
