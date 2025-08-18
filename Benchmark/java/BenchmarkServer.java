import com.sun.net.httpserver.HttpServer;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpExchange;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class BenchmarkServer {
    private static final Map<String, byte[]> dataStore = new ConcurrentHashMap<>();
    
    public static void main(String[] args) throws IOException {
        int port = args.length > 0 ? Integer.parseInt(args[0]) : 8080;
        
        HttpServer server = HttpServer.create(new InetSocketAddress(port), 0);
        
        // C0 Pure Compute (Negative Control)
        server.createContext("/compute/c0a", new C0aHandler());
        server.createContext("/compute/c0b", new C0bHandler());
        server.createContext("/compute/c0c", new C0cHandler());
        server.createContext("/compute/c0d", new C0dHandler());
        
        // Micro Tests (for academic rigor, even though we expect poor performance)
        server.createContext("/compute/a1", new A1Handler());
        
        // Health check
        server.createContext("/health", new HealthHandler());
        
        server.setExecutor(null);
        
        // JVM Warmup
        System.out.println("Warming up JVM...");
        for (int i = 0; i < 50; i++) {
            C0Tests.vectorDotProduct(100000, 1);
            C0Tests.vectorizableVsBranchy(100000, false);
        }
        System.gc(); // Suggest GC after warmup
        System.out.println("Warmup complete");
        
        server.start();
        System.out.println("Java benchmark server started on port " + port);
    }
    
    static class HealthHandler implements HttpHandler {
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
}
