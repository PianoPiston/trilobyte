# DriftCI pitch video

A narrated 1920×1080 Remotion pitch for DriftCI. Product scenes use the verified captures in `../docs/screenshots/`; the status cards and diagrams are conceptual motion graphics. The local QA hold shown in the decision scene is a DriftCI record, not a GitHub approval.

## Rebuild

The generated narration, music and timing data are included, so rendering only needs Node.js:

```bash
npm install
npm run render
```

The render is written to `out/driftci-pitch.mp4`. Use `npm run studio` to edit the composition interactively.

To change the narration, edit `script.json` and regenerate the audio with Python 3.12 and a Piper voice model. The default voice path is `/home/user/models/piper/en_US-ryan-high.onnx`; pass another `.onnx` path as the first argument to `make_audio.py` when needed.

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python piper-tts numpy
npm run audio
npm run render
```

- `script.json`: narration, one entry per scene
- `src/timing.json`: generated scene durations
- `src/DriftCI.tsx`: motion design, screenshots, captions and audio placement
- `scripts/make_audio.py`: Piper narration, timing and synthesized music
- `public/shots/`: verified DriftCI product captures

The final video is under two minutes. It does not claim that DriftCI merges code, deploys applications, proves exploitability or substitutes a local decision for a GitHub review.
