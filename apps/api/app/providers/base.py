from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class TranscriptResult:
    text: str
    confidence: float


class STTProvider(Protocol):
    async def transcribe_stream(self, audio_chunk: bytes) -> TranscriptResult: ...


class TTSProvider(Protocol):
    async def synthesize(self, text: str) -> bytes: ...


class TelephonyProvider(Protocol):
    async def transfer(self, call_id: str, destination: str) -> bool: ...


class LLMProvider(Protocol):
    async def respond_structured(self, state: dict) -> dict: ...
