fn main() {
    // Example usage
    let n = 10;
    println!("The {}th Fibonacci number is: {}", n, fibonacci(n));

    // Print first 20 Fibonacci numbers
    println!("First 20 Fibonacci numbers:");
    for i in 0..20 {
        print!("{} ", fibonacci(i));
    }
    println!();
}

fn fibonacci(n: u32) -> u64 {
    // Base case
    if n <= 1 {
        return n as u64;
    }

    // Recursive case: fib(n) = fib(n-1) + fib(n-2)
    fibonacci(n - 1) + fibonacci(n - 2)
}
