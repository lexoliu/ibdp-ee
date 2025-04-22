import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.ByteBuffer;
import java.nio.channels.AsynchronousServerSocketChannel;
import java.nio.channels.AsynchronousSocketChannel;
import java.nio.channels.CompletionHandler;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

public class WebServerNIO {

    public static void main(String[] args) {
        try {
            AsynchronousServerSocketChannel serverChannel =
                AsynchronousServerSocketChannel.open();
            serverChannel.bind(new InetSocketAddress("127.0.0.1", 8080));
            System.out.println("HTTP Echo Server正在监听 127.0.0.1:8080...");

            serverChannel.accept(
                null,
                new CompletionHandler<AsynchronousSocketChannel, Void>() {
                    @Override
                    public void completed(
                        AsynchronousSocketChannel clientChannel,
                        Void attachment
                    ) {
                        // Accept the next connection
                        serverChannel.accept(null, this);

                        // Handle this connection
                        handleConnection(clientChannel);
                    }

                    @Override
                    public void failed(Throwable exc, Void attachment) {
                        System.err.println("连接失败: " + exc.getMessage());
                    }
                }
            );

            // Keep the main thread alive
            try {
                Thread.currentThread().join();
            } catch (InterruptedException e) {
                System.err.println("服务器中断: " + e.getMessage());
            }
        } catch (IOException e) {
            System.err.println("无法绑定地址: " + e.getMessage());
        }
    }

    private static void handleConnection(
        AsynchronousSocketChannel clientChannel
    ) {
        ByteBuffer buffer = ByteBuffer.allocate(4096);
        StringBuilder requestBuilder = new StringBuilder();

        readData(clientChannel, buffer, requestBuilder, response -> {
            try {
                ByteBuffer responseBuffer = ByteBuffer.wrap(
                    response.getBytes(StandardCharsets.UTF_8)
                );
                Future<Integer> writeFuture = clientChannel.write(
                    responseBuffer
                );

                writeFuture.get(30, TimeUnit.SECONDS);
                System.out.println("响应已发送");

                clientChannel.close();
            } catch (Exception e) {
                System.err.println("发送响应时出错: " + e.getMessage());
            }
        });
    }

    private static void readData(
        AsynchronousSocketChannel clientChannel,
        ByteBuffer buffer,
        StringBuilder requestBuilder,
        java.util.function.Consumer<String> onComplete
    ) {
        clientChannel.read(
            buffer,
            null,
            new CompletionHandler<Integer, Void>() {
                @Override
                public void completed(Integer result, Void attachment) {
                    if (result > 0) {
                        buffer.flip();
                        byte[] data = new byte[buffer.remaining()];
                        buffer.get(data);
                        requestBuilder.append(
                            new String(data, StandardCharsets.UTF_8)
                        );
                        buffer.clear();

                        // Check if we have read the full request
                        String request = requestBuilder.toString();
                        if (request.contains("\r\n\r\n")) {
                            String response =
                                "HTTP/1.1 200 OK\r\n" +
                                "Content-Type: text/plain; charset=UTF-8\r\n" +
                                "Connection: close\r\n" +
                                "\r\n" +
                                request;

                            onComplete.accept(response);
                        } else {
                            // Continue reading
                            clientChannel.read(buffer, null, this);
                        }
                    } else {
                        // End of stream reached
                        String request = requestBuilder.toString();
                        String response =
                            "HTTP/1.1 200 OK\r\n" +
                            "Content-Type: text/plain; charset=UTF-8\r\n" +
                            "Connection: close\r\n" +
                            "\r\n" +
                            request;

                        onComplete.accept(response);
                    }
                }

                @Override
                public void failed(Throwable exc, Void attachment) {
                    System.err.println("读取请求时出错: " + exc.getMessage());
                    try {
                        clientChannel.close();
                    } catch (IOException e) {
                        System.err.println("关闭连接时出错: " + e.getMessage());
                    }
                }
            }
        );
    }
}
