"""
Finite state machine (VoiceFSM) managing voice assistant lifecycle states.
"""

import asyncio
import logging
from enum import Enum
from typing import Awaitable, Callable, Dict, List

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
    Thread-safe asynchronous state machine enforcing valid state transition paths
    for the voice pipeline.
    """

    ALLOWED_TRANSITIONS: Dict[FSMState, List[FSMState]] = {
        FSMState.STARTING: [FSMState.IDLE, FSMState.ERROR, FSMState.STOPPING],
        FSMState.IDLE: [
            FSMState.WAKE_DETECTED,
            FSMState.LISTENING,
            FSMState.TRANSCRIBING,
            FSMState.THINKING,
            FSMState.ERROR,
            FSMState.STOPPING,
        ],
        FSMState.WAKE_DETECTED: [
            FSMState.LISTENING,
            FSMState.THINKING,
            FSMState.TRANSCRIBING,
            FSMState.SPEAKING,
            FSMState.IDLE,
            FSMState.ERROR,
            FSMState.STOPPING,
        ],
        FSMState.LISTENING: [
            FSMState.TRANSCRIBING,
            FSMState.THINKING,
            FSMState.SPEAKING,
            FSMState.IDLE,
            FSMState.ERROR,
            FSMState.STOPPING,
        ],
        FSMState.TRANSCRIBING: [
            FSMState.THINKING,
            FSMState.SPEAKING,
            FSMState.IDLE,
            FSMState.ERROR,
            FSMState.STOPPING,
        ],
        FSMState.THINKING: [
            FSMState.SPEAKING,
            FSMState.LISTENING,
            FSMState.IDLE,
            FSMState.ERROR,
            FSMState.STOPPING,
        ],
        FSMState.SPEAKING: [
            FSMState.IDLE,
            FSMState.LISTENING,
            FSMState.ERROR,
            FSMState.STOPPING,
        ],
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
        """Register a callback to be notified on state changes (from_state, to_state)."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    async def transition_to(self, target_state: FSMState) -> bool:
        """Attempt an atomic state transition to target_state."""
        async with self._lock:
            current = self._state
            if current == target_state:
                return True

            allowed = self.ALLOWED_TRANSITIONS.get(current, [])
            if target_state not in allowed:
                logger.warning(
                    f"Invalid FSM state transition requested: {current.value} -> {target_state.value}"
                )
                return False

            self._state = target_state
            logger.info(f"[FSM] Transition: {current.value} -> {target_state.value}")

        for cb in self._callbacks:
            try:
                await cb(current, target_state)
            except Exception as e:
                logger.error(f"FSM state notification callback exception: {e}", exc_info=True)

        return True

    async def initialize(self) -> bool:
        self._status = ServiceStatus.RUNNING
        await self.transition_to(FSMState.IDLE)
        return True

    async def health(self) -> HealthStatus:
        return HealthStatus(
            status=self._status,
            message=f"Current state: {self._state.value}",
            details={"state": self._state.value},
        )

    async def shutdown(self) -> None:
        await self.transition_to(FSMState.STOPPING)
        self._status = ServiceStatus.STOPPED

    async def cancel(self) -> None:
        """Reset state upon task cancellation or user interruption."""
        if self._state == FSMState.SPEAKING:
            await self.transition_to(FSMState.LISTENING)
        elif self._state in (FSMState.LISTENING, FSMState.TRANSCRIBING, FSMState.THINKING):
            await self.transition_to(FSMState.IDLE)

