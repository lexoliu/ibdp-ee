#!/usr/bin/env python3

import numpy as np

def generate_matrix(rows, cols, rule='mul'):
    if rule == 'mul':
        return np.fromfunction(lambda i, j: i * j, (rows, cols), dtype=int)
    elif rule == 'add':
        return np.fromfunction(lambda i, j: i + j, (rows, cols), dtype=int)
    elif rule == 'ones':
        return np.ones((rows, cols), dtype=int)
    else:
        raise ValueError("Unsupported rule.")

def save_matrix_as_csv(matrix, filename):
    with open(filename, 'w') as f:
        for row in matrix:
            f.write(','.join(str(x) for x in row) + '\n')

if __name__ == "__main__":
    rows, cols = 1000, 1000
    a = generate_matrix(rows, cols, rule='mul')
    b = generate_matrix(cols, rows, rule='add')

    save_matrix_as_csv(a, 'a.csv')
    save_matrix_as_csv(b, 'b.csv')

    print("✅ Saved two matrixs")