#!/usr/bin/env python3
"""Reels NARRADO (estilo dos vídeos virais "feitos com o Claude"): voz em português, legenda grande
palavra por palavra no centro (a palavra falada fica amarela), carta/foto ocupando a tela com zoom lento.

Uso: python narrado.py videos/pokemon-rica-narrado.yaml

Voz: Piper (código aberto, voz pt_BR "faber", dataset CC0), baixada de huggingface.co/rhasspy/piper-voices.
Cada cena tem `fala` (o que a voz lê, números por extenso) e `tela` (a legenda, com números).
"""
import subprocess
import sys
import wave
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFilter

import carrossel as C
import reel as R

BASE = Path(__file__).resolve().parent
VOZ = BASE / "vozes" / "pt_BR-jeff-medium.onnx"   # a mais expressiva das vozes pt-BR livres (CC0)
VOZ_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/jeff/medium/pt_BR-jeff-medium.onnx"
TOM = 1.12  # +2 semitons: soa mais jovem e animado
VW, VH, FPS = R.VW, R.VH, R.FPS
SR = 22050


def _garantir_voz():
    if VOZ.exists():
        return
    VOZ.parent.mkdir(exist_ok=True)
    subprocess.run(["curl", "-sL", "-o", str(VOZ), VOZ_URL], check=True)
    subprocess.run(["curl", "-sL", "-o", str(VOZ) + ".json", VOZ_URL + ".json"], check=True)


def falar(texto, saida, ritmo=0.9):
    _garantir_voz()
    cru = Path(str(saida) + ".cru.wav")
    subprocess.run([sys.executable, "-m", "piper", "-m", str(VOZ), "-f", str(cru), "--length-scale", str(ritmo),
                    "--sentence-silence", "0.12"], input=texto.encode("utf-8"), check=True, capture_output=True)
    # tom mais alto sem mudar a velocidade + leve brilho e compressão (voz de vídeo)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(cru), "-af",
                    f"asetrate={SR}*{TOM},aresample={SR},atempo={1 / TOM:.4f},"
                    "equalizer=f=3500:t=q:w=1.2:g=3,acompressor=threshold=-18dB:ratio=3:attack=5:release=60",
                    "-ar", str(SR), "-ac", "1", str(saida)], check=True)
    cru.unlink()
    with wave.open(str(saida)) as w:
        return w.getnframes() / w.getframerate()


def _tempos_palavras(tela, dur, ini=0.15, fim=0.25):
    """Distribui as palavras da legenda no tempo da fala, proporcional ao tamanho de cada palavra."""
    pal = tela.split()
    pesos = [len(p) + 2 for p in pal]
    tot = sum(pesos)
    util = max(0.5, dur - ini - fim)
    t, out = ini, []
    for p, w in zip(pal, pesos):
        d = util * w / tot
        out.append((p, t, t + d))
        t += d
    return out


def _blocos(tempos, n=3):
    return [tempos[i:i + n] for i in range(0, len(tempos), n)]


def _legenda(fr, bloco, agora, y=1240):
    d = ImageDraw.Draw(fr)
    f = C.cond(112)
    esp = d.textlength(" ", font=f)
    larg = VW - 100
    # quebra o bloco em linhas que cabem
    linhas, atual = [], []
    for item in bloco:
        teste = " ".join(x[0] for x in atual + [item]).upper()
        if atual and d.textlength(teste, font=f) > larg:
            linhas.append(atual)
            atual = [item]
        else:
            atual.append(item)
    if atual:
        linhas.append(atual)
    for ln in linhas:
        txts = [x[0].upper() for x in ln]
        wtot = sum(d.textlength(t, font=f) for t in txts) + esp * (len(txts) - 1)
        x = (VW - wtot) / 2
        for (p, a, b), t in zip(ln, txts):
            ativo = a <= agora < b
            cor = C.AMARELO if ativo else C.BRANCO
            d.text((x, y), t, font=f, fill=cor, stroke_width=9, stroke_fill=(0, 0, 0))
            x += d.textlength(t, font=f) + esp
        y += 124


def gerar(arq):
    v = yaml.safe_load(open(arq, encoding="utf-8"))
    if not v.get("fontes"):
        raise SystemExit("vídeo sem fonte: não monto")
    pasta = BASE / "videos"
    tmp = pasta / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    cenas = v["cenas"]
    # 1) voz de cada cena
    durs, wavs = [], []
    for k, c in enumerate(cenas):
        w = tmp / f"{v['id']}-{k}.wav"
        d = falar(c["fala"], w, v.get("ritmo", 0.9))
        wavs.append(w)
        durs.append(d + 0.25)
    # cena final (fontes), sem voz
    durs.append(3.0)
    # 2) áudio completo: cada fala + 0,25 s de respiro, mais 3 s de silêncio no fim
    lista = tmp / f"{v['id']}-lista.txt"
    sil = tmp / "sil025.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono",
                    "-t", "0.25", str(sil)], check=True)
    sil3 = tmp / "sil3.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono",
                    "-t", "3", str(sil3)], check=True)
    lista.write_text("".join(f"file '{w.name}'\nfile '{sil.name}'\n" for w in wavs) + f"file '{sil3.name}'\n")
    audio = tmp / f"{v['id']}-voz.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lista),
                    "-c", "copy", str(audio)], check=True)
    # 3) imagens
    imgs = [R._img(c["imagem"], pasta / "fotos") for c in cenas]
    tot_q = int(sum(durs) * FPS)
    saida = pasta / f"{v['id']}.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{VW}x{VH}",
           "-r", str(FPS), "-i", "-", "-i", str(audio), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-af", "loudnorm=I=-14:TP=-1.5",
           "-shortest", "-movflags", "+faststart", str(saida)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    q0 = 0
    for k, c in enumerate(cenas):
        fundo, carta = R._fundo(c, imgs[k])
        tempos = _tempos_palavras(c.get("tela", c["fala"]), durs[k] - 0.25)
        blocos = _blocos(tempos, c.get("palavras_por_vez", 3))
        n = int(durs[k] * FPS)
        cred = c.get("credito", v.get("credito_padrao", ""))
        for i in range(n):
            t, agora = i / n, i / FPS
            z = 1.0 + 0.10 * t if k % 2 == 0 else 1.10 - 0.10 * t
            bw, bh = fundo.size
            cw, ch = int(bw / z), int(bh / z)
            x0, y0 = (bw - cw) // 2, (bh - ch) // 2
            fr = fundo.crop((x0, y0, x0 + cw, y0 + ch)).resize((VW, VH), Image.BILINEAR)
            if carta is not None:
                e = min(1.0, i / 8)
                esc = (0.92 + 0.08 * e + 0.04 * t) * 0.95
                cc = carta.resize((int(carta.width * esc), int(carta.height * esc)), Image.BILINEAR)
                cx, cy = (VW - cc.width) // 2, 150 + int((1 - e) * 70)
                sombra = Image.new("RGBA", fr.size, (0, 0, 0, 0))
                ImageDraw.Draw(sombra).rounded_rectangle([cx + 10, cy + 24, cx + cc.width + 10, cy + cc.height + 24],
                                                         radius=26, fill=(0, 0, 0, 160))
                fr = Image.alpha_composite(fr, sombra.filter(ImageFilter.GaussianBlur(20)))
                fr.alpha_composite(cc, (cx, cy))
            d = ImageDraw.Draw(fr)
            if c.get("rotulo"):
                fr_ = C.cond(50)
                tt = c["rotulo"].upper()
                w = d.textlength(tt, font=fr_)
                d.rounded_rectangle([(VW - w) / 2 - 24, 1100, (VW + w) / 2 + 24, 1176], radius=18, fill=C.AMARELO)
                d.text(((VW - w) / 2, 1102), tt, font=fr_, fill=C.NOITE1)
            atual = next((b for b in blocos if b[0][1] <= agora < b[-1][2]), None)
            if atual is None and blocos and agora >= blocos[-1][-1][2]:
                atual = blocos[-1]
            if atual:
                _legenda(fr, atual, agora)
            prog = (q0 + i) / tot_q
            d.rectangle([0, 0, VW, 10], fill=(255, 255, 255))
            d.rectangle([0, 0, int(VW * prog), 10], fill=C.AMARELO)
            C.logo(fr, 48, 40, 0.7)
            d.text((48, VH - 70), cred[:90], font=C.txt2(24), fill=C.SUAVE)
            p.stdin.write(fr.convert("RGB").tobytes())
        q0 += n
    # cena final: fontes
    fim = C.fundo_feed(VW, VH, semente="fim").convert("RGBA")
    d = ImageDraw.Draw(fim)
    C.logo(fim, (VW - 330) // 2, 420, 1.2)
    y = C._titulo_revista(d, v.get("chamada", "Segue a @montoptcg pra mais"), 640,
                          v.get("destaques_chamada", ["@MONTOPTCG"]), maior=120, menor=70, larg=VW - 120, alt=420)
    fs = C.txt(32)
    y += 60
    d.text((80, y), "Fontes:", font=C.txt(30), fill=C.SUAVE)
    y += 46
    for fnt in v["fontes"]:
        for ln in C.quebrar(d, fnt, fs, VW - 160):
            d.text((80, y), ln, font=fs, fill=C.SUAVE)
            y += 42
    fim_rgb = fim.convert("RGB").tobytes()
    for i in range(int(durs[-1] * FPS)):
        p.stdin.write(fim_rgb)
    p.stdin.close()
    p.wait()
    capa = pasta / f"{v['id']}-capa.jpg"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1.2", "-i", str(saida), "-frames:v", "1", str(capa)])
    agenda = BASE / "agenda.yaml"
    itens = yaml.safe_load(agenda.read_text(encoding="utf-8")) if agenda.exists() else []
    itens = [x for x in (itens or []) if x["id"] != v["id"]]
    if v.get("quando"):
        itens.append({"quando": v["quando"], "id": v["id"], "jogo": v.get("jogo", "Pokémon"), "tipo": "reel",
                      "video": f"videos/{saida.name}", "capa": f"videos/{capa.name}", "slides": [],
                      "legenda_telegram": v["legenda"], "legenda_instagram": v["legenda"]})
    agenda.write_text(yaml.safe_dump(sorted(itens, key=lambda x: x["quando"]), allow_unicode=True,
                                     sort_keys=False), encoding="utf-8")
    print("Vídeo narrado pronto:", saida, f"({sum(durs):.1f} s)")
    return saida


if __name__ == "__main__":
    gerar(sys.argv[1])
