#!/usr/bin/env python3
"""Robô de promoções TCG.

Coleta preços das lojas aprovadas, guarda o histórico, decide o que é promoção
de verdade, descarta o que é suspeito e posta no Telegram e no Instagram.

Uso:
  python bot.py --config config.yaml --simular      # testa sem postar nada
  python bot.py --config config.yaml                # uma rodada (para cron)
  python bot.py --config config.yaml --loop 30      # roda sem parar, a cada 30 min
  python bot.py --diagnostico --testar-lojas        # confere config, tokens e lojas
  python bot.py --etapa preparar | publicar         # duas etapas (GitHub Actions)
"""
import argparse
import json
import logging
import os
import re
import sqlite3
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import yaml

import afiliados
import marketplaces

AVISO_COMPRA = ("ℹ️ O Arcos só mostra promoções. A compra é livre e espontânea, "
                "por decisão de cada um: não forçamos nem incentivamos.")

BASE = Path(__file__).resolve().parent
UA = {
    "User-Agent": "Mozilla/5.0 (compatible; PromoTCGBot/1.0)",
    "Accept-Language": "pt-BR,pt;q=0.9",
}
FUSO = timezone(timedelta(hours=-3))
log = logging.getLogger("promo")


# ---------------------------------------------------------------- utilidades

def agora():
    return datetime.now(FUSO)


def iso(dt):
    return dt.isoformat(timespec="seconds")


def para_float(valor):
    """Converte '1.299,90', '1299.90' ou 1299.9 em 1299.9."""
    if isinstance(valor, (int, float)):
        return float(valor)
    s = str(valor).strip().replace("R$", "").replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    return float(s)


def reais(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------- banco

def abrir_banco(caminho):
    con = sqlite3.connect(caminho)
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS precos(
            produto TEXT, loja TEXT, url TEXT, preco REAL,
            em_estoque INTEGER, imagem TEXT, visto_em TEXT);
        CREATE TABLE IF NOT EXISTS postados(
            produto TEXT, loja TEXT, preco REAL, canal TEXT, postado_em TEXT);
        CREATE INDEX IF NOT EXISTS idx_precos ON precos(produto, loja, visto_em);
        CREATE TABLE IF NOT EXISTS saude(
            loja TEXT PRIMARY KEY, falhas_seguidas INTEGER, ultimo_alerta TEXT);
        """
    )
    return con


# ---------------------------------------------------------------- coleta

LD_RE = re.compile(
    r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", re.S | re.I
)


def _percorrer(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _percorrer(v)
    elif isinstance(o, list):
        for v in o:
            yield from _percorrer(v)


LIGA_LINHA_RE = re.compile(r'<div class="table-produtos-row".*?(?=<div class="table-produtos-row"|$)', re.S)
LIGA_PRECO_RE = re.compile(r'Pre(?:ç|&#231;|&ccedil;)o</div>\s*<div>\s*R\$\s*([\d.]+,\d{2})', re.I)
LIGA_ESTOQUE_RE = re.compile(r'Estoque</div>\s*<div>\s*(\d+)\s*unid', re.I)


def extrair_oferta_liga(html):
    """Lojas na plataforma de e-commerce da rede Liga (?view=ecom/item...), sem JSON-LD.

    Lê a tabela de produtos da página: só linhas "Lacrado" e com estoque > 0.
    Produto em PRÉ-VENDA conta como "sem estoque" (não posta), por segurança.
    Retorna (preco, em_estoque, imagem) ou None.
    """
    pre_venda = re.search(r"encontra em pr[ée][\s-]?(order|venda)|previs[ãa]o de envio", html, re.I)
    i = html.find('class="table-produtos-body"')
    if i < 0:
        return None
    corpo = html[i:]
    fim = corpo.find('<div class="table-produtos-footer')
    corpo = corpo[:fim] if fim > 0 else corpo[:60000]
    precos_ok, precos_todos = [], []
    for linha in LIGA_LINHA_RE.findall(corpo):
        mp = LIGA_PRECO_RE.search(linha)
        if not mp:
            continue
        preco = para_float(mp.group(1))
        precos_todos.append(preco)
        me = LIGA_ESTOQUE_RE.search(linha)
        lacrado = re.search(r">\s*Lacrado\s*<", linha, re.I)
        if lacrado and me and int(me.group(1)) > 0 and not pre_venda:
            precos_ok.append(preco)
    if not precos_todos:
        return None
    og = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html, re.I)
    img = og.group(1) if og else None
    if img and img.startswith("//"):
        img = "https:" + img
    if precos_ok:
        return min(precos_ok), True, img
    return min(precos_todos), False, img


def extrair_oferta(html):
    """Lê o bloco JSON-LD schema.org/Product da página.

    Retorna (preco, em_estoque, imagem) ou None. A maioria das lojas virtuais
    (Nuvemshop, Tray, Shopify, VTEX, WooCommerce) publica esse bloco. Sem ele,
    tenta a plataforma da rede Liga (usada por muitas lojas de TCG no Brasil).
    """
    res = _extrair_jsonld(html)
    return res if res else extrair_oferta_liga(html)


def _extrair_jsonld(html):
    for bloco in LD_RE.findall(html):
        try:
            dados = json.loads(bloco.strip())
        except json.JSONDecodeError:
            continue
        for o in _percorrer(dados):
            tipo = o.get("@type")
            tipos = tipo if isinstance(tipo, list) else [tipo]
            if "Product" not in tipos:
                continue
            ofertas = o.get("offers")
            if isinstance(ofertas, dict):
                ofertas = [ofertas]
            if not ofertas:
                continue
            precos, estoque = [], False
            for of in ofertas:
                if not isinstance(of, dict):
                    continue
                moeda = of.get("priceCurrency", "BRL")
                if moeda and moeda != "BRL":
                    continue
                bruto = of.get("price", of.get("lowPrice"))
                if bruto in (None, ""):
                    continue
                try:
                    precos.append(para_float(bruto))
                except ValueError:
                    continue
                if "InStock" in str(of.get("availability", "")):
                    estoque = True
            if precos:
                img = o.get("image")
                if isinstance(img, list):
                    img = img[0] if img else None
                if isinstance(img, dict):
                    img = img.get("url")
                return min(precos), estoque, img
    return None


# ---------------------------------------------------------------- anti-golpe
TERMOS_SUSPEITOS_PADRAO = [
    "réplica", "replica", "proxy", "custom", "fan made", "fanmade", "repack",
    "lote misterioso", "lote surpresa", "não oficial", "nao oficial", "orica",
    "weighed", "pesado", "falsificad", "imitação", "imitacao", "paralelo", "genérico",
]


def extrair_nome(html):
    """Nome do produto no JSON-LD schema.org/Product (ou o <title>)."""
    for bloco in LD_RE.findall(html or ""):
        try:
            dados = json.loads(bloco.strip())
        except json.JSONDecodeError:
            continue
        for o in _percorrer(dados):
            tipo = o.get("@type")
            tipos = tipo if isinstance(tipo, list) else [tipo]
            if "Product" in tipos and o.get("name"):
                return str(o["name"])
    m = re.search(r"<title[^>]*>(.*?)</title>", html or "", re.S | re.I)
    if not m:
        return ""
    import html as html_lib
    return html_lib.unescape(m.group(1)).split(" | ")[0].strip()


def dominio(url):
    host = re.sub(r"^[a-z]+://", "", (url or "").lower()).split("/", 1)[0].split(":", 1)[0]
    return host[4:] if host.startswith("www.") else host


def na_lista_negra(cfg, url):
    """Devolve o motivo se o domínio (ou um domínio-pai) estiver na lista negra."""
    host = dominio(url)
    for item in (cfg.get("anti_golpe") or {}).get("lista_negra") or []:
        d = dominio(item.get("dominio", "")) if isinstance(item, dict) else dominio(str(item))
        if d and (host == d or host.endswith("." + d)):
            return (item.get("motivo") if isinstance(item, dict) else None) or "lista negra"
    return None


def termo_suspeito(cfg, nome):
    """Devolve o termo suspeito achado no nome do anúncio (réplica, proxy, repack...)."""
    ag = cfg.get("anti_golpe") or {}
    termos = ag.get("termos_suspeitos") or TERMOS_SUSPEITOS_PADRAO
    n = " " + (nome or "").lower() + " "
    for t in termos:
        t = t.lower().strip()
        if t and re.search(r"(?<![a-zà-ú])" + re.escape(t), n):
            return t
    return None


def alerta_golpe(cfg, con, url, motivo):
    """Avisa o admin no Telegram, no máximo 1 vez por dia por endereço."""
    con.execute("CREATE TABLE IF NOT EXISTS alertas_golpe(url TEXT, dia TEXT, motivo TEXT, "
                "PRIMARY KEY(url, dia))")
    dia = agora().date().isoformat()
    if con.execute("SELECT 1 FROM alertas_golpe WHERE url=? AND dia=?", (url, dia)).fetchone():
        return False
    con.execute("INSERT INTO alertas_golpe VALUES (?,?,?)", (url, dia, motivo))
    con.commit()
    try:
        import publicar
        publicar.avisar_admin(cfg, f"🚨 Anti-golpe: anúncio bloqueado\n{motivo}\n{url}\n"
                                   "Não vai para post. Confira e, se for golpe, ponha na lista negra.")
    except Exception as e:  # aviso nunca derruba a coleta
        log.warning("Anti-golpe: não consegui avisar o admin: %s", e)
    return True


def baixar_pagina(url, tentativas=3):
    """Abre a página com até 3 tentativas e espera crescente. Devolve (html, erro)."""
    erro = None
    for n in range(tentativas):
        try:
            r = requests.get(url, headers=UA, timeout=25)
            if r.status_code in (429, 503):  # loja pediu calma
                raise requests.RequestException(f"HTTP {r.status_code}")
            r.raise_for_status()
            return r.text, None
        except requests.RequestException as e:
            erro = str(e)
            time.sleep(5 * (n + 1))
    return None, erro


def registrar_sucesso(con, loja_id):
    con.execute("INSERT INTO saude VALUES (?,0,NULL) ON CONFLICT(loja) DO UPDATE "
                "SET falhas_seguidas=0", (loja_id,))


def registrar_falha(cfg, con, loja, erro):
    """Conta falhas seguidas; com 5 ou mais, avisa o admin (no máximo 1 vez por dia)."""
    con.execute("INSERT INTO saude VALUES (?,1,NULL) ON CONFLICT(loja) DO UPDATE "
                "SET falhas_seguidas=falhas_seguidas+1", (loja["id"],))
    falhas, alerta = con.execute(
        "SELECT falhas_seguidas, ultimo_alerta FROM saude WHERE loja=?",
        (loja["id"],)).fetchone()
    ontem = iso(agora() - timedelta(hours=24))
    if falhas >= 5 and (not alerta or alerta < ontem):
        import publicar
        publicar.avisar_admin(cfg, f"⚠️ Robô Arcos: {falhas} falhas seguidas na loja "
                                   f"{loja['nome']}. Último erro: {erro[:150]}")
        con.execute("UPDATE saude SET ultimo_alerta=? WHERE loja=?",
                    (iso(agora()), loja["id"]))


def coletar(cfg, con):
    lojas = {l["id"]: l for l in cfg["lojas"]}
    pausa = cfg.get("pausa_entre_paginas_seg", 5)
    lidos = 0
    for prod in cfg["produtos"]:
        for item in prod["ofertas"]:
            loja = lojas.get(item["loja"])
            if not loja or not loja.get("aprovada"):
                log.info("Pulando %s: loja não aprovada", item["loja"])
                continue
            golpe = na_lista_negra(cfg, item["url"])
            if golpe:
                log.warning("Anti-golpe: %s está na lista negra (%s)", item["url"], golpe)
                alerta_golpe(cfg, con, item["url"], f"Domínio na lista negra: {golpe}")
                continue
            if loja.get("coleta_automatica") is False:
                continue  # loja bloqueia robôs: só varredura manual (references/varredura-manual.md)
            api = loja.get("api")
            if api in marketplaces.AGUARDANDO_CHAVE:
                log.info("Pulando %s: integração aguardando %s", loja["id"],
                         marketplaces.AGUARDANDO_CHAVE[api])
                continue
            if loja.get("so_acessorios") and prod.get("tipo") != "acessorio":
                log.warning("Anti-golpe: %s só pode ser usada para acessórios (%s)", loja["id"], prod["nome"])
                continue
            if api == "mercadolivre":
                res, erro = marketplaces.ml_oferta(item["url"], loja)
                if res:
                    preco, estoque, img, titulo, selo = res
                    termo = termo_suspeito(cfg, titulo)
                    if termo:
                        alerta_golpe(cfg, con, item["url"],
                                     f"Termo suspeito no anúncio: \"{termo}\" ({prod['nome']})")
                        continue
                    res = (preco, estoque, img)
                elif erro and erro.startswith("barrado"):
                    log.warning("Mercado Livre %s: %s", item["url"], erro)
                    continue
                html = None
            else:
                html, erro = baixar_pagina(item["url"])
                res = None
            if html:
                termo = termo_suspeito(cfg, extrair_nome(html))
                if termo:
                    log.warning("Anti-golpe: '%s' no anúncio %s", termo, item["url"])
                    alerta_golpe(cfg, con, item["url"],
                                 f"Termo suspeito no anúncio: \"{termo}\" ({prod['nome']})")
                    continue
            if html:
                res = extrair_oferta(html)
            if not res:
                erro = erro or "sem preço legível (a loja pode ter mudado o site)"
                log.warning("Falha em %s: %s", item["url"], erro)
                registrar_falha(cfg, con, loja, erro)
                continue
            registrar_sucesso(con, loja["id"])
            preco, estoque, img = res
            con.execute(
                "INSERT INTO precos VALUES (?,?,?,?,?,?,?)",
                (prod["nome"], loja["id"], item["url"], preco, int(estoque),
                 img, iso(agora())),
            )
            lidos += 1
            time.sleep(pausa)
    con.commit()
    log.info("Coleta concluída: %d preços lidos", lidos)


# ---------------------------------------------------------------- análise

def preco_referencia(con, prod, dias, minimo_leituras):
    if prod.get("referencia_manual"):
        return float(prod["referencia_manual"])
    desde = iso(agora() - timedelta(days=dias))
    precos = [
        p for (p,) in con.execute(
            "SELECT preco FROM precos WHERE produto=? AND visto_em>=? "
            "AND em_estoque=1", (prod["nome"], desde))
    ]
    if len(precos) < minimo_leituras:
        return None  # pouco histórico: não dá para afirmar que é promoção
    return statistics.median(precos)


def ultimas_leituras(con, produto, loja, n=2):
    return con.execute(
        "SELECT preco, em_estoque, url, imagem, visto_em FROM precos "
        "WHERE produto=? AND loja=? ORDER BY visto_em DESC LIMIT ?",
        (produto, loja, n),
    ).fetchall()


def ja_postado(con, produto, loja, preco, canal, horas):
    desde = iso(agora() - timedelta(hours=horas))
    return con.execute(
        "SELECT 1 FROM postados WHERE produto=? AND loja=? AND canal=? "
        "AND preco<=? AND postado_em>=?",
        (produto, loja, canal, preco, desde),
    ).fetchone() is not None


def avaliar(cfg, con):
    """Devolve (aprovadas, descartadas). Uma aprovada por produto: a mais barata."""
    r = cfg["regras"]
    lojas = {l["id"]: l for l in cfg["lojas"]}
    import cupons
    # cupons do config + cupons achados pelo robô e testados pelo admin (/cupom_ok)
    cfg_cupons = {**cfg, "cupons": (cfg.get("cupons") or []) + cupons.cupons_aprovados(con)}
    conf_min = r.get("confianca_minima", 3)
    aprovadas, descartadas = [], []
    for prod in cfg["produtos"]:
        ref = preco_referencia(con, prod, r["dias_historico"], r["minimo_leituras"])
        candidatas = []
        for loja_id in {o["loja"] for o in prod["ofertas"]}:
            loja = lojas.get(loja_id)
            if not loja or not loja.get("aprovada"):
                continue
            leit = ultimas_leituras(con, prod["nome"], loja_id)
            if not leit:
                continue
            preco, estoque, url, img, visto = leit[0]
            motivo = None
            golpe = na_lista_negra(cfg, url) or na_lista_negra(cfg, loja.get("site", ""))
            if golpe:
                motivo = f"anti-golpe: lista negra ({golpe})"
            elif not estoque:
                motivo = "sem estoque"
            elif len(leit) < 2 or abs(leit[1][0] - preco) > 0.01:
                motivo = "preço ainda não confirmado em 2 leituras seguidas"
            elif ref is None:
                motivo = "histórico insuficiente para saber o preço normal"
            elif preco < ref * (1 - r["alerta_suspeito"]):
                motivo = (f"preço suspeito: {reais(preco)} está mais de "
                          f"{int(r['alerta_suspeito']*100)}% abaixo da referência")
            elif preco > ref * (1 - r["desconto_minimo"]):
                motivo = "desconto pequeno demais"
            elif loja.get("confianca", 3) < conf_min:
                motivo = f"loja com nota de confiança {loja.get('confianca')} (mínimo {conf_min})"
            link, eh_afiliado = afiliados.link_afiliado(loja, url)
            cupom = afiliados.cupom_valido(cfg_cupons, loja_id)
            preco_final = afiliados.preco_com_cupom(preco, cupom)
            item = {
                "produto": prod["nome"], "jogo": prod.get("jogo", ""),
                "loja": loja_id, "loja_nome": loja["nome"], "preco": preco,
                "ref": ref, "url": url, "link": link, "imagem": img, "visto": visto,
                "descricao": prod.get("descricao", "Lacrado"),
                "afiliado": eh_afiliado, "cupom": cupom, "preco_final": preco_final,
                "confianca": loja.get("confianca", 3),
                "bandeira": prod.get("bandeira", ""), "unidades": prod.get("unidades"),
                "unidade_nome": prod.get("unidade_nome", "unidades"),
                "unidade_singular": prod.get("unidade_singular", "unidade"),
                "reputacao": loja.get("reputacao", ""),
                "frete_gratis": prod.get("frete_gratis", loja.get("frete_gratis", False)),
            }
            if motivo:
                descartadas.append({**item, "motivo": motivo})
            else:
                candidatas.append(item)
        if candidatas:  # a mais barata com cupom; empate: a loja mais confiável
            aprovadas.append(min(candidatas, key=lambda x: (x["preco_final"], -x["confianca"])))
    aprovadas.sort(key=lambda x: x["preco_final"] / x["ref"])  # maior economia primeiro
    return aprovadas, descartadas


# ---------------------------------------------------------------- textos

def texto_telegram(o):
    """Formato de oferta direto ao ponto: título, De/Por, preço por unidade, cupom, loja, link.

    Só escreve o que o robô conferiu. Nada de "últimas unidades" ou "acaba hoje" sem prova.
    """
    desc = round((1 - o["preco"] / o["ref"]) * 100)
    hora = datetime.fromisoformat(o["visto"]).strftime("%d/%m, %H:%M")
    final = o.get("preco_final", o["preco"])
    from html import escape
    o = {**o, "produto": escape(o["produto"]), "loja_nome": escape(o["loja_nome"]),
         "reputacao": escape(o.get("reputacao") or "")}
    titulo = f"{o.get('bandeira', '')} {o['produto'].upper()}".strip()
    linhas = [f"🔥 {titulo}"]
    if o.get("unidades"):
        linhas.append(f"({o['unidades']} {o.get('unidade_nome', 'unidades')})")
    linhas += ["", f"De: <s>{reais(o['ref'])}</s> Por: <b>{reais(o['preco'])}</b>",
               f"<b>{desc}% abaixo do preço normal</b>"]
    if o.get("unidades"):
        linhas.append(f"Cada {o.get('unidade_singular', 'unidade')} sai por <b>{reais(final / o['unidades'])}</b>")
    linhas.append("")
    if o.get("cupom"):
        c = o["cupom"]
        linhas.append(f"🎟️ Cupom: <b>{c['codigo']}</b> ({c.get('descricao', 'desconto extra')}, "
                      f"até {datetime.fromisoformat(str(c['valido_ate'])):%d/%m})")
        if final < o["preco"]:
            linhas.append(f"💸 Com o cupom: <b>{reais(final)}</b>*")
    vend = f" ({o['reputacao']})" if o.get("reputacao") else ""
    linhas.append(f"🏪 Loja: <b>{o['loja_nome']}</b>{vend} ✅ verificada pelo Arcos")
    if o.get("frete_gratis"):
        linhas.append("🚚 Frete grátis")
    linhas += ["", f"🛒 Compre aqui: {o.get('link') or o['url']}", "",
               f"⏰ Preço conferido em {hora}. Pode mudar a qualquer momento."]
    if o.get("cupom") and final < o["preco"]:
        linhas.append("*Confira as regras do cupom na loja.")
    linhas.append(f"📷 Imagem: {o['loja_nome']}" + (" · 🔗 Link de afiliado" if o["afiliado"] else ""))
    linhas.append(AVISO_COMPRA)
    return "\n".join(linhas)


def texto_instagram(o, cfg):
    desc = round((1 - o["preco"] / o["ref"]) * 100)
    hora = datetime.fromisoformat(o["visto"]).strftime("%d/%m às %H:%M")
    tags = " ".join(cfg["instagram"].get("hashtags", []))
    cup = (f"🎟️ Cupom {o['cupom']['codigo']}: {o['cupom'].get('descricao', 'desconto extra')}\n"
           if o.get("cupom") else "")
    afil = f"\nImagem do produto: {o['loja_nome']}."
    afil += "\nLink de afiliado." if o["afiliado"] else ""
    return (
        f"🔥 {o['produto']}\n\n"
        f"💰 {reais(o['preco'])} na {o['loja_nome']} (−{desc}% do preço normal)\n"
        f"📦 {o['descricao']}\n{cup}\n"
        f"Link no nosso Telegram (está na bio).\n"
        f"Preço conferido em {hora} e pode mudar a qualquer momento.{afil}\n"
        f"{AVISO_COMPRA}\n\n"
        f"{tags}"
    ).strip()


# ---------------------------------------------------------------- postagem

FILA = BASE / "fila.json"
PASTA_IMG = BASE / "imagens"


def posts_hoje(con, canal):
    desde = iso(agora() - timedelta(hours=24))
    return con.execute(
        "SELECT COUNT(*) FROM postados WHERE canal=? AND postado_em>=?",
        (canal, desde)).fetchone()[0]


def canais(cfg):
    r = cfg["regras"]
    lista = []
    if cfg["telegram"].get("ativo"):
        lista.append(("telegram", r["max_posts_telegram_dia"]))
    if cfg["instagram"].get("ativo"):
        lista.append(("instagram", r["max_posts_instagram_dia"]))
    return lista


def preparar(cfg, con, aprovadas):
    """Gera os carrosséis das ofertas que ainda vão ser postadas e grava a fila."""
    import carrossel
    import imagens
    r = cfg["regras"]
    limite = time.time() - 7 * 86400  # apaga imagens com mais de 7 dias
    for velho in PASTA_IMG.glob("*.jpg"):
        if velho.stat().st_mtime < limite:
            velho.unlink()
    fila = []
    for o in aprovadas:
        destinos = [c for c, _ in canais(cfg)
                    if not ja_postado(con, o["produto"], o["loja"], o["preco"], c,
                                      r["nao_repetir_horas"])]
        if not destinos:
            continue
        foto = imagens.baixar(o["imagem"]) if o.get("imagem") else None
        slides, creditos = carrossel.carrossel_promocao(o, foto, PASTA_IMG)
        fila.append({**o, "slides": [str(x) for x in slides],
                     "creditos": creditos, "destinos": destinos})
    FILA.write_text(json.dumps(fila, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("Fila preparada: %d carrosséis", len(fila))
    return fila


def publicar_fila(cfg, con, simular):
    import publicar
    if not FILA.exists():
        return
    fila = json.loads(FILA.read_text(encoding="utf-8"))
    limites = dict(canais(cfg))
    for o in fila:
        for canal in o["destinos"]:
            if canal not in limites or posts_hoje(con, canal) >= limites[canal]:
                continue
            if simular:
                print(f"\n--- [{canal.upper()} | SIMULAÇÃO] {len(o['slides'])} slides: "
                      f"{', '.join(Path(x).name for x in o['slides'])}")
                print(re.sub(r"</?[bs]>", "", texto_telegram(o)) if canal == "telegram" else texto_instagram(o, cfg))
                continue
            try:
                if canal == "telegram":
                    publicar.telegram_album(cfg, o["slides"], texto_telegram(o), html=True)
                else:
                    publicar.instagram_carrossel(cfg, o["slides"], texto_instagram(o, cfg))
            except Exception as e:  # um canal com erro não derruba o outro
                log.error("Erro ao postar no %s: %s", canal, e)
                continue
            con.execute("INSERT INTO postados VALUES (?,?,?,?,?)",
                        (o["produto"], o["loja"], o["preco"], canal, iso(agora())))
            con.commit()
            log.info("Carrossel postado no %s: %s por %s", canal, o["produto"], reais(o["preco"]))
            time.sleep(5)
    if not simular:
        FILA.unlink()


# ---------------------------------------------------------------- execução

def aviso_diario_cupons(cfg, con):
    """Uma vez por dia, avisa o admin sobre cupons vencendo ou sem teste recente."""
    linha = con.execute("SELECT ultimo_alerta FROM saude WHERE loja='__cupons__'").fetchone()
    hoje = agora().date().isoformat()
    if linha and linha[0] and linha[0][:10] == hoje:
        return
    import cupons
    avisos = afiliados.cupons_vencendo({**cfg, "cupons": (cfg.get("cupons") or [])
                                        + cupons.cupons_aprovados(con)})
    if avisos:
        import publicar
        publicar.avisar_admin(cfg, "🎟️ Cupons do Arcos:\n" + "\n".join(avisos))
    con.execute("INSERT INTO saude VALUES ('__cupons__',0,?) ON CONFLICT(loja) DO UPDATE "
                "SET ultimo_alerta=excluded.ultimo_alerta", (iso(agora()),))
    con.commit()


def diagnostico(cfg, testar_lojas=False):
    """Confere a configuração e mostra o que falta para o robô funcionar."""
    ok, falta = [], []
    (ok if os.environ.get("TELEGRAM_TOKEN") else falta).append("TELEGRAM_TOKEN definido")
    if cfg["instagram"].get("ativo"):
        (ok if os.environ.get("INSTAGRAM_TOKEN") else falta).append("INSTAGRAM_TOKEN definido")
        (ok if cfg.get("curiosidades", {}).get("url_publica_imagens") else falta).append(
            "curiosidades.url_publica_imagens (link público das imagens)")
    (ok if cfg["telegram"].get("admin_chat") else falta).append("telegram.admin_chat (alertas)")
    aprovadas = [l for l in cfg["lojas"] if l.get("aprovada")]
    (ok if aprovadas else falta).append(f"{len(aprovadas)} loja(s) aprovada(s)")
    com_afiliado = [l["nome"] for l in aprovadas if l.get("link_afiliado")]
    (ok if com_afiliado else falta).append(
        f"lojas com link de afiliado: {', '.join(com_afiliado) or 'nenhuma (sem comissão!)'}")
    (ok if cfg.get("produtos") else falta).append(f"{len(cfg.get('produtos', []))} produto(s)")
    nt = cfg.get("noticias", {})
    if nt.get("ativo"):
        prov = nt.get("ia", {}).get("provedor", "nenhum")
        chave = {"gemini": "GEMINI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}.get(prov)
        if chave:
            (ok if os.environ.get(chave) else falta).append(f"{chave} (resumo e tradução das notícias)")
        else:
            falta.append("noticias.ia.provedor: sem IA, só fontes em português são postadas")
        (ok if nt.get("fontes") else falta).append(f"{len(nt.get('fontes', []))} fonte(s) de notícias "
                                                   "(teste com: python noticias.py --testar-fontes)")
    rd = cfg.get("radar", {})
    if rd.get("ativo"):
        (ok if rd.get("canais") else falta).append(f"{len(rd.get('canais', []))} canal(is) no radar")
    print("OK:", *[f"  ✔ {x}" for x in ok], sep="\n")
    print("FALTA:", *[f"  ✘ {x}" for x in falta] or ["  nada"], sep="\n")
    for aviso in afiliados.cupons_vencendo(cfg):
        print("  ⚠", aviso)
    if testar_lojas:
        lojas = {l["id"]: l for l in aprovadas}
        vistos = set()
        for prod in cfg.get("produtos", []):
            for item in prod["ofertas"]:
                if item["loja"] in lojas and item["loja"] not in vistos:
                    vistos.add(item["loja"])
                    html, erro = baixar_pagina(item["url"], tentativas=1)
                    res = extrair_oferta(html) if html else None
                    estado = f"preço {reais(res[0])}" if res else f"NÃO LEU ({erro or 'sem JSON-LD'})"
                    print(f"  loja {lojas[item['loja']]['nome']}: {estado}")


def rodada(cfg, con, simular, etapa="tudo"):
    if etapa in ("tudo", "preparar"):
        if not simular:
            aviso_diario_cupons(cfg, con)
        coletar(cfg, con)
        aprovadas, descartadas = avaliar(cfg, con)
        log.info("Aprovadas: %d | Descartadas: %d", len(aprovadas), len(descartadas))
        for d in descartadas:
            log.info("Descartado: %s na %s: %s", d["produto"], d["loja_nome"], d["motivo"])
        preparar(cfg, con, aprovadas)
    if etapa in ("tudo", "publicar"):
        publicar_fila(cfg, con, simular)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(BASE / "config.yaml"))
    ap.add_argument("--simular", action="store_true", help="não posta, só mostra")
    ap.add_argument("--etapa", choices=["tudo", "preparar", "publicar"], default="tudo",
                    help="preparar = coleta e gera os carrosséis; publicar = posta a fila")
    ap.add_argument("--diagnostico", action="store_true",
                    help="confere a configuração (com --testar-lojas, abre uma página de cada loja)")
    ap.add_argument("--testar-lojas", action="store_true")
    ap.add_argument("--loop", type=int, metavar="MIN",
                    help="repete a cada MIN minutos, sem parar")
    a = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(),
                  logging.FileHandler(BASE / "bot.log", encoding="utf-8")],
    )
    with open(a.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if a.diagnostico:
        diagnostico(cfg, a.testar_lojas)
        return
    con = abrir_banco(BASE / cfg.get("banco", "precos.db"))

    if not a.loop:
        rodada(cfg, con, a.simular, a.etapa)
        return
    if a.loop < 15:
        sys.exit("Use pelo menos 15 minutos: menos que isso pode fazer as lojas bloquearem o robô.")
    while True:
        try:
            rodada(cfg, con, a.simular)
        except Exception as e:
            log.exception("Rodada falhou: %s", e)
        time.sleep(a.loop * 60)


if __name__ == "__main__":
    main()
