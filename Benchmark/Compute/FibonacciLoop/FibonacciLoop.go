package main

import (
 "fmt"
)

// Fibonacci calculates the nth Fibonacci number using an iterative approach
func fibonacci(n int) int64 {
 if n <= 1 {
  return int64(n)
 }

 var a, b int64 = 0, 1

 for i := 2; i <= n; i++ {
  temp := a + b
  a = b
  b = temp
 }

 return b
}

func main() {
 // Example usage
 n := 10
 fmt.Printf("The %dth Fibonacci number is: %d\n", n, fibonacci(n))

 // Print first 20 Fibonacci numbers
 fmt.Println("First 20 Fibonacci numbers:")
 for i := 0; i < 20; i++ {
  fmt.Printf("%d ", fibonacci(i))
 }
 fmt.Println()
}
