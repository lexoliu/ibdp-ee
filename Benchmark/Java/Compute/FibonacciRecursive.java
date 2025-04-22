public class FibonacciRecursive {

    public static void main(String[] args) {
        // Example usage
        int n = 10;
        System.out.println(
            "The " + n + "th Fibonacci number is: " + fibonacci(n)
        );

        // Print first 20 Fibonacci numbers
        System.out.println("First 20 Fibonacci numbers:");
        for (int i = 0; i < 20; i++) {
            System.out.print(fibonacci(i) + " ");
        }
        System.out.println();
    }

    public static long fibonacci(int n) {
        // Base case
        if (n <= 1) {
            return n;
        }

        // Recursive case: fib(n) = fib(n-1) + fib(n-2)
        return fibonacci(n - 1) + fibonacci(n - 2);
    }
}
