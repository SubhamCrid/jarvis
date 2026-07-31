"""
Vidya CLI Entry Point and Application Bootstrap.
"""

import sys
import asyncio
import signal
import argparse
import logging
from typing import Optional

from vidya.utils.logger import setup_logger
from vidya.core.config.loader import load_config
from vidya.orchestrator import AssistantOrchestrator

logger = logging.getLogger("vidya.main")


async def run_assistant(config_file: Optional[str] = None) -> None:
    """Run Vidya desktop voice assistant."""
    config = load_config()
    setup_logger(log_level=config.system.log_level, log_dir=f"{config.system.data_dir}/logs")
    
    orchestrator = AssistantOrchestrator(config)
    if not await orchestrator.initialize():
        logger.error("Failed to initialize Vidya Orchestrator.")
        return

    stop_event = asyncio.Event()

    def signal_handler():
        logger.info("Shutdown signal received (SIGINT/SIGTERM). Stopping Vidya...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            # Signal handling on Windows event loop fallback
            pass

    await orchestrator.start()

    try:
        await stop_event.wait()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received.")
    finally:
        await orchestrator.shutdown()
        logger.info("Vidya desktop assistant stopped gracefully.")


async def run_health_check() -> None:
    """Run diagnostic health checks on all registered providers and capabilities."""
    config = load_config()
    setup_logger(log_level="INFO", log_dir=f"{config.system.data_dir}/logs")
    
    logger.info("Running Vidya System Health Check...")
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
    """Run synthetic end-to-end voice pipeline test."""
    config = load_config(user_overrides={"system": {"environment": "test"}})
    setup_logger(log_level="INFO", log_dir=f"{config.system.data_dir}/logs")

    logger.info("Running Vidya Synthetic Voice Pipeline Test...")
    orchestrator = AssistantOrchestrator(config)
    await orchestrator.initialize()

    dummy_pcm = (b"\x7f\x3f" * 512)
    result = await orchestrator.process_task(
        session_id="test_cli_sess",
        task_type="voice_interaction",
        payload={"pcm_data": dummy_pcm}
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
    parser = argparse.ArgumentParser(description="Vidya Local-First Desktop Voice Assistant")
    subparsers = parser.add_subparsers(dest="command", help="Sub-command to run")

    run_parser = subparsers.add_parser("run", help="Run active voice assistant")
    run_parser.add_argument("--config", type=str, help="Path to config file")

    health_parser = subparsers.add_parser("check-health", help="Run system health checks")
    test_parser = subparsers.add_parser("test-pipeline", help="Run synthetic pipeline test")

    args = parser.parse_args()

    command = args.command or "run"

    if command == "run":
        asyncio.run(run_assistant(args.config))
    elif command == "check-health":
        asyncio.run(run_health_check())
    elif command == "test-pipeline":
        asyncio.run(run_pipeline_test())


if __name__ == "__main__":
    main()
