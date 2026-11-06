import sys, json, wave, numpy as np, subprocess
from faster_whisper import WhisperModel
src = sys.argv[1]; tmp = "/home/claude/previa/v16.wav"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-ac", "1", "-ar", "16000", tmp], check=True)
w = wave.open(tmp); a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
m = WhisperModel("small", device="cpu", compute_type="int8")
segs, _ = m.transcribe(a, language="pt", word_timestamps=True, initial_prompt=sys.argv[3] if len(sys.argv) > 3 else None)
out = []
for s in segs:
    for p in s.words:
        out.append({"text": p.word.strip(), "startMs": int(p.start * 1000), "endMs": int(p.end * 1000),
                    "timestampMs": int((p.start + p.end) * 500), "confidence": round(p.probability, 3)})
json.dump(out, open(sys.argv[2], "w"), ensure_ascii=False, indent=0)
print(" ".join(f"{o['text']}" for o in out))
print(len(out), "palavras; fim", out[-1]["endMs"] / 1000, "s; confiança média", round(sum(o["confidence"] for o in out) / len(out), 3))
