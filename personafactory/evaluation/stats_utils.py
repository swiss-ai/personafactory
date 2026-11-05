"""Small statistics helpers shared by the evaluation scripts."""
import math


def wilson(k, n, z=1.96):
    """95% Wilson score interval for k successes out of n, as (lo, hi) fractions; None if n == 0."""
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def wilson_pct(k, n, z=1.96, nd=1):
    """Wilson interval in percent, rounded: {'pct', 'lo', 'hi', 'n'}; None if n == 0."""
    if not n:
        return None
    lo, hi = wilson(k, n, z)
    return {'pct': round(100 * k / n, nd), 'lo': round(100 * lo, nd), 'hi': round(100 * hi, nd), 'n': n}
