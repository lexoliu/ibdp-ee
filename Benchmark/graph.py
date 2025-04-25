#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
import sys
import os
import re

def plot(csv_path):
    if not os.path.exists(csv_path):
        return

    task = re.sub(r'^benchmark_|\.csv$', '', os.path.basename(csv_path))
    df = pd.read_csv(csv_path)
    df["command"] = df["command"].str.replace(r"bash .*/run.sh ", "", regex=True)
    df["mean"] = df["mean"] * 1000

    plt.figure(figsize=(6, 4))
    plt.bar(df["command"], df["mean"], color="skyblue", edgecolor="black")
    plt.title(f"Benchmark: {task}")
    plt.ylabel("Execution Time (ms)")
    plt.xlabel("Language")
    plt.tight_layout()
    plt.savefig(f"benchmark_{task}.png")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(1)
    plot(sys.argv[1])