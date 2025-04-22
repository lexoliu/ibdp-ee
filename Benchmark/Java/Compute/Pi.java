public class Pi {

    public static double calculatePi(int terms) {
        double pi = 0.0;
        for (int k = 0; k < terms; k++) {
            if (k % 2 == 0) {
                pi += 1.0 / (2 * k + 1);
            } else {
                pi -= 1.0 / (2 * k + 1);
            }
        }
        return 4 * pi;
    }

    public static void main(String[] args) {
        int terms = 1_000_000;
        double pi = calculatePi(terms);
        System.out.printf("Estimated Pi: %f\n", pi);
    }
}
