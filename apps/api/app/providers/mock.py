from app.providers.base import TranscriptResult


class MockSTT:
    async def transcribe_stream(self, audio_chunk: bytes) -> TranscriptResult:
        return TranscriptResult(text="Synthetic local transcript", confidence=0.97)

class MockTTS:
    async def synthesize(self, text: str) -> bytes:
        return f"SIMULATED_AUDIO::{text}".encode()

class MockTelephony:
    async def transfer(self, call_id: str, destination: str) -> bool:
        return bool(call_id and destination)

class MockLLM:
    async def respond_structured(self, state: dict) -> dict:
        return {"summary": "Synthetic local structured response", "state": state.get("stage")}
