# IBDP Extended Essay

This repository has two main parts:

- `Paper/` contains the essay itself, written in Typst.
- `Benchmark/` contains the benchmark harness and reference service implementations used to produce the figures and measurements discussed in the essay.

If you only want to build the paper, you can ignore most of the benchmark code.

## Repository Layout

- `Paper/main.typ` - the main Typst source
- `Paper/references.bib` - bibliography database
- `Paper/build.sh` - the simplest way to compile the paper
- `Benchmark/` - benchmark harness, k6 scripts, and language implementations
- `Benchmark/linux_results/` - checked-in benchmark outputs used by the paper
- `gc_pause_distribution.png` - GC pause chart included by the paper

## Prerequisites

To build the paper, you need:

- `typst` on `PATH`

This repository has been verified with:

```bash
typst 0.14.2
```

The paper imports Typst preview packages and reads figures from outside `Paper/`, so the compile command must set the project root correctly.

## Build the Paper

From the repository root, run:

```bash
bash Paper/build.sh
```

This compiles:

- input: `Paper/main.typ`
- output: `Paper/main.pdf`

The build script changes into `Paper/` and runs:

```bash
typst compile --root .. ./main.typ
```

If you prefer to run Typst directly from the repository root, this is equivalent:

```bash
typst compile --root . Paper/main.typ Paper/main.pdf
```

## Clean Rebuild

There is no special build cache in this repository that needs manual cleanup for normal paper edits. If the PDF already exists, rebuilding simply overwrites `Paper/main.pdf`.

## Benchmark Harness

The benchmark workflow is documented separately in:

- `Benchmark/README.md`

That README covers:

- manager/client architecture
- running k6 workloads
- plotting benchmark results
- GC tracing
- troubleshooting benchmark runs

## Notes

- Keep the repository layout intact when building. The paper references files in `Benchmark/` and the repository root.
- If you change bibliography entries, rebuild the PDF to refresh citations.
- If you update benchmark plots or GC analysis outputs, rebuild the paper after regenerating those assets.
