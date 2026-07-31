"""
Real SoundDevice AudioSessionManager for hardware microphone input and speaker output streams.
Single owner of mic & speaker audio hardware resources. Supports dynamic microphone device selection.
"""

import asyncio
import logging
from typing import List, Callable, Awaitable, Optional, Dict, Any
from vidya.core.base import ServiceStatus, HealthStatus
from vidya.providers.base import AudioSessionProtocol, AudioChunk
from vidya.utils.async_utils import BoundedQueue, safe_cancel_task

logger = logging.getLogger("vidya.providers.audio.sounddevice_session")

AudioSubscriber = Callable[[bytes], Awaitable[None]]


class SoundDeviceAudioSession(AudioSessionProtocol):
    """
    Hardware SoundDevice AudioSessionManager.
    Single owner of hardware mic and speaker streams with device selection support.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        speaker_sample_rate: int = 22050,
        channels: int = 1,
        chunk_size: int = 1024,
        device_index: Optional[int] = None
    ) -> None:
        self.sample_rate = sample_rate
        self.speaker_sample_rate = speaker_sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.device_index = device_index

        self._is_listening: bool = False
        self._is_playing: bool = False
        self._stop_requested: bool = False
        self._status: ServiceStatus = ServiceStatus.UNINITIALIZED
        self._subscribers: List[AudioSubscriber] = []
        self._playback_queue: BoundedQueue[AudioChunk] = BoundedQueue(maxsize=50)

        self._sd = None
        self._input_stream = None
        self._output_stream = None
        self._playback_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    def subscribe_mic(self, subscriber: AudioSubscriber) -> None:
        if subscriber not in self._subscribers:
            self._subscribers.append(subscriber)

    def unsubscribe_mic(self, subscriber: AudioSubscriber) -> None:
        if subscriber in self._subscribers:
            self._subscribers.remove(subscriber)

    def list_input_devices(self) -> List[Dict[str, Any]]:
        """List all available microphone input devices on system."""
        if not self._sd:
            return []
        try:
            devices = self._sd.query_devices()
            input_devices = []
            for idx, dev in enumerate(devices):
                if dev.get("max_input_channels", 0) > 0:
                    input_devices.append({
                        "index": idx,
                        "name": dev.get("name"),
                        "channels": dev.get("max_input_channels"),
                        "default_sample_rate": int(dev.get("default_samplerate", 16000))
                    })
            return input_devices
        except Exception as e:
            logger.error(f"Error querying audio devices: {e}")
            return []

    async def set_input_device(self, device_index: int) -> bool:
        """Switch active microphone device by index."""
        was_listening = self._is_listening
        if was_listening:
            await self.stop_listening()

        self.device_index = device_index
        logger.info(f"Selected microphone device index: {device_index}")

        if was_listening:
            await self.start_listening()
        return True

    async def initialize(self) -> bool:
        self._loop = asyncio.get_running_loop()
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

    def _mic_callback(self, indata, frames, time_info, status):
        """Callback invoked by sounddevice C thread for every microphone PCM audio block."""
        if status:
            logger.debug(f"Sounddevice input status: {status}")
        if self._is_listening and self._status == ServiceStatus.RUNNING and indata is not None and self._loop and self._loop.is_running():
            pcm_bytes = bytes(indata)
            for sub in self._subscribers:
                try:
                    coro = sub(pcm_bytes)
                    if asyncio.iscoroutine(coro):
                        if self._loop and self._loop.is_running():
                            try:
                                asyncio.run_coroutine_threadsafe(coro, self._loop)
                            except Exception:
                                coro.close()
                        else:
                            coro.close()
                except Exception:
                    pass

    async def start_listening(self) -> None:
        if self._is_listening:
            return
        if not self._sd:
            logger.warning("Sounddevice not available for mic recording.")
            return

        try:
            self._input_stream = self._sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=self.chunk_size,
                device=self.device_index,
                channels=self.channels,
                dtype="int16",
                callback=self._mic_callback
            )
            self._input_stream.start()
            self._is_listening = True
            dev_name = self.device_index if self.device_index is not None else "default"
            logger.info(f"Hardware microphone stream started (device: {dev_name}, {self.sample_rate}Hz).")
        except Exception as e:
            logger.error(f"Error starting hardware microphone stream: {e}")
            self._is_listening = False

    async def stop_listening(self) -> None:
        if self._input_stream:
            try:
                self._input_stream.stop()
                self._input_stream.close()
            except Exception as e:
                logger.error(f"Error closing input stream: {e}")
            self._input_stream = None
        self._is_listening = False
        logger.info("Hardware microphone stream disabled.")

    async def play_audio_chunk(self, chunk: AudioChunk) -> None:
        """Queue AudioChunk for speaker playback (unless playback stopped)."""
        if self._stop_requested:
            return
        await self._playback_queue.put(chunk)

    async def stop_playback(self) -> None:
        """Instantly flush playback queue on barge-in interrupt."""
        self._stop_requested = True
        cleared = self._playback_queue.clear()
        self._is_playing = False
        if self._output_stream:
            try:
                self._output_stream.abort()
                self._output_stream.close()
            except Exception as e:
                logger.error(f"Error aborting output stream: {e}")
            self._output_stream = None
        logger.info(f"Barge-in interrupt: cleared {cleared} queued audio chunks from speaker.")

    async def wait_for_playback_complete(self, timeout_s: float = 10.0) -> None:
        """Wait until speaker playback queue is empty and active playback completes."""
        t0 = asyncio.get_running_loop().time()
        while (not self._playback_queue.empty() or self._is_playing) and not self._stop_requested:
            if asyncio.get_running_loop().time() - t0 > timeout_s:
                logger.warning("wait_for_playback_complete timed out.")
                break
            await asyncio.sleep(0.03)

    def reset_stop_flag(self) -> None:
        """Reset stop requested flag before starting new playback stream."""
        self._stop_requested = False

    async def _playback_loop(self) -> None:
        """Background loop reading from playback queue and outputting to speaker."""
        loop = asyncio.get_running_loop()
        current_sr = None

        while self._status in (ServiceStatus.RUNNING, ServiceStatus.DEGRADED):
            if self._stop_requested:
                self._playback_queue.clear()
                self._is_playing = False
                await asyncio.sleep(0.02)
                continue

            chunk = await self._playback_queue.get(timeout=0.1)
            if chunk and chunk.data and not self._stop_requested:
                self._is_playing = True
                try:
                    if self._sd:
                        import numpy as np
                        audio_np = np.frombuffer(chunk.data, dtype=np.int16)
                        sr = chunk.sample_rate or self.speaker_sample_rate

                        if self._output_stream is None or current_sr != sr:
                            if self._output_stream:
                                try:
                                    self._output_stream.stop()
                                    self._output_stream.close()
                                except Exception:
                                    pass
                            self._output_stream = self._sd.OutputStream(
                                samplerate=sr,
                                channels=self.channels,
                                dtype="int16"
                            )
                            self._output_stream.start()
                            current_sr = sr

                        def _write_pcm():
                            if not self._stop_requested and self._output_stream and self._output_stream.active:
                                try:
                                    self._output_stream.write(audio_np)
                                except Exception:
                                    pass

                        await loop.run_in_executor(None, _write_pcm)
                    else:
                        duration = len(chunk.data) / (2 * (chunk.sample_rate or self.speaker_sample_rate))
                        await asyncio.sleep(duration)
                except Exception as e:
                    logger.error(f"Error playing audio chunk: {e}")
            else:
                if self._playback_queue.empty():
                    self._is_playing = False

        if self._output_stream:
            try:
                self._output_stream.stop()
                self._output_stream.close()
            except Exception:
                pass
            self._output_stream = None

    async def health(self) -> HealthStatus:
        return HealthStatus(
            status=self._status,
            message="SoundDevice session status",
            details={
                "listening": self._is_listening,
                "playing": self._is_playing,
                "device_index": self.device_index,
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

