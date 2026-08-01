"""
Unit tests for Jarvis modular tool execution platform.
Tests path sandboxing, command safety, cancellation, secret redaction,
schema exporters, tool runner, and orchestrator integration.
"""

import asyncio
import os
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from jarvis.orchestrator import AssistantOrchestrator
from jarvis.tools.adapters.file_tools import (
    ListDirectoryTool,
    ReadFileTool,
    SearchFilesTool,
    WriteFileTool,
)
from jarvis.tools.adapters.shell_tools import RunCommandSafeTool
from jarvis.tools.config import ToolsConfig
from jarvis.tools.concurrency import ResourceLockManager
from jarvis.tools.exporters.ollama import OllamaSchemaExporter
from jarvis.tools.exporters.openai import OpenAISchemaExporter
from jarvis.tools.exporters.xml_prompt import XMLPromptExporter
from jarvis.tools.health import ToolHealthCheck
from jarvis.tools.normalizer import ToolNormalizer
from jarvis.tools.persistence import ToolStore
from jarvis.tools.policy import PolicyDecision, ToolPolicyEngine
from jarvis.tools.redactor import OutputRedactor
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.runner import ToolRunner
from jarvis.tools.sandbox import PathSandbox, PathTraversalError
from jarvis.tools.schemas import (
    AuditEvent,
    CancellationToken,
    ExecutionContext,
    PermissionLevel,
    SideEffectLevel,
    ToolCall,
    ToolManifest,
    ToolResult,
    ToolSpec,
)
from jarvis.tools.validator import ToolValidator, ValidationError


@pytest.fixture
def temp_workspace():
    with TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir).resolve()
        # Create test files
        (ws / "hello.txt").write_text("Hello Jarvis World!\nLine 2\nLine 3", encoding="utf-8")
        (ws / "config.json").write_text('{"api_key": "sk-1234567890abcdef123456"}', encoding="utf-8")
        (ws / "sub").mkdir()
        (ws / "sub" / "data.csv").write_text("a,b,c\n1,2,3", encoding="utf-8")
        yield ws


@pytest.mark.asyncio
async def test_path_sandbox_confinement(temp_workspace):
    sandbox = PathSandbox(temp_workspace)

    # Valid relative path
    resolved = sandbox.validate_and_resolve("hello.txt", must_exist=True)
    assert resolved == (temp_workspace / "hello.txt").resolve()

    # Valid subdirectory path
    resolved_sub = sandbox.validate_and_resolve("sub/data.csv", must_exist=True)
    assert resolved_sub == (temp_workspace / "sub" / "data.csv").resolve()

    # Path traversal attack attempting to escape workspace
    with pytest.raises(PathTraversalError):
        sandbox.validate_and_resolve("../../../etc/passwd")

    with pytest.raises(PathTraversalError):
        sandbox.validate_and_resolve("sub/../../outside.txt")


def test_output_redactor():
    text = "User key is sk-1234567890abcdef123456 and token is Bearer secret_token_abc"
    redacted = OutputRedactor.redact_text(text)
    assert "[REDACTED_API_KEY]" in redacted
    assert "Bearer [REDACTED_TOKEN]" in redacted

    nested = {
        "password": "my_super_secret_pass",
        "nested": {"api_key": "sk-abcdef1234567890123456"},
    }
    redacted_data = OutputRedactor.redact_data(nested)
    assert redacted_data["password"] == "[REDACTED]"
    assert redacted_data["nested"]["api_key"] == "[REDACTED]"


@pytest.mark.asyncio
async def test_resource_lock_manager():
    lock_mgr = ResourceLockManager()
    key = "file.txt"

    async with lock_mgr.lock_resource(key):
        assert lock_mgr.active_locks_count() == 1


def test_tool_validator():
    spec = ToolSpec(
        manifest=ToolManifest(name="test_tool"),
        parameters_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    )

    # Valid
    clean = ToolValidator.validate(spec, {"path": "hello.txt"})
    assert clean["path"] == "hello.txt"

    # Missing required
    with pytest.raises(ValidationError):
        ToolValidator.validate(spec, {})


def test_policy_engine(temp_workspace):
    cfg = ToolsConfig(workspace_root=temp_workspace, policy_mode="STRICT")
    policy = ToolPolicyEngine(cfg)

    read_spec = ToolSpec(manifest=ToolManifest(name="read", permission_level=PermissionLevel.READ_ONLY, read_only=True))
    assert policy.evaluate(read_spec, {}).allowed is True

    # Forbidden shell command
    shell_spec = ToolSpec(manifest=ToolManifest(name="run_command_safe", permission_level=PermissionLevel.RISKY, read_only=False))
    forbidden_dec = policy.evaluate(shell_spec, {"argv": ["rm", "-rf", "/"]})
    assert forbidden_dec.allowed is False
    assert "forbidden" in forbidden_dec.reason.lower()


@pytest.mark.asyncio
async def test_file_tool_adapters(temp_workspace):
    read_tool = ReadFileTool(temp_workspace)
    write_tool = WriteFileTool(temp_workspace)
    list_tool = ListDirectoryTool(temp_workspace)
    search_tool = SearchFilesTool(temp_workspace)
    ctx = ExecutionContext(session_id="s1", task_id="t1")

    # Read
    res_read = await read_tool.execute({"path": "hello.txt"}, ctx)
    assert "Hello Jarvis World!" in res_read["content"]

    # Write
    res_write = await write_tool.execute({"path": "new.txt", "content": "Sample text"}, ctx)
    assert res_write["success"] is True
    assert (temp_workspace / "new.txt").exists()

    # List
    res_list = await list_tool.execute({"path": "."}, ctx)
    assert res_list["total_items"] >= 3

    # Search
    res_search = await search_tool.execute({"pattern": "*.txt"}, ctx)
    assert "hello.txt" in res_search["matches"] or any("hello.txt" in m for m in res_search["matches"])


@pytest.mark.asyncio
async def test_shell_tool_adapter(temp_workspace):
    shell_tool = RunCommandSafeTool(temp_workspace)
    ctx = ExecutionContext(session_id="s1", task_id="t1")

    # Safe command python --version or echo
    cmd = ["python", "--version"]
    res = await shell_tool.execute({"argv": cmd}, ctx)
    assert res["success"] is True
    assert res["exit_code"] == 0


@pytest.mark.asyncio
async def test_cancellation_token():
    token = CancellationToken()
    assert token.is_cancelled() is False
    token.cancel()
    assert token.is_cancelled() is True


def test_schema_exporters():
    spec = ToolSpec(
        manifest=ToolManifest(name="read_file", description="Read a file."),
        parameters_schema={"type": "object", "properties": {"path": {"type": "string"}}},
    )

    ollama_exp = OllamaSchemaExporter()
    exported_ollama = ollama_exp.export([spec])
    assert len(exported_ollama) == 1
    assert exported_ollama[0]["function"]["name"] == "read_file"

    openai_exp = OpenAISchemaExporter()
    exported_openai = openai_exp.export([spec])
    assert exported_openai[0]["function"]["name"] == "read_file"

    xml_exp = XMLPromptExporter()
    exported_xml = xml_exp.export([spec])
    assert "<tool name=\"read_file\">" in exported_xml


@pytest.mark.asyncio
async def test_tool_runner_execution(temp_workspace):
    cfg = ToolsConfig(workspace_root=temp_workspace)
    runner = ToolRunner(config=cfg)
    adapter = ReadFileTool(temp_workspace)
    spec = adapter.spec

    call = ToolCall(tool_name="read_file", params={"path": "hello.txt"})
    result = await runner.execute_call(call, spec, adapter)

    assert result.success is True
    assert result.data["total_lines"] == 3
    assert runner.health.get_health_metrics(["read_file"]).successful_calls == 1


@pytest.mark.asyncio
async def test_orchestrator_tools_integration():
    orchestrator = AssistantOrchestrator()
    initialized = await orchestrator.initialize()
    assert initialized is True

    # Test processing tool task through orchestrator
    result = await orchestrator.process_task(
        session_id="test_tool_session",
        task_type="tool_call",
        payload={"tool_name": "list_directory", "params": {"path": "."}},
    )

    assert result is not None
    assert result.success is True

    health = await orchestrator.health()
    assert "tool_platform_health" in health.details
    assert "read_file" in health.details["tool_platform_health"]["registered_tools"]

    await orchestrator.shutdown()


def test_bridge_imports_consistency():
    from jarvis.capabilities.tools import ToolsCapability as CapToolsCap
    from jarvis.capabilities import ToolsCapability as PkgToolsCap
    from jarvis.tools.capability import ToolsCapability as CoreToolsCap

    assert CapToolsCap is CoreToolsCap
    assert PkgToolsCap is CoreToolsCap
