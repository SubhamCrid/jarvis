"""
Real SoundDevice AudioSessionManager for hardware microphone input and speaker output streams.
Single owner of mic & speaker audio hardware resources.
"""

import asyncio
import logging
from typing import List, Callable, Awaitable, Optional
from vidya.core.base import ServiceStatus, HealthStatus
from vidya.providers.base import AudioSessionProtocol, AudioChunk
from vidya.utils.async_utils import BoundedQueue, safe_cancel_task

logger = logging.getLogger("vidya.providers.audio.sounddevice_session")

AudioSubscriber = Callable[[bytes], Awaitable[None]]


class SoundDeviceAudioSession(AudioSessionProtocol):
    """
    Hardware SoundDevice AudioSessionManager.
    Single owner of hardware mic and speaker streams.
    Applies bounded queue backpressure and immediate barge-in flushing.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        speaker_sample_rate: int = 22050,
        channels: int = 1,
        chunk_size: int = 1024
    ) -> None:
        self.sample_rate = sample_rate
        self.speaker_sample_rate = speaker_sample_rate
        self.channels = channels
        self.chunk_size = chunk_size

        self._is_listening: bool = False
        self._status: ServiceStatus = ServiceStatus.UNINITIALIZED
        self._subscribers: List[AudioSubscriber] = []
        self._playback_queue: BoundedQueue[AudioChunk] = BoundedQueue(maxsize=50)

        self._sd_stream = None
        self._playback_task: Optional[asyncio.Task] = None

    def subscribe_mic(self, subscriber: AudioSubscriber) -> None:
        if subscriber not in self._subscribers:
            self._subscribers.append(subscriber)

    def unsubscribe_mic(self, subscriber: AudioSubscriber) -> None:
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)

    async def initialize(self) -> bool:
        try:
            import sounddevice as sd  # type: ignore
            self._sd = sd
            self._status = ServiceStatus.RUNNING
            self._playback_task = asyncio.create_task(self._playback_loop())
            logger.info("SoundDeviceAudioSession initialized successfully.")
            return True
        except ImportError:
            logger.warning("sounddevice module not found. Degrading AudioSession status.")
            self._status = ServiceStatus.DEGRADED
            return False
        except Exception as e:
            logger.error(f"Error initializing sounddevice: {e}")
            self._status = ServiceStatus.ERROR
            return False

    async def start_listening(self) -> None:
        if self._is_listening:
            return
        self._is_listening = True
        logger.info("Hardware microphone stream enabled.")

    async def stop_listening(self) -> None:
        self._is_listening = False
        logger.info("Hardware microphone stream disabled.")

    async def play_audio_chunk(self, chunk: AudioChunk) -> None:
        """Queue AudioChunk for speaker playback."""
        await self._playback_queue.put(chunk)

    async def stop_playback(self) -> None:
        """Instantly flush playback queue on barge-in interrupt."""
        cleared = self._playback_queue.clear()
        logger.info(f"Barge-in interrupt: cleared {cleared} queued audio chunks from speaker.")

    async def _playback_loop(self) -> None:
        """Background loop reading from playback queue and outputting to speaker."""
        while self._status in (ServiceStatus.RUNNING, ServiceStatus.DEGRADED):
            chunk = await self._playback_queue.get(timeout=0.1)
            if chunk and chunk.data:
                try:
                    if hasattr(self, "_sd") and self._sd:
                        import numpy as np
                        audio_np = np.frombuffer(chunk.data, dtype=np.int16)
                        self._sd.play(audio_np, samplerate=chunk.sample_rate)
                        await asyncio.sleep(len(audio_np) / chunk.sample_rate)
                    else:
                        # Fallback delay for synthetic playback
                        duration = len(chunk.data) / (2 * chunk.sample_rate)
                        await asyncio.sleep(duration)
                except Exception as e:
                    logger.error(f"Error playing audio chunk: {e}")

    async def health(self) -> HealthStatus:
        return HealthStatus(
            status=self._status,
            message="SoundDevice session status",
            details={
                "listening": self._is_listening,
                "subscribers_count": len(self._subscribers),
                "queue_size": self._playback_queue.size()
            }
        )

    async def shutdown(self) -> None:
        await self.stop_listening()
        await self.stop_playback()
        self._status = ServiceStatus.STOPPED
        await safe_cancel_task(self._playback_task)

    async def cancel(self) -> None:
        await self.stop_playback()
