"""
InternetBenchmarkHarness for repeatable performance & regression testing.
"""

import time
from typing import Any, Dict
from jarvis.internet.platform import InternetPlatform
from jarvis.internet.providers.mock import MockSearchProvider


class InternetBenchmarkHarness:
    """Repeatable benchmark suite measuring latency, memory, and throughput."""

    def __init__(self, platform: InternetPlatform) -> None:
        self.platform = platform

    async def run_benchmark_suite(self) -> Dict[str, Any]:
        """Run standard benchmark workloads."""
        results = {}

        # 1. Direct search benchmark
        start_t = time.time()
        res1 = await self.platform.execute_query("Wikipedia search benchmark")
        dur1 = (time.time() - start_t) * 1000.0
        results["direct_search_ms"] = round(dur1, 2)
        results["direct_search_docs_count"] = len(res1.documents)

        # 2. Cache hit benchmark
        start_t2 = time.time()
        res2 = await self.platform.execute_query("Wikipedia search benchmark")
        dur2 = (time.time() - start_t2) * 1000.0
        results["cache_hit_ms"] = round(dur2, 2)

        return results
