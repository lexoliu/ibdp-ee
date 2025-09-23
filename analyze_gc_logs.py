#!/usr/bin/env python3
"""
GC Log Analysis Script for Research Paper
Analyzes Go and Java garbage collection logs to extract insights
"""

import re
import json
import statistics
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime

def analyze_go_gc_log(file_path):
    """Analyze Go GC log format: gc N @Xs Y%: times clock, cpu_times, memory_info"""
    print(f"\n=== Analyzing Go GC Log: {file_path} ===")
    
    gc_events = []
    benchmark_phases = []
    current_phase = None
    
    with open(file_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            
            # Detect benchmark phase markers
            if '# benchmark' in line:
                current_phase = line_num
                benchmark_phases.append(line_num)
                continue
                
            # Parse GC events
            gc_match = re.match(r'gc (\d+) @([\d.]+)s (\d+)%: ([\d.+]+) ms clock, ([\d./+]+) ms cpu, (\d+)->(\d+)->(\d+) MB, (\d+) MB goal.*?(\d+) P', line)
            if gc_match:
                gc_num, timestamp, gc_percent, clock_time, cpu_time, heap_before, heap_after, heap_live, heap_goal, procs = gc_match.groups()
                
                gc_events.append({
                    'gc_num': int(gc_num),
                    'timestamp': float(timestamp),
                    'gc_percent': int(gc_percent),
                    'clock_time': float(clock_time.split('+')[0]) if '+' in clock_time else float(clock_time),
                    'heap_before': int(heap_before),
                    'heap_after': int(heap_after), 
                    'heap_live': int(heap_live),
                    'heap_goal': int(heap_goal),
                    'procs': int(procs),
                    'phase': current_phase,
                    'line_num': line_num
                })
    
    # Analysis
    if not gc_events:
        print("No GC events found")
        return {}
        
    total_events = len(gc_events)
    clock_times = [e['clock_time'] for e in gc_events]
    heap_sizes = [e['heap_live'] for e in gc_events]
    gc_percentages = [e['gc_percent'] for e in gc_events]
    
    # Phase analysis
    phase_stats = defaultdict(list)
    for event in gc_events:
        phase_key = f"phase_{event['phase']}" if event['phase'] else "startup"
        phase_stats[phase_key].append(event)
    
    print(f"Total GC events: {total_events}")
    print(f"Benchmark phases detected: {len(benchmark_phases)}")
    print(f"Average GC time: {statistics.mean(clock_times):.3f}ms")
    print(f"Median GC time: {statistics.median(clock_times):.3f}ms")
    print(f"Max GC time: {max(clock_times):.3f}ms")
    print(f"Average heap size: {statistics.mean(heap_sizes):.1f}MB")
    print(f"Max heap size: {max(heap_sizes)}MB")
    print(f"Average GC overhead: {statistics.mean(gc_percentages):.1f}%")
    
    # Frequency analysis
    if len(gc_events) > 1:
        intervals = [gc_events[i]['timestamp'] - gc_events[i-1]['timestamp'] for i in range(1, len(gc_events))]
        print(f"Average GC interval: {statistics.mean(intervals):.3f}s")
        print(f"GC frequency: {1/statistics.mean(intervals):.1f} GCs/second")
    
    return {
        'total_events': total_events,
        'avg_gc_time': statistics.mean(clock_times),
        'median_gc_time': statistics.median(clock_times),
        'max_gc_time': max(clock_times),
        'avg_heap_size': statistics.mean(heap_sizes),
        'max_heap_size': max(heap_sizes),
        'avg_gc_overhead': statistics.mean(gc_percentages),
        'phase_count': len(benchmark_phases),
        'phase_stats': dict(phase_stats)
    }

def analyze_java_gc_log(file_path):
    """Analyze Java G1 GC log format"""
    print(f"\n=== Analyzing Java GC Log: {file_path} ===")
    
    gc_events = []
    concurrent_events = []
    heap_info = {}
    
    with open(file_path, 'r') as f:
        content = f.read()
        
    # Extract initialization info
    init_match = re.search(r'Heap Min Capacity: (\d+)G.*?Heap Max Capacity: (\d+)G.*?Parallel Workers: (\d+)', content, re.DOTALL)
    if init_match:
        heap_info = {
            'min_heap': int(init_match.group(1)),
            'max_heap': int(init_match.group(2)), 
            'parallel_workers': int(init_match.group(3))
        }
    
    # Parse pause events (stop-the-world)
    pause_pattern = r'\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3})\+\d{4}\].*?GC\((\d+)\) Pause.*?(\d+)M->(\d+)M\((\d+)M\) ([\d.]+)ms'
    for match in re.finditer(pause_pattern, content):
        timestamp, gc_num, heap_before, heap_after, heap_total, pause_time = match.groups()
        gc_events.append({
            'timestamp': timestamp,
            'gc_num': int(gc_num),
            'heap_before': int(heap_before),
            'heap_after': int(heap_after),
            'heap_total': int(heap_total),
            'pause_time': float(pause_time),
            'type': 'pause'
        })
    
    # Parse concurrent events
    concurrent_pattern = r'\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3})\+\d{4}\].*?GC\((\d+)\) (Concurrent.*?) ([\d.]+)ms'
    for match in re.finditer(concurrent_pattern, content):
        timestamp, gc_num, phase, duration = match.groups()
        concurrent_events.append({
            'timestamp': timestamp,
            'gc_num': int(gc_num),
            'phase': phase,
            'duration': float(duration),
            'type': 'concurrent'
        })
    
    # Analysis
    if not gc_events:
        print("No pause GC events found")
        return {}
        
    pause_times = [e['pause_time'] for e in gc_events]
    heap_reductions = [e['heap_before'] - e['heap_after'] for e in gc_events]
    heap_utilizations = [e['heap_after'] / e['heap_total'] * 100 for e in gc_events]
    
    print(f"Heap configuration: {heap_info.get('min_heap', 'N/A')}G min, {heap_info.get('max_heap', 'N/A')}G max")
    print(f"Parallel workers: {heap_info.get('parallel_workers', 'N/A')}")
    print(f"Total pause events: {len(gc_events)}")
    print(f"Total concurrent events: {len(concurrent_events)}")
    print(f"Average pause time: {statistics.mean(pause_times):.3f}ms")
    print(f"Median pause time: {statistics.median(pause_times):.3f}ms") 
    print(f"Max pause time: {max(pause_times):.3f}ms")
    print(f"Average memory freed: {statistics.mean(heap_reductions):.1f}MB")
    print(f"Average heap utilization: {statistics.mean(heap_utilizations):.1f}%")
    
    # Concurrent phase analysis
    concurrent_phases = Counter([e['phase'] for e in concurrent_events])
    print(f"Concurrent phases: {dict(concurrent_phases)}")
    
    return {
        'heap_config': heap_info,
        'total_pause_events': len(gc_events),
        'total_concurrent_events': len(concurrent_events),
        'avg_pause_time': statistics.mean(pause_times),
        'median_pause_time': statistics.median(pause_times),
        'max_pause_time': max(pause_times),
        'avg_memory_freed': statistics.mean(heap_reductions),
        'avg_heap_utilization': statistics.mean(heap_utilizations),
        'concurrent_phases': dict(concurrent_phases)
    }

def main():
    """Main analysis function"""
    logs_dir = Path("Benchmark/linux_results/logs")
    
    print("GC Log Analysis for Research Paper")
    print("=" * 50)
    
    results = {}
    
    # Analyze Go logs
    go_logs = list(logs_dir.glob("go_*.log"))
    for log_file in go_logs:
        if log_file.stat().st_size > 0:
            results[f'go_{log_file.stem}'] = analyze_go_gc_log(log_file)
    
    # Analyze Java GC logs  
    java_logs = list(logs_dir.glob("java_gc_*.log"))
    for log_file in java_logs:
        if log_file.stat().st_size > 0:
            results[f'java_{log_file.stem}'] = analyze_java_gc_log(log_file)
    
    # Cross-language comparison
    print(f"\n=== Cross-Language GC Comparison ===")
    
    go_results = [v for k, v in results.items() if k.startswith('go_') and v]
    java_results = [v for k, v in results.items() if k.startswith('java_') and v]
    
    if go_results and java_results:
        avg_go_gc_time = statistics.mean([r['avg_gc_time'] for r in go_results])
        avg_java_pause_time = statistics.mean([r['avg_pause_time'] for r in java_results])
        
        print(f"Go average GC time: {avg_go_gc_time:.3f}ms")
        print(f"Java average pause time: {avg_java_pause_time:.3f}ms")
        print(f"Ratio (Java/Go): {avg_java_pause_time/avg_go_gc_time:.2f}x")
        
        max_go_gc_time = max([r['max_gc_time'] for r in go_results])
        max_java_pause_time = max([r['max_pause_time'] for r in java_results])
        
        print(f"Go max GC time: {max_go_gc_time:.3f}ms")
        print(f"Java max pause time: {max_java_pause_time:.3f}ms")
        print(f"Max ratio (Java/Go): {max_java_pause_time/max_go_gc_time:.2f}x")
    
    # Save results
    with open('gc_analysis_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nResults saved to gc_analysis_results.json")

if __name__ == "__main__":
    main()