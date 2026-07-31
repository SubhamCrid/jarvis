"""
CLI entry point and runtime runner for Vidya local voice assistant engine and web dashboard.
"""

import argparse
import asyncio
import logging
import signal
import sys
from typing import Optional

from vidya.core.config.loader import load_config
from vidya.orchestrator import AssistantOrchestrator
from vidya.utils.logger import setup_logger
from vidya.web.server import WebDashboardServer

logger = logging.getLogger("vidya.main")


async def run_assistant(config_file: Optional[str] = None, port: int = 8000) -> None:
    """Initialize and run the voice assistant service alongside the web dashboard."""
    config = load_config()
    setup_logger(log_level=config.system.log_level, log_dir=f"{config.system.data_dir}/logs")

    orchestrator = AssistantOrchestrator(config)
    if not await orchestrator.initialize():
        logger.error("Failed to initialize Vidya Assistant orchestrator.")
        return

    web_server = WebDashboardServer(orchestrator, port=port)
    await web_server.start()

    print("\n" + "=" * 60)
    print("  VIDYA LOCAL VOICE ASSISTANT ENGINE")
    print(f"  Web Dashboard Active at: http://localhost:{port}")
    print(f"  Listening for wake word: '{config.wakeword.model_name}'")
    print("=" * 60 + "\n")

    stop_event = asyncio.Event()

    def signal_handler() -> None:
        logger.info("Termination signal received. Initiating graceful shutdown...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            pass

    await orchestrator.start()

    try:
        await stop_event.wait()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received.")
    finally:
        await web_server.stop()
        await orchestrator.shutdown()
        logger.info("Vidya desktop assistant stopped cleanly.")


async def run_health_check() -> None:
    """Perform diagnostic health evaluation of orchestrator providers and capabilities."""
    config = load_config()
    setup_logger(log_level="INFO", log_dir=f"{config.system.data_dir}/logs")

    logger.info("Running Vidya system health check...")
    orchestrator = AssistantOrchestrator(config)
    await orchestrator.initialize()

    health = await orchestrator.health()
    print("\n" + "=" * 50)
    print(f"VIDYA SYSTEM HEALTH: {health.status.value.upper()}")
    print(f"Message: {health.message}")
    print("Details:")
    for k, v in health.details.items():
        print(f"  - {k}: {v}")
    print("=" * 50 + "\n")

    await orchestrator.shutdown()


async def run_pipeline_test() -> None:
    """Execute a synthetic end-to-end voice processing test."""
    config = load_config(user_overrides={"system": {"environment": "test"}})
    setup_logger(log_level="INFO", log_dir=f"{config.system.data_dir}/logs")

    logger.info("Executing synthetic voice pipeline verification...")
    orchestrator = AssistantOrchestrator(config)
    await orchestrator.initialize()

    dummy_pcm = b"\x7f\x3f" * 512
    result = await orchestrator.process_task(
        session_id="test_cli_sess",
        task_type="voice_interaction",
        payload={"pcm_data": dummy_pcm},
    )

    print("\n" + "=" * 50)
    print(f"PIPELINE TEST RESULT: {result}")
    metrics = orchestrator.observability.get_metrics_summary()
    print("METRICS SUMMARY:")
    for metric_name, data in metrics.items():
        print(f"  - {metric_name}: {data}")
    print("=" * 50 + "\n")

    await orchestrator.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser(description="Vidya Local Voice Assistant Engine")
    subparsers = parser.add_subparsers(dest="command", help="Sub-command to run")

    run_parser = subparsers.add_parser("run", help="Run active voice assistant with Web UI")
    run_parser.add_argument("--config", type=str, help="Path to config file")
    run_parser.add_argument("--port", type=int, default=8000, help="Web UI port (default: 8000)")

    ui_parser = subparsers.add_parser("ui", help="Launch Web UI Dashboard")
    ui_parser.add_argument("--port", type=int, default=8000, help="Web UI port (default: 8000)")

    subparsers.add_parser("check-health", help="Run system health checks")
    subparsers.add_parser("test-pipeline", help="Run synthetic pipeline test")

    args = parser.parse_args()
    command = args.command or "run"

    try:
        if command in ("run", "ui"):
            port = getattr(args, "port", 8000)
            asyncio.run(run_assistant(getattr(args, "config", None), port=port))
        elif command == "check-health":
            asyncio.run(run_health_check())
        elif command == "test-pipeline":
            asyncio.run(run_pipeline_test())
    except KeyboardInterrupt:
        logger.info("Vidya desktop assistant shutdown completed via KeyboardInterrupt.")
        sys.exit(0)


if __name__ == "__main__":
    main()


