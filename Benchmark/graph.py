#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
import sys
import os
import re

def plot(csv_path):
    if not os.path.exists(csv_path):
        print(f"❌ File not found: {csv_path}")
        return

    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.size": 12
    })

    task = re.sub(r'^benchmark_|\.csv$', '', os.path.basename(csv_path))
    df = pd.read_csv(csv_path)

    def extract_language(cmd):
        if cmd.startswith("java "):
            return "Java"
        match = re.search(r"./(\w+)_", cmd)
        if match:
            return match.group(1).capitalize()
        return "Unknown"

    df["language"] = df["command"].apply(extract_language)
    df["mean"] *= 1000
    df["stddev"] *= 1000
    df = df.sort_values(by="mean", ascending=True).reset_index(drop=True)

    plt.figure(figsize=(8, 5))
    bars = plt.bar(df["language"], df["mean"], yerr=df["stddev"], capsize=6,
                   color="#7EC8E3", edgecolor="black", error_kw=dict(ecolor='darkred', lw=2))

    for i, (mean_val, std_val) in enumerate(zip(df["mean"], df["stddev"])):
        plt.text(i, mean_val + std_val + 1.5, f"{mean_val:.2f}", ha='center', va='bottom', fontsize=10, fontweight='medium')

    plt.title(f"Benchmark: {task}", fontsize=15, weight='bold')
    plt.ylabel("Execution Time (ms)", fontsize=12)
    plt.xlabel("Language", fontsize=12)
    plt.xticks(rotation=0)
    plt.grid(axis='y', linestyle='--', alpha=0.4)
    plt.tight_layout()

    output_path = f"benchmark_{task}.pdf"
    plt.savefig(output_path, format='pdf')
    plt.close()
    print(f"✅ Saved PDF to: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: ./plot.py <benchmark.csv>")
        sys.exit(1)
    plot(sys.argv[1])