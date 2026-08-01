"""
Aiohttp web server hosting the dashboard static application and WebSocket streaming bridge.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Set

from aiohttp import web

from jarvis.core.bus import (
    SentenceReady,
    TaskCancelled,
    TokenGenerated,
    TranscriptReady,
    WakeDetected,
)
from jarvis.core.fsm import FSMState
from jarvis.orchestrator import AssistantOrchestrator

logger = logging.getLogger("jarvis.web.server")


class WebDashboardServer:
    """
    HTTP server hosting the frontend web dashboard and broadcasting real-time
    orchestrator events over WebSocket connections.
    """

    def __init__(self, orchestrator: AssistantOrchestrator, port: int = 8000) -> None:
        self.orchestrator = orchestrator
        self.port = port
        self.app = web.Application()
        self.sockets: Set[web.WebSocketResponse] = set()
        self._runner: Optional[web.AppRunner] = None
        self._setup_routes()

    def _setup_routes(self) -> None:
        static_dir = Path(__file__).parent / "static"
        self.app.router.add_static("/static", static_dir)
        self.app.router.add_get("/", self._handle_index)
        self.app.router.add_get("/ws", self._handle_websocket)

        self.app.router.add_post("/api/trigger-wake", self._handle_trigger_wake)
        self.app.router.add_post("/api/stop-listening", self._handle_stop_listening)
        self.app.router.add_post("/api/interrupt", self._handle_interrupt)
        self.app.router.add_post("/api/simulate-voice", self._handle_simulate_voice)
        self.app.router.add_get("/api/audio-devices", self._handle_list_audio_devices)
        self.app.router.add_post("/api/select-device", self._handle_select_audio_device)
        self.app.router.add_get("/api/settings", self._handle_get_settings)
        self.app.router.add_post("/api/settings", self._handle_update_settings)
        self.app.router.add_get("/api/health", self._handle_health)
        self.app.router.add_get("/api/metrics", self._handle_metrics)

        self.app.router.add_get("/api/tools", self._handle_list_tools)
        self.app.router.add_post("/api/tools/execute", self._handle_execute_tool)
        self.app.router.add_get("/api/capabilities", self._handle_list_capabilities)
        self.app.router.add_get("/api/agent/state", self._handle_get_agent_state)
        self.app.router.add_post("/api/approval/respond", self._handle_respond_approval)

        self.orchestrator.bus.subscribe_all(self._on_bus_event)
        self.orchestrator.fsm.add_state_callback(self._on_fsm_state_change)

    async def _handle_index(self, request: web.Request) -> web.FileResponse:
        index_path = Path(__file__).parent / "static" / "index.html"
        return web.FileResponse(index_path)

    async def _handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.sockets.add(ws)
        logger.info("WebSocket client connected to web dashboard.")

        await ws.send_json({
            "type": "state_change",
            "state": self.orchestrator.fsm.state.value,
        })
        await ws.send_json({
            "type": "metrics",
            "metrics": self.orchestrator.observability.get_metrics_summary(),
        })

        try:
            async for _ in ws:
                pass
        except Exception as err:
            logger.debug(f"WebSocket client loop exited: {err}")
        finally:
            self.sockets.discard(ws)
            logger.info("WebSocket client disconnected from web dashboard.")

        return ws

    async def broadcast(self, payload: Dict[str, Any]) -> None:
        """Broadcast payload dictionary to all connected WebSocket clients."""
        for ws in self.sockets.copy():
            try:
                if not ws.closed:
                    await ws.send_json(payload)
                else:
                    self.sockets.discard(ws)
            except Exception:
                self.sockets.discard(ws)


    async def _on_fsm_state_change(self, from_state: FSMState, to_state: FSMState) -> None:
        await self.broadcast({
            "type": "state_change",
            "state": to_state.value,
        })

    async def _on_bus_event(self, event: Any) -> None:
        from jarvis.runtime.events import StepStarted, StepCompleted
        if isinstance(event, TranscriptReady):
            await self.broadcast({"type": "transcript", "text": event.text})
        elif isinstance(event, TokenGenerated):
            await self.broadcast({"type": "llm_chunk", "token": event.token})
        elif isinstance(event, SentenceReady):
            await self.broadcast({"type": "sentence", "sentence": event.sentence})
        elif isinstance(event, TaskCancelled):
            await self.broadcast({"type": "task_cancelled", "reason": event.reason})
        elif isinstance(event, StepStarted):
            await self.broadcast({
                "type": "tool_executing",
                "call_id": event.step_id,
                "tool_name": event.action_name,
                "params": getattr(event, "params", {}),
            })
        elif isinstance(event, StepCompleted):
            await self.broadcast({
                "type": "tool_completed",
                "call_id": event.step_id,
                "tool_name": getattr(event, "capability_name", "tool"),
                "success": event.success,
                "result": event.result,
                "execution_time_ms": getattr(event, "execution_time_ms", 0),
            })

        await self.broadcast({
            "type": "metrics",
            "metrics": self.orchestrator.observability.get_metrics_summary(),
        })

    async def _handle_trigger_wake(self, request: web.Request) -> web.Response:
        logger.info("Web dashboard triggered wake event.")
        await self.orchestrator.cancel()
        if self.orchestrator.wakeword and hasattr(self.orchestrator.wakeword, "reset"):
            self.orchestrator.wakeword.reset()
        if self.orchestrator.voice_capability:
            self.orchestrator.voice_capability._seed_audio_buffer_from_preroll()
            self.orchestrator.voice_capability.vad.reset()
            if hasattr(self.orchestrator.voice_capability.wakeword, "reset"):
                self.orchestrator.voice_capability.wakeword.reset()
            import time
            self.orchestrator.voice_capability._listening_start_time = time.perf_counter()
        await self.orchestrator.bus.publish(WakeDetected(score=1.0, model_name="hey_jarvis"))
        await self.orchestrator.fsm.transition_to(FSMState.WAKE_DETECTED)
        await self.orchestrator.fsm.transition_to(FSMState.LISTENING)
        return web.json_response({"status": "wake_triggered"})

    async def _handle_stop_listening(self, request: web.Request) -> web.Response:
        logger.info("Web dashboard triggered stop listening.")
        await self.orchestrator.cancel()
        if self.orchestrator.wakeword and hasattr(self.orchestrator.wakeword, "reset"):
            self.orchestrator.wakeword.reset()
        if self.orchestrator.voice_capability:
            self.orchestrator.voice_capability._audio_buffer.clear()
            self.orchestrator.voice_capability.vad.reset()
            self.orchestrator.voice_capability._listening_start_time = 0.0
            if hasattr(self.orchestrator.voice_capability.wakeword, "reset"):
                self.orchestrator.voice_capability.wakeword.reset()
        await self.orchestrator.fsm.force_transition_to(FSMState.IDLE)
        return web.json_response({"status": "listening_stopped"})

    async def _handle_interrupt(self, request: web.Request) -> web.Response:
        logger.info("Web dashboard triggered barge-in interrupt.")
        current_state = self.orchestrator.fsm.state
        if current_state == FSMState.IDLE:
            logger.info("Assistant is in IDLE state. Ignoring interrupt request.")
            return web.json_response({"status": "ignored", "reason": "IDLE state"})

        await self.orchestrator.cancel()
        if self.orchestrator.voice_capability:
            self.orchestrator.voice_capability._seed_audio_buffer_from_preroll()
            self.orchestrator.voice_capability.vad.reset()

        if current_state == FSMState.SPEAKING:
            import time
            if self.orchestrator.voice_capability:
                self.orchestrator.voice_capability._listening_start_time = time.perf_counter()
            await self.orchestrator.fsm.transition_to(FSMState.LISTENING)
        else:
            await self.orchestrator.fsm.force_transition_to(FSMState.IDLE)

        return web.json_response({"status": "interrupted"})

    async def _handle_simulate_voice(self, request: web.Request) -> web.Response:
        data = await request.json()
        prompt = data.get("prompt", "")
        if prompt and self.orchestrator.voice_capability:
            logger.info(f"Web dashboard submitted prompt: '{prompt}'")
            # Cancel active audio synthesis/generation before starting new prompt
            await self.orchestrator.cancel()
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

    async def _handle_get_settings(self, request: web.Request) -> web.Response:
        silence_ms = getattr(self.orchestrator.config.vad, "silence_duration_ms", 1800)
        provider = getattr(self.orchestrator.config.tts, "provider", "kokoro")
        voice = getattr(self.orchestrator.config.tts, "voice", "af_bella")
        speed = getattr(self.orchestrator.config.tts, "speed", 1.15)
        cfg_weight = getattr(self.orchestrator.config.tts, "cfg_weight", 0.5)
        exaggeration = getattr(self.orchestrator.config.tts, "exaggeration", 0.5)
        enable_fallback = getattr(self.orchestrator.config.tts, "enable_fallback", False)
        fallback_provider = getattr(self.orchestrator.config.tts, "fallback_provider", "edge_tts")
        policy_mode = getattr(self.orchestrator.tools_config, "policy_mode", "PERMISSIVE")
        return web.json_response({
            "silence_duration_ms": silence_ms,
            "tts_provider": provider,
            "tts_voice": voice,
            "tts_speed": speed,
            "tts_cfg_weight": cfg_weight,
            "tts_exaggeration": exaggeration,
            "tts_enable_fallback": enable_fallback,
            "tts_fallback_provider": fallback_provider,
            "policy_mode": policy_mode,
        })

    async def _handle_update_settings(self, request: web.Request) -> web.Response:
        data = await request.json()
        silence_ms = data.get("silence_duration_ms")
        tts_provider = data.get("tts_provider")
        tts_voice = data.get("tts_voice")
        tts_speed = data.get("tts_speed")
        tts_cfg_weight = data.get("tts_cfg_weight")
        tts_exaggeration = data.get("tts_exaggeration")
        tts_enable_fallback = data.get("tts_enable_fallback")
        tts_fallback_provider = data.get("tts_fallback_provider")
        policy_mode = data.get("policy_mode")

        updated = self.orchestrator.update_settings(
            silence_duration_ms=silence_ms,
            tts_provider=tts_provider,
            tts_voice=tts_voice,
            tts_speed=tts_speed,
            tts_cfg_weight=tts_cfg_weight,
            tts_exaggeration=tts_exaggeration,
            tts_enable_fallback=tts_enable_fallback,
            tts_fallback_provider=tts_fallback_provider,
            policy_mode=policy_mode,
        )

        return web.json_response({
            "status": "updated",
            "settings": updated,
        })

    async def _handle_health(self, request: web.Request) -> web.Response:
        health = await self.orchestrator.health()
        return web.json_response({
            "status": health.status.value,
            "message": health.message,
            "details": health.details,
        })

    async def _handle_metrics(self, request: web.Request) -> web.Response:
        metrics = self.orchestrator.observability.get_metrics_summary()
        return web.json_response(metrics)

    async def _handle_list_tools(self, request: web.Request) -> web.Response:
        tools_list = []
        if hasattr(self.orchestrator, "tool_registry") and self.orchestrator.tool_registry:
            for spec, _ in self.orchestrator.tool_registry.list_tools():
                tools_list.append({
                    "name": spec.manifest.name,
                    "version": spec.manifest.version,
                    "description": spec.manifest.description,
                    "permission_level": spec.manifest.permission_level.value,
                    "read_only": spec.manifest.read_only,
                    "parameters_schema": spec.parameters_schema,
                })
        return web.json_response({"tools": tools_list, "total": len(tools_list)})

    async def _handle_execute_tool(self, request: web.Request) -> web.Response:
        data = await request.json()
        tool_name = data.get("tool_name")
        params = data.get("params", {})
        if not tool_name:
            return web.json_response({"status": "error", "message": "Missing tool_name"}, status=400)

        if not hasattr(self.orchestrator, "tool_runner") or not self.orchestrator.tool_runner:
            return web.json_response({"status": "error", "message": "Tool execution platform unavailable"}, status=503)

        from jarvis.tools.schemas import ToolCall
        import uuid
        call = ToolCall(call_id=f"manual_{uuid.uuid4().hex[:8]}", tool_name=tool_name, params=params)
        pair = self.orchestrator.tool_registry.get_tool(tool_name)
        if not pair:
            return web.json_response({"status": "error", "message": f"Tool '{tool_name}' not found"}, status=444)
        spec, adapter = pair
        res = await self.orchestrator.tool_runner.execute_call(call, spec, adapter)
        res_data = getattr(res, "data", getattr(res, "result", None))
        return web.json_response({
            "call_id": res.call_id,
            "tool_name": res.tool_name,
            "success": res.success,
            "result": res_data,
            "error": res.error.message if res.error else None,
            "execution_time_ms": res.execution_time_ms,
        })

    async def _handle_list_capabilities(self, request: web.Request) -> web.Response:
        caps = self.orchestrator.capability_registry.list_capabilities()
        return web.json_response({"capabilities": caps, "total": len(caps)})

    async def _handle_get_agent_state(self, request: web.Request) -> web.Response:
        state = self.orchestrator.fsm.state.value if self.orchestrator.fsm else "IDLE"
        return web.json_response({"fsm_state": state})

    async def _handle_respond_approval(self, request: web.Request) -> web.Response:
        data = await request.json() if request and request.can_read_body else {}
        req_id = data.get("request_id", "default")
        approved = data.get("approved", True)
        logger.info(f"Human approval response for {req_id}: approved={approved}")
        return web.json_response({"status": "acknowledged", "request_id": req_id, "approved": approved})

    async def start(self) -> None:
        """Start the HTTP server site."""
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self.port)
        await site.start()
        logger.info(f"Jarvis web dashboard active at http://localhost:{self.port}")

    async def stop(self) -> None:
        """Stop and cleanup HTTP server runner."""
        if self._runner:
            await self._runner.cleanup()

