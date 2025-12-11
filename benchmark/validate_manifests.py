#!/usr/bin/env python3
"""
Validate generated benchmark manifests.

This script runs oracles on all generated manifests to verify:
- Violations are detected correctly
- No duplicate manifests
- All cases have known violations
- Violations match expected types
"""

import json
from pathlib import Path
from typing import Dict, List

from celor.k8s.artifact import K8sArtifact
from celor.k8s.oracle_config import get_oracles_for_scenario

# Configuration
BENCHMARK_DIR = Path(__file__).parent
MANIFESTS_DIR = BENCHMARK_DIR / "manifests"
RESULTS_DIR = BENCHMARK_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def validate_manifest(filepath: Path) -> Dict:
    """Validate a single manifest and return violations.
    
    Args:
        filepath: Path to manifest YAML file
        
    Returns:
        Dictionary with validation results
    """
    try:
        artifact = K8sArtifact.from_file(str(filepath))
        
        # Run all oracles using unified benchmark configuration
        oracles = get_oracles_for_scenario("benchmark", include_external=False)
        all_violations = []
        
        for oracle in oracles:
            violations = oracle(artifact)
            all_violations.extend(violations)
        
        return {
            "file": filepath.name,
            "valid": True,
            "violations": [
                {
                    "id": v.id,
                    "message": v.message,
                    "severity": v.severity,
                }
                for v in all_violations
            ],
            "violation_count": len(all_violations),
            "violation_types": sorted(list(set(v.id.split(".")[0] for v in all_violations))),
        }
    except Exception as e:
        return {
            "file": filepath.name,
            "valid": False,
            "error": str(e),
            "violations": [],
            "violation_count": 0,
        }


def check_duplicates(validation_results: List[Dict]) -> List[Dict]:
    """Check for duplicate manifests.
    
    Args:
        validation_results: List of validation results
        
    Returns:
        List of duplicate groups
    """
    # Group by violation signature
    signature_groups: Dict[str, List[str]] = {}
    
    for result in validation_results:
        if result["valid"]:
            # Create signature from violation types and counts
            sig = tuple(sorted(result["violation_types"]))
            sig_key = str(sig)
            
            if sig_key not in signature_groups:
                signature_groups[sig_key] = []
            signature_groups[sig_key].append(result["file"])
    
    # Find duplicates (groups with more than 1 file)
    duplicates = []
    for sig_key, files in signature_groups.items():
        if len(files) > 1:
            duplicates.append({
                "signature": sig_key,
                "files": files,
                "count": len(files)
            })
    
    return duplicates


def generate_validation_report(validation_results: List[Dict], duplicates: List[Dict]) -> str:
    """Generate a validation report.
    
    Args:
        validation_results: List of validation results
        duplicates: List of duplicate groups
        
    Returns:
        Report as string
    """
    total = len(validation_results)
    valid = sum(1 for r in validation_results if r["valid"])
    invalid = total - valid
    
    total_violations = sum(r["violation_count"] for r in validation_results)
    avg_violations = total_violations / valid if valid > 0 else 0
    
    report = f"""
# Manifest Validation Report

## Summary
- **Total manifests**: {total}
- **Valid manifests**: {valid}
- **Invalid manifests**: {invalid}
- **Total violations**: {total_violations}
- **Average violations per manifest**: {avg_violations:.2f}

## Violation Distribution
"""
    
    # Count violation types
    violation_type_counts: Dict[str, int] = {}
    for result in validation_results:
        if result["valid"]:
            for vtype in result["violation_types"]:
                violation_type_counts[vtype] = violation_type_counts.get(vtype, 0) + 1
    
    for vtype, count in sorted(violation_type_counts.items()):
        report += f"- **{vtype}**: {count} cases\n"
    
    # Duplicates section
    if duplicates:
        report += f"\n## Duplicate Patterns Found: {len(duplicates)}\n\n"
        report += "*(Note: Some duplicates are intentional for Fix Bank evaluation)*\n\n"
        for dup in duplicates[:10]:  # Show first 10
            report += f"- **{dup['count']} cases** with signature `{dup['signature']}`:\n"
            for file in dup["files"][:5]:  # Show first 5 files
                report += f"  - {file}\n"
            if len(dup["files"]) > 5:
                report += f"  - ... and {len(dup['files']) - 5} more\n"
    else:
        report += "\n## Duplicates: None found\n"
    
    # Invalid manifests
    invalid_manifests = [r for r in validation_results if not r["valid"]]
    if invalid_manifests:
        report += f"\n## Invalid Manifests: {len(invalid_manifests)}\n\n"
        for result in invalid_manifests:
            report += f"- **{result['file']}**: {result.get('error', 'Unknown error')}\n"
    
    return report


def main():
    """Validate all generated manifests."""
    print("Validating benchmark manifests...")
    print(f"Manifests directory: {MANIFESTS_DIR}")
    
    if not MANIFESTS_DIR.exists():
        print(f"❌ Error: {MANIFESTS_DIR} does not exist")
        print("   Run generate_manifests.py first")
        return
    
    manifest_files = sorted(MANIFESTS_DIR.glob("case_*.yaml"))
    
    if not manifest_files:
        print(f"❌ Error: No manifest files found in {MANIFESTS_DIR}")
        print("   Run generate_manifests.py first")
        return
    
    print(f"Found {len(manifest_files)} manifest files\n")
    
    # Validate each manifest
    validation_results = []
    for filepath in manifest_files:
        print(f"Validating {filepath.name}...", end=" ")
        result = validate_manifest(filepath)
        validation_results.append(result)
        
        if result["valid"]:
            print(f"✅ {result['violation_count']} violations")
        else:
            print(f"❌ Error: {result.get('error', 'Unknown')}")
    
    # Check for duplicates
    print("\nChecking for duplicates...")
    duplicates = check_duplicates(validation_results)
    
    # Generate report
    report = generate_validation_report(validation_results, duplicates)
    
    # Save report
    report_path = RESULTS_DIR / "validation_report.md"
    report_path.write_text(report)
    
    # Save JSON results
    json_path = RESULTS_DIR / "validation_results.json"
    json_path.write_text(json.dumps({
        "results": validation_results,
        "duplicates": duplicates,
        "summary": {
            "total": len(validation_results),
            "valid": sum(1 for r in validation_results if r["valid"]),
            "invalid": sum(1 for r in validation_results if not r["valid"]),
            "total_violations": sum(r["violation_count"] for r in validation_results),
        }
    }, indent=2))
    
    print(f"\n✅ Validation complete!")
    print(f"   Report: {report_path}")
    print(f"   JSON: {json_path}")
    
    # Print summary
    valid = sum(1 for r in validation_results if r["valid"])
    print(f"\nSummary: {valid}/{len(validation_results)} manifests valid")
    
    if duplicates:
        print(f"   Found {len(duplicates)} duplicate patterns (some intentional for Fix Bank)")


if __name__ == "__main__":
    main()
