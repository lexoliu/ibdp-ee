package main

import (
 "fmt"
 "io/ioutil"
 "net"
 "net/http"
)

func main() {
 listener, err := net.Listen("tcp", "127.0.0.1:8080")
 if err != nil {
  fmt.Printf("无法绑定地址: %v\n", err)
  return
 }
 defer listener.Close()

 fmt.Println("HTTP Echo Server正在监听 127.0.0.1:8080...")

 for {
  conn, err := listener.Accept()
  if err != nil {
   fmt.Printf("连接失败: %v\n", err)
   continue
  }

  go handleConnection(conn)
 }
}

func handleConnection(conn net.Conn) {
 defer conn.Close()

 // 读取请求
 request, err := ioutil.ReadAll(conn)
 if err != nil {
  fmt.Printf("处理连接时出错: %v\n", err)
  return
 }

 // 构建响应
 response := "HTTP/1.1 200 OK\r\n" +
  "Content-Type: text/plain; charset=UTF-8\r\n" +
  "Connection: close\r\n" +
  "\r\n" +
  string(request)

 // 发送响应
 _, err = conn.Write([]byte(response))
 if err != nil {
  fmt.Printf("发送响应时出错: %v\n", err)
  return
 }

 fmt.Println("响应已发送")
}
