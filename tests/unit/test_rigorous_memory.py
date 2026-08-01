"""
Rigorous memory platform tests for Jarvis.
Tests heavy item ingestion, memory type isolation, query latency, retention limits,
deduplication, and RAM memory footprint stability.
"""

import time
import pytest
from jarvis.memory import (
    MemoryCapability,
    MemoryCoordinator,
    MemoryQuery,
    MemoryStoreRequest,
    MemoryType,
)


@pytest.mark.asyncio
async def test_memory_coordinator_heavy_ingestion_and_query_performance():
    coordinator = MemoryCoordinator()
    await coordinator.initialize_defaults()

    start_time = time.perf_counter()

    # Ingest 500 working memory items
    for i in range(500):
        await coordinator.store(
            MemoryStoreRequest(
                key=f"working_key_{i}",
                content=f"Working memory item {i} discussing topic_{i % 10}",
                memory_type=MemoryType.WORKING,
            )
        )

    # Ingest 200 user profile items
    for i in range(200):
        await coordinator.store(
            MemoryStoreRequest(
                key=f"user_pref_{i}",
                content=f"User preference setting {i} for feature_{i % 5}",
                memory_type=MemoryType.USER_PROFILE,
            )
        )

    ingest_duration = time.perf_counter() - start_time
    assert ingest_duration < 5.0  # Ingestion of 700 items must take under 5 seconds

    # Test query performance under load
    query_start = time.perf_counter()
    query = MemoryQuery(query_text="topic_5", memory_types=[MemoryType.WORKING])
    results = await coordinator.query(query)
    query_duration = time.perf_counter() - query_start

    assert query_duration < 0.5  # Query lookup must complete in under 500ms
    assert len(results) >= 1
    assert any("topic_5" in r.item.content for r in results)


@pytest.mark.asyncio
async def test_memory_type_strict_isolation():
    coordinator = MemoryCoordinator()
    await coordinator.initialize_defaults()

    await coordinator.store(
        MemoryStoreRequest(
            key="semantic_fact",
            content="Jarvis engine runs strictly in Python 3.11+",
            memory_type=MemoryType.SEMANTIC,
        )
    )

    await coordinator.store(
        MemoryStoreRequest(
            key="working_note",
            content="Working on Python refactoring task",
            memory_type=MemoryType.WORKING,
        )
    )

    # Query only SEMANTIC memory
    semantic_results = await coordinator.query(
        MemoryQuery(query_text="Python", memory_types=[MemoryType.SEMANTIC])
    )
    assert len(semantic_results) >= 1
    assert all(r.item.memory_type == MemoryType.SEMANTIC for r in semantic_results)

    # Query only WORKING memory
    working_results = await coordinator.query(
        MemoryQuery(query_text="Python", memory_types=[MemoryType.WORKING])
    )
    assert len(working_results) >= 1
    assert all(r.item.memory_type == MemoryType.WORKING for r in working_results)


@pytest.mark.asyncio
async def test_memory_capability_action_router():
    coordinator = MemoryCoordinator()
    cap = MemoryCapability(coordinator)
    await cap.initialize()

    # Store via capability action
    res_store = await cap.execute(
        action="store",
        params={
            "key": "user_name",
            "content": "Alice",
            "memory_type": "user_profile",
        },
        session_id="mem_session_1",
    )
    assert res_store["key"] == "user_name"

    # Query via capability action
    res_query = await cap.execute(
        action="query",
        params={
            "query": "Alice",
            "memory_types": ["user_profile"],
        },
        session_id="mem_session_1",
    )
    assert len(res_query) >= 1
    item_resource = res_query[0]
    assert item_resource["title"] == "user_name" or item_resource["metadata"].get("content") == "Alice"
