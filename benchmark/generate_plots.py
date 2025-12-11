#!/usr/bin/env python3
"""
Generate visualization plots for benchmark results.

Creates comprehensive plots comparing CeLoR vs Pure-LLM across multiple metrics.
"""

import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from typing import Dict, List

# Set style
plt.style.use('seaborn-v0_8-darkgrid')
plt.rcParams['figure.figsize'] = (12, 8)
plt.rcParams['font.size'] = 11

RESULTS_DIR = Path(__file__).parent / "results"
OUTPUT_DIR = Path(__file__).parent / "plots"
OUTPUT_DIR.mkdir(exist_ok=True)


def load_results():
    """Load all benchmark result files."""
    with open(RESULTS_DIR / "cold_results.json") as f:
        cold = json.load(f)
    with open(RESULTS_DIR / "warm_results.json") as f:
        warm = json.load(f)
    with open(RESULTS_DIR / "pure_llm_results.json") as f:
        pure_llm = json.load(f)
    return cold, warm, pure_llm


def calculate_stats(results):
    """Calculate aggregate statistics from results."""
    stats = {
        'total_cases': len(results['results']),
        'successful': sum(1 for r in results['results'] if r['success']),
        'total_time': sum(r['time_seconds'] for r in results['results']),
        'total_llm_calls': sum(r['llm_calls'] for r in results['results']),
        'total_violations': sum(r['initial_violations'] for r in results['results']),
        'fixed_violations': sum(r['violations_fixed'] for r in results['results']),
        'times': [r['time_seconds'] for r in results['results']],
        'llm_calls': [r['llm_calls'] for r in results['results']],
        'violations': [r['initial_violations'] for r in results['results']],
    }
    stats['avg_time'] = stats['total_time'] / stats['total_cases']
    stats['avg_llm_calls'] = stats['total_llm_calls'] / stats['total_cases']
    stats['success_rate'] = stats['successful'] / stats['total_cases'] * 100
    return stats


def plot_success_rate(cold_stats, warm_stats, pure_llm_stats):
    """Plot success rate comparison."""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    approaches = ['CeLoR\nCold Start', 'CeLoR\nWarm Start', 'Pure-LLM\nBaseline']
    success_rates = [
        cold_stats['success_rate'],
        warm_stats['success_rate'],
        pure_llm_stats['success_rate']
    ]
    
    bars = ax.bar(approaches, success_rates, color=['#2E86AB', '#A23B72', '#F18F01'], alpha=0.8)
    
    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}%',
                ha='center', va='bottom', fontsize=12, fontweight='bold')
    
    ax.set_ylabel('Success Rate (%)', fontsize=12, fontweight='bold')
    ax.set_title('Success Rate Comparison', fontsize=14, fontweight='bold', pad=20)
    ax.set_ylim([95, 105])
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'success_rate.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✓ Saved: {OUTPUT_DIR / 'success_rate.png'}")


def plot_llm_efficiency(cold_stats, warm_stats, pure_llm_stats):
    """Plot LLM call efficiency comparison."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    approaches = ['CeLoR\nCold', 'CeLoR\nWarm', 'Pure-LLM']
    total_calls = [
        cold_stats['total_llm_calls'],
        warm_stats['total_llm_calls'],
        pure_llm_stats['total_llm_calls']
    ]
    avg_calls = [
        cold_stats['avg_llm_calls'],
        warm_stats['avg_llm_calls'],
        pure_llm_stats['avg_llm_calls']
    ]
    
    # Total LLM calls
    bars1 = ax1.bar(approaches, total_calls, color=['#2E86AB', '#A23B72', '#F18F01'], alpha=0.8)
    for bar in bars1:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}',
                ha='center', va='bottom', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Total LLM Calls', fontsize=12, fontweight='bold')
    ax1.set_title('Total LLM Calls (30 cases)', fontsize=13, fontweight='bold')
    ax1.grid(axis='y', alpha=0.3)
    
    # Average LLM calls per case
    bars2 = ax2.bar(approaches, avg_calls, color=['#2E86AB', '#A23B72', '#F18F01'], alpha=0.8)
    for bar in bars2:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.2f}',
                ha='center', va='bottom', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Average LLM Calls per Case', fontsize=12, fontweight='bold')
    ax2.set_title('Average LLM Calls per Case', fontsize=13, fontweight='bold')
    ax2.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'llm_efficiency.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✓ Saved: {OUTPUT_DIR / 'llm_efficiency.png'}")


def plot_time_comparison(cold_stats, warm_stats, pure_llm_stats):
    """Plot time efficiency comparison."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    approaches = ['CeLoR\nCold', 'CeLoR\nWarm', 'Pure-LLM']
    total_times = [
        cold_stats['total_time'],
        warm_stats['total_time'],
        pure_llm_stats['total_time']
    ]
    avg_times = [
        cold_stats['avg_time'],
        warm_stats['avg_time'],
        pure_llm_stats['avg_time']
    ]
    
    # Total time
    bars1 = ax1.bar(approaches, total_times, color=['#2E86AB', '#A23B72', '#F18F01'], alpha=0.8)
    for bar in bars1:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}s',
                ha='center', va='bottom', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Total Time (seconds)', fontsize=12, fontweight='bold')
    ax1.set_title('Total Execution Time (30 cases)', fontsize=13, fontweight='bold')
    ax1.grid(axis='y', alpha=0.3)
    
    # Average time per case
    bars2 = ax2.bar(approaches, avg_times, color=['#2E86AB', '#A23B72', '#F18F01'], alpha=0.8)
    for bar in bars2:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.2f}s',
                ha='center', va='bottom', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Average Time per Case (seconds)', fontsize=12, fontweight='bold')
    ax2.set_title('Average Time per Case', fontsize=13, fontweight='bold')
    ax2.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'time_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✓ Saved: {OUTPUT_DIR / 'time_comparison.png'}")


def plot_time_distribution(cold_stats, warm_stats, pure_llm_stats):
    """Plot time distribution across cases."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Create box plot
    data = [cold_stats['times'], warm_stats['times'], pure_llm_stats['times']]
    labels = ['CeLoR Cold', 'CeLoR Warm', 'Pure-LLM']
    
    bp = ax.boxplot(data, tick_labels=labels, patch_artist=True,
                    boxprops=dict(facecolor='lightblue', alpha=0.7),
                    medianprops=dict(color='red', linewidth=2))
    
    # Color the boxes
    colors = ['#2E86AB', '#A23B72', '#F18F01']
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    
    ax.set_ylabel('Time per Case (seconds)', fontsize=12, fontweight='bold')
    ax.set_title('Time Distribution Across Cases', fontsize=14, fontweight='bold', pad=20)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'time_distribution.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✓ Saved: {OUTPUT_DIR / 'time_distribution.png'}")


def plot_fixbank_benefits(cold_stats, warm_stats):
    """Plot Fix Bank benefits visualization."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # LLM calls reduction
    approaches = ['Cold Start', 'Warm Start']
    llm_calls = [cold_stats['total_llm_calls'], warm_stats['total_llm_calls']]
    
    bars1 = ax1.bar(approaches, llm_calls, color=['#2E86AB', '#A23B72'], alpha=0.8)
    for bar in bars1:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}',
                ha='center', va='bottom', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Total LLM Calls', fontsize=12, fontweight='bold')
    ax1.set_title('LLM Calls: Cold vs Warm Start', fontsize=13, fontweight='bold')
    ax1.grid(axis='y', alpha=0.3)
    
    # Time speedup
    times = [cold_stats['avg_time'], warm_stats['avg_time']]
    bars2 = ax2.bar(approaches, times, color=['#2E86AB', '#A23B72'], alpha=0.8)
    for bar in bars2:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.3f}s',
                ha='center', va='bottom', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Average Time per Case (seconds)', fontsize=12, fontweight='bold')
    ax2.set_title('Time: Cold vs Warm Start', fontsize=13, fontweight='bold')
    ax2.grid(axis='y', alpha=0.3)
    
    # Add speedup annotation
    speedup = cold_stats['avg_time'] / warm_stats['avg_time']
    ax2.text(0.5, max(times) * 0.7, f'{speedup:.1f}x speedup',
            ha='center', fontsize=14, fontweight='bold', color='green',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'fixbank_benefits.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✓ Saved: {OUTPUT_DIR / 'fixbank_benefits.png'}")


def plot_iteration_analysis(pure_llm_results):
    """Plot Pure-LLM iteration analysis."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Count cases by number of LLM calls
    llm_call_counts = {}
    for result in pure_llm_results['results']:
        calls = result['llm_calls']
        llm_call_counts[calls] = llm_call_counts.get(calls, 0) + 1
    
    calls = sorted(llm_call_counts.keys())
    counts = [llm_call_counts[c] for c in calls]
    
    bars = ax.bar([f'{c} call{"s" if c > 1 else ""}' for c in calls], counts,
                  color=['#F18F01' if c == 1 else '#C73E1D' for c in calls], alpha=0.8)
    
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}',
                ha='center', va='bottom', fontsize=12, fontweight='bold')
    
    ax.set_ylabel('Number of Cases', fontsize=12, fontweight='bold')
    ax.set_xlabel('LLM Calls Required', fontsize=12, fontweight='bold')
    ax.set_title('Pure-LLM: Cases Requiring Multiple Iterations', fontsize=14, fontweight='bold', pad=20)
    ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'iteration_analysis.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✓ Saved: {OUTPUT_DIR / 'iteration_analysis.png'}")


def plot_comprehensive_comparison(cold_stats, warm_stats, pure_llm_stats):
    """Create a comprehensive comparison plot."""
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(2, 3, hspace=0.3, wspace=0.3)
    
    approaches = ['CeLoR\nCold', 'CeLoR\nWarm', 'Pure-LLM']
    
    # 1. Success Rate
    ax1 = fig.add_subplot(gs[0, 0])
    success_rates = [cold_stats['success_rate'], warm_stats['success_rate'], pure_llm_stats['success_rate']]
    bars = ax1.bar(approaches, success_rates, color=['#2E86AB', '#A23B72', '#F18F01'], alpha=0.8)
    for bar in bars:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height, f'{height:.0f}%',
                ha='center', va='bottom', fontweight='bold')
    ax1.set_ylabel('Success Rate (%)', fontweight='bold')
    ax1.set_title('Success Rate', fontweight='bold')
    ax1.set_ylim([95, 105])
    ax1.grid(axis='y', alpha=0.3)
    
    # 2. LLM Calls
    ax2 = fig.add_subplot(gs[0, 1])
    llm_calls = [cold_stats['avg_llm_calls'], warm_stats['avg_llm_calls'], pure_llm_stats['avg_llm_calls']]
    bars = ax2.bar(approaches, llm_calls, color=['#2E86AB', '#A23B72', '#F18F01'], alpha=0.8)
    for bar in bars:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height, f'{height:.2f}',
                ha='center', va='bottom', fontweight='bold')
    ax2.set_ylabel('Avg LLM Calls per Case', fontweight='bold')
    ax2.set_title('LLM Efficiency', fontweight='bold')
    ax2.grid(axis='y', alpha=0.3)
    
    # 3. Time
    ax3 = fig.add_subplot(gs[0, 2])
    avg_times = [cold_stats['avg_time'], warm_stats['avg_time'], pure_llm_stats['avg_time']]
    bars = ax3.bar(approaches, avg_times, color=['#2E86AB', '#A23B72', '#F18F01'], alpha=0.8)
    for bar in bars:
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2., height, f'{height:.2f}s',
                ha='center', va='bottom', fontweight='bold')
    ax3.set_ylabel('Avg Time per Case (s)', fontweight='bold')
    ax3.set_title('Time Efficiency', fontweight='bold')
    ax3.grid(axis='y', alpha=0.3)
    
    # 4. Time Distribution
    ax4 = fig.add_subplot(gs[1, :])
    data = [cold_stats['times'], warm_stats['times'], pure_llm_stats['times']]
    bp = ax4.boxplot(data, tick_labels=['CeLoR Cold', 'CeLoR Warm', 'Pure-LLM'],
                     patch_artist=True, boxprops=dict(alpha=0.7),
                     medianprops=dict(color='red', linewidth=2))
    colors = ['#2E86AB', '#A23B72', '#F18F01']
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
    ax4.set_ylabel('Time per Case (seconds)', fontweight='bold')
    ax4.set_title('Time Distribution Across All Cases', fontweight='bold')
    ax4.grid(axis='y', alpha=0.3)
    
    plt.suptitle('Comprehensive Benchmark Comparison: CeLoR vs Pure-LLM', 
                 fontsize=16, fontweight='bold', y=0.98)
    
    plt.savefig(OUTPUT_DIR / 'comprehensive_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✓ Saved: {OUTPUT_DIR / 'comprehensive_comparison.png'}")


def main():
    """Generate all plots."""
    print("Loading benchmark results...")
    cold, warm, pure_llm = load_results()
    
    print("Calculating statistics...")
    cold_stats = calculate_stats(cold)
    warm_stats = calculate_stats(warm)
    pure_llm_stats = calculate_stats(pure_llm)
    
    print("\nGenerating plots...")
    plot_success_rate(cold_stats, warm_stats, pure_llm_stats)
    plot_llm_efficiency(cold_stats, warm_stats, pure_llm_stats)
    plot_time_comparison(cold_stats, warm_stats, pure_llm_stats)
    plot_time_distribution(cold_stats, warm_stats, pure_llm_stats)
    plot_fixbank_benefits(cold_stats, warm_stats)
    plot_iteration_analysis(pure_llm)
    plot_comprehensive_comparison(cold_stats, warm_stats, pure_llm_stats)
    
    print(f"\n✅ All plots saved to: {OUTPUT_DIR}")
    print("\nGenerated plots:")
    print("  - success_rate.png")
    print("  - llm_efficiency.png")
    print("  - time_comparison.png")
    print("  - time_distribution.png")
    print("  - fixbank_benefits.png")
    print("  - iteration_analysis.png")
    print("  - comprehensive_comparison.png")


if __name__ == "__main__":
    main()
