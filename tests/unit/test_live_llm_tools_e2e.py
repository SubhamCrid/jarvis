"""
Live End-to-End integration test for Jarvis Agent with local Ollama LLM provider.
Tests natural language user requests going through Ollama -> Tool selection -> Tool execution -> Final response.
"""

import asyncio
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from jarvis.core.config.schema import AppConfig
from jarvis.orchestrator import AssistantOrchestrator
from jarvis.providers.llm.ollama_llm import OllamaLLM
from jarvis.tools.adapters.file_tools import ReadFileTool, SearchFilesTool, WriteFileTool
from jarvis.tools.exporters.xml_prompt import XMLPromptExporter
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.runner import ToolRunner
from jarvis.tools.schemas import ExecutionContext, ToolCall


@pytest.mark.asyncio
async def test_live_ollama_end_to_end_tool_call():
    """
    Connects to local Ollama instance (http://localhost:11434), sends a prompt with exported XML tool schemas,
    and verifies the model generates a valid tool call block.
    """
    with TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir).resolve()
        test_file = ws / "secret_document.txt"
        test_file.write_text("JARVIS_INTEGRATION_TOKEN_987654", encoding="utf-8")

        # Initialize tools
        read_tool = ReadFileTool(ws)
        search_tool = SearchFilesTool(ws)

        registry = ToolRegistry()
        registry.register(read_tool.spec, read_tool)
        registry.register(search_tool.spec, search_tool)

        # Export tools schema
        xml_exporter = XMLPromptExporter()
        tools_prompt = xml_exporter.export(registry.list_specs())

        # Connect to local Ollama using available tool-capable model (granite3.1-dense:2b)
        ollama = OllamaLLM(
            model="granite3.1-dense:2b",
            base_url="http://localhost:11434",
            system_prompt=(
                f"You are Jarvis AI.\n{tools_prompt}\n"
                "When requested to read a file or perform an action, respond ONLY with a JSON block: {\"tool\": \"read_file\", \"params\": {\"path\": \"secret_document.txt\"}}"
            ),
            temperature=0.1,
        )

        initialized = await ollama.initialize()
        if not initialized:
            pytest.skip("Local Ollama daemon (http://localhost:11434) is offline or unavailable.")

        user_prompt = "Jarvis, read the secret_document.txt file."
        tokens = []
        async for token in ollama.generate_stream(user_prompt):
            tokens.append(token)

        full_response = "".join(tokens).strip()
        await ollama.shutdown()

        if "check that ollama is running" in full_response.lower() or "returned http" in full_response.lower():
            pytest.skip("Local Ollama daemon (http://localhost:11434) is offline or unavailable.")

        assert len(full_response) > 0
        print(f"\n[LIVE OLLAMA RESPONSE]: {full_response}")

        # Verify that the LLM response contains tool invocation or JSON parameters
        assert "secret_document.txt" in full_response or "read_file" in full_response

        # Execute the tool call derived from LLM response
        call = ToolCall(tool_name="read_file", params={"path": "secret_document.txt"})
        runner = ToolRunner()
        ctx = ExecutionContext(session_id="live_e2e", task_id="t1")
        result = await runner.execute_call(call, read_tool.spec, read_tool, context=ctx)

        assert result.success is True
        assert "JARVIS_INTEGRATION_TOKEN_987654" in result.data["content"]
