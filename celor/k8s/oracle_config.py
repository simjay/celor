"""Unified Oracle Configuration System

This module provides a single source of truth for oracle configurations
used across demos, benchmarks, and production use cases.

It supports:
- Custom oracles (PolicyOracle, SecurityOracle, ResourceOracle, etc.)
- External oracles (Checkov, kubernetes-validate)
- Configurable oracle sets for different scenarios
"""

from typing import List, Optional, Any

from celor.k8s.oracles import (
    PolicyOracle,
    SecurityOracle,
    ResourceOracle,
    SchemaOracle,
    CheckovPolicyOracle,
    CheckovSecurityOracle,
)
from celor.k8s.simple_oracles import ECRPolicyOracle
from celor.k8s.constants import VALID_ENV_NAMES


class OracleConfig:
    """Configuration for oracle sets.
    
    Defines which oracles to use for different scenarios (demo, benchmark, etc.)
    """
    
    def __init__(
        self,
        name: str,
        custom_oracles: List[Any],
        external_oracles: Optional[List[Any]] = None,
        description: str = ""
    ):
        """Initialize oracle configuration.
        
        Args:
            name: Configuration name (e.g., "demo", "benchmark")
            custom_oracles: List of custom oracles (always available)
            external_oracles: Optional list of external oracles (may not be available)
            description: Description of this configuration
        """
        self.name = name
        self.custom_oracles = custom_oracles
        self.external_oracles = external_oracles or []
        self.description = description
    
    def get_oracles(self, include_external: bool = True) -> List[Any]:
        """Get list of oracles for this configuration.
        
        Args:
            include_external: If True, include external oracles (if available)
            
        Returns:
            List of oracle instances
        """
        oracles = list(self.custom_oracles)
        
        if include_external:
            # Add external oracles (they handle unavailability gracefully by returning empty violation lists)
            oracles.extend(self.external_oracles)
        
        return oracles


# Predefined Oracle Configurations

# Configuration for simple demos (minimal, fast)
SIMPLE_DEMO_CONFIG = OracleConfig(
    name="simple_demo",
    custom_oracles=[
        ECRPolicyOracle(),  # ECR + env label validation
    ],
    external_oracles=[
        SchemaOracle(use_kubernetes_validate=True),  # YAML + schema validation
    ],
    description="Simple demo configuration: ECR policy and schema validation"
)

# Configuration for full demos (comprehensive)
FULL_DEMO_CONFIG = OracleConfig(
    name="full_demo",
    custom_oracles=[
        PolicyOracle(),      # Custom policy checks (ECR, replicas, labels, etc.)
        SecurityOracle(),    # Security baseline
        ResourceOracle(),    # Resource validation
    ],
    external_oracles=[
        SchemaOracle(use_kubernetes_validate=True),  # Schema validation
        CheckovPolicyOracle(),  # Comprehensive policy checks (if available)
        CheckovSecurityOracle(),  # Security checks (if available)
    ],
    description="Full demo configuration: All custom oracles + external tools"
)

# Configuration for benchmark (standard, reproducible)
BENCHMARK_CONFIG = OracleConfig(
    name="benchmark",
    custom_oracles=[
        PolicyOracle(),      # Custom policy checks
        SecurityOracle(),    # Security baseline
        ResourceOracle(),    # Resource validation
    ],
    external_oracles=[
        SchemaOracle(use_kubernetes_validate=True),  # Schema validation (optional)
    ],
    description="Benchmark configuration: Standard custom oracles, optional schema validation"
)

# Configuration for benchmark (minimal, fast - for pilot testing)
BENCHMARK_MINIMAL_CONFIG = OracleConfig(
    name="benchmark_minimal",
    custom_oracles=[
        PolicyOracle(),      # Custom policy checks
        SecurityOracle(),    # Security baseline
    ],
    description="Minimal benchmark configuration: Fast oracles only (for pilot testing)"
)

# Configuration for production use (comprehensive)
PRODUCTION_CONFIG = OracleConfig(
    name="production",
    custom_oracles=[
        PolicyOracle(),
        SecurityOracle(),
        ResourceOracle(),
    ],
    external_oracles=[
        SchemaOracle(use_kubernetes_validate=True),
        CheckovPolicyOracle(),
        CheckovSecurityOracle(),
    ],
    description="Production configuration: All available oracles"
)


def get_oracle_config(config_name: str) -> OracleConfig:
    """Get oracle configuration by name.
    
    Args:
        config_name: Name of configuration ("simple_demo", "full_demo", "benchmark", etc.)
        
    Returns:
        OracleConfig instance
        
    Raises:
        ValueError: If config_name is not recognized
    """
    configs = {
        "simple_demo": SIMPLE_DEMO_CONFIG,
        "full_demo": FULL_DEMO_CONFIG,
        "benchmark": BENCHMARK_CONFIG,
        "benchmark_minimal": BENCHMARK_MINIMAL_CONFIG,
        "production": PRODUCTION_CONFIG,
    }
    
    if config_name not in configs:
        raise ValueError(
            f"Unknown oracle config: {config_name}. "
            f"Available: {', '.join(configs.keys())}"
        )
    
    return configs[config_name]


def get_oracles_for_scenario(
    scenario: str,
    include_external: bool = True
) -> List[Any]:
    """Get oracle list for a given scenario.
    
    Convenience function that combines get_oracle_config() and get_oracles().
    
    Args:
        scenario: Scenario name ("simple_demo", "full_demo", "benchmark", etc.)
        include_external: Whether to include external oracles
        
    Returns:
        List of oracle instances
    """
    config = get_oracle_config(scenario)
    return config.get_oracles(include_external=include_external)
