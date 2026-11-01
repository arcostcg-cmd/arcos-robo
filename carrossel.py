"""Monta os carrosséis do Arcos TCG (1080×1350) com a identidade da marca.

Cores e fontes seguem a identidade: azul-noite, amarelo ouro, rosa-coral,
roxo e branco; Fredoka nos títulos e Nunito nos textos.
"""
import re
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFont, ImageOps

BASE = Path(__file__).resolve().parent
W, H = 1080, 1350
NAVY, AMARELO, CORAL, ROXO = "#10142E", "#FFD23F", "#FF5D73", "#6C4DFF"
BRANCO, GELO, CINZA = "#FFFFFF", "#F4F5FA", "#4A5276"


def _f(nome, tam):
    return ImageFont.truetype(str(BASE / "fontes" / nome), tam)


def tit(t): return _f("Fredoka-Bold.ttf", t)
def txt(t): return _f("Nunito-ExtraBold.ttf", t)
def txt2(t): return _f("Nunito-Bold.ttf", t)


def reais(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ------------------------------------------------------------ utilidades

def quebrar(d, texto, fonte, largura):
    linhas, atual = [], ""
    for p in texto.split():
        teste = f"{atual} {p}".strip()
        if d.textlength(teste, font=fonte) <= largura:
            atual = teste
        else:
            if atual:
                linhas.append(atual)
            atual = p
    if atual:
        linhas.append(atual)
    return linhas


def escrever(d, xy, texto, fonte, cor, largura, entrelinha=1.18, **kw):
    """Escreve texto quebrado em linhas; devolve o y final."""
    x, y = xy
    alt = int(fonte.size * entrelinha)
    for linha in quebrar(d, texto, fonte, largura):
        d.text((x, y), linha, font=fonte, fill=cor, **kw)
        y += alt
    return y


def caber(d, texto, nome_fonte, largura, altura, maior, menor, entrelinha=1.12):
    """Escolhe o maior tamanho de fonte em que o texto cabe na caixa."""
    for t in range(maior, menor - 1, -4):
        f = _f(nome_fonte, t)
        if len(quebrar(d, texto, f, largura)) * t * entrelinha <= altura:
            return f
    return _f(nome_fonte, menor)


def pilula(d, xy, texto, fonte, fundo, cor, borda=None, pad=(28, 14)):
    x, y = xy
    w = d.textlength(texto, font=fonte)
    caixa = [x, y, x + w + 2 * pad[0], y + fonte.size + 2 * pad[1]]
    d.rounded_rectangle(caixa, radius=999, fill=fundo,
                        outline=borda, width=5 if borda else 0)
    d.text((x + pad[0], y + pad[1] - fonte.size * 0.08), texto, font=fonte, fill=cor)
    return caixa


def logo(img, x, y, escala=1.0, sombra=AMARELO, cor_tcg=CORAL):
    d = ImageDraw.Draw(img)
    f, f2 = tit(int(64 * escala)), tit(int(32 * escala))
    sw, off = max(3, int(7 * escala)), max(3, int(5 * escala))
    d.text((x + off, y + off), "ARCOS", font=f, fill=sombra,
           stroke_width=sw, stroke_fill=sombra)
    d.text((x, y), "ARCOS", font=f, fill=BRANCO, stroke_width=sw, stroke_fill=NAVY)
    lx = x + d.textlength("ARCOS", font=f) + int(18 * escala)
    d.text((lx, y + int(30 * escala)), "TCG", font=f2, fill=cor_tcg,
           stroke_width=max(2, int(5 * escala)), stroke_fill=NAVY)


def colar_foto(img, foto, caixa, modo="cobrir", fundo=GELO, raio=40):
    """Cola a foto dentro da caixa com cantos arredondados e borda."""
    x0, y0, x1, y1 = caixa
    bw, bh = x1 - x0, y1 - y0
    base = Image.new("RGB", (bw, bh), fundo)
    if foto is not None:
        if modo == "cobrir":
            base = ImageOps.fit(foto, (bw, bh), Image.LANCZOS)
        else:  # "conter": mostra o produto inteiro, sem cortar
            f = ImageOps.contain(foto, (bw - 60, bh - 60), Image.LANCZOS)
            base.paste(f, ((bw - f.width) // 2, (bh - f.height) // 2))
    mascara = Image.new("L", (bw, bh), 0)
    ImageDraw.Draw(mascara).rounded_rectangle([0, 0, bw, bh], radius=raio, fill=255)
    img.paste(base, (x0, y0), mascara)
    ImageDraw.Draw(img).rounded_rectangle(caixa, radius=raio, outline=NAVY, width=6)


def numero(d, i, total, cor=CINZA):
    f = txt2(26)
    s = f"{i}/{total}"
    d.text((W - 72 - d.textlength(s, font=f), H - 80), s, font=f, fill=cor)


def salvar(slides, pasta, prefixo):
    pasta.mkdir(parents=True, exist_ok=True)
    caminhos = []
    for i, s in enumerate(slides, 1):
        p = pasta / f"{prefixo}-{i}.jpg"
        s.save(p, "JPEG", quality=85)
        caminhos.append(p)
    return caminhos


def slug(texto):
    s = re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")
    return s[:50] or "post"


# ------------------------------------------------------------ promoção

# ------------------------------------------------------------ curiosidade

def _frases(texto, limite=170):
    """Divide o texto em blocos curtos, sem cortar frases."""
    frases = re.split(r"(?<=[.!?])\s+", texto.strip())
    blocos, atual = [], ""
    for f in frases:
        if atual and len(atual) + len(f) > limite:
            blocos.append(atual)
            atual = f
        else:
            atual = f"{atual} {f}".strip()
    if atual:
        blocos.append(atual)
    return blocos[:5]


CHAMADAS_FINAIS = [
    "Salva pra mostrar na próxima partida",
    "Manda pro amigo que precisa saber disso",
    "Salva e manda pro seu grupo",
    "Marca quem vai dizer \"eu sabia\"",
]


def chamada_final(c):
    """Chamada do último slide: varia por post (novidade) e é sempre um convite, nunca pressão."""
    if c.get("chamada"):
        return c["chamada"]
    return CHAMADAS_FINAIS[sum(map(ord, c["id"])) % len(CHAMADAS_FINAIS)]


# ------------------------------------------------------------ notícia

def _selo_noticia(d, x, y, n):
    if n.get("rumor"):
        return pilula(d, (x, y), "RUMOR · NÃO CONFIRMADO", txt(30), CORAL, NAVY, borda=NAVY)
    return pilula(d, (x, y), "NOTÍCIA", txt(30), ROXO, BRANCO)


# ------------------------------------------------------------ arte em volta da carta real
# A carta (imagem oficial) fica INTACTA no centro; só o fundo é arte generativa do Arcos.
# Sem personagens nem logos de terceiros no fundo: só formas, luz e cores da marca.

ESTILOS_ARTE = ["explosao", "neon", "holo", "halftone"]


def _gradiente(w, h, c1, c2, vertical=True):
    from PIL import Image as _I
    base = _I.new("RGB", (w, h), c1)
    topo = _I.new("RGB", (w, h), c2)
    mask = _I.linear_gradient("L").resize((w, h))
    if not vertical:
        mask = mask.rotate(90, expand=False).resize((w, h))
    return _I.composite(topo, base, mask)


def fundo_arte(w, h, estilo=None, semente=None):
    """Fundo jovem e colorido, gerado por algoritmo (sem custo, sem API)."""
    import math
    import random
    from PIL import ImageFilter
    rnd = random.Random(semente)
    estilo = estilo or "halftone"  # um estilo só: o feed fica coeso
    c1, c2 = "#0E1233", "#3B1E8C"  # paleta fixa do feed: grade harmônica
    img = _gradiente(w, h, c1, c2)
    cam = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(cam)
    cx, cy = w // 2, int(h * 0.45)
    if estilo in ("explosao", "holo"):
        raios = 28 if estilo == "explosao" else 60
        for i in range(raios):
            a1 = 2 * math.pi * i / raios
            a2 = a1 + math.pi / raios * (0.6 if estilo == "explosao" else 0.3)
            r = max(w, h) * 1.2
            cor = (255, 255, 255, 38) if i % 2 else (255, 210, 63, 30)
            d.polygon([(cx, cy), (cx + r * math.cos(a1), cy + r * math.sin(a1)),
                       (cx + r * math.cos(a2), cy + r * math.sin(a2))], fill=cor)
    if estilo == "neon":
        for k in range(9):
            r = 120 + k * 95
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 255, 255, 60 - k * 5), width=6)
    if estilo == "halftone":
        passo = 34
        for y in range(0, h, passo):
            for x in range(0, w, passo):
                dist = math.hypot(x - cx, y - cy) / max(w, h)
                rr = max(1, int(14 * (1 - dist)))
                d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(255, 255, 255, 40))
    # bolhas de luz (bokeh) e brilhos
    for _ in range(22):
        r = rnd.randint(20, 110)
        x, y = rnd.randint(0, w), rnd.randint(0, h)
        cor = rnd.choice([(255, 255, 255, 45), (255, 210, 63, 55), (255, 93, 115, 50), (108, 77, 255, 55)])
        d.ellipse([x - r, y - r, x + r, y + r], fill=cor)
    cam = cam.filter(ImageFilter.GaussianBlur(3))
    d2 = ImageDraw.Draw(cam)
    for _ in range(26):  # estrelinhas
        x, y, s = rnd.randint(0, w), rnd.randint(0, h), rnd.randint(8, 22)
        d2.polygon([(x, y - s), (x + s * 0.25, y - s * 0.25), (x + s, y), (x + s * 0.25, y + s * 0.25),
                    (x, y + s), (x - s * 0.25, y + s * 0.25), (x - s, y), (x - s * 0.25, y - s * 0.25)],
                   fill=(255, 255, 255, 200))
    img = Image.alpha_composite(img.convert("RGBA"), cam)
    return img.convert("RGB")


def colar_carta(fundo, carta, caixa_alt, cy):
    """Carta intacta, com borda branca, brilho e sombra. Devolve a caixa usada."""
    from PIL import ImageFilter
    W_, _ = fundo.size
    carta = carta.convert("RGBA")
    escala = caixa_alt / carta.height
    cw, ch = int(carta.width * escala), int(carta.height * escala)
    if cw > W_ * 0.82:
        escala = W_ * 0.82 / carta.width
        cw, ch = int(carta.width * escala), int(carta.height * escala)
    carta = carta.resize((cw, ch), Image.LANCZOS)
    x, y = (W_ - cw) // 2, cy - ch // 2
    brilho = Image.new("RGBA", fundo.size, (0, 0, 0, 0))
    ImageDraw.Draw(brilho).rounded_rectangle([x - 40, y - 40, x + cw + 40, y + ch + 40], radius=60,
                                             fill=(255, 210, 63, 150))
    brilho = brilho.filter(ImageFilter.GaussianBlur(45))
    sombra = Image.new("RGBA", fundo.size, (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle([x + 18, y + 28, x + cw + 18, y + ch + 28], radius=30,
                                             fill=(0, 0, 0, 140))
    sombra = sombra.filter(ImageFilter.GaussianBlur(18))
    base = Image.alpha_composite(fundo.convert("RGBA"), brilho)
    base = Image.alpha_composite(base, sombra)
    moldura = Image.new("RGBA", (cw + 24, ch + 24), (255, 255, 255, 255))
    m = Image.new("L", moldura.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, cw + 23, ch + 23], radius=28, fill=255)
    base.paste(moldura, (x - 12, y - 12), m)
    mc = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(mc).rounded_rectangle([0, 0, cw - 1, ch - 1], radius=20, fill=255)
    base.paste(carta, (x, y), mc)
    return base.convert("RGB"), (x, y, x + cw, y + ch)


def arte_carta_story(carta, titulo, jogo, credito, rumor=False, semente=None):
    """Story 1080×1920: carta real no centro, arte em volta, título e crédito."""
    SW, SH = 1080, 1920
    img = fundo_arte(SW, SH, semente=semente)
    img, (x0, y0, x1, y1) = colar_carta(img, carta, 820, 830)
    d = ImageDraw.Draw(img)
    logo(img, 72, 220, 0.9)
    selo = "RUMOR · NÃO CONFIRMADO" if rumor else "NOVA CARTA"
    pilula(d, (72, 330), selo, txt(34), CORAL if rumor else AMARELO, BRANCO if rumor else NAVY, borda=NAVY)
    pilula(d, (SW - 72 - d.textlength(jogo.upper()[:20], font=txt(30)) - 56, 330), jogo.upper()[:20], txt(30), BRANCO, NAVY)
    t = ("Rumor: " + titulo) if rumor and not titulo.lower().startswith("rumor") else titulo
    ft = caber(d, t, "Fredoka-Bold.ttf", SW - 144, 190, 84, 46, 1.05)
    yt = escrever(d, (72, y1 + 45), t, ft, BRANCO, SW - 144, 1.05, stroke_width=6, stroke_fill=NAVY)
    yc = max(yt + 20, 1490)
    d.text((72, yc), f"Imagem: {credito}"[:70], font=txt2(30), fill=BRANCO, stroke_width=3, stroke_fill=NAVY)
    d.text((72, yc + 45), "Link e detalhes no nosso Telegram", font=txt2(30), fill=AMARELO, stroke_width=3, stroke_fill=NAVY)
    return img


def arte_carta_post(carta, titulo, jogo, credito, rumor=False, semente=None):
    """Capa de carrossel 1080×1350 com a carta real e arte em volta."""
    img = fundo_arte(W, H, semente=semente)
    img, (x0, y0, x1, y1) = colar_carta(img, carta, 820, 640)
    d = ImageDraw.Draw(img)
    logo(img, 72, 60, 0.8)
    selo = "RUMOR · NÃO CONFIRMADO" if rumor else "NOVA CARTA"
    pilula(d, (W - 72 - d.textlength(selo, font=txt(30)) - 56, 70), selo, txt(30),
           CORAL if rumor else AMARELO, BRANCO if rumor else NAVY, borda=NAVY)
    t = ("Rumor: " + titulo) if rumor and not titulo.lower().startswith("rumor") else titulo
    ft = caber(d, t, "Fredoka-Bold.ttf", W - 144, 200, 72, 44, 1.05)
    escrever(d, (72, y1 + 40), t, ft, BRANCO, W - 144, 1.05, stroke_width=5, stroke_fill=NAVY)
    d.text((72, H - 70), f"Imagem: {credito}"[:70], font=txt2(26), fill=BRANCO, stroke_width=3, stroke_fill=NAVY)
    return img


# ------------------------------------------------------------ identidade única do feed
# Todo post do feed usa a MESMA base (noite azul → roxo, pontilhado suave, brilhos),
# o mesmo enquadramento (logo em cima à esquerda, selo à direita, número embaixo)
# e uma cor de destaque por tipo de conteúdo. Assim a grade fica harmônica.

NOITE1, NOITE2 = "#0E1233", "#3B1E8C"
SUAVE = "#C9CEE6"
ACENTO = {"curiosidade": AMARELO, "promocao": CORAL, "noticia": "#9C86FF", "rumor": CORAL}


def fundo_feed(w=W, h=H, acento=AMARELO, semente="arcos", claro=False):
    """Base visual de todos os posts: gradiente fixo da marca + textura e brilhos discretos."""
    import math
    import random
    from PIL import ImageFilter
    rnd = random.Random(semente)
    img = _gradiente(w, h, NOITE1 if not claro else NOITE2, NOITE2 if not claro else "#5B2FC9")
    cam = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(cam)
    cx, cy = int(w * 0.85), int(h * 0.12)
    passo = 36
    for y in range(0, h, passo):
        for x in range(0, w, passo):
            dist = math.hypot(x - cx, y - cy) / max(w, h)
            rr = int(9 * max(0, 1 - dist * 1.4))
            if rr:
                d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(255, 255, 255, 22))
    ac = ImageColor.getrgb(acento)
    for _ in range(9):
        r = rnd.randint(60, 180)
        x, y = rnd.randint(-80, w + 80), rnd.randint(-80, h + 80)
        cor = rnd.choice([(*ac, 46), (108, 77, 255, 52), (255, 255, 255, 18)])
        d.ellipse([x - r, y - r, x + r, y + r], fill=cor)
    cam = cam.filter(ImageFilter.GaussianBlur(28))
    d2 = ImageDraw.Draw(cam)
    for _ in range(14):
        x, y, s = rnd.randint(0, w), rnd.randint(0, h), rnd.randint(7, 18)
        d2.polygon([(x, y - s), (x + s * 0.25, y - s * 0.25), (x + s, y), (x + s * 0.25, y + s * 0.25),
                    (x, y + s), (x - s * 0.25, y + s * 0.25), (x - s, y), (x - s * 0.25, y - s * 0.25)],
                   fill=(255, 255, 255, 170))
    return Image.alpha_composite(img.convert("RGBA"), cam).convert("RGB")


def moldura_foto(img, foto, caixa, modo="cobrir", acento=AMARELO):
    """Foto com borda branca, brilho na cor de destaque e sombra (mesmo estilo das cartas)."""
    from PIL import ImageFilter
    x0, y0, x1, y1 = caixa
    base = img.convert("RGBA")
    brilho = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(brilho).rounded_rectangle([x0 - 30, y0 - 30, x1 + 30, y1 + 30], radius=70,
                                             fill=(*ImageColor.getrgb(acento), 110))
    base = Image.alpha_composite(base, brilho.filter(ImageFilter.GaussianBlur(40)))
    sombra = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle([x0 + 14, y0 + 22, x1 + 14, y1 + 22], radius=44,
                                             fill=(0, 0, 0, 130))
    base = Image.alpha_composite(base, sombra.filter(ImageFilter.GaussianBlur(16))).convert("RGB")
    ImageDraw.Draw(base).rounded_rectangle([x0 - 12, y0 - 12, x1 + 12, y1 + 12], radius=48, fill=BRANCO)
    colar_foto(base, foto, caixa, modo=modo, fundo=BRANCO, raio=38)
    ImageDraw.Draw(base).rounded_rectangle(caixa, radius=38, outline=BRANCO, width=2)
    return base


def cabecalho(img, selo, acento, cor_selo=NAVY):
    d = ImageDraw.Draw(img)
    logo(img, 72, 60, 0.8)
    f = txt(28)
    pilula(d, (W - 72 - d.textlength(selo, font=f) - 56, 70), selo, f, acento, cor_selo)
    return d


def rodape(d, i, total, texto="Arrasta pro lado »", acento=AMARELO):
    if texto:
        d.text((72, H - 84), texto, font=txt(32), fill=acento)
    numero(d, i, total, SUAVE)


def destaque(d, x, y, largura, acento):
    d.rounded_rectangle([x, y, x + largura, y + 14], radius=7, fill=acento)


def titulo_grande(d, xy, texto, largura, altura, maior, menor, acento=AMARELO):
    f = caber(d, texto, "Fredoka-Bold.ttf", largura, altura, maior, menor, 1.02)
    return escrever(d, xy, texto, f, BRANCO, largura, 1.02, stroke_width=max(4, f.size // 14),
                    stroke_fill=NOITE1)


def slide_texto(bloco, i, total, acento, semente, selo="ARCOS TCG"):
    s = fundo_feed(acento=acento, semente=semente)
    d = cabecalho(s, selo, acento)
    f_b = caber(d, bloco, "Nunito-ExtraBold.ttf", W - 144, 820, 84, 40, 1.25)
    alt = len(quebrar(d, bloco, f_b, W - 144)) * int(f_b.size * 1.25)
    y = max(260, (H - alt) // 2 - 20)
    destaque(d, 72, y - 50, 120, acento)
    escrever(d, (72, y), bloco, f_b, BRANCO, W - 144, 1.25)
    rodape(d, i, total, "Continua »" if i < total else None, acento)
    return s


def foto_cheia(foto, acento=AMARELO, semente="x", escuro_de=0.38):
    """Foto ocupando o slide inteiro, com degradê escuro embaixo para o texto ler bem."""
    if foto is None:
        return fundo_feed(acento=acento, semente=semente)
    base = ImageOps.fit(foto.convert("RGB"), (W, H), Image.LANCZOS)
    veu = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dv = ImageDraw.Draw(veu)
    r, g, b = ImageColor.getrgb(NOITE1)
    ini = int(H * escuro_de)
    for y in range(ini, H):
        a = int(235 * ((y - ini) / (H - ini)) ** 0.85)
        dv.line([(0, y), (W, y)], fill=(r, g, b, a))
    dv.rectangle([0, 0, W, 170], fill=(r, g, b, 70))  # leitura do logo e do selo
    return Image.alpha_composite(base.convert("RGBA"), veu).convert("RGB")


def _texto_rodape(d, texto, acento, maior=92, menor=54, topo=None):
    """Texto grande na parte de baixo do slide (área escura do degradê)."""
    f = caber(d, texto, "Fredoka-Bold.ttf", W - 144, 430, maior, menor, 1.05)
    linhas = quebrar(d, texto, f, W - 144)
    alt = len(linhas) * int(f.size * 1.05)
    y = topo if topo is not None else H - 150 - alt
    destaque(d, 72, y - 40, 120, acento)
    escrever(d, (72, y), texto, f, BRANCO, W - 144, 1.05, stroke_width=max(3, f.size // 18),
             stroke_fill=NOITE1)


def carrossel_curiosidade(c, fotos, pasta, cartas=None):
    """Carrossel visual: cada slide é uma imagem (foto livre ou carta oficial) com pouco texto.

    fotos  = lista de retornos de imagens.buscar_commons_varias (ou um único dict, ou None)
    cartas = lista de {"imagem": PIL.Image, "credito": str} de fontes OFICIAIS (opcional)
    """
    if isinstance(fotos, dict):
        fotos = [fotos]
    fotos, cartas = list(fotos or []), list(cartas or [])
    ac = ACENTO["curiosidade"]
    blocos = _frases(c["texto"], limite=110)
    total = 1 + len(blocos) + 1
    capa = c.get("gancho") or c["titulo"]
    sem = c["id"]
    selo = f"VOCÊ SABIA? · {c['jogo'].upper()}"[:34]
    visuais = [("carta", x) for x in cartas] + [("foto", x) for x in fotos]

    def visual(k):
        return visuais[k % len(visuais)] if visuais else (None, None)

    def montar(k):
        tipo, v = visual(k)
        if tipo == "carta":
            img, _ = colar_carta(fundo_feed(acento=ac, semente=f"{sem}{k}"), v["imagem"], 760, 560)
            return img
        return foto_cheia(v["imagem"] if v else None, ac, f"{sem}{k}")

    slides = []
    s = montar(0)
    d = cabecalho(s, selo, ac)
    _texto_rodape(d, capa, ac, 120, 64)
    rodape(d, 1, total, "Arrasta pro lado »", ac)
    slides.append(s)

    for i, b in enumerate(blocos, 2):
        s = montar(i - 1)
        d = cabecalho(s, selo, ac)
        _texto_rodape(d, b, ac, 76, 46)
        rodape(d, i, total, "Continua »", ac)
        slides.append(s)

    s = montar(total - 1) if len(visuais) > 1 else fundo_feed(acento=CORAL, semente=sem + "x", claro=True)
    if len(visuais) > 1:  # escurece mais para a chamada final
        s = Image.blend(s, fundo_feed(acento=CORAL, semente=sem + "x", claro=True), 0.55)
    d = cabecalho(s, "ARCOS TCG", ac)
    y = titulo_grande(d, (72, 230), chamada_final(c), W - 144, 400, 108, 60)
    if c.get("pergunta"):
        y = escrever(d, (72, y + 50), "Comenta aí: " + c["pergunta"], txt(46), ac, W - 144, 1.2)
    pilula(d, (72, max(740, y + 60)), "Promoções verificadas no Telegram · link na bio", txt(30), BRANCO, NOITE1)
    data = datetime.fromisoformat(c["verificado_em"]).strftime("%d/%m/%Y")
    creditos = [f"Texto: Arcos TCG, com base em {c['fonte_nome']} (conferido em {data})"]
    creditos += [x["credito"] for x in cartas] + [x["credito"] for x in fotos]
    vistos, cred_unicos = set(), []
    for cr in creditos:
        if cr not in vistos:
            vistos.add(cr)
            cred_unicos.append(cr)
    yy = 1000
    for cr in cred_unicos[:5]:
        yy = escrever(d, (72, yy), cr, txt2(24), BRANCO, W - 144) + 4
    rodape(d, total, total, None)
    slides.append(s)
    return salvar(slides, pasta, f"cur-{c['id']}"), cred_unicos


def carrossel_promocao(o, foto, pasta):
    """o = oferta aprovada pelo robô; foto = PIL.Image da loja ou None."""
    ac = ACENTO["promocao"]
    total = 4
    desc = round((1 - o["preco"] / o["ref"]) * 100)
    hora = datetime.fromisoformat(o["visto"]).strftime("%d/%m às %H:%M")
    sem = f"{o['produto']}{o['loja']}"
    slides = []

    s = fundo_feed(acento=ac, semente=sem)
    s = moldura_foto(s, foto, (120, 190, W - 120, 790), modo="conter", acento=ac)
    d = cabecalho(s, "PROMOÇÃO VERIFICADA", ac)
    d.text((72, 850), f"{o['jogo']} · {o['descricao']}".upper()[:46], font=txt(28), fill=AMARELO)
    f_nome = caber(d, o["produto"], "Fredoka-Bold.ttf", W - 144, 150, 62, 38)
    escrever(d, (72, 895), o["produto"], f_nome, BRANCO, W - 144, 1.06)
    fp = tit(104)
    preco = reais(o["preco"])
    pw = d.textlength(preco, font=fp)
    d.rounded_rectangle([72, 1090, 72 + pw + 64, 1232], radius=30, fill=AMARELO)
    d.text((104, 1100), preco, font=fp, fill=NOITE1)
    pilula(d, (72 + pw + 94, 1124), f"−{desc}%", tit(54), ac, BRANCO)
    numero(d, 1, total, SUAVE)
    slides.append(s)

    s = fundo_feed(acento=ac, semente=sem + "2")
    d = cabecalho(s, "QUANTO VOCÊ ECONOMIZA", ac)
    d.text((72, 230), "Preço normal", font=txt(40), fill=SUAVE)
    fr = tit(96)
    ref = reais(o["ref"])
    d.text((72, 290), ref, font=fr, fill=SUAVE)
    rw = d.textlength(ref, font=fr)
    d.line([72, 350, 72 + rw, 350], fill=ac, width=10)
    d.text((72, 480), "Agora", font=txt(40), fill=BRANCO)
    d.text((72, 530), reais(o["preco"]), font=tit(150), fill=AMARELO, stroke_width=6, stroke_fill=NOITE1)
    eco = reais(o["ref"] - o["preco"])
    pilula(d, (72, 760), f"Economia de {eco} (−{desc}%)", tit(46), ac, BRANCO)
    if o.get("cupom") and o.get("preco_final", o["preco"]) < o["preco"]:
        d.text((72, 870), f"Com o cupom {o['cupom']['codigo']}: {reais(o['preco_final'])}",
               font=tit(50), fill=AMARELO)
    escrever(d, (72, 990), "Preço normal = mediana dos preços que o robô registrou nas lojas "
             "verificadas nos últimos 30 dias.", txt2(32), SUAVE, W - 144)
    numero(d, 2, total, SUAVE)
    slides.append(s)

    s = fundo_feed(acento=ac, semente=sem + "3")
    d = cabecalho(s, "LOJA VERIFICADA", ac)
    d.ellipse([72, 220, 212, 360], fill=AMARELO)
    d.line([(108, 292), (134, 320), (182, 262)], fill=NOITE1, width=16, joint="curve")
    escrever(d, (72, 400), o["loja_nome"], tit(80), BRANCO, W - 144, 1.05)
    y = 620
    for item in ["CNPJ ativo e contato real", "Boa reputação de atendimento",
                 "Produto oficial e lacrado", f"Preço conferido em {hora}"]:
        d.ellipse([72, y + 12, 100, y + 40], fill=ac)
        d.text((124, y), item, font=txt(40), fill=BRANCO)
        y += 92
    escrever(d, (72, 1080), "Preço e estoque podem mudar a qualquer momento.", txt2(30), SUAVE, W - 144)
    numero(d, 3, total, SUAVE)
    slides.append(s)

    s = fundo_feed(acento=ac, semente=sem + "4", claro=True)
    d = cabecalho(s, "ARCOS TCG", ac)
    titulo_grande(d, (72, 220), "O link está no nosso Telegram", W - 144, 380, 104, 60)
    pilula(d, (72, 620), "Link na bio »", tit(54), AMARELO, NOITE1)
    d.text((72, 760), "Salva e manda pro seu grupo", font=txt(42), fill=BRANCO)
    if o.get("cupom"):
        pilula(d, (72, 850), f"CUPOM {o['cupom']['codigo']}", tit(54), BRANCO, NOITE1)
        d.text((72, 960), o["cupom"].get("descricao", "desconto extra")[:50], font=txt(32), fill=BRANCO)
    creditos = [f"Imagem do produto: {o['loja_nome']}"]
    if o.get("afiliado"):
        creditos.append("Link de afiliado")
    y = 1100
    for c in creditos:
        d.text((72, y), c, font=txt2(30), fill=SUAVE)
        y += 44
    numero(d, 4, total, SUAVE)
    slides.append(s)

    nome = f"promo-{slug(o['produto'])}-{o['loja']}-{int(o['preco']*100)}"
    return salvar(slides, pasta, nome), creditos


def carrossel_noticia(n, pasta):
    """Carrossel 1080×1350 do destaque do dia: capa, resumo, fonte."""
    rumor = bool(n.get("rumor"))
    ac = ACENTO["rumor" if rumor else "noticia"]
    sem = n["titulo"]
    selo = (f"RUMOR · NÃO CONFIRMADO" if rumor else f"NOTÍCIA · {n['jogo'].upper()[:20]}")
    slides = []
    s = fundo_feed(acento=ac, semente=sem)
    d = cabecalho(s, selo, ac, NOITE1 if not rumor else BRANCO)
    d.text((72, 230), n["jogo"].upper()[:30], font=txt(34), fill=AMARELO)
    destaque(d, 72, 300, 120, ac)
    titulo_grande(d, (72, 340), n["titulo"], W - 144, 760, 130, 64)
    rodape(d, 1, 3, "Arrasta pro lado »", ac)
    slides.append(s)
    slides.append(slide_texto(n["resumo"], 2, 3, ac, sem + "2", "RESUMO"))
    s = fundo_feed(acento=ac, semente=sem + "3")
    d = cabecalho(s, "FONTE", ac, NOITE1 if not rumor else BRANCO)
    destaque(d, 72, 250, 120, ac)
    escrever(d, (72, 290), n["fonte"], tit(76), BRANCO, W - 144, 1.05)
    dominio = re.sub(r"^https?://(www\.)?", "", n["link"]).split("/")[0]
    d.text((72, 640), dominio, font=txt(40), fill=SUAVE)
    escrever(d, (72, 880), "Notícia resumida pelo Arcos. Link completo no nosso Telegram.", txt(42), AMARELO, W - 144)
    rodape(d, 3, 3, None)
    slides.append(s)
    return salvar(slides, pasta, f"news-{slug(n['titulo'])}")


def story_noticia(n, pasta):
    """Story 1080×1920. Texto importante longe das bordas (250 px em cima, 340 embaixo)."""
    SW, SH = 1080, 1920
    rumor = bool(n.get("rumor"))
    ac = ACENTO["rumor" if rumor else "noticia"]
    s = fundo_feed(SW, SH, acento=ac, semente=n["titulo"])
    d = ImageDraw.Draw(s)
    logo(s, 72, 260, 1.0)
    pilula(d, (72, 400), n["jogo"].upper()[:30], txt(32), AMARELO, NOITE1)
    _selo_noticia(d, 72, 490, n)
    f_t = caber(d, n["titulo"], "Fredoka-Bold.ttf", SW - 144, 520, 120, 64, 1.02)
    y = escrever(d, (72, 620), n["titulo"], f_t, BRANCO, SW - 144, 1.02, stroke_width=5, stroke_fill=NOITE1)
    f_r = caber(d, n["resumo"], "Nunito-ExtraBold.ttf", SW - 144, 1500 - y - 60, 48, 32, 1.3)
    escrever(d, (72, y + 50), n["resumo"], f_r, "#E3E6F7", SW - 144, 1.3)
    d.text((72, 1520), f"Fonte: {n['fonte']}"[:60], font=txt2(32), fill=AMARELO)
    d.text((72, 1570), "Link da fonte no nosso Telegram", font=txt2(30), fill=SUAVE)
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"news-{slug(n['titulo'])}.jpg"
    s.save(caminho, "JPEG", quality=85)
    return caminho


# ------------------------------------------------------------ série Top 10 (contagem regressiva)

def _carta_nitida(img, altura):
    """Amplia a imagem oficial com cuidado (no máximo 2,2x) e devolve nítida."""
    from PIL import ImageFilter
    img = img.convert("RGBA")
    esc = min(altura / img.height, 2.2)
    img = img.resize((int(img.width * esc), int(img.height * esc)), Image.LANCZOS)
    return img.filter(ImageFilter.UnsharpMask(radius=1.6, percent=90, threshold=2))


def _posicao(d, x, y, pos, acento):
    f = tit(150)
    t = f"{pos}º"
    d.text((x + 8, y + 8), t, font=f, fill=NOITE1)
    d.text((x, y), t, font=f, fill=acento, stroke_width=8, stroke_fill=NOITE1)


def _preco(d, xy, texto, centro=True):
    f = tit(76)
    w = d.textlength(texto, font=f)
    x, y = xy
    if centro:
        x = (W - w) // 2 - 30
    d.rounded_rectangle([x, y, x + w + 60, y + 110], radius=30, fill=AMARELO)
    d.text((x + 30, y + 10), texto, font=f, fill=NOITE1)


def carrossel_top10(top, imagens_cartas, pasta, prefixo):
    """top = {titulo, gancho, jogo, fonte_preco, data, nota, itens:[{pos, nome, numero, preco}]}
    imagens_cartas = {pos: PIL.Image} (só imagem OFICIAL). Instagram aceita 10 imagens:
    capa, 10º e 9º juntos, 8º ao 2º, e o 1º revelado no fim.
    """
    ac = AMARELO
    itens = {i["pos"]: i for i in top["itens"]}
    sem = prefixo
    rodape_txt = f"Preço: {top['fonte_preco'].split(' (')[0]} · {top['data']} · Imagem: The Pokémon Company"
    slides = []

    def base(k):
        return fundo_feed(acento=[AMARELO, CORAL, "#9C86FF"][k % 3], semente=f"{sem}{k}")

    def credito(d):
        d.text((72, H - 64), rodape_txt[:80], font=txt2(22), fill=SUAVE)

    # capa: o 1º lugar escondido (silhueta escura) + pergunta
    s = base(0)
    um = _carta_nitida(imagens_cartas[1], 700)
    silh = Image.new("RGBA", um.size, (14, 18, 51, 255))
    silh.putalpha(um.split()[-1])
    s, cx = colar_carta(s, silh.convert("RGB"), 640, 520)
    d = cabecalho(s, f"TOP 10 · {top['jogo'].upper()}", ac)
    f_q = tit(220)
    q = "?"
    d.text(((W - d.textlength(q, font=f_q)) // 2, 380), q, font=f_q, fill=AMARELO, stroke_width=10, stroke_fill=NOITE1)
    _texto_rodape(d, top["gancho"], ac, 92, 54, topo=900)
    rodape(d, 1, 10, "Arrasta e descobre o nº 1 »", ac)
    slides.append(s)

    # 10º e 9º lado a lado
    s = base(1)
    for j, pos in enumerate((10, 9)):
        c = _carta_nitida(imagens_cartas[pos], 600)
        c = ImageOps.contain(c, (430, 600), Image.LANCZOS)
        x0 = 90 + j * 480
        caixa = Image.new("RGBA", (c.width + 20, c.height + 20), (255, 255, 255, 255))
        s.paste(caixa.convert("RGB"), (x0 - 10, 330 - 10))
        s.paste(c, (x0, 330), c)
        d = ImageDraw.Draw(s)
        d.text((x0, 190), f"{pos}º", font=tit(110), fill=AMARELO, stroke_width=7, stroke_fill=NOITE1)
        it = itens[pos]
        escrever(d, (x0, 960), it["nome"], txt(34), BRANCO, 430, 1.1)
        d.text((x0, 1050), it["preco"], font=tit(58), fill=AMARELO, stroke_width=4, stroke_fill=NOITE1)
    cabecalho(s, f"TOP 10 · {top['jogo'].upper()}", ac)
    credito(d)
    numero(d, 2, 10, SUAVE)
    slides.append(s)

    # 8º ao 1º
    for k, pos in enumerate(range(8, 0, -1), 3):
        it = itens[pos]
        s = base(k)
        s, (x0, y0, x1, y1) = colar_carta(s, _carta_nitida(imagens_cartas[pos], 720), 720, 600)
        d = cabecalho(s, "O Nº 1!" if pos == 1 else f"TOP 10 · {top['jogo'].upper()}", ac)
        _posicao(d, 72, 150, pos, ac)
        escrever(d, (72, y1 + 34), f"{it['nome']} · {it['numero']}", txt(40), BRANCO, W - 144, 1.1)
        _preco(d, (0, y1 + 100), it["preco"])
        credito(d)
        numero(d, k, 10, SUAVE)
        slides.append(s)
    return salvar(slides, pasta, prefixo)
