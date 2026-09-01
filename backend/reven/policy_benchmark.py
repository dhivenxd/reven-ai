"""
Canonical policy benchmark entry point.

The actual benchmark lives in uplift_benchmark.py. Keeping a thin
wrapper here prevents the project from having two competing benchmark
implementations with different probability models.
"""

from backend.reven.uplift_benchmark import run_uplift_benchmark


def run_policy_benchmark(
    customer_count: int = 10_000,
    seed: int = 42,
) -> None:
    run_uplift_benchmark(
        customer_count=customer_count,
        seed=seed,
    )


if __name__ == "__main__":
    run_policy_benchmark(
        customer_count=10_000,
        seed=42,
    )
