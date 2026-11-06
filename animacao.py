#!/usr/bin/env python3
"""Curtas animados no estilo "você decide" (bonecos 2D desenhados em código, narração em 2ª pessoa,
legenda grande com palavra em laranja, silêncio antes da revelação e grave só no impacto).

Uso: python animacao.py episodios/pikachu-ilustrador.py   (o episódio é um módulo com CENAS e META)

Regras da Montop: personagens 100% originais (nunca Pokémon desenhado), fatos com fonte,
carta oficial só como imagem oficial; voz Piper livre (ou gravação do Marcos em vozes/).
"""
import importlib.util
import math
import random
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = Path(__file__).resolve().parent
W, H, FPS, SS = 1080, 1920, 30, 2          # SS = supersampling (desenha em 2x e reduz: traço liso)
SR = 22050
LARANJA = (255, 153, 0)
BRANCO = (255, 255, 255)


import functools


@functools.lru_cache(maxsize=256)
def fonte(tam, peso=b"ExtraBold"):
    f = ImageFont.truetype(str(BASE / "fontes" / "Montserrat.ttf"), tam)
    f.set_variation_by_name(peso)
    return f


def suave(t):  # easing
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def mix(a, b, t):
    return a + (b - a) * t


def cor_mix(c1, c2, t):
    return tuple(int(mix(a, b, t)) for a, b in zip(c1, c2))


# ------------------------------------------------------------------ pincel com câmera

class Pincel:
    """Desenha em coordenadas do 'mundo' (1080×1920) com câmera (zoom + posição), em 2x."""

    def __init__(self, cam=(540, 960, 1.0), tremor=0.0):
        self.im = Image.new("RGB", (W * SS, H * SS), (10, 10, 20))
        self.d = ImageDraw.Draw(self.im, "RGBA")
        cx, cy, z = cam
        if tremor:
            cx += random.uniform(-tremor, tremor)
            cy += random.uniform(-tremor, tremor)
        self.cx, self.cy, self.z = cx, cy, z

    def p(self, x, y):
        return ((x - self.cx) * self.z + W / 2) * SS, ((y - self.cy) * self.z + H / 2) * SS

    def r(self, v):
        return v * self.z * SS

    def ret(self, x0, y0, x1, y1, cor, raio=0, borda=None, lw=0):
        a, b = self.p(x0, y0), self.p(x1, y1)
        self.d.rounded_rectangle([a, b], radius=self.r(raio), fill=cor,
                                 outline=borda, width=int(self.r(lw)) if lw else 0)

    def circ(self, x, y, raio, cor, borda=None, lw=0):
        cx, cy = self.p(x, y)
        rr = self.r(raio)
        self.d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=cor, outline=borda,
                       width=int(self.r(lw)) if lw else 0)

    def linha(self, pts, cor, lw):
        pp = [self.p(*q) for q in pts]
        w = max(1, int(self.r(lw)))
        self.d.line(pp, fill=cor, width=w, joint="curve")
        for q in (pp[0], pp[-1]):
            self.d.ellipse([q[0] - w / 2, q[1] - w / 2, q[0] + w / 2, q[1] + w / 2], fill=cor)

    def poli(self, pts, cor):
        self.d.polygon([self.p(*q) for q in pts], fill=cor)

    def fundo(self, topo, base):
        for y in range(0, H * SS, 8):
            self.d.rectangle([0, y, W * SS, y + 8], fill=cor_mix(topo, base, y / (H * SS)))

    def final(self):
        return self.im.reduce(SS)


# ------------------------------------------------------------------ boneco (personagem original)

class Boneco:
    """Boneco simples e expressivo: cabeça grande, olhos de ponto, corpo de cápsula, membros grossos."""

    def __init__(self, pele=(238, 200, 160), camisa=(240, 190, 40), calca=(50, 60, 90), bone=(40, 150, 90),
                 cabelo=(40, 30, 25), oculos=False, altura=1.0):
        self.pele, self.camisa, self.calca, self.bone = pele, camisa, calca, bone
        self.cabelo, self.oculos, self.h = cabelo, oculos, altura

    def desenhar(self, pc, x, y, s=1.0, braco_e=(200, 160), braco_d=(-20, 20), perna=(0, 0), olhar=0.0,
                 boca="neutra", piscar=False, sentado=False, cabeca_incl=0.0, objeto_mao=None):
        """(x, y) = pés. Ângulos dos braços em graus (ombro, cotovelo); 0 = para baixo."""
        s *= self.h
        tron = 150 * s
        ombro_y = y - (170 if not sentado else 110) * s - tron
        quadril_y = ombro_y + tron
        cor_linha = (20, 20, 30)
        # pernas
        if sentado:
            for dx in (-22, 22):
                pts = [(x + dx * s, quadril_y), (x + (dx + 70) * s, quadril_y), (x + (dx + 70) * s, quadril_y + 95 * s)]
                pc.linha(pts, cor_linha, 44 * s)
                pc.linha(pts, self.calca, 34 * s)
        else:
            for k, dx in enumerate((-22, 22)):
                a = math.radians(perna[k % len(perna)] if isinstance(perna, tuple) else 0)
                jx = x + dx * s + math.sin(a) * 85 * s
                jy = quadril_y + math.cos(a) * 85 * s
                pts = [(x + dx * s, quadril_y), (jx, jy), (jx - math.sin(a) * 5 * s, y)]
                pc.linha(pts, cor_linha, 44 * s)
                pc.linha(pts, self.calca, 34 * s)
                pc.ret(jx - 26 * s, y - 14 * s, jx + 30 * s, y + 6 * s, (30, 30, 35), raio=8 * s)
        # tronco (cápsula)
        pc.ret(x - 58 * s, ombro_y - 10 * s, x + 58 * s, quadril_y + 18 * s, self.camisa, raio=46 * s,
               borda=cor_linha, lw=6 * s)
        # braços (ombro -> cotovelo -> mão)
        maos = []
        for lado, (a1, a2) in ((-1, braco_e), (1, braco_d)):
            ox, oy = x + lado * 50 * s, ombro_y + 22 * s
            r1, r2 = math.radians(a1), math.radians(a1 + a2)
            cx_, cy_ = ox + lado * math.sin(r1) * 78 * s, oy + math.cos(r1) * 78 * s
            mx, my = cx_ + lado * math.sin(r2) * 72 * s, cy_ + math.cos(r2) * 72 * s
            pc.linha([(ox, oy), (cx_, cy_), (mx, my)], cor_linha, 38 * s)
            pc.linha([(ox, oy), (cx_, cy_), (mx, my)], self.camisa, 28 * s)
            pc.circ(mx, my, 18 * s, self.pele, borda=cor_linha, lw=5 * s)
            maos.append((mx, my))
        if objeto_mao:
            objeto_mao(pc, *maos[1], s)
        # pescoço + cabeça
        hx, hy = x + cabeca_incl * 20 * s, ombro_y - 78 * s
        pc.ret(x - 14 * s, ombro_y - 30 * s, x + 14 * s, ombro_y + 4 * s, self.pele, raio=6 * s)
        pc.circ(hx, hy, 74 * s, self.pele, borda=cor_linha, lw=6 * s)
        # cabelo/boné
        if self.bone:
            pc.d.pieslice([*pc.p(hx - 78 * s, hy - 84 * s), *pc.p(hx + 78 * s, hy + 60 * s)], 180, 360, fill=self.bone)
            pc.ret(hx + (-10 if olhar < 0 else 10) * s, hy - 22 * s, hx + (95 if olhar >= 0 else -95) * s, hy - 8 * s,
                   self.bone, raio=6 * s)
        else:
            pc.d.pieslice([*pc.p(hx - 76 * s, hy - 80 * s), *pc.p(hx + 76 * s, hy + 40 * s)], 180, 360, fill=self.cabelo)
        # rosto
        ox = olhar * 18 * s
        for dx in (-26, 26):
            if piscar:
                pc.linha([(hx + (dx - 9) * s + ox, hy + 8 * s), (hx + (dx + 9) * s + ox, hy + 8 * s)], cor_linha, 6 * s)
            else:
                pc.circ(hx + dx * s + ox, hy + 8 * s, 8 * s, cor_linha)
            if self.oculos:
                pc.circ(hx + dx * s + ox, hy + 8 * s, 22 * s, None, borda=cor_linha, lw=5 * s)
        my = hy + 42 * s
        if boca == "sorriso":
            pc.d.arc([*pc.p(hx - 22 * s + ox, my - 18 * s), *pc.p(hx + 22 * s + ox, my + 10 * s)], 20, 160,
                     fill=cor_linha, width=int(pc.r(6 * s)))
        elif boca == "o":
            pc.circ(hx + ox, my, 12 * s, cor_linha)
        else:
            pc.linha([(hx - 14 * s + ox, my), (hx + 14 * s + ox, my)], cor_linha, 6 * s)
        return maos


# ------------------------------------------------------------------ efeitos

def luz(im, x, y, raio, cor=(255, 220, 150), forca=0.55):
    """Foco de luz (abajur, janela) somado à imagem."""
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).ellipse([x - raio, y - raio, x + raio, y + raio], fill=int(255 * forca))
    m = m.filter(ImageFilter.GaussianBlur(raio * 0.45))
    camada = Image.new("RGB", (W, H), cor)
    return Image.composite(Image.blend(im, camada, 0.5), im, m)


def vinheta(im, forca=0.65):
    if not hasattr(vinheta, "m"):
        m = Image.new("L", (W, H), 0)
        ImageDraw.Draw(m).ellipse([-260, -200, W + 260, H + 200], fill=255)
        vinheta.m = m.filter(ImageFilter.GaussianBlur(260))
    escuro = Image.new("RGB", (W, H), (0, 0, 0))
    return Image.composite(im, Image.blend(im, escuro, forca), vinheta.m)


def poeira(d, t, n=40, semente=1, cor=(255, 240, 210)):
    rnd = random.Random(semente)
    for _ in range(n):
        x0, y0, v = rnd.uniform(0, W), rnd.uniform(0, H), rnd.uniform(8, 30)
        x = (x0 + math.sin(t * 0.7 + y0) * 20) % W
        y = (y0 - t * v) % H
        a = int(60 + 60 * math.sin(t * 2 + x0))
        d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(*cor, a))


def hud(d, linha1, linha2):
    """Contador no canto, como o '06:40 / DIA 4' da referência."""
    f1, f2 = fonte(26, b"Bold"), fonte(64, b"ExtraBold")
    d.rounded_rectangle([60, 150, 60 + max(240, d.textlength(linha2, font=f2) + 50), 290], radius=18,
                        fill=(0, 0, 0, 150))
    d.text((84, 166), linha1.upper(), font=f1, fill=(255, 210, 60))
    d.text((82, 196), linha2, font=f2, fill=BRANCO)


def legenda(d, palavras, agora, y=1180):
    """2–3 palavras por vez, caixa alta, a palavra falada em laranja (como na referência)."""
    f = fonte(78)
    ativos = [p for p in palavras if p[1] <= agora < p[2] + 0.05]
    if not ativos:
        return
    i = palavras.index(ativos[0])
    bloco = palavras[(i // 3) * 3:(i // 3) * 3 + 3]
    txts = [p[0].upper() for p in bloco]
    esp = d.textlength(" ", font=f)
    wt = sum(d.textlength(t, font=f) for t in txts) + esp * (len(txts) - 1)
    if wt > W - 80:
        f = fonte(int(78 * (W - 80) / wt))
        esp = d.textlength(" ", font=f)
        wt = sum(d.textlength(t, font=f) for t in txts) + esp * (len(txts) - 1)
    x = (W - wt) / 2
    for p, t in zip(bloco, txts):
        cor = LARANJA if p is ativos[0] and p[3] else BRANCO
        d.text((x, y), t, font=f, fill=cor, stroke_width=7, stroke_fill=(0, 0, 0))
        x += d.textlength(t, font=f) + esp


# ------------------------------------------------------------------ som

def _wav(caminho):
    with wave.open(str(caminho)) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        return a, w.getframerate()


def grave(dur=1.4):
    """Impacto grave (só nas revelações): seno descendo + ruído curto."""
    t = np.arange(int(SR * dur)) / SR
    f = 70 * np.exp(-t * 2.2) + 32
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.8)
    s += np.random.default_rng(1).normal(0, 1, len(t)) * np.exp(-t * 18) * 0.25
    return (s * 0.9).astype(np.float32)


def ambiente(dur):
    """Fundo bem baixo e escuro (ruído filtrado), para o silêncio não ficar 'morto'."""
    n = int(SR * dur)
    r = np.random.default_rng(7).normal(0, 1, n)
    k = np.ones(400) / 400
    return (np.convolve(r, k, "same") * 0.35).astype(np.float32)


def falar(texto, saida, ritmo=0.9):
    import narrado
    return narrado.falar(texto, saida, ritmo)


def tempos(texto, ini, dur, destaques):
    pal = texto.split()
    pesos = [len(p) + 2 for p in pal]
    tot, t, out = sum(pesos), ini + 0.1, []
    for p, w in zip(pal, pesos):
        d = (dur - 0.25) * w / tot
        limpo = "".join(ch for ch in p.upper() if ch.isalnum())
        out.append((p, t, t + d, limpo in {x.upper() for x in destaques}))
        t += d
    return out


# ------------------------------------------------------------------ render

def gerar(arq_episodio):
    spec = importlib.util.spec_from_file_location("ep", arq_episodio)
    ep = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ep)
    meta, cenas = ep.META, ep.CENAS
    pasta = BASE / "videos"
    tmp = pasta / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    # 1) falas e linha do tempo
    linha, t = [], 0.0
    for k, c in enumerate(cenas):
        dur_fala = 0.0
        if c.get("fala"):
            w = tmp / f"{meta['id']}-{k}.wav"
            dur_fala = falar(c["fala"], w, meta.get("ritmo", 0.88))
            c["_wav"] = w
        pre = c.get("silencio_antes", 0.0)
        dur = max(c.get("min", 0), pre + dur_fala + c.get("respiro", 0.35))
        c["_ini"], c["_dur"], c["_fala_ini"] = t, dur, t + pre
        c["_pal"] = tempos(c.get("tela", c.get("fala", "")), t + pre, dur_fala, c.get("destaques", ())) if c.get("fala") else []
        t += dur
    total = t
    # 2) áudio: ambiente + falas + graves
    audio = ambiente(total) * 0.05
    for c in cenas:
        if c.get("_wav"):
            a, sr = _wav(c["_wav"])
            i = int(c["_fala_ini"] * SR)
            audio[i:i + len(a)] += a[: len(audio) - i]
        if c.get("grave"):
            g = grave()
            i = int((c["_fala_ini"]) * SR)
            audio[i:i + len(g)] += g[: len(audio) - i] * 0.8
    audio = np.clip(audio / max(1e-6, np.abs(audio).max()) * 0.95, -1, 1)
    wav = tmp / f"{meta['id']}-mix.wav"
    with wave.open(str(wav), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((audio * 32767).astype(np.int16).tobytes())
    # 3) vídeo
    saida = pasta / f"{meta['id']}.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-af", "loudnorm=I=-15:TP=-1.5",
           "-shortest", "-movflags", "+faststart", str(saida)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for c in cenas:
        n = int(round(c["_dur"] * FPS))
        for i in range(n):
            tl = i / FPS                      # tempo dentro da cena
            u = i / max(1, n - 1)             # 0..1 da cena
            agora = c["_ini"] + tl
            im = c["desenhar"](tl, u, c)      # devolve Image RGB 1080×1920
            im = vinheta(im, c.get("vinheta", 0.6))
            # flash branco no impacto
            if c.get("grave") and c["_fala_ini"] <= agora < c["_fala_ini"] + 0.12:
                im = Image.blend(im, Image.new("RGB", (W, H), BRANCO), 0.35)
            d = ImageDraw.Draw(im, "RGBA")
            if c.get("hud"):
                hud(d, *c["hud"])
            legenda(d, c["_pal"], agora, y=c.get("leg_y", 1180))
            d.text((W - 230, H - 90), "@montoptcg", font=fonte(28, b"Bold"), fill=(255, 255, 255, 150))
            p.stdin.write(im.tobytes())
    p.stdin.close()
    p.wait()
    print(f"Episódio pronto: {saida} ({total:.1f} s)")
    return saida


if __name__ == "__main__":
    gerar(sys.argv[1])
