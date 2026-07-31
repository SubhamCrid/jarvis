"""
Unit tests for VoiceFSM state machine and barge-in state transitions.
"""

import pytest
from vidya.core.fsm import VoiceFSM, FSMState


@pytest.mark.asyncio
async def test_fsm_valid_transitions():
    fsm = VoiceFSM()
    assert fsm.state == FSMState.STARTING

    await fsm.initialize()
    assert fsm.state == FSMState.IDLE

    assert await fsm.transition_to(FSMState.WAKE_DETECTED)
    assert fsm.state == FSMState.WAKE_DETECTED

    assert await fsm.transition_to(FSMState.LISTENING)
    assert fsm.state == FSMState.LISTENING

    assert await fsm.transition_to(FSMState.TRANSCRIBING)
    assert fsm.state == FSMState.TRANSCRIBING

    assert await fsm.transition_to(FSMState.THINKING)
    assert fsm.state == FSMState.THINKING

    assert await fsm.transition_to(FSMState.SPEAKING)
    assert fsm.state == FSMState.SPEAKING

    assert await fsm.transition_to(FSMState.IDLE)
    assert fsm.state == FSMState.IDLE


@pytest.mark.asyncio
async def test_fsm_barge_in_transition():
    fsm = VoiceFSM()
    await fsm.initialize()
    await fsm.transition_to(FSMState.WAKE_DETECTED)
    await fsm.transition_to(FSMState.LISTENING)
    await fsm.transition_to(FSMState.TRANSCRIBING)
    await fsm.transition_to(FSMState.THINKING)
    await fsm.transition_to(FSMState.SPEAKING)

    # Barge-in cancel: SPEAKING -> LISTENING
    await fsm.cancel()
    assert fsm.state == FSMState.LISTENING


@pytest.mark.asyncio
async def test_fsm_invalid_transition():
    fsm = VoiceFSM()
    await fsm.initialize()  # Now in IDLE
    
    # IDLE -> SPEAKING directly is invalid
    success = await fsm.transition_to(FSMState.SPEAKING)
    assert not success
    assert fsm.state == FSMState.IDLE
