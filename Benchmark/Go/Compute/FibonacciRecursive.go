package main

import (
 "fmt"
)

// fibonacci calculates the nth Fibonacci number recursively
func fibonacci(n int) int64 {
 // Base case
 if n <= 1 {
  return int64(n)
 }

 // Recursive case: fib(n) = fib(n-1) + fib(n-2)
 return fibonacci(n-1) + fibonacci(n-2)
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
