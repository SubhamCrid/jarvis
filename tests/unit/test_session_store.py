"""
Unit tests for SQLiteSessionStore.
"""

import pytest
import tempfile
from pathlib import Path
from jarvis.providers.storage.session_store import SQLiteSessionStore


@pytest.mark.asyncio
async def test_session_store_lifecycle():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_jarvis.db"
        store = SQLiteSessionStore(db_path=str(db_path))

        assert await store.initialize()

        # Create session
        sess = await store.create_session("sess-001", "Test Conversation")
        assert sess["session_id"] == "sess-001"

        # Save turns
        turn1 = await store.save_turn("sess-001", "user", "Hello Jarvis")
        turn2 = await store.save_turn("sess-001", "assistant", "Hello! How can I help?")

        assert turn1["turn_id"] == 1
        assert turn2["turn_id"] == 2

        # Fetch history
        history = await store.get_history("sess-001", limit=10)
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello Jarvis"
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "Hello! How can I help?"

        await store.shutdown()
