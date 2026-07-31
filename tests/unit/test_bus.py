"""
Unit tests for MessageBus and event schemas.
"""

import pytest
import asyncio
from vidya.core.bus import (
    MessageBus,
    WakeDetected,
    SpeechStarted,
    TranscriptReady,
    TokenGenerated,
    SentenceReady,
    AudioChunkReady,
    PlaybackFinished,
    TaskCompleted,
    ErrorOccurred,
)


@pytest.mark.asyncio
async def test_message_bus_publish_subscribe(message_bus: MessageBus):
    received_events = []

    async def on_wake(event: WakeDetected):
        received_events.append(event)

    message_bus.subscribe(WakeDetected, on_wake)

    wake_event = WakeDetected(score=0.95, model_name="openwakeword")
    await message_bus.publish(wake_event)
    await asyncio.sleep(0.05)  # Allow async task to complete

    assert len(received_events) == 1
    assert received_events[0].score == 0.95


@pytest.mark.asyncio
async def test_message_bus_multiple_schemas(message_bus: MessageBus):
    tokens = []

    async def on_token(event: TokenGenerated):
        tokens.append(event.token)

    message_bus.subscribe(TokenGenerated, on_token)

    await message_bus.publish(TokenGenerated(token="Hello"))
    await message_bus.publish(TokenGenerated(token=" world"))
    await asyncio.sleep(0.05)

    assert tokens == ["Hello", " world"]


@pytest.mark.asyncio
async def test_message_bus_background_task_tracking(message_bus: MessageBus):
    executed = asyncio.Event()

    async def slow_handler(event: SpeechStarted):
        await asyncio.sleep(0.01)
        executed.set()

    message_bus.subscribe(SpeechStarted, slow_handler)
    await message_bus.publish(SpeechStarted())

    await asyncio.wait_for(executed.wait(), timeout=1.0)
    await asyncio.sleep(0.02)
    assert len(message_bus._background_tasks) == 0

