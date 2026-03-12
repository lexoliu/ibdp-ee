// Garbage Collection Overhead in HTTP Service Benchmarks
// IBDP Extended Essay - Computer Science

#import "@preview/wordometer:0.1.5": word-count, total-words

#set document(
  title: "Garbage Collection Overhead in HTTP Service Benchmarks: Comparing Go, Java, and Rust",
)

#set page(
  margin: 1in,
  numbering: "1",
)

#set text(
  font: "New Computer Modern",
  size: 11pt,
)

#set par(
  justify: true,
  leading: 0.65em,
)

#set heading(numbering: "1.")

// Code block styling
#show raw.where(block: true): set text(size: 9pt)
#show raw.where(block: true): block.with(
  fill: rgb("#f5f5f2"),
  inset: 8pt,
  radius: 4pt,
  width: 100%,
)

// Word count - exclude elements not counted for IBDP EE
#show: word-count.with(exclude: (
  heading.where(level: 1),  // Section titles
  figure,                    // Figures, tables, and their captions
  raw,                       // Code blocks
  bibliography,              // References
  <no-wc>,                   // Manual exclusion label
))

// Title Page (excluded from word count)
#page(numbering: none)[
  #align(center)[
    #v(3cm)
    #text(size: 24pt, weight: "bold")[
      Garbage Collection Overhead in HTTP Service Benchmarks
    ]
    #v(2cm)
    #text(size: 14pt, weight: "bold")[
      To what extent does garbage collection affect throughput, latency, and memory consumption in HTTP services built with Go, Java, and Rust?
    ]
    #v(1.5cm)
    #text(size: 12pt)[
      Subject: Computer Science
    ]
    #v(1cm)
    #text(size: 10pt)[
      Word Count: #total-words
    ]
  ]
] <no-wc>

// Table of Contents (excluded from word count)
#[
  #outline(
    title: [Table of Contents],
    indent: auto,
  )
  #pagebreak()
] <no-wc>

= Introduction

Programming languages handle memory differently. Languages like C and Rust require the programmer to manage heap memory explicitly. Garbage-collected languages like Java and Go automate that work: the runtime identifies unreachable objects and reclaims them. The conventional view is that this automation costs performance, and many engineering teams choose languages partly on that assumption.

How much performance, exactly? That turns out to be hard to answer from existing literature. Most comparisons rely on micro-benchmarks like the Computer Language Benchmarks Game, or they conflate too many variables: different algorithms, different frameworks, different levels of developer optimization. Few studies try to separate garbage collection from other runtime costs like JIT compilation or framework overhead, and fewer still collect GC telemetry alongside application-level metrics.

This essay measures the overhead by implementing the same HTTP service logic in Rust (ownership-based memory management), Go (concurrent GC), and Java (generational GC) using production web frameworks, then benchmarking all three under compute-intensive, serialization, and allocation-heavy workloads on cloud servers. The results reflect the combined effect of language runtime, framework, and memory management strategy. Isolating GC from those other factors would require bare-runtime comparisons that do not represent how developers actually deploy code, so the trade-off is deliberate and discussed in §6.

The research question is: *To what extent does garbage collection affect throughput, latency, and memory consumption in HTTP services built with Go, Java, and Rust?*

This question matters because the choice between GC and non-GC languages is often made based on assumptions rather than measurements. If GC overhead is as large as commonly believed, it would justify the steeper learning curve and longer development time of languages like Rust. If it is small, that changes the calculus.

= Background

== Stack and heap memory

Most languages split memory between the stack and the heap. Stack frames hold local variables and vanish when a function returns. Heap allocations persist beyond function scope and need either explicit cleanup or a runtime that reclaims dead objects.

#figure(
  {
    import "@preview/cetz:0.3.4"
    cetz.canvas({
      import cetz.draw: *

      // Memory layout box
      rect((0, 0), (4, 7), stroke: 1pt)

      // Address labels on the right
      content((4.5, 6.8), anchor: "west", text(size: 9pt)[Higher Address])
      content((4.5, 0.2), anchor: "west", text(size: 9pt)[Lower Address])

      // Stack region title
      content((2, 6.5), text(weight: "bold")[Stack (LIFO)])

      // Stack boxes
      rect((0.5, 5.6), (3.5, 6.2), fill: rgb("#e6f0ff"))
      content((2, 5.9), text(size: 9pt)[Function Call Frame])

      rect((0.5, 4.8), (3.5, 5.4), fill: rgb("#e6f0ff"))
      content((2, 5.1), text(size: 9pt)[Local Variables])

      // Stack growth arrow on the right side (pointing down)
      line((4.8, 5.8), (4.8, 4.2), mark: (end: ">"))
      content((5.6, 5.0), anchor: "west", text(size: 8pt)[Stack grows down])

      // Stack/Heap boundary
      line((0, 3.5), (4, 3.5), stroke: (dash: "dashed"))
      content((4.5, 3.5), anchor: "west", text(size: 9pt)[Stack/Heap Boundary])

      // Heap region title
      content((2, 3.0), text(weight: "bold")[Heap (Dynamic)])

      // Heap boxes
      rect((0.5, 1.8), (3.5, 2.4), fill: rgb("#ffe6e6"))
      content((2, 2.1), text(size: 9pt)[Object A])

      rect((0.5, 1.0), (3.5, 1.6), fill: rgb("#ffe6e6"))
      content((2, 1.3), text(size: 9pt)[Object B])

      // Heap growth arrow on the right side (pointing up)
      line((4.8, 1.2), (4.8, 2.8), mark: (end: ">"))
      content((5.6, 2.0), anchor: "west", text(size: 8pt)[Heap grows up])
    })
  },
  caption: [Stack and heap memory layout in a typical program],
) <fig:memory-layout>

The expensive part of memory management happens on the heap. Web servers allocate heap objects for every request (parsing buffers, response bodies, session data), so the question of how heap memory is reclaimed matters directly for HTTP service performance.

== Manual memory management

C and C++ leave heap lifetime to the programmer. `malloc` and `free` (or `new` and `delete`) are explicit. This gives full control but leads to a class of bugs that are hard to find and dangerous in production: memory leaks, dangling pointers, double frees, and use-after-free vulnerabilities. Multithreaded programs compound the problem because traditional allocators contend on shared structures @berger2000hoard.

Rust takes a different approach to manual management. Its ownership system tracks which variable "owns" each allocation at compile time. When the owner goes out of scope, the allocation is freed automatically. The compiler rejects many programs that would create dangling references or data races, moving those checks to compile time instead of leaving them to testing or production failures @jung2017rustbelt. The trade-off is a stricter programming model and longer compile times.

== Automatic memory management

Two automatic approaches exist. Reference counting tracks how many pointers refer to each object and frees it when the count reaches zero. This spreads cost across execution but cannot handle reference cycles (two objects pointing at each other never reach zero and leak). Python and Swift use reference counting as their primary strategy.

Tracing garbage collectors work differently. They walk the heap from root references (stack variables and globals), mark everything reachable, and reclaim the rest. The simplest version is mark-and-sweep. Modern collectors add generational heaps (exploiting the observation that most objects die young) and concurrent marking (running alongside application threads to reduce pause times).

Go's collector is a concurrent, non-generational mark-and-sweep. It uses tri-color marking with write barriers so it can trace the heap while the application is running. The Go team's own guide is explicit about the trade-off: the runtime is tuned for low latency, even when that means giving up some throughput efficiency @goteam2023gcguide.

Java's G1GC is a generational, region-based collector. It divides the heap into regions and collects young regions (where most allocations die quickly) more often than old regions. The default pause-time target is 200ms (`-XX:MaxGCPauseMillis`), though in practice pauses for well-sized heaps are much shorter @oracle2023gctuning. G1 also performs concurrent marking to identify garbage without stopping the application.

== The cost of garbage collection

The trade-off is real: replacing manual memory bugs with automated collection means accepting brief pauses, extra heap space, and CPU cycles spent finding dead objects. But the magnitude of that cost in real applications is an empirical question, not a theoretical one. That is what the rest of this essay investigates.

= Literature review

== GC theory and modern collectors

GC theory goes back to @mccarthy1960lisp's work on Lisp, where garbage collection was introduced for list-processing systems. @wilson1992garbage later laid out a taxonomy that is still useful: collectors can be grouped by traversal strategy, timing, and heap organization.

Recent collector work has focused less on raw throughput and more on keeping pauses short on large heaps. ZGC @liden2018zgc and Shenandoah @flood2016shenandoah both move major parts of collection and compaction off the stop-the-world path. Go's runtime documents a similar priority: short pauses matter enough that some throughput is intentionally traded away to get them @goteam2023gcguide.

== Empirical performance studies

Comparing languages fairly is harder than it sounds. Results change with warm-up policy, repetition count, and the point where a run is treated as steady state. @kalibera2013rigorous argue that without careful experimental design, small reported differences may be measurement noise rather than real system effects.

That warning matters here because HTTP services mix CPU work, allocation, serialization, and framework overhead. A single micro-benchmark can miss that mix completely. This essay therefore uses several workloads instead of one synthetic test.

On the runtime side, @tene2011c4 showed how far JVM collectors had moved toward concurrent compaction in production-oriented systems. The paper is not a survey of every managed runtime, but it is a useful reminder that modern GC design is no longer limited to simple stop-the-world collection.

== Memory safety without GC

@jung2017rustbelt formally verified key parts of Rust's safety story, showing that ownership and borrowing can support memory safety without a garbage collector. That does not make Rust effortless in practice. @astrauskas2020learning found that real Rust projects still rely on `unsafe` in a relatively small but important fraction of code, so some safety reasoning still remains with the programmer.

== Gaps this research addresses

Most studies compare bare language runtimes and ignore framework overhead, which matters because no one deploys bare runtimes in production. Previous comparisons often test a single workload type, making it impossible to see how GC overhead varies with allocation pressure. Most comparative studies also predate recent collector improvements like ZGC and Go 1.19+. This study uses production frameworks across three workload categories to produce numbers that are closer to what developers encounter when building actual services.

= Methodology <sec:methodology>

== Experimental setup

Three languages with different compilation and memory management strategies were compared:

- *Rust*: AOT-compiled, ownership-based memory management (no GC), used as the performance baseline
- *Go*: AOT-compiled with concurrent garbage collection, separating GC overhead from JIT effects
- *Java*: JIT-compiled with G1 generational garbage collection

Production frameworks were used: Axum (Rust), Chi (Go), Spring Boot WebFlux (Java). The goal was to measure language-plus-ecosystem performance, since developers pick technology stacks, not bare languages. Framework overhead is part of the measurement. This is a deliberate choice discussed further in §6.

== Runtime configuration

Default configurations were used throughout: Java (OpenJDK 21) with G1 auto-tuning @oracle2023gctuning, Go (1.22) with GOGC=100 @goteam2023gcguide, Rust (1.80) with ownership-based management @rustteam2023ownership. No language-specific tuning was applied, which reflects how most applications are deployed in practice.

The test environment used two Aliyun ECS instances in the same security group in Tokyo Zone C: an ecs.g7.2xlarge (8 vCPU, 32 GiB) hosting the services and an ecs.c7nex.xlarge (4 vCPU, 8 GiB) running load generation, both on Ubuntu 22.04 with ESSD cloud disks (PL1, 80 GiB, 5800 IOPS). Separating the load generator from the service under test prevents them from competing for CPU.

== Workload design

Three workload categories were chosen to vary the amount of heap allocation:

#figure(
  table(
    columns: (auto, auto, auto),
    inset: 8pt,
    align: (left, left, left),
    table.header(
      [*Group*], [*Endpoint(s)*], [*Characteristics*],
    ),
    [Prime], [`/is_prime`], [CPU-bound, minimal allocation],
    [Light], [`/echo`, `/json`, `/json2xml`], [Mixed serialization, moderate allocation],
    [KV], [`/kv/get`, `/kv/set`, `/kv/delete`], [Allocation-heavy, persistent state],
  ),
  caption: [Workload categories and their characteristics.],
) <tab:workloads>

Prime does almost no heap allocation: it just computes whether a number is prime. Light allocates moderately through JSON serialization and XML conversion. KV allocates heavily, maintaining an in-memory key-value store with data sizes from 200 bytes to 10 KB. If garbage collection imposes a throughput cost, the cost should grow from Prime to KV.

The KV workload uses a dedicated prewarm phase (0--250s) to populate the key-value store before measurement begins (250--600s). This ensures all three languages start the measurement phase with a comparable dataset. Without prewarm, higher-throughput languages would insert more keys, making memory comparisons unfair.

== Load generation and metrics

Load was generated using the `k6` framework with 64 virtual users for 10 minutes per run. Each language-workload combination was run once on the cloud servers. An initial warm-up run was performed and discarded to allow Java's JIT compiler to optimize hot paths.

Each run produced per-second time-series data: throughput (from `http_reqs`), latency percentiles (P50, P90, P99 from `http_req_duration`), and failure rate (`http_req_failed`). Memory (RSS) was sampled at 1 Hz using `ps`. GC telemetry was collected via `GODEBUG=gctrace=1` for Go and `-Xlog:gc*` for Java.

== Data analysis

For each workload-language combination, time-series data was analyzed for steady-state behavior. Steady-state windows were identified by excluding periods after service crashes (where throughput dropped to near zero). GC pause distributions were extracted from telemetry logs and plotted as histograms.

Because the data comes from a single run per combination, the results are reported as observed values. There are no confidence intervals and no statistical significance tests. This is a limitation discussed in §6.

= Results and analysis

This section reports benchmark results from the Aliyun servers (8 vCPU, 32 GB RAM). For each workload, throughput, median latency, and RSS memory are compared across implementations. All numbers come from the per-second CSV time-series, averaged over each steady-state window.

== Performance summary

#figure(
  table(
    columns: (auto, auto, auto, auto, auto, auto),
    inset: 6pt,
    align: (left, left, right, right, left, right),
    table.header(
      [*Workload*], [*Language*], [*Throughput (req/s)*], [*P50 (ms)*], [*Stability*], [*Peak RSS (GB)*],
    ),
    table.cell(rowspan: 3)[Prime], [Java], [11,451], [5.16], [Full 600s], [5.7],
    [], [Go], [29,180], [1.86], [Crash \@103s], [4.2],
    [], [Rust], [30,833], [1.77], [Crash \@102s], [4.1],
    table.cell(rowspan: 3)[Light], [Java], [18,733], [1.66], [Crash \@173s], [5.7],
    [], [Go], [18,088], [1.71], [Crash \@180s], [4.1],
    [], [Rust], [18,403], [1.67], [Crash \@182s], [4.1],
    table.cell(rowspan: 3)[KV], [Java], [7,966], [2.17], [Stable], [4.9],
    [], [Go], [7,859], [2.18], [Stable], [3.4],
    [], [Rust], [7,877], [2.17], [Stable], [4.1],
  ),
  caption: [Steady-state performance from a single benchmark run per combination. Throughput and latency averaged over the stable window before any crash. Peak RSS is the highest observed value.],
) <tab:performance-summary>

== Prime workload: CPU-intensive, minimal allocation

#figure(
  image("../Benchmark/linux_results/plots/comparison_prime.png", width: 90%),
  caption: [Prime workload over time. Go and Rust crash around 100s. Java runs the full 600s at lower but steady throughput.],
) <fig:prime-performance>

Rust averaged 30,833 req/s during its stable window (10--102s), Go averaged 29,180 req/s (10--103s), and Java held steady at 11,451 req/s over the full 600 seconds. The Rust-to-Java throughput ratio is 2.7:1.

Java's median latency was 5.16ms, well above Go's 1.86ms and Rust's 1.77ms. Java also used more memory (5.7 GB vs. 4.1--4.2 GB for the others), which reflects JVM heap pre-allocation even in a workload that barely touches the heap.

Go and Rust both crashed around 102--103 seconds into the run. Java, despite lower throughput, ran for the full 10 minutes without interruption. The cause of the Go/Rust crashes was not investigated and is discussed as a limitation in §6. But the pattern is worth noting: the services producing the highest throughput were also the ones that crashed earliest.

Since Prime involves minimal heap allocation, the throughput gap between Java and the others likely reflects JVM runtime overhead (object model, safety checks, interpreter-to-JIT transition) rather than garbage collection cost. This is the workload where GC should matter _least_, and it is also where the performance gap is _largest_, which supports the hypothesis that runtime characteristics, not GC, drive the difference.

== Light workload: serialization and moderate allocation

#figure(
  image("../Benchmark/linux_results/plots/comparison_light.png", width: 90%),
  caption: [Light workload. All three languages reach similar throughput (~18k req/s) during stable periods.],
) <fig:light-performance>

All three languages performed within 4% of each other: Java at 18,733, Rust at 18,403, and Go at 18,088 req/s. Median latencies were also nearly identical (1.66--1.71ms). The performance hierarchy from Prime vanished entirely.

This was the result I least expected. Java, 63% behind in Prime, pulled even with Go and Rust once the workload shifted to serialization. One possible explanation is that Java's optimized serialization libraries (Jackson, Spring WebFlux's reactive pipeline) offset its runtime overhead, or that serialization is I/O-bound enough to equalize all three. Either way, the data shows that Java's deficit in Prime does not generalize.

All three crashed during the run (Java at 173s, Go at 180s, Rust at 182s), giving roughly equal stable windows. Memory followed the same pattern as Prime: Java at 5.7 GB, Go and Rust at 4.1 GB.

== KV workload: allocation-heavy, persistent state

#figure(
  image("../Benchmark/linux_results/plots/comparison_kv.png", width: 90%),
  caption: [KV workload showing prewarm phase (0--250s) with memory growth, then stable measurement phase (250--600s) at ~8k req/s.],
) <fig:kv-performance>

The KV workload uses GET/SET/DELETE operations on an in-memory key-value store with data sizes from 200 bytes to 10 KB. Two phases were visible in the data.

During prewarm (0--250s), keys were populated at roughly 2,800--2,900 req/s, totaling about 720,000 requests across the prewarm window. During the measurement phase (250--600s), the three languages converged: throughput at 7,859--7,966 req/s, median latency at 2.17--2.18ms. No crashes occurred in the full 600 seconds.

Peak RSS was Java 4.9 GB, Rust 4.1 GB, Go 3.4 GB. These are total process RSS values (including runtime baseline, framework overhead, and the actual key-value data). The memory growth during prewarm reflects keys being loaded; the cross-language spread reflects differences in runtime baseline rather than workload-specific allocation.

This is the workload that should stress garbage collectors the most, since every request creates and destroys heap objects. That all three languages converged to nearly identical throughput suggests the GC overhead for this kind of workload is too small to measure against framework and I/O overhead.

== Garbage collection telemetry

GC telemetry logs were parsed from the Go and Java runs. Go produced 244 GC events; Java produced 83 pause events and 40 concurrent operations.#footnote[Parsed from `GODEBUG=gctrace=1` (Go) and `-Xlog:gc*` (Java) output using custom scripts.]

Go's collector paused for 0.054ms on average (median 0.046ms, max 0.150ms), with 0.4% reported GC time. The primary load phase alone accounted for 209 of the 244 events, averaging 0.059ms each. Go collects frequently (244 events) but briefly (sub-0.1ms).

Java's G1GC paused for 3.213ms on average (max 15.943ms), with 83 stop-the-world events and 40 concurrent operations. Each collection freed roughly 745 MB on average. The JVM was configured with a 4 GB minimum heap and 24 GB maximum capacity.

#figure(
  table(
    columns: (auto, auto, auto),
    inset: 8pt,
    align: (left, center, center),
    table.header(
      [*Metric*], [*Go*], [*Java G1GC*],
    ),
    [Avg pause], [0.054ms], [3.213ms],
    [Max pause], [0.150ms], [15.943ms],
    [Events], [244], [83],
    [GC time], [0.4%], [--],
  ),
  caption: [GC pause metrics from telemetry logs.],
) <tab:gc-comparison>

#figure(
  image("../gc_pause_distribution.png", width: 90%),
  caption: [GC pause time distributions. Go: n=244 events, Java: n=83 events.],
) <fig:gc-pause-dist>

Go's pauses (50--150 μs) are roughly 60× shorter than Java's (3--16ms). This reflects a real design trade-off: Go's non-generational collector sacrifices throughput for predictable latency, while Java's G1GC batches work into fewer, longer pauses to reduce total overhead. For HTTP services with typical response times of 1--10ms, Go's pauses are invisible. Java's 3ms average is usually below the noise floor of network latency, though its 16ms maximum could occasionally show up in P99 tail latency.

== Memory consumption

RSS was measured via 1 Hz `ps` sampling. It captures everything: application state, framework overhead, runtime systems, and shared libraries. For Prime and Light, baseline memory was large (Java 5.7 GB, Go/Rust ~4.1 GB), reflecting JVM heap pre-allocation and runtime initialization rather than workload state. Neither Prime nor Light retains much data between requests.

The KV workload told a different story. Go's RSS grew from near zero to 3.4 GB as keys were inserted. Java started higher (due to JVM pre-allocation) and reached 4.9 GB. Rust grew to 4.1 GB. All values are total process RSS. The cross-language variation in KV memory reflects different runtime baselines added to roughly similar workload data.

== Cross-workload patterns

Three patterns stand out when comparing across workloads:

+ Java's throughput varied sharply by workload: 63% below Rust in Prime, but within 2% of Go and Rust in Light, and within 1% in KV. A blanket claim like "Java is slow" would be accurate for one workload and wrong for the other two.

+ Go and Rust were close in Prime (5.4% gap) and essentially identical in Light and KV. Whatever overhead Go's garbage collector adds, it was not visible in throughput at this measurement granularity.

+ The largest throughput gap appeared in the workload with the least allocation (Prime), while the most allocation-heavy workload (KV) showed no gap. If garbage collection were the main bottleneck, the pattern should be reversed. This points to JVM runtime characteristics as the primary source of Java's deficit.

= Discussion

== Research process and challenges

Keeping implementations consistent across languages was the main challenge. Each service used minimal code on top of its framework (Axum, Chi, Spring Boot WebFlux) to avoid framework-specific optimizations. The implementations share the same endpoint structure and the same algorithmic logic.

An early lesson was that the test environment matters more than expected. Initial results collected on a local MacBook Pro (M2 Max) showed different performance rankings than the cloud servers, presumably because the M2's unified memory architecture and ARM cores interact differently with each runtime. Moving to x86 cloud instances with dedicated resources gave more reproducible numbers and eliminated the confounding effect of background processes competing for resources on a development machine.

An unexpected problem appeared during KV testing. Higher-throughput languages showed paradoxically higher memory because their SET operations were silently failing. Without noticing this, I would have been comparing languages working with different dataset sizes. Adding `/kv/stats` endpoints and retry logic caught and fixed the problem. This experience reinforced why benchmarks need validation beyond just throughput numbers.

== Stability analysis <sec:stability-analysis>

The crash patterns were not what I expected. In Prime, Go and Rust crashed after about 100 seconds while Java ran for the full 600 seconds. In Light, all three crashed at similar times (173--182s). KV had no crashes across the full run.

The cause of the Prime and Light crashes was not investigated and remains unknown. It could be OS-level resource limits, framework behavior under extreme throughput, or something else entirely. I report this as an observed fact, not as evidence for any specific explanation. What is clear is that memory footprint did not predict stability: KV had the highest RSS values and was the most stable workload, while Prime had lower RSS but triggered the earliest crashes.

== What the data says about GC overhead

The original expectation was that garbage-collected languages would show a measurable performance penalty. The data complicates that picture.

Go's telemetry shows 0.054ms average pauses at 0.4% reported GC time. In Light and KV, Go's throughput was indistinguishable from Rust's. In Prime, the gap was 5.4%. If garbage collection is imposing a throughput cost, it is small enough that framework efficiency and runtime characteristics dominate.

Java's G1GC paused for 3.2ms on average, but application throughput in Prime was 63% below Rust despite minimal allocation. Since Prime barely uses the heap, garbage collection is not what slowed Java down. The JVM runtime itself, with its object model overhead and safety mechanisms, appears to be the limiting factor in pure computation. But once the workload shifted to serialization or I/O, Java performed on par with the others.

The Go-Rust comparison is the cleaner test of GC overhead, since both are AOT-compiled and differ primarily in memory management strategy. The 5.4% Prime gap and near-zero Light/KV gap suggest the cost of Go's concurrent GC is small in these workloads. Go collects frequently (244 events vs. Java's 83) but each collection is so short (0.054ms) that the total time spent in GC is barely measurable. Java's G1GC takes longer per pause (3.2ms) but runs fewer collections, and the total overhead did not prevent Java from matching Go and Rust in serialization or I/O workloads. The two GC strategies reflect different design priorities, but neither one prevented competitive throughput.

== Methodological considerations

Using production frameworks means these results capture ecosystem performance, not bare-language performance. Some observed differences may reflect framework maturity rather than language characteristics. For example, Java's competitive Light performance could reflect mature serialization libraries rather than language-level efficiency.

This is a deliberate trade-off. Developers choose technology stacks, and framework performance is inseparable from language performance in practice. That said, these results should be read as ecosystem comparisons. Testing with minimal implementations would isolate language-level differences more cleanly and would complement this work.

== Limitations

Several limitations should be stated directly:

- These results come from a single run per language-workload combination. Without repeated runs, there are no confidence intervals. The reported numbers are point observations, not population estimates, and could shift with repeated measurement.

- The measurements capture the combined effect of language runtime, framework, and memory management. Attributing performance differences to garbage collection specifically is not possible from this data alone.

- Go and Rust crashed during Prime (at ~102s) and Light (at ~180s). The stable windows are short, and the crash causes are unknown. Results for those workloads rest on limited observation periods.

- 10-minute runs may miss long-term GC effects like heap fragmentation or memory leaks that emerge over hours of operation.

- Workloads are synthetic. Production applications involve database calls, network I/O, and request diversity that these benchmarks do not capture.

- Results come from a single cloud region (Aliyun Tokyo) and may not generalize to other hardware or providers.

= Conclusion

This study compared Rust, Go, and Java HTTP services under compute-intensive, serialization, and allocation-heavy workloads on Aliyun cloud servers. GC telemetry from 244 Go collection events and 83 Java pause events was collected alongside per-second throughput, latency, and memory data.

The main findings:

- Go and Rust performed within 5.4% of each other in Prime, and were indistinguishable in Light and KV. Go's collector paused for 0.054ms on average at 0.4% reported GC time. For these workloads, the cost of concurrent garbage collection was not visible in throughput.

- Java was 63% slower than Rust in Prime, a compute-heavy workload with minimal allocation. Since Java's G1GC operated efficiently (3.2ms average pauses), the throughput gap points to JVM runtime overhead rather than garbage collection.

- In Light (serialization), all three languages hit nearly identical throughput: 18,088--18,733 req/s. The large gap from Prime disappeared entirely.

- In KV (allocation-heavy), all three converged at ~7,900 req/s. The workload with the heaviest heap allocation produced no measurable throughput difference.

- Go pauses were roughly 60× shorter than Java pauses (0.054ms vs. 3.2ms average), reflecting distinct design philosophies. Both produced acceptable latency for HTTP services.

These are single-run observations from benchmarks using production frameworks. They measure ecosystem performance, not GC overhead in isolation. The data shows that for these specific workloads, garbage collection overhead was smaller than I expected going in. Whether that holds for other workload types, longer run times, or different frameworks is an open question.

Useful follow-up work would include longer benchmark runs (hours instead of minutes) to surface fragmentation and heap-growth effects, repeating the experiment to obtain confidence intervals, testing with minimal (non-framework) implementations to separate language-level from framework-level performance, and measuring energy consumption alongside throughput.

// Bibliography (excluded from word count by wordometer)
#bibliography("references.bib", style: "ieee")

// Appendices (excluded from word count)
#[
  = Appendices

  Appendices include benchmark data tables, raw CSVs, GC log analysis scripts, and comparison charts.
] <no-wc>
