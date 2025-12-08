CeLoR Architecture
==================

This document explains CeLoR's two-phase architecture that separates high-level structural reasoning from low-level value synthesis.

Overview
--------

CeLoR uses a **two-phase architecture** that separates high-level structural reasoning from low-level value synthesis:

1. **Phase 1 (Template Generation)**: Generate PatchTemplate with holes from Fix Bank, LLM, or default
2. **Phase 2 (Synthesis)**: Local iterative CEGIS loop that fills holes using custom synthesizer with constraint learning

The key insight is that LLMs excel at **structure** (what operations to use, where to place holes) but struggle with **concrete values** (exact values). Custom synthesis excels at finding concrete values that satisfy formal constraints (oracle checks).

Complete Flow Diagram
---------------------

.. code-block:: text

   ┌─────────────────────────────────────────────────────────────┐
   │                    START: Broken Manifest                   │
   │              replicas: 2, missing labels, etc.              │
   └───────────────────────┬─────────────────────────────────────┘
                           │
                           ▼
   ┌─────────────────────────────────────────────────────────────┐
   │              PHASE 1: Template Generation                   │
   │                                                             │
   │  Priority: Fix Bank > LLM > Default                         │
   │                                                             │
   │  Input:  Artifact + Violations                              │
   │  Process: Generate PatchTemplate with holes                 │
   │  Output: PatchTemplate + HoleSpace                          │
   │                                                             │
   │  Example: EnsureReplicas(replicas=HoleRef("replicas"))      │
   │           HoleSpace: {"replicas": {3, 4, 5}}                │
   └───────────────────────┬─────────────────────────────────────┘
                           │
                           ▼
   ┌─────────────────────────────────────────────────────────────┐
   │              PHASE 2: Synthesis (CEGIS Loop)                │
   │              (Iterative, Local, No Network)                 │
   └───────────────────────┬─────────────────────────────────────┘
                           │
                           │
        ┌──────────────────┴────────────────────┐
        │                                       │
        │  ┌────────────────────────────────┐   │
        │  │  ITERATION N                   │   │
        │  └──────────┬─────────────────────┘   │
        │             │                         │
        │             ▼                         │
        │  ┌────────────────────────────────┐   │
        │  │ Step 1: VERIFY                 │   │
        │  │ Run all oracles                │   │
        │  │ → List[Violation]              │   │
        │  └──────────┬─────────────────────┘   │
        │             │                         │
        │             ├─ No Violations ─────────┼─► SUCCESS
        │             │                         │
        │             ├─ Has Violations         │
        │             │                         │
        │             ▼                         │
        │  ┌────────────────────────────────┐   │
        │  │ Step 2: EXTRACT CONSTRAINTS    │   │
        │  │ From violation evidence        │   │
        │  │ → List[Constraint]             │   │
        │  └──────────┬─────────────────────┘   │
        │             │                         │
        │             ▼                         │
        │  ┌────────────────────────────────┐   │
        │  │ Step 3: ENUMERATE CANDIDATES   │   │
        │  │ CandidateGenerator             │   │
        │  │ → CandidateAssignments         │   │
        │  └──────────┬─────────────────────┘   │
        │             │                         │
        │             ▼                         │
        │  ┌────────────────────────────────┐   │
        │  │ Step 4: INSTANTIATE & APPLY    │   │
        │  │ instantiate() + apply_patch()  │   │
        │  │ → Updated Artifact             │   │
        │  └──────────┬─────────────────────┘   │
        │             │                         │
        │             └───────────┬─────────────┘
        │                         │
        │                         │
        │             ┌───────────┴─────────────┐
        │             │                         │
        │             ├─ Max Candidates/Timeout ┼─► UNSAT/TIMEOUT
        │             │                         │
        │             └─ Loop Back to Step 1 ───┘
        │
        │
        ▼
   ┌─────────────────────────────────────────────────────────────┐
   │                    END: Repaired Manifest                   │
   │                  (All oracles pass)                         │
   └─────────────────────────────────────────────────────────────┘

Phase 1: Template Generation
----------------------------

The template generation phase creates a PatchTemplate with holes from Fix Bank, LLM, or default sources. For details, see :doc:`../patch_generation_layer/index` and :doc:`../patch_generation_layer/template_generation`.

Phase 2: Synthesis (CEGIS Loop)
--------------------------------

The synthesis phase executes a local iterative CEGIS loop that fills holes using custom enumeration. For details, see :doc:`../cegis_layer/index`.


Next Steps
----------

* Learn about :doc:`../patch_generation_layer/template_generation` for Phase 1 details
* Understand :doc:`../cegis_layer/index` for Phase 2 details
* Explore :doc:`key_concepts` for key terms and definitions
* Read :doc:`../reference/api_reference/core` for implementation details

