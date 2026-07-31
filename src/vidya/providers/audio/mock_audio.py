"""
MockAudioSession for synthetic audio input/output testing without physical hardware.
"""

import asyncio
import logging
from typing import List, Callable, Awaitable, Optional
from vidya.core.base import ServiceStatus, HealthStatus
from vidya.providers.base import AudioSessionProtocol, AudioChunk
from vidya.utils.async_utils import BoundedQueue

logger = logging.getLogger("vidya.providers.audio.mock_audio")

AudioSubscriber = Callable[[bytes], Awaitable[None]]


class MockAudioSession(AudioSessionProtocol):
    """
    Synthetic AudioSession implementation for CI/CD and non-hardware environments.
    """

    def __init__(self, sample_rate: int = 16000) -> None:
        self.sample_rate = sample_rate
        self._is_listening: bool = False
        self._status: ServiceStatus = ServiceStatus.UNINITIALIZED
        self._played_chunks: List[AudioChunk] = []
        self._subscribers: List[AudioSubscriber] = []
        self._playback_queue: BoundedQueue[AudioChunk] = BoundedQueue(maxsize=100)
        self._generator_task: Optional[asyncio.Task] = None

    def subscribe_mic(self, subscriber: AudioSubscriber) -> None:
        if subscriber not in self._subscribers:
            self._subscribers.append(subscriber)

    def unsubscribe_mic(self, subscriber: AudioSubscriber) -> None:
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)

    async def start_listening(self) -> None:
        self._is_listening = True
        logger.info("MockAudioSession listening started.")

    async def stop_listening(self) -> None:
        self._is_listening = False
        logger.info("MockAudioSession listening stopped.")

    async def play_audio_chunk(self, chunk: AudioChunk) -> None:
        self._played_chunks.append(chunk)
        await self._playback_queue.put(chunk)
        logger.debug(f"MockAudioSession played chunk: {len(chunk.data)} bytes")

    async def stop_playback(self) -> None:
        cleared = self._playback_queue.clear()
        logger.info(f"MockAudioSession stopped playback (cleared {cleared} chunks).")

    async def wait_for_playback_complete(self, timeout_s: float = 10.0) -> None:
        self._playback_queue.clear()

    async def simulate_mic_input(self, pcm_data: bytes) -> None:
        """Simulate mic audio input frame pushing to subscribers."""
        if self._is_listening:
            for sub in self._subscribers:
                await sub(pcm_data)

    def get_played_chunks(self) -> List[AudioChunk]:
        return self._played_chunks.copy()

    def clear_played_chunks(self) -> None:
        self._played_chunks.clear()

    async def initialize(self) -> bool:
        self._status = ServiceStatus.RUNNING
        return True

    async def health(self) -> HealthStatus:
        return HealthStatus(
            status=self._status,
            message="Mock audio session active",
            details={
                "listening": self._is_listening,
                "played_count": len(self._played_chunks)
            }
        )

    async def shutdown(self) -> None:
        await self.stop_listening()
        await self.stop_playback()
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        await self.stop_playback()
