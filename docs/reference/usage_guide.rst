Usage Guide
===========

This guide covers configuration, CLI usage, and common issues for CeLoR.

Configuration
-------------

Configuration File
~~~~~~~~~~~~~~~~~~

CeLoR uses ``config.json`` in the project root:

.. code-block:: json

   {
     "openai": {
       "api_key": "sk-...",
       "model": "gpt-4",
       "temperature": 0.7,
       "timeout": 30.0
     },
     "cegis": {
       "max_iters": 5,
       "max_candidates": 1000,
       "timeout_seconds": 60.0
     }
   }

OpenAI Configuration
~~~~~~~~~~~~~~~~~~~~

**openai.api_key** (str, required for LLM)
   OpenAI API key. Set in ``config.json`` only (not environment variables).

**openai.model** (str, default: "gpt-4")
   LLM model for template generation. Examples: ``"gpt-4"``, ``"gpt-4-turbo"``

**openai.temperature** (float, default: 0.7)
   Sampling temperature (0.0 = deterministic, 1.0 = creative)

**openai.timeout** (float, default: 30.0)
   Request timeout in seconds

CEGIS Configuration
~~~~~~~~~~~~~~~~~~~

**cegis.max_iters** (int, default: 5)
   Maximum CEGIS loop iterations

**cegis.max_candidates** (int, default: 1000)
   Maximum candidates to try during synthesis

**cegis.timeout_seconds** (float, default: 60.0)
   Synthesis timeout in seconds

Configuration Priority
~~~~~~~~~~~~~~~~~~~~~~

1. Command-line arguments (highest)
2. ``config.json`` file
3. Default values (lowest)

CLI Commands
------------

Repair Command
~~~~~~~~~~~~~~

Repair a Kubernetes deployment manifest:

.. code-block:: bash

   celor repair <deployment.yaml> --out <output_dir>

**Options**:

- ``--out DIR``: Output directory for repaired manifest (required)
- ``--max-candidates N``: Maximum candidates to try (default: 1000)
- ``--timeout SECONDS``: Synthesis timeout (default: 60.0)
- ``--max-iters N``: Maximum CEGIS iterations (default: 5)
- ``--fixbank PATH``: Fix Bank file path (default: ``.celor-fixes.json``)
- ``--no-fixbank``: Disable Fix Bank
- ``--openai-model MODEL``: Override OpenAI model
- ``--no-llm``: Disable LLM adapter
- ``-v, --verbose``: Enable verbose output

**Example**:

.. code-block:: bash

   celor repair deployment.yaml --out fixed/ --max-candidates 500

Demo Command
~~~~~~~~~~~~

Run demo with example manifest:

.. code-block:: bash

   celor demo [--out <output_dir>]

Common Issues
-------------

Synthesis Timeout
~~~~~~~~~~~~~~~~~~

**Problem**: Synthesis times out before finding repair

**Solutions**:
   - Reduce HoleSpace size (fewer values per hole)
   - Increase timeout: ``--timeout 120.0``
   - Use Fix Bank to reuse learned constraints
   - Reduce ``--max-candidates``

No Valid Repair Found (UNSAT)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Problem**: Repair returns "unsat" status

**Solutions**:
   - Verify HoleSpace contains valid values
   - Check for conflicting oracle requirements
   - Inspect learned constraints: ``metadata['constraints']``
   - Expand HoleSpace with more values

LLM Integration Issues
~~~~~~~~~~~~~~~~~~~~~~~

**Problem**: LLM adapter fails

**Solutions**:
   - Verify ``config.json`` has valid ``openai.api_key``
   - Check API quota/limits
   - Use ``--no-llm`` to fall back to default template

YAML Parsing Errors
~~~~~~~~~~~~~~~~~~~

**Problem**: YAML parsing failures

**Solutions**:
   - Validate YAML syntax
   - Check file encoding (UTF-8)
   - Verify proper indentation (2 spaces)

Next Steps
----------

* Explore :doc:`oracle_system` for oracle details
* See :doc:`limitations` for known limitations
* Read :doc:`api_reference/core` for API details

