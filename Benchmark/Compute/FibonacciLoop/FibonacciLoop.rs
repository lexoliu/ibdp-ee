fn fibonacci(n: u32) -> u64 {
    if n <= 1 {
        return n as u64;
    }

    let mut a = 0;
    let mut b = 1;

    for _ in 2..=n {
        let temp = a + b;
        a = b;
        b = temp;
    }

    b
}

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
