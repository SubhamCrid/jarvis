# Jarvis - Local-First Desktop Voice Assistant Engine

**Jarvis** is a low-latency, modular, local-first desktop voice assistant framework optimized for low VRAM (6 GB VRAM target). It features an always-on wake word detector ("Jarvis"), finite-state machine (FSM) voice pipeline, instantaneous **barge-in / interruption** support, streaming STT/LLM/TTS, unified session persistence, typed message bus, task executor, capability registry, and focused performance observability.

---

## Key Architectural Features

- **Central Orchestrator Pattern (`AssistantOrchestrator`)**: Thin coordinator handling component initialization, dependency wiring, service lifecycle, and request delegation.
- **TaskExecutor & Planner (`TaskManager`, `Planner`, `TaskExecutor`)**: Structured task lifecycle (`User → Task → Planner → Plan → TaskExecutor → Capability → Provider`) with retries, timeouts, and active cancellation.
- **Finite State Machine (`VoiceFSM`)**: Manages states `STARTING → IDLE → WAKE_DETECTED → LISTENING → TRANSCRIBING → THINKING → SPEAKING → ERROR → STOPPING` with instant barge-in transition (`SPEAKING` + user speech → `LISTENING`).
- **Exclusive Audio Resource Owner (`AudioSessionManager`)**: Single owner of hardware microphone input and speaker output streams with streaming backpressure over bounded queues (`BoundedQueue`).
- **Pluggable Low-Footprint Providers**:
  - **STT**: Default to `whisper.cpp` (`WhisperCppSTT`), with optional `faster-whisper`, cloud `OpenAI`, and `MockSTT`.
  - **TTS**: Default to 100% local `Piper` neural TTS (`PiperTTS`), with optional `EdgeTTS`, cloud `OpenAI`, and `MockTTS`.
  - **LLM**: Direct pluggable `LLMProtocol` supporting `OllamaLLM`, `LlamaCppLLM`, `OpenAILLM`, `GroqLLM`, and `MockLLM`.
  - **Wake Word**: `OpenWakeWordProvider` and `MockWakeWord`.
- **Capability & Tool Abstraction (`CapabilityRegistry`, `ToolProtocol`)**: Voice capabilities implemented via `VoiceAssistantCapability`, with placeholder contracts ready for future expansion (`BrowserCapability`, `DesktopCapability`).
- **Unified Session Store (`SQLiteSessionStore`)**: Persists conversation history, turns, task states, metrics, and recordings in `data/sessions/jarvis.db`.
- **Focused Observability (`ObservabilityService`)**: Tracks operational latencies (`wake_latency`, `stt_latency`, `ttft`, `tts_first_audio`, `total_response_latency`) and cancellation counts.

---

## Directory Structure

```
jarvis/
├── config/
│   ├── default.yaml           # Base default configuration (version: 1.0)
│   ├── development.yaml       # Development overrides
│   ├── production.yaml        # Production overrides
│   └── user.yaml.example      # Example local user overrides
├── data/                      # Local database & audio storage
│   ├── sessions/              # SQLite session DBs
│   ├── logs/                  # Rotating log files
│   └── models/                # Downloaded model files (whisper.cpp, Piper)
├── src/
│   └── jarvis/
│       ├── orchestrator.py    # Thin AssistantOrchestrator
│       ├── core/              # Framework Foundation (MessageBus, FSM, TaskManager, Planner, Executor, Observability, Config)
│       ├── providers/         # Swappable Service Providers (STT, LLM, TTS, WakeWord, AudioSession, SessionStore)
│       ├── capabilities/      # Domain Capabilities (VoiceAssistantCapability, Browser/Desktop placeholders)
│       └── utils/             # Logging & BoundedQueue Async Utilities
└── tests/
    └── unit/                  # Automated Pytest Suite
```

---

## Quick Start

### 1. Installation

Install Jarvis in editable mode:
```bash
pip install -e .
```

### 2. Configuration

Hierarchy: `default.yaml` → `development.yaml` / `production.yaml` → `user.yaml` → Environment Variables (`JARVIS_*`).

Copy the example configuration to customize local providers:
```bash
cp config/user.yaml.example config/user.yaml
```

Environment variable override example:
```bash
export JARVIS_LLM__MODEL="llama3.2:3b"
```

### 3. CLI Commands

- **Run Synthetic Pipeline Test**:
  ```bash
  python -m jarvis.main test-pipeline
  ```

- **Check System Health**:
  ```bash
  python -m jarvis.main check-health
  ```

- **Run Active Voice Assistant**:
  ```bash
  python -m jarvis.main run
  ```

---

## Running Automated Tests

Run the full unit and integration test suite:
```bash
pytest tests/ -v
```

All 34 unit and integration tests verify configuration, MessageBus event schemas, FSM state transitions, audio session barge-in, session store persistence, streaming chunkers, TaskExecutor retries/cancellation, and end-to-end voice processing.
