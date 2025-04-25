package main

import (
    "fmt"
    "os"
    "strconv"
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
    terms, _ := strconv.Atoi(os.Args[1])
    pi := calculatePi(terms)
    fmt.Printf("%.12f\n", pi)
}