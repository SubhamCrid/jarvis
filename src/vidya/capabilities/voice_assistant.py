"""
VoiceAssistantCapability orchestrating Voice FSM, VAD, STT, LLM streaming, TTS chunking,
AudioSession, SessionStore, and Instantaneous Barge-in Interruption with Streaming Backpressure.
"""

import time
import asyncio
import logging
from typing import Dict, Any, Optional, List
from vidya.capabilities.base import BaseCapability, PermissionEnum
from vidya.core.base import ServiceStatus, HealthStatus
from vidya.core.fsm import VoiceFSM, FSMState
from vidya.core.bus import (
    MessageBus,
    WakeDetected,
    SpeechStarted,
    SpeechEnded,
    TranscriptReady,
    TokenGenerated,
    SentenceReady,
    AudioChunkReady,
    PlaybackFinished,
    TaskCancelled,
    ErrorOccurred,
)
from vidya.core.observability import ObservabilityService
from vidya.providers.base import AudioSessionProtocol, STTProtocol, LLMProtocol, TTSProtocol, WakeWordProtocol, StorageProtocol, AudioChunk
from vidya.providers.audio.vad import VADEngine
from vidya.providers.chunker import SentenceChunker
from vidya.utils.async_utils import BoundedQueue, safe_cancel_task

logger = logging.getLogger("vidya.capabilities.voice_assistant")


class VoiceAssistantCapability(BaseCapability):
    """
    Primary Voice Assistant Capability.
    Orchestrates finite state machine voice pipeline with bounded queue backpressure and barge-in.
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
        silence_duration_ms: int = 700
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

        self.vad = VADEngine(energy_threshold=vad_threshold, silence_duration_ms=silence_duration_ms)
        self.chunker = SentenceChunker()
        self._status = ServiceStatus.UNINITIALIZED

        # Bounded queues for backpressure
        self._audio_buffer: bytearray = bytearray()
        self._token_queue: BoundedQueue[str] = BoundedQueue(maxsize=100)
        self._active_task: Optional[asyncio.Task] = None
        self._is_cancelled: bool = False

    async def initialize(self) -> bool:
        await self.fsm.initialize()
        await self.audio_session.initialize()
        await self.wakeword.initialize()
        await self.stt.initialize()
        await self.llm.initialize()
        await self.tts.initialize()
        await self.session_store.initialize()

        # Subscribe mic stream from AudioSession
        if hasattr(self.audio_session, "subscribe_mic"):
            self.audio_session.subscribe_mic(self._handle_mic_frame)

        self._status = ServiceStatus.RUNNING
        logger.info("VoiceAssistantCapability initialized successfully.")
        return True

    async def _handle_mic_frame(self, pcm_data: bytes) -> None:
        """Process incoming mic frame from AudioSessionManager."""
        if not pcm_data:
            return

        current_state = self.fsm.state

        # 1. Wake word detection during IDLE state
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
                await self.bus.publish(SpeechStarted())

        # 2. VAD processing during LISTENING state
        elif current_state == FSMState.LISTENING:
            self._audio_buffer.extend(pcm_data)
            vad_res = self.vad.process_chunk(pcm_data)

            if vad_res["speech_ended"]:
                await self.bus.publish(SpeechEnded(duration_ms=vad_res["silence_ms"]))
                await self.fsm.transition_to(FSMState.TRANSCRIBING)
                pcm_copy = bytes(self._audio_buffer)
                self._audio_buffer.clear()
                self._active_task = asyncio.create_task(self._process_utterance(pcm_copy))

        # 3. Barge-in / Interruption check during SPEAKING state
        elif current_state == FSMState.SPEAKING:
            vad_res = self.vad.process_chunk(pcm_data)
            if vad_res["is_speech"]:
                logger.info("Barge-in interrupt detected! Halting active speech synthesis.")
                self.observability.increment_counter("cancellation_count")
                await self.cancel()
                await self.bus.publish(TaskCancelled(reason="Barge-in user speech"))
                await self.fsm.transition_to(FSMState.LISTENING)
                self._audio_buffer.clear()
                self._audio_buffer.extend(pcm_data)
                self.vad.reset()

    async def _process_utterance(self, pcm_bytes: bytes) -> None:
        """Full audio pipeline: STT -> LLM token stream -> Sentence Chunker -> TTS -> Speaker."""
        self._is_cancelled = False
        session_id = "default_session"
        start_time = time.perf_counter()

        try:
            # Step A: STT Transcription
            t0 = time.perf_counter()
            transcript = await self.stt.transcribe(pcm_bytes)
            stt_dt = (time.perf_counter() - t0) * 1000.0
            self.observability.record_latency("stt_latency", stt_dt)
            self.observability.log_timeline_event("STT_COMPLETE", duration_ms=stt_dt)

            if not transcript or not transcript.strip():
                logger.info("Empty transcript received from STT. Returning to IDLE.")
                await self.fsm.transition_to(FSMState.IDLE)
                return

            await self.process_text_prompt(transcript, session_id=session_id, start_time=start_time)

        except asyncio.CancelledError:
            self._is_cancelled = True
            logger.info("Utterance processing cancelled.")
        except Exception as e:
            logger.error(f"Error in utterance pipeline: {e}", exc_info=True)
            await self.bus.publish(ErrorOccurred(component="voice_assistant", message=str(e), exception=e))
            await self.fsm.transition_to(FSMState.ERROR)
        finally:
            if not self._is_cancelled and self.fsm.state != FSMState.ERROR:
                await self.fsm.transition_to(FSMState.IDLE)

    async def process_text_prompt(self, transcript: str, session_id: str = "default_session", start_time: Optional[float] = None) -> None:
        """Direct text prompt execution bypassing STT (used for UI prompt testing or direct commands)."""
        self._is_cancelled = False
        if start_time is None:
            start_time = time.perf_counter()

        try:
            logger.info(f"Processing text prompt: '{transcript}'")
            await self.bus.publish(TranscriptReady(text=transcript))
            await self.session_store.save_turn(session_id, "user", transcript)

            # Step B: LLM Generation
            await self.fsm.transition_to(FSMState.THINKING)
            history = await self.session_store.get_history(session_id, limit=10)
            
            formatted_history = [
                {"role": turn["role"], "content": turn["content"]}
                for turn in history[:-1]
            ]

            t_llm_start = time.perf_counter()
            first_token_received = False
            full_response_text = ""

            self.chunker.reset()

            async for token in self.llm.generate_stream(transcript, formatted_history):
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

            remaining_sentence = self.chunker.flush()
            if remaining_sentence and not self._is_cancelled:
                await self._synthesize_and_speak(remaining_sentence)

            if full_response_text and not self._is_cancelled:
                await self.session_store.save_turn(session_id, "assistant", full_response_text)

            total_dt = (time.perf_counter() - start_time) * 1000.0
            self.observability.record_latency("total_response_latency", total_dt)
            self.observability.log_timeline_event("RESPONSE_COMPLETE", duration_ms=total_dt)

        except asyncio.CancelledError:
            self._is_cancelled = True
            logger.info("Text prompt processing cancelled.")
        except Exception as e:
            logger.error(f"Error processing text prompt: {e}", exc_info=True)
            await self.bus.publish(ErrorOccurred(component="voice_assistant", message=str(e), exception=e))
            await self.fsm.transition_to(FSMState.ERROR)
        finally:
            if not self._is_cancelled and self.fsm.state != FSMState.ERROR:
                await self.fsm.transition_to(FSMState.IDLE)

    async def _synthesize_and_speak(self, sentence: str) -> None:
        """Synthesize sentence to TTS AudioChunks and output to Speaker."""
        if not sentence or self._is_cancelled:
            return

        await self.fsm.transition_to(FSMState.SPEAKING)
        await self.bus.publish(SentenceReady(sentence=sentence))

        t_tts_start = time.perf_counter()
        first_chunk = True

        async for audio_chunk in self.tts.synthesize_stream(sentence):
            if self._is_cancelled:
                break

            if first_chunk:
                tts_fa = (time.perf_counter() - t_tts_start) * 1000.0
                self.observability.record_latency("tts_first_audio", tts_fa)
                first_chunk = False

            await self.bus.publish(AudioChunkReady(audio_bytes=audio_chunk.data))
            await self.audio_session.play_audio_chunk(audio_chunk)

        await self.bus.publish(PlaybackFinished())

    async def execute(self, action: str, params: Dict[str, Any], session_id: str) -> Any:
        """Execute action passed from TaskExecutor."""
        if action == "process_voice":
            pcm = params.get("pcm_data", b"")
            if pcm:
                await self._process_utterance(pcm)
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
                "audio_buffer_size": len(self._audio_buffer)
            }
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
        await safe_cancel_task(self._active_task)
