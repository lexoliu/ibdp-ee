use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::thread;

fn main() {
    let listener = TcpListener::bind("127.0.0.1:8080").expect("无法绑定地址");
    println!("HTTP Echo Server正在监听 127.0.0.1:8080...");

    for stream in listener.incoming() {
        match stream {
            Ok(stream) => {
                thread::spawn(|| {
                    handle_connection(stream);
                });
            }
            Err(e) => {
                eprintln!("连接失败: {}", e);
            }
        }
    }
}

fn handle_connection(mut stream: TcpStream) {
    let mut buffer = [0; 1024];

    match stream.read(&mut buffer) {
        Ok(size) => {
            if size == 0 {
                return;
            }

            let request_str = String::from_utf8_lossy(&buffer[0..size]);

            let response = format!(
                "HTTP/1.1 200 OK\r\n\
                Content-Type: text/plain; charset=UTF-8\r\n\
                Connection: close\r\n\
                \r\n\
                {}",
                request_str
            );

            match stream.write(response.as_bytes()) {
                Ok(_) => {
                    stream.flush().unwrap();
                    println!("响应已发送");
                }
                Err(e) => {
                    eprintln!("发送响应时出错: {}", e);
                }
            }
        }
        Err(e) => {
            eprintln!("读取请求时出错: {}", e);
        }
    }
}
