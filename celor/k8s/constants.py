"""K8s constants used across oracle modules.

This module contains constants that are shared across multiple oracle modules
to avoid circular import issues.
"""

# Company standard environment names (used across all oracles)
# Only these three values are valid - exact match required, no aliases or variations
VALID_ENV_NAMES = {"production-us", "staging-us", "dev-us"}
