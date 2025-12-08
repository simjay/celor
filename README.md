# CeLoR: CEGIS-in-the-Loop Reasoning

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Inference-time verification and repair for LLM-generated Kubernetes manifests**

CeLoR transforms LLM-generated Kubernetes manifests into verified, compliant configurations through a two-phase architecture: LLM calls generate parametric repair templates with holes, then a local CEGIS (Counterexample-Guided Inductive Synthesis) loop with a custom synthesizer fills those holes—no additional LLM tokens required during synthesis.

## Features

- **Minimal Token Usage**: LLM generates repair templates with holes (typically 1 call)
- **Custom Synthesizer**: Lexicographic candidate enumeration with constraint pruning
- **Privacy-Preserving**: All synthesis happens locally on your machine
- **Deterministic**: Identical inputs produce identical patches
- **Multi-Oracle**: Supports K8s schema, policy, security, and resource oracles
- **Fix Bank**: Cross-run learning and team knowledge sharing
- **Domain-Agnostic Core**: Extensible architecture for K8s, Python, JSON, and more

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/celor.git
cd celor

# Install CeLoR
pip install -e .

# Optional: Install enhanced oracle support
pip install celor[oracles]  # Adds kubernetes-validate and checkov
```

### Configuration

Create a `config.json` file in your project root:

```json
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
```

**Note**: LLM integration is optional. Without an API key, CeLoR uses default templates.

### Basic Usage

#### CLI

```bash
# Repair a deployment manifest
celor repair deployment.yaml --out fixed/

# Without LLM (use default template)
celor repair deployment.yaml --out fixed/ --no-llm

# With custom synthesis limits
celor repair deployment.yaml --out fixed/ --max-candidates 500 --timeout 60

# Run demo with example manifest
celor demo --out output/
```

#### Python API

```python
from celor.k8s.artifact import K8sArtifact
from celor.k8s.oracles import PolicyOracle, SecurityOracle, ResourceOracle
from celor.core.controller import repair_artifact

# 1. Load manifest
artifact = K8sArtifact.from_file("deployment.yaml")

# 2. Create oracles
oracles = [
    PolicyOracle(),      # Policy checks (replicas, labels, image tags)
    SecurityOracle(),    # Security baseline
    ResourceOracle()     # Resource validation
]

# 3. Run repair
repaired, metadata = repair_artifact(
    artifact=artifact,
    oracles=oracles
)

# 4. Check results
print(f"Status: {metadata['status']}")
print(f"Iterations: {metadata['iterations']}")
print(f"Candidates tried: {metadata['tried_candidates']}")

if metadata['status'] == 'success':
    # Save repaired manifest
    repaired.write_to_dir("fixed")
```

## How It Works

CeLoR uses a **two-phase architecture**:

1. **Template Generation Phase**
   - LLM call (if API key configured) generates a `PatchTemplate` with **holes** marking uncertain values
   - Template includes operations (e.g., `EnsureLabel`, `EnsureReplicas`) with holes for values
   - If LLM is unavailable or Fix Bank has a match, use stored/default template

2. **Synthesis Phase (CEGIS Loop)**
   - Local iterative loop that:
     - **Verifies** the artifact against oracles (policy, security, resource, schema)
     - **Extracts constraints** from violation evidence (forbidden_value, forbidden_tuple)
     - **Enumerates candidates** lexicographically from HoleSpace
     - **Prunes candidates** that violate learned constraints
     - **Applies patch** with candidate values
     - **Re-verifies** until all oracles pass or max candidates/timeout reached

This approach combines the **structural intuition of LLMs** (where to place operations) with the **systematic search of custom synthesis** (which values to use).

## K8s Oracles

CeLoR provides four built-in oracles for Kubernetes:

- **PolicyOracle**: Policy checks (replicas, labels, image tags, priority class)
- **SecurityOracle**: Security baseline (runAsNonRoot, allowPrivilegeEscalation, etc.)
- **ResourceOracle**: Resource validation and profile checks
- **SchemaOracle**: K8s schema validation (optional, requires kubectl or kubernetes-validate)

## Fix Bank

Fix Bank enables cross-run learning by persisting successful repair patterns:

- **Signature-based matching**: Identifies similar violations across runs
- **Constraint warm-starting**: Reuses learned constraints for faster synthesis
- **Team knowledge sharing**: Commit `.celor-fixes.json` to git for team-wide learning

```bash
# Fix Bank is enabled by default
celor repair deployment.yaml --out fixed/

# Disable Fix Bank
celor repair deployment.yaml --out fixed/ --no-fixbank
```

## Documentation

- **[Full Documentation](docs/)** - Comprehensive guides and API reference
- **[Getting Started](docs/getting_started/)** - Installation and quickstart guides
- **[Core Concepts](docs/core_concepts/)** - Key concepts, architecture, and how it works
- **[Example](docs/example/)** - Step-by-step example walkthroughs
- **[Reference](docs/reference/)** - API reference, CLI, oracles, and troubleshooting

## When to Use CeLoR

CeLoR excels when:
- **LLM-generated K8s manifests fail policy checks**
- **You need deterministic, reproducible repairs**
- **You want to minimize LLM API costs**
- **You have privacy or compliance requirements**
- **You need formal guarantees that repairs satisfy all oracle checks**

Less ideal for:
- Manifests that are already compliant
- Simple fixes (single field changes)
- Subjective requirements (code quality, readability)

## Example Workflow

1. LLM generates K8s deployment manifest with policy violations
2. Oracles detect violations: replicas too low, missing labels, security issues
3. CeLoR calls LLM once (if configured) to get PatchTemplate with holes
4. Local CEGIS loop:
   - Runs oracles → extracts constraints from violations
   - Enumerates candidates from HoleSpace (e.g., replicas ∈ {3, 4, 5})
   - Prunes candidates violating constraints (e.g., forbid replicas=2 for prod)
   - Applies patch with candidate values
   - Re-runs oracles → all pass
5. Returns verified, repaired manifest
6. Stores repair pattern in Fix Bank for future reuse

## Requirements

- Python 3.11+
- `ruamel.yaml >= 0.18.0` (YAML manipulation)
- `openai >= 1.0.0` (LLM integration, optional)

Optional:
- `kubernetes-validate >= 1.28.0` (for SchemaOracle)
- `checkov >= 3.0.0` (for enhanced policy/security checks)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **CEGIS**: Counterexample-Guided Inductive Synthesis methodology
- Inspired by research in program synthesis and LLM verification
