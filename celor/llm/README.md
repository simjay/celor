# LLM Module Architecture

This module provides LLM integration for automatic PatchTemplate generation.

## Structure

```
celor/llm/
  ├── clients/         # Layer 1: Vendor API wrappers
  │   └── openai.py   # OpenAI API client
  │
  ├── adapter.py      # Layer 2: Domain-agnostic orchestrator
  │
  └── prompts/        # Layer 3: Domain-specific prompt logic
      └── k8s.py      # K8s-specific prompts
```

## Layer Responsibilities

### Layer 1: `clients/` - Vendor API Wrappers

**Purpose:** Pure API communication, zero domain knowledge

- **`openai.py`**: OpenAI API wrapper
  - Loads API key and model from `config.json`
  - Handles timeouts and error messages
  - No CeLoR or domain knowledge

**Characteristics:**
- ✅ Vendor-specific (knows OpenAI APIs)
- ✅ Domain-agnostic (no CeLoR/K8s knowledge)
- ✅ Reusable outside CeLoR

### Layer 2: `adapter.py` - Orchestrator

**Purpose:** Routes to correct prompt builder, parses responses

```python
from celor.llm.adapter import LLMAdapter

# Auto-loads from config.json
adapter = LLMAdapter()
template, hole_space = adapter.propose_template(
    artifact, violations, domain="k8s"
)
```

**Characteristics:**
- ✅ Vendor-agnostic (works with any client)
- ✅ Domain-aware (routes to k8s.py, python.py, etc.)
- ✅ Handles parsing and error recovery
- ✅ Auto-loads configuration from config.json

### Layer 3: `prompts/` - Domain Logic

**Purpose:** All domain knowledge lives here

- **`k8s.py`**: Knows K8s PatchDSL, manifest structure, policies
- **`python.py`**: (Future) Knows Python PatchDSL, AST patterns

**Characteristics:**
- ✅ Domain-specific (K8s experts write k8s.py)
- ✅ Client-agnostic (just builds prompt strings)
- ✅ Easy to extend (add new domains)

## Configuration

All configuration is loaded from `config.json`:

```json
{
  "openai": {
    "api_key": "sk-...",
    "model": "gpt-4"
  }
}
```

The `LLMAdapter` and `OpenAIClient` automatically load these values. You can also override them explicitly:

```python
# Override model
adapter = LLMAdapter(model="gpt-4-turbo")

# Override API key (rarely needed)
adapter = LLMAdapter(api_key="sk-...")
```

## Usage

### Basic Usage

```python
from celor.llm.adapter import LLMAdapter
from celor.k8s.artifact import K8sArtifact
from celor.k8s.oracles import PolicyOracle

# Auto-loads from config.json
adapter = LLMAdapter()

artifact = K8sArtifact.from_file("deployment.yaml")
oracles = [PolicyOracle()]

# Get violations
violations = []
for oracle in oracles:
    violations.extend(oracle(artifact))

# Generate template
template, hole_space = adapter.propose_template(
    artifact, violations, domain="k8s"
)

# Use template in synthesis
from celor.core.controller import repair_artifact
repaired, metadata = repair_artifact(
    artifact=artifact,
    template=template,
    hole_space=hole_space,
    oracles=oracles
)
```

### Auto-Creation in Controller

The controller automatically creates an LLMAdapter if:
1. `llm_adapter` parameter is `None`
2. `config.json` has an OpenAI API key
3. Fix Bank misses (no stored template)

```python
# LLMAdapter auto-created from config.json
repaired, metadata = repair_artifact(
    artifact=artifact,
    oracles=oracles,
    # llm_adapter=None by default - will auto-create
)
```

### CLI Integration

The CLI automatically uses LLM if `config.json` has an API key:

```bash
# LLM adapter auto-created from config.json
celor repair deployment.yaml --out fixed/

# Override model
celor repair deployment.yaml --out fixed/ --openai-model gpt-4-turbo
```

## Error Handling

### Missing API Key

If `config.json` doesn't have an API key, you'll get a clear error:

```
ValueError: OpenAI API key required. Set in config.json: {'openai': {'api_key': 'sk-...'}}
```

### API Errors

The client provides clear error messages for:
- **Timeout**: Request took too long (default 30 seconds)
- **Authentication**: Invalid API key
- **API errors**: Rate limits, server errors, etc.

## Testing

Tests use `unittest.mock` to mock OpenAI API calls (no real API calls):

```python
from unittest.mock import patch, MagicMock

@patch('celor.llm.clients.openai.OpenAI')
def test_llm_adapter(mock_openai_class):
    # Setup mock response
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps({
        "template": {"ops": [...]},
        "hole_space": {...}
    })
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai_class.return_value = mock_client
    
    # Test adapter
    adapter = LLMAdapter()
    template, holes = adapter.propose_template(...)
```

## Requirements

- **OpenAI API key**: Required (set in `config.json`)
- **openai package**: `pip install openai>=1.0.0`
- **config.json**: Must have `openai.api_key` and optionally `openai.model`

## Architecture Benefits

- ✅ Easy to add vendors (clients/anthropic.py)
- ✅ Easy to add domains (prompts/python.py)
- ✅ Clean separation of concerns
- ✅ Testable at each layer
- ✅ No mock clients - use unittest.mock for tests
