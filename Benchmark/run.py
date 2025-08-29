#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基准跑法（固定使用已有 k6 脚本）：
- 顺序在 8080 端口启动 Java/Go/Rust（每次只跑一个）
- 依次跑 prime / light / kv 三组
- 采样 RSS 内存
- 生成三组图：吞吐(req/s)、平均延迟(ms)、内存(MB)

改进：
- k6 原始 JSON 在本地逐行聚合为“按秒”数据后 **立即删除**，内存中保存聚合后的 DataFrame 用于最终跨语言对比绘图
- 设 KEEP_RAW=1 可保留 *.k6.json / *.summary.json / *_mem.csv
- 健康检查仅使用 POST /echo
- 启动前强制释放 8080（SIGTERM→SIGKILL）
- Java 用 mvn spring-boot:run；Go 用 go run .；Rust 用 cargo run --release
"""

import os, sys, time, json, shlex, signal, threading, subprocess, socket, re
from pathlib import Path
from datetime import datetime

import pandas as pd
import matplotlib.pyplot as plt

# -------------------- 基本配置 --------------------
ROOT = Path(__file__).resolve().parent
JAVA_DIR = ROOT / "java"
GO_DIR   = ROOT / "go"
RUST_DIR = ROOT / "rust"
K6_DIR   = ROOT / "k6"
RESULTS  = ROOT / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

# k6 脚本路径（使用你已有的文件）
K6_PRIME = K6_DIR / "prime.js"
K6_LIGHT = K6_DIR / "light.js"
K6_KV    = (K6_DIR / "kv.js") if (K6_DIR / "kv.js").exists() else (K6_DIR / "kv" / "kv.js")

VUS      = int(os.environ.get("VUS", "64"))
DURATION = os.environ.get("DURATION", "60s")

# 快速验流程：DEBUG=1 时收紧参数
DEBUG = os.environ.get("DEBUG", "0") in ("1", "true", "True", "YES", "yes")

if DEBUG:
    # 仅当用户没手动覆盖时，才改成轻量
    if "VUS" not in os.environ:
        VUS = 4
    if "DURATION" not in os.environ:
        DURATION = "3s"

BASE_URL    = "http://127.0.0.1:8080"
HEALTH_PATH = "/echo"            # 仅用 POST /echo 探活
K6_BIN      = "k6"               # 确保 PATH 能找到 k6
KEEP_RAW    = os.environ.get("KEEP_RAW", "0") == "1"

# -------------------- 工具函数 --------------------
def popen(cmd: str, cwd: Path=None, env=None, stdout=None, stderr=None):
    return subprocess.Popen(
        cmd, cwd=str(cwd) if cwd else None, env=env,
        shell=True, stdout=stdout, stderr=stderr,
        preexec_fn=os.setsid if os.name != 'nt' else None
    )

def kill_tree(p: subprocess.Popen):
    if not p: return
    try:
        if os.name == 'nt':
            p.terminate()
        else:
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)
    except Exception:
        pass

def port_busy(port: int) -> bool:
    s = socket.socket(); s.settimeout(0.2)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()

# 可选：丢弃首尾的“半秒/预热”噪声（环境变量控制）
TRIM_HEAD_SEC = int(os.environ.get("TRIM_HEAD_SEC", "0"))   # e.g. 1~2
TRIM_TAIL_SEC = int(os.environ.get("TRIM_TAIL_SEC", "0"))   # e.g. 1

def aggregate_to_compact_csv(k6_jsonl: Path, mem_csv: Path, out_csv: Path):
    """
    将 k6 JSONL + mem.csv 聚合成“每秒”的紧凑 CSV，时间轴为“相对秒”（该任务起点=0）。
    输出列：sec,throughput,latency_ms,rss_kb
    """
    # 1) RSS -> {abs_sec: rss_kb}
    rss_by_sec = {}
    try:
        with mem_csv.open("r") as f:
            f.readline()
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 2:
                    try:
                        sec = int(parts[0]); rss = int(parts[1])
                        rss_by_sec[sec] = rss
                    except: pass
    except FileNotFoundError:
        pass

    # 2) k6 JSONL -> thr/lat（abs_sec 桶）
    thr, lat_sum, lat_cnt = {}, {}, {}
    with k6_jsonl.open("r") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                obj = json.loads(line)
            except: 
                continue
            if obj.get("type") != "Point": 
                continue
            metric = obj.get("metric"); data = obj.get("data", {})
            sec = _parse_k6_time_to_sec(data.get("time", 0))
            if sec <= 0: 
                continue
            val = data.get("value", None)
            if metric == "http_reqs":
                thr[sec] = thr.get(sec, 0) + 1
            elif metric == "http_req_duration" and val is not None:
                try:
                    v = float(val)  # ms
                except:
                    continue
                lat_sum[sec] = lat_sum.get(sec, 0.0) + v
                lat_cnt[sec] = lat_cnt.get(sec, 0) + 1

    # 3) 统一得到该任务的起点（abs -> rel）
    keys = set(thr.keys()) | set(lat_sum.keys()) | set(rss_by_sec.keys())
    if not keys:
        with out_csv.open("w") as w:
            w.write("sec,throughput,latency_ms,rss_kb\n")
        return

    min_sec = min(keys)
    max_sec = max(keys)

    # 4) 写 compact：相对秒，并按需裁剪首尾
    with out_csv.open("w") as w:
        w.write("sec,throughput,latency_ms,rss_kb\n")
        for abs_s in range(min_sec, max_sec + 1):
            rel = abs_s - min_sec
            if rel < TRIM_HEAD_SEC:
                continue
            # 注意尾部裁剪是相对“rel_max”
            if (max_sec - min_sec - rel) < TRIM_TAIL_SEC:
                continue

            t = thr.get(abs_s, 0)
            l = (lat_sum[abs_s] / lat_cnt[abs_s]) if abs_s in lat_sum and lat_cnt[abs_s] > 0 else ""
            r = rss_by_sec.get(abs_s, "")
            w.write(f"{rel},{t},{l},{r}\n")

def pids_on_port(port: int):
    try:
        out = subprocess.check_output(f"lsof -iTCP:{port} -sTCP:LISTEN -n -P", shell=True, text=True)
        return list({int(line.split()[1]) for line in out.splitlines()[1:] if line.split()})
    except Exception:
        try:
            out = subprocess.check_output(f"fuser -n tcp {port}", shell=True, text=True, stderr=subprocess.DEVNULL)
            return [int(x) for x in re.findall(r"\d+", out)]
        except Exception:
            return []

def ensure_port_free(port=8080, wait_after_kill=1.0):
    if not port_busy(port):
        return
    print(f"!! port {port} busy, trying to free...")
    pids = pids_on_port(port)
    for pid in pids:
        try: os.kill(pid, signal.SIGTERM)
        except Exception: pass
    for _ in range(20):
        if not port_busy(port):
            print(f"-- port {port} is free (after SIGTERM)")
            return
        time.sleep(0.2)
    # 强杀
    pids = pids_on_port(port)
    for pid in pids:
        try: os.kill(pid, signal.SIGKILL)
        except Exception: pass
    time.sleep(wait_after_kill)
    assert not port_busy(port), f"port {port} still busy after SIGKILL"
    print(f"-- port {port} is free (after SIGKILL)")

def curl_post_echo_ok(url: str) -> bool:
    cmd = f"curl -fsS -X POST {shlex.quote(url)} -H 'Content-Type: text/plain' -d 'ok'"
    return subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0

def wait_echo_health(base_url: str, path: str, proc: subprocess.Popen,
                     port: int = 8080, port_wait: int = 60, timeout: int = 120) -> bool:
    # 1) 等端口
    deadline = time.time() + port_wait
    while time.time() < deadline:
        if proc.poll() is not None:
            print("!! process exited before port opened")
            return False
        if port_busy(port):
            break
        time.sleep(0.2)
    if not port_busy(port):
        return False
    # 2) 轮询 /echo
    start = time.time()
    while time.time() - start < timeout:
        if proc.poll() is not None:
            print("!! process exited during healthcheck")
            return False
        if curl_post_echo_ok(base_url + path):
            return True
        time.sleep(1)
    return False

def sample_rss(pid: int, out_csv: Path, stop_evt: threading.Event):
    with out_csv.open("w") as f:
        f.write("ts,rss_kb\n")
        while not stop_evt.is_set():
            try:
                proc = subprocess.run(f"ps -o rss= -p {pid}",
                                      shell=True, capture_output=True, text=True)
                rss = proc.stdout.strip() or "0"
                f.write(f"{int(time.time())},{rss}\n"); f.flush()
            except Exception:
                pass
            time.sleep(1)

def run_k6(script_path: Path, tag_prefix: str):
    json_out    = RESULTS / f"{tag_prefix}.k6.json"
    summary_out = RESULTS / f"{tag_prefix}.summary.json"
    env = os.environ.copy()
    env["K6_BASE_URL"] = BASE_URL
    env["VUS"] = str(VUS)
    env["DURATION"] = DURATION
    cmd = (
        f'{K6_BIN} run '
        f'--vus {VUS} --duration {DURATION} '
        f'--summary-export {shlex.quote(str(summary_out))} '
        f'--out json={shlex.quote(str(json_out))} '
        f'{shlex.quote(str(script_path))}'
    )
    print(f">> k6: {script_path.name}")
    proc = subprocess.run(cmd, shell=True, env=env)
    if proc.returncode not in (0, 99):
        raise RuntimeError(f"k6 failed: {script_path} (exit {proc.returncode})")
    if proc.returncode == 99:
        print(f"!! k6 thresholds breached for {script_path.name} (exit 99) — continuing")
    return json_out, summary_out

# ---------- JSON 按秒聚合 ----------
def _parse_k6_time_to_sec(traw):
    """
    k6 json 输出的 data.time 可能是：
      - RFC3339 字符串，如 '2025-08-29T01:23:45.123456789Z'
      - 数字（秒/毫秒/纳秒）
    统一转为 int 秒。
    """
    if isinstance(traw, (int, float)):
        v = float(traw)
        if v > 1e12:      # ns
            return int(v / 1_000_000_000)
        if 1e6 < v < 1e9: # ms
            return int(v / 1_000)
        return int(v)     # s
    if isinstance(traw, str):
        s = traw.strip()
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        try:
            dt = datetime.fromisoformat(s)
            return int(dt.timestamp())
        except Exception:
            return 0
    return 0

def parse_k6_timeseries(jsonl_path: Path):
    """
    把 k6 --out json 的逐样本流聚合成“每秒”的两条序列：
      - throughput(req/s) 由 http_reqs 计数
      - latency_ms        由 http_req_duration 做平均
    返回 (thr_df, lat_df)
    """
    through, lat_sum, lat_cnt = {}, {}, {}
    with jsonl_path.open("r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("type") != "Point":
                continue
            metric = obj.get("metric")
            data   = obj.get("data", {})
            t_sec  = _parse_k6_time_to_sec(data.get("time", 0))
            if t_sec <= 0:
                continue
            if metric == "http_reqs":
                through[t_sec] = through.get(t_sec, 0) + 1
            elif metric == "http_req_duration":
                try:
                    v = float(data.get("value", 0.0))  # ms
                except Exception:
                    continue
                lat_sum[t_sec] = lat_sum.get(t_sec, 0.0) + v
                lat_cnt[t_sec] = lat_cnt.get(t_sec, 0) + 1

    if not through and not lat_sum:
        return pd.DataFrame(), pd.DataFrame()

    keys = list(through.keys()) + list(lat_sum.keys())
    t_min, t_max = min(keys), max(keys)
    idx = pd.Index(range(t_min, t_max + 1), name="sec")

    thr = pd.Series(through, name="throughput").reindex(idx, fill_value=0).to_frame()
    lat = pd.Series({t: (lat_sum[t] / lat_cnt[t]) for t in lat_sum}, name="latency_ms").reindex(idx).to_frame()
    return thr, lat

def load_mem_df(mem_csv: Path):
    df = pd.read_csv(mem_csv)  # ts,rss_kb
    df["sec"] = df["ts"]
    return df.set_index("sec")[["rss_kb"]]


# -------------------- 启动命令 --------------------
def java_run_cmd() -> str:
    jvm_args = "-Xms512m -Xmx1024m -XX:+UseG1GC -XX:+AlwaysPreTouch"
    return ("mvn -q -DskipTests "
            f"-Dspring-boot.run.arguments=--server.port=8080 "
            f"-Dspring-boot.run.jvmArguments='{jvm_args}' "
            "spring-boot:run")

def go_run_cmd() -> str:
    return "go run ."

def rust_run_cmd() -> str:
    return "cargo run --release"
def load_compact(compact_csv: Path):
    secs, thr, lat, rss = [], [], [], []
    with compact_csv.open("r") as f:
        f.readline()
        for line in f:
            parts = line.strip().split(",")
            if len(parts) >= 4:
                try: s = int(parts[0])
                except: continue
                secs.append(s)
                try: thr.append(int(parts[1]))
                except: thr.append(0)
                try: lat.append(float(parts[2]))
                except: lat.append(float("nan"))
                try: rss.append(float(parts[3]) / 1024.0)
                except: rss.append(float("nan"))
    return secs, thr, lat, rss

def plot_group(group_title: str, series: dict):
    plt.rcParams.update({'figure.dpi': 140})
    fig1, ax1 = plt.subplots(); fig2, ax2 = plt.subplots(); fig3, ax3 = plt.subplots()

    for lang, paths in series.items():
        secs, thr, lat, rss = load_compact(paths["compact"])
        if secs:
            ax1.plot(secs, thr, label=lang)
            ax2.plot(secs, lat, label=lang)
            ax3.plot(secs, rss, label=lang)

    ax1.set_title(f'{group_title}: Throughput'); ax1.set_ylabel('req/s'); ax1.legend()
    ax2.set_title(f'{group_title}: Latency');    ax2.set_ylabel('ms');    ax2.legend()
    ax3.set_title(f'{group_title}: Memory');     ax3.set_ylabel('MB');    ax3.legend()
    for ax in (ax1, ax2, ax3): ax.set_xlabel('Time (s)'); ax.grid(True)

    fig1.savefig(RESULTS / f'{group_title}_throughput.png')
    fig2.savefig(RESULTS / f'{group_title}_latency.png')
    fig3.savefig(RESULTS / f'{group_title}_memory.png')
    plt.close(fig1); plt.close(fig2); plt.close(fig3)

# -------------------- 主流程 --------------------
def bench_one(name: str, workdir: Path, run_cmd: str):
    ensure_port_free(8080)
    print(f"\n==== {name}: start on 8080 ====")
    log_path = RESULTS / f"{name}.log"
    proc = popen(run_cmd, cwd=workdir, stdout=log_path.open("w"), stderr=subprocess.STDOUT)
    print("Health check: waiting for POST /echo ...")
    if not wait_echo_health(BASE_URL, HEALTH_PATH, proc):
        kill_tree(proc); raise RuntimeError(f"{name} health check failed: POST {HEALTH_PATH}")

    out = {}
    try:
        for group, script in [("prime", K6_PRIME), ("light", K6_LIGHT), ("kv", K6_KV)]:
            if not script.exists():
                raise FileNotFoundError(f"k6 script not found: {script}")
            print(f"-- {name} · {group} --")

            # 1) 采样内存到 CSV
            mem_csv = RESULTS / f"{name}_{group}_mem.csv"
            stop_evt = threading.Event()
            t = threading.Thread(target=sample_rss, args=(proc.pid, mem_csv, stop_evt), daemon=True)
            t.start()

            k6_json, k6_sum = run_k6(script, f"{name}_{group}")
            stop_evt.set(); t.join(timeout=5)

            compact = RESULTS / f"{name}_{group}_compact.csv"
            aggregate_to_compact_csv(k6_json, mem_csv, compact)

            # 非对比模式下，立刻删除大文件，释放磁盘
            if not KEEP_RAW:
                try: k6_json.unlink(missing_ok=True)
                except Exception: pass
                try: k6_sum.unlink(missing_ok=True)
                except Exception: pass
                try: mem_csv.unlink(missing_ok=True)
                except Exception: pass

            # 把“紧凑文件”作为后续画图的数据来源
            out[group] = {"compact": compact}
            # 5) 根据策略删除中间产物
            if not KEEP_RAW:
                for p in [k6_json, k6_sum, mem_csv]:
                    try:
                        Path(p).unlink(missing_ok=True)
                    except Exception:
                        pass

    finally:
        print(f"== stopping {name} ==")
        kill_tree(proc); time.sleep(2); ensure_port_free(8080)

    return out

def main():
    # all_series[group][lang] = {'thr':DF,'lat':DF,'mem':DF}
    all_series = {"prime":{}, "light":{}, "kv":{}}

    if JAVA_DIR.exists():
        r = bench_one("JAVA", JAVA_DIR, java_run_cmd())
        for g in r: all_series[g]["JAVA"] = r[g]

    if GO_DIR.exists():
        r = bench_one("GO", GO_DIR, go_run_cmd())
        for g in r: all_series[g]["GO"] = r[g]

    if RUST_DIR.exists():
        r = bench_one("RUST", RUST_DIR, rust_run_cmd())
        for g in r: all_series[g]["RUST"] = r[g]

    print("\n== plotting ==")
    for g in ["prime","light","kv"]:
        if all_series[g]:
            plot_group(g.upper(), all_series[g])

    print(f"\n✅ Done: {RESULTS}\n(聚合后的图已生成；原始大文件默认已删除，设置 KEEP_RAW=1 可保留)")
    if KEEP_RAW:
        print("⚠️ 你开启了 KEEP_RAW=1，将保留 *.k6.json / *.summary.json / *_mem.csv。")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)