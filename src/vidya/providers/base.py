"""
Unified Provider Protocols for STT, LLM, TTS, WakeWord, AudioSession, and Storage.
All providers inherit from BaseServiceProtocol (initialize, health, shutdown, cancel).
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional, Dict, Any, List
from dataclasses import dataclass, field
import datetime
from vidya.core.base import BaseServiceProtocol


@dataclass
class AudioChunk:
    """Standard decoupled audio chunk passed from TTS to Speaker or from Mic to Subscribers."""
    data: bytes
    sample_rate: int = 22050
    channels: int = 1
    sample_width: int = 2  # 16-bit PCM
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())


class AudioSessionProtocol(BaseServiceProtocol):
    """Exclusive owner of Microphone input and Speaker output streams."""

    @abstractmethod
    async def start_listening(self) -> None:
        """Enable microphone capture stream."""
        pass

    @abstractmethod
    async def stop_listening(self) -> None:
        """Disable microphone capture stream."""
        pass

    @abstractmethod
    async def play_audio_chunk(self, chunk: AudioChunk) -> None:
        """Queue AudioChunk for speaker playback."""
        pass

    @abstractmethod
    async def stop_playback(self) -> None:
        """Instantly halt active speaker playback buffer on barge-in."""
        pass


class WakeWordProtocol(BaseServiceProtocol):
    """Wake Word Detector engine protocol."""

    @abstractmethod
    async def detect(self, pcm_data: bytes) -> bool:
        """Process PCM audio frame and return True if wake word is detected."""
        pass


class STTProtocol(BaseServiceProtocol):
    """Speech-to-Text provider protocol."""

    @abstractmethod
    async def transcribe(self, pcm_data: bytes, sample_rate: int = 16000) -> str:
        """Transcribe raw PCM audio bytes to text string."""
        pass


class LLMProtocol(BaseServiceProtocol):
    """Language Model provider protocol."""

    @abstractmethod
    async def generate_stream(self, prompt: str, history: Optional[List[Dict[str, str]]] = None) -> AsyncGenerator[str, None]:
        """Stream generated text tokens asynchronously."""
        yield ""


class TTSProtocol(BaseServiceProtocol):
    """Text-to-Speech provider yielding AudioChunk streams."""

    @abstractmethod
    async def synthesize_stream(self, text: str) -> AsyncGenerator[AudioChunk, None]:
        """Synthesize text into a stream of AudioChunk objects."""
        yield AudioChunk(data=b"")


class StorageProtocol(BaseServiceProtocol):
    """SessionStore database & file persistence protocol."""

    @abstractmethod
    async def create_session(self, session_id: str, title: str = "New Session") -> Dict[str, Any]:
        pass

    @abstractmethod
    async def save_turn(self, session_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def get_history(self, session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        pass
