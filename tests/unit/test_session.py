"""
Unit tests for AudioSessionManager, VADEngine, and MockAudioSession.
"""

import pytest
import asyncio
from jarvis.providers.audio.vad import VADEngine
from jarvis.providers.audio.mock_audio import MockAudioSession
from jarvis.providers.base import AudioChunk


@pytest.mark.asyncio
async def test_vad_engine():
    vad = VADEngine(energy_threshold=0.02, silence_duration_ms=200, sample_rate=16000)
    
    # Silence frame (all zeros)
    silence_pcm = b"\x00\x00" * 512
    res_silence = vad.process_chunk(silence_pcm)
    assert not res_silence["is_speech"]
    assert res_silence["rms"] == 0.0

    # Loud speech frame (high amplitude PCM)
    speech_pcm = (b"\x7f\x3f" * 512)
    res_speech = vad.process_chunk(speech_pcm)
    assert res_speech["is_speech"]
    assert res_speech["in_speech_session"]


@pytest.mark.asyncio
async def test_mock_audio_session_mic_subscribers():
    session = MockAudioSession()
    await session.initialize()

    received_frames = []

    async def mic_handler(pcm: bytes):
        received_frames.append(pcm)

    session.subscribe_mic(mic_handler)
    await session.start_listening()

    # Simulate mic input
    sample_pcm = b"\x01\x02\x03\x04"
    await session.simulate_mic_input(sample_pcm)

    assert len(received_frames) == 1
    assert received_frames[0] == sample_pcm

    await session.stop_listening()
    await session.simulate_mic_input(sample_pcm)
    # Should not receive frame after listening stopped
    assert len(received_frames) == 1


@pytest.mark.asyncio
async def test_mock_audio_session_barge_in_flush():
    session = MockAudioSession()
    await session.initialize()

    chunk1 = AudioChunk(data=b"1234")
    chunk2 = AudioChunk(data=b"5678")

    await session.play_audio_chunk(chunk1)
    await session.play_audio_chunk(chunk2)

    assert len(session.get_played_chunks()) == 2

    # Interrupt barge-in
    await session.stop_playback()
    assert session._playback_queue.empty()
