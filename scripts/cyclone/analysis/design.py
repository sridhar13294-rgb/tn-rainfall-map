"""51-member design for many 3-level inputs: member 0 = every input as observed; members 1-50: each input's three
settings used 16-17 times, and for every pair of inputs all 9 combinations of their settings appear (at least 3 times
where possible), with the inputs as uncorrelated as possible. Built once by a fixed search (seeded), so it never changes."""
import numpy as np, functools
@functools.lru_cache(None)
def design(k, n=50, seed=2026, iters=40000):
    rng = np.random.default_rng(seed)
    base = np.array([i % 3 for i in range(n)])
    X = np.stack([rng.permutation(base) for _ in range(k)], 1)
    def score(X):
        s = 0.0
        for a in range(k):
            for b in range(a + 1, k):
                c = np.bincount(X[:, a] * 3 + X[:, b], minlength=9); s += ((c - n / 9) ** 2).sum() + 50 * (c < 3).sum()
        return s
    best = score(X)
    for _ in range(iters):
        j = rng.integers(k); r1, r2 = rng.integers(n, size=2)
        if X[r1, j] == X[r2, j]: continue
        X[[r1, r2], j] = X[[r2, r1], j]; s = score(X)
        if s <= best: best = s
        else: X[[r1, r2], j] = X[[r2, r1], j]
    return [[1] * k] + X.tolist()
def check(D):
    D = np.array(D[1:]); k = D.shape[1]; mins = []
    for a in range(k):
        for b in range(a + 1, k): mins.append(np.bincount(D[:, a] * 3 + D[:, b], minlength=9).min())
    return dict(per_setting=[np.bincount(D[:, j], minlength=3).tolist() for j in range(k)][:3], min_pair_count=int(min(mins)), max_corr=float(np.max(np.abs(np.corrcoef(D.T) - np.eye(k)))))
