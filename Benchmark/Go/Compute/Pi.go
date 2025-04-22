// Calculate pi

package main

import (
    "fmt"
)

func calculatePi(terms int) float64 {
    pi := 0.0
    for k := 0; k < terms; k++ {
        if k%2 == 0 {
            pi += 1.0 / float64(2*k+1)
        } else {
            pi -= 1.0 / float64(2*k+1)
        }
    }
    return 4 * pi
}

func main() {
    terms := 1000000
    pi := calculatePi(terms)
    fmt.Printf("Estimated Pi: %f\n", pi)
}
