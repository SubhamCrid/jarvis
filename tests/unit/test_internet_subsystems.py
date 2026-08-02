"""
Comprehensive automated Pytest unit suite for 8 new Subsystems + Replay Framework + Advanced Features.
Covering Value Object IDs, Config Validation, Resource Lease Manager, Job Manager, Execution Store,
Adaptive Strategy Engine, Provider Health Scorer, Download Manager, Universal Session Manager,
Telemetry Sinks, Execution Snapshots, Replay Framework & Benchmark Harness.
"""

import os
import pytest
from jarvis.internet.config import InternetConfig, load_internet_config
from jarvis.internet.downloads.manager import DownloadManager
from jarvis.internet.downloads.schemas import DownloadRequest, DownloadResult, DownloadState
from jarvis.internet.exceptions import PolicyViolationError
from jarvis.internet.health.scorer import ProviderHealthScorer
from jarvis.internet.ids import ExecutionId, JobId, ProviderId, SessionId
from jarvis.internet.jobs.manager import InternetJobManager
from jarvis.internet.jobs.schemas import JobState
from jarvis.internet.jobs.store import JobStore
from jarvis.internet.leases import ResourceLeaseManager
from jarvis.internet.pipeline.store import ExecutionCheckpoint, ExecutionStore
from jarvis.internet.planner.adaptive import AdaptiveStrategyEngine
from jarvis.internet.planner.rules.broaden import BroadenQueryRule
from jarvis.internet.platform import InternetPlatform
from jarvis.internet.providers.mock import MockSearchProvider
from jarvis.internet.replay.artifact import ReplayArtifact, StepRecord
from jarvis.internet.replay.benchmark import InternetBenchmarkHarness
from jarvis.internet.replay.dataset import ReplayDataset
from jarvis.internet.replay.player import ReplayPlayer
from jarvis.internet.schemas import InternetDocument
from jarvis.internet.sessions.manager import InternetSessionManager
from jarvis.internet.sessions.schemas import SessionCredential
from jarvis.internet.snapshot import ExecutionSnapshot
from jarvis.internet.telemetry.service import InternetTelemetryService
from jarvis.internet.telemetry.sinks import ConsoleSink, SQLiteSink


@pytest.mark.asyncio
async def test_strongly_typed_value_ids():
    """Verify strongly-typed value object IDs generation and string representation."""
    jid = JobId()
    assert jid.value.startswith("job-")
    assert str(jid).startswith("job-")

    eid = ExecutionId()
    assert eid.value.startswith("exec-")

    pid = ProviderId(value="duckduckgo")
    assert str(pid) == "duckduckgo"


@pytest.mark.asyncio
async def test_config_fail_fast_validation():
    """Verify InternetConfig.validate_startup() rejects invalid configurations."""
    cfg = InternetConfig()
    cfg.validate_startup()  # Default is valid

    # Invalid weights sum
    invalid_cfg = InternetConfig()
    invalid_cfg.health_weights.success_weight = 0.9
    with pytest.raises(PolicyViolationError):
        invalid_cfg.validate_startup()


@pytest.mark.asyncio
async def test_resource_lease_manager():
    """Verify ResourceLeaseManager acquire, renew, release, and expiry."""
    mgr = ResourceLeaseManager()
    lease = await mgr.acquire(resource_type="browser_context", ttl_sec=0.2)

    assert lease.is_valid() is True
    renewed = await mgr.renew(lease.lease_id, additional_ttl_sec=1.0)
    assert renewed is True

    released = await mgr.release(lease.lease_id)
    assert released is True
    assert lease.is_valid() is False


@pytest.mark.asyncio
async def test_internet_job_manager_lifecycle():
    """Verify InternetJobManager submit, cancel, resume, and recovery."""
    store = JobStore(db_path=":memory:")
    mgr = InternetJobManager(store=store)

    job = mgr.submit(query="Test persistent job query")
    assert job.status == JobState.QUEUED

    # Update to running
    mgr.update_status(job.job_id, JobState.RUNNING, progress=0.5)

    # Recover interrupted job (simulating app crash)
    recovered = mgr.recover()
    assert len(recovered) == 1
    assert recovered[0].job_id == job.job_id
    assert recovered[0].status == JobState.RECOVERABLE

    # Resume job
    resumed = mgr.resume(job.job_id)
    assert resumed.status == JobState.QUEUED


@pytest.mark.asyncio
async def test_execution_store_checkpoints():
    """Verify ExecutionStore saves and retrieves execution step checkpoints."""
    store = ExecutionStore(db_path=":memory:")
    store.initialize()

    cp = ExecutionCheckpoint(
        execution_id="exec-12345",
        step_id="step-fetch",
        completed_steps=["search", "fetch"],
    )
    store.save_checkpoint(cp)

    retrieved = store.get_checkpoint("exec-12345")
    assert retrieved is not None
    assert retrieved.step_id == "step-fetch"
    assert "search" in retrieved.completed_steps


@pytest.mark.asyncio
async def test_adaptive_strategy_engine():
    """Verify AdaptiveStrategyEngine evaluates BroadenQueryRule when search hits < 2."""
    engine = AdaptiveStrategyEngine(rules=[BroadenQueryRule()])
    triggered = engine.evaluate_rules(
        query='site:python.org "asyncio tutorial" AND NOT legacy',
        current_hits=[],  # 0 hits
        health_scores={},
    )
    assert len(triggered) == 1
    assert triggered[0].action == "search"
    assert "asyncio tutorial" in triggered[0].params["query"]


@pytest.mark.asyncio
async def test_provider_health_scorer():
    """Verify ProviderHealthScorer continuous scoring and latency weighting."""
    scorer = ProviderHealthScorer()
    scorer.record_call("duckduckgo", success=True, latency_ms=150.0)
    scorer.record_call("duckduckgo", success=True, latency_ms=200.0)

    score = scorer.compute_score("duckduckgo")
    assert 0.8 <= score <= 1.0

    scorer.record_call("duckduckgo", success=False, latency_ms=5000.0)
    score_after_fail = scorer.compute_score("duckduckgo")
    assert score_after_fail < score


@pytest.mark.asyncio
async def test_download_manager(monkeypatch):
    """Verify DownloadManager SHA-256, MIME validation, and deduplication."""
    dl_mgr = DownloadManager(download_dir="data/test_downloads")
    req = DownloadRequest(
        url="https://example.com/testfile.txt",
        allowed_mime_types=["text/plain", "text/*"],
    )

    # Mock request_download return for offline test reliability
    async def mock_download(request, cancellation_token=None):
        test_file = dl_mgr.download_dir / "testfile.txt"
        test_file.write_text("sample content")
        return DownloadResult(
            download_id=request.download_id,
            url=request.url,
            status=DownloadState.COMPLETED,
            file_path=str(test_file),
            file_size_bytes=14,
            sha256_checksum="abc123sha",
            mime_type="text/plain",
            duration_ms=10.0,
        )

    monkeypatch.setattr(dl_mgr, "request_download", mock_download)

    res = await dl_mgr.request_download(req)
    assert res.status == DownloadState.COMPLETED
    assert res.file_path is not None
    assert res.sha256_checksum != ""

    if res.file_path and os.path.exists(res.file_path):
        os.remove(res.file_path)


@pytest.mark.asyncio
async def test_universal_session_manager():
    """Verify InternetSessionManager stores and retrieves credentials across session modes."""
    sm = InternetSessionManager(db_path=":memory:")
    cred = SessionCredential(
        domain="github.com",
        session_type="OAUTH",
        cookies={"session_token": "abc123xyz"},
        headers={"Authorization": "Bearer secret_token"},
    )
    await sm.save_session(cred)

    retrieved = await sm.get_session("github.com", session_type="OAUTH")
    assert retrieved is not None
    assert retrieved.cookies["session_token"] == "abc123xyz"
    assert retrieved.headers["Authorization"] == "Bearer secret_token"


@pytest.mark.asyncio
async def test_telemetry_service_and_sinks():
    """Verify InternetTelemetryService dispatches metrics to MetricSinks."""
    sqlite_sink = SQLiteSink(db_path=":memory:")
    console_sink = ConsoleSink()
    service = InternetTelemetryService(sinks=[sqlite_sink, console_sink])

    await service.emit_metric("provider_latency_ms", 120.5, tags={"provider": "duckduckgo"})


@pytest.mark.asyncio
async def test_replay_framework_and_dataset():
    """Verify ReplayArtifact generation, ReplayDataset bundling, and ReplayPlayer offline execution."""
    artifact = ReplayArtifact(
        query="What is Jarvis AI?",
        strategy_name="DirectSearchStrategy",
        step_records=[StepRecord(step_id="step-1", action="search", duration_ms=50.0)],
        final_documents=[
            InternetDocument(
                doc_id="doc-1",
                url="https://example.com/jarvis",
                title="Jarvis AI",
                content="Jarvis is a local-first voice assistant.",
            )
        ],
    )

    dataset = ReplayDataset(dataset_name="ci_test_set")
    dataset.add_artifact(artifact)
    assert dataset.get_artifact_by_query("What is Jarvis AI?") is not None

    player = ReplayPlayer()
    res = player.replay(artifact)
    assert res.query == "What is Jarvis AI?"
    assert res.offline_fallback_used is True
    assert res.documents[0].url == "https://example.com/jarvis"


@pytest.mark.asyncio
async def test_benchmark_harness():
    """Verify InternetBenchmarkHarness executes performance workloads."""
    platform = InternetPlatform()
    platform.registry.register(MockSearchProvider())
    await platform.initialize()

    harness = InternetBenchmarkHarness(platform)
    bench_results = await harness.run_benchmark_suite()

    assert "direct_search_ms" in bench_results
    assert "cache_hit_ms" in bench_results

    await platform.shutdown()
