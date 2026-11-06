"""Monta o JSON de um episódio Fofoca TCG: corta a instrução de estilo lida pela IA,
alinha as cenas pelas palavras-âncora e corrige a grafia das legendas."""
import json, subprocess, sys, unicodedata

ep, primeira = sys.argv[1], sys.argv[2]
cfg = json.load(open(f"/home/claude/previa/{ep}-cenas.json"))
pal = json.load(open(f"/home/claude/previa/{ep}-pal.json"))
norm = lambda s: unicodedata.normalize("NFD", s.lower()).encode("ascii", "ignore").decode().strip().strip(".,!?…:;")

i0 = next(i for i, p in enumerate(pal) if norm(p["text"]) == primeira)
corte = max(0, pal[i0]["startMs"] - 120)
pal = pal[i0:]
src = f"/home/claude/arcos-robo/videos/audio/{ep}.wav"
dst = f"/home/claude/montop-video/public/{ep}-voz.wav"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{corte/1000:.3f}", "-i", src,
                "-af", "afade=t=in:d=0.03,loudnorm=I=-14:TP=-1.5", "-ar", "44100", dst], check=True)
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", dst],
                           capture_output=True, text=True).stdout)

troca = cfg.get("troca", {})
leg = []
for p in pal:
    t = troca.get(norm(p["text"]), p["text"])
    leg.append({"text": " " + t, "startMs": p["startMs"] - corte, "endMs": p["endMs"] - corte,
                "timestampMs": p["timestampMs"] - corte, "confidence": p["confidence"], "pageBreakAfter": False})
# quebra de página em fim de frase
for a, p in zip(leg, pal):
    if p["text"][-1:] in ".?!,":
        a["pageBreakAfter"] = True

cenas, pos = [], 0
for c in cfg["cenas"]:
    anc = c.pop("ancora", None)
    if anc is None:
        c["inicioMs"] = 0
    else:
        seq = anc.split()
        ks = [k for k in range(pos, len(leg)) if [norm(x["text"]) for x in leg[k:k + len(seq)]] == seq]
        if not ks: sys.exit(f"âncora não achada: {anc}")
        k = ks[0]
        c["inicioMs"] = max(0, leg[k]["startMs"] - 150)
        pos = k + 1
        leg[k - 1]["pageBreakAfter"] = True
    cenas.append(c)
out = {"audio": f"{ep}-voz.wav", "duracaoMs": int(dur * 1000) + 900, "legendas": leg, "cenas": cenas,
       "fontes": cfg.get("fontes", "")}
json.dump(out, open(f"/home/claude/montop-video/public/{ep}.json", "w"), ensure_ascii=False)
print(ep, "dur", round(dur, 1), "s;", [(c["tipo"], c["inicioMs"]) for c in cenas])
