Fix Bank
========

Fix Bank enables cross-run learning by persisting successful repair patterns. It stores templates, hole spaces, learned constraints, and successful assignments for future reuse.

What is Fix Bank?
-----------------

Fix Bank is a persistent storage system (JSON file) that maps violation signatures to successful repair patterns. When similar violations are detected, the stored pattern is reused, leading to faster repairs.

**Key Benefits**:

* **Cross-Run Learning**: Reuse successful repair patterns across multiple runs
* **Team Knowledge Sharing**: Commit Fix Bank to git for team-wide learning
* **Speedup**: Constraint warm-starting can provide 3-10x speedup
* **Cost Reduction**: Eliminates LLM calls when Fix Bank hits

**How It Works**:

Fix Bank operates in two phases:

1. **Lookup**: When violations are detected, build a signature and lookup in Fix Bank

  - If match found (Fix Bank HIT): Reuse stored template, hole space, and constraints; skip LLM call
  - If no match (Fix Bank MISS): Use LLM or default template; proceed with normal synthesis
  
2. **Storage**: After successful synthesis, store the pattern for future reuse

Storage Format
--------------

Fix Bank entries are stored as JSON with the following structure:

.. code-block:: json

   {
     "signature": {
       "failed_oracles": ["policy", "security"],
       "error_codes": ["ENV_PROD_REPLICA_COUNT"],
       "context": {"app": "payments-api", "env": "production-us"}
     },
     "template": {
       "ops": [
         {"op": "EnsureReplicas", "args": {"replicas": {"$hole": "replicas"}}}
       ]
     },
     "hole_space": {
       "replicas": [3, 4, 5]
     },
     "learned_constraints": [
       {
         "type": "forbidden_tuple",
         "data": {"holes": ["env", "replicas"], "values": ["production-us", 2]}
       }
     ],
     "successful_assignment": {"replicas": 3},
     "metadata": {
       "success_count": 1,
       "candidates_tried": 1,
       "first_used": "2024-01-15T10:30:00Z",
       "last_used": "2024-01-15T10:30:00Z"
     }
   }

**Fields**:

* **signature**: Fingerprint of violations (see Signature Matching below)
* **template**: PatchTemplate with holes that was used
* **hole_space**: Domain of possible values for each hole
* **learned_constraints**: All constraints learned during synthesis
* **successful_assignment**: The candidate assignment that satisfied all oracles
* **metadata**: Usage statistics and timestamps

**File Location**: ``.celor-fixes.json`` in current directory (configurable)

When a Fix Bank entry is reused, it is updated:
  - Success count is incremented
  - Last used timestamp is updated
  - Constraints are merged with new constraints learned in this run
  - This allows Fix Bank entries to improve over time

Signature Matching
------------------

Signatures are fingerprints of oracle failures that identify similar problems. They enable Fix Bank to match new violations to stored patterns.

**Signature Components**:

.. code-block:: python

   signature = {
       "failed_oracles": ["policy", "security"],
       "error_codes": ["ENV_PROD_REPLICA_COUNT", "NO_RUN_AS_NON_ROOT"],
       "context": {"app": "payments-api", "env": "production-us"}
   }

* **failed_oracles**: Names of oracles that detected violations
* **error_codes**: Specific error codes from violations (from ``violation.error_code``)
* **context**: Optional artifact context (app name, environment, etc.)

**Matching Process**:

1. Build signature from current violations
2. Lookup in Fix Bank (exact match on signature)
3. If match found: Reuse stored template, hole space, and constraints
4. If no match: Use LLM or default template

**Matching Properties**:

* **Conservative**: Signatures are exact matches (may have false negatives)
* **Context Flexibility**: Context fields are optional (allows artifact variations)
* **Error Code Precision**: Error codes provide fine-grained matching

Counterexample to Fix Bank
---------------------------

When the CEGIS Layer learns constraints from counterexamples (violations), these constraints are stored in Fix Bank and reused in future runs.

**Constraint Storage**:

After successful synthesis, all learned constraints are stored in the Fix Bank entry:

.. code-block:: json

   "learned_constraints": [
     {
       "type": "forbidden_value",
       "data": {"hole": "replicas", "value": 1}
     },
     {
       "type": "forbidden_tuple",
       "data": {"holes": ["env", "replicas"], "values": ["production-us", 2]}
     }
   ]

**Constraint Reuse**:

When a Fix Bank entry is reused:
  1. Stored constraints are loaded as ``initial_constraints``
  2. These constraints prune the search space immediately
  3. New constraints learned in this run are merged back into the entry
  4. This enables progressive refinement of constraints over time

**Example Flow**:

1. **Run 1**: Violations detected → LLM generates template → CEGIS learns constraints → Fix Bank stores pattern
2. **Run 2**: Similar violations → Fix Bank HIT → Load stored constraints → CEGIS starts with warm constraints → Faster synthesis
3. **Run 3**: Same violations → Fix Bank HIT → Load merged constraints (from Run 1 + Run 2) → Even faster synthesis

**Benefits**:

* **Warm-Start**: Constraints immediately prune invalid candidates
* **Progressive Learning**: Constraints improve over multiple runs
* **Cross-Run Knowledge**: Constraints learned in one run benefit future runs

Next Steps
----------

* Learn about :doc:`../patch_generation_layer/template_generation` for how Fix Bank fits into template generation
* Understand :doc:`../cegis_layer/constraints` for constraint learning and reuse
* Explore :doc:`../reference/api_reference/core` for Fix Bank API details
