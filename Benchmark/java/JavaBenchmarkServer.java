import com.sun.net.httpserver.HttpServer;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpExchange;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.util.HashMap;
import java.util.Map;

public class JavaBenchmarkServer {

    public static void main(String[] args) throws IOException {
        int port = args.length > 0 ? Integer.parseInt(args[0]) : 8082;

        HttpServer server = HttpServer.create(new InetSocketAddress(port), 0);

        // C0 Pure Compute (Negative Control)
        server.createContext("/compute/c0a", new C0aHandler());
        server.createContext("/compute/c0b", new C0bHandler());
        server.createContext("/compute/c0c", new C0cHandler());
        server.createContext("/compute/c0d", new C0dHandler());

        // Health check
        server.createContext("/health", new HealthHandler());

        server.setExecutor(null);

        // JVM Warmup
        System.out.println("Warming up JVM...");
        for (int i = 0; i < 50; i++) {
            vectorDotProduct(100000, 1);
            vectorizableVsBranchy(100000, false);
        }
        System.gc(); // Suggest GC after warmup
        System.out.println("Warmup complete");

        server.start();
        System.out.println("Java benchmark server started on port " + port);
    }

    // C0a: Vector dot product/reduction (zero allocation)
    static double vectorDotProduct(int size, int threads) {
        double[] a = new double[size];
        double[] b = new double[size];

        for (int i = 0; i < size; i++) {
            a[i] = i;
            b[i] = i * 2;
        }

        double result = 0.0;
        if (threads == 1) {
            for (int i = 0; i < size; i++) {
                result += a[i] * b[i];
            }
        } else {
            // Simplified multi-threading
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

            try {
                for (Thread worker : workers) {
                    worker.join();
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }

            for (double partial : partialResults) {
                result += partial;
            }
        }

        return result;
    }

    // C0b: Vectorizable vs branch-intensive computation
    static double vectorizableVsBranchy(int size, boolean branchy) {
        double[] data = new double[size];
        for (int i = 0; i < size; i++) {
            data[i] = i * 0.1;
        }

        double result = 0.0;
        if (branchy) {
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
            for (double x : data) {
                result += x * 2.0 + 1.0;
            }
        }

        return result;
    }

    // C0c: FFT/Convolution (pre-allocated work area)
    static double fftConvolution(int size) {
        double[] signal = new double[size];
        double[] kernel = { 0.25, 0.5, 0.25 };

        for (int i = 0; i < size; i++) {
            signal[i] = Math.sin(i * 0.1);
        }

        double[] output = new double[size];

        for (int i = 1; i < size - 1; i++) {
            output[i] = signal[i - 1] * kernel[0] + signal[i] * kernel[1] + signal[i + 1] * kernel[2];
        }

        double result = 0.0;
        for (double val : output) {
            result += val;
        }

        return result;
    }

    // C0d: Allocation strategy comparison
    static double allocationStrategy(int size, boolean usePool) {
        double result = 0.0;

        if (usePool) {
            double[] buffer = new double[100];

            for (int i = 0; i < size; i++) {
                for (int j = 0; j < 100; j++) {
                    buffer[j] = i + j;
                }

                for (double val : buffer) {
                    result += val;
                }
            }
        } else {
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

        return result;
    }

    // Helper methods
    static Map<String, String> parseQuery(String query) {
        Map<String, String> params = new HashMap<>();
        if (query != null) {
            String[] pairs = query.split("&");
            for (String pair : pairs) {
                String[] keyValue = pair.split("=");
                if (keyValue.length == 2) {
                    params.put(keyValue[0], keyValue[1]);
                }
            }
        }
        return params;
    }

    static void sendJsonResponse(HttpExchange exchange, String json) throws IOException {
        exchange.getResponseHeaders().set("Content-Type", "application/json");
        exchange.sendResponseHeaders(200, json.length());
        OutputStream os = exchange.getResponseBody();
        os.write(json.getBytes());
        os.close();
    }
}

class HealthHandler implements HttpHandler {
    @Override
    public void handle(HttpExchange exchange) throws IOException {
        String response = "OK";
        exchange.getResponseHeaders().set("Content-Type", "text/plain");
        exchange.sendResponseHeaders(200, response.length());
        OutputStream os = exchange.getResponseBody();
        os.write(response.getBytes());
        os.close();
    }
}

class C0aHandler implements HttpHandler {
    @Override
    public void handle(HttpExchange exchange) throws IOException {
        Map<String, String> params = JavaBenchmarkServer.parseQuery(exchange.getRequestURI().getQuery());

        int size = Integer.parseInt(params.getOrDefault("size", "1000000"));
        int threads = Integer.parseInt(params.getOrDefault("threads", "1"));

        long startTime = System.nanoTime();
        double result = JavaBenchmarkServer.vectorDotProduct(size, threads);
        long endTime = System.nanoTime();

        double duration = (endTime - startTime) / 1_000_000.0;

        String json = String.format(
                "{\"result\":%.12f,\"duration_ms\":%.3f,\"operations\":%d}",
                result, duration, size);

        JavaBenchmarkServer.sendJsonResponse(exchange, json);
    }
}

class C0bHandler implements HttpHandler {
    @Override
    public void handle(HttpExchange exchange) throws IOException {
        Map<String, String> params = JavaBenchmarkServer.parseQuery(exchange.getRequestURI().getQuery());

        int size = Integer.parseInt(params.getOrDefault("size", "1000000"));
        boolean branchy = Boolean.parseBoolean(params.getOrDefault("branchy", "false"));

        long startTime = System.nanoTime();
        double result = JavaBenchmarkServer.vectorizableVsBranchy(size, branchy);
        long endTime = System.nanoTime();

        double duration = (endTime - startTime) / 1_000_000.0;

        String json = String.format(
                "{\"result\":%.12f,\"duration_ms\":%.3f,\"operations\":%d}",
                result, duration, size);

        JavaBenchmarkServer.sendJsonResponse(exchange, json);
    }
}

class C0cHandler implements HttpHandler {
    @Override
    public void handle(HttpExchange exchange) throws IOException {
        Map<String, String> params = JavaBenchmarkServer.parseQuery(exchange.getRequestURI().getQuery());

        int size = Integer.parseInt(params.getOrDefault("size", "2048"));

        long startTime = System.nanoTime();
        double result = JavaBenchmarkServer.fftConvolution(size);
        long endTime = System.nanoTime();

        double duration = (endTime - startTime) / 1_000_000.0;

        String json = String.format(
                "{\"result\":%.12f,\"duration_ms\":%.3f,\"operations\":%d}",
                result, duration, size * 3);

        JavaBenchmarkServer.sendJsonResponse(exchange, json);
    }
}

class C0dHandler implements HttpHandler {
    @Override
    public void handle(HttpExchange exchange) throws IOException {
        Map<String, String> params = JavaBenchmarkServer.parseQuery(exchange.getRequestURI().getQuery());

        int size = Integer.parseInt(params.getOrDefault("size", "10000"));
        boolean usePool = Boolean.parseBoolean(params.getOrDefault("use_pool", "true"));

        long startTime = System.nanoTime();
        double result = JavaBenchmarkServer.allocationStrategy(size, usePool);
        long endTime = System.nanoTime();

        double duration = (endTime - startTime) / 1_000_000.0;

        String json = String.format(
                "{\"result\":%.12f,\"duration_ms\":%.3f,\"operations\":%d}",
                result, duration, size * 100);

        JavaBenchmarkServer.sendJsonResponse(exchange, json);
    }
}
