"""
Abstract base protocols defining provider interfaces for hardware and cloud backends.
"""

import datetime
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional

from jarvis.core.base import BaseServiceProtocol


@dataclass
class AudioChunk:
    """Decoupled audio frame container passed between pipeline stages."""

    data: bytes
    sample_rate: int = 22050
    channels: int = 1
    sample_width: int = 2
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )


class AudioSessionProtocol(BaseServiceProtocol):
    """Protocol governing hardware microphone capture and speaker playback streams."""

    @abstractmethod
    async def start_listening(self) -> None:
        """Enable active microphone capture."""
        pass

    @abstractmethod
    async def stop_listening(self) -> None:
        """Disable active microphone capture."""
        pass

    @abstractmethod
    async def play_audio_chunk(self, chunk: AudioChunk) -> None:
        """Queue an audio chunk for speaker playback."""
        pass

    @abstractmethod
    async def stop_playback(self) -> None:
        """Immediately halt active speaker playback buffer on user interruption."""
        pass

    @abstractmethod
    async def wait_for_playback_complete(self, timeout_s: float = 10.0) -> None:
        """Block until speaker playback drains all queued audio chunks."""
        pass


class WakeWordProtocol(BaseServiceProtocol):
    """Protocol for wake word detection engines."""

    @abstractmethod
    async def detect(self, pcm_data: bytes) -> bool:
        """Evaluate a raw audio frame for wake word trigger match."""
        pass


class STTProtocol(BaseServiceProtocol):
    """Protocol for Speech-to-Text transcription engines."""

    @abstractmethod
    async def transcribe(self, pcm_data: bytes, sample_rate: int = 16000) -> str:
        """Transcribe raw PCM audio bytes to a text string."""
        pass


class LLMProtocol(BaseServiceProtocol):
    """Protocol for Language Model text generation backends."""

    @abstractmethod
    async def generate_stream(
        self, prompt: str, history: Optional[List[Dict[str, str]]] = None
    ) -> AsyncGenerator[str, None]:
        """Stream generated response tokens asynchronously."""
        yield ""


class TTSProtocol(BaseServiceProtocol):
    """Protocol for Text-to-Speech synthesis engines."""

    @abstractmethod
    async def synthesize_stream(self, text: str) -> AsyncGenerator[AudioChunk, None]:
        """Synthesize text into a stream of audio chunks."""
        yield AudioChunk(data=b"")


class StorageProtocol(BaseServiceProtocol):
    """Protocol for session state and turn persistence backends."""

    @abstractmethod
    async def create_session(self, session_id: str, title: str = "New Session") -> Dict[str, Any]:
        """Initialize a new session entry."""
        pass

    @abstractmethod
    async def save_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Persist a single user or assistant conversation turn."""
        pass

    @abstractmethod
    async def get_history(self, session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve recent conversation history for context assembly."""
        pass

