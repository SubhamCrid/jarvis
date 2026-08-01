"""
Unit tests for jarvis.memory platform.
"""

import pytest
from jarvis.memory import (
    MemoryCoordinator,
    MemoryType,
    MemoryStoreRequest,
    MemoryQuery,
    MemoryCapability,
    MockEmbeddingProvider,
)


@pytest.mark.asyncio
async def test_memory_coordinator_store_and_query():
    coordinator = MemoryCoordinator()
    await coordinator.initialize_defaults()

    # Store working memory item
    req1 = MemoryStoreRequest(
        key="active_topic",
        content="Discussing Jarvis 0.1% platform capabilities",
        memory_type=MemoryType.WORKING,
    )
    item1 = await coordinator.store(req1)
    assert item1.key == "active_topic"

    # Store user profile memory item
    req2 = MemoryStoreRequest(
        key="preferred_language",
        content="Python",
        memory_type=MemoryType.USER_PROFILE,
    )
    await coordinator.store(req2)

    # Query working memory
    q = MemoryQuery(query_text="Jarvis", memory_types=[MemoryType.WORKING])
    results = await coordinator.query(q)
    assert len(results) >= 1
    assert "capabilities" in results[0].item.content


@pytest.mark.asyncio
async def test_memory_coordinator_resources():
    coordinator = MemoryCoordinator()
    await coordinator.initialize_defaults()

    await coordinator.store(
        MemoryStoreRequest(
            key="fact-1",
            content="Jarvis has 8 core platform capabilities",
            memory_type=MemoryType.SEMANTIC,
        )
    )

    q = MemoryQuery(query_text="Jarvis", memory_types=[MemoryType.SEMANTIC])
    resources = await coordinator.query_as_resources(q)
    assert len(resources) >= 1
    assert resources[0].uri.startswith("memory://semantic/")


@pytest.mark.asyncio
async def test_memory_capability():
    coordinator = MemoryCoordinator()
    cap = MemoryCapability(coordinator)
    await cap.initialize()

    res_store = await cap.execute(
        action="store",
        params={"key": "k1", "content": "v1", "memory_type": "working"},
        session_id="s1",
    )
    assert res_store["key"] == "k1"

    res_query = await cap.execute(
        action="query",
        params={"query": "v1", "memory_types": ["working"]},
        session_id="s1",
    )
    assert len(res_query) >= 1


@pytest.mark.asyncio
async def test_mock_embeddings():
    embedder = MockEmbeddingProvider(dimension=32)
    vec = await embedder.embed_text("test string")
    assert len(vec) == 32
