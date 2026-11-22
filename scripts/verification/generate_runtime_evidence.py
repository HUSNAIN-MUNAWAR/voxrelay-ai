from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import math
import os
import platform
import sys
import wave
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
API_ROOT = ROOT / "apps/api"
DB_PATH = ROOT / "runtime_evidence.db"
OUTPUT_DIR = ROOT / "docs/runtime_evidence"
AUDIO_PATH = OUTPUT_DIR / "voxrelay-sapi-call.wav"
ANIMATION_PATH = OUTPUT_DIR / "voxrelay-call-runtime-animation.mp4"
POSTER_PATH = OUTPUT_DIR / "voxrelay-call-runtime-poster.jpg"
TRACE_PATH = OUTPUT_DIR / "voxrelay-call-event-trace.csv"
SUMMARY_PATH = OUTPUT_DIR / "voxrelay-runtime-summary.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact(path: Path) -> dict[str, str | int]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def read_wave(path: Path) -> tuple[np.ndarray, int, int, int]:
    with wave.open(str(path), "rb") as source:
        channels = source.getnchannels()
        sample_width = source.getsampwidth()
        rate = source.getframerate()
        frames = source.getnframes()
        raw = source.readframes(frames)
    if sample_width != 2:
        raise RuntimeError(
            f"Expected 16-bit SAPI PCM, received sample width {sample_width}"
        )
    samples = np.frombuffer(raw, dtype=np.int16)
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1).astype(np.int16)
    return samples, rate, channels, frames


def render_animation(
    samples: np.ndarray,
    rate: int,
    duration_s: float,
    trace_rows: list[dict[str, object]],
) -> dict[str, int | float]:
    width, height, fps = 960, 540, 15.0
    frame_count = max(1, math.ceil(duration_s * fps))
    writer = cv2.VideoWriter(
        str(ANIMATION_PATH),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Could not open animation writer: {ANIMATION_PATH}")

    normal = samples.astype(np.float32) / 32768.0
    max_event = max(1, len(trace_rows) - 1)
    for frame_index in range(frame_count):
        time_s = frame_index / fps
        canvas = np.full((height, width, 3), (15, 23, 42), dtype=np.uint8)
        cv2.putText(
            canvas,
            "VoxRelay AI - real local voice runtime",
            (36, 48),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.85,
            (226, 232, 240),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            canvas,
            f"Windows System.Speech / Microsoft Zira Desktop   t={time_s:.2f}s",
            (38, 82),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (125, 211, 252),
            2,
            cv2.LINE_AA,
        )

        start = max(0, int((time_s - 1.0) * rate))
        end = min(len(normal), max(start + 1, int((time_s + 0.05) * rate)))
        window = normal[start:end]
        if len(window) > 1:
            positions = np.linspace(0, len(window) - 1, 1100).astype(np.int32)
            values = window[positions]
            x = np.linspace(38, width - 38, len(values)).astype(np.int32)
            y = (260 - values * 105).astype(np.int32)
            points = np.column_stack((x, y)).reshape(-1, 1, 2)
            cv2.polylines(canvas, [points], False, (45, 212, 191), 2, cv2.LINE_AA)
        cv2.line(canvas, (38, 260), (width - 38, 260), (71, 85, 105), 1)

        timeline_y = 370
        cv2.line(canvas, (38, timeline_y), (width - 38, timeline_y), (71, 85, 105), 2)
        for row in trace_rows:
            event_time = float(row["timestamp_s"])
            x = int(38 + (width - 76) * event_time / max(duration_s, 0.001))
            cv2.line(
                canvas, (x, timeline_y - 18), (x, timeline_y + 18), (251, 191, 36), 2
            )
            if event_time <= time_s:
                cv2.circle(canvas, (x, timeline_y), 7, (251, 191, 36), -1)

        current = trace_rows[0] if trace_rows else {"event_type": "no event"}
        for row in trace_rows:
            if float(row["timestamp_s"]) <= time_s:
                current = row
        label = str(current.get("event_type", "call started"))
        detail = str(current.get("detail", ""))[:100]
        cv2.putText(
            canvas,
            f"Current event: {label}",
            (38, 445),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (248, 250, 252),
            2,
        )
        cv2.putText(
            canvas,
            detail,
            (38, 478),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (148, 163, 184),
            1,
        )
        cv2.putText(
            canvas,
            f"Persisted event {min(max_event, int(current.get('sequence', 0)))} / {max_event}  |  audio waveform is from the emitted WAV",
            (38, 515),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (148, 163, 184),
            1,
        )
        writer.write(canvas)
        if frame_index == min(int(fps), frame_count - 1):
            cv2.imwrite(str(POSTER_PATH), canvas)
    writer.release()
    return {"frames": frame_count, "fps": fps, "width": width, "height": height}


async def run_call() -> tuple[str, str, list[dict[str, object]]]:
    sys.path.insert(0, str(API_ROOT))
    from app.db import Base, SessionLocal, TranscriptSegment, engine
    from app.providers.windows_sapi import WindowsSapiTTS
    from app.services.simulation import create_simulated_call, stream_scenario

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        call = create_simulated_call(
            db,
            "clinic_booking",
            agent_id="agent-clinic",
            organization_id="org-carebridge",
            actor="runtime.evidence",
        )
        payloads: list[dict[str, object]] = []
        async for payload in stream_scenario(db, call):
            payloads.append(payload)
        transcript = (
            db.query(TranscriptSegment)
            .filter(TranscriptSegment.call_id == call.id)
            .all()
        )
        text = " ".join(segment.text for segment in transcript)
        audio = await WindowsSapiTTS().synthesize(text)
        AUDIO_PATH.write_bytes(audio)
        with wave.open(str(AUDIO_PATH), "rb") as source:
            duration = max(0.1, source.getnframes() / source.getframerate())
        trace_rows = [
            {
                "sequence": index,
                "timestamp_s": round(index * duration / max(1, len(payloads) - 1), 6),
                "event_type": str(payload.get("event_type", "unknown")),
                "speaker": str(payload.get("speaker", "system")),
                "confidence": payload.get("confidence", ""),
                "detail": str(
                    payload.get("text", payload.get("note", payload.get("state", "")))
                ),
            }
            for index, payload in enumerate(payloads)
        ]
        TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with TRACE_PATH.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(trace_rows[0]))
            writer.writeheader()
            writer.writerows(trace_rows)
        return call.id, call.status, trace_rows


def main() -> None:
    os.chdir(ROOT)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in (AUDIO_PATH, ANIMATION_PATH, POSTER_PATH, TRACE_PATH, SUMMARY_PATH):
        path.unlink(missing_ok=True)
    DB_PATH.unlink(missing_ok=True)
    os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH.as_posix()}"
    os.environ["JWT_SECRET"] = "runtime-evidence-only-not-for-production"

    call_id, call_status, trace_rows = asyncio.run(run_call())
    samples, rate, channels, frame_count = read_wave(AUDIO_PATH)
    duration = frame_count / rate
    encoded = render_animation(samples, rate, duration, trace_rows)
    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": {
            "os": platform.platform(),
            "python": sys.version.split()[0],
            "opencv": cv2.__version__,
        },
        "scenario": {
            "name": "clinic_booking",
            "call_id": call_id,
            "status": call_status,
            "events": len(trace_rows),
            "synthetic": True,
            "provider_mode": "deterministic_local",
        },
        "audio": {
            "provider": "Windows System.Speech",
            "voice": "Microsoft Zira Desktop",
            "channels": channels,
            "sample_rate_hz": rate,
            "sample_width_bytes": 2,
            "frames": frame_count,
            "duration_s": round(duration, 6),
        },
        "artifacts": {
            "audio_wav": artifact(AUDIO_PATH),
            "animation_mp4": artifact(ANIMATION_PATH),
            "poster_jpg": artifact(POSTER_PATH),
            "event_trace_csv": artifact(TRACE_PATH),
        },
        "encoded_animation": encoded,
        "claim_boundary": [
            "The simulator persisted a real local call, transcript segments, and ordered event records before evidence generation.",
            "The WAV was synthesized by the installed Windows System.Speech Microsoft Zira Desktop voice from the persisted synthetic transcript.",
            "The MP4 is a waveform and event-timeline animation derived from that emitted WAV and persisted event trace; it has no audio track.",
            "This is not neural TTS, speech recognition, an external telephony call, an external LLM, or a production benchmark.",
            "No customer audio, private data, or fabricated provider result is used.",
        ],
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
