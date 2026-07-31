"""
Voice Activity Detection (VAD) Engine with energy thresholding and endpoint detection.
"""

import math
import struct
import logging
from typing import Dict, Any

logger = logging.getLogger("jarvis.providers.audio.vad")


class VADEngine:
    """
    Energy & RMS-based VAD engine with adaptive noise floor estimation for real-time
    speech boundary and endpoint detection.
    """

    def __init__(
        self,
        energy_threshold: float = 0.008,
        silence_duration_ms: int = 1800,
        sample_rate: int = 16000,
        chunk_size: int = 1024,
    ) -> None:
        self.energy_threshold = energy_threshold
        self.silence_duration_ms = silence_duration_ms
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size

        self._in_speech: bool = False
        self._silence_start_time_ms: float = 0.0
        self._accumulated_silence_ms: float = 0.0
        self._noise_floor: float = energy_threshold * 0.5

    def calculate_rms(self, pcm_bytes: bytes) -> float:
        """Calculate Root Mean Square (RMS) energy of 16-bit PCM audio bytes."""
        if not pcm_bytes:
            return 0.0
        count = len(pcm_bytes) // 2
        if count == 0:
            return 0.0

        shorts = struct.unpack(f"<{count}h", pcm_bytes)
        sum_squares = sum((sample / 32768.0) ** 2 for sample in shorts)
        return math.sqrt(sum_squares / count)

    def process_chunk(self, pcm_bytes: bytes) -> Dict[str, Any]:
        """
        Process a PCM audio chunk and evaluate speech activity.
        Returns dict with is_speech, speech_ended, and rms.
        """
        rms = self.calculate_rms(pcm_bytes)
        chunk_duration_ms = (len(pcm_bytes) / (2 * self.sample_rate)) * 1000.0

        # Adaptively update background noise floor during silence
        if not self._in_speech and rms < self.energy_threshold * 2.0:
            self._noise_floor = 0.95 * self._noise_floor + 0.05 * rms

        effective_threshold = max(self.energy_threshold, self._noise_floor * 2.0)
        is_speech = rms >= effective_threshold
        speech_ended = False

        if is_speech:
            self._in_speech = True
            self._accumulated_silence_ms = 0.0
        else:
            if self._in_speech:
                self._accumulated_silence_ms += chunk_duration_ms
                if self._accumulated_silence_ms >= self.silence_duration_ms:
                    speech_ended = True
                    self._in_speech = False
                    self._accumulated_silence_ms = 0.0

        return {
            "is_speech": is_speech,
            "in_speech_session": self._in_speech,
            "speech_ended": speech_ended,
            "silence_ms": self._accumulated_silence_ms,
            "rms": rms,
            "effective_threshold": effective_threshold,
        }

    def reset(self) -> None:
        self._in_speech = False
        self._accumulated_silence_ms = 0.0

