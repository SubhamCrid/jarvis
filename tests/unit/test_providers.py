"""
Unit tests for STT, LLM, TTS, and WakeWord Provider contracts and health checks.
"""

import pytest
from vidya.providers.stt.mock_stt import MockSTT
from vidya.providers.stt.whisper_cpp_stt import WhisperCppSTT
from vidya.providers.llm.mock_llm import MockLLM
from vidya.providers.llm.ollama_llm import OllamaLLM
from vidya.providers.tts.mock_tts import MockTTS
from vidya.providers.tts.piper_tts import PiperTTS
from vidya.providers.wakeword.mock_wakeword import MockWakeWord
from vidya.providers.wakeword.openwakeword_provider import OpenWakeWordProvider
from vidya.core.base import ServiceStatus


@pytest.mark.asyncio
async def test_mock_stt():
    stt = MockSTT(response_text="Hello world")
    assert await stt.initialize()
    res = await stt.transcribe(b"\x00" * 1024)
    assert res == "Hello world"
    health = await stt.health()
    assert health.status == ServiceStatus.RUNNING
    await stt.shutdown()


@pytest.mark.asyncio
async def test_whisper_cpp_stt_standby():
    stt = WhisperCppSTT(model="tiny")
    assert await stt.initialize()
    health = await stt.health()
    assert health.status in (ServiceStatus.RUNNING, ServiceStatus.DEGRADED)
    res = await stt.transcribe(b"")
    assert res == ""
    await stt.shutdown()


@pytest.mark.asyncio
async def test_mock_llm_streaming():
    llm = MockLLM(response="Testing LLM response stream")
    assert await llm.initialize()

    tokens = []
    async for token in llm.generate_stream("Hi"):
        tokens.append(token)

    full_text = "".join(tokens)
    assert full_text == "Testing LLM response stream"
    await llm.shutdown()


@pytest.mark.asyncio
async def test_mock_tts_streaming():
    tts = MockTTS()
    assert await tts.initialize()

    chunks = []
    async for chunk in tts.synthesize_stream("Testing speech synthesis"):
        chunks.append(chunk)

    assert len(chunks) == 2
    assert len(chunks[0].data) > 0
    await tts.shutdown()


@pytest.mark.asyncio
async def test_mock_wakeword():
    ww = MockWakeWord()
    assert await ww.initialize()

    # Normal frame should return False
    assert not await ww.detect(b"\x00" * 512)

    # Trigger wake programmatically
    ww.trigger_wake()
    assert await ww.detect(b"\x00" * 512)
    assert not await ww.detect(b"\x00" * 512)
    await ww.shutdown()


def test_edge_tts_script_selection():
    from vidya.providers.tts.edge_tts_provider import EdgeTTSProvider
    # Default: auto_switch_voice=False preserves selected voice even with Devanagari characters
    provider_default = EdgeTTSProvider(voice="en-US-AvaMultilingualNeural", auto_switch_voice=False, speed=1.25)
    assert provider_default._select_voice_for_text("Hello, how are you?") == "en-US-AvaMultilingualNeural"
    assert provider_default._select_voice_for_text("नमस्ते, आप कैसे हैं?") == "en-US-AvaMultilingualNeural"
    assert provider_default._get_rate_str() == "+25%"

    # When auto_switch_voice=True, Hindi Devanagari script triggers Hindi voice
    provider_auto = EdgeTTSProvider(voice="en-US-AvaMultilingualNeural", auto_switch_voice=True)
    assert provider_auto._select_voice_for_text("नमस्ते, आप कैसे हैं?") == "hi-IN-SwaraNeural"

