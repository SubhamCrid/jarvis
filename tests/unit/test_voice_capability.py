"""
Unit & Integration tests for VoiceAssistantCapability, pipeline, and barge-in interruption.
"""

import pytest
import asyncio
from jarvis.core.config.loader import load_config
from jarvis.orchestrator import AssistantOrchestrator
from jarvis.core.fsm import FSMState
from jarvis.core.bus import WakeDetected, TranscriptReady, TokenGenerated, SentenceReady


@pytest.mark.asyncio
async def test_voice_capability_full_pipeline():
    config = load_config(user_overrides={
        "system": {"environment": "test"},
        "wakeword": {"provider": "mock"},
        "stt": {"provider": "mock"},
        "llm": {"provider": "mock"},
        "tts": {"provider": "mock"},
    })

    orchestrator = AssistantOrchestrator(config)
    assert await orchestrator.initialize()

    events_received = []

    async def event_handler(event):
        events_received.append(type(event).__name__)

    orchestrator.bus.subscribe_all(event_handler)

    # Simulate PCM audio processing
    dummy_speech_pcm = (b"\x7f\x3f" * 512)
    
    # Process voice task
    result = await orchestrator.process_task(
        session_id="test_sess_001",
        task_type="voice_interaction",
        payload={"pcm_data": dummy_speech_pcm}
    )

    assert result == "Voice processed successfully"
    await asyncio.sleep(0.1)

    # Verify event timeline sequence
    assert "TranscriptReady" in events_received
    assert "TokenGenerated" in events_received
    assert "SentenceReady" in events_received

    # Verify storage history persistence
    history = await orchestrator.session_store.get_history("test_sess_001")
    assert len(history) >= 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"

    # Verify observability metrics
    metrics = orchestrator.observability.get_metrics_summary()
    assert "stt_latency" in metrics
    assert "ttft" in metrics
    assert "tts_first_audio" in metrics

    await orchestrator.shutdown()


@pytest.mark.asyncio
async def test_voice_capability_barge_in():
    config = load_config(user_overrides={"system": {"environment": "test"}})
    orchestrator = AssistantOrchestrator(config)
    await orchestrator.initialize()

    # Manually transition FSM to SPEAKING to test barge-in
    fsm = orchestrator.fsm
    await fsm.transition_to(FSMState.WAKE_DETECTED)
    await fsm.transition_to(FSMState.LISTENING)
    await fsm.transition_to(FSMState.TRANSCRIBING)
    await fsm.transition_to(FSMState.THINKING)
    await fsm.transition_to(FSMState.SPEAKING)

    assert fsm.state == FSMState.SPEAKING
    orchestrator.voice_capability._speaking_start_time = 0.0

    # Send 3 consecutive loud speech PCM frames to trigger barge-in interrupt
    loud_speech_pcm = (b"\x7f\x3f" * 512)
    for _ in range(3):
        await orchestrator.voice_capability._handle_mic_frame(loud_speech_pcm)

    # Verify FSM transitioned to LISTENING
    assert fsm.state == FSMState.LISTENING
    assert orchestrator.observability.get_metrics_summary()["counters"]["cancellation_count"] == 1

    await orchestrator.shutdown()


@pytest.mark.asyncio
async def test_voice_capability_llm_fallback_transitions_to_idle():
    config = load_config(user_overrides={"system": {"environment": "test"}})
    orchestrator = AssistantOrchestrator(config)
    await orchestrator.initialize()

    # Simulate LLM provider error state
    orchestrator.voice_capability.llm.has_error = True

    await orchestrator.voice_capability.process_text_prompt("Hello", session_id="test_fallback_sess")

    # Should transition to IDLE instead of LISTENING to avoid infinite retry loop
    assert orchestrator.fsm.state == FSMState.IDLE

    await orchestrator.shutdown()
