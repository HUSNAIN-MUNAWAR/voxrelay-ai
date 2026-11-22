# VoxRelay runtime evidence

The evidence files in this directory were generated from a real local run of the VoxRelay call domain:

1. `create_simulated_call` persisted a `clinic_booking` call.
2. `stream_scenario` persisted the transcript segments and ordered call events.
3. Windows System.Speech synthesized the persisted transcript with `Microsoft Zira Desktop` into a PCM WAV.
4. OpenCV rendered a frame-by-frame waveform/event animation from the emitted WAV and event trace.

Run on Windows:

```powershell
py -3.12 -m pip install -e "apps/api[dev]"
py -3.12 scripts/verification/generate_runtime_evidence.py
```

The WAV and MP4 are evidence artifacts, not customer data. The MP4 is a visual timeline and deliberately has no audio track. The summary records the source path, runtime, hashes, event count, and claim boundary. No neural speech checkpoint is present in this repository or in the local cache used for the run; adding a learned STT/TTS provider requires a separately authorized model and must not be inferred from this evidence.
