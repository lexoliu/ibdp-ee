#!/usr/bin/env python3
"""
Plot comparison charts for multiple programming languages benchmark results.
Shows memory usage, latency, and throughput over time for three languages.
"""

from __future__ import annotations

import json
import csv
import argparse
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate comparison charts for benchmark results")
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results"),
        help="Root directory containing benchmark runs (default: results)",
    )
    parser.add_argument(
        "--run-dirs",
        nargs="+",
        type=Path,
        default=None,
        help="Explicit benchmark run directories. If omitted the latest run per language under --results-dir/<language> is used.",
    )
    parser.add_argument(
        "--languages",
        nargs="+",
        default=["java", "go", "rust"],
        help="Languages to compare when auto-discovering runs (default: java go rust)",
    )
    parser.add_argument(
        "--tests",
        nargs="+",
        default=["prime", "light", "kv"],
        choices=["prime", "light", "kv"],
        help="Test types to analyze (default: all tests)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Output directory for generated charts (default: current directory)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        help="Optional X-axis limit in seconds. Defaults to the longest series length.",
    )
    return parser.parse_args()

def resolve_run_directories(args: argparse.Namespace) -> List[Tuple[str, Path]]:
    runs: List[Tuple[str, Path]] = []

    if args.run_dirs:
        for run_dir in args.run_dirs:
            payload = load_results_payload(run_dir)
            language = payload.get("language") if isinstance(payload, dict) else None
            if not language:
                print(f"Warning: skipping {run_dir}, missing language metadata")
                continue
            runs.append((language, run_dir))
        return runs

    for language in args.languages:
        language_root = args.results_dir / language
        candidates: List[Path] = []
        if language_root.is_dir():
            candidates.extend(p for p in language_root.iterdir() if p.is_dir())
        candidates.extend(p for p in args.results_dir.glob(f"{language}_*") if p.is_dir())
        candidates = sorted(candidates, key=lambda path: path.name, reverse=True)

        selected: Path | None = None
        for candidate in candidates:
            payload = load_results_payload(candidate)
            if payload.get("language") == language:
                selected = candidate
                break
        if selected is None:
            print(f"Warning: no completed run found for {language}")
            continue
        runs.append((language, selected))

    return runs


def load_memory_data(run_dir: Path, language: str, test: str) -> List[Tuple[int, float]]:
    """Load memory usage data from CSV file if available."""
    candidates = [
        run_dir / f"{test}_memory.csv",
        run_dir / f"{test}_mem.csv",
        run_dir / f"{language}_{test}_mem.csv",
        run_dir / f"{language.upper()}_{test}_mem.csv",
    ]

    for memory_file in candidates:
        if memory_file.exists():
            data: List[Tuple[int, float]] = []
            try:
                with memory_file.open("r", encoding="utf-8") as handle:
                    reader = csv.DictReader(handle)
                    for row in reader:
                        timestamp = int(row["timestamp"])
                        memory_mb = float(row["memory_mb"])
                        data.append((timestamp, memory_mb))
            except Exception as exc:
                print(f"Error reading memory data for {language} at {memory_file}: {exc}")
                return []
            return data

    return []


def load_timeseries(run_dir: Path, test: str) -> List[Tuple[int, float, float]]:
    """Load throughput/latency timeseries for a test."""
    timeseries_file = run_dir / f"{test}_timeseries.csv"
    if not timeseries_file.exists():
        print(f"Warning: Timeseries file not found: {timeseries_file}")
        return []

    data: List[Tuple[int, float, float]] = []
    try:
        with timeseries_file.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                second = int(row["second"])
                throughput = float(row["throughput"])
                latency = float(row["latency_ms"])
                data.append((second, throughput, latency))
    except Exception as exc:
        print(f"Error reading timeseries from {timeseries_file}: {exc}")
        return []
    return data


def load_results_payload(run_dir: Path) -> Dict[str, object]:
    summary_path = run_dir / "results.json"
    if not summary_path.exists():
        print(f"Warning: summary file missing at {summary_path}")
        return {}

    try:
        with summary_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:
        print(f"Error reading summary from {summary_path}: {exc}")
        return {}


def load_summary(run_dir: Path) -> Dict[str, Dict[str, float]]:
    payload = load_results_payload(run_dir)
    summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
    if not isinstance(summary, dict):
        return {}
    return summary


def plot_comparison(
    languages: List[str],
    test: str,
    duration_hint: int | None,
    memory_data: Dict[str, List[Tuple[int, float]]],
    perf_data: Dict[str, List[Tuple[int, float, float]]],
    summary_data: Dict[str, Dict[str, float]],
    output_path: Path,
) -> None:
    """Create comparison plots for three metrics across languages."""
    
    # Set up the figure with 3 subplots
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 10))
    fig.suptitle(f'Benchmark Comparison - {test.upper()} Test', fontsize=16, fontweight='bold')
    
    # Color scheme for languages
    colors = {'java': '#ED8B00', 'go': '#00ADD8', 'rust': '#CE422B', 'python': '#306998'}
    
    # Plot 1: Memory Usage
    ax1.set_title('Memory Usage Over Time', fontweight='bold')
    ax1.set_xlabel('Time (seconds)')
    ax1.set_ylabel('Memory Usage (MB)')
    ax1.grid(True, alpha=0.3)
    
    for lang in languages:
        if lang in memory_data and memory_data[lang]:
            times = [t for t, _ in memory_data[lang]]
            memory = [m for _, m in memory_data[lang]]
            ax1.plot(times, memory, label=lang.upper(), color=colors.get(lang, 'gray'), 
                    linewidth=2, marker='o', markersize=3)
    
    ax1.legend()

    # Plot 2: Throughput Over Time
    ax2.set_title('Throughput Over Time', fontweight='bold')
    ax2.set_xlabel('Time (seconds)')
    ax2.set_ylabel('Requests per Second')
    ax2.grid(True, alpha=0.3)
    
    for lang in languages:
        if lang in perf_data and perf_data[lang]:
            times = [t for t, _, _ in perf_data[lang]]
            throughput = [th for _, th, _ in perf_data[lang]]
            ax2.plot(times, throughput, label=lang.upper(), color=colors.get(lang, 'gray'), 
                    linewidth=2)
    
    ax2.legend()
    
    # Plot 3: Latency Over Time
    ax3.set_title('Latency Over Time', fontweight='bold')
    ax3.set_xlabel('Time (seconds)')
    ax3.set_ylabel('Latency (ms)')
    ax3.grid(True, alpha=0.3)
    
    for lang in languages:
        if lang in perf_data and perf_data[lang]:
            times = [t for t, _, _ in perf_data[lang]]
            latency = [lat for _, _, lat in perf_data[lang]]
            ax3.plot(times, latency, label=lang.upper(), color=colors.get(lang, 'gray'), 
                    linewidth=2)
    
    ax3.legend()

    max_time = max((series[-1][0] for series in perf_data.values() if series), default=0)
    x_limit = duration_hint if duration_hint else max_time
    if x_limit == 0:
        x_limit = max_time if max_time else 1

    ax1.set_xlim(0, x_limit)
    ax2.set_xlim(0, x_limit)
    ax3.set_xlim(0, x_limit)
    
    # Adjust layout and save
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Comparison chart saved to: {output_path}")
    
    # Show summary statistics
    print("\n=== Summary Statistics ===")
    for lang in languages:
        if lang in perf_data and perf_data[lang]:
            throughput_values = [th for _, th, _ in perf_data[lang]]
            latency_values = [lat for _, _, lat in perf_data[lang]]
            memory_values = [m for _, m in memory_data.get(lang, [])]

            avg_throughput = np.mean(throughput_values) if throughput_values else 0
            avg_latency = np.mean(latency_values) if latency_values else 0
            avg_memory = np.mean(memory_values) if memory_values else 0

            print(f"{lang.upper()}:")
            summary = summary_data.get(lang, {})
            if summary:
                print(
                    "  Reported Throughput: "
                    f"{summary.get('throughput', 0.0):.2f} req/s"
                )
                print(
                    "  Reported Latency avg/p95: "
                    f"{summary.get('latency_avg', 0.0):.2f} / {summary.get('latency_p95', 0.0):.2f} ms"
                )
            else:
                print(f"  Average Throughput: {avg_throughput:.2f} req/s")
                print(f"  Average Latency: {avg_latency:.2f} ms")
            print(f"  Average Memory: {avg_memory:.2f} MB")
            print()

def generate_plots(
    run_entries: List[Tuple[str, Path]],
    tests: List[str],
    output_dir: Path,
    duration_hint: int | None,
    *,
    verbose: bool = True,
) -> None:
    if not run_entries:
        if verbose:
            print("No benchmark runs provided; skipping plot generation.")
        return

    languages_in_run = [language for language, _ in run_entries]
    if verbose:
        print(f"Generating comparison charts for languages: {languages_in_run}")
        print(f"Tests: {tests}")

    output_dir.mkdir(parents=True, exist_ok=True)

    summary_cache: Dict[str, Dict[str, Dict[str, float]]] = {}
    for language, run_dir in run_entries:
        summary_cache[language] = load_summary(run_dir)

    for test in tests:
        if verbose:
            print(f"\n=== Processing {test.upper()} test ===")
        memory_data: Dict[str, List[Tuple[int, float]]] = {}
        perf_data: Dict[str, List[Tuple[int, float, float]]] = {}
        summary_slice: Dict[str, Dict[str, float]] = {}

        for language, run_dir in run_entries:
            memory_data[language] = load_memory_data(run_dir, language, test)
            perf_data[language] = load_timeseries(run_dir, test)
            summary_slice[language] = summary_cache.get(language, {}).get(test, {})

        output_file = output_dir / f"comparison_{test}.png"
        plot_comparison(
            languages_in_run,
            test,
            duration_hint,
            memory_data,
            perf_data,
            summary_slice,
            output_file,
        )


def main() -> None:
    args = parse_args()

    runs = resolve_run_directories(args)
    if not runs:
        print("No benchmark runs found; nothing to plot.")
        return

    generate_plots(runs, args.tests, args.output_dir, args.duration)

if __name__ == "__main__":
    main()
