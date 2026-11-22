"""Windows SAPI text-to-speech adapter for local runtime evidence.

This adapter deliberately does not pretend to be neural TTS. It uses the installed
Windows System.Speech voice and raises a clear error on non-Windows hosts.
"""

from __future__ import annotations

import asyncio
import base64
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


class WindowsSapiTTS:
    """Synthesize text with an installed Windows System.Speech voice."""

    def __init__(self, voice_name: str = "Microsoft Zira Desktop") -> None:
        self.voice_name = voice_name

    async def synthesize(self, text: str) -> bytes:
        return await asyncio.to_thread(self._synthesize_sync, text)

    def _synthesize_sync(self, text: str) -> bytes:
        if os.name != "nt":
            raise RuntimeError("Windows System.Speech is available only on Windows hosts")
        powershell = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
        if not powershell:
            raise RuntimeError("powershell.exe is required for the Windows SAPI adapter")
        if not text.strip():
            raise ValueError("Cannot synthesize empty text")

        encoded_text = base64.b64encode(text.encode("utf-8")).decode("ascii")
        encoded_voice = base64.b64encode(self.voice_name.encode("utf-8")).decode("ascii")
        with tempfile.TemporaryDirectory(prefix="voxrelay-sapi-") as temp_dir:
            output = Path(temp_dir) / "speech.wav"
            encoded_output = base64.b64encode(str(output).encode("utf-8")).decode("ascii")
            script = (
                "$text=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"
                + encoded_text
                + "'));"
                "$voice=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"
                + encoded_voice
                + "'));"
                "$out=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"
                + encoded_output
                + "'));"
                "Add-Type -AssemblyName System.Speech;"
                "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                "$s.SelectVoice($voice);"
                "$s.SetOutputToWaveFile($out);"
                "$s.Speak($text);"
                "$s.Dispose();"
            )
            completed = subprocess.run(
                [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout).strip()
                raise RuntimeError(f"Windows SAPI synthesis failed: {detail[:500]}")
            if not output.exists() or output.stat().st_size < 44:
                raise RuntimeError("Windows SAPI returned no valid WAV file")
            return output.read_bytes()
