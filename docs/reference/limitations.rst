Known Limitations
=================

This document describes known limitations of CeLoR for K8s manifest repair and potential workarounds.

Synthesis Limitations
---------------------

HoleSpace Size
~~~~~~~~~~~~~~

**Limitation**: Synthesis search space grows exponentially with number of holes and values.

**Impact**: Large HoleSpaces (e.g., 5 holes with 10 values each = 100,000 candidates) may timeout or exceed budget.

**Workaround**: 
    - Keep HoleSpaces small (3-10 values per hole)
    - Use domain knowledge to narrow values
    - Use Fix Bank to reuse learned constraints

Constraint Complexity
~~~~~~~~~~~~~~~~~~~~~

**Limitation**: Constraints are limited to ``forbidden_value`` and ``forbidden_tuple`` types.

**Impact**: Complex constraints (ranges, inequalities, etc.) are not directly supported.

**Workaround**: 
    - Encode constraints in HoleSpace (e.g., only include valid values)
    - Use multiple ``forbidden_tuple`` constraints for complex relationships

Enumeration Order
~~~~~~~~~~~~~~~~~

**Limitation**: Candidates are enumerated lexicographically (not heuristically ordered).

**Impact**: May try many invalid candidates before finding valid ones.

**Workaround**: 
    - Use Fix Bank to warm-start with learned constraints
    - Design HoleSpace with most likely values first (if ordering matters)

Timeout and Budget
~~~~~~~~~~~~~~~~~~

**Limitation**: Synthesis may timeout or hit budget limits for large search spaces.

**Impact**: Repair may fail even if valid solution exists.

**Workaround**:
    - Increase ``timeout_seconds`` and ``max_candidates``
    - Reduce HoleSpace size
    - Use Fix Bank for faster convergence

Oracle Limitations
------------------

Policy Coverage
~~~~~~~~~~~~~~~

**Limitation**: PolicyOracle implements a limited set of custom policies.

**Impact**: May not catch all policy violations.

**Workaround**: 
    - Extend PolicyOracle with custom checks
    - Use external tools (Checkov) for comprehensive policy coverage

Schema Validation
~~~~~~~~~~~~~~~~~

**Limitation**: SchemaOracle requires kubectl or kubernetes-validate (optional).

**Impact**: Schema validation may be skipped if tools unavailable.

**Workaround**: 
    - Install ``kubernetes-validate``: ``pip install kubernetes-validate``
    - Or ensure ``kubectl`` is in PATH

Security Checks
~~~~~~~~~~~~~~~

**Limitation**: SecurityOracle implements basic security baseline only.

**Impact**: May not catch all security issues.

**Workaround**: 
    - Extend SecurityOracle with additional checks
    - Use external tools (Checkov) for comprehensive security coverage

PatchDSL Limitations
--------------------

Operation Coverage
~~~~~~~~~~~~~~~~~~

**Limitation**: PatchDSL supports 6 operations (EnsureLabel, EnsureImageVersion, etc.).

**Impact**: Complex repairs may require operations not in PatchDSL.

**Workaround**: 
    - Extend PatchDSL with new operations
    - Use multiple operations in sequence

YAML Preservation
~~~~~~~~~~~~~~~~~~

**Limitation**: YAML formatting may change slightly after patch application.

**Impact**: Comments or formatting may be lost.

**Workaround**: 
    - Uses ``ruamel.yaml`` for better preservation
    - Most formatting is preserved, but not guaranteed

Fix Bank Limitations
---------------------

Signature Matching
~~~~~~~~~~~~~~~~~~

**Limitation**: Signature matching is based on oracle names and error codes.

**Impact**: May miss similar violations with different error codes.

**Workaround**: 
    - Signature matching is conservative (may have false negatives)
    - Can manually inspect Fix Bank entries

Storage Format
~~~~~~~~~~~~~~

**Limitation**: Fix Bank uses JSON (not versioned or schema-validated).

**Impact**: Manual edits may corrupt Fix Bank.

**Workaround**: 
    - Don't manually edit ``.celor-fixes.json``
    - Use Fix Bank API for updates

LLM Limitations
---------------

API Dependency
~~~~~~~~~~~~~~

**Limitation**: LLM integration requires OpenAI API key and network access.

**Impact**: LLM features unavailable without API key.

**Workaround**: 
    - Use ``--no-llm`` flag to disable
    - Use default templates instead

Response Parsing
~~~~~~~~~~~~~~~~

**Limitation**: LLM responses must be valid JSON matching expected schema.

**Impact**: Malformed responses cause fallback to default template.

**Workaround**: 
    - LLM adapter handles parsing errors gracefully
    - Falls back to default template on failure

Cost
~~~~

**Limitation**: LLM API calls incur costs.

**Impact**: Frequent repairs may be expensive.

**Workaround**: 
    - Use Fix Bank to minimize LLM calls
    - Use ``--no-llm`` for testing

Next Steps
----------

* See :doc:`usage_guide` for solutions to common issues
* Explore :doc:`oracle_system` for oracle details
