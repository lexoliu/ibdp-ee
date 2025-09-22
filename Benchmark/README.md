# Benchmark Harness

This directory provides a small harness for exercising the reference language
implementations with [k6](https://k6.io/) load tests. The workflow is split into
three layers so that the service under test can run on a different host from the
benchmark runner.

## Prerequisites

- Python 3.9+
- `k6` installed and available on `PATH`
- Language build tools for the services you intend to run (e.g. Maven, Go tool
  chain, Rust tool chain)

All Python entry points are self-contained; no additional libraries are
required beyond the Python standard library.

Quick setup helpers:

- `install_server.sh` – Installs Java 21, Maven, Go, Rust, and curl on
  Linux/macOS hosts that will run the services and manager.
- `install_client.sh` – Installs Python 3, required Python libraries
  (`matplotlib`, `numpy`), and k6 on the machine that will run the benchmark
  client.

## Components

- `manager.py` – REST API that starts/stops a language service on the host where
  the services live.
- `benchmark.py` – Runs the k6 workloads against an already running service and
  produces structured CSV/JSON output. Can be used as a CLI or imported as a
  helper.
- `run.py` – Client-side orchestrator that talks to the manager, runs the
  benchmarks for each language, and optionally generates plots.
- `plot_comparison.py` – Consumes the structured results and emits comparison
  plots across languages/tests.
- `start_service.py` / `service_utils.py` – Shared helpers for local process
  management.

## Typical Deployment

1. **Server host** – Run `manager.py` so the services can be started remotely.
2. **Client/runner host** – Run `run.py` to execute the full benchmark cycle. It
   contacts the manager, waits for readiness, runs k6 workloads via
   `benchmark.py`, and tears the service down before moving to the next
   language.

The client and server may be the same machine for local testing.

## Starting the Manager

```bash
python manager.py --bind 0.0.0.0 --port 9000
```

Important arguments:

- `--bind` – Interface to listen on (default `0.0.0.0`).
- `--port` – Manager port (default `9000`).

Endpoints exposed:

- `POST /start` – Start a service. JSON body mirrors the parameters accepted by
  `start_service.py`. The response includes the service PID and current memory
  usage in MB.
- `POST /stop` – Stop the currently running service, if any.
- `GET /status` – Report whether a service is running, its PID, and the latest
  measured memory usage in MB.

## Running the Full Benchmark

On the client machine:

```bash
python run.py \
  --manager-url http://SERVER:9000 \
  --client-host SERVER \
  --mode normal
```

Common flags:

- `--languages` – Languages to benchmark (default `java go rust`).
- `--tests` – Which k6 scripts to run (`prime`, `light`, `kv`).
- `--mode` – Preset for duration/repetition. `debug` runs a single 10 second
  smoke test. `normal` performs three 10 minute runs and keeps the final one.
- `--duration` / `--repeats` – Explicit overrides that replace the mode
  defaults.
- `--vus` – Virtual users for k6 (default `64`).
- `--keep-raw` – Preserve the raw k6 JSON exports instead of deleting them.
- `--plots-dir` – Write comparison plots to a custom directory (defaults to
  `results/plots/<timestamp>`).
- `--skip-plots` – Skip the plotting phase entirely (useful for headless runs).
- `--manager-url` – Override the manager endpoint (defaults to
  `http://<service-host>:<manager-port>`). Use with `--manager-port` if the
  manager listens on a non-default port.
- `--health-host` – Hostname/IP the manager uses for health checks. Defaults to
  the service bind host (or `127.0.0.1` when binding to all interfaces).
- `--memory-interval` – Sampling interval when fetching memory usage from the
  manager (default `1` second).

The runner writes each benchmark into `results/<language>/<timestamp>/` with:

- `results.json` – Summary metrics per test and metadata about the run.
- `<test>_timeseries.csv` – Requests-per-second and latency per second.
- `<test>_memory.csv` – Average RSS (MB) per second while the test executed.
- Optional raw k6 outputs if `--keep-raw` is set.

## Running a Single Suite Manually

To exercise one language manually when the service is already running:

```bash
python benchmark.py java --mode debug --base-url http://127.0.0.1:8080
```

This generates the same CSV/JSON artifacts without touching the manager.

## Plotting Only

`plot_comparison.py` will discover the latest results per language underneath
`results/`, or you can point it at specific run directories:

```bash
python plot_comparison.py \
  --run-dirs results/java/20240101_120000 results/go/20240101_121500 \
  --tests prime kv \
  --output-dir results/plots/manual
```

## Health Checks and Modes

The harness checks the `/echo` endpoint for readiness, matching the k6 scripts.
During `normal` mode the suite repeats each test twice and uses the last
attempt's artifacts. In `debug` mode only a single short run is executed.

## Logs

Service stdout/stderr are captured into `results/logs/<language>_<timestamp>.log`
so you can inspect startup issues or crashes after the run completes.

All services start in quiet mode to avoid skewing benchmarks with console I/O.
Set the `SERVER_LOG=1` environment variable (or `true`/`on`) before launching a
service if you need verbose startup or request logging.

## Troubleshooting

- Ensure the manager host can reach language build tools and has open ports.
- For remote runs, confirm the client can reach the service via the computed
  base URL (use `--client-host` / `--client-port` to override as needed).
- Use `curl http://SERVER:9000/status` to inspect manager state.
- Run in `--mode debug` for a quick smoke test before committing to long runs.
