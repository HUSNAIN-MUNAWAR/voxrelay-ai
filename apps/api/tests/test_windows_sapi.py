import asyncio
import sys

import pytest

from app.providers.windows_sapi import WindowsSapiTTS


@pytest.mark.skipif(sys.platform != "win32", reason="Windows System.Speech is Windows-only")
def test_windows_sapi_emits_pcm_wave_bytes():
    audio = asyncio.run(WindowsSapiTTS().synthesize("VoxRelay local runtime check."))
    assert audio[:4] == b"RIFF"
    assert audio[8:12] == b"WAVE"
    assert len(audio) > 44
