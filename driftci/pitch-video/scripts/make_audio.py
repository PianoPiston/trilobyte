"""Generate scene narration, timing data and a quiet synthesized score."""
import json
import math
from pathlib import Path
import subprocess
import sys
import wave

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
VOICE = sys.argv[1] if len(sys.argv) > 1 else "/home/user/models/piper/en_US-ryan-high.onnx"
SPEED = float(sys.argv[2]) if len(sys.argv) > 2 else 0.92
PAD = 0.65
MINIMUM = {"hook": 9.5, "problem": 9, "release": 12, "manager": 13, "watch": 14, "vulnerability": 17, "decision": 17, "close": 9}

(ROOT / "public/vo").mkdir(parents=True, exist_ok=True)
scenes = json.loads((ROOT / "script.json").read_text())
timing = []
for i, scene in enumerate(scenes):
    relative = f"vo/{i:02d}-{scene['id']}.wav"
    output = ROOT / "public" / relative
    subprocess.run(
        [sys.executable, "-m", "piper", "-m", VOICE, "--length-scale", str(SPEED), "--sentence-silence", "0.22", "-f", str(output)],
        input=scene["say"].encode(), check=True, capture_output=True,
    )
    with wave.open(str(output)) as audio:
        voice_seconds = audio.getnframes() / audio.getframerate()
    seconds = max(voice_seconds + PAD, MINIMUM.get(scene["id"], 0)) + (0.6 if i == 0 else 0)
    timing.append({**scene, "vo": relative, "voSec": round(voice_seconds, 2), "sec": round(seconds, 2)})

total = sum(scene["sec"] for scene in timing)
(ROOT / "src/timing.json").write_text(json.dumps({"total": total, "scenes": timing}, indent=2) + "\n")
print(f"total seconds {total:.1f}")
for scene in timing:
    print(f"  {scene['id']:14s} voice {scene['voSec']:5.1f}s  scene {scene['sec']:5.1f}s")

# Slow major-seven pad. Sidechaining is handled by keeping the bed deliberately quiet.
sample_rate = 44100
count = int((total + 1) * sample_rate)
t = np.arange(count) / sample_rate
chords = [
    [220.0, 277.18, 329.63, 415.30],
    [164.81, 220.0, 277.18, 329.63],
    [174.61, 220.0, 261.63, 329.63],
    [196.0, 246.94, 293.66, 369.99],
]
music = np.zeros(count)
bar = 4.0
for k in range(int(total / bar) + 2):
    start, end = int(k * bar * sample_rate), min(count, int((k + 1) * bar * sample_rate + 0.5 * sample_rate))
    if start >= count:
        break
    segment = t[start:end] - t[start]
    envelope = np.minimum(1, segment / 1.1) * np.minimum(1, (segment[-1] - segment + 1e-3) / 1.1)
    for frequency in chords[k % len(chords)]:
        music[start:end] += envelope * (
            np.sin(2 * math.pi * frequency / 2 * segment) * 0.5
            + np.sin(2 * math.pi * frequency * segment) * 0.16
        )
music *= np.minimum(1, t / 3) * np.minimum(1, (t[-1] - t) / 3)
music = music / np.abs(music).max() * 0.85
with wave.open(str(ROOT / "public/music.wav"), "wb") as output:
    output.setnchannels(1)
    output.setsampwidth(2)
    output.setframerate(sample_rate)
    output.writeframes((music * 32767).astype(np.int16).tobytes())
