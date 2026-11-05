#!/usr/bin/env python3
"""Vídeo vertical (Reels 1080×1920) no estilo "revista" da Montop: imagem cheia, título enorme
condensado com palavras em destaque, texto entrando com animação e barra de progresso.

Uso: python reel.py videos/pokemon-rica.yaml
Imagens: só carta OFICIAL (cache_cartas/ ou URL oficial) ou foto livre do Commons com crédito.
Sem música: o áudio em alta é escolhido no app do Instagram (evita problema de direitos).
"""
import subprocess
import sys
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

import carrossel as C

BASE = Path(__file__).resolve().parent
VW, VH, FPS = 1080, 1920, 30


def _img(ref, pasta_fotos):
    p = BASE / "cache_cartas" / str(ref).rsplit("/", 1)[-1]
    if p.exists():
        return Image.open(p).convert("RGB")
    q = Path(pasta_fotos) / str(ref)
    if q.exists():
        return Image.open(q).convert("RGB")
    import imagens
    img = imagens.baixar(str(ref))
    if img is None:
        raise SystemExit(f"sem imagem ({ref}): não monto")
    return img


def _quebrar(d, texto, f, larg):
    return C.quebrar(d, texto, f, larg)


def _camada_texto(cena, k, total):
    """Tudo que não é fundo: carta, faixa da marca, título, subtítulo. RGBA transparente."""
    cam = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d = ImageDraw.Draw(cam)
    topo = 1080 if cena.get("tipo") != "texto" else 640
    if cena.get("rotulo"):
        f = C.cond(54)
        t = cena["rotulo"].upper()
        w = d.textlength(t, font=f)
        d.rounded_rectangle([(VW - w) / 2 - 26, topo - 120, (VW + w) / 2 + 26, topo - 40], radius=18,
                            fill=C.AMARELO)
        d.text(((VW - w) / 2, topo - 118), t, font=f, fill=C.NOITE1)
    fim = C._titulo_revista(d, cena["titulo"], topo, cena.get("destaques", ()), maior=130, menor=70,
                            larg=VW - 110, alt=520)
    if cena.get("sub"):
        fs = C.txt(42)
        y = fim + 40
        for ln in _quebrar(d, cena["sub"], fs, VW - 160):
            d.text(((VW - d.textlength(ln, font=fs)) / 2 + 2, y + 2), ln, font=fs, fill=(0, 0, 0))
            d.text(((VW - d.textlength(ln, font=fs)) / 2, y), ln, font=fs, fill=C.BRANCO)
            y += 54
    return cam


def _fundo(cena, img):
    """Fundo maior que a tela (para o zoom lento) + carta grande por cima, se for carta."""
    S = 1.12
    bw, bh = int(VW * S), int(VH * S)
    if cena.get("tipo") == "foto":
        b = ImageOps.fit(img, (bw, bh), Image.LANCZOS, centering=cena.get("centro", (0.5, 0.5)))
        b = ImageEnhance.Brightness(b).enhance(0.8)
    else:
        b = ImageOps.fit(img, (bw, bh), Image.LANCZOS, centering=(0.5, 0.35)).filter(ImageFilter.GaussianBlur(40))
        b = ImageEnhance.Color(b).enhance(1.3)
        b = ImageEnhance.Brightness(b).enhance(0.6)
    # degradê escuro embaixo para o texto
    veu = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    dv = ImageDraw.Draw(veu)
    ini = int(bh * 0.42)
    for y in range(ini, bh):
        dv.line([(0, y), (bw, y)], fill=(6, 7, 16, int(245 * ((y - ini) / (bh - ini)) ** 0.8)))
    dv.rectangle([0, 0, bw, int(bh * 0.08)], fill=(6, 7, 16, 90))
    b = Image.alpha_composite(b.convert("RGBA"), veu)
    carta = None
    if cena.get("tipo", "carta") == "carta":
        alt = 860
        c = ImageOps.contain(C._carta_nitida(img, alt), (int(alt * 0.75), alt), Image.LANCZOS)
        carta = C._arredondar(c.convert("RGB"), 22)
    return b, carta


def _quadros(cenas, imgs, creditos_linha):
    total = len(cenas)
    dur = [float(c.get("seg", 3.6)) for c in cenas]
    tot_q = int(sum(dur) * FPS)
    q0 = 0
    for k, (cena, img) in enumerate(zip(cenas, imgs)):
        fundo, carta = _fundo(cena, img) if img is not None else (C.fundo_feed(VW, VH, semente=str(k)).convert("RGBA"), None)
        if img is None:
            fundo = ImageOps.fit(fundo, (int(VW * 1.12), int(VH * 1.12)))
        texto = _camada_texto(cena, k, total)
        n = int(dur[k] * FPS)
        for i in range(n):
            t = i / n
            # zoom lento (Ken Burns)
            z = 1.0 + 0.10 * t if k % 2 == 0 else 1.10 - 0.10 * t
            bw, bh = fundo.size
            cw, ch = int(bw / z), int(bh / z)
            x0, y0 = (bw - cw) // 2, (bh - ch) // 2
            fr = fundo.crop((x0, y0, x0 + cw, y0 + ch)).resize((VW, VH), Image.BILINEAR)
            if carta is not None:
                e = min(1.0, i / 9)  # entra subindo
                esc = 0.92 + 0.08 * e + 0.03 * t
                c = carta.resize((int(carta.width * esc), int(carta.height * esc)), Image.BILINEAR)
                cx, cy = (VW - c.width) // 2, 140 + int((1 - e) * 60)
                sombra = Image.new("RGBA", fr.size, (0, 0, 0, 0))
                ImageDraw.Draw(sombra).rounded_rectangle([cx + 10, cy + 24, cx + c.width + 10, cy + c.height + 24],
                                                         radius=26, fill=(0, 0, 0, 160))
                fr = Image.alpha_composite(fr, sombra.filter(ImageFilter.GaussianBlur(20)))
                fr.alpha_composite(c, (cx, cy))
            # texto: aparece subindo nos primeiros 0,4 s
            a = min(1.0, max(0.0, (i - 4) / 10))
            dy = int((1 - a) * 50)
            if a > 0:
                tx = texto.copy()
                if a < 1:
                    tx.putalpha(tx.split()[-1].point(lambda v: int(v * a)))
                fr.alpha_composite(tx, (0, dy) if dy else (0, 0))
            d = ImageDraw.Draw(fr)
            # barra de progresso + marca
            prog = (q0 + i) / tot_q
            d.rectangle([0, 0, VW, 10], fill=(255, 255, 255, 60))
            d.rectangle([0, 0, int(VW * prog), 10], fill=C.AMARELO)
            C.logo(fr, 48, 40, 0.7)
            d.text((48, VH - 70), creditos_linha[k][:90], font=C.txt2(24), fill=C.SUAVE)
            yield fr.convert("RGB")
        q0 += n


def gerar(arq):
    v = yaml.safe_load(open(arq, encoding="utf-8"))
    if not v.get("fontes"):
        raise SystemExit("vídeo sem fonte: não monto")
    pasta = BASE / "videos"
    imgs, cred = [], []
    for c in v["cenas"]:
        if c.get("tipo") == "texto":
            imgs.append(None)
            cred.append("")
        else:
            imgs.append(_img(c["imagem"], pasta / "fotos"))
            cred.append(c.get("credito", v.get("credito_padrao", "")))
    # cena final de fontes (fixa)
    v["cenas"].append({"tipo": "texto", "rotulo": "Segue a @montoptcg", "titulo": v.get("chamada", "Segue a @montoptcg pra mais"),
                       "destaques": v.get("destaques_chamada", ["@MONTOPTCG"]),
                       "sub": "Fontes: " + " · ".join(v["fontes"]), "seg": 3.5})
    imgs.append(None)
    cred.append("")
    saida = pasta / f"{v['id']}.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{VW}x{VH}",
           "-r", str(FPS), "-i", "-", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
           "-shortest", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-movflags", "+faststart", str(saida)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for fr in _quadros(v["cenas"], imgs, cred):
        p.stdin.write(fr.tobytes())
    p.stdin.close()
    p.wait()
    # capa (1º quadro com texto) para o feed
    capa = pasta / f"{v['id']}-capa.jpg"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1.5", "-i", str(saida), "-frames:v", "1",
                    str(capa)])
    agenda = BASE / "agenda.yaml"
    itens = yaml.safe_load(agenda.read_text(encoding="utf-8")) if agenda.exists() else []
    itens = [x for x in (itens or []) if x["id"] != v["id"]]
    itens.append({"quando": v["quando"], "id": v["id"], "jogo": v.get("jogo", "Pokémon"), "tipo": "reel",
                  "video": f"videos/{saida.name}", "capa": f"videos/{capa.name}", "slides": [],
                  "legenda_telegram": v["legenda"], "legenda_instagram": v["legenda"]})
    agenda.write_text(yaml.safe_dump(sorted(itens, key=lambda x: x["quando"]), allow_unicode=True,
                                     sort_keys=False), encoding="utf-8")
    print("Vídeo pronto:", saida, "| capa:", capa, "| agendado:", v["quando"])
    return saida


if __name__ == "__main__":
    gerar(sys.argv[1])
