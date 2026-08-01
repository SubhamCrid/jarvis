"""
Application configuration schema definitions using Pydantic validation models.
"""

from pydantic import BaseModel, Field


class SystemConfig(BaseModel):
    environment: str = Field(default="default")
    log_level: str = Field(default="INFO")
    data_dir: str = Field(default="data")


class AudioConfig(BaseModel):
    sample_rate: int = Field(default=16000)
    channels: int = Field(default=1)
    chunk_size: int = Field(default=1024)
    buffer_queue_size: int = Field(default=50)
    speaker_sample_rate: int = Field(default=22050)


class WakeWordConfig(BaseModel):
    provider: str = Field(default="openwakeword")
    model_name: str = Field(default="hey_jarvis")
    threshold: float = Field(default=0.5)
    sample_rate: int = Field(default=16000)


class VADConfig(BaseModel):
    energy_threshold: float = Field(default=0.02)
    silence_duration_ms: int = Field(default=1800)
    speech_pad_ms: int = Field(default=300)


class STTConfig(BaseModel):
    provider: str = Field(default="whisper_cpp")
    model: str = Field(default="base")
    language: str = Field(default="auto")
    device: str = Field(default="auto")
    compute_type: str = Field(default="int8")
    cloud_fallback: bool = Field(default=False)


class LLMConfig(BaseModel):
    provider: str = Field(default="ollama")
    model: str = Field(default="qwen3.5:4b")
    temperature: float = Field(default=0.7)
    max_tokens: int = Field(default=1024)
    stream: bool = Field(default=True)
    system_prompt: str = Field(
        default="You are Jarvis, a powerful local voice assistant equipped with workspace file system tools (reading, writing, listing, searching files) and command execution capabilities. Keep all responses brief (1 to 2 sentences maximum), clear, and natural for speech synthesis."
    )


class TTSConfig(BaseModel):
    provider: str = Field(default="kokoro")
    voice: str = Field(default="af_bella")
    speaker_id: int = Field(default=0)
    speed: float = Field(default=1.15)
    auto_switch_voice: bool = Field(default=False)
    chunk_queue_size: int = Field(default=20)


class SessionConfig(BaseModel):
    max_history_turns: int = Field(default=0)
    save_audio_logs: bool = Field(default=False)


class ObservabilityConfig(BaseModel):
    enable_metrics: bool = Field(default=True)
    enable_timeline: bool = Field(default=True)


class AppConfig(BaseModel):
    version: str = Field(default="1.0")
    system: SystemConfig = Field(default_factory=SystemConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    wakeword: WakeWordConfig = Field(default_factory=WakeWordConfig)
    vad: VADConfig = Field(default_factory=VADConfig)
    stt: STTConfig = Field(default_factory=STTConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)

