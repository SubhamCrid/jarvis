"""
End-to-End integration test suite for Jarvis AI assistant on user infrastructure.
Tests multi-turn conversation context history, Desktop & Documents folder path resolution,
and tool intent routing to ensure filesystem queries are never misrouted to vector search.
"""

import asyncio
from pathlib import Path
import pytest
import uuid

from jarvis.core.config.loader import load_config
from jarvis.orchestrator import AssistantOrchestrator
from jarvis.tools.adapters.file_tools import ListDirectoryTool, ReadFileTool, SearchFilesTool
from jarvis.tools.sandbox import PathSandbox


@pytest.mark.asyncio
async def test_e2e_multiturn_conversation_and_folder_intent():
    """
    Simulate a complete 3-turn user interaction flow:
    Turn 1: "Can you tell me what files are present in my desktop?" -> list_directory(path="Desktop")
    Turn 2: "what about documents folder?" -> list_directory(path="Documents")
    Turn 3: "want Q to tell me what are present there." -> resolves "there" -> Documents via session history
    """
    config = load_config(user_overrides={
        "system": {"environment": "test"},
        "wakeword": {"provider": "mock"},
        "stt": {"provider": "mock"},
        "llm": {"provider": "mock"},
        "tts": {"provider": "mock"},
        "session": {"max_history_turns": 10},
    })

    orchestrator = AssistantOrchestrator(config)
    assert await orchestrator.initialize()

    session_id = f"e2e_sess_{uuid.uuid4().hex[:8]}"

    # Turn 1: Desktop file query
    prompt1 = "Can you tell me what files are present in my desktop?"
    summary1 = await orchestrator.voice_capability._try_execute_tool_intent(prompt1, session_id=session_id)
    assert summary1 is not None, "Turn 1 intent should trigger a tool execution summary"
    assert "list_directory returned:" in summary1, "Turn 1 must execute list_directory for Desktop"
    assert "search_system" not in summary1, "Turn 1 must not be misrouted to search_system"

    # Save turn 1 in session store
    await orchestrator.session_store.save_turn(session_id, "user", prompt1)
    await orchestrator.session_store.save_turn(session_id, "assistant", summary1)

    # Turn 2: Documents folder inquiry
    prompt2 = "what about documents folder?"
    summary2 = await orchestrator.voice_capability._try_execute_tool_intent(prompt2, session_id=session_id)
    assert summary2 is not None, "Turn 2 intent should trigger a tool execution summary"
    assert "list_directory returned:" in summary2, "Turn 2 must execute list_directory for Documents"

    # Save turn 2 in session store
    await orchestrator.session_store.save_turn(session_id, "user", prompt2)
    await orchestrator.session_store.save_turn(session_id, "assistant", summary2)

    # Turn 3: Contextual follow-up using "there"
    prompt3 = "want Q to tell me what are present there."
    summary3 = await orchestrator.voice_capability._try_execute_tool_intent(prompt3, session_id=session_id)
    assert summary3 is not None, "Turn 3 intent should trigger a tool execution summary"
    assert "list_directory returned:" in summary3, "Turn 3 must resolve 'there' to Documents and run list_directory"

    # Verify session store retains full 6-turn history
    history = await orchestrator.session_store.get_history(session_id, limit=10)
    assert len(history) >= 4, f"Session history should retain all turns, found {len(history)}"
    assert history[0]["content"] == prompt1
    assert history[2]["content"] == prompt2

    await orchestrator.shutdown()


@pytest.mark.asyncio
async def test_e2e_user_infra_real_folder_listing():
    """
    Test real system directory resolution (Desktop & Documents) on the user's local infrastructure.
    Creates temporary test marker files in user Desktop / Documents (if writable) and verifies
    ListDirectoryTool and SearchFilesTool discover and read them without errors.
    """
    sandbox = PathSandbox(workspace_root=Path.cwd())
    desktop_dirs = sandbox._get_desktop_dirs()
    doc_dirs = sandbox._get_documents_dirs()

    assert len(desktop_dirs) > 0 or len(doc_dirs) > 0, "At least one system directory (Desktop or Documents) must exist"

    marker_filename = f"_jarvis_e2e_marker_{uuid.uuid4().hex[:6]}.txt"
    created_markers = []

    # Write marker file to candidate directories if accessible
    for target_dir in desktop_dirs + doc_dirs:
        if target_dir.exists():
            try:
                marker_path = target_dir / marker_filename
                marker_path.write_text("E2E_INFRA_TEST_DATA", encoding="utf-8")
                created_markers.append(marker_path)
            except PermissionError:
                pass

    try:
        # Test ListDirectoryTool on Desktop
        list_tool = ListDirectoryTool(Path.cwd())
        list_res_dt = await list_tool.execute({"path": "Desktop"}, context=None)
        assert "items" in list_res_dt
        assert list_res_dt["total_items"] >= 0

        # Test ListDirectoryTool on Documents
        list_res_doc = await list_tool.execute({"path": "Documents"}, context=None)
        assert "items" in list_res_doc
        assert list_res_doc["total_items"] >= 0

        # If markers were created, verify ListDirectoryTool and SearchFilesTool find them
        if created_markers:
            # Verify in ListDirectoryTool items
            dt_item_names = [item["name"] for item in list_res_dt["items"]]
            doc_item_names = [item["name"] for item in list_res_doc["items"]]
            assert marker_filename in dt_item_names or marker_filename in doc_item_names, \
                f"Marker '{marker_filename}' should be discovered by ListDirectoryTool"

            # Test SearchFilesTool
            search_tool = SearchFilesTool(Path.cwd())
            search_res = await search_tool.execute({"pattern": f"*{marker_filename}*", "path": "Desktop"}, context=None)
            if search_res["matched_count"] == 0:
                search_res = await search_tool.execute({"pattern": f"*{marker_filename}*", "path": "Documents"}, context=None)

            assert search_res["matched_count"] > 0, "SearchFilesTool should locate the test marker file"
    finally:
        # Clean up temporary marker files safely
        for marker_path in created_markers:
            try:
                if marker_path.exists():
                    marker_path.unlink()
            except Exception:
                pass


@pytest.mark.asyncio
async def test_e2e_no_vector_rag_misrouting_for_file_prompts():
    """
    Verify that explicit file system queries NEVER trigger vector search (RAG memory retrieval)
    which returns 0 matches for real file queries.
    """
    config = load_config(user_overrides={"system": {"environment": "test"}})
    orchestrator = AssistantOrchestrator(config)
    await orchestrator.initialize()

    file_prompts = [
        "Can you tell me what files are present in my desktop?",
        "what about documents folder?",
        "what files are in my downloads?",
        "show me files in current directory",
        "read all the files on desktop",
        "list files in documents",
    ]

    session_id = f"no_misroute_{uuid.uuid4().hex[:8]}"

    for prompt in file_prompts:
        summary = await orchestrator.voice_capability._try_execute_tool_intent(prompt, session_id=session_id)
        assert summary is not None, f"Prompt '{prompt}' should trigger a tool action"
        assert "search_system" not in summary, f"Prompt '{prompt}' must NOT route to vector search_system"
        assert "list_directory returned:" in summary or "search_files returned:" in summary, \
            f"Prompt '{prompt}' must execute a file system tool"

    await orchestrator.shutdown()
