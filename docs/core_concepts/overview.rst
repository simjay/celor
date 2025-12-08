Overview
========

What is CeLoR?
-----------------

CeLoR (CEGIS-in-the-Loop Reasoning) is an inference-time verification and repair system for LLM-generated Kubernetes manifests. It addresses a fundamental challenge in using LLMs for configuration generation: **how to verify and repair generated configurations efficiently while minimizing token usage and preserving privacy**.

Motivation
----------

Traditional LLM-based configuration repair approaches face several challenges:

**High Token Costs**
   Iterative repair loops that call the LLM multiple times can consume thousands of tokens, making them expensive and slow.

**Non-Determinism**
   LLM outputs vary across runs, making it difficult to reproduce results or debug failures.

**Privacy Concerns**
   Sending sensitive configurations to external APIs repeatedly raises security and compliance issues.

**Lack of Formal Guarantees**
   LLMs can generate plausible-looking configurations that still fail policy checks or violate specifications.

Goals
-----

CeLoR is designed to address these challenges with the following goals:

**Minimal Token Usage**
   Use minimal LLM calls (typically 1) to generate parametric repair templates with holes. Then synthesize concrete values locally using a custom synthesizer.

**Deterministic Repair**
   Given the same inputs and oracles, produce identical patches across multiple runs.

**Privacy-Preserving**
   Execute all verification and synthesis iterations locally. Only the LLM template generation call sends data externally.

**Formal Correctness**
   Use custom synthesizer with constraint learning to guarantee that repairs satisfy all oracle checks and learned constraints.

**Multi-Oracle Support**
   Verify artifacts against multiple criteria: K8s schema, policy rules, security baselines, and resource constraints.

**Domain Agnostic**
   Provide a core architecture that can be extended to Kubernetes manifests, Python code, JSON, and other artifact types.

How It Works
------------

CeLoR uses a **two-phase architecture** that separates high-level structural reasoning from low-level value synthesis. For detailed architecture explanation, see :doc:`architecture`.

Key Concepts
------------

For detailed explanations of key terms and concepts, see :doc:`key_concepts`.

Use Cases
---------

CeLoR is designed for scenarios where:
   * You need to repair LLM-generated K8s manifests that fail policy checks
   * You want deterministic, reproducible repairs
   * You need to minimize LLM API costs
   * You have privacy or compliance requirements
   * You want formal guarantees that repairs satisfy all oracle checks
   * You need to verify manifests against multiple criteria (policy + security + resources + schema)

Example Workflow
----------------

For a complete walkthrough of the repair workflow, see :doc:`../example/repair_workflow`.

Next Steps
----------

* Learn about the :doc:`architecture` in detail
* Understand the :doc:`../cegis_layer/cegis_loop` workflow
* Explore :doc:`../cegis_layer/holes_and_templates` for synthesis details
* Try the :doc:`../getting_started` guide
