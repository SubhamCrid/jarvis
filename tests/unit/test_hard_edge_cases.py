"""
Hard edge case and stress tests for Jarvis tool execution platform.
Includes needle-in-a-haystack random file discovery and buffer overflow / output capping stress tests.
"""

import uuid
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from jarvis.search.adapter import SearchToolAdapter
from jarvis.search.config import SearchConfig
from jarvis.search.pipeline import SearchPipelineEngine
from jarvis.tools.adapters.file_tools import (
    ReadFileTool,
    SearchFilesTool,
    WriteFileTool,
)
from jarvis.tools.adapters.shell_tools import RunCommandSafeTool
from jarvis.tools.config import ToolsConfig
from jarvis.tools.runner import ToolRunner
from jarvis.tools.schemas import ExecutionContext, ToolCall


@pytest.fixture
def complex_workspace():
    with TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir).resolve()

        # Create nested directory tree up to 5 levels deep
        cur = ws
        for i in range(5):
            cur = cur / f"level_{i}"
            cur.mkdir(parents=True, exist_ok=True)
            for j in range(10):
                (cur / f"file_{j}.py").write_text(f"# Python source file level {i} index {j}\n", encoding="utf-8")
                (cur / f"doc_{j}.txt").write_text(f"Text document level {i} index {j}\n", encoding="utf-8")

        yield ws


# ==========================================
# 1. NEEDLE-IN-A-HAYSTACK RANDOM FILE DISCOVERY
# ==========================================

@pytest.mark.asyncio
async def test_needle_in_a_haystack_discovery(complex_workspace):
    # Secret needle token
    needle_uuid = f"NEEDLE_SECRET_TOKEN_{uuid.uuid4().hex}"
    needle_rel_path = "level_0/level_1/level_2/level_3/level_4/hidden_needle.secret"
    needle_abs_path = complex_workspace / needle_rel_path
    needle_abs_path.write_text(f"KEY_DATA: {needle_uuid}\nCLASSIFIED=TRUE\n", encoding="utf-8")

    search_tool = SearchFilesTool(complex_workspace)
    read_tool = ReadFileTool(complex_workspace)
    ctx = ExecutionContext(session_id="needle_test", task_id="t_needle")

    # Step 1: Find file via recursive glob pattern search
    res_search = await search_tool.execute({"pattern": "**/*.secret"}, ctx)
    assert res_search["matched_count"] >= 1
    found_matches = res_search["matches"]
    assert any("hidden_needle.secret" in m for m in found_matches)

    target_match = [m for m in found_matches if "hidden_needle.secret" in m][0]

    # Step 2: Read needle file content and extract UUID
    res_read = await read_tool.execute({"path": target_match}, ctx)
    assert needle_uuid in res_read["content"]


@pytest.mark.asyncio
async def test_search_system_adapter_needle_discovery(complex_workspace):
    needle_uuid = f"SEARCH_DSL_NEEDLE_{uuid.uuid4().hex}"
    target_file = complex_workspace / "level_0" / "level_1" / "dsl_target.py"
    target_file.write_text(f"# Search DSL Target File\n# TOKEN={needle_uuid}\n", encoding="utf-8")

    search_cfg = SearchConfig(search_root=complex_workspace)
    search_engine = SearchPipelineEngine(config=search_cfg)
    adapter = SearchToolAdapter(search_engine)
    ctx = ExecutionContext(session_id="dsl_test", task_id="t_dsl")

    # Search via DSL query
    res = await adapter.execute({"query": "dsl_target.py"}, ctx)
    assert res is not None
    assert "matches" in res or "resources" in res


# ==========================================
# 2. BUFFER OVERFLOW & STRESS CAPPING TESTS
# ==========================================

@pytest.mark.asyncio
async def test_large_file_read_line_slicing(complex_workspace):
    large_file = complex_workspace / "huge_file.log"
    lines = [f"Log line number {i}" for i in range(5000)]
    large_file.write_text("\n".join(lines), encoding="utf-8")

    read_tool = ReadFileTool(complex_workspace)
    ctx = ExecutionContext(session_id="large_file_test", task_id="t_large")

    # Read line slice (lines 100 to 150)
    res = await read_tool.execute({"path": "huge_file.log", "start_line": 100, "end_line": 150}, ctx)
    assert res["total_lines"] == 5000
    read_lines = res["content"].splitlines()
    assert len(read_lines) == 51
    assert read_lines[0] == "Log line number 99"
    assert read_lines[-1] == "Log line number 149"


@pytest.mark.asyncio
async def test_run_command_safe_stdout_capping(complex_workspace):
    shell_tool = RunCommandSafeTool(complex_workspace)
    ctx = ExecutionContext(session_id="cap_test", task_id="t_cap")

    # Command generating huge output via python
    huge_stdout_cmd = ["python", "-c", "print('X' * 100000)"]
    res = await shell_tool.execute({"argv": huge_stdout_cmd}, ctx)
    assert res["success"] is True
    # Verify stdout buffer capping (capped at 65536 bytes)
    assert len(res["stdout"]) <= 65536
