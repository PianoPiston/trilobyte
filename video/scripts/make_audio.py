"""Narration (Piper TTS, one wav per scene) + a soft synthesized music bed. Writes public/vo/*.wav, public/music.wav, src/timing.json."""
import json, math, subprocess, sys, wave
import numpy as np
VOICE = sys.argv[1] if len(sys.argv) > 1 else "/home/user/models/piper/en_US-ryan-high.onnx"
SPEED = float(sys.argv[2]) if len(sys.argv) > 2 else 0.95  # piper length_scale (<1 = faster)
PAD = 0.7  # seconds of air after each line
MIN = {"title": 6, "drop": 6, "measure": 6, "model3d": 7, "close": 7.5}
scenes = json.load(open("script.json"))
timing = []
for i, s in enumerate(scenes):
    out = f"public/vo/{i:02d}-{s['id']}.wav"
    subprocess.run([sys.executable, "-m", "piper", "-m", VOICE, "--length-scale", str(SPEED), "--sentence-silence", "0.25", "-f", out],
                   input=s["say"].encode(), check=True, capture_output=True)
    with wave.open(out) as w:
        dur = w.getnframes() / w.getframerate()
    sec = max(dur + PAD, MIN.get(s["id"], 0)) + (0.6 if i == 0 else 0)
    timing.append({"id": s["id"], "say": s["say"], "text": s.get("text", s["say"]), "vo": out.replace("public/", ""), "voSec": round(dur, 2), "sec": round(sec, 2)})
total = sum(t["sec"] for t in timing)
json.dump({"total": total, "scenes": timing}, open("src/timing.json", "w"), indent=1)
print("total seconds", round(total, 1)); [print(f"  {t['id']:8s} vo {t['voSec']:5.1f}s scene {t['sec']:5.1f}s") for t in timing]
# music bed: slow I–vi–IV–V pad in C, soft sine + octave, gentle fades
sr = 44100; n = int((total + 1) * sr); t = np.arange(n) / sr
chords = [[261.63, 329.63, 392.0], [220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [196.0, 246.94, 293.66]]
bar = 4.0; y = np.zeros(n)
for k in range(int(total / bar) + 2):
    a, b = int(k * bar * sr), min(n, int((k + 1) * bar * sr + 0.5 * sr))
    if a >= n: break
    seg = t[a:b] - t[a]; env = np.minimum(1, seg / 0.8) * np.minimum(1, (seg[-1] - seg + 1e-3) / 0.8)
    for f in chords[k % 4]:
        y[a:b] += env * (np.sin(2 * math.pi * f / 2 * seg) * 0.5 + np.sin(2 * math.pi * f * seg) * 0.25)
y *= np.minimum(1, t / 3) * np.minimum(1, (t[-1] - t) / 3)
y = y / np.abs(y).max() * 0.9
with wave.open("public/music.wav", "w") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((y * 32767).astype(np.int16).tobytes())
