"""Monta os carrosséis do Arcos TCG (1080×1350) com a identidade da marca.

Cores e fontes seguem a identidade: azul-noite, amarelo ouro, rosa-coral,
roxo e branco; Fredoka nos títulos e Nunito nos textos.
"""
import re
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

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

def carrossel_promocao(o, foto, pasta):
    """o = oferta aprovada pelo robô; foto = PIL.Image da loja ou None."""
    total = 4
    desc = round((1 - o["preco"] / o["ref"]) * 100)
    hora = datetime.fromisoformat(o["visto"]).strftime("%d/%m às %H:%M")
    slides = []

    # 1. capa
    s = Image.new("RGB", (W, H), BRANCO)
    d = ImageDraw.Draw(s)
    logo(s, 64, 56, 0.9)
    pilula(d, (W - 470, 66), "PROMOÇÃO VERIFICADA", txt(26), ROXO, BRANCO)
    colar_foto(s, foto, (64, 180, W - 64, 820), modo="conter")
    d.text((64, 860), f"{o['jogo']} · {o['descricao']}".upper()[:48], font=txt(28), fill=ROXO)
    f_nome = caber(d, o["produto"], "Fredoka-Bold.ttf", W - 128, 170, 64, 40)
    escrever(d, (64, 905), o["produto"], f_nome, NAVY, W - 128, 1.08)
    fp = tit(100)
    preco = reais(o["preco"])
    pw = d.textlength(preco, font=fp)
    d.rounded_rectangle([72, 1110, 72 + pw + 60, 1250], radius=28, fill=NAVY)
    d.rounded_rectangle([64, 1100, 64 + pw + 60, 1240], radius=28, fill=AMARELO,
                        outline=NAVY, width=6)
    d.text((94, 1112), preco, font=fp, fill=NAVY)
    pilula(d, (64 + pw + 90, 1132), f"−{desc}%", tit(54), CORAL, NAVY, borda=NAVY)
    numero(d, 1, total)
    slides.append(s)

    # 2. comparação de preço
    s = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(s)
    d.text((72, 90), "QUANTO VOCÊ ECONOMIZA", font=txt(32), fill=AMARELO)
    d.text((72, 200), "Preço normal", font=txt(40), fill="#C9CEE6")
    fr = tit(96)
    ref = reais(o["ref"])
    d.text((72, 260), ref, font=fr, fill="#C9CEE6")
    rw = d.textlength(ref, font=fr)
    d.line([72, 318, 72 + rw, 318], fill=CORAL, width=10)
    d.text((72, 450), "Agora", font=txt(40), fill=BRANCO)
    d.text((72, 505), reais(o["preco"]), font=tit(150), fill=AMARELO,
           stroke_width=8, stroke_fill=NAVY)
    eco = reais(o["ref"] - o["preco"])
    pilula(d, (72, 730), f"Economia de {eco} (−{desc}%)", tit(48), CORAL, NAVY)
    if o.get("cupom") and o.get("preco_final", o["preco"]) < o["preco"]:
        d.text((72, 840), f"Com o cupom {o['cupom']['codigo']}: {reais(o['preco_final'])}",
               font=tit(52), fill=AMARELO)
    escrever(d, (72, 960),
             "Preço normal = mediana dos preços que o robô registrou nas lojas "
             "verificadas nos últimos 30 dias.", txt2(32), "#C9CEE6", W - 144)
    numero(d, 2, total, "#C9CEE6")
    slides.append(s)

    # 3. loja verificada
    s = Image.new("RGB", (W, H), ROXO)
    d = ImageDraw.Draw(s)
    d.ellipse([72, 100, 232, 260], fill=BRANCO, outline=NAVY, width=8)
    d.line([(112, 182), (142, 214), (196, 146)], fill=ROXO, width=18, joint="curve")
    escrever(d, (72, 310), f"{o['loja_nome']}", tit(84), BRANCO, W - 144, 1.05)
    d.text((72, 520), "Loja verificada pelo Arcos", font=txt(40), fill=AMARELO)
    y = 620
    for item in ["CNPJ ativo e contato real", "Boa reputação de atendimento",
                 "Produto oficial e lacrado", f"Preço conferido em {hora}"]:
        d.ellipse([72, y + 12, 100, y + 40], fill=AMARELO)
        d.text((124, y), item, font=txt(40), fill=BRANCO)
        y += 92
    escrever(d, (72, 1080), "Preço e estoque podem mudar a qualquer momento.",
             txt2(30), "#E4DEFF", W - 144)
    numero(d, 3, total, "#E4DEFF")
    slides.append(s)

    # 4. chamada e créditos
    s = Image.new("RGB", (W, H), AMARELO)
    d = ImageDraw.Draw(s)
    escrever(d, (72, 150), "O link está no nosso Telegram", tit(104), NAVY, W - 144, 1.0)
    pilula(d, (72, 560), "Link na bio »", tit(56), NAVY, AMARELO)
    d.text((72, 720), "Salva e manda pro seu grupo", font=txt(44), fill=NAVY)
    if o.get("cupom"):
        pilula(d, (72, 820), f"CUPOM {o['cupom']['codigo']}", tit(56), BRANCO, NAVY, borda=NAVY)
        d.text((72, 930), o["cupom"].get("descricao", "desconto extra")[:50], font=txt(32), fill=NAVY)
    creditos = [f"Imagem do produto: {o['loja_nome']}"]
    if o.get("afiliado"):
        creditos.append("Link de afiliado")
    y = 1000
    for c in creditos:
        d.text((72, y), c, font=txt2(30), fill=NAVY)
        y += 44
    logo(s, 72, 1150, 1.0, sombra=CORAL, cor_tcg=CORAL)
    numero(d, 4, total, NAVY)
    slides.append(s)

    nome = f"promo-{slug(o['produto'])}-{o['loja']}-{int(o['preco']*100)}"
    return salvar(slides, pasta, nome), creditos


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


def carrossel_curiosidade(c, foto_info, pasta):
    """c = item de curiosidades.yaml; foto_info = retorno de buscar_commons ou None."""
    blocos = _frases(c["texto"])
    total = 1 + len(blocos) + 2
    capa = c.get("gancho") or c["titulo"]
    slides = []

    # 1. capa
    s = Image.new("RGB", (W, H), AMARELO)
    d = ImageDraw.Draw(s)
    pilula(d, (72, 72), f"VOCÊ SABIA? · {c['jogo'].upper()}", txt(30), NAVY, AMARELO)
    if foto_info:
        colar_foto(s, foto_info["imagem"], (72, 190, W - 72, 760))
        f_t = caber(d, capa, "Fredoka-Bold.ttf", W - 144, 360, 110, 60, 1.0)
        escrever(d, (72, 800), capa, f_t, BRANCO, W - 144, 1.0,
                 stroke_width=8, stroke_fill=NAVY)
    else:
        f_t = caber(d, capa, "Fredoka-Bold.ttf", W - 144, 760, 150, 80, 1.0)
        escrever(d, (72, 260), capa, f_t, BRANCO, W - 144, 1.0,
                 stroke_width=10, stroke_fill=NAVY)
    d.text((72, 1220), "Arrasta pro lado »", font=txt(36), fill=NAVY)
    numero(d, 1, total, NAVY)
    slides.append(s)

    # 2.. texto
    for i, b in enumerate(blocos, 2):
        s = Image.new("RGB", (W, H), BRANCO)
        d = ImageDraw.Draw(s)
        d.rounded_rectangle([72, 90, 200, 110], radius=10, fill=CORAL)
        f_b = caber(d, b, "Nunito-ExtraBold.ttf", W - 144, 900, 88, 40, 1.25)
        alt = len(quebrar(d, b, f_b, W - 144)) * int(f_b.size * 1.25)
        escrever(d, (72, max(200, (H - alt) // 2 - 40)), b, f_b, NAVY, W - 144, 1.25)
        logo(s, 72, 1180, 0.7)
        numero(d, i, total)
        slides.append(s)

    # fonte
    s = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(s)
    d.text((72, 120), "FONTE", font=txt(36), fill=AMARELO)
    escrever(d, (72, 200), c["fonte_nome"], tit(80), BRANCO, W - 144, 1.05)
    dominio = re.sub(r"^https?://(www\.)?", "", c["fonte_url"]).split("/")[0]
    d.text((72, 560), dominio, font=txt(40), fill="#C9CEE6")
    data = datetime.fromisoformat(c["verificado_em"]).strftime("%d/%m/%Y")
    d.text((72, 640), f"Conferido em {data}", font=txt2(34), fill="#C9CEE6")
    escrever(d, (72, 900), "No Arcos, toda curiosidade tem fonte. Nada de boato.",
             txt(46), AMARELO, W - 144)
    numero(d, total - 1, total, "#C9CEE6")
    slides.append(s)

    # créditos e chamada
    s = Image.new("RGB", (W, H), CORAL)
    d = ImageDraw.Draw(s)
    y_cta = escrever(d, (72, 150), chamada_final(c), tit(100), BRANCO, W - 144, 1.0,
                     stroke_width=8, stroke_fill=NAVY)
    if c.get("pergunta"):
        y_cta = escrever(d, (72, y_cta + 40), "Comenta aí: " + c["pergunta"], txt(44), NAVY, W - 144, 1.2)
    d.text((72, max(620, y_cta + 40)), "Promoções verificadas no Telegram · link na bio",
           font=txt(36), fill=NAVY)
    creditos = [f"Texto: Arcos TCG, com base em {c['fonte_nome']}"]
    if foto_info:
        creditos.append(foto_info["credito"])
    y = 980
    for cr in creditos:
        y = escrever(d, (72, y), cr, txt2(28), NAVY, W - 144) + 6
    logo(s, 72, 1180, 0.8)
    numero(d, total, total, NAVY)
    slides.append(s)

    return salvar(slides, pasta, f"cur-{c['id']}"), creditos


# ------------------------------------------------------------ notícia

def _selo_noticia(d, x, y, n):
    if n.get("rumor"):
        return pilula(d, (x, y), "RUMOR · NÃO CONFIRMADO", txt(30), CORAL, NAVY, borda=NAVY)
    return pilula(d, (x, y), "NOTÍCIA", txt(30), ROXO, BRANCO)


def story_noticia(n, pasta):
    """Story 1080×1920. Texto importante longe das bordas (250 px em cima, 340 embaixo)."""
    SW, SH = 1080, 1920
    s = Image.new("RGB", (SW, SH), NAVY if not n.get("rumor") else "#1B1F3B")
    d = ImageDraw.Draw(s)
    logo(s, 72, 260, 1.0)
    pilula(d, (72, 400), n["jogo"].upper()[:30], txt(32), AMARELO, NAVY)
    _selo_noticia(d, 72, 490, n)
    f_t = caber(d, n["titulo"], "Fredoka-Bold.ttf", SW - 144, 520, 120, 64, 1.02)
    y = escrever(d, (72, 620), n["titulo"], f_t, BRANCO, SW - 144, 1.02)
    f_r = caber(d, n["resumo"], "Nunito-ExtraBold.ttf", SW - 144, 1500 - y - 60, 48, 32, 1.3)
    escrever(d, (72, y + 50), n["resumo"], f_r, "#D7DBF0", SW - 144, 1.3)
    d.text((72, 1520), f"Fonte: {n['fonte']}"[:60], font=txt2(32), fill=AMARELO)
    d.text((72, 1570), "Link da fonte no nosso Telegram", font=txt2(30), fill="#C9CEE6")
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"news-{slug(n['titulo'])}.jpg"
    s.save(caminho, "JPEG", quality=85)
    return caminho


def carrossel_noticia(n, pasta):
    """Carrossel 1080×1350 do destaque do dia: capa, resumo, fonte."""
    slides = []
    s = Image.new("RGB", (W, H), ROXO)
    d = ImageDraw.Draw(s)
    if n.get("rumor"):
        pilula(d, (72, 72), f"RUMOR · NÃO CONFIRMADO · {n['jogo'].upper()[:16]}", txt(30), CORAL, NAVY, borda=NAVY)
    else:
        pilula(d, (72, 72), f"NOTÍCIA · {n['jogo'].upper()[:24]}", txt(30), AMARELO, NAVY)
    f_t = caber(d, n["titulo"], "Fredoka-Bold.ttf", W - 144, 820, 140, 70, 1.0)
    escrever(d, (72, 220), n["titulo"], f_t, BRANCO, W - 144, 1.0, stroke_width=8, stroke_fill=NAVY)
    d.text((72, 1220), "Arrasta pro lado »", font=txt(36), fill=BRANCO)
    numero(d, 1, 3, BRANCO)
    slides.append(s)

    s = Image.new("RGB", (W, H), BRANCO)
    d = ImageDraw.Draw(s)
    d.rounded_rectangle([72, 90, 200, 110], radius=10, fill=ROXO)
    f_b = caber(d, n["resumo"], "Nunito-ExtraBold.ttf", W - 144, 900, 80, 40, 1.25)
    alt = len(quebrar(d, n["resumo"], f_b, W - 144)) * int(f_b.size * 1.25)
    escrever(d, (72, max(200, (H - alt) // 2 - 40)), n["resumo"], f_b, NAVY, W - 144, 1.25)
    logo(s, 72, 1180, 0.7)
    numero(d, 2, 3)
    slides.append(s)

    s = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(s)
    d.text((72, 120), "FONTE", font=txt(36), fill=AMARELO)
    escrever(d, (72, 200), n["fonte"], tit(80), BRANCO, W - 144, 1.05)
    dominio = re.sub(r"^https?://(www\.)?", "", n["link"]).split("/")[0]
    d.text((72, 560), dominio, font=txt(40), fill="#C9CEE6")
    escrever(d, (72, 860), "Notícia resumida pelo Arcos. Link completo no nosso Telegram.",
             txt(42), AMARELO, W - 144)
    logo(s, 72, 1180, 0.8)
    numero(d, 3, 3, "#C9CEE6")
    slides.append(s)
    return salvar(slides, pasta, f"news-{slug(n['titulo'])}")


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
    estilo = estilo or rnd.choice(ESTILOS_ARTE)
    paletas = [(ROXO, CORAL), (NAVY, ROXO), (CORAL, AMARELO), ("#1B1F5E", "#FF5D73")]
    c1, c2 = rnd.choice(paletas)
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
