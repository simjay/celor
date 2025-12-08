"""CeLoR CLI - Command-line interface for K8s manifest repair.

This module provides the main CLI entrypoint for CeLoR, allowing users
to repair K8s manifests from the command line.
"""

import argparse
import logging
import sys
from pathlib import Path

from celor.core.cegis.loop import repair
from celor.core.cegis.synthesizer import SynthConfig
from celor.core.config import get_config_value
from celor.k8s.artifact import K8sArtifact
from celor.k8s.examples import payments_api_template_and_holes
from celor.k8s.oracles import PolicyOracle, ResourceOracle, SecurityOracle

logger = logging.getLogger(__name__)


def main():
    """Main CLI entrypoint for CeLoR."""
    parser = argparse.ArgumentParser(
        prog="celor",
        description="CeLoR - CEGIS-based K8s manifest repair",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Repair a deployment manifest
  celor repair deployment.yaml --out fixed/
  
  # With custom synthesis config
  celor repair deployment.yaml --out fixed/ --max-candidates 200 --timeout 60
  
  # With custom OpenAI model
  celor repair deployment.yaml --out fixed/ --openai-model gpt-4-turbo
  
  # Without LLM (use default template)
  celor repair deployment.yaml --out fixed/ --no-llm
  
  # Verbose mode
  celor repair deployment.yaml --out fixed/ -v
  
Note:
  LLM adapter will be auto-created from config.json if API key is present.
  Set {'openai': {'api_key': 'sk-...'}} in config.json to enable LLM integration.
"""
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Repair command
    repair_parser = subparsers.add_parser(
        "repair",
        help="Repair a K8s deployment manifest"
    )
    repair_parser.add_argument(
        "input",
        help="Path to input deployment.yaml"
    )
    repair_parser.add_argument(
        "--out",
        required=True,
        help="Output directory for repaired manifest"
    )
    repair_parser.add_argument(
        "--output-filename",
        help="Output filename (default: preserves input filename). Example: fixed.yaml"
    )
    repair_parser.add_argument(
        "--max-candidates",
        type=int,
        default=None,
        help="Maximum candidates to try (default: from config.json or 1000)"
    )
    repair_parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Synthesis timeout in seconds (default: from config.json or 60.0)"
    )
    repair_parser.add_argument(
        "--max-iters",
        type=int,
        default=None,
        help="Maximum CEGIS iterations (default: from config.json or 5)"
    )
    repair_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    repair_parser.add_argument(
        "--fixbank",
        default=".celor-fixes.json",
        help="Path to Fix Bank file (default: .celor-fixes.json)"
    )
    repair_parser.add_argument(
        "--no-fixbank",
        action="store_true",
        help="Disable Fix Bank"
    )
    repair_parser.add_argument(
        "--openai-model",
        help="OpenAI model to use (overrides config.json, e.g., gpt-4-turbo)"
    )
    repair_parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM adapter (always use default template)"
    )
    
    # Demo command
    demo_parser = subparsers.add_parser(
        "demo",
        help="Run demo with example manifest"
    )
    demo_parser.add_argument(
        "--out",
        help="Output directory for repaired manifest"
    )
    demo_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    demo_parser.add_argument(
        "--fixbank",
        help="Path to Fix Bank file (enables cross-run learning)"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    if hasattr(args, 'verbose') and args.verbose:
        logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    else:
        logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
    
    # Handle commands
    if args.command == "repair":
        return cmd_repair(args)
    elif args.command == "demo":
        return cmd_demo(args)
    else:
        parser.print_help()
        return 1


def cmd_repair(args):
    """Handle repair command."""
    input_path = Path(args.input)
    output_dir = Path(args.out)
    
    # Validate input
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        return 1
    
    print(f"Repairing: {input_path}")
    
    # Load CEGIS config from config.json with CLI args as overrides
    max_iters = args.max_iters
    if max_iters is None:
        max_iters = get_config_value(["cegis", "max_iters"], default=5)
    
    max_candidates = args.max_candidates
    if max_candidates is None:
        max_candidates = get_config_value(["cegis", "max_candidates"], default=1000)
    
    timeout_seconds = args.timeout
    if timeout_seconds is None:
        timeout_seconds = get_config_value(["cegis", "timeout_seconds"], default=60.0)
    
    # Setup Fix Bank
    fixbank = None
    if not args.no_fixbank:
        from celor.core.fixbank import FixBank
        fixbank = FixBank(args.fixbank)
        print(f"Fix Bank: {args.fixbank} ({len(fixbank.entries)} entries)")
    
    try:
        # Load artifact
        artifact = K8sArtifact.from_file(str(input_path))
        
        # Setup
        oracles = [PolicyOracle(), SecurityOracle(), ResourceOracle()]
        config = SynthConfig(
            max_candidates=max_candidates,
            timeout_seconds=timeout_seconds
        )
        
        # Check initial violations
        initial_violations = []
        for oracle in oracles:
            initial_violations.extend(oracle(artifact))
        
        if not initial_violations:
            print("✓ Manifest already passes all oracles, no repair needed")
            return 0
        
        print(f"Found {len(initial_violations)} violations")
        
        # Setup LLM adapter if config.json has API key and --no-llm not set
        llm_adapter = None
        if not args.no_llm:
            if get_config_value(["openai", "api_key"]):
                from celor.llm.adapter import LLMAdapter
                llm_config = {}
                if args.openai_model:
                    llm_config["model"] = args.openai_model
                llm_adapter = LLMAdapter(**llm_config)
                print(f"LLM adapter: {llm_adapter.client.model}")
        else:
            print("LLM adapter: disabled (--no-llm flag)")
        
        # Repair
        print("Running CEGIS synthesis...")
        from celor.core.controller import repair_artifact
        
        repaired_artifact, metadata = repair_artifact(
            artifact=artifact,
            template=None,  # Let controller decide
            hole_space=None,
            oracles=oracles,
            max_iters=max_iters,
            config=config,
            fixbank=fixbank,
            llm_adapter=llm_adapter,
            default_template_fn=payments_api_template_and_holes
        )
        
        # Results
        print(f"\nStatus: {metadata['status']}")
        print(f"Fix Bank: {'HIT' if metadata.get('fixbank_hit') else 'MISS'}")
        print(f"Iterations: {metadata['iterations']}")
        print(f"Candidates tried: {metadata['tried_candidates']}")
        print(f"Constraints learned: {len(metadata['constraints'])}")
        
        if metadata['status'] == 'success':
            # Verify
            final_violations = []
            for oracle in oracles:
                final_violations.extend(oracle(repaired_artifact))
            
            if final_violations:
                print(f"\n⚠ Warning: Repaired manifest still has {len(final_violations)} violations")
                for v in final_violations:
                    print(f"  - {v.id}: {v.message}")
                return 1
            
            # Write output
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Use output_filename if provided, otherwise None (preserves original)
            output_filename = getattr(args, 'output_filename', None)
            repaired_artifact.write_to_dir(str(output_dir), output_filename=output_filename)
            
            print(f"\n✅ Repair successful!")
            if output_filename:
                print(f"   Wrote repaired manifest to: {output_dir}/{output_filename}")
            else:
                # Show what was actually saved
                saved_files = list(repaired_artifact.files.keys())
                if saved_files:
                    print(f"   Wrote repaired manifest to: {output_dir}/{saved_files[0]}")
            return 0
        else:
            print(f"\n❌ Repair failed: {metadata['status']}")
            if 'violations' in metadata:
                print(f"   Remaining violations: {len(metadata['violations'])}")
            return 1
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        logger.exception("Repair failed")
        return 1


def cmd_demo(args):
    """Handle demo command."""
    print("Running CeLoR demo with example manifest...")
    print()
    
    try:
        from celor.k8s.demo import demo_repair as run_demo
        
        repaired, metadata = run_demo(
            input_file=None,  # Use example
            output_dir=args.out,
            verbose=True,
            fixbank_path=args.fixbank
        )
        
        if metadata['status'] == 'success':
            return 0
        else:
            return 1
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        logger.exception("Demo failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

