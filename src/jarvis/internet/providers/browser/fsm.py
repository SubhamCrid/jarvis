"""
BrowserState FSM for explicit browser runtime supervisor state tracking.
States: STARTING -> READY -> BUSY -> DEGRADED -> RECOVERING -> STOPPED -> FAILED.
"""

from enum import Enum


class BrowserState(str, Enum):
    STARTING = "STARTING"
    READY = "READY"
    BUSY = "BUSY"
    DEGRADED = "DEGRADED"
    RECOVERING = "RECOVERING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
