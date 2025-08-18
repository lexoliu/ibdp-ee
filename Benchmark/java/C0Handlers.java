import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpExchange;
import java.io.IOException;
import java.io.OutputStream;
import java.util.HashMap;
import java.util.Map;

public class C0Handlers {

    // Helper method to parse query parameters
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

    // Helper method to send JSON response
    static void sendJsonResponse(HttpExchange exchange, String jsonResponse) throws IOException {
        exchange.getResponseHeaders().set("Content-Type", "application/json");
        exchange.sendResponseHeaders(200, jsonResponse.length());
        OutputStream os = exchange.getResponseBody();
        os.write(jsonResponse.getBytes());
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
        Map<String, String> params = C0Handlers.parseQuery(exchange.getRequestURI().getQuery());

        int size = Integer.parseInt(params.getOrDefault("size", "1000000"));
        int threads = Integer.parseInt(params.getOrDefault("threads", "1"));

        C0Tests.C0Response response = C0Tests.vectorDotProduct(size, threads);
        C0Handlers.sendJsonResponse(exchange, response.toJson());
    }
}

class C0bHandler implements HttpHandler {
    @Override
    public void handle(HttpExchange exchange) throws IOException {
        Map<String, String> params = C0Handlers.parseQuery(exchange.getRequestURI().getQuery());

        int size = Integer.parseInt(params.getOrDefault("size", "1000000"));
        boolean branchy = Boolean.parseBoolean(params.getOrDefault("branchy", "false"));

        C0Tests.C0Response response = C0Tests.vectorizableVsBranchy(size, branchy);
        C0Handlers.sendJsonResponse(exchange, response.toJson());
    }
}

class C0cHandler implements HttpHandler {
    @Override
    public void handle(HttpExchange exchange) throws IOException {
        Map<String, String> params = C0Handlers.parseQuery(exchange.getRequestURI().getQuery());

        int size = Integer.parseInt(params.getOrDefault("size", "2048"));

        C0Tests.C0Response response = C0Tests.fftConvolution(size);
        C0Handlers.sendJsonResponse(exchange, response.toJson());
    }
}

class C0dHandler implements HttpHandler {
    @Override
    public void handle(HttpExchange exchange) throws IOException {
        Map<String, String> params = C0Handlers.parseQuery(exchange.getRequestURI().getQuery());

        int size = Integer.parseInt(params.getOrDefault("size", "10000"));
        boolean usePool = Boolean.parseBoolean(params.getOrDefault("use_pool", "true"));

        C0Tests.C0Response response = C0Tests.allocationStrategy(size, usePool);
        C0Handlers.sendJsonResponse(exchange, response.toJson());
    }
}

class A1Handler implements HttpHandler {
    @Override
    public void handle(HttpExchange exchange) throws IOException {
        Map<String, String> params = C0Handlers.parseQuery(exchange.getRequestURI().getQuery());

        int ops = Integer.parseInt(params.getOrDefault("ops", "10000"));
        int size = Integer.parseInt(params.getOrDefault("size", "64"));

        // Simple A1 test (will show poor performance for Java)
        long startTime = System.nanoTime();

        long totalSum = 0;
        for (int i = 0; i < ops; i++) {
            // Create short-lived small objects
            byte[] data = new byte[size];
            for (int j = 0; j < size; j++) {
                data[j] = (byte) (j % 256);
            }

            // Do some computation to prevent optimization
            for (byte b : data) {
                totalSum += b;
            }
        }

        long endTime = System.nanoTime();
        double duration = (endTime - startTime) / 1_000_000.0;

        String jsonResponse = String.format(
                "{\"operations\":%d,\"duration_ms\":%.3f,\"allocations\":%d,\"result\":\"sum_%d\"}",
                ops, duration, ops, totalSum);

        C0Handlers.sendJsonResponse(exchange, jsonResponse);
    }
}
