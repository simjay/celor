Key Concepts and Terms
=======================

This document provides detailed explanations of key concepts and terms used throughout CeLoR for K8s manifest repair. For quick definitions, see :doc:`../../reference/glossary`.

Architecture Concepts
---------------------

Template Generation vs Synthesis
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

CeLoR uses a two-phase architecture that separates high-level structural reasoning from low-level value synthesis. For details, see :doc:`architecture`, :doc:`../patch_generation_layer/index`, and :doc:`../cegis_layer/index`.

Violation
~~~~~~~~~

A **violation** is a standardized representation of a failure detected by an oracle.

**What it represents**:
   * Policy violations (PolicyOracle)
   * Security issues (SecurityOracle)
   * Resource problems (ResourceOracle)
   * Schema errors (SchemaOracle)

**Structure**:
   * ``id``: Unique identifier (e.g., ``"policy.ENV_PROD_REPLICA_COUNT"``)
   * ``message``: Human-readable description
   * ``evidence``: Domain-specific data with constraint hints

**Evidence Contents**:
   * Constraint hints: ``forbid_value``, ``forbid_tuple``
   * Location information (file, line)
   * Context (e.g., current values that caused violation)

**Usage in CeLoR**:
   Violations are produced by oracles and then used to extract constraints for synthesis. They provide rich context about failures that helps with constraint learning.

For API details, see :doc:`../../reference/api_reference/core`.

CEGIS Loop Components
---------------------

For implementation details about the verifier and synthesizer components, see :doc:`../reference/api_reference/core`.

Core Data Structures
--------------------

PatchTemplate
~~~~~~~~~~~~~

A **PatchTemplate** is a partially specified patch containing operations with holes. For details, see :doc:`../cegis_layer/holes_and_templates`.

HoleSpace
~~~~~~~~~

A **HoleSpace** defines the domain of possible values for each hole. For details, see :doc:`../cegis_layer/holes_and_templates`.

CandidateAssignments
~~~~~~~~~~~~~~~~~~~~

A **CandidateAssignments** is a specific choice of values for all holes. For details, see :doc:`../cegis_layer/holes_and_templates`.

Constraint
~~~~~~~~~~

A **Constraint** is a learned restriction on hole values. For details, see :doc:`../cegis_layer/constraints`.

Fix Bank
~~~~~~~~

A **Fix Bank** is persistent storage for successful repair patterns, enabling cross-run learning. For details, see :doc:`fix_bank`.

PatchDSL
--------

**PatchDSL** (Patch Domain-Specific Language) defines structured edit operations for K8s manifests. For details, see :doc:`../patch_generation_layer/patch_dsl`.

Oracles
-------

**Oracles** are verification functions that check artifacts and return violations. For details, see :doc:`oracles`.

Next Steps
----------

* Understand the :doc:`architecture` workflow
* See the example for hands-on walkthroughs
* Read the API reference for implementation details
