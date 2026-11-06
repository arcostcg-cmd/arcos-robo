"""Episódio: a carta que você ganhou desenhando (Pikachu Ilustrador).

Fatos (conferidos em 06/11/2026):
- Concursos de ilustração da revista CoroCoro Comic (anunciado na edição de nov/1997, vencedores em jan/1998;
  mais dois concursos em 1998): 39 cópias da carta "Pikachu Illustrator" distribuídas. (Bulbapedia; Heritage Auctions)
- A única cópia PSA 10 foi leiloada por US$ 16.492.000 na Goldin, em 16/02/2026 (recorde). (Bulbapedia; Pokémon Pricing)
Nenhum Pokémon é desenhado: só bonecos originais e a carta como silhueta dourada.
"""
import math
import random

from PIL import Image, ImageDraw, ImageFilter

import animacao as A
from animacao import Boneco, Pincel, luz, poeira, suave, mix

META = {
    "id": "ep01-pikachu-ilustrador",
    "titulo": "A carta que você ganhou desenhando",
    "ritmo": 0.88,
    "fontes": ["Bulbapedia: Pokémon Illustrator (CoroCoro promo)", "Heritage Auctions (lote 7459-21001)",
               "Pokémon Pricing: maiores vendas (fev/2026)"],
}

GAROTO = Boneco(camisa=(240, 190, 40), bone=(40, 150, 90), calca=(45, 55, 85))
ADULTO = Boneco(camisa=(70, 80, 110), bone=None, cabelo=(45, 35, 30), oculos=True, altura=1.08)

NOITE_TOPO, NOITE_BASE = (16, 20, 48), (28, 22, 46)


def quarto(pc, t):
    pc.fundo(NOITE_TOPO, NOITE_BASE)
    pc.ret(-400, 1380, 1500, 2400, (36, 30, 40))                      # chão
    pc.ret(-400, 1372, 1500, 1392, (24, 20, 30))                      # rodapé
    # janela com lua
    pc.ret(640, 420, 960, 780, (20, 30, 70), raio=10, borda=(60, 50, 60), lw=16)
    pc.circ(860, 520, 46, (230, 230, 210))
    pc.linha([(800, 420), (800, 780)], (60, 50, 60), 12)
    pc.linha([(640, 600), (960, 600)], (60, 50, 60), 12)
    # pôster genérico
    pc.ret(120, 470, 380, 820, (120, 40, 50), raio=6)
    pc.ret(150, 500, 350, 640, (220, 160, 60), raio=4)


def cadeira(pc, x):
    pc.ret(x - 70, 1250, x + 80, 1275, (90, 60, 42), raio=6)
    pc.ret(x - 70, 1060, x - 45, 1390, (90, 60, 42), raio=6)
    pc.ret(x + 55, 1270, x + 80, 1390, (90, 60, 42), raio=6)


def mesa(pc, desenho=0.0):
    pc.ret(380, 1120, 1010, 1160, (110, 75, 50), raio=8)             # tampo
    pc.ret(410, 1160, 440, 1390, (80, 55, 38))
    pc.ret(950, 1160, 980, 1390, (80, 55, 38))
    # abajur
    pc.linha([(900, 1120), (880, 900), (820, 860)], (60, 60, 70), 12)
    pc.poli([(760, 900), (880, 900), (850, 830), (790, 830)], (220, 170, 70))
    # folha de desenho com rabiscos crescendo
    pc.ret(560, 1095, 800, 1122, (245, 245, 235), raio=4)
    for k in range(int(desenho * 8)):
        x = 580 + k * 26
        pc.linha([(x, 1103), (x + 16, 1112)], (40, 90, 200) if k % 2 else (220, 60, 60), 5)


def carta_dourada(pc, x, y, s, t, brilho=1.0):
    """Carta misteriosa: só verso dourado e um '?', sem arte de Pokémon."""
    for k in range(12):
        a = t * 0.6 + k * math.pi / 6
        pc.poli([(x, y), (x + math.cos(a) * 520 * s, y + math.sin(a) * 520 * s),
                 (x + math.cos(a + 0.12) * 520 * s, y + math.sin(a + 0.12) * 520 * s)], (255, 210, 90, int(40 * brilho)))
    pc.ret(x - 120 * s, y - 168 * s, x + 120 * s, y + 168 * s, (230, 175, 40), raio=18 * s,
           borda=(255, 240, 170), lw=10 * s)
    pc.ret(x - 92 * s, y - 138 * s, x + 92 * s, y + 138 * s, (200, 140, 25), raio=10 * s)
    pc.d.text(pc.p(x - 38 * s, y - 92 * s), "?", font=A.fonte(int(pc.r(170 * s)), b"Black"), fill=(255, 240, 180))


def _cena(f):
    def desenhar(tl, u, c):
        return f(tl, u, c)
    return desenhar


# --- 1. 1997, você desenhando
def c1(tl, u, c):
    pc = Pincel((mix(600, 620, suave(u)), mix(1080, 1060, suave(u)), mix(1.45, 1.75, suave(u))))
    quarto(pc, tl)
    cadeira(pc, 470)
    mesa(pc, desenho=u * 0.5)
    mao = 205 + math.sin(tl * 9) * 6
    GAROTO.desenhar(pc, 470, 1390, 1.0, braco_e=(30, 20), braco_d=(mao - 120, -40), sentado=True, olhar=0.8,
                    piscar=(int(tl * 10) % 37 == 0))
    im = luz(pc.final(), 820, 980, 330)
    poeira(ImageDraw.Draw(im, "RGBA"), tl)
    return im


# --- 2. o desafio da revista
def c2(tl, u, c):
    pc = Pincel((540, 900, mix(1.25, 1.4, suave(u))))
    pc.fundo((40, 30, 70), (20, 16, 40))
    ang = math.sin(tl * 1.5) * 2
    pc.ret(170, 380, 910, 1440, (250, 245, 230), raio=16)
    pc.ret(170, 380, 910, 560, (220, 50, 60), raio=16)
    d = pc.d
    d.text(pc.p(220, 420), "CONCURSO", font=A.fonte(int(pc.r(110)), b"Black"), fill=(255, 255, 255))
    d.text(pc.p(220, 600), "DESENHE SUA", font=A.fonte(int(pc.r(76)), b"Black"), fill=(30, 30, 40))
    d.text(pc.p(220, 690), "PRÓPRIA CARTA!", font=A.fonte(int(pc.r(76)), b"Black"), fill=(220, 50, 60))
    # estrela de prêmio pulsando
    r = 120 + 10 * math.sin(tl * 6)
    pts = [(700 + math.cos(k * math.pi / 8 + ang) * (r if k % 2 else r * 0.6),
            1150 + math.sin(k * math.pi / 8 + ang) * (r if k % 2 else r * 0.6)) for k in range(16)]
    pc.poli(pts, (255, 200, 40))
    d.text(pc.p(625, 1110), "PRÊMIO", font=A.fonte(int(pc.r(38)), b"Black"), fill=(120, 40, 20))
    for k in range(5):
        pc.ret(220, 830 + k * 70, 600 - (k % 2) * 90, 856 + k * 70, (200, 200, 195), raio=6)
    return pc.final()


# --- 3. a noite inteira
def c3(tl, u, c):
    pc = Pincel((610, 1070, mix(1.9, 2.1, u)))
    quarto(pc, tl)
    cadeira(pc, 470)
    mesa(pc, desenho=0.5 + u * 0.5)
    # folhas amassadas no chão aparecendo
    for k in range(int(u * 7) + 1):
        rnd = random.Random(k)
        pc.circ(420 + rnd.uniform(-80, 520), 1440 + rnd.uniform(-20, 60), 26, (230, 230, 220))
    mao = 205 + math.sin(tl * 14) * 9
    GAROTO.desenhar(pc, 470, 1390, 1.0, braco_e=(30, 20), braco_d=(mao - 120, -40), sentado=True, olhar=0.9,
                    piscar=(int(tl * 8) % 9 == 0))
    im = luz(pc.final(), 820, 980, 300, forca=0.6)
    # relógio no canto (noite passando)
    d = ImageDraw.Draw(im, "RGBA")
    h = int(mix(23, 29, u)) % 24
    d.text((760, 260), f"{h:02d}:{int(mix(10, 50, u)) % 60:02d}", font=A.fonte(64, b"Bold"), fill=(255, 90, 80))
    return im


# --- 4. correndo até o correio (dia)
def c4(tl, u, c):
    pc = Pincel((mix(260, 780, suave(u)), 1150, 1.55))
    pc.fundo((120, 180, 230), (200, 225, 240))
    for k in range(6):                                          # prédios
        pc.ret(-300 + k * 300, 640 - (k % 3) * 120, -80 + k * 300, 1400, (150 + k * 8, 160, 185), raio=8)
    pc.ret(-400, 1400, 1800, 2400, (120, 120, 130))           # calçada
    pc.ret(880, 1100, 1000, 1400, (210, 40, 40), raio=26)    # caixa de correio vermelha
    pc.ret(900, 1180, 980, 1196, (40, 20, 20))
    x = mix(180, 760, suave(u))
    passo = math.sin(tl * 14) * 28
    GAROTO.desenhar(pc, x, 1400, 1.0, braco_e=(passo, 30), braco_d=(-passo + 40, 60), perna=(passo, -passo),
                    olhar=0.9, boca="sorriso",
                    objeto_mao=lambda pc, mx, my, s: pc.ret(mx - 10, my - 70, mx + 60, my - 20, (245, 240, 220), raio=4))
    return pc.final()


# --- 5. semanas depois: o envelope
def c5(tl, u, c):
    pc = Pincel((560, mix(1300, 1360, u), mix(1.2, 1.6, suave(u))))
    quarto(pc, tl)
    pc.ret(120, 820, 420, 1390, (90, 60, 45), raio=6)          # porta
    pc.circ(380, 1110, 14, (220, 190, 80))
    queda = suave(min(1, tl / 0.9))
    ex, ey = mix(300, 560, queda), mix(1330, 1420, queda)
    pc.ret(ex - 110, ey - 60, ex + 110, ey + 60, (240, 230, 210), raio=8)
    pc.poli([(ex - 110, ey - 60), (ex, ey + 8), (ex + 110, ey - 60)], (220, 205, 180))
    pc.circ(ex, ey + 8, 16, (200, 40, 40))
    return luz(pc.final(), 540, 1500, 260, cor=(255, 230, 190), forca=0.35)


# --- 6. a carta dourada (impacto)
def c6(tl, u, c):
    pc = Pincel((540, 900, mix(1.0, 1.12, suave(u))))
    pc.fundo((30, 20, 50), (10, 8, 20))
    s = mix(0.7, 1.15, suave(min(1, tl / 1.2)))
    carta_dourada(pc, 540, 760, s * 1.3, tl)
    GAROTO.desenhar(pc, 540, 1880, 1.25, braco_e=(150, 20), braco_d=(150, 20), boca="o", olhar=0)
    return luz(pc.final(), 540, 760, 420, cor=(255, 210, 100), forca=0.55)


# --- 7. só 39 crianças
def c7(tl, u, c):
    pc = Pincel((540, 960, 1.0))
    pc.fundo((22, 26, 60), (12, 12, 30))
    n = min(39, int(39 * suave(u * 1.6)) + 1)
    rnd = random.Random(3)
    cores = [(240, 190, 40), (90, 170, 230), (230, 90, 110), (120, 200, 120), (200, 130, 230)]
    for k in range(n):
        col, lin = k % 8, k // 8
        x, y = 120 + col * 122, 620 + lin * 150
        b = Boneco(camisa=rnd.choice(cores), bone=rnd.choice([None, (40, 150, 90), (60, 60, 160)]))
        b.desenhar(pc, x, y + 120, 0.32, braco_e=(20, 10), braco_d=(160, 20), boca="sorriso")
        pc.ret(x + 26, y - 34, x + 52, y + 2, (230, 175, 40), raio=3)
    im = pc.final()
    d = ImageDraw.Draw(im, "RGBA")
    f = A.fonte(220, b"Black")
    d.text(((A.W - d.textlength(str(n), font=f)) / 2, 1440), f"{n}", font=f, fill=(255, 200, 40))
    return im


# --- 8. 2026: o leilão
def c8(tl, u, c):
    pc = Pincel((540, mix(1000, 940, u), mix(1.0, 1.15, suave(u))))
    pc.fundo((40, 10, 20), (12, 6, 10))
    for k in range(9):                                          # plateia (silhuetas)
        x = 60 + k * 125
        pc.circ(x, 1600, 52, (20, 14, 18))
        pc.ret(x - 60, 1640, x + 60, 1900, (20, 14, 18), raio=40)
    ADULTO.desenhar(pc, 540, 1560, 1.25, braco_e=(30, 10), braco_d=(150, 40 + math.sin(tl * 4) * 25), olhar=-0.3,
                    objeto_mao=lambda pc, mx, my, s: pc.ret(mx - 16, my - 70, mx + 16, my + 10, (140, 90, 50), raio=6))
    pc.ret(300, 1180, 780, 1560, (90, 40, 40), raio=8, borda=(20, 10, 10), lw=8)   # púlpito na frente
    pc.ret(360, 1240, 720, 1300, (200, 160, 60), raio=6)
    return luz(pc.final(), 540, 900, 520, cor=(255, 200, 170), forca=0.45)


# --- 9. o valor (silêncio + grave)
def c9(tl, u, c):
    im = Image.new("RGB", (A.W, A.H), (6, 6, 10))
    d = ImageDraw.Draw(im, "RGBA")
    ini = c.get("silencio_antes", 0)
    if tl >= ini:
        k = suave((tl - ini) / 1.0)
        v = 16.49 * k
        txt = f"US$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        f = A.fonte(150, b"Black")
        d.text(((A.W - d.textlength(txt, font=f)) / 2, 700), txt, font=f, fill=(255, 200, 40))
        f2 = A.fonte(110, b"Black")
        d.text(((A.W - d.textlength("MILHÕES", font=f2)) / 2, 880), "MILHÕES", font=f2, fill=A.BRANCO)
    return luz(im, 540, 820, 380, cor=(255, 190, 60), forca=0.3 if tl >= ini else 0)


# --- 10. o nome da carta
def c10(tl, u, c):
    pc = Pincel((540, 860, 1.0))
    pc.fundo((30, 20, 50), (10, 8, 20))
    carta_dourada(pc, 540, 720, 1.35, tl)
    im = luz(pc.final(), 540, 720, 420, cor=(255, 210, 100), forca=0.5)
    d = ImageDraw.Draw(im, "RGBA")
    for k, (txt, tam) in enumerate((("PIKACHU", 120), ("ILUSTRADOR", 96))):
        f = A.fonte(tam, b"Black")
        d.text(((A.W - d.textlength(txt, font=f)) / 2, 1000 + k * 130), txt, font=f, fill=A.BRANCO,
               stroke_width=6, stroke_fill=(0, 0, 0))
    return im


# --- 11. e você?
def c11(tl, u, c):
    pc = Pincel((540, 1120, mix(1.45, 1.65, suave(u))))
    quarto(pc, tl)
    ADULTO.desenhar(pc, 540, 1500, 1.15, braco_e=(30, 10), braco_d=(150, 20), olhar=0, boca="sorriso",
                    objeto_mao=lambda pc, mx, my, s: carta_dourada(pc, mx + 10, my - 120, 0.35, tl, 0.5))
    return luz(pc.final(), 560, 1000, 380)


CENAS = [
    {"desenhar": c1, "hud": ("Japão", "1997"), "fala": "Você tem dez anos. É mil novecentos e noventa e sete, no Japão.",
     "tela": "Você tem 10 anos. É 1997, no Japão.", "destaques": ["JAPÃO"]},
    {"desenhar": c2, "leg_y": 1560, "fala": "Na sua revista favorita, um desafio: desenhe a sua própria carta Pokémon.",
     "destaques": ["DESAFIO", "CARTA"]},
    {"desenhar": c3, "fala": "Você desenha a noite inteira.", "destaques": ["NOITE"], "min": 3.2},
    {"desenhar": c4, "fala": "De manhã, você corre até o correio e manda o desenho.", "destaques": ["CORREIO"]},
    {"desenhar": c5, "silencio_antes": 0.9, "fala": "Semanas depois, chega um envelope com o seu nome.",
     "destaques": ["ENVELOPE"]},
    {"desenhar": c6, "grave": True, "fala": "Dentro, uma carta que nenhuma loja do mundo vendia.",
     "destaques": ["NENHUMA"], "vinheta": 0.5},
    {"desenhar": c7, "fala": "Só trinta e nove crianças ganharam essa carta.", "tela": "Só 39 crianças ganharam essa carta.",
     "destaques": ["39"], "min": 3.6},
    {"desenhar": c8, "hud": ("Leilão", "2026"), "fala": "Quase trinta anos depois, uma delas vai a leilão.",
     "tela": "Quase 30 anos depois, uma delas vai a leilão.", "destaques": ["LEILÃO"]},
    {"desenhar": c9, "silencio_antes": 1.1, "grave": True, "fala": "Dezesseis milhões e meio de dólares.",
     "tela": "16 milhões e meio de dólares.", "destaques": ["MILHÕES"], "min": 3.8, "vinheta": 0.4},
    {"desenhar": c10, "leg_y": 1480, "fala": "É a Pikachu Ilustrador. A carta Pokémon mais cara da história.",
     "destaques": ["HISTÓRIA"]},
    {"desenhar": c11, "fala": "E aí? Você teria vendido? Comenta aqui.", "destaques": ["VENDIDO"], "respiro": 1.2},
]
