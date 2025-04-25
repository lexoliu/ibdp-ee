public class FibonacciLoop {

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
        if (n <= 1) {
            return n;
        }

        long a = 0;
        long b = 1;

        for (int i = 2; i <= n; i++) {
            long temp = a + b;
            a = b;
            b = temp;
        }

        return b;
    }
}
