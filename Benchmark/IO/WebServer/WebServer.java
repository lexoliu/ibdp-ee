import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.ServerSocket;
import java.net.Socket;

public class WebServer {

    public static void main(String[] args) {
        try {
            ServerSocket serverSocket = new ServerSocket(8080);
            System.out.println("HTTP Echo Server正在监听 127.0.0.1:8080...");

            while (true) {
                try {
                    Socket clientSocket = serverSocket.accept();

                    new Thread(() -> {
                        handleConnection(clientSocket);
                    }).start();
                } catch (IOException e) {
                    System.err.println("连接失败: " + e.getMessage());
                    serverSocket.close();
                }
            }
        } catch (IOException e) {
            System.err.println("无法绑定地址: " + e.getMessage());
        }
    }

    private static void handleConnection(Socket clientSocket) {
        try {
            BufferedReader reader = new BufferedReader(
                new InputStreamReader(clientSocket.getInputStream())
            );
            OutputStream output = clientSocket.getOutputStream();

            StringBuilder requestBuilder = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null && !line.isEmpty()) {
                requestBuilder.append(line).append("\r\n");
            }

            char[] body = new char[1024];
            if (reader.ready()) {
                reader.read(body);
                requestBuilder.append(new String(body).trim());
            }

            String requestStr = requestBuilder.toString();

            String response =
                "HTTP/1.1 200 OK\r\n" +
                "Content-Type: text/plain; charset=UTF-8\r\n" +
                "Connection: close\r\n" +
                "\r\n" +
                requestStr;

            output.write(response.getBytes());
            output.flush();
            System.out.println("响应已发送");

            clientSocket.close();
        } catch (IOException e) {
            System.err.println("处理连接时出错: " + e.getMessage());
        }
    }
}
