"""
Voice Finite State Machine (VoiceFSM) for Vidya Assistant.
"""

import asyncio
import logging
from enum import Enum
from typing import Callable, Awaitable, List, Dict, Optional, Any
from vidya.core.base import BaseServiceProtocol, HealthStatus, ServiceStatus

logger = logging.getLogger("vidya.core.fsm")


class FSMState(str, Enum):
    STARTING = "STARTING"
    IDLE = "IDLE"
    WAKE_DETECTED = "WAKE_DETECTED"
    LISTENING = "LISTENING"
    TRANSCRIBING = "TRANSCRIBING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    ERROR = "ERROR"
    STOPPING = "STOPPING"


StateCallback = Callable[[FSMState, FSMState], Awaitable[None]]


class VoiceFSM(BaseServiceProtocol):
    """
    Thread-safe, async state machine managing voice assistant lifecycle and state transitions.
    States: STARTING -> IDLE -> WAKE_DETECTED -> LISTENING -> TRANSCRIBING -> THINKING -> SPEAKING -> IDLE
    Supports instantaneous barge-in: (SPEAKING + speech_detected -> LISTENING).
    """

    # Allowed state transition matrix
    ALLOWED_TRANSITIONS: Dict[FSMState, List[FSMState]] = {
        FSMState.STARTING: [FSMState.IDLE, FSMState.ERROR, FSMState.STOPPING],
        FSMState.IDLE: [FSMState.WAKE_DETECTED, FSMState.LISTENING, FSMState.TRANSCRIBING, FSMState.THINKING, FSMState.ERROR, FSMState.STOPPING],
        FSMState.WAKE_DETECTED: [FSMState.LISTENING, FSMState.IDLE, FSMState.ERROR, FSMState.STOPPING],
        FSMState.LISTENING: [FSMState.TRANSCRIBING, FSMState.IDLE, FSMState.ERROR, FSMState.STOPPING],
        FSMState.TRANSCRIBING: [FSMState.THINKING, FSMState.IDLE, FSMState.ERROR, FSMState.STOPPING],
        FSMState.THINKING: [FSMState.SPEAKING, FSMState.IDLE, FSMState.ERROR, FSMState.STOPPING],
        FSMState.SPEAKING: [FSMState.IDLE, FSMState.LISTENING, FSMState.ERROR, FSMState.STOPPING],
        FSMState.ERROR: [FSMState.IDLE, FSMState.STOPPING],
        FSMState.STOPPING: [FSMState.STOPPING],
    }

    def __init__(self) -> None:
        self._state: FSMState = FSMState.STARTING
        self._lock = asyncio.Lock()
        self._callbacks: List[StateCallback] = []
        self._status: ServiceStatus = ServiceStatus.UNINITIALIZED

    @property
    def state(self) -> FSMState:
        return self._state

    def add_state_callback(self, callback: StateCallback) -> None:
        """Register callback for state transition notifications (from_state, to_state)."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    async def transition_to(self, target_state: FSMState) -> bool:
        """Attempt atomic transition to target_state."""
        async with self._lock:
            current = self._state
            if current == target_state:
                return True

            allowed = self.ALLOWED_TRANSITIONS.get(current, [])
            if target_state not in allowed:
                logger.warning(f"Invalid FSM transition: {current.value} -> {target_state.value}")
                return False

            self._state = target_state
            logger.info(f"[FSM] State transition: {current.value} -> {target_state.value}")

        # Notify callbacks outside lock
        for cb in self._callbacks:
            try:
                await cb(current, target_state)
            except Exception as e:
                logger.error(f"Error in FSM callback: {e}", exc_info=True)

        return True

    async def initialize(self) -> bool:
        self._status = ServiceStatus.RUNNING
        await self.transition_to(FSMState.IDLE)
        return True

    async def health(self) -> HealthStatus:
        return HealthStatus(
            status=self._status,
            message=f"Current state: {self._state.value}",
            details={"state": self._state.value}
        )

    async def shutdown(self) -> None:
        await self.transition_to(FSMState.STOPPING)
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        """On cancel / interruption, transition directly back to IDLE or LISTENING."""
        if self._state == FSMState.SPEAKING:
            await self.transition_to(FSMState.LISTENING)
        elif self._state in (FSMState.LISTENING, FSMState.TRANSCRIBING, FSMState.THINKING):
            await self.transition_to(FSMState.IDLE)
