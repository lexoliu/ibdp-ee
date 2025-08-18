public class C0Tests {

    public static class C0Response {
        public double result;
        public double duration_ms;
        public int operations;

        public C0Response(double result, double duration_ms, int operations) {
            this.result = result;
            this.duration_ms = duration_ms;
            this.operations = operations;
        }

        public String toJson() {
            return String.format(
                    "{\"result\":%.12f,\"duration_ms\":%.3f,\"operations\":%d}",
                    result, duration_ms, operations);
        }
    }

    // C0a: Vector dot product/reduction (zero allocation)
    public static C0Response vectorDotProduct(int size, int threads) {
        // Pre-allocate vectors (not counted as dynamic allocation)
        double[] a = new double[size];
        double[] b = new double[size];

        for (int i = 0; i < size; i++) {
            a[i] = i;
            b[i] = i * 2;
        }

        long startTime = System.nanoTime();

        double result;
        if (threads == 1) {
            // Single-threaded dot product
            result = 0.0;
            for (int i = 0; i < size; i++) {
                result += a[i] * b[i];
            }
        } else {
            // Multi-threaded (simplified version)
            int numThreads = Math.min(threads, Runtime.getRuntime().availableProcessors());
            int chunkSize = size / numThreads;
            double[] partialResults = new double[numThreads];
            Thread[] workers = new Thread[numThreads];

            for (int t = 0; t < numThreads; t++) {
                final int threadId = t;
                final int start = threadId * chunkSize;
                final int end = (threadId == numThreads - 1) ? size : (threadId + 1) * chunkSize;

                workers[t] = new Thread(() -> {
                    double sum = 0.0;
                    for (int i = start; i < end; i++) {
                        sum += a[i] * b[i];
                    }
                    partialResults[threadId] = sum;
                });
                workers[t].start();
            }

            // Wait for all threads to complete
            try {
                for (Thread worker : workers) {
                    worker.join();
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new RuntimeException(e);
            }

            result = 0.0;
            for (double partial : partialResults) {
                result += partial;
            }
        }

        long endTime = System.nanoTime();
        double duration = (endTime - startTime) / 1_000_000.0; // Convert to milliseconds

        return new C0Response(result, duration, size);
    }

    // C0b: Vectorizable vs branch-intensive computation
    public static C0Response vectorizableVsBranchy(int size, boolean branchy) {
        double[] data = new double[size];
        for (int i = 0; i < size; i++) {
            data[i] = i * 0.1;
        }

        long startTime = System.nanoTime();

        double result = 0.0;
        if (branchy) {
            // Branch-intensive version
            for (double x : data) {
                if (x < 0.0) {
                    result += x * -1.0;
                } else if (x < 10000.0) {
                    result += x * 2.0 + 1.0;
                } else if (x < 50000.0) {
                    result += Math.sqrt(x);
                } else {
                    result += x / 3.0;
                }
            }
        } else {
            // Vectorizable version
            for (double x : data) {
                result += x * 2.0 + 1.0;
            }
        }

        long endTime = System.nanoTime();
        double duration = (endTime - startTime) / 1_000_000.0;

        return new C0Response(result, duration, size);
    }

    // C0c: FFT/Convolution (pre-allocated work area)
    public static C0Response fftConvolution(int size) {
        // Simple discrete convolution as FFT substitute
        double[] signal = new double[size];
        double[] kernel = { 0.25, 0.5, 0.25 }; // Simple 3-tap filter

        for (int i = 0; i < size; i++) {
            signal[i] = Math.sin(i * 0.1);
        }

        // Pre-allocate output buffer
        double[] output = new double[size];

        long startTime = System.nanoTime();

        // Convolution operation (zero additional allocation)
        for (int i = 1; i < size - 1; i++) {
            output[i] = signal[i - 1] * kernel[0] + signal[i] * kernel[1] + signal[i + 1] * kernel[2];
        }

        double result = 0.0;
        for (double val : output) {
            result += val;
        }

        long endTime = System.nanoTime();
        double duration = (endTime - startTime) / 1_000_000.0;

        return new C0Response(result, duration, size * kernel.length);
    }

    // C0d: Allocation strategy comparison (pre-allocated vs temporary buffers)
    public static C0Response allocationStrategy(int size, boolean usePool) {
        long startTime = System.nanoTime();

        double result = 0.0;

        if (usePool) {
            // Pre-allocated strategy
            double[] buffer = new double[100];

            for (int i = 0; i < size; i++) {
                // Clear and reuse the same buffer
                for (int j = 0; j < 100; j++) {
                    buffer[j] = i + j;
                }

                for (double val : buffer) {
                    result += val;
                }
            }
        } else {
            // Temporary allocation strategy
            for (int i = 0; i < size; i++) {
                double[] buffer = new double[100];
                for (int j = 0; j < 100; j++) {
                    buffer[j] = i + j;
                }

                for (double val : buffer) {
                    result += val;
                }
            }
        }

        long endTime = System.nanoTime();
        double duration = (endTime - startTime) / 1_000_000.0;

        return new C0Response(result, duration, size * 100);
    }
}
