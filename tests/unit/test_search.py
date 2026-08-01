"""
Unit tests for Jarvis Search Platform.
Tests DSL parsing, query planning, search sandbox confinement, ranking,
multi-provider merging, caching, sessions, streaming, providers, and orchestrator integration.
"""

import asyncio
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from jarvis.orchestrator import AssistantOrchestrator
from jarvis.search.adapter import SearchToolAdapter
from jarvis.search.cache import SearchCache
from jarvis.search.capability import SearchCapability
from jarvis.search.config import SearchConfig
from jarvis.search.dsl import SearchDSLParser
from jarvis.search.filter import SearchFilterEngine
from jarvis.search.index_manager import SearchIndexManager
from jarvis.search.merge import SearchMergeEngine
from jarvis.search.pipeline import SearchPipelineEngine
from jarvis.search.planner import SearchQueryPlanner
from jarvis.search.providers.filesystem import FilesystemSearchProvider
from jarvis.search.providers.ripgrep import RipgrepSearchProvider
from jarvis.search.ranking import SearchRanker
from jarvis.search.registry import SearchProviderRegistry
from jarvis.search.sandbox import SearchRootSandbox, SearchSandboxError
from jarvis.search.schemas import (
    SearchMatch,
    SearchQuery,
    SearchResponse,
    SearchTargetType,
)
from jarvis.search.session import SearchSessionStore


@pytest.fixture
def temp_search_workspace():
    with TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir).resolve()
        # Create test search hierarchy
        (ws / "notes.txt").write_text("Hello Search Platform", encoding="utf-8")
        (ws / "report.pdf").write_text("%PDF-dummy-content", encoding="utf-8")
        (ws / "script.py").write_text("print('hello world')", encoding="utf-8")
        (ws / "sub").mkdir()
        (ws / "sub" / "data.json").write_text('{"key": "value"}', encoding="utf-8")
        yield ws


def test_search_dsl_parser():
    query_str = "kind:file ext:py,txt size>1KB path:sub hello"
    parsed = SearchDSLParser.parse(query_str)

    assert parsed.target_type == SearchTargetType.FILE
    assert "py" in parsed.extensions and "txt" in parsed.extensions
    assert parsed.min_size_bytes == 1024
    assert parsed.search_root == "sub"
    assert parsed.clean_query == "hello"


def test_query_planner():
    query_content = SearchQuery(raw_query="find text", target_type=SearchTargetType.CONTENT)
    plan_content = SearchQueryPlanner.plan(query_content, ["ripgrep", "filesystem"])
    assert plan_content.strategy == "content_search"
    assert "ripgrep" in plan_content.primary_providers

    query_file = SearchQuery(raw_query="report.pdf", target_type=SearchTargetType.FILE)
    plan_file = SearchQueryPlanner.plan(query_file, ["everything", "windows_index", "filesystem"])
    assert plan_file.strategy == "filename_search"


def test_search_root_sandbox(temp_search_workspace):
    sandbox = SearchRootSandbox(temp_search_workspace)

    valid = sandbox.validate_path("notes.txt")
    assert valid == (temp_search_workspace / "notes.txt").resolve()

    with pytest.raises(SearchSandboxError):
        sandbox.validate_path("../../../etc/passwd")


def test_search_ranker():
    query = SearchQuery(raw_query="script.py", clean_query="script.py")
    matches = [
        SearchMatch(path="/ws/other.txt", filename="other.txt", score=0.2),
        SearchMatch(path="/ws/script.py", filename="script.py", score=0.5),
    ]

    ranked = SearchRanker.rank(query, matches)
    assert len(ranked) == 2
    assert ranked[0].filename == "script.py"
    assert ranked[0].score > ranked[1].score


def test_merge_engine():
    m1 = SearchMatch(path="/ws/file1.txt", filename="file1.txt", score=0.5)
    m2 = SearchMatch(path="/ws/file1.txt", filename="file1.txt", score=0.9, highlights=["line 1"])
    m3 = SearchMatch(path="/ws/file2.txt", filename="file2.txt", score=0.7)

    merged = SearchMergeEngine.merge([[m1], [m2, m3]])
    assert len(merged) == 2
    # Check deduplicated item has highest score
    file1_match = [m for m in merged if m.filename == "file1.txt"][0]
    assert file1_match.score == 0.9
    assert "line 1" in file1_match.highlights


@pytest.mark.asyncio
async def test_filesystem_search_provider(temp_search_workspace):
    provider = FilesystemSearchProvider()

    query = SearchQuery(
        raw_query="notes",
        clean_query="notes",
        search_root=str(temp_search_workspace),
    )

    matches = await provider.search(query)
    assert len(matches) >= 1
    assert any(m.filename == "notes.txt" for m in matches)


def test_search_cache():
    cache = SearchCache(ttl_sec=60.0)
    resp = SearchResponse(query="notes", matches=[], total_found=0)

    cache.put("key1", resp)
    cached = cache.get("key1")

    assert cached is not None
    assert cached.cached is True


def test_search_session_store():
    store = SearchSessionStore()
    query = SearchQuery(raw_query="test")
    matches = [SearchMatch(path=f"/ws/file{i}.txt", filename=f"file{i}.txt") for i in range(15)]

    store.update_session("sess1", query, matches)
    item_3 = store.get_result_by_index("sess1", 3)
    assert item_3 is not None
    assert item_3.filename == "file2.txt"

    next_page = store.get_next_page("sess1", page_size=5)
    assert len(next_page) == 5


@pytest.mark.asyncio
async def test_index_manager(temp_search_workspace):
    idx_mgr = SearchIndexManager(
        db_path=temp_search_workspace / "index.db",
        workspace_root=temp_search_workspace,
    )

    indexed = await idx_mgr.index_workspace()
    assert indexed >= 3

    results = idx_mgr.query_index("report")
    assert len(results) >= 1
    assert results[0].filename == "report.pdf"


@pytest.mark.asyncio
async def test_search_pipeline_end_to_end(temp_search_workspace):
    cfg = SearchConfig(search_root=temp_search_workspace)
    pipeline = SearchPipelineEngine(config=cfg)
    pipeline.registry.register(FilesystemSearchProvider())

    response = await pipeline.execute_search("notes.txt")
    assert response is not None
    assert response.total_found >= 1
    assert response.matches[0].filename == "notes.txt"


@pytest.mark.asyncio
async def test_orchestrator_search_integration():
    orchestrator = AssistantOrchestrator()
    initialized = await orchestrator.initialize()
    assert initialized is True

    # Test processing search task via search_system tool
    result = await orchestrator.process_task(
        session_id="test_search_sess",
        task_type="tool_call",
        payload={"tool_name": "search_system", "params": {"query": "notes.txt"}},
    )

    assert result is not None
    assert result.success is True

    health = await orchestrator.health()
    assert "search_platform_health" in health.details

    await orchestrator.shutdown()
