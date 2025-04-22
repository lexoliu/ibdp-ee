import os
import subprocess
import time
import py_spy
import matplotlib.pyplot as plt
from pathlib import Path

def generate_large_test_file(file_path, size_bytes=1024*1024*1024):
    """Generate a large test file of specified size (1GB by default)"""
    print(f"Generating large test file ({size_bytes/1024/1024/1024:.2f} GB) at {file_path}...")
    with open(file_path, 'wb') as f:
        chunk_size = 1024 * 1024  # 1MB chunks
        remaining_bytes = size_bytes
        while remaining_bytes > 0:
            write_size = min(chunk_size, remaining_bytes)
            f.write(os.urandom(write_size))
            remaining_bytes -= write_size
    print(f"Large test file generated: {file_path}")

def run_benchmarks(base_dir="Benchmark"):
    """Run performance tests and generate flamegraphs."""
    large_file_path = os.path.join(base_dir, "large_file.bin")
    generate_large_test_file(large_file_path)

    languages = ["Go", "Java", "Python", "Rust"]
    test_types = ["Compute", "IO"]
    results = {}

    try:
        for lang in languages:
            lang_dir = os.path.join(base_dir, lang)
            if not os.path.exists(lang_dir):
                print(f"Directory does not exist: {lang_dir}")
                continue

            results[lang] = {}

            for test_type in test_types:
                test_dir = os.path.join(lang_dir, test_type)
                if not os.path.exists(test_dir):
                    print(f"Directory does not exist: {test_dir}")
                    continue

                results[lang][test_type] = {}

                test_files = [os.path.join(test_dir, f) for f in os.listdir(test_dir) if os.path.isfile(os.path.join(test_dir, f))]

                for test_file in test_files:
                    test_name = os.path.basename(test_file)
                    print(f"Running test: {test_file}")

                    start_time = time.time()
                    process = None

                    try:
                        if lang == "Go":
                            process = subprocess.Popen(["go", "run", test_file])
                        elif lang == "Java":
                            subprocess.run(["javac", test_file], check=True)
                            class_name = os.path.splitext(test_name)[0]
                            process = subprocess.Popen(["java", "-cp", test_dir, class_name])
                        elif lang == "Python":
                            process = subprocess.Popen(["python", test_file])
                        elif lang == "Rust":
                            out_file = os.path.join(test_dir, os.path.splitext(test_name)[0])
                            subprocess.run(["rustc", test_file, "-o", out_file], check=True)
                            process = subprocess.Popen([out_file])

                        if process:
                            pid = process.pid
                            flamegraph_path = f"{test_dir}/{os.path.splitext(test_name)[0]}_flamegraph.svg"

                            # 使用 perf (Linux) 或 dtrace (macOS) 生成性能数据
                            if os.system("uname -s | grep -qi linux") == 0:
                                perf_data = f"{test_dir}/{test_name}.perf"
                                subprocess.run(["perf", "record", "-F", "99", "-p", str(pid), "-o", perf_data], check=True)
                                subprocess.run(["perf", "script", "-i", perf_data, "|", "flamegraph.pl", ">", flamegraph_path], shell=True)
                            else:
                                dtrace_script = f"{test_dir}/{test_name}.dtrace"
                                subprocess.run(["dtrace", "-n", f'profile-997 /pid == {pid}/ {{ @[ustack()] = count(); }}', "-o", dtrace_script], check=True)
                                subprocess.run(["flamegraph.pl", dtrace_script, ">", flamegraph_path], shell=True)

                            process.wait()

                            execution_time = time.time() - start_time
                            results[lang][test_type][test_name] = {
                                "execution_time": execution_time,
                                "flamegraph_path": flamegraph_path
                            }

                            print(f"Test completed: {test_file}, duration: {execution_time:.2f} seconds")
                            print(f"Generated flamegraph: {flamegraph_path}")

                    except Exception as e:
                        print(f"Test execution failed: {test_file}")
                        print(f"Error message: {str(e)}")
                        if process and process.poll() is None:
                            process.terminate()

        generate_comparison_charts(results)

    finally:
        if os.path.exists(large_file_path):
            print(f"Removing large test file: {large_file_path}")
            os.remove(large_file_path)

    return results

def generate_comparison_charts(results):
    """Generate comparison charts"""
    test_types = ["Compute", "IO"]

    for test_type in test_types:
        plt.figure(figsize=(12, 6))

        languages = []
        times = []

        for lang, lang_data in results.items():
            if test_type in lang_data:
                for test_name, test_data in lang_data[test_type].items():
                    languages.append(f"{lang}\n{test_name}")
                    times.append(test_data["execution_time"])

        plt.bar(languages, times)
        plt.title(f"{test_type} Performance Comparison")
        plt.ylabel("Execution Time (seconds)")
        plt.xlabel("Language / Test")
        plt.xticks(rotation=45)
        plt.tight_layout()

        chart_path = f"Benchmark/{test_type}_comparison.png"
        plt.savefig(chart_path)
        print(f"Generated comparison chart: {chart_path}")

if __name__ == "__main__":
    run_benchmarks()
