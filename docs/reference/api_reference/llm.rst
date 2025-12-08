LLM API
=======

The LLM API provides integration with language models for automatic PatchTemplate and HoleSpace generation.

LLM Adapter
-----------

Domain-agnostic orchestrator for LLM integration.

celor.llm.adapter
~~~~~~~~~~~~~~~~~

.. automodule:: celor.llm.adapter
   :members:
   
   :show-inheritance:

**Key Methods**:

* ``propose_template(artifact, violations, domain)``: Generate PatchTemplate and HoleSpace from violations

**Example**:

.. code-block:: python

   from celor.llm.adapter import LLMAdapter
   from celor.k8s.artifact import K8sArtifact
   
   adapter = LLMAdapter()  # Auto-loads from config.json
   template, hole_space = adapter.propose_template(
       artifact=artifact,
       violations=violations,
       domain="k8s"
   )

LLM Clients
-----------

Vendor-specific API wrappers.

celor.llm.clients.openai
~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: celor.llm.clients.openai
   :members:
   
   :show-inheritance:

**Key Methods**:

* ``chat(messages, response_format, temperature)``: Send chat completion request

**Configuration**:

Loads API key and model from ``config.json``:

.. code-block:: json

   {
     "openai": {
       "api_key": "sk-...",
       "model": "gpt-4",
       "temperature": 0.7,
       "timeout": 30.0
     }
   }

**Example**:

.. code-block:: python

   from celor.llm.clients.openai import OpenAIClient
   
   client = OpenAIClient()  # Auto-loads from config.json
   response = client.chat(
       messages=[{"role": "user", "content": "..."}],
       response_format={"type": "json_object"}
   )

K8s Prompts
-----------

Domain-specific prompt building for K8s.

celor.llm.prompts.k8s
~~~~~~~~~~~~~~~~~~~~~

.. automodule:: celor.llm.prompts.k8s
   :members:
   
   :show-inheritance:

**Key Functions**:

* ``build_k8s_prompt(artifact, violations)``: Build comprehensive prompt for K8s manifest repair

Example Usage
-------------

Automatic Template Generation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from celor.llm.adapter import LLMAdapter
   from celor.k8s.artifact import K8sArtifact
   from celor.k8s.oracles import PolicyOracle
   
   # Load artifact and detect violations
   artifact = K8sArtifact.from_file("deployment.yaml")
   oracle = PolicyOracle()
   violations = oracle(artifact)
   
   # Generate template from LLM
   adapter = LLMAdapter()  # Auto-loads from config.json
   template, hole_space = adapter.propose_template(
       artifact=artifact,
       violations=violations,
       domain="k8s"
   )

Integration with Controller
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The controller auto-creates LLMAdapter if API key is in config.json:

.. code-block:: python

   from celor.core.controller import repair_artifact
   
   # LLM adapter auto-created if config.json has openai.api_key
   repaired, metadata = repair_artifact(
       artifact=artifact,
       oracles=oracles
   )
   
   # Check if LLM was used
   print(f"LLM calls: {metadata.get('llm_calls', 0)}")

Configuration
-------------

LLM configuration is loaded from ``config.json``:

.. code-block:: json

   {
     "openai": {
       "api_key": "sk-...",
       "model": "gpt-4",
       "temperature": 0.7,
       "timeout": 30.0
     }
   }

**Priority**:
1. Explicit parameters (if provided to LLMAdapter)
2. config.json values
3. Defaults (model="gpt-4", temperature=0.7, timeout=30.0)

**Error Handling**:
- Missing API key raises ``ValueError`` with clear message
- API failures are logged and handled gracefully
- Timeout errors are caught and reported

Next Steps
----------

* See :doc:`../../patch_generation_layer/template_generation` to understand LLM integration
* Explore :doc:`core` for controller API details
* Try the :doc:`../../example/repair_workflow` tutorial
