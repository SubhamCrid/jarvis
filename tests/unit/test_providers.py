"""
Unit tests for STT, LLM, TTS, and WakeWord Provider contracts and health checks.
"""

import pytest
from jarvis.providers.stt.mock_stt import MockSTT
from jarvis.providers.stt.whisper_cpp_stt import WhisperCppSTT
from jarvis.providers.llm.mock_llm import MockLLM
from jarvis.providers.llm.ollama_llm import OllamaLLM
from jarvis.providers.tts.mock_tts import MockTTS
from jarvis.providers.tts.piper_tts import PiperTTS
from jarvis.providers.wakeword.mock_wakeword import MockWakeWord
from jarvis.providers.wakeword.openwakeword_provider import OpenWakeWordProvider
from jarvis.core.base import ServiceStatus


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
    initialized = await stt.initialize()
    if initialized:
        health = await stt.health()
        assert health.status in (ServiceStatus.RUNNING, ServiceStatus.DEGRADED)
        res = await stt.transcribe(b"")
        assert res == ""
        await stt.shutdown()
    else:
        health = await stt.health()
        assert health.status in (ServiceStatus.STOPPED, ServiceStatus.ERROR)


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
    from jarvis.providers.tts.edge_tts_provider import EdgeTTSProvider
    # Default: auto_switch_voice=False preserves selected voice even with Devanagari characters
    provider_default = EdgeTTSProvider(voice="en-US-AvaMultilingualNeural", auto_switch_voice=False, speed=1.25)
    assert provider_default._select_voice_for_text("Hello, how are you?") == "en-US-AvaMultilingualNeural"
    assert provider_default._select_voice_for_text("नमस्ते, आप कैसे हैं?") == "en-US-AvaMultilingualNeural"
    assert provider_default._get_rate_str() == "+25%"

    # When auto_switch_voice=True, Hindi Devanagari script triggers Hindi voice
    provider_auto = EdgeTTSProvider(voice="en-US-AvaMultilingualNeural", auto_switch_voice=True)
    assert provider_auto._select_voice_for_text("नमस्ते, आप कैसे हैं?") == "hi-IN-SwaraNeural"


@pytest.mark.asyncio
async def test_kokoro_tts_streaming():
    from jarvis.providers.tts.kokoro_tts import KokoroTTS
    tts = KokoroTTS(voice="af_bella", speed=1.15)
    # Initialize will return True if kokoro installed, False if standby mode (both handled gracefully)
    init_res = await tts.initialize()
    assert isinstance(init_res, bool)

    health_res = await tts.health()
    assert health_res.details["voice"] == "af_bella"

    chunks = []
    async for chunk in tts.synthesize_stream("Hello from Kokoro TTS"):
        chunks.append(chunk)

    assert len(chunks) > 0
    assert len(chunks[0].data) > 0
    await tts.shutdown()


@pytest.mark.asyncio
async def test_chatterbox_tts_streaming():
    from jarvis.providers.tts.chatterbox_tts import ChatterboxTTS
    tts = ChatterboxTTS(voice="en_female", cfg_weight=0.7, exaggeration=0.6, enable_fallback=False)

    # Test script language detection
    assert tts._infer_language_id("Hello world") == "en"
    assert tts._infer_language_id("नमस्ते दुनिया") == "hi"
    assert tts._infer_language_id("こんにちは") == "ja"
    assert tts._infer_language_id("你好") == "zh"

    # Initialize handles missing dependencies gracefully
    init_res = await tts.initialize()
    assert isinstance(init_res, bool)

    health_res = await tts.health()
    assert health_res.details["voice"] == "en_female"
    assert health_res.details["cfg_weight"] == 0.7
    assert health_res.details["exaggeration"] == 0.6
    assert health_res.details["enable_fallback"] is False

    chunks = []
    async for chunk in tts.synthesize_stream("Testing Chatterbox synthesis"):
        chunks.append(chunk)

    assert len(chunks) > 0
    assert len(chunks[0].data) > 0
    await tts.shutdown()



