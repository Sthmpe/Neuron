"""Small matrix helpers. A matrix is a list of rows; each row is a list of numbers."""


def shape(m):
    return (len(m), len(m[0]) if m else 0)


def transpose(m):
    rows, cols = shape(m)
    return [[m[r][c] for r in range(rows)] for c in range(cols)]


def multiply(a, b):
    """Matrix product a x b."""
    a_rows, a_cols = shape(a)
    b_rows, b_cols = shape(b)
    if a_cols != b_rows:
        raise ValueError("shapes do not match")
    result = []
    for i in range(a_rows):
        row = []
        for j in range(b_cols):
            row.append(sum(a[i][k] * b[k][j] for k in range(a_cols)))
        result.append(row)
    return result


def identity(n):
    return [[1 if r == c else 0 for c in range(n)] for r in range(n)]
