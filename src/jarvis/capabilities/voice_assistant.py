"""
Voice assistant capability orchestrating finite state machine voice interaction,
speech-to-text, streaming language model inference, text-to-speech synthesis,
barge-in interruption detection, and event broadcasting.
"""

import asyncio
import logging
import re
import time
from typing import Any, Dict, List, Optional

from vidya.capabilities.base import BaseCapability, PermissionEnum
from vidya.core.base import HealthStatus, ServiceStatus
from vidya.core.bus import (
    AudioChunkReady,
    ErrorOccurred,
    MessageBus,
    PlaybackFinished,
    SentenceReady,
    SpeechEnded,
    SpeechStarted,
    TaskCancelled,
    TokenGenerated,
    TranscriptReady,
    WakeDetected,
)
from vidya.core.fsm import FSMState, VoiceFSM
from vidya.core.observability import ObservabilityService
from vidya.providers.audio.vad import VADEngine
from vidya.providers.base import (
    AudioSessionProtocol,
    LLMProtocol,
    STTProtocol,
    StorageProtocol,
    TTSProtocol,
    WakeWordProtocol,
)
from vidya.providers.chunker import SentenceChunker
from vidya.utils.async_utils import BoundedQueue, safe_cancel_task

logger = logging.getLogger("vidya.capabilities.voice_assistant")

_WAKE_PREFIX_PATTERN = re.compile(
    r"^(?:hey\s+jarvis|jarvis|hello\s+jarvis|hey\s+vidya|vidya|hello\s+vidya)[\s,.:;!?]*",
    re.IGNORECASE,
)


def _strip_wake_word_prefixes(text: str) -> str:
    """Remove leading wake-word salutations from the input transcript."""
    if not text:
        return ""
    clean = text.strip()
    return _WAKE_PREFIX_PATTERN.sub("", clean).lstrip(" ,.:;!?")


class VoiceAssistantCapability(BaseCapability):
    """
    Primary voice processing capability managing speech capture, transcription,
    model streaming, audio synthesis, and real-time user interruption (barge-in).
    """

    name = "voice_assistant"
    required_permissions = [PermissionEnum.AUDIO, PermissionEnum.INTERNET]

    def __init__(
        self,
        fsm: VoiceFSM,
        bus: MessageBus,
        audio_session: AudioSessionProtocol,
        wakeword: WakeWordProtocol,
        stt: STTProtocol,
        llm: LLMProtocol,
        tts: TTSProtocol,
        session_store: StorageProtocol,
        observability: ObservabilityService,
        vad_threshold: float = 0.02,
        silence_duration_ms: int = 1800,
        followup_timeout_s: float = 6.0,
        max_history_turns: int = 0,
    ) -> None:
        self.fsm = fsm
        self.bus = bus
        self.audio_session = audio_session
        self.wakeword = wakeword
        self.stt = stt
        self.llm = llm
        self.tts = tts
        self.session_store = session_store
        self.observability = observability
        self.followup_timeout_s = followup_timeout_s
        self.max_history_turns = max_history_turns

        self.vad = VADEngine(energy_threshold=vad_threshold, silence_duration_ms=silence_duration_ms)
        self.chunker = SentenceChunker()
        self._status = ServiceStatus.UNINITIALIZED

        self._audio_buffer: bytearray = bytearray()
        self._token_queue: BoundedQueue[str] = BoundedQueue(maxsize=100)
        self._active_task: Optional[asyncio.Task] = None
        self._is_cancelled: bool = False
        self._speaking_start_time: float = 0.0
        self._listening_start_time: float = 0.0
        self._consecutive_speech_count: int = 0

    async def initialize(self) -> bool:
        await self.fsm.initialize()
        await self.audio_session.initialize()
        await self.wakeword.initialize()
        await self.stt.initialize()
        await self.llm.initialize()
        await self.tts.initialize()
        await self.session_store.initialize()

        if hasattr(self.audio_session, "subscribe_mic"):
            self.audio_session.subscribe_mic(self._handle_mic_frame)

        self._status = ServiceStatus.RUNNING
        logger.info("VoiceAssistantCapability initialized.")
        return True

    async def _handle_mic_frame(self, pcm_data: bytes) -> None:
        """Process incoming raw audio frames from the microphone stream."""
        if not pcm_data:
            return

        current_state = self.fsm.state

        if current_state == FSMState.IDLE:
            t0 = time.perf_counter()
            if await self.wakeword.detect(pcm_data):
                dt_ms = (time.perf_counter() - t0) * 1000.0
                self.observability.record_latency("wake_latency", dt_ms)
                await self.bus.publish(WakeDetected(score=1.0))
                await self.fsm.transition_to(FSMState.WAKE_DETECTED)
                await self.fsm.transition_to(FSMState.LISTENING)
                self._audio_buffer.clear()
                self.vad.reset()
                self._listening_start_time = time.perf_counter()
                await self.bus.publish(SpeechStarted())

        elif current_state == FSMState.LISTENING:
            if not self.vad._in_speech:
                if (
                    self._listening_start_time > 0
                    and (time.perf_counter() - self._listening_start_time > self.followup_timeout_s)
                ):
                    logger.info(
                        f"Listening timeout ({self.followup_timeout_s}s) elapsed without speech. Returning to IDLE."
                    )
                    self._listening_start_time = 0.0
                    self._audio_buffer.clear()
                    self.vad.reset()
                    await self.fsm.transition_to(FSMState.IDLE)
                    return

            self._audio_buffer.extend(pcm_data)
            vad_res = self.vad.process_chunk(pcm_data)

            if vad_res["speech_ended"]:
                await self.bus.publish(SpeechEnded(duration_ms=vad_res["silence_ms"]))
                await self.fsm.transition_to(FSMState.TRANSCRIBING)
                pcm_copy = bytes(self._audio_buffer)
                self._audio_buffer.clear()
                self.vad.reset()
                self._listening_start_time = 0.0
                self._active_task = asyncio.create_task(self._process_utterance(pcm_copy))

        elif current_state == FSMState.SPEAKING:
            if time.perf_counter() - self._speaking_start_time < 0.5:
                return

            is_playing = getattr(self.audio_session, "is_playing", False)
            rms = self.vad.calculate_rms(pcm_data)
            if is_playing and rms < self.vad.energy_threshold * 1.8:
                self._consecutive_speech_count = 0
                return

            vad_res = self.vad.process_chunk(pcm_data)
            if vad_res["is_speech"]:
                self._consecutive_speech_count += 1
                if self._consecutive_speech_count >= 2:
                    logger.info("User barge-in interrupt detected. Halting speech output.")
                    self.observability.increment_counter("cancellation_count")
                    await self.cancel()
                    await self.bus.publish(TaskCancelled(reason="Barge-in user speech"))
                    await self.fsm.transition_to(FSMState.LISTENING)
                    self._audio_buffer.clear()
                    self.vad.reset()
                    self._listening_start_time = time.perf_counter()
                    self._consecutive_speech_count = 0
            else:
                self._consecutive_speech_count = 0

    async def _process_utterance(self, pcm_bytes: bytes, session_id: str = "default_session") -> None:
        """Transcribe microphone audio and execute the response generation pipeline."""
        self._is_cancelled = False
        start_time = time.perf_counter()

        try:
            t0 = time.perf_counter()
            transcript = await self.stt.transcribe(pcm_bytes)
            stt_dt = (time.perf_counter() - t0) * 1000.0
            self.observability.record_latency("stt_latency", stt_dt)
            self.observability.log_timeline_event("STT_COMPLETE", duration_ms=stt_dt)

            clean_text = transcript.strip() if transcript else ""
            lower_text = clean_text.lower()
            ignored_hallucinations = {
                "[blank_audio]",
                "(silence)",
                "thank you.",
                "subtitles by",
                "thanks for watching!",
                "i can hear you clearly",
                "please ensure ollama is active",
                "i am processing your request",
                "model response timed out",
                "check if your computer is under high load",
                "then then then",
            }

            if not clean_text or any(h in lower_text for h in ignored_hallucinations):
                logger.info(
                    f"Discarding empty or hallucinated transcript ('{clean_text}'). Returning to IDLE."
                )
                await self.fsm.transition_to(FSMState.IDLE)
                return

            await self.process_text_prompt(clean_text, session_id=session_id, start_time=start_time)

        except asyncio.CancelledError:
            self._is_cancelled = True
            logger.info("Utterance processing task cancelled.")
        except Exception as e:
            logger.error(f"Utterance pipeline exception: {e}", exc_info=True)
            await self.bus.publish(
                ErrorOccurred(component="voice_assistant", message=str(e), exception=e)
            )
            await self.fsm.transition_to(FSMState.ERROR)

    async def process_text_prompt(
        self,
        transcript: str,
        session_id: str = "default_session",
        start_time: Optional[float] = None,
    ) -> None:
        """Process a text query directly through LLM and TTS pipeline."""
        self._is_cancelled = False
        if hasattr(self.audio_session, "reset_stop_flag"):
            self.audio_session.reset_stop_flag()

        if start_time is None:
            start_time = time.perf_counter()

        cleaned_prompt = _strip_wake_word_prefixes(transcript)
        if not cleaned_prompt:
            cleaned_prompt = "Hello! How can I help you today?"

        fallback_occurred = False

        try:
            logger.info(f"Processing prompt: '{cleaned_prompt}' (raw: '{transcript}')")
            await self.bus.publish(TranscriptReady(text=cleaned_prompt))
            await self.session_store.save_turn(session_id, "user", cleaned_prompt)

            await self.fsm.transition_to(FSMState.THINKING)
            if self.max_history_turns > 0:
                history = await self.session_store.get_history(session_id, limit=self.max_history_turns)
                formatted_history = (
                    [{"role": turn["role"], "content": turn["content"]} for turn in history[:-1]]
                    if len(history) > 1
                    else []
                )
            else:
                formatted_history = []

            t_llm_start = time.perf_counter()
            first_token_received = False
            full_response_text = ""

            self.chunker.reset()
            max_sentences_per_turn = 5

            async for token in self.llm.generate_stream(cleaned_prompt, formatted_history):
                if self._is_cancelled:
                    break

                if not first_token_received:
                    ttft = (time.perf_counter() - t_llm_start) * 1000.0
                    self.observability.record_latency("ttft", ttft)
                    self.observability.log_timeline_event("TTFT", duration_ms=ttft)
                    first_token_received = True

                full_response_text += token
                await self.bus.publish(TokenGenerated(token=token, accumulated_text=full_response_text))

                sentence_chunks = self.chunker.add_token(token)
                for sentence in sentence_chunks:
                    if self._is_cancelled:
                        break
                    await self._synthesize_and_speak(sentence)

                if self.chunker._sentence_count >= max_sentences_per_turn:
                    logger.info(f"Maximum sentence threshold ({max_sentences_per_turn}) reached for turn.")
                    break

            if self.chunker._sentence_count < max_sentences_per_turn:
                remaining_sentence = self.chunker.flush()
                if remaining_sentence and not self._is_cancelled:
                    await self._synthesize_and_speak(remaining_sentence)

            if not full_response_text.strip() and not self._is_cancelled:
                fallback_msg = "I heard you clearly! How can I help you today?"
                full_response_text = fallback_msg
                await self._synthesize_and_speak(fallback_msg)

            if (
                getattr(self.llm, "has_error", False)
                or "please ensure ollama is active" in full_response_text.lower()
            ):
                fallback_occurred = True

            if full_response_text and not self._is_cancelled and not fallback_occurred:
                await self.session_store.save_turn(session_id, "assistant", full_response_text)

            total_dt = (time.perf_counter() - start_time) * 1000.0
            self.observability.record_latency("total_response_latency", total_dt)
            self.observability.log_timeline_event("RESPONSE_COMPLETE", duration_ms=total_dt)

        except asyncio.CancelledError:
            self._is_cancelled = True
            logger.info("Text prompt task cancelled.")
        except Exception as e:
            logger.error(f"Text prompt execution error: {e}", exc_info=True)
            await self.bus.publish(
                ErrorOccurred(component="voice_assistant", message=str(e), exception=e)
            )
            await self.fsm.transition_to(FSMState.ERROR)
        finally:
            self._audio_buffer.clear()
            self.vad.reset()
            if not self._is_cancelled and self.fsm.state != FSMState.ERROR:
                if fallback_occurred:
                    logger.info("LLM fallback triggered; returning to IDLE state.")
                    await self.fsm.transition_to(FSMState.IDLE)
                else:
                    logger.info("Turn completed. Transitioning to LISTENING state.")
                    self._listening_start_time = time.perf_counter()
                    await self.fsm.transition_to(FSMState.LISTENING)

    async def _synthesize_and_speak(self, sentence: str) -> None:
        """Synthesize sentence text to speech audio chunks and queue for playback."""
        if not sentence or self._is_cancelled or getattr(self.audio_session, "_stop_requested", False):
            return

        self._speaking_start_time = time.perf_counter()
        self._consecutive_speech_count = 0
        await self.fsm.transition_to(FSMState.SPEAKING)
        await self.bus.publish(SentenceReady(sentence=sentence))

        t_tts_start = time.perf_counter()
        first_chunk = True

        async for audio_chunk in self.tts.synthesize_stream(sentence):
            if self._is_cancelled or getattr(self.audio_session, "_stop_requested", False):
                logger.info("Speech synthesis aborted due to cancellation.")
                break

            if first_chunk:
                tts_fa = (time.perf_counter() - t_tts_start) * 1000.0
                self.observability.record_latency("tts_first_audio", tts_fa)
                first_chunk = False

            await self.bus.publish(AudioChunkReady(audio_bytes=audio_chunk.data))
            await self.audio_session.play_audio_chunk(audio_chunk)

        if not self._is_cancelled and hasattr(self.audio_session, "wait_for_playback_complete"):
            await self.audio_session.wait_for_playback_complete()

        await self.bus.publish(PlaybackFinished())
        self._audio_buffer.clear()
        self.vad.reset()

    async def execute(self, action: str, params: Dict[str, Any], session_id: str) -> Any:
        """Execute capability actions requested by the task executor."""
        if action == "process_voice":
            pcm = params.get("pcm_data", b"")
            if pcm:
                await self._process_utterance(pcm, session_id=session_id)
            else:
                prompt = params.get("prompt", "Hello")
                await self.process_text_prompt(prompt, session_id=session_id)
            return "Voice processed successfully"
        return "Unknown action"

    async def health(self) -> HealthStatus:
        return HealthStatus(
            status=self._status,
            message="VoiceAssistantCapability active",
            details={
                "fsm_state": self.fsm.state.value,
                "audio_buffer_size": len(self._audio_buffer),
            },
        )

    async def shutdown(self) -> None:
        await self.cancel()
        await self.fsm.shutdown()
        await self.audio_session.shutdown()
        await self.stt.shutdown()
        await self.llm.shutdown()
        await self.tts.shutdown()
        await self.session_store.shutdown()
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        self._is_cancelled = True
        await self.audio_session.stop_playback()
        await self.tts.cancel()
        await self.llm.cancel()
        await self.bus.publish(TaskCancelled(reason="Barge-in / User Cancellation"))
        await safe_cancel_task(self._active_task)

