# CeLoR: CEGIS-in-the-Loop Reasoning

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Research Report](https://img.shields.io/badge/📄-Research%20Report-red)](report/celor.pdf)

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
git clone https://github.com/simjay/celor.git
cd celor

# Install CeLoR
pip install -e .

# Optional: Install enhanced oracle support
pip install celor[oracles]  # Adds kubernetes-validate and checkov
```

### Configuration

Create a `config.json` file with your OpenAI API key. LLM integration is optional—without an API key, CeLoR uses default templates.

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

artifact = K8sArtifact.from_file("deployment.yaml")
oracles = [PolicyOracle(), SecurityOracle(), ResourceOracle()]
repaired, metadata = repair_artifact(artifact=artifact, oracles=oracles)

if metadata['status'] == 'success':
    repaired.write_to_dir("fixed")
```

## How It Works

CeLoR uses a two-phase approach: (1) LLM generates repair templates with holes, (2) local CEGIS loop fills holes via systematic search. This combines LLM structural intuition with deterministic synthesis.

## Fix Bank

Fix Bank enables cross-run learning by persisting successful repair patterns. Enabled by default; disable with `--no-fixbank`.

## Benchmark

Compare CeLoR vs Pure-LLM on 30 Kubernetes manifest repair cases:

```bash
cd benchmark
python run_benchmark.py                   # Run all phases
python run_benchmark.py --phase cold      # Cold start only
python run_benchmark.py --phase warm      # Warm start only
python run_benchmark.py --phase pure_llm  # Pure-LLM only
```

## Documentation

- **[Full Documentation](docs/)** - Comprehensive guides and API reference
- **[Getting Started](docs/getting_started/)** - Installation and quickstart guides
- **[Core Concepts](docs/core_concepts/)** - Key concepts, architecture, and how it works
- **[Example](docs/example/)** - Step-by-step example walkthroughs
- **[Reference](docs/reference/)** - API reference, CLI, oracles, and troubleshooting


## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
