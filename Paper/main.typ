// Performance Impact of Garbage Collection in Real-World Applications
// IBDP Extended Essay - Computer Science

#import "@preview/wordometer:0.1.5": word-count, total-words

#set document(
  title: "Performance Impact of Garbage Collection in Real-World Applications",
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
      Performance Impact of Garbage Collection in Real-World Applications
    ]
    #v(2cm)
    #text(size: 14pt, weight: "bold")[
      How do performance characteristics vary between GC and non-GC languages?
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

Different programming languages deal with memory in very different ways. In C and Rust, the programmer has to manage heap memory by hand. Java and Go take a different route -- their runtimes track which objects are still in use and clean up the rest automatically. The common assumption is that this automation makes programs slower, and a lot of engineering teams pick their language partly based on that belief.

But how much slower, really? I tried to find a clear answer in the existing literature and could not. Most benchmarks out there are micro-benchmarks like the Computer Language Benchmarks Game, or they mix together too many variables at once -- different algorithms, different frameworks, different levels of programmer effort. Very few studies actually try to separate what garbage collection costs from other runtime overhead like JIT compilation or framework inefficiency, and almost none collect GC telemetry at the same time as application metrics.

For this essay, I implemented the same HTTP service logic in Rust (which uses ownership instead of GC), Go (concurrent GC), and Java (generational GC), all using production web frameworks. I then ran benchmarks across three workload types -- compute-intensive, serialization, and allocation-heavy -- on cloud servers. The numbers I got reflect everything together: runtime, framework, and memory management. Pulling GC apart from the other factors would mean testing bare runtimes with no framework, which is not how anyone actually deploys code. I made this trade-off on purpose and come back to it in §6.

The research question is: *How do performance characteristics vary between GC and non-GC languages?*

I think this question matters because in practice, developers choose between GC and non-GC languages based on gut feeling more than evidence. If GC overhead really is as large as people assume, then it makes sense to invest in the steeper learning curve of something like Rust. But if the overhead is small, that whole argument falls apart.

= Background

== Stack and heap memory

Most languages divide memory into two regions: the stack and the heap. The stack is simple -- it holds local variables in frames that get created when a function is called and thrown away when it returns. The heap is where things get complicated. Heap-allocated objects live beyond the function that created them, so somebody or something has to decide when to free that memory.

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

For HTTP services, almost all the interesting memory activity happens on the heap. Every incoming request means the server allocates buffers for parsing, builds response objects, maybe stores session data. So how the heap gets cleaned up directly affects how well the service performs.

== Manual memory management

In C and C++, the programmer is responsible for heap memory. You call `malloc` and `free` (or `new` and `delete`) yourself. This gives you full control, but it also means you can get things wrong -- memory leaks if you forget to free, dangling pointers if you free too early, double frees, use-after-free bugs. These are some of the nastiest bugs in software because they are hard to reproduce and can cause security vulnerabilities. Threads make it even worse because multiple threads may fight over the same allocator @berger2000hoard.

Rust handles things differently. Instead of making programmers remember to free memory, Rust's compiler tracks which variable "owns" each piece of heap data. When that variable goes out of scope, the memory is freed automatically. The compiler also refuses to compile code that would create dangling references or data races, catching those bugs before the program ever runs @jung2017rustbelt. The downside is that Rust's rules can feel restrictive, and the compiler is slower.

== Automatic memory management

There are two main automatic approaches. Reference counting keeps track of how many pointers point at each object and frees it once the count drops to zero. It spreads the cleanup cost over time, but it cannot deal with cycles -- if two objects point at each other, their counts never reach zero and the memory leaks. Python and Swift both use reference counting.

Tracing garbage collectors work in a completely different way. They start from known "root" references -- things on the stack, global variables -- and follow every pointer they can reach. Anything they cannot reach is dead and gets reclaimed. The simplest form of this is mark-and-sweep. Modern collectors build on top of that with generational heaps (since most objects are short-lived) and concurrent marking (so the collector can run alongside the application instead of pausing it).

Go uses a concurrent, non-generational mark-and-sweep collector. It does tri-color marking with write barriers, which lets it trace the heap while the program keeps running. The Go team is quite open about their design choice: they prioritize low latency over raw throughput, and they are willing to give up some efficiency to keep pauses short @goteam2023gcguide.

Java's G1GC is a generational, region-based collector. It divides the heap into regions and collects young regions (where most allocations die quickly) more often than old regions. The default pause-time target is 200ms (`-XX:MaxGCPauseMillis`), though in practice pauses for well-sized heaps are much shorter @oracle2023gctuning. G1 also performs concurrent marking to identify garbage without stopping the application.

== The cost of garbage collection

There is a real trade-off here. By automating memory cleanup, GC languages eliminate a whole class of manual memory bugs, but in return the program has to accept short pauses, extra heap space, and CPU time spent looking for dead objects. The question is: how big are those costs in a real application? That is an empirical question, and it is what the rest of this essay tries to answer.

= Literature review

== GC theory and modern collectors

The idea of garbage collection is older than most people think -- it goes back to @mccarthy1960lisp's work on Lisp in 1960, where it was invented to handle list structures. @wilson1992garbage later wrote a survey that organized collectors into categories by how they traverse the heap, when they pause, and how they lay out memory. Those categories are still the standard way people talk about GC.

More recently, collector designers have been focused on getting pause times down rather than maximizing throughput. ZGC @liden2018zgc and Shenandoah @flood2016shenandoah both moved the expensive parts of collection off the stop-the-world path, so pauses stay short even with very large heaps. Go's runtime team made a similar bet: they documented that they would rather have short pauses than maximum throughput @goteam2023gcguide.

== Empirical performance studies

Comparing programming languages fairly turns out to be really hard. Results depend on warm-up policy, how many times you repeat a run, and where you decide steady state begins. @kalibera2013rigorous made the point that without careful experimental design, small differences in benchmarks might just be noise rather than real effects.

This matters for my essay because HTTP services are not pure computation -- they mix CPU work, allocation, serialization, and framework overhead all together. A single micro-benchmark would miss that mix. That is why I use three different workloads instead of one.

@tene2011c4 showed how far JVM collectors had come with concurrent compaction in production systems. It is not a comprehensive survey, but it is a good reminder that modern GC is nothing like the simple stop-the-world collectors from textbooks.

== Memory safety without GC

@jung2017rustbelt formally proved that Rust's ownership and borrowing model can guarantee memory safety without needing a garbage collector. That said, using Rust is not exactly effortless. @astrauskas2020learning found that real-world Rust codebases still use `unsafe` in a small but significant portion of their code, which means the programmer still has to reason about safety in those parts.

== Gaps this research addresses

Most existing studies compare bare language runtimes without any framework, but nobody deploys code that way. Previous comparisons also tend to test just one type of workload, so you cannot tell whether GC overhead changes when allocation pressure goes up. And many of the older studies were done before recent improvements like ZGC and Go 1.19+. This study tries to fill those gaps by using production frameworks and testing across three workload categories, which should give numbers closer to what a developer would actually see.

= Methodology <sec:methodology>

== Experimental setup

I compared three languages that handle compilation and memory management differently:

- *Rust*: AOT-compiled, ownership-based memory management (no GC), used as the performance baseline
- *Go*: AOT-compiled with concurrent garbage collection, separating GC overhead from JIT effects
- *Java*: JIT-compiled with G1 generational garbage collection

I used production frameworks for each language: Axum for Rust, Chi for Go, and Spring Boot WebFlux for Java. The point was to measure what you actually get when you pick a technology stack, not what the language can do in isolation. Framework overhead is baked into these numbers, and I think that is the right choice since real developers ship code with frameworks. I discuss this further in §6.

== Runtime configuration

I kept default configurations for everything: Java (OpenJDK 21) with G1 auto-tuning @oracle2023gctuning, Go (1.22) with GOGC=100 @goteam2023gcguide, Rust (1.80) with ownership-based management @rustteam2023ownership. I did not do any language-specific tuning, since most real applications are deployed with defaults anyway.

The tests ran on two Aliyun ECS instances in the same security group in Tokyo Zone C. The service ran on an ecs.g7.2xlarge (8 vCPU, 32 GiB) and load generation ran on a separate ecs.c7nex.xlarge (4 vCPU, 8 GiB). Both used Ubuntu 22.04 with ESSD cloud disks (PL1, 80 GiB, 5800 IOPS). I put the load generator on a separate machine so it would not compete with the service for CPU.

== Workload design

I picked three workload categories that put different amounts of pressure on heap allocation:

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

Prime barely touches the heap -- it just checks whether a number is prime. Light does moderate allocation through JSON serialization and XML conversion. KV is the heavy one: it maintains an in-memory key-value store with values ranging from 200 bytes to 10 KB. My reasoning was that if GC really costs throughput, the cost should get bigger as we move from Prime to KV.

The KV test has a dedicated prewarm phase (0--250s) where the key-value store gets populated before I start measuring (250--600s). This way all three languages begin the actual measurement with roughly the same number of keys. Without this, whichever language is fastest would insert more keys during the test, and that would mess up the memory comparison.

== Load generation and metrics

I used the `k6` load testing framework with 64 virtual users, running each test for 10 minutes. Each language-workload combination was run once on the cloud servers. Before the actual run, I did a warm-up run and threw it away so Java's JIT compiler could optimize its hot paths.

Each run gave me per-second time-series data: throughput (from `http_reqs`), latency percentiles (P50, P90, P99 from `http_req_duration`), and failure rate (`http_req_failed`). I also sampled memory (RSS) every second using `ps`, and collected GC logs via `GODEBUG=gctrace=1` for Go and `-Xlog:gc*` for Java.

== Data analysis

For each language-workload pair, I looked at the time-series data to find the steady-state window. I identified steady state by cutting out periods after service crashes (where throughput fell to basically zero). I also pulled GC pause distributions from the telemetry logs and plotted them as histograms.

Since I only have one run per combination, the results are just point observations. There are no confidence intervals or significance tests. I acknowledge this as a limitation in §6.

= Results and analysis

What follows are the benchmark results from the Aliyun servers (8 vCPU, 32 GB RAM). For each workload I compare throughput, median latency, and RSS memory across the three implementations. All numbers come from the per-second CSV time-series, averaged over each steady-state window.

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

During its stable window (10--102s), Rust averaged 30,833 req/s. Go was close at 29,180 req/s (10--103s). Java was much lower at 11,451 req/s but ran steadily for the full 600 seconds. That puts the Rust-to-Java throughput ratio at 2.7:1.

Java's median latency was 5.16ms, noticeably higher than Go's 1.86ms and Rust's 1.77ms. Java also used more memory (5.7 GB vs. 4.1--4.2 GB for the others). That extra memory comes from JVM heap pre-allocation, which happens even though this workload barely touches the heap.

Go and Rust both crashed around 102--103 seconds in. Java, despite being slower, ran the entire 10 minutes without any interruption. I did not investigate what caused the crashes and discuss this as a limitation in §6. But it is interesting that the fastest services were the ones that crashed first.

Since Prime does almost no heap allocation, the throughput gap between Java and the others probably comes from JVM runtime overhead -- the object model, safety checks, interpreter-to-JIT warm-up -- not from garbage collection. This is the workload where GC should matter _least_, and yet the performance gap is _largest_. That supports the idea that runtime characteristics, not GC, are driving the difference.

== Light workload: serialization and moderate allocation

#figure(
  image("../Benchmark/linux_results/plots/comparison_light.png", width: 90%),
  caption: [Light workload. All three languages reach similar throughput (~18k req/s) during stable periods.],
) <fig:light-performance>

All three languages landed within 4% of each other: Java at 18,733, Rust at 18,403, and Go at 18,088 req/s. Median latencies were almost the same too (1.66--1.71ms). The huge performance gap from Prime just vanished.

I genuinely did not expect this result. Java was 63% behind in Prime, and then it pulled completely even once the workload shifted to serialization. One explanation could be that Java's serialization libraries (Jackson, Spring WebFlux's reactive pipeline) are mature enough to offset the runtime overhead. Or maybe serialization is just I/O-bound enough that all three languages hit the same ceiling. Either way, Java's poor showing in Prime clearly does not generalize.

All three crashed during the run (Java at 173s, Go at 180s, Rust at 182s), so they had roughly equal stable windows. Memory was the same pattern as Prime: Java around 5.7 GB, Go and Rust at 4.1 GB.

== KV workload: allocation-heavy, persistent state

#figure(
  image("../Benchmark/linux_results/plots/comparison_kv.png", width: 90%),
  caption: [KV workload showing prewarm phase (0--250s) with memory growth, then stable measurement phase (250--600s) at ~8k req/s.],
) <fig:kv-performance>

This test uses GET/SET/DELETE operations on an in-memory key-value store with values from 200 bytes to 10 KB. The data clearly showed two phases.

During prewarm (0--250s), keys were being inserted at roughly 2,800--2,900 req/s, around 720,000 requests total across the window. Once measurement started (250--600s), all three languages converged: throughput was 7,859--7,966 req/s, median latency 2.17--2.18ms. Nothing crashed in the full 600 seconds.

Peak RSS was Java 4.9 GB, Rust 4.1 GB, Go 3.4 GB. These are total process RSS numbers, so they include the runtime baseline, framework overhead, and the actual key-value data. The memory growth during prewarm is just keys being loaded. The spread between languages mostly comes from different runtime baselines, not from the workload data itself.

This is the workload that should stress garbage collectors the hardest, because every request creates and destroys heap objects. And yet all three languages ended up at virtually the same throughput. To me, that suggests the GC overhead is just too small to show up against the framework and I/O costs.

== Garbage collection telemetry

I parsed GC telemetry logs from the Go and Java runs. Go had 244 GC events; Java had 83 pause events plus 40 concurrent operations.#footnote[Parsed from `GODEBUG=gctrace=1` (Go) and `-Xlog:gc*` (Java) output using custom scripts.]

Go's collector paused for 0.054ms on average (median 0.046ms, max 0.150ms), spending only 0.4% of total time on GC. The primary load phase alone accounted for 209 of the 244 events, averaging 0.059ms each. So Go collects very often (244 times) but each collection is extremely brief -- under 0.1ms.

Java's G1GC paused for 3.213ms on average (max 15.943ms), with 83 stop-the-world events and 40 concurrent operations. Each collection freed around 745 MB on average. The JVM had a 4 GB minimum heap and 24 GB maximum capacity.

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

Go's pauses (50--150 μs) are about 60× shorter than Java's (3--16ms). This is a genuine design trade-off in action: Go's non-generational collector gives up some throughput to keep latency predictable, while Java's G1GC batches work into fewer but longer pauses to reduce total overhead. In practice, for HTTP services where response times are typically 1--10ms, Go's pauses are basically invisible. Java's 3ms average is usually lost in network noise too, though the 16ms max could occasionally bump up P99 tail latency.

== Memory consumption

I measured RSS via 1 Hz `ps` sampling, which captures everything -- application state, framework overhead, the runtime itself, shared libraries. For Prime and Light, baseline memory was high across the board (Java 5.7 GB, Go/Rust around 4.1 GB). This is mostly runtime initialization and JVM heap pre-allocation rather than actual workload data, since neither Prime nor Light holds much state between requests.

KV was a different story. Go's RSS climbed from near zero to 3.4 GB as keys were loaded in. Java started higher because of JVM pre-allocation and ended up at 4.9 GB. Rust grew to 4.1 GB. The differences between languages in KV memory are mostly from their different runtime baselines sitting on top of roughly the same amount of workload data.

== Cross-workload patterns

Looking across all three workloads, three things stood out to me:

+ Java's throughput swung wildly depending on the workload: 63% below Rust in Prime, but within 2% in Light and 1% in KV. If someone told you "Java is slow," they would be right about Prime and wrong about everything else.

+ Go and Rust were close in Prime (5.4% gap) and basically identical in Light and KV. Whatever overhead Go's GC adds, it did not show up in throughput at this level of measurement.

+ The biggest throughput gap was in the workload with the _least_ allocation (Prime), and the most allocation-heavy workload (KV) had _no_ gap. If garbage collection were really the bottleneck, you would expect the opposite pattern. This points toward JVM runtime overhead, not GC, as the main reason Java fell behind in Prime.

= Discussion

== Research process and challenges

The hardest part of this project was keeping the three implementations consistent. Each service sits on top of its framework (Axum, Chi, Spring Boot WebFlux) with as little custom code as possible, so I would not accidentally optimize one version more than the others. All three share the same endpoint structure and the same algorithms.

One thing I learned early on is that the test environment makes a huge difference. My first round of results was collected on my MacBook Pro (M2 Max), and the performance rankings were completely different from the cloud results. I think the M2's unified memory and ARM cores interact with each runtime differently. Once I moved to x86 cloud instances with dedicated resources, the numbers became much more consistent and I did not have to worry about background processes on my laptop interfering.

I also ran into an unexpected problem during KV testing. Languages with higher throughput were showing paradoxically higher memory usage. It turned out their SET operations were silently failing, so they were actually working with fewer keys. If I had not caught this, I would have been comparing languages against different dataset sizes without realizing it. I added `/kv/stats` endpoints and retry logic to fix it. That experience really drove home why benchmarks need more validation than just looking at throughput.

== Stability analysis <sec:stability-analysis>

The crashes surprised me. In Prime, Go and Rust both died after about 100 seconds while Java ran the full 600. In Light, all three crashed around the same time (173--182s). KV had zero crashes across the full run.

I did not investigate the Prime and Light crashes -- it could be OS-level resource limits, something about how the frameworks behave under extreme throughput, or something else. I am just reporting what happened. One interesting detail: memory footprint did not predict stability at all. KV had the highest RSS and was the most stable, while Prime had lower RSS but crashed earliest.

== What the data says about GC overhead

Going into this, I expected garbage-collected languages to have a clear, measurable performance penalty. The data turned out to be more complicated than that.

Go's telemetry shows 0.054ms average pauses and only 0.4% of time spent on GC. In Light and KV, Go's throughput was indistinguishable from Rust's. In Prime there was a 5.4% gap. So if Go's GC is costing throughput, the cost is small enough that framework differences and runtime characteristics matter more.

Java's G1GC paused for 3.2ms on average, but the throughput story is weird: Java was 63% slower than Rust in Prime even though Prime barely uses the heap. So GC is not what slowed Java down there. The JVM runtime itself -- object model overhead, safety mechanisms, JIT warm-up -- seems to be the limiting factor for pure computation. But once the workload involved serialization or I/O, Java caught up completely.

The Go-Rust comparison is probably the cleaner test of GC overhead since both are AOT-compiled and the main difference between them is memory management. The 5.4% gap in Prime and near-zero gap in Light/KV suggest Go's concurrent GC does not cost much in these workloads. Go runs collections more often (244 events vs. Java's 83) but each one is so short (0.054ms) that the total time in GC barely registers. Java's G1GC pauses longer (3.2ms each) but runs fewer collections, and the total overhead still did not stop Java from matching Go and Rust in the serialization and I/O workloads. The two GC designs have different priorities, but neither one prevented competitive throughput.

== Methodological considerations

Because I used production frameworks, these results show ecosystem performance rather than bare-language performance. Some of the differences I observed might be about framework maturity rather than anything inherent to the language. For instance, Java doing well in Light could just mean Jackson and WebFlux are really good serialization libraries, not that Java itself is fast at serialization.

I made this choice deliberately. Developers choose technology stacks, and in practice framework performance is inseparable from language performance. But these results should be read as ecosystem comparisons. Testing with minimal, framework-free implementations would give a cleaner picture of language-level differences and would be a good complement to this work.

== Limitations

I want to be upfront about what this study cannot tell you:

- I only did one run per language-workload combination. Without repeated runs, there are no confidence intervals. These are point observations that could shift if I ran everything again.

- The numbers reflect language runtime, framework, and memory management all mixed together. I cannot attribute any specific performance difference to garbage collection alone based on this data.

- Go and Rust crashed during Prime (at ~102s) and Light (at ~180s). The stable windows are short and I do not know why the crashes happened. The results for those workloads rest on limited observation time.

- 10-minute runs might miss longer-term GC effects like heap fragmentation or slow memory leaks that only show up after hours.

- These workloads are synthetic. Real production services make database calls, do network I/O, and handle diverse request types that my benchmarks do not cover.

- Everything ran in one cloud region (Aliyun Tokyo). Different hardware or providers might give different results.

= Conclusion

I compared Rust, Go, and Java HTTP services across compute-intensive, serialization, and allocation-heavy workloads on Aliyun cloud servers. I collected GC telemetry from 244 Go collection events and 83 Java pause events alongside per-second throughput, latency, and memory data.

Here is what I found:

- Go and Rust were within 5.4% of each other in Prime, and basically identical in Light and KV. Go's collector paused for 0.054ms on average, spending 0.4% of total time on GC. For these workloads, concurrent garbage collection did not have a visible cost in throughput.

- Java was 63% slower than Rust in Prime, which is a compute-heavy workload with almost no heap allocation. Since Java's G1GC was pausing efficiently (3.2ms average), the gap seems to come from JVM runtime overhead, not garbage collection.

- In Light (serialization), all three languages hit nearly the same throughput: 18,088--18,733 req/s. The massive gap from Prime disappeared.

- In KV (allocation-heavy), all three converged around 7,900 req/s. The workload that should have stressed GC the most produced no measurable throughput difference.

- Go pauses were about 60× shorter than Java pauses (0.054ms vs. 3.2ms average). They represent different design philosophies, but both produced acceptable latency for HTTP services.

These are single-run observations using production frameworks. They measure ecosystem performance, not GC overhead by itself. For these specific workloads, garbage collection overhead was smaller than I expected going in. Whether that would hold for other workloads, longer runs, or different frameworks, I cannot say.

Some follow-up work that would be useful: longer benchmark runs (hours, not minutes) to catch fragmentation and heap-growth effects, repeated runs for confidence intervals, testing without frameworks to isolate language-level performance, and measuring energy consumption alongside throughput.

// Bibliography (excluded from word count by wordometer)
#bibliography("references.bib", style: "ieee")

// Appendices (excluded from word count)
#[
  = Appendices

  Appendices include benchmark data tables, raw CSVs, GC log analysis scripts, and comparison charts.
] <no-wc>
