# Jarvis Modular Tool Execution Platform Architecture

This document defines the production-grade, modular, model-agnostic, low-VRAM (<6GB) tool execution platform for the local AI assistant "Jarvis".

## 1. Core Principles

- **Model Agnosticism**: Core tool runtime (`src/jarvis/tools/`) has ZERO dependencies on LLM provider formats (Ollama, OpenAI, Anthropic, etc.).
- **Decoupled Schema Exporters**: Provider formatting logic is isolated in `src/jarvis/tools/exporters/` (`OllamaSchemaExporter`, `OpenAISchemaExporter`, `XMLPromptExporter`).
- **Backend Adapter Isolation**: Execution capabilities reside exclusively in modular adapters (`src/jarvis/tools/adapters/`).
- **Strict Path Sandboxing**: All file tools enforce `PathSandbox` canonicalization (`Path.resolve()`), root confinement checks, and symlink/traversal prevention.
- **`argv` Command Safety**: Shell tools execute via `execv` array (`shell=False`), command whitelisting, strict working directory sandbox, and environment variable sanitization.
- **Cancellation & Process Cleanup**: `CancellationToken` support ensures subprocesses (`proc.terminate()` -> `proc.kill()`) and async tasks abort cleanly during voice barge-in or stop signals.
- **Secret-Aware Redaction**: `OutputRedactor` filters API keys, passwords, and private tokens before results reach logs, traces, or LLM prompts.
- **Resource Lock Management**: `ResourceLockManager` enforces per-path `asyncio.Lock` to prevent parallel file write races.
- **Structured Audit Persistence**: `ToolStore` persists `AuditEvent` records into SQLite for historical replay, debugging, and offline security audits.
- **Telemetry & Health Monitoring**: `ToolHealthCheck` exposes failure rates, lock contention, tool manifests, and degraded mode indicators.

---

## 2. Directory Structure

```
src/jarvis/tools/
├── __init__.py              # Package entry point
├── config.py                # ToolsConfig (runtime settings, sandboxing, timeouts, redaction rules)
├── schemas.py               # Typed contracts (ToolSpec, ToolManifest, ToolCall, ToolResult, ToolError, AuditEvent, PermissionLevel, StepState)
├── policy.py                # ToolPolicyEngine (permission level checks, argv safety rules, path safety checks)
├── sandbox.py               # PathSandbox (path normalization, symlink resolution, root confinement)
├── redactor.py              # OutputRedactor (secret scrubbing for logs, results, and LLM context)
├── concurrency.py           # ResourceLockManager (per-resource file locks, execution concurrency caps)
├── tracer.py                # ToolTracer (event tracking and execution telemetry)
├── persistence.py           # ToolStore (persists tool calls, traces, policy decisions to SQLite)
├── health.py                # ToolHealthCheck (monitors tool health, lock contention, failure rates)
├── validator.py             # ToolValidator (Pydantic parameter schema validation)
├── normalizer.py            # ToolNormalizer (standardized ToolError formatting)
├── runner.py                # ToolRunner (orchestrates execution, CancellationToken, process cleanup)
├── registry.py              # Pure ToolRegistry (version-aware tool registration and adapter lookup)
├── capability.py            # ToolsCapability (wrapper integrating tools into CapabilityRegistry)
├── exporters/               # Model-Agnostic LLM Schema Exporters
│   ├── base.py              # BaseSchemaExporter interface
│   ├── ollama.py            # OllamaSchemaExporter
│   ├── openai.py            # OpenAISchemaExporter
│   └── xml_prompt.py        # XMLPromptExporter (for 3B local quantized LLMs)
└── adapters/                # Modular Plug-and-Play Backend Adapters
    ├── base.py              # BaseToolAdapter interface
    ├── file_tools.py        # ReadFileTool, WriteFileTool, ListDirectoryTool, SearchFilesTool
    └── shell_tools.py       # RunCommandSafeTool (argv-based execution)
```

---

## 3. Initial Built-in Tools

- `read_file`: Safe file read with path sandboxing and line range filtering.
- `write_file`: Gated file write with parent directory auto-creation and path sandboxing.
- `list_directory`: Folder listing with file size and type details.
- `search_files`: Glob pattern search constrained within workspace bounds.
- `run_command_safe`: Subprocess `argv` execution (`shell=False`), executable whitelist, sanitized environment, timeout, and output capping.

---

## 4. Verification

The tool platform is verified via comprehensive Pytest unit tests in `tests/unit/test_tools.py` covering path traversal attacks, command injection attempts, cancellation signals, secret redaction, schema exporters, and orchestrator integration.
