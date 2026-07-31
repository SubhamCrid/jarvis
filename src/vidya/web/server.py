"""
Aiohttp Web Dashboard Server and WebSocket Real-Time Bridge for Vidya Assistant.
"""

import json
import asyncio
import logging
from pathlib import Path
from typing import Set, Any, Optional
from aiohttp import web

from vidya.orchestrator import AssistantOrchestrator
from vidya.core.fsm import FSMState
from vidya.core.bus import (
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

logger = logging.getLogger("vidya.web.server")


class WebDashboardServer:
    """
    Hosts Web Dashboard and bridges AssistantOrchestrator events over WebSockets.
    """

    def __init__(self, orchestrator: AssistantOrchestrator, port: int = 8000) -> None:
        self.orchestrator = orchestrator
        self.port = port
        self.app = web.Application()
        self.sockets: Set[web.WebSocketResponse] = set()
        self._runner: Optional[web.AppRunner] = None
        self._setup_routes()

    def _setup_routes(self) -> None:
        # Static Dashboard Frontend
        static_dir = Path(__file__).parent / "static"
        self.app.router.add_static("/static", static_dir)
        self.app.router.add_get("/", self._handle_index)

        # WebSockets
        self.app.router.add_get("/ws", self._handle_websocket)

        # REST API Endpoints
        self.app.router.add_post("/api/trigger-wake", self._handle_trigger_wake)
        self.app.router.add_post("/api/interrupt", self._handle_interrupt)
        self.app.router.add_post("/api/simulate-voice", self._handle_simulate_voice)
        self.app.router.add_get("/api/audio-devices", self._handle_list_audio_devices)
        self.app.router.add_post("/api/select-device", self._handle_select_audio_device)
        self.app.router.add_get("/api/health", self._handle_health)
        self.app.router.add_get("/api/metrics", self._handle_metrics)

        # Subscribe MessageBus events to push to WebSocket clients
        self.orchestrator.bus.subscribe_all(self._on_bus_event)
        self.orchestrator.fsm.add_state_callback(self._on_fsm_state_change)

    async def _handle_index(self, request: web.Request) -> web.Response:
        index_path = Path(__file__).parent / "static" / "index.html"
        return web.FileResponse(index_path)

    async def _handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.sockets.add(ws)
        logger.info("New Web UI WebSocket client connected.")

        # Send initial state and metrics
        await ws.send_json({
            "type": "state_change",
            "state": self.orchestrator.fsm.state.value
        })
        await ws.send_json({
            "type": "metrics",
            "metrics": self.orchestrator.observability.get_metrics_summary()
        })

        try:
            async for msg in ws:
                pass
        finally:
            self.sockets.remove(ws)
            logger.info("Web UI WebSocket client disconnected.")

        return ws

    async def broadcast(self, payload: dict) -> None:
        """Broadcast payload to all connected Web UI clients."""
        for ws in self.sockets.copy():
            try:
                await ws.send_json(payload)
            except Exception:
                pass

    async def _on_fsm_state_change(self, from_state: FSMState, to_state: FSMState) -> None:
        await self.broadcast({
            "type": "state_change",
            "state": to_state.value
        })

    async def _on_bus_event(self, event: Any) -> None:
        event_type = type(event).__name__
        if isinstance(event, TranscriptReady):
            await self.broadcast({"type": "transcript", "text": event.text})
        elif isinstance(event, TokenGenerated):
            await self.broadcast({"type": "llm_chunk", "token": event.token})
        elif isinstance(event, SentenceReady):
            await self.broadcast({"type": "sentence", "sentence": event.sentence})
        
        # Always push metrics update
        await self.broadcast({
            "type": "metrics",
            "metrics": self.orchestrator.observability.get_metrics_summary()
        })

    async def _handle_trigger_wake(self, request: web.Request) -> web.Response:
        logger.info("Web UI triggered wake event ('hey_jarvis')")
        await self.orchestrator.bus.publish(WakeDetected(score=1.0, model_name="hey_jarvis"))
        await self.orchestrator.fsm.transition_to(FSMState.WAKE_DETECTED)
        await self.orchestrator.fsm.transition_to(FSMState.LISTENING)
        return web.json_response({"status": "wake_triggered"})

    async def _handle_interrupt(self, request: web.Request) -> web.Response:
        logger.info("Web UI triggered interrupt / barge-in")
        await self.orchestrator.cancel()
        await self.orchestrator.fsm.transition_to(FSMState.LISTENING)
        return web.json_response({"status": "interrupted"})

    async def _handle_simulate_voice(self, request: web.Request) -> web.Response:
        data = await request.json()
        prompt = data.get("prompt", "")
        if prompt:
            logger.info(f"Web UI submitted prompt: '{prompt}'")
            if self.orchestrator.voice_capability:
                asyncio.create_task(
                    self.orchestrator.voice_capability.process_text_prompt(prompt)
                )
        return web.json_response({"status": "processing", "prompt": prompt})

    async def _handle_list_audio_devices(self, request: web.Request) -> web.Response:
        devices = []
        if hasattr(self.orchestrator.audio_session, "list_input_devices"):
            devices = self.orchestrator.audio_session.list_input_devices()
        return web.json_response({"devices": devices})

    async def _handle_select_audio_device(self, request: web.Request) -> web.Response:
        data = await request.json()
        device_index = data.get("device_index")
        if device_index is not None and hasattr(self.orchestrator.audio_session, "set_input_device"):
            await self.orchestrator.audio_session.set_input_device(device_index)
            return web.json_response({"status": "selected", "device_index": device_index})
        return web.json_response({"status": "error", "message": "Invalid device_index"}, status=400)

    async def _handle_health(self, request: web.Request) -> web.Response:
        health = await self.orchestrator.health()
        return web.json_response({
            "status": health.status.value,
            "message": health.message,
            "details": health.details
        })

    async def _handle_metrics(self, request: web.Request) -> web.Response:
        metrics = self.orchestrator.observability.get_metrics_summary()
        return web.json_response(metrics)

    async def start(self) -> None:
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self.port)
        await site.start()
        logger.info(f"Vidya Web Dashboard active at http://localhost:{self.port}")

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()
