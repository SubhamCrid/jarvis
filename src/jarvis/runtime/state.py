"""
Deterministic execution state machine for Agent Runtime Platform.
"""

from typing import Dict, Set
from jarvis.runtime.schemas import ExecutionState


class StateMachineError(Exception):
    pass


class RuntimeStateMachine:
    """
    State machine enforcing valid, deterministic transitions across all 12 execution states.
    """

    ALLOWED_TRANSITIONS: Dict[ExecutionState, Set[ExecutionState]] = {
        ExecutionState.CREATED: {ExecutionState.PLANNED, ExecutionState.QUEUED, ExecutionState.CANCELLED},
        ExecutionState.PLANNED: {ExecutionState.QUEUED, ExecutionState.RUNNING, ExecutionState.CANCELLED},
        ExecutionState.QUEUED: {ExecutionState.RUNNING, ExecutionState.PAUSED, ExecutionState.CANCELLED},
        ExecutionState.RUNNING: {
            ExecutionState.WAITING_APPROVAL,
            ExecutionState.WAITING_EVENT,
            ExecutionState.PAUSED,
            ExecutionState.COMPLETED,
            ExecutionState.FAILED,
            ExecutionState.CANCELLED,
            ExecutionState.ROLLING_BACK,
        },
        ExecutionState.WAITING_APPROVAL: {
            ExecutionState.RUNNING,
            ExecutionState.CANCELLED,
            ExecutionState.FAILED,
        },
        ExecutionState.WAITING_EVENT: {
            ExecutionState.RUNNING,
            ExecutionState.CANCELLED,
            ExecutionState.FAILED,
        },
        ExecutionState.PAUSED: {ExecutionState.RUNNING, ExecutionState.CANCELLED},
        ExecutionState.COMPLETED: set(),
        ExecutionState.FAILED: {ExecutionState.ROLLING_BACK, ExecutionState.QUEUED},
        ExecutionState.CANCELLED: {ExecutionState.ROLLING_BACK},
        ExecutionState.ROLLING_BACK: {ExecutionState.ROLLED_BACK, ExecutionState.FAILED},
        ExecutionState.ROLLED_BACK: set(),
    }

    def __init__(self, initial_state: ExecutionState = ExecutionState.CREATED) -> None:
        self._current_state = initial_state

    @property
    def current_state(self) -> ExecutionState:
        return self._current_state

    def can_transition_to(self, target_state: ExecutionState) -> bool:
        return target_state in self.ALLOWED_TRANSITIONS.get(self._current_state, set())

    def transition_to(self, target_state: ExecutionState) -> ExecutionState:
        if not self.can_transition_to(target_state):
            raise StateMachineError(
                f"Invalid state transition from '{self._current_state.value}' to '{target_state.value}'"
            )
        self._current_state = target_state
        return self._current_state
